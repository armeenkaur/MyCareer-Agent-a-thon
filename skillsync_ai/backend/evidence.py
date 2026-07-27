from __future__ import annotations

from typing import Any
from ..agents.evidence_curator import AGENT_NAME as EVIDENCE_AGENT, CURATOR_VERSION, curate_evidence
from ..agents.rd_suggestion import AGENT_NAME as RD_SUGGEST_AGENT, suggest_rd_rating
from ..core.logging_setup import get_logger
from .errors import BackendError
log = get_logger('skillsync.backend')

class EvidenceMixin:
    def zm_assessment_evidence(self, user: dict[str, Any], employee_code: str) -> dict[str, Any]:
        """Supporting evidence for ZM rating UI — no AI suggested ratings."""
        if user.get("role") != "zm":
            raise BackendError("ZM access required.", "forbidden", 403)
        self._assert_employee_scope(user, employee_code)
        evidence: dict[str, Any] = {}
        for competency in self.competencies:
            cached = self._cached_evidence(employee_code, competency)
            # Always fill on miss — ZM needs evidence for draft and submitted review.
            if cached is None:
                cached = curate_evidence(self.data, employee_code, competency)
                cached.pop("suggested_rating", None)
                cached.pop("suggested_rationale", None)
                self._save_evidence(employee_code, competency, cached)
                self._audit(employee_code, EVIDENCE_AGENT, competency, "Workbook evidence (ZM)", cached, "ok")
            if isinstance(cached, dict):
                bundle = dict(cached)
                bundle.pop("suggested_rating", None)
                bundle.pop("suggested_rationale", None)
                evidence[competency] = self._evidence_for_manager_ui(bundle)
            else:
                evidence[competency] = {
                    "competency": competency,
                    "evidence": [],
                    "empty_message": "No relevant evidence found.",
                }
        return {
            "employee": self.employee(employee_code),
            "evidence": evidence,
            "career_move": self.career_move_options(user, employee_code),
        }


    def rd_validation_context(self, user: dict[str, Any], employee_code: str) -> dict[str, Any]:
        if user["role"] not in {"rd", "admin"}:
            raise BackendError("RD or Admin access required.", "forbidden", 403)
        if user["role"] == "rd":
            self._assert_employee_scope(user, employee_code)
        zm_assessment = self.assessment(employee_code, "zm")
        if not zm_assessment or zm_assessment["status"] != "submitted":
            raise BackendError(
                "ZM assessment must be submitted before RD validation.",
                "zm_assessment_required",
                409,
            )
        evidence = {}
        rd_assessment = self.assessment(employee_code, "rd")
        # Agent runs only on Start/draft cache miss. View (submitted) never re-curates.
        allow_curate = not (rd_assessment and rd_assessment.get("status") == "submitted")
        for competency in self.competencies:
            cached = self._cached_evidence(employee_code, competency)
            if cached is None and allow_curate:
                cached = curate_evidence(self.data, employee_code, competency)
                suggestion = suggest_rd_rating(
                    competency,
                    (zm_assessment.get("ratings") or {}).get(competency),
                    (zm_assessment.get("notes") or {}).get(competency),
                    cached.get("evidence") or [],
                    self.data.level_definitions.get(competency, {}),
                    employee_code,
                )
                cached["suggested_rating"] = suggestion.get("proficiency")
                cached.pop("suggested_rationale", None)
                self._save_evidence(employee_code, competency, cached)
                self._audit(employee_code, EVIDENCE_AGENT, competency, "Workbook evidence", cached, "ok")
                self._audit(employee_code, RD_SUGGEST_AGENT, competency, f"ZM={(zm_assessment.get('ratings') or {}).get(competency)}", {"proficiency": suggestion.get("proficiency")}, "ok")
            elif cached is None:
                cached = {
                    "competency": competency,
                    "evidence": [],
                    "empty_message": "No saved evidence for this competency.",
                    "source": "cache",
                    "curator_version": CURATOR_VERSION,
                }
            elif allow_curate and not cached.get("suggested_rating"):
                suggestion = suggest_rd_rating(
                    competency,
                    (zm_assessment.get("ratings") or {}).get(competency),
                    (zm_assessment.get("notes") or {}).get(competency),
                    cached.get("evidence") or [],
                    self.data.level_definitions.get(competency, {}),
                    employee_code,
                )
                cached["suggested_rating"] = suggestion.get("proficiency")
                cached.pop("suggested_rationale", None)
                self._save_evidence(employee_code, competency, cached)
                self._audit(employee_code, RD_SUGGEST_AGENT, competency, f"ZM={(zm_assessment.get('ratings') or {}).get(competency)}", {"proficiency": suggestion.get("proficiency")}, "ok")
            if isinstance(cached, dict):
                cached.pop("suggested_rationale", None)
            evidence[competency] = self._evidence_for_manager_ui(cached)
        zm_public = {
            "status": zm_assessment.get("status"),
            "ratings": zm_assessment.get("ratings") or {},
            "notes": zm_assessment.get("notes") or {},
        }
        return {
            "employee": self.employee(employee_code),
            "zm_assessment": zm_public,
            "rd_assessment": rd_assessment,
            "evidence": evidence,
            "rubric": self.data.level_definitions,
            "career_move": self.career_move_options(user, employee_code),
        }

    @staticmethod

    def _evidence_for_manager_ui(bundle: dict[str, Any] | None) -> dict[str, Any]:
        """Hide TNA / employee learning input from ZM+RD UI; agents still use full cache."""
        if not isinstance(bundle, dict):
            return {
                "competency": "",
                "evidence": [],
                "empty_message": "No relevant evidence found.",
            }
        out = dict(bundle)
        items = [
            item
            for item in (out.get("evidence") or [])
            if str(item.get("source") or "").strip().upper() != "TNA"
        ]
        out["evidence"] = items
        if not items and not out.get("empty_message"):
            out["empty_message"] = "No relevant evidence found."
        return out

    # Employee role-play, career, and learning workflows
