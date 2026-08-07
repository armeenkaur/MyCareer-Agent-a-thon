from __future__ import annotations

import unittest
from unittest.mock import patch

from skillsync_ai.agents.ocr_qwen import extract_screenshot_text


class ScreenshotOcrTest(unittest.TestCase):
    @patch("skillsync_ai.agents.ocr_qwen._extract_tesseract")
    @patch("skillsync_ai.agents.ocr_qwen._extract_openai_vision")
    def test_openai_vision_is_primary_when_transcript_is_useful(self, vision, tesseract) -> None:
        vision.return_value = {
            "text": "A sufficiently detailed role-play behavior transcript from the screenshot.",
            "source": "openai-vision",
            "error": "",
        }

        result = extract_screenshot_text(b"image", "roleplay.png")

        self.assertEqual(result["source"], "openai-vision")
        tesseract.assert_not_called()

    @patch("skillsync_ai.agents.ocr_qwen._extract_tesseract")
    @patch("skillsync_ai.agents.ocr_qwen._extract_openai_vision")
    def test_tesseract_fallback_wins_when_vision_is_unavailable(self, vision, tesseract) -> None:
        vision.return_value = {
            "text": "",
            "source": "openai-vision",
            "error": "service unavailable",
        }
        tesseract.return_value = {
            "text": "Detailed local OCR transcript containing enough behavior evidence.",
            "source": "tesseract",
            "error": "",
        }

        result = extract_screenshot_text(b"image", "roleplay.png")

        self.assertEqual(result["source"], "tesseract")
        self.assertIn("behavior evidence", result["text"])


if __name__ == "__main__":
    unittest.main()
