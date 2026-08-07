from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import mimetypes
import os
import re
import ssl

from ..backend import MyCareerBackend
from ..core.config import DATABASE_PATH, STATIC_DIR, STITCH_DIR, database_is_ephemeral
from ..database import Database
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
        self.database = Database.open()
        self.backend = MyCareerBackend(self.data, self.database)
        self.api = BackendAPI(self.backend)
        db_label = (
            f"mysql://{self.database.mysql['host']}:{self.database.mysql['port']}/{self.database.mysql['database']}"
            if self.database.engine == "mysql" and self.database.mysql
            else str((self.database.path or DATABASE_PATH).resolve())
        )
        log.info(
            "Backend ready employees=%s engine=%s database=%s",
            len(self.data.employees),
            self.database.engine,
            db_label,
        )
        if self.database.engine == "sqlite" and database_is_ephemeral():
            log.error(
                "DATABASE ON EPHEMERAL RENDER DISK (%s). ZM/RD assessments WILL BE LOST on "
                "redeploy or free-tier spin-down. Use MySQL (MYSQL_HOST/...) or attach Persistent Disk.",
                db_label,
            )

    def handler(self) -> type[BaseHTTPRequestHandler]:
        app = self
        tls_on = bool(
            (os.environ.get("SSL_CERTFILE") or "").strip()
            and (os.environ.get("SSL_KEYFILE") or "").strip()
        )

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def _behind_https_proxy(self) -> bool:
                return str(self.headers.get("X-Forwarded-Proto") or "").strip().lower() == "https"

            def end_headers(self) -> None:
                # HTTPS-compatible defaults (direct TLS or reverse-proxy TLS termination).
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
                if tls_on or self._behind_https_proxy():
                    self.send_header("Strict-Transport-Security", "max-age=31536000")
                super().end_headers()

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
    server = ThreadingHTTPServer((host, port), application.handler())
    cert = (os.environ.get("SSL_CERTFILE") or "").strip()
    key = (os.environ.get("SSL_KEYFILE") or "").strip()
    if cert and key:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(certfile=cert, keyfile=key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        log.info("TLS enabled (TLSv1.2+) cert=%s", cert)
    elif cert or key:
        log.warning("Set both SSL_CERTFILE and SSL_KEYFILE to enable HTTPS")
    return server
