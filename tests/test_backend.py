from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from skillsync_ai.backend import BackendError, MyCareerBackend
from skillsync_ai.data_sources import WorkbookData
from skillsync_ai.database import Database, generated_password, utc_now


class BackendWorkflowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = WorkbookData()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(f"{self.temp.name}/test.db")
        self.backend = MyCareerBackend(self.data, self.db)
        self.admin = self.db.authenticate("ADMIN", "admin", "Admin")
        assert self.admin is not None

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_role_scoped_accounts_and_generated_passwords(self) -> None:
        employee = self.data.employees["MMT001"]
        account = self.db.authenticate("MMT001", "employee", generated_password(employee["name"]))
        self.assertIsNotNone(account)
        self.assertIsNone(self.db.authenticate("MMT001", "employee", "wrong"))

        # Dinesh keeps separate ZM and RD account rows under the same login ID.
        self.assertIsNotNone(self.db.authenticate("MMT11043", "zm", "Dinesh"))
        self.assertIsNotNone(self.db.authenticate("MMT11043", "rd", "Dinesh"))

    def test_runtime_cache_clear_preserves_source_and_workflow_data(self) -> None:
        self.db.create_session(int(self.admin["id"]))
        with self.db.transaction() as connection:
            connection.execute(
                "INSERT INTO curated_evidence(employee_code,competency,evidence_json,generated_at) VALUES(?,?,?,?)",
                ("MMT001", "Communication", "{}", utc_now()),
            )
            connection.execute(
                """
                INSERT INTO course_recommendations(
                    employee_code,target_key,competency,current_level,target_level,
                    candidate_ids_json,courses_json,generated_at
                ) VALUES(?,?,?,?,?,?,?,?)
                """,
                ("MMT001", "test", "Communication", "Beginner", "Intermediate", "[]", "[]", utc_now()),
            )

        self.db.clear_runtime_cache()

        with self.db.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM curated_evidence").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM course_recommendations").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM employees").fetchone()[0], 44)

    def test_phase_gate_blocks_login_until_admin_opens_phase(self) -> None:
        employee = self.data.employees["MMT001"]
        with self.assertRaises(BackendError) as error:
            self.backend.login(employee["manager_code"], "zm", generated_password(employee["manager"]))
        self.assertEqual(error.exception.code, "phase_closed")

        self.backend.open_phase(self.admin, "zm")
        result = self.backend.login(employee["manager_code"], "zm", generated_password(employee["manager"]))
        self.assertEqual(result["user"]["role"], "zm")

    def test_phase_override_does_not_report_incomplete_previous_phase_as_complete(self) -> None:
        self.backend.open_phase(self.admin, "rd", override=True)

        self.assertEqual(self.backend.phase("zm")["status"], "closed")
        self.assertEqual(self.backend.phase("rd")["status"], "open")
        self.assertFalse(self.backend.phase("zm")["progress"]["is_complete"])

    def test_rd_cannot_rate_employee_before_zm_submission(self) -> None:
        employee = self.data.employees["MMT001"]
        self.backend.open_phase(self.admin, "rd", override=True)
        rd = self.db.authenticate(employee["rd_code"], "rd", generated_password(employee["rd"]))
        assert rd is not None

        with self.assertRaises(BackendError) as error:
            self.backend.save_assessment(
                rd,
                employee["code"],
                {competency: "Intermediate" for competency in self.backend.competencies},
                submit=False,
            )

        self.assertEqual(error.exception.code, "zm_assessment_required")

    def test_rd_validation_does_not_run_evidence_agent_before_zm_submission(self) -> None:
        employee = self.data.employees["MMT001"]
        rd = self.db.authenticate(employee["rd_code"], "rd", generated_password(employee["rd"]))
        assert rd is not None

        with self.assertRaises(BackendError) as error:
            self.backend.rd_validation_context(rd, employee["code"])

        self.assertEqual(error.exception.code, "zm_assessment_required")
        self.assertEqual(self.backend.agent_audit(), [])

    @patch("skillsync_ai.backend._rank_all_with_agent", return_value=({}, "test ranker"))
    def test_zm_then_rd_submission_makes_rd_profile_final(self, ranker) -> None:
        employee = self.data.employees["MMT001"]
        self.backend.open_phase(self.admin, "zm")
        zm = self.db.authenticate(employee["manager_code"], "zm", generated_password(employee["manager"]))
        assert zm is not None
        zm_ratings = {competency: "Beginner" for competency in self.backend.competencies}
        result = self.backend.save_assessment(zm, "MMT001", zm_ratings, submit=True)
        self.assertEqual(result["status"], "submitted")

        self.backend.open_phase(self.admin, "rd", override=True)
        rd = self.db.authenticate(employee["rd_code"], "rd", generated_password(employee["rd"]))
        assert rd is not None
        rd_ratings = {competency: "Intermediate" for competency in self.backend.competencies}
        result = self.backend.save_assessment(rd, "MMT001", rd_ratings, submit=True)
        self.assertEqual(result["status"], "submitted")
        self.assertEqual(self.backend.final_profile("MMT001"), rd_ratings)
        expected_agent_runs = sum(
            bool(target["gaps"]) for target in self.backend.recommendation_targets("MMT001")
        )
        self.assertEqual(ranker.call_count, expected_agent_runs)
        self.assertTrue(self.backend.recommendations("MMT001")["ready"])

    @patch("skillsync_ai.backend._rank_all_with_agent", return_value=({}, "test ranker"))
    def test_confidence_is_deterministic_and_uses_zm_plus_ai(self, _ranker) -> None:
        employee = self.data.employees["MMT001"]
        self.backend.open_phase(self.admin, "zm")
        zm = self.db.authenticate(employee["manager_code"], "zm", generated_password(employee["manager"]))
        assert zm is not None
        ratings = {competency: "Proficient" for competency in self.backend.competencies}
        self.backend.save_assessment(zm, "MMT001", ratings, submit=True)
        self.backend.open_phase(self.admin, "rd", override=True)
        rd = self.db.authenticate(employee["rd_code"], "rd", generated_password(employee["rd"]))
        assert rd is not None
        self.backend.save_assessment(rd, "MMT001", ratings, submit=True)
        with self.db.transaction() as connection:
            for competency in self.backend.competencies:
                connection.execute(
                    """
                    INSERT INTO roleplay_assessments(
                        employee_code,competency,status,ai_proficiency,updated_at
                    ) VALUES(?,?, 'completed','Proficient',?)
                    """,
                    ("MMT001", competency, utc_now()),
                )
        confidence = self.backend.confidence("MMT001")
        self.assertEqual(confidence["status"], "complete")
        self.assertEqual(confidence["score"], 100.0)

    def test_roleplay_assessment_evidence_is_admin_only(self) -> None:
        screenshot = Path(self.temp.name) / "communication.png"
        screenshot.write_bytes(b"private screenshot")
        with self.db.transaction() as connection:
            connection.execute(
                """
                INSERT INTO roleplay_assessments(
                    employee_code,competency,filename,file_path,status,ai_proficiency,
                    rationale,ocr_text,error,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "MMT001",
                    "Communication",
                    screenshot.name,
                    str(screenshot),
                    "completed",
                    "Proficient",
                    "Observed behavior",
                    "Private OCR transcript",
                    "",
                    utc_now(),
                ),
            )

        employee_view = next(
            row for row in self.backend.roleplays("MMT001") if row["competency"] == "Communication"
        )
        for private_field in ("ai_proficiency", "rationale", "ocr_text", "filename", "file_path"):
            self.assertNotIn(private_field, employee_view)

        admin_view = self.backend.admin_roleplays(self.admin, "MMT001", "Communication")
        communication = next(
            row for row in admin_view["roleplays"] if row["competency"] == "Communication"
        )
        self.assertEqual(communication["ai_proficiency"], "Proficient")
        self.assertEqual(communication["rationale"], "Observed behavior")
        self.assertEqual(admin_view["screenshot"]["content_base64"], "cHJpdmF0ZSBzY3JlZW5zaG90")

        employee = self.db.authenticate("MMT001", "employee", generated_password(self.data.employees["MMT001"]["name"]))
        assert employee is not None
        with self.assertRaises(BackendError) as error:
            self.backend.admin_roleplays(employee, "MMT001")
        self.assertEqual(error.exception.code, "forbidden")

    @patch("skillsync_ai.backend._rank_all_with_agent")
    def test_aspiration_lock_and_backend_filtered_course_candidates(self, ranker) -> None:
        ranker.side_effect = lambda groups, *_args: (
            {key: _first_two(value["candidates"]) for key, value in groups.items()},
            "test ranker",
        )
        employee = self.data.employees["MMT002"]
        self.backend.open_phase(self.admin, "zm")
        zm = self.db.authenticate(employee["manager_code"], "zm", generated_password(employee["manager"]))
        assert zm is not None
        ratings = {competency: "Advanced" for competency in self.backend.competencies}
        self.backend.save_assessment(zm, "MMT002", ratings, submit=True)
        self.backend.open_phase(self.admin, "rd", override=True)
        rd = self.db.authenticate(employee["rd_code"], "rd", generated_password(employee["rd"]))
        assert rd is not None
        self.backend.save_assessment(rd, "MMT002", ratings, submit=True)
        self.backend.open_phase(self.admin, "employee", override=True)
        with self.db.transaction() as connection:
            for competency in self.backend.competencies:
                connection.execute(
                    """
                    INSERT INTO roleplay_assessments(
                        employee_code,competency,status,ai_proficiency,updated_at
                    ) VALUES(?,?, 'completed','Advanced',?)
                    """,
                    ("MMT002", competency, utc_now()),
                )
        user = self.db.authenticate("MMT002", "employee", generated_password(employee["name"]))
        assert user is not None
        state = self.backend.choose_career(user, "kam")
        self.assertEqual(state["choice"]["aspiration_role"], "kam")
        with self.assertRaises(BackendError) as error:
            self.backend.choose_career(user, "kam")
        self.assertEqual(error.exception.code, "career_locked")

        with self.db.connect() as connection:
            rows = connection.execute(
                "SELECT candidate_ids_json FROM course_recommendations WHERE employee_code='MMT002'"
            ).fetchall()
        # Candidate rows can be empty when final profile already meets the target; no general course can enter either way.
        self.assertTrue(all("general" not in row["candidate_ids_json"] for row in rows))

    def test_leaderboard_ranks_only_linkedin_hours_and_shares_ties(self) -> None:
        with self.db.transaction() as connection:
            for code in ("MMT002", "MMT004"):
                cursor = connection.execute(
                    """
                    INSERT INTO assessments(
                        employee_code,assessor_role,assessor_login_id,status,created_at,updated_at,submitted_at
                    ) VALUES(?, 'rd', 'TEST-RD', 'submitted', ?, ?, ?)
                    """,
                    (code, utc_now(), utc_now(), utc_now()),
                )
                for competency in self.backend.competencies:
                    connection.execute(
                        "INSERT INTO assessment_ratings(assessment_id,competency,proficiency) VALUES(?,?,'Beginner')",
                        (cursor.lastrowid, competency),
                    )
            for code, hours in (("MMT002", 3.5), ("MMT004", 3.5)):
                connection.execute(
                    "INSERT INTO linkedin_activity(employee_code,learning_hours,completions,synced_at) VALUES(?,?,0,?)",
                    (code, hours, utc_now()),
                )
        rows = [row for row in self.backend.leaderboard(self.admin) if row["employee_code"] in {"MMT002", "MMT004"}]
        self.assertEqual(len(rows), 2)
        self.assertEqual({row["rank"] for row in rows}, {1})
        self.assertEqual({row["learning_hours"] for row in rows}, {3.5})

    def test_course_frontend_contract_contains_required_catalog_fields(self) -> None:
        row = self.backend._course_contract(
            {"title": "Example", "url": "https://example.com", "author": "Provider", "duration": "01:00:00"},
            "Communication",
            "Beginner",
            "Intermediate",
        )
        self.assertEqual(row["provider"], "Provider")
        self.assertEqual(row["source_type"], "LinkedIn Learning")
        self.assertEqual(row["competency"], "Communication")
        self.assertEqual(row["supported_proficiency_movement"], {"from": "Beginner", "to": "Intermediate"})

    def test_frontend_employee_summary_and_final_profile_contract(self) -> None:
        employee = self.data.employees["MMT001"]
        with self.db.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO assessments(employee_code,assessor_role,assessor_login_id,status,created_at,updated_at,submitted_at)
                VALUES('MMT001','rd','TEST-RD','submitted',?,?,?)
                """,
                (utc_now(), utc_now(), utc_now()),
            )
            for competency in self.backend.competencies:
                connection.execute(
                    "INSERT INTO assessment_ratings(assessment_id,competency,proficiency) VALUES(?,?,'Intermediate')",
                    (cursor.lastrowid, competency),
                )
        zm = self.db.authenticate(employee["manager_code"], "zm", generated_password(employee["manager"]))
        assert zm is not None
        summary = next(row for row in self.backend.employee_summaries(zm) if row["employee_code"] == "MMT001")
        self.assertTrue(summary["final_profile_available"])
        profile = self.backend.profile_for_user(zm, "MMT001")
        self.assertEqual(profile["status"], "final")
        self.assertEqual(len(profile["ratings"]), 7)

    def test_agent_audit_contract_lists_recorded_agent(self) -> None:
        self.backend._audit("MMT001", "Evidence Curator Agent", "Communication", "TNA", {"evidence": []}, "ok")
        rows = self.backend.agent_audit()
        self.assertEqual(rows[0]["agent"], "Evidence Curator Agent")
        self.assertEqual(rows[0]["output"], {"evidence": []})


def _first_two(candidates):
    return [dict(row) for row in candidates[:2]]


if __name__ == "__main__":
    unittest.main()
