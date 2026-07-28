from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import mimetypes
import re

from ..backend import MyCareerBackend
from ..core.config import DATABASE_PATH, STATIC_DIR, STITCH_DIR
from ..core.logging_setup import get_logger
from ..data_sources import WorkbookData
from ..database import Database
from .api import BackendAPI
from .templates import render_template
from .views import backend_status


log = get_logger("skillsync.server")


STITCH_PAGES = {
    "login": "login_portal_final",
    "zm/welcome": "zm_welcome_screen",
    "zm/assessments": "zm_competency_assessment_list",
    "zm/dashboard": "zm_dashboard_final",
    "zm/leaderboard": "zm_learning_leaderboard",
    "rd/welcome": "rd_welcome_screen",
    "rd/validations": "rd_competency_validation_list_1",
    "rd/validation": "rd_validation_detail",
    "rd/dashboard": "rd_dashboard_final",
    "rd/leaderboard": "rd_learning_leaderboard_1",
    "employee/welcome": "employee_welcome_screen",
    "employee/roleplays": "employee_role_play_gate",
    "employee/career": "employee_career_roadmap",
    "employee/courses": "employee_shop_your_courses_2",
    "employee/learning": "employee_learning_journey_2",
    "employee/leaderboard": "employee_leaderboard_1",
    "admin/overview": "admin_overview_final",
    "admin/phases": "admin_phase_control",
    "admin/employees": "admin_employee_master_table",
    "admin/leaderboard": "rd_learning_leaderboard_1",
    "admin/confidence": "admin_confidence_scores",
    "admin/audit": "admin_agent_audit",
    "lteam/dashboard": "rd_learning_leaderboard_1",
}


def prepare_stitch_html(html: str, route: str) -> str:
    injection = f'<script>window.MYCAREER_PAGE={route!r};</script><script src="/stitch/runtime.js"></script>'
    if route == "login":
        return html.replace("</body>", f"{injection}</body>")
    return re.sub(
        r"<body\b[^>]*>.*?</body>",
        f'<body><div id="mycareer-app"></div>{injection}</body>',
        html,
        count=1,
        flags=re.DOTALL | re.IGNORECASE,
    )


class MyCareerServer:
    def __init__(self) -> None:
        self.data = WorkbookData()
        self.database = Database(DATABASE_PATH)
        self.backend = MyCareerBackend(self.data, self.database)
        self.api = BackendAPI(self.backend)
        log.info(
            "Backend ready employees=%s database=%s (SQLite persists assessments/roleplays/career/evidence)",
            len(self.data.employees),
            DATABASE_PATH.resolve(),
        )

    def handler(self) -> type[BaseHTTPRequestHandler]:
        app = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                path = urlparse(self.path).path
                if path.startswith("/ws/voice-roleplay"):
                    from ..voice_live.ws_bridge import handle_voice_roleplay_ws

                    handle_voice_roleplay_ws(self, app.backend)
                    return
                if path.startswith("/api/"):
                    app.api.handle_get(self)
                elif path == "/app" or path == "/app/":
                    self.send_response(302)
                    self.send_header("Location", "/app/login")
                    self.end_headers()
                elif path.startswith("/app/"):
                    self.send_stitch_page(path.removeprefix("/app/").strip("/"))
                elif path.startswith("/stitch/"):
                    self.send_stitch_asset(path.removeprefix("/stitch/"))
                elif path.startswith("/static/"):
                    self.send_static(path)
                elif path in {"/", "/backend"}:
                    self.send_html(backend_status(app.data, app.backend))
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)

            def do_HEAD(self) -> None:
                # Render health checks use HEAD; BaseHTTPRequestHandler defaults to 501.
                path = urlparse(self.path).path
                if (
                    path in {"/", "/backend", "/api/health"}
                    or path.startswith("/api/")
                    or path.startswith("/app")
                ):
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_error(HTTPStatus.NOT_FOUND)

            def do_POST(self) -> None:
                path = urlparse(self.path).path
                if path.startswith("/api/"):
                    app.api.handle_post(self)
                else:
                    self.send_error(
                        HTTPStatus.GONE,
                        "Legacy frontend retired. Connect Stitch frontend to /api/* endpoints.",
                    )

            def do_OPTIONS(self) -> None:
                if urlparse(self.path).path.startswith("/api/"):
                    app.api.handle_options(self)
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)

            def send_html(self, body: str) -> None:
                payload = render_template(
                    "base.html", title="MyCareer Compass Backend", page_role="admin", body=body
                ).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)

            def send_static(self, path: str) -> None:
                relative = Path(path.removeprefix("/static/"))
                target = (STATIC_DIR / relative).resolve()
                if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.is_file():
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                payload = target.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(payload)

            def send_stitch_page(self, route: str) -> None:
                folder = STITCH_PAGES.get(route)
                target = STITCH_DIR / str(folder) / "code.html" if folder else None
                if not target or not target.is_file():
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                html = target.read_text(encoding="utf-8")
                payload = prepare_stitch_html(html, route).encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.end_headers()
                self.wfile.write(payload)

            def send_stitch_asset(self, relative_path: str) -> None:
                target = (STITCH_DIR / relative_path).resolve()
                if not str(target).startswith(str(STITCH_DIR.resolve())) or not target.is_file():
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                payload = target.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: object) -> None:
                log.info("HTTP %s", format % args)

        return Handler


def create_server(host: str = "0.0.0.0", port: int = 5050) -> ThreadingHTTPServer:
    application = MyCareerServer()
    log.info("Binding HTTP server host=%s port=%s", host, port)
    return ThreadingHTTPServer((host, port), application.handler())
