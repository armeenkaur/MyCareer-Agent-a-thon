from __future__ import annotations

from typing import Any
from ..agents.llm import normalize_proficiency
from ..core.config import PROFICIENCY_ORDER, PROFICIENCY_VALUE, UPLOAD_DIR
from ..core.logging_setup import get_logger
from ..database import Database, FEEDBACK_QUESTION, KUDOS_PRESET, PHASES, PHASE_FREE_ROLES, ist_today, utc_now
from .errors import BackendError
log = get_logger('skillsync.backend')

class AssessmentsMixin:
    def assessment(self, employee_code: str, role: str) -> dict[str, Any] | None:
        with self.db.connect() as connection:
            row = connection.execute(
                "SELECT * FROM assessments WHERE employee_code=? AND assessor_role=?", (employee_code, role)
            ).fetchone()
            if not row:
                return None
            ratings = connection.execute(
                "SELECT competency,proficiency,note FROM assessment_ratings WHERE assessment_id=? ORDER BY competency",
                (row["id"],),
            ).fetchall()
        result = dict(row)
        result["ratings"] = {rating["competency"]: rating["proficiency"] for rating in ratings}
        result["notes"] = {rating["competency"]: rating["note"] for rating in ratings if rating["note"]}
        result["career_recommendation"] = str(result.get("career_recommendation") or "")
        return result


    def career_move_options(self, user: dict[str, Any], employee_code: str) -> dict[str, Any]:
        if user["role"] not in {"zm", "rd", "admin"}:
            raise BackendError("ZM, RD, or Admin access required.", "forbidden", 403)
        if user["role"] in {"zm", "rd"}:
            self._assert_employee_scope(user, employee_code)
        employee = self.employee(employee_code)
        return {
            "employee_code": employee_code,
            "question": "What career move do you recommend for the employee?",
            "options": self.data.manager_career_move_options(employee),
        }


    def save_assessment(
        self,
        user: dict[str, Any],
        employee_code: str,
        ratings: dict[str, str],
        notes: dict[str, str] | None = None,
        submit: bool = False,
        career_recommendation: str = "",
        require_career_move: bool = True,
    ) -> dict[str, Any]:
        role = user["role"]
        if role not in {"zm", "rd"}:
            raise BackendError("ZM or RD access required.", "forbidden", 403)
        if not self.phase_is_open(role):
            raise BackendError("Assessment phase is closed.", "phase_closed", 403)
        self._assert_employee_scope(user, employee_code)
        if role == "rd":
            zm_assessment = self.assessment(employee_code, "zm")
            if not zm_assessment or zm_assessment["status"] != "submitted":
                raise BackendError(
                    "ZM assessment must be submitted before RD validation.",
                    "zm_assessment_required",
                    409,
                )
        self._validate_ratings(ratings, complete=submit)
        recommendation = str(career_recommendation or "").strip().lower()
        if submit and require_career_move:
            self._validate_career_recommendation(employee_code, recommendation)
        elif recommendation:
            self._validate_career_recommendation(employee_code, recommendation)
        if submit and role == "zm":
            self._validate_ai_override_notes(employee_code, ratings, notes or {}, "zm_suggested_rating")
        if submit and role == "rd":
            self._validate_ai_override_notes(employee_code, ratings, notes or {}, "suggested_rating")
        existing = self.assessment(employee_code, role)
        if existing and existing["status"] == "submitted":
            raise BackendError("Submitted assessment is locked.", "assessment_locked", 409)
        if not recommendation and existing:
            recommendation = str(existing.get("career_recommendation") or "")
        now = utc_now()
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO assessments(
                    employee_code,assessor_role,assessor_login_id,status,created_at,updated_at,submitted_at,career_recommendation
                )
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(employee_code,assessor_role) DO UPDATE SET
                    assessor_login_id=excluded.assessor_login_id,status=excluded.status,
                    updated_at=excluded.updated_at,submitted_at=excluded.submitted_at,
                    career_recommendation=excluded.career_recommendation
                """,
                (
                    employee_code,
                    role,
                    user["login_id"],
                    "submitted" if submit else "draft",
                    now,
                    now,
                    now if submit else None,
                    recommendation,
                ),
            )
            assessment_id = connection.execute(
                "SELECT id FROM assessments WHERE employee_code=? AND assessor_role=?", (employee_code, role)
            ).fetchone()[0]
            for competency, proficiency in ratings.items():
                connection.execute(
                    """
                    INSERT INTO assessment_ratings(assessment_id,competency,proficiency,note) VALUES(?,?,?,?)
                    ON CONFLICT(assessment_id,competency) DO UPDATE SET proficiency=excluded.proficiency,note=excluded.note
                    """,
                    (assessment_id, competency, proficiency, (notes or {}).get(competency, "")),
                )
        if submit and self.phase_progress(role)["is_complete"]:
            with self.db.transaction() as connection:
                connection.execute("UPDATE phases SET status='complete', closed_at=? WHERE phase=?", (utc_now(), role))
        if submit and role == "rd":
            try:
                self.precompute_recommendations(employee_code)
            except Exception:  # noqa: BLE001
                log.exception("Course precomputation failed employee=%s", employee_code)
        return self.assessment(employee_code, role) or {}

    def _validate_ai_override_notes(
        self,
        employee_code: str,
        ratings: dict[str, str],
        notes: dict[str, str],
        suggestion_key: str,
    ) -> None:
        """When assessor overrides an AI suggested rating, a note is required for that competency."""
        missing: list[str] = []
        for competency, proficiency in ratings.items():
            cached = self._cached_evidence(employee_code, competency)
            if not isinstance(cached, dict):
                continue
            suggested = str(cached.get(suggestion_key) or "").strip()
            if suggested not in {"Beginner", "Intermediate", "Proficient", "Advanced"}:
                continue
            if proficiency == suggested:
                continue
            note = str(notes.get(competency) or "").strip()
            if not note:
                missing.append(competency)
        if missing:
            raise BackendError(
                "Add a note for each competency where your rating differs from the AI suggestion: "
                + ", ".join(missing),
                "note_required",
                422,
            )

    def download_assessment_template(self, user: dict[str, Any]) -> tuple[bytes, str]:
        """Excel template: scoped incomplete employees + competency columns with dropdowns."""
        from io import BytesIO

        from openpyxl import Workbook
        from openpyxl.worksheet.datavalidation import DataValidation

        role = user.get("role")
        if role not in {"zm", "rd"}:
            raise BackendError("ZM or RD access required.", "forbidden", 403)
        if not self.phase_is_open(role):
            raise BackendError("Assessment phase is closed.", "phase_closed", 403)

        rows = self._template_employee_rows(user)
        wb = Workbook()
        ws = wb.active
        ws.title = "Ratings"
        headers = ["Employee Code", "Employee Name", *self.competencies]
        ws.append(headers)
        for row in rows:
            code = row["employee_code"]
            draft = self.assessment(code, role)
            ratings = (draft or {}).get("ratings") or {}
            ws.append([code, row.get("name") or "", *[ratings.get(comp, "") for comp in self.competencies]])

        # Dropdowns for proficiency columns (C onward).
        if rows:
            from openpyxl.utils import get_column_letter

            first_data = 2
            last_data = 1 + len(rows)
            levels = ",".join(PROFICIENCY_ORDER)
            for index in range(3, 3 + len(self.competencies)):
                col = get_column_letter(index)
                dv = DataValidation(
                    type="list",
                    formula1=f'"{levels}"',
                    allow_blank=True,
                    showDropDown=False,
                )
                dv.error = "Pick Beginner, Intermediate, Proficient, or Advanced"
                dv.errorTitle = "Invalid proficiency"
                ws.add_data_validation(dv)
                dv.add(f"{col}{first_data}:{col}{last_data}")

        ws.append([])
        ws.append(["Instructions"])
        ws.append(["1. Fill proficiency for each competency using the dropdown."])
        ws.append(["2. Leave a cell blank to skip that competency."])
        ws.append(["3. Fill all seven competencies to submit; partial rows save as draft."])
        ws.append(["4. Already submitted employees are excluded from this template."])
        if role == "rd":
            ws.append(["5. RD template only includes employees whose ZM assessment is submitted."])

        buffer = BytesIO()
        wb.save(buffer)
        filename = f"{role.upper()}_ratings_template.xlsx"
        return buffer.getvalue(), filename


    def upload_assessment_workbook(
        self,
        user: dict[str, Any],
        filename: str,
        payload: bytes,
    ) -> dict[str, Any]:
        """Parse uploaded ratings workbook/CSV and apply via save_assessment."""
        role = user.get("role")
        if role not in {"zm", "rd"}:
            raise BackendError("ZM or RD access required.", "forbidden", 403)
        if not self.phase_is_open(role):
            raise BackendError("Assessment phase is closed.", "phase_closed", 403)
        if not payload:
            raise BackendError("Uploaded file is empty.")

        records = self._parse_assessment_upload(filename, payload)
        scope = {row["employee_code"] for row in self.scoped_employees(user)}
        applied: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for record in records:
            code = record["employee_code"]
            ratings = record["ratings"]
            if code not in scope:
                errors.append({"employee_code": code, "message": "Outside your reporting scope."})
                continue
            if not ratings:
                skipped.append({"employee_code": code, "message": "No proficiency values filled."})
                continue
            existing = self.assessment(code, role)
            if existing and existing.get("status") == "submitted":
                skipped.append({"employee_code": code, "message": "Already submitted and locked."})
                continue
            if role == "rd":
                zm = self.assessment(code, "zm")
                if not zm or zm.get("status") != "submitted":
                    errors.append({"employee_code": code, "message": "ZM assessment not submitted yet."})
                    continue
            submit = set(ratings.keys()) == set(self.competencies)
            try:
                result = self.save_assessment(
                    user, code, ratings, notes={}, submit=submit, require_career_move=False
                )
                applied.append(
                    {
                        "employee_code": code,
                        "status": result.get("status"),
                        "ratings_count": len(ratings),
                        "submitted": submit,
                    }
                )
            except BackendError as exc:
                errors.append({"employee_code": code, "message": exc.message})

        return {
            "applied": applied,
            "skipped": skipped,
            "errors": errors,
            "summary": {
                "applied": len(applied),
                "skipped": len(skipped),
                "errors": len(errors),
                "total_rows": len(records),
            },
        }


    def _template_employee_rows(self, user: dict[str, Any]) -> list[dict[str, Any]]:
        role = user["role"]
        rows = []
        for employee in sorted(self.employee_summaries(user), key=lambda row: str(row.get("name") or "").lower()):
            status_key = "zm_status" if role == "zm" else "rd_status"
            if employee.get(status_key) == "submitted":
                continue
            if role == "rd" and employee.get("zm_status") != "submitted":
                continue
            rows.append(employee)
        return rows


    def _parse_assessment_upload(self, filename: str, payload: bytes) -> list[dict[str, Any]]:
        name = str(filename or "").lower()
        if name.endswith(".csv"):
            return self._parse_assessment_csv(payload)
        return self._parse_assessment_xlsx(payload)


    def _parse_assessment_xlsx(self, payload: bytes) -> list[dict[str, Any]]:
        from io import BytesIO

        from openpyxl import load_workbook

        try:
            wb = load_workbook(BytesIO(payload), data_only=True, read_only=True)
        except Exception as exc:  # noqa: BLE001
            raise BackendError("Could not read Excel file. Upload a valid .xlsx template.") from exc
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        try:
            header_row = next(rows_iter)
        except StopIteration:
            raise BackendError("Workbook is empty.")
        return self._records_from_header_rows(header_row, rows_iter)


    def _parse_assessment_csv(self, payload: bytes) -> list[dict[str, Any]]:
        import csv
        from io import StringIO

        try:
            text = payload.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise BackendError("CSV must be UTF-8 encoded.") from exc
        reader = csv.reader(StringIO(text))
        try:
            header_row = next(reader)
        except StopIteration:
            raise BackendError("CSV is empty.")
        return self._records_from_header_rows(header_row, reader)


    def _records_from_header_rows(self, header_row: Any, data_rows: Any) -> list[dict[str, Any]]:
        headers = [str(cell or "").strip() for cell in header_row]
        if not headers or headers[0].lower() not in {"employee code", "employee_code", "emp code", "emp_code"}:
            raise BackendError("First column must be Employee Code.")
        # Map competency headers (exact or case-insensitive).
        comp_index: dict[int, str] = {}
        lower_map = {name.lower(): name for name in self.competencies}
        for index, header in enumerate(headers[2:], start=2):
            key = header.lower()
            if key in lower_map:
                comp_index[index] = lower_map[key]
            elif header in self.competencies:
                comp_index[index] = header
        if not comp_index:
            raise BackendError("No competency columns found. Download a fresh template.")

        records: list[dict[str, Any]] = []
        for raw in data_rows:
            cells = list(raw)
            if not cells:
                continue
            code = str(cells[0] or "").strip()
            if not code or code.lower().startswith("instruction"):
                continue
            # Stop at instruction block.
            if code.lower() == "instructions":
                break
            ratings: dict[str, str] = {}
            for index, competency in comp_index.items():
                if index >= len(cells):
                    continue
                level = normalize_proficiency(cells[index])
                if level:
                    ratings[competency] = level
            records.append({"employee_code": code, "ratings": ratings})
        if not records:
            raise BackendError("No employee rows found in the upload.")
        return records

