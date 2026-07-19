from __future__ import annotations

import unittest

from skillsync_ai.agents.course_recommendation import _allowed_levels


class LearningRulesTest(unittest.TestCase):
    def test_course_level_mapping(self) -> None:
        self.assertEqual(_allowed_levels("Beginner"), {"beginner", "beginner_intermediate"})
        self.assertEqual(_allowed_levels("Intermediate"), {"intermediate", "beginner_intermediate"})
        self.assertEqual(_allowed_levels("Proficient"), {"advanced"})
        self.assertEqual(_allowed_levels("Advanced"), {"advanced"})


if __name__ == "__main__":
    unittest.main()
