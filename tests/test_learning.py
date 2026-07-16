from __future__ import annotations

import unittest

from skillsync_ai.agents.course_recommendation import _allowed_levels, duration_hours


class LearningRulesTest(unittest.TestCase):
    def test_course_level_mapping(self) -> None:
        self.assertEqual(_allowed_levels("Beginner"), {"beginner", "beginner_intermediate"})
        self.assertEqual(_allowed_levels("Intermediate"), {"intermediate", "beginner_intermediate"})
        self.assertEqual(_allowed_levels("Proficient"), {"advanced"})
        self.assertEqual(_allowed_levels("Advanced"), {"advanced"})

    def test_duration_is_counted_in_hours(self) -> None:
        self.assertEqual(duration_hours("01:30:00"), 1.5)
        self.assertEqual(duration_hours("00:45:00"), 0.75)

if __name__ == "__main__":
    unittest.main()
