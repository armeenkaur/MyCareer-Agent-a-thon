from __future__ import annotations

import unittest

from skillsync_ai.data_sources import WorkbookData
from skillsync_ai.state import RuntimeState
from skillsync_ai.web import views


class PageRenderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = WorkbookData()
        cls.emp_code = next(iter(cls.data.employees))

    def setUp(self) -> None:
        self.state = RuntimeState()

    def test_public_pages_render_without_completed_profile(self) -> None:
        pages = [
            views.home(self.data),
            views.feedback_page(self.data, self.state, {"role": "employee"}),
            views.employee_dashboard(self.data, self.state, {}),
            views.course_shop(self.data, self.state, {}),
            views.learning_journey(self.data, self.state, {}),
            views.manager_dashboard(self.data, self.state, {}),
            views.manager_employee(self.data, self.state, {}),
            views.admin_dashboard(self.data, self.state, {}),
        ]
        for page in pages:
            self.assertTrue(page.strip())
            self.assertNotIn("Traceback", page)

    def test_completed_profile_pages_render(self) -> None:
        code = self.emp_code
        skill = self.data.functional_skills[0]
        course = {
            "id": "course-1",
            "title": "Consultative Selling Foundations",
            "description": "Practice discovery and value-led partner conversations.",
            "duration": "01:00:00",
            "url": "https://www.linkedin.com/learning/",
            "level": "beginner",
        }
        resource = {
            "id": "resource-1",
            "type": "YouTube",
            "title": "Discovery conversation practice",
            "description": "Open practice resource.",
            "url": "https://www.youtube.com/",
        }
        profile = {
            "scores": {name: "Beginner" for name in self.data.functional_skills + self.data.behavioral_skills},
            "profile_v0": {name: "Beginner" for name in self.data.functional_skills + self.data.behavioral_skills},
            "ideal": {skill: "Intermediate"},
            "gaps": [{"skill": skill, "current": "Beginner", "ideal": "Intermediate"}],
            "good_skills": [],
            "work_on_skills": [skill],
            "coaching": {"good_skills": [], "work_on_skills": [skill]},
            "confidence": {"band": "High", "score": 90, "explanation": "Test profile."},
            "adjustments": [],
        }
        recommendation = {
            "skills": {skill: [course]},
            "external": {skill: [resource]},
            "external_searched": True,
            "ideal_reached": False,
            "career_options": [],
            "mentor": "",
        }
        self.state.profiles[code] = profile
        self.state.recommendations[code] = recommendation
        self.state.learning_selections[code] = [course["id"]]
        self.state.external_selections[code] = [resource["id"]]

        pages = [
            views.employee_dashboard(self.data, self.state, {"emp": code, "section": "results"}),
            views.course_shop(self.data, self.state, {"emp": code}),
            views.learning_journey(self.data, self.state, {"emp": code}),
            views.manager_dashboard(self.data, self.state, {}),
            views.manager_employee(self.data, self.state, {"emp": code}),
            views.admin_dashboard(self.data, self.state, {"emp": code}),
        ]
        for page in pages:
            self.assertTrue(page.strip())
            self.assertNotIn("Traceback", page)

    def test_career_choice_gate_hides_levels(self) -> None:
        employee = self.data.employees[self.emp_code]
        recommendation = {
            "career_options": [
                {"id": "bdm", "label": "Business Development Manager", "skills": ["Communication"]},
                {"id": "kam", "label": "Key Account Manager", "skills": ["Business Acumen"]},
                {"id": "bdfe", "label": "BDFE", "skills": ["Data Analytics"]},
            ]
        }
        page = views.career_choice_gate(self.data, employee, recommendation, {})
        self.assertIn("Which role do you want to become?", page)
        self.assertNotIn("RL1", page)
        self.assertNotIn("RL2", page)
        self.assertNotIn("RL3", page)
        self.assertNotIn("RL4", page)


if __name__ == "__main__":
    unittest.main()
