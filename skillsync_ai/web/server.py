from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import cgi
import mimetypes
import re

from ..agents.behavioral import score_behavioral_evidence
from ..agents.logging import log_entry
from ..core.config import STATIC_DIR, UPLOAD_DIR
from ..core.utils import slug
from ..data_sources import WorkbookData
from ..profile_pipeline import compute_or_get_profile
from ..state import RuntimeState
from .templates import render_template
from . import views


class MyCareerServer:
    def __init__(self) -> None:
        self.data = WorkbookData()
        self.state = RuntimeState()

    def handler(self) -> type[BaseHTTPRequestHandler]:
        app = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
                if parsed.path.startswith("/static/"):
                    self.send_static(parsed.path)
                    return
                routes = {
                    "/": lambda: views.home(app.data),
                    "/employee": lambda: views.employee_dashboard(app.data, app.state, query),
                    "/manager": lambda: views.manager_dashboard(app.data, app.state, query),
                    "/manager/employee": lambda: views.manager_employee(app.data, app.state, query),
                    "/admin": lambda: views.admin_dashboard(app.data, app.state),
                }
                route = routes.get(parsed.path)
                if route:
                    self.send_html(route())
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)

            def do_POST(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path == "/employee/submit":
                    self.post_employee_form()
                elif parsed.path == "/employee/upload":
                    self.post_behavioral_upload()
                elif parsed.path == "/manager/submit":
                    self.post_manager_form()
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)

            def send_html(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
                payload = render_template("base.html", title="MyCareer Compass", body=body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def send_static(self, path: str) -> None:
                relative = Path(path.removeprefix("/static/"))
                target = (STATIC_DIR / relative).resolve()
                if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.is_file():
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                payload = target.read_bytes()
                mime_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def redirect(self, path: str) -> None:
                self.send_response(HTTPStatus.SEE_OTHER)
                self.send_header("Location", path)
                self.end_headers()

            def read_form(self) -> dict[str, str]:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8")
                return {key: values[0] for key, values in parse_qs(raw).items()}

            def post_employee_form(self) -> None:
                form = self.read_form()
                emp_code = form.get("emp_code", "")
                if emp_code and emp_code not in app.state.employee_forms:
                    app.state.employee_forms[emp_code] = {
                        skill: form.get(slug(skill), "Intermediate") for skill in app.data.functional_skills
                    }
                    app.state.agent_logs.append(log_entry(emp_code, "Backend", "Employee functional form locked."))
                self.redirect(f"/employee?emp={emp_code}")

            def post_manager_form(self) -> None:
                form = self.read_form()
                emp_code = form.get("emp_code", "")
                if emp_code and emp_code not in app.state.manager_forms:
                    app.state.manager_forms[emp_code] = {
                        skill: form.get(slug(skill), "Intermediate") for skill in app.data.functional_skills
                    }
                    app.state.agent_logs.append(log_entry(emp_code, "Backend", "Manager functional form locked."))
                    compute_or_get_profile(app.data, app.state, emp_code)
                self.redirect(f"/manager/employee?emp={emp_code}")

            def post_behavioral_upload(self) -> None:
                form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST"})
                emp_code = str(form.getfirst("emp_code", ""))
                skill = str(form.getfirst("skill", ""))
                item = form["screenshot"] if "screenshot" in form else None
                if emp_code and skill and item is not None and getattr(item, "filename", ""):
                    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(item.filename).name)
                    payload = item.file.read()
                    UPLOAD_DIR.mkdir(exist_ok=True)
                    path = UPLOAD_DIR / f"{emp_code}_{slug(skill)}_{safe_name}"
                    path.write_bytes(payload)
                    score_behavioral_evidence(emp_code, skill, safe_name, payload, app.state)
                    app.state.profiles.pop(emp_code, None)
                    compute_or_get_profile(app.data, app.state, emp_code)
                self.redirect(f"/employee?emp={emp_code}")

        return Handler


def create_server(host: str = "127.0.0.1", port: int = 5050) -> ThreadingHTTPServer:
    application = MyCareerServer()
    return ThreadingHTTPServer((host, port), application.handler())
