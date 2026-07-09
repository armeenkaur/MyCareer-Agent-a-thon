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
        self.roleplay_links = self._load_roleplay_links()
        self.employees = self._load_employees()
        self.tna = self._load_tna()
        self.appraisal = self._load_appraisal()
        self.amber = self._load_amber()
        self.variable = self._load_variable()

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

    def team_for_manager(self, manager: str | None) -> list[dict[str, Any]]:
        if not manager:
            return self.employee_options()
        return [emp for emp in self.employee_options() if emp.get("manager") == manager]

    def ideal_for_employee(self, emp_code: str) -> dict[str, str]:
        employee = self.employees.get(emp_code, {})
        key = role_level_key(employee.get("designation", ""), employee.get("level", ""))
        ideal: dict[str, str] = {}
        for row in self.competencies:
            ideal[row["skill"]] = row["ideals"].get(key) or row["ideals"].get("BDM (RL1-2)") or "Intermediate"
        return ideal

    def _load_competencies(self) -> list[dict[str, Any]]:
        wb = load_workbook(SOURCE_FILES["competency"], data_only=True, read_only=True)
        ws = wb["Competency"]
        headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]
        rows: list[dict[str, Any]] = []
        for cells in ws.iter_rows(min_row=3, values_only=True):
            if not cells[0] or not cells[1]:
                continue
            ideals = {}
            for idx, header in enumerate(headers[4:], start=4):
                if header and cells[idx]:
                    ideals[str(header).strip()] = str(cells[idx]).strip()
            rows.append(
                {
                    "skill": str(cells[0]).strip(),
                    "tag": str(cells[1]).strip(),
                    "sales_note": str(cells[2] or "").strip(),
                    "product_note": str(cells[3] or "").strip(),
                    "ideals": ideals,
                }
            )
        return rows

    def _load_roleplay_links(self) -> dict[str, str]:
        wb = load_workbook(SOURCE_FILES["competency"], data_only=True, read_only=True)
        links: dict[str, str] = {}
        if "Sheet4" in wb.sheetnames:
            for skill, link in wb["Sheet4"].iter_rows(min_row=2, values_only=True):
                if skill and link:
                    links[str(skill).strip()] = str(link).strip()
        links.setdefault(
            "Team Management",
            "https://www.linkedin.com/learning/role-play/scenarios/urn:li:la_rolePlayScenario:urn:li:llsServeScenario:127536712?u=236676260",
        )
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

    def _load_variable(self) -> dict[str, dict[str, Any]]:
        wb = load_workbook(SOURCE_FILES["variable"], data_only=True, read_only=True)
        ws = wb.active
        headers = [str(v or "").strip() for v in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
        rows: dict[str, dict[str, Any]] = {}
        for values in ws.iter_rows(min_row=2, values_only=True):
            row = dict(zip(headers, values))
            code = clean(row.get("EMP Code"))
            if code:
                rows[code] = {
                    "avg": float(row.get("Avg") or 0),
                    "cohort": clean(row.get("Cohort")),
                    "level": clean(row.get("Level")),
                }
        return rows
