from __future__ import annotations

import tempfile
import unittest

from skillsync_ai.backend import MyCareerBackend
from skillsync_ai.data_sources import WorkbookData
from skillsync_ai.database import Database
from skillsync_ai.core.config import STITCH_DIR
from skillsync_ai.web.server import STITCH_PAGES, prepare_stitch_html
from skillsync_ai.web.views import backend_status


class HandoffContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = WorkbookData()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.backend = MyCareerBackend(self.data, Database(f"{self.temp.name}/handoff.db"))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_metadata_contract(self) -> None:
        self.assertEqual(len(self.data.competencies), 7)
        self.assertEqual(
            set(self.data.level_definitions["Communication"]),
            {"Beginner", "Intermediate", "Proficient", "Advanced"},
        )
        self.assertFalse(hasattr(self.data, "variable"))

    def test_backend_handoff_page_renders(self) -> None:
        page = backend_status(self.data, self.backend)
        self.assertIn("MyCareer Compass backend is ready", page)
        self.assertIn("/api/*", page)
        self.assertIn("44", page)
        self.assertIn("10,847", page)

    def test_stitch_routes_have_html_and_shared_runtime(self) -> None:
        self.assertEqual(len(STITCH_PAGES), 22)
        for folder in STITCH_PAGES.values():
            self.assertTrue((STITCH_DIR / folder / "code.html").is_file(), folder)
        self.assertTrue((STITCH_DIR / "runtime.js").is_file())

    def test_authenticated_pages_do_not_serve_stitch_demo_body(self) -> None:
        source = (STITCH_DIR / "admin_overview_final" / "code.html").read_text(encoding="utf-8")
        page = prepare_stitch_html(source, "admin/overview")

        self.assertIn('<div id="mycareer-app"></div>', page)
        self.assertIn("/stitch/runtime.js", page)
        self.assertNotIn("Jordan Smith", page)
        self.assertNotIn("94%", page)

    def test_login_keeps_interactive_form(self) -> None:
        source = (STITCH_DIR / "login_portal_final" / "code.html").read_text(encoding="utf-8")
        page = prepare_stitch_html(source, "login")

        self.assertIn('id="password-input"', page)
        self.assertIn("/stitch/runtime.js", page)

    def test_employee_welcome_uses_shared_shell_mount(self) -> None:
        source = (STITCH_DIR / "employee_welcome_screen" / "code.html").read_text(encoding="utf-8")
        page = prepare_stitch_html(source, "employee/welcome")

        self.assertIn('<div id="mycareer-app"></div>', page)
        self.assertIn("/stitch/runtime.js", page)
        self.assertNotIn("Jordan Smith", page)

    def test_zm_welcome_uses_shared_shell_mount(self) -> None:
        source = (STITCH_DIR / "zm_welcome_screen" / "code.html").read_text(encoding="utf-8")
        page = prepare_stitch_html(source, "zm/welcome")

        self.assertIn('<div id="mycareer-app"></div>', page)
        self.assertIn("/stitch/runtime.js", page)
        self.assertNotIn("Jordan Smith", page)


if __name__ == "__main__":
    unittest.main()
