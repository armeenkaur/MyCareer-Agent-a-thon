from __future__ import annotations

from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
import cgi
import mimetypes
import re

from ..agents.behavioral import extract_behavioral_evidence, score_behavioral_batch
from ..agents.logging import log_entry
from ..core.config import PROFICIENCY_ORDER, STATIC_DIR, UPLOAD_DIR
from ..core.logging_setup import get_logger
from ..core.utils import slug
from ..data_sources import WorkbookData
from ..profile_pipeline import inputs_ready, start_pipeline_background
from ..linkedin_learning import sync_learning_activity
from ..agents.feedback import analyze_feedback
from ..state import RuntimeState
from .templates import render_template
from . import views

log = get_logger("skillsync.server")


class MyCareerServer:
    def __init__(self) -> None:
        self.data = WorkbookData()
        self.state = RuntimeState()
        log.info("Workbook loaded employees=%s", len(self.data.employees))

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
                    "/employee/shop": lambda: views.course_shop(app.data, app.state, query),
                    "/employee/journey": lambda: views.learning_journey(app.data, app.state, query),
                    "/employee/resource": lambda: self.open_external_resource(query),
                    "/manager": lambda: views.manager_dashboard(app.data, app.state, query),
                    "/manager/employee": lambda: views.manager_employee(app.data, app.state, query),
                    "/admin": lambda: views.admin_dashboard(app.data, app.state, query),
                    "/feedback": lambda: views.feedback_page(app.data, app.state, query),
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
                elif parsed.path == "/employee/behavioral-submit":
                    self.post_behavioral_submit()
                elif parsed.path == "/employee/career-choice":
                    self.post_career_choice()
                elif parsed.path == "/manager/submit":
                    self.post_manager_form()
                elif parsed.path == "/employee/checkout":
                    self.post_course_checkout()
                elif parsed.path == "/employee/complete":
                    self.post_course_completion()
                elif parsed.path == "/employee/external-complete":
                    self.post_external_completion()
                elif parsed.path == "/admin/linkedin/sync":
                    self.post_linkedin_sync()
                elif parsed.path == "/feedback/submit":
                    self.post_feedback()
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)

            def send_html(self, body: str, status: HTTPStatus = HTTPStatus.OK) -> None:
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                requested_role = (query.get("role") or [""])[0]
                if parsed.path.startswith("/manager") or requested_role == "manager":
                    page_role = "manager"
                elif parsed.path.startswith("/admin") or requested_role == "admin":
                    page_role = "admin"
                else:
                    page_role = "employee"
                payload = render_template(
                    "base.html",
                    title="MyCareer Compass",
                    page_role=page_role,
                    body=body,
                ).encode("utf-8")
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
                try:
                    self.send_response(HTTPStatus.SEE_OTHER)
                    self.send_header("Location", path)
                    self.end_headers()
                except (BrokenPipeError, ConnectionResetError):
                    log.info("Client disconnected before redirect path=%s", path)

            def redirect_external(self, url: str) -> None:
                self.send_response(HTTPStatus.SEE_OTHER)
                self.send_header("Location", url)
                self.end_headers()

            def read_form(self) -> dict[str, str]:
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length).decode("utf-8")
                self._last_raw_form = raw
                return {key: values[0] for key, values in parse_qs(raw).items()}

            def read_ratings(self, form: dict[str, str], skills: list[str]) -> dict[str, str] | None:
                ratings: dict[str, str] = {}
                for skill in skills:
                    value = form.get(slug(skill), "")
                    if value not in PROFICIENCY_ORDER:
                        return None
                    ratings[skill] = value
                return ratings

            def maybe_run_pipeline(self, emp_code: str) -> None:
                ready = inputs_ready(app.data, app.state, emp_code)
                log.info("Pipeline trigger check emp=%s ready=%s", emp_code, ready)
                if ready:
                    started = start_pipeline_background(app.data, app.state, emp_code)
                    log.info("Pipeline background emp=%s started=%s", emp_code, started)

            def post_employee_form(self) -> None:
                form = self.read_form()
                emp_code = form.get("emp_code", "")
                ratings = self.read_ratings(form, app.data.functional_skills)
                log.info("POST /employee/submit emp=%s ratings_ok=%s", emp_code, bool(ratings))
                if emp_code and ratings and emp_code not in app.state.employee_forms:
                    app.state.employee_forms[emp_code] = ratings
                    app.state.agent_logs.append(log_entry(emp_code, "Backend", "Employee functional form locked."))
                    self.maybe_run_pipeline(emp_code)
                self.redirect(f"/employee?emp={emp_code}&section=functional")

            def post_manager_form(self) -> None:
                form = self.read_form()
                emp_code = form.get("emp_code", "")
                ratings = self.read_ratings(form, app.data.functional_skills)
                log.info("POST /manager/submit emp=%s ratings_ok=%s", emp_code, bool(ratings))
                if emp_code and ratings and emp_code not in app.state.manager_forms:
                    app.state.manager_forms[emp_code] = ratings
                    app.state.agent_logs.append(log_entry(emp_code, "Backend", "Manager functional form locked."))
                    self.maybe_run_pipeline(emp_code)
                self.redirect(f"/manager/employee?emp={emp_code}")

            def post_behavioral_upload(self) -> None:
                form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD": "POST"})
                emp_code = str(form.getfirst("emp_code", ""))
                skill = str(form.getfirst("skill", ""))
                item = form["screenshot"] if "screenshot" in form else None
                filename = ""
                if item is not None:
                    filename = str(getattr(item, "filename", "") or "")
                log.info(
                    "POST /employee/upload emp=%s skill=%s has_file=%s filename=%s",
                    emp_code,
                    skill,
                    bool(filename),
                    filename,
                )
                if emp_code and skill and filename and emp_code not in app.state.behavioral_submitted:
                    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(filename).name)
                    payload = item.file.read()
                    UPLOAD_DIR.mkdir(exist_ok=True)
                    path = UPLOAD_DIR / f"{emp_code}_{slug(skill)}_{safe_name}"
                    path.write_bytes(payload)
                    log.info("Saved upload path=%s bytes=%s", path, len(payload))
                    extract_behavioral_evidence(emp_code, skill, safe_name, payload, app.state)
                self.redirect(f"/employee?emp={emp_code}&section=behavioral")

            def post_behavioral_submit(self) -> None:
                form = self.read_form()
                emp_code = form.get("emp_code", "")
                uploads = app.state.behavioral_uploads.get(emp_code, {})
                all_uploaded = all(skill in uploads for skill in app.data.behavioral_skills)
                if emp_code in app.state.behavioral_submitted:
                    self.redirect(f"/employee?emp={emp_code}&section=overview")
                    return
                if not all_uploaded:
                    self.redirect(f"/employee?{urlencode({'emp': emp_code, 'section': 'behavioral', 'error': 'Upload all behavioural screenshots before submitting.'})}")
                    return
                if not score_behavioral_batch(emp_code, app.data.behavioral_skills, app.state):
                    self.redirect(f"/employee?{urlencode({'emp': emp_code, 'section': 'behavioral', 'error': 'BBehavioural assessment service is temporarily unavailable. Your uploads are saved. Please submit again later.'})}")
                    return
                app.state.behavioral_submitted.add(emp_code)
                app.state.agent_logs.append(log_entry(emp_code, "Backend", "Behavioural response submitted and locked."))
                self.maybe_run_pipeline(emp_code)
                self.redirect(f"/employee?emp={emp_code}&section=overview")

            def post_course_checkout(self) -> None:
                form = self.read_form()
                emp_code = form.get("emp_code", "")
                recommendation = app.state.recommendations.get(emp_code, {})
                active_skills = set(recommendation.get("skills", {}))
                if recommendation.get("ideal_reached") and recommendation.get("career_options"):
                    choice = app.state.career_choices.get(emp_code, "")
                    option = next((row for row in recommendation["career_options"] if row.get("id") == choice), None)
                    if not option:
                        self.redirect(f"/employee/shop?emp={emp_code}")
                        return
                    active_skills = set(option.get("skills", []))
                selected = set(parse_qs(self._last_raw_form).get("course", []))
                valid_ids = {
                    str(course.get("id"))
                    for skill, rows in recommendation.get("skills", {}).items()
                    if skill in active_skills
                    for course in rows
                }
                selected &= valid_ids
                external_selected = set(parse_qs(self._last_raw_form).get("external", []))
                valid_external_ids = {
                    str(resource.get("id"))
                    for skill, rows in recommendation.get("external", {}).items()
                    if skill in active_skills
                    for resource in rows
                }
                external_selected &= valid_external_ids
                app.state.learning_selections[emp_code] = sorted(selected)
                app.state.external_selections[emp_code] = sorted(external_selected)
                missing = [
                    skill for skill, rows in recommendation.get("skills", {}).items()
                    if skill in active_skills
                    if not any(str(course.get("id")) in selected for course in rows)
                ]
                if missing:
                    self.redirect(f"/employee/shop?{urlencode({'emp': emp_code, 'error': 'Choose at least one LinkedIn course for every outlined skill.', 'missing': '|'.join(missing)})}")
                    return
                app.state.learning_completed.setdefault(emp_code, set())
                app.state.external_completed.setdefault(emp_code, set())
                app.state.agent_logs.append(log_entry(emp_code, "Learning Journey", f"Checked out {len(selected)} LinkedIn courses and {len(external_selected)} open resources."))
                self.redirect(f"/employee/journey?emp={emp_code}")

            def post_career_choice(self) -> None:
                form = self.read_form()
                emp_code = form.get("emp_code", "")
                choice = form.get("career_choice", "")
                recommendation = app.state.recommendations.get(emp_code, {})
                valid = {str(row.get("id")) for row in recommendation.get("career_options", [])}
                if choice not in valid:
                    self.redirect(f"/employee/shop?{urlencode({'emp': emp_code, 'error': 'Choose one career role to continue.'})}")
                    return
                previous = app.state.career_choices.get(emp_code)
                app.state.career_choices[emp_code] = choice
                option = next(row for row in recommendation["career_options"] if str(row.get("id")) == choice)
                recommendation["exploration_path"] = option.get("label", "")
                if previous and previous != choice:
                    app.state.learning_selections.pop(emp_code, None)
                    app.state.external_selections.pop(emp_code, None)
                    app.state.learning_completed.pop(emp_code, None)
                    app.state.external_completed.pop(emp_code, None)
                app.state.agent_logs.append(log_entry(emp_code, "Career Path", f"Selected {option.get('label')}."))
                self.redirect(f"/employee/shop?emp={emp_code}")

            def post_external_completion(self) -> None:
                form = self.read_form()
                emp_code = form.get("emp_code", "")
                resource_id = form.get("resource_id", "")
                if resource_id in set(app.state.external_selections.get(emp_code, [])):
                    completed = app.state.external_completed.setdefault(emp_code, set())
                    if resource_id in completed:
                        completed.remove(resource_id)
                    else:
                        completed.add(resource_id)
                    app.state.agent_logs.append(log_entry(emp_code, "Learning Tracker", f"Open resource {resource_id} completion toggled."))
                self.redirect(f"/employee/journey?emp={emp_code}")

            def post_linkedin_sync(self) -> None:
                result = sync_learning_activity(app.data, app.state)
                self.redirect(f"/admin?linkedin={result.get('status', 'error')}")

            def post_feedback(self) -> None:
                form = self.read_form()
                role = form.get("actor_role", "employee")
                actor_id = form.get("actor_id", "")
                target = form.get("target_agent", "")
                message = form.get("message", "").strip()
                if not message:
                    self.redirect(f"/feedback?{urlencode({'role': role, 'actor': actor_id, 'error': 'Feedback cannot be empty.'})}")
                    return
                result = analyze_feedback(app.state, role, actor_id, target, message)
                self.redirect(f"/feedback?{urlencode({'role': role, 'actor': actor_id, 'status': 'accepted' if result['relevant'] else 'rejected'})}")

            def post_course_completion(self) -> None:
                form = self.read_form()
                emp_code = form.get("emp_code", "")
                course_id = form.get("course_id", "")
                selected = set(app.state.learning_selections.get(emp_code, []))
                if course_id in selected:
                    completed = app.state.learning_completed.setdefault(emp_code, set())
                    if course_id in completed:
                        completed.remove(course_id)
                    else:
                        completed.add(course_id)
                    app.state.agent_logs.append(log_entry(emp_code, "Learning Tracker", f"Course {course_id} completion toggled."))
                self.redirect(f"/employee/journey?emp={emp_code}")

            def open_external_resource(self, query: dict[str, str]) -> None:
                emp_code = query.get("emp", "")
                resource_id = query.get("id", "")
                recommendation = app.state.recommendations.get(emp_code, {})
                resource = next(
                    (row for rows in recommendation.get("external", {}).values() for row in rows if row.get("id") == resource_id),
                    None,
                )
                if not resource:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                app.state.external_clicks.setdefault(emp_code, {})[resource_id] = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                app.state.agent_logs.append(log_entry(emp_code, "Learning Tracker", f"Opened external resource {resource_id}."))
                self.redirect_external(str(resource["url"]))

        return Handler


def create_server(host: str = "127.0.0.1", port: int = 5050) -> ThreadingHTTPServer:
    application = MyCareerServer()
    return ThreadingHTTPServer((host, port), application.handler())
