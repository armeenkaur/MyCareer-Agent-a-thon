from __future__ import annotations

import unittest

from skillsync_ai.voice_live import merge_roleplay_scores
from skillsync_ai.voice_live.client import parse_ratings_json


class VoiceLiveParseTests(unittest.TestCase):
    def test_parse_ratings_json_with_confidence(self) -> None:
        text = (
            '{"ratings":{'
            '"Consultative Selling":{"level":"Intermediate","confidence":0.8},'
            '"Data Analytics":{"level":"Beginner","confidence":0.6},'
            '"Stakeholder Relationship":{"level":"Proficient","confidence":0.9},'
            '"Communication":{"level":"Proficient","confidence":0.7},'
            '"Executive Presence":{"level":"Advanced","confidence":0.5},'
            '"Ownership & Accountability":null,'
            '"Team Management":null'
            "}}"
        )
        result = parse_ratings_json(text, "functional")
        self.assertEqual(result["Consultative Selling"]["level"], "Intermediate")
        self.assertAlmostEqual(result["Consultative Selling"]["confidence"], 0.8)
        self.assertIsNone(result["Ownership & Accountability"])
        self.assertIsNone(result["Team Management"])

    def test_parse_rejects_null_strong_skill(self) -> None:
        text = (
            '{"ratings":{'
            '"Consultative Selling":null,'
            '"Data Analytics":{"level":"Beginner","confidence":0.6},'
            '"Stakeholder Relationship":{"level":"Proficient","confidence":0.9},'
            '"Communication":{"level":"Proficient","confidence":0.7},'
            '"Executive Presence":{"level":"Advanced","confidence":0.5},'
            '"Ownership & Accountability":null,'
            '"Team Management":null'
            "}}"
        )
        with self.assertRaises(ValueError):
            parse_ratings_json(text, "functional")

    def test_parse_legacy_flat_strings(self) -> None:
        text = (
            '{"ratings":{'
            '"Communication":"Intermediate",'
            '"Ownership & Accountability":"Proficient",'
            '"Team Management":"Beginner",'
            '"Executive Presence":"Advanced",'
            '"Stakeholder Relationship":"Proficient",'
            '"Data Analytics":null,'
            '"Consultative Selling":null'
            "}}"
        )
        result = parse_ratings_json(text, "behavioural")
        self.assertEqual(result["Communication"]["level"], "Intermediate")
        self.assertAlmostEqual(result["Communication"]["confidence"], 0.7)

    def test_merge_confidence_weighted(self) -> None:
        functional = {
            "Consultative Selling": {"level": "Advanced", "confidence": 1.0},
            "Data Analytics": {"level": "Beginner", "confidence": 1.0},
            "Stakeholder Relationship": {"level": "Beginner", "confidence": 0.2},
            "Communication": {"level": "Beginner", "confidence": 0.2},
            "Executive Presence": {"level": "Beginner", "confidence": 0.2},
            "Ownership & Accountability": None,
            "Team Management": None,
        }
        behavioural = {
            "Communication": {"level": "Advanced", "confidence": 1.0},
            "Ownership & Accountability": {"level": "Intermediate", "confidence": 0.8},
            "Team Management": {"level": "Beginner", "confidence": 0.7},
            "Executive Presence": {"level": "Advanced", "confidence": 1.0},
            "Stakeholder Relationship": {"level": "Advanced", "confidence": 1.0},
            "Data Analytics": None,
            "Consultative Selling": None,
        }
        merged = merge_roleplay_scores([functional, behavioural])
        self.assertEqual(merged["Consultative Selling"], "Advanced")
        self.assertEqual(merged["Data Analytics"], "Beginner")
        self.assertEqual(merged["Ownership & Accountability"], "Intermediate")
        # Stakeholder: Beginner@0.2 + Advanced@1.0 → weighted toward Advanced
        self.assertEqual(merged["Stakeholder Relationship"], "Advanced")
        self.assertEqual(merged["Communication"], "Advanced")

    def test_merge_rejects_both_null(self) -> None:
        functional = {
            "Consultative Selling": {"level": "Advanced", "confidence": 1.0},
            "Data Analytics": {"level": "Beginner", "confidence": 1.0},
            "Stakeholder Relationship": {"level": "Beginner", "confidence": 0.2},
            "Communication": {"level": "Beginner", "confidence": 0.2},
            "Executive Presence": {"level": "Beginner", "confidence": 0.2},
            "Ownership & Accountability": None,
            "Team Management": None,
        }
        behavioural = {
            "Communication": {"level": "Advanced", "confidence": 1.0},
            "Ownership & Accountability": None,  # both null — illegal
            "Team Management": {"level": "Beginner", "confidence": 0.7},
            "Executive Presence": {"level": "Advanced", "confidence": 1.0},
            "Stakeholder Relationship": {"level": "Advanced", "confidence": 1.0},
            "Data Analytics": None,
            "Consultative Selling": None,
        }
        with self.assertRaises(ValueError):
            merge_roleplay_scores([functional, behavioural])


if __name__ == "__main__":
    unittest.main()
