from __future__ import annotations

import unittest

from skillsync_ai.voice_live.client import parse_ratings_json


class VoiceLiveParseTests(unittest.TestCase):
    def test_parse_ratings_json(self) -> None:
        skills = ["Communication", "Team Management"]
        text = 'Here you go:\n{"ratings":{"Communication":"Intermediate","Team Management":"Proficient"}}\n'
        result = parse_ratings_json(text, skills)
        self.assertEqual(result["Communication"], "Intermediate")
        self.assertEqual(result["Team Management"], "Proficient")

    def test_parse_duplicated_json_blob(self) -> None:
        skills = ["Communication", "Team Management"]
        blob = '{"ratings":{"Communication":"Beginner","Team Management":"Proficient"}}'
        text = blob + "\n" + blob
        result = parse_ratings_json(text, skills)
        self.assertEqual(result["Communication"], "Beginner")

    def test_parse_rejects_missing_skill(self) -> None:
        with self.assertRaises(ValueError):
            parse_ratings_json('{"ratings":{"Communication":"Beginner"}}', ["Communication", "Team Management"])


if __name__ == "__main__":
    unittest.main()
