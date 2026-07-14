from __future__ import annotations

import unittest

from skillsync_ai.agents.course_recommendation import _allowed_levels, duration_hours, gap_levels
from skillsync_ai.state import RuntimeState
from skillsync_ai.web.views import leaderboard_rows


class LearningRulesTest(unittest.TestCase):
    def test_course_level_mapping(self) -> None:
        self.assertEqual(_allowed_levels("Beginner"), {"beginner", "beginner_intermediate", "general"})
        self.assertEqual(_allowed_levels("Intermediate"), {"intermediate", "beginner_intermediate", "general"})
        self.assertEqual(_allowed_levels("Proficient"), {"advanced", "general"})
        self.assertEqual(_allowed_levels("Advanced"), {"advanced", "general"})

    def test_duration_is_counted_in_hours(self) -> None:
        self.assertEqual(duration_hours("01:30:00"), 1.5)
        self.assertEqual(duration_hours("00:45:00"), 0.75)

    def test_gap_levels_are_summed(self) -> None:
        profile = {"gaps": [
            {"current": "Beginner", "ideal": "Intermediate"},
            {"current": "Beginner", "ideal": "Proficient"},
        ]}
        self.assertEqual(gap_levels(profile), 3)

    def test_leaderboard_uses_hours_only_and_ties_share_rank(self) -> None:
        class Data:
            employees = {
                "A": {"name": "A", "manager": "M"},
                "B": {"name": "B", "manager": "M"},
            }

        state = RuntimeState()
        profile = {"gaps": [{"current": "Beginner", "ideal": "Intermediate"}]}
        state.profiles = {"A": profile, "B": profile}
        course = {"id": "1", "duration": "01:00:00"}
        state.recommendations = {
            "A": {"skills": {"Communication": [course]}},
            "B": {"skills": {"Communication": [course]}},
        }
        state.learning_selections = {"A": ["1"], "B": ["1"]}
        state.learning_completed = {"A": {"1"}, "B": {"1"}}
        rows = leaderboard_rows(Data(), state, cohort=1)
        self.assertEqual([row["rank"] for row in rows], [1, 1])
        self.assertEqual([row["hours"] for row in rows], [1.0, 1.0])


if __name__ == "__main__":
    unittest.main()
