from __future__ import annotations

import unittest
from unittest.mock import patch

from skillsync_ai.agents.roleplay_assessment import assess_roleplay, transcript_is_keyword_stuffed


class RoleplayAssessmentTest(unittest.TestCase):
    def test_keyword_stuffed_advanced_page_is_detected(self) -> None:
        transcript = "Communication\n" + ("advanced " * 80)
        self.assertTrue(transcript_is_keyword_stuffed(transcript))

    @patch("skillsync_ai.agents.roleplay_assessment.chat_json")
    @patch("skillsync_ai.agents.roleplay_assessment.extract_screenshot_text")
    def test_keyword_stuffing_rejects_without_llm(self, ocr, chat) -> None:
        ocr.return_value = {
            "text": "Communication\n" + ("Advanced advanced " * 40),
            "source": "openai-vision",
            "error": "",
        }

        result = assess_roleplay(
            "Communication",
            "fake.png",
            b"image",
            {"Advanced": "definition"},
            "MMT1001",
        )

        self.assertEqual(result["status"], "reupload_required")
        self.assertIsNone(result["proficiency"])
        self.assertIn("genuine role-play feedback", result["error"])
        chat.assert_not_called()

    @patch("skillsync_ai.agents.roleplay_assessment.chat_json")
    @patch("skillsync_ai.agents.roleplay_assessment.extract_screenshot_text")
    def test_readable_wrong_competency_returns_specific_message(self, ocr, chat) -> None:
        ocr.return_value = {
            "text": "Readable feedback about presentation delivery and client communication." * 2,
            "source": "openai-vision",
            "error": "",
        }
        chat.return_value = {
            "rejected": True,
            "reason_code": "competency_mismatch",
            "reason": "No Team Management behavior is present.",
        }

        result = assess_roleplay(
            "Team Management",
            "result.png",
            b"image",
            {"Beginner": "definition"},
            "MMT1001",
        )

        self.assertEqual(result["status"], "reupload_required")
        self.assertIn("does not match the selected competency", result["error"])
        self.assertEqual(result["rationale"], "No Team Management behavior is present.")

    @patch("skillsync_ai.agents.roleplay_assessment.chat_json")
    @patch("skillsync_ai.agents.roleplay_assessment.extract_screenshot_text")
    def test_readable_matching_competency_completes(self, ocr, chat) -> None:
        ocr.return_value = {
            "text": "Readable feedback showing coaching, delegation, and team development behavior." * 2,
            "source": "openai-vision",
            "error": "",
        }
        chat.return_value = {
            "proficiency": "Proficient",
            "rationale": "Demonstrates team coaching and delegation.",
            "evidence": ["Coached team members"],
        }

        result = assess_roleplay(
            "Team Management",
            "result.png",
            b"image",
            {"Proficient": "definition"},
            "MMT1001",
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["proficiency"], "Proficient")
        self.assertEqual(result["error"], "")


if __name__ == "__main__":
    unittest.main()
