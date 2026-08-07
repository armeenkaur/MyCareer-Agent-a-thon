from __future__ import annotations

from typing import Any
from ..core.config import PROFICIENCY_ORDER, PROFICIENCY_VALUE, UPLOAD_DIR
from ..core.logging_setup import get_logger
log = get_logger('skillsync.backend')

class ConfidenceMixin:
    def confidence(self, employee_code: str) -> dict[str, Any]:
        rd = self.assessment(employee_code, "rd")
        zm = self.assessment(employee_code, "zm")
        if not rd or rd["status"] != "submitted" or not zm or zm["status"] != "submitted":
            return {"status": "pending", "score": None, "competencies": []}
        roleplays = {
            row["competency"]: row for row in self.roleplays(employee_code, include_private=True)
        }
        rows = []
        for competency in self.competencies:
            ai_level = roleplays[competency].get("ai_proficiency")
            if not ai_level:
                rows.append({"competency": competency, "status": "pending"})
                continue
            rd_value = PROFICIENCY_VALUE[rd["ratings"][competency]]
            zm_value = PROFICIENCY_VALUE[zm["ratings"][competency]]
            ai_value = PROFICIENCY_VALUE[ai_level]
            zm_agreement = round((1 - abs(rd_value - zm_value) / 3) * 100, 1)
            ai_agreement = round((1 - abs(rd_value - ai_value) / 3) * 100, 1)
            rows.append(
                {
                    "competency": competency,
                    "status": "complete",
                    "rd_rating": rd["ratings"][competency],
                    "zm_rating": zm["ratings"][competency],
                    "ai_rating": ai_level,
                    "zm_agreement": zm_agreement,
                    "ai_agreement": ai_agreement,
                    "confidence": round((zm_agreement + ai_agreement) / 2, 1),
                }
            )
        completed = [row for row in rows if row["status"] == "complete"]
        if len(completed) != len(self.competencies):
            return {"status": "pending", "score": None, "completed": len(completed), "total": len(self.competencies), "competencies": rows}
        score = round(sum(row["confidence"] for row in completed) / len(completed), 1)
        band = "High" if score >= 75 else "Medium" if score >= 55 else "Low"
        return {"status": "complete", "score": score, "band": band, "competencies": rows}

