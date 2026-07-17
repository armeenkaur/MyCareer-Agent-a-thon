from __future__ import annotations

from datetime import datetime
from typing import Any

from openpyxl import load_workbook

from .core.config import SOURCE_FILES
from .core.utils import clean, role_level_key


class WorkbookData:
    """Loads the attached workbooks as configurable master and evidence data."""

    def __init__(self) -> None:
        self.generated_at = datetime.now()
        self.competencies = self._load_competencies()
        self.level_definitions = self._load_level_definitions()
        self.roleplay_links = self._load_roleplay_links()
        self.employees = self._load_employees()
        self.tna = self._load_tna()
        self.appraisal = self._load_appraisal()
        self.interview = self._load_interview()
        self.amber = self._load_amber()
        self.courses = self._load_courses()

    @property
    def functional_skills(self) -> list[str]:
        return [row["skill"] for row in self.competencies if row["tag"] == "Functional"]

    @property
    def behavioral_skills(self) -> list[str]:
        return [row["skill"] for row in self.competencies if row["tag"] == "Behavioral"]

    def employee_options(self) -> list[dict[str, Any]]:
        return sorted(self.employees.values(), key=lambda item: item["code"])

    def managers(self) -> list[str]:
        names = {emp.get("manager") for emp in self.employees.values() if emp.get("manager")}
        return sorted(names)

    def manager_accounts(self) -> list[dict[str, str]]:
        accounts: dict[str, dict[str, str]] = {}
        for employee in self.employees.values():
            code = employee.get("manager_code", "")
            if code:
                accounts[code] = {"code": code, "name": employee.get("manager", "")}
        return sorted(accounts.values(), key=lambda row: row["code"])

    def rd_accounts(self) -> list[dict[str, str]]:
        accounts: dict[str, dict[str, str]] = {}
        for employee in self.employees.values():
            code = employee.get("rd_code", "")
            if code:
                accounts[code] = {"code": code, "name": employee.get("rd", "")}
        return sorted(accounts.values(), key=lambda row: row["code"])

    def team_for_manager(self, manager: str | None) -> list[dict[str, Any]]:
        if not manager:
            return self.employee_options()
        return [emp for emp in self.employee_options() if emp.get("manager") == manager]

    def team_for_manager_code(self, manager_code: str) -> list[dict[str, Any]]:
        return [emp for emp in self.employee_options() if emp.get("manager_code") == manager_code]

    def team_for_rd_code(self, rd_code: str) -> list[dict[str, Any]]:
        return [emp for emp in self.employee_options() if emp.get("rd_code") == rd_code]

    def ideal_for_employee(self, emp_code: str) -> dict[str, str]:
        employee = self.employees.get(emp_code, {})
        key = role_level_key(employee.get("designation", ""), employee.get("level", ""))
        return self.ideal_for_role_key(key)

    def ideal_for_role_key(self, key: str) -> dict[str, str]:
        ideal: dict[str, str] = {}
        for row in self.competencies:
            ideal[row["skill"]] = row["ideals"].get(key) or row["ideals"].get("BDM (RL2-3)") or "Intermediate"
        return ideal

    def _load_competencies(self) -> list[dict[str, Any]]:
        wb = load_workbook(SOURCE_FILES["competency"], data_only=True, read_only=True)
        sheet_name = "Role-Competency Mapping" if "Role-Competency Mapping" in wb.sheetnames else "Competency"
        ws = wb[sheet_name]
        headers = [str(cell.value or "").strip() for cell in next(ws.iter_rows(min_row=1, max_row=1))]
        rows: list[dict[str, Any]] = []
        start_row = 2 if sheet_name == "Role-Competency Mapping" else 3
        for cells in ws.iter_rows(min_row=start_row, values_only=True):
            if not cells[0] or not cells[1]:
                continue
            ideals = {}
            ideal_start = 3 if sheet_name == "Role-Competency Mapping" else 4
            for idx, header in enumerate(headers[ideal_start:], start=ideal_start):
                if header and cells[idx]:
                    value = str(cells[idx]).strip()
                    if value.upper() != "NA":
                        ideals[self._normalize_role_key(header)] = value
            rows.append(
                {
                    "skill": str(cells[0]).strip(),
                    "tag": str(cells[1]).strip(),
                    "definition": str(cells[2] or "").strip(),
                    "sales_note": str(cells[2] or "").strip(),
                    "product_note": "" if sheet_name == "Role-Competency Mapping" else str(cells[3] or "").strip(),
                    "ideals": ideals,
                }
            )
        return rows

    @staticmethod
    def _normalize_role_key(value: str) -> str:
        text = str(value).strip().replace(" ", "")
        aliases = {
            "BDM(RL2-3)": "BDM (RL2-3)",
            "BDM(RL4)": "BDM (RL4)",
            "KAM(RL2-3)": "KAM (RL2-3)",
            "KAM(RL4)": "KAM (RL4)",
            "ZM(RL4-5)": "ZM (RL4-5)",
            "ZM(RL6)": "ZM (RL6)",
            "RD(RL7-8)": "RD (RL7-8)",
        }
        return aliases.get(text, str(value).strip())

    def _load_level_definitions(self) -> dict[str, dict[str, str]]:
        wb = load_workbook(SOURCE_FILES["competency"], data_only=True, read_only=True)
        if "Competency vs Level Definitions" not in wb.sheetnames:
            return {}
        ws = wb["Competency vs Level Definitions"]
        headers = [str(value or "").strip() for value in next(ws.iter_rows(values_only=True))]
        definitions: dict[str, dict[str, str]] = {}
        for values in ws.iter_rows(min_row=2, values_only=True):
            competency = clean(values[0])
            if not competency or any(
                competency.lower().startswith(f"{level.lower()}:")
                for level in ("Beginner", "Intermediate", "Proficient", "Advanced")
            ):
                continue
            definitions[competency] = {
                headers[index]: clean(values[index])
                for index in range(1, min(len(headers), len(values)))
                if headers[index] and values[index]
            }
        return definitions

    def _load_roleplay_links(self) -> dict[str, str]:
        wb = load_workbook(SOURCE_FILES["competency"], data_only=True, read_only=True)
        links: dict[str, str] = {}
        sheet_name = "Role Plays" if "Role Plays" in wb.sheetnames else "Sheet4" if "Sheet4" in wb.sheetnames else ""
        if sheet_name:
            for skill, link in wb[sheet_name].iter_rows(min_row=2, values_only=True):
                if skill and link:
                    url = str(link).strip()
                    if url.startswith("https://") and "…" not in url and "..." not in url:
                        links[str(skill).strip()] = url
        return links

    def _load_employees(self) -> dict[str, dict[str, Any]]:
        wb = load_workbook(SOURCE_FILES["darwin"], data_only=True, read_only=True)
        ws = wb.active
        headers = [str(v or "").strip() for v in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
        rows: dict[str, dict[str, Any]] = {}
        for values in ws.iter_rows(min_row=2, values_only=True):
            row = dict(zip(headers, values))
            code = clean(row.get("EMP Code"))
            if not code:
                continue
            past_years = int(row.get("Past Exp In Years") or 0)
            past_months = int(row.get("Past Exp In Months") or 0)
            rows[code] = {
                "code": code,
                "name": clean(row.get("EMP Full Name")),
                "designation": clean(row.get("Designation")),
                "level": clean(row.get("Level")),
                "location": clean(row.get("Location")),
                "state": clean(row.get("Office State")),
                "department": clean(row.get("Integration Department")),
                "function": clean(row.get("Function")),
                "manager": clean(row.get("Immediate Supervisor")),
                "manager_code": clean(row.get("Immediate Supervisor Code")),
                "rd": clean(row.get("Skip Manager")).split("(", 1)[0].strip(),
                "rd_code": clean(row.get("Skip Manager ID")),
                "role": clean(row.get("Role")),
                "past_exp_years": past_years,
                "past_exp_months": past_months,
                "total_exp_years": round(past_years + past_months / 12, 1),
                "cohort": clean(row.get("Cohort")),
            }
        return rows

    def _load_tna(self) -> dict[str, list[dict[str, str]]]:
        wb = load_workbook(SOURCE_FILES["tna"], data_only=True, read_only=True)
        ws = wb.active
        headers = [str(v or "").strip() for v in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
        grouped: dict[str, list[dict[str, str]]] = {}
        for values in ws.iter_rows(min_row=2, values_only=True):
            row = {key: clean(value) for key, value in zip(headers, values)}
            code = row.get("EMP Code")
            if code:
                grouped.setdefault(code, []).append(row)
        return grouped

    def _load_appraisal(self) -> dict[str, dict[str, str]]:
        wb = load_workbook(SOURCE_FILES["appraisal"], data_only=True, read_only=True)
        ws = wb.active
        headers = [str(v or "").strip() for v in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
        rows: dict[str, dict[str, str]] = {}
        for values in ws.iter_rows(min_row=2, values_only=True):
            row = {key: clean(value) for key, value in zip(headers, values)}
            code = row.get("EMP Code")
            if code:
                rows[code] = row
        return rows

    def _load_interview(self) -> dict[str, dict[str, str]]:
        path = SOURCE_FILES["interview"]
        if not path.is_file():
            return {}
        wb = load_workbook(path, data_only=True, read_only=True)
        ws = wb.active
        headers = [str(v or "").strip() for v in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
        rows: dict[str, dict[str, str]] = {}
        for values in ws.iter_rows(min_row=2, values_only=True):
            row = {key: clean(value) for key, value in zip(headers, values)}
            code = row.get("EMP Code")
            if code:
                rows[code] = row
        return rows

    def _load_amber(self) -> dict[str, list[dict[str, str]]]:
        wb = load_workbook(SOURCE_FILES["amber"], data_only=True, read_only=True)
        ws = wb.active
        headers = [str(v or "").strip() for v in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
        grouped: dict[str, list[dict[str, str]]] = {}
        keep = {"Question", "Answer", "Mood", "Engagement Score", "Driver(Element Name)", "Driver Element Score", "Follow-up Comments"}
        for values in ws.iter_rows(min_row=2, values_only=True):
            row = {key: clean(value) for key, value in zip(headers, values)}
            code = row.get("Emp Code")
            if code:
                grouped.setdefault(code, []).append({key: row.get(key, "") for key in keep})
        return grouped

    def _load_courses(self) -> list[dict[str, Any]]:
        path = SOURCE_FILES["courses"]
        if not path.is_file():
            return []
        wb = load_workbook(path, data_only=True, read_only=True)
        ws = wb.active
        headers = [str(v or "").strip() for v in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
        courses: list[dict[str, Any]] = []
        for values in ws.iter_rows(min_row=2, values_only=True):
            row = dict(zip(headers, values))
            course_id = clean(row.get("Course ID"))
            title = _repair_catalog_text(row.get("Course Title"))
            if not course_id or not title or clean(row.get("Status")).lower() != "active":
                continue
            release = row.get("Release Date")
            courses.append(
                {
                    "id": course_id,
                    "title": title,
                    "author": _repair_catalog_text(row.get("Author")),
                    "release_date": release.strftime("%Y-%m-%d") if hasattr(release, "strftime") else clean(release),
                    "level": clean(row.get("Level")).lower(),
                    "duration": clean(row.get("Duration")),
                    "category": clean(row.get("Category")),
                    "subjects": _repair_catalog_text(row.get("Subjects")),
                    "description": _repair_catalog_text(row.get("Description")),
                    "url": clean(row.get("SSO URL")) or clean(row.get("Course URL")),
                    "thumbnail": clean(row.get("Large Thumbnail")),
                }
            )
        return courses


def _repair_catalog_text(value: Any) -> str:
    text = clean(value)
    if not any(marker in text for marker in ("â", "Ã", "Â")):
        return text
    for encoding in ("cp1252", "latin-1"):
        try:
            return text.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    replacements = {
        "â€™": "’", "â€˜": "‘", "â€œ": "“", "â€\x9d": "”",
        "â€”": "—", "â€“": "–", "â€¦": "…", "Â": "",
    }
    for broken, repaired in replacements.items():
        text = text.replace(broken, repaired)
    return text
