from __future__ import annotations

from ..core.config import PROFICIENCY_ORDER, UPLOAD_DIR
from ..core.utils import escape, slug
from ..data_sources import WorkbookData
from ..profile_pipeline import analytics, compute_or_get_profile
from ..state import RuntimeState


def home(data: WorkbookData) -> str:
    return f"""
    <section class="grid">
      <div class="span-7">
        <h1>MyCareer Compass</h1>
        <p>Agent-a-thon production-style MVP for BD skill profiling and Level 2 gap identification.</p>
      </div>
      <div class="span-5 card">
        <h2>Current Build Scope</h2>
        <p>Functional scoring is backend math. Agents handle behavioural evidence, context interpretation, score adjustment, confidence, and gaps.</p>
        <div class="actions">
          <a class="button" href="/employee">Employee</a>
          <a class="button secondary" href="/manager">Manager</a>
          <a class="button ghost" href="/admin">Admin</a>
        </div>
      </div>
      <div class="span-12 card">
        <h2>Loaded Source Data</h2>
        <table><tr><th>Source</th><th>Status</th></tr>
          <tr><td>Competency and ideal matrix</td><td><span class="pill">Loaded</span></td></tr>
          <tr><td>Darwin employee demographics</td><td><span class="pill">Loaded {len(data.employees)} employees</span></td></tr>
          <tr><td>TNA</td><td><span class="pill">Always used</span></td></tr>
          <tr><td>Appraisal feedback</td><td><span class="pill">Treated as recent</span></td></tr>
          <tr><td>Amber and variable pay</td><td><span class="pill">Loaded</span></td></tr>
        </table>
      </div>
    </section>
    """


def employee_dashboard(data: WorkbookData, state: RuntimeState, query: dict[str, str]) -> str:
    emp_code = query.get("emp") or next(iter(data.employees))
    employee = data.employees.get(emp_code) or next(iter(data.employees.values()))
    emp_code = employee["code"]
    profile = compute_or_get_profile(data, state, emp_code)
    self_locked = emp_code in state.employee_forms
    manager_locked = emp_code in state.manager_forms

    body = [employee_picker(data, "/employee", emp_code), profile_card(employee)]
    body.append("<section class='grid'>")
    body.append("<div class='span-6 card'><h2>Functional Skill Form</h2>")
    if self_locked:
        body.append("<div class='notice locked'>Your response is locked until the project is restarted.</div>")
        body.append(ratings_table(state.employee_forms[emp_code], "Your submitted rating"))
    else:
        body.append("<p>Submit once. This locks immediately after submission.</p>")
        body.append(rating_form("/employee/submit", emp_code, data.functional_skills, "Submit self-rating"))
    body.append("</div>")
    body.append("<div class='span-6 card'><h2>Behavioural Assessment Upload</h2>")
    body.append("<p>Upload one screenshot per role-play. The agent stores only the assigned proficiency level.</p>")
    body.append(upload_form(data, emp_code))
    body.append(behavioral_status(data, state, emp_code))
    body.append("</div></section>")

    if not manager_locked:
        body.append("<section class='card'><div class='notice warn'>Waiting for manager response.</div></section>")
    elif profile:
        body.append("<section class='card'><h2>Level 2 Skill Gaps</h2>")
        if profile["gaps"]:
            body.append(employee_gaps_table(profile["gaps"]))
        else:
            body.append("<div class='notice'>No Level 2 skill gaps identified for your current role and level.</div>")
        body.append("</section>")
    return "".join(body)


def manager_dashboard(data: WorkbookData, state: RuntimeState, query: dict[str, str]) -> str:
    manager = query.get("manager") or (data.managers()[0] if data.managers() else "")
    rows = []
    for emp in data.team_for_manager(manager):
        status = "Locked" if emp["code"] in state.manager_forms else "Pending"
        rows.append(
            f"<tr><td>{escape(emp['code'])}</td><td>{escape(emp['name'])}</td><td>{escape(emp['designation'])}</td>"
            f"<td>{escape(emp['level'])}</td><td><span class='pill'>{status}</span></td>"
            f"<td><a class='button ghost' href='/manager/employee?emp={escape(emp['code'])}'>Open</a></td></tr>"
        )
    return f"""
    <section class="grid">
      <div class="span-4 card">{manager_picker(data, manager)}</div>
      <div class="span-8 card">
        <h2>Team Members</h2>
        <table><tr><th>Code</th><th>Name</th><th>Role</th><th>Level</th><th>Form</th><th></th></tr>{''.join(rows)}</table>
      </div>
    </section>
    """


def manager_employee(data: WorkbookData, state: RuntimeState, query: dict[str, str]) -> str:
    emp_code = query.get("emp") or next(iter(data.employees))
    employee = data.employees.get(emp_code) or next(iter(data.employees.values()))
    emp_code = employee["code"]
    locked = emp_code in state.manager_forms
    body = [profile_card(employee)]
    body.append("<section class='grid'>")
    body.append("<div class='span-5 card'><h2>Manager Functional Rating</h2>")
    if locked:
        body.append("<div class='notice locked'>Your manager response is locked until the project is restarted.</div>")
        body.append(ratings_table(state.manager_forms[emp_code], "Your submitted rating"))
    else:
        body.append(rating_form("/manager/submit", emp_code, data.functional_skills, "Submit manager rating"))
    body.append("</div>")
    body.append("<div class='span-7 card'><h2>Supporting Context</h2>")
    body.append(context_view(data, emp_code))
    body.append("</div></section>")
    return "".join(body)


def admin_dashboard(data: WorkbookData, state: RuntimeState) -> str:
    stats = analytics(data, state)
    return f"""
    <section class="grid">
      <div class="span-12"><h1>Admin Dashboard</h1><p>Auto-approved pipeline, source management view, logs, and analytics.</p></div>
      <div class="span-4 card"><h2>Pipeline</h2>{metric("Employees", stats["employee_count"])}{metric("Employee forms", stats["employee_forms"])}{metric("Manager forms", stats["manager_forms"])}{metric("Completed profiles", stats["completed_profiles"])}</div>
      <div class="span-8 card"><h2>Source Files</h2>{source_files_table()}</div>
      <div class="span-6 card"><h2>Gap Analytics by Level</h2>{dict_table(stats["gap_by_level"], "Level", "Gap count")}</div>
      <div class="span-6 card"><h2>Gap Analytics by Manager</h2>{dict_table(stats["gap_by_manager"], "Manager", "Gap count")}</div>
      <div class="span-6 card"><h2>Missing Data</h2><p>{len(stats["missing_employee_form"])} employee forms pending. {len(stats["missing_manager_form"])} manager forms pending.</p></div>
      <div class="span-6 card"><h2>Low Confidence Profiles</h2><p>{escape(', '.join(stats["low_confidence"]) or 'None')}</p></div>
      <div class="span-12 card"><h2>Agent Pipeline Logs</h2><div class="scroll">{logs_table(state)}</div></div>
    </section>
    """


def employee_picker(data: WorkbookData, path: str, selected: str) -> str:
    options = "".join(
        f"<option value='{escape(emp['code'])}' {'selected' if emp['code']==selected else ''}>{escape(emp['code'])} - {escape(emp['name'])}</option>"
        for emp in data.employee_options()
    )
    return f"<form class='card' method='get' action='{path}'><label>Employee</label><select name='emp' onchange='this.form.submit()'>{options}</select></form>"


def manager_picker(data: WorkbookData, selected: str) -> str:
    options = "".join(f"<option value='{escape(name)}' {'selected' if name==selected else ''}>{escape(name)}</option>" for name in data.managers())
    return f"<h2>Manager</h2><form method='get' action='/manager'><select name='manager' onchange='this.form.submit()'>{options}</select></form>"


def profile_card(employee: dict[str, object]) -> str:
    return f"""
    <section class="card">
      <h1>{escape(employee['name'])}</h1>
      <p>{escape(employee['designation'])} · {escape(employee['level'])} · {escape(employee['location'])} · Manager: {escape(employee['manager'])}</p>
    </section>
    """


def rating_form(action: str, emp_code: str, skills: list[str], label: str) -> str:
    fields = [f"<input type='hidden' name='emp_code' value='{escape(emp_code)}'>"]
    for skill in skills:
        options = "".join(f"<option value='{value}'>{value}</option>" for value in PROFICIENCY_ORDER)
        fields.append(f"<label>{escape(skill)}</label><select name='{slug(skill)}'>{options}</select>")
    fields.append(f"<div class='actions'><button type='submit'>{escape(label)}</button></div>")
    return f"<form method='post' action='{action}'>{''.join(fields)}</form>"


def ratings_table(values: dict[str, str], heading: str) -> str:
    rows = "".join(f"<tr><td>{escape(skill)}</td><td>{escape(score)}</td></tr>" for skill, score in values.items())
    return f"<h3>{escape(heading)}</h3><table><tr><th>Skill</th><th>Rating</th></tr>{rows}</table>"


def upload_form(data: WorkbookData, emp_code: str) -> str:
    options = "".join(f"<option value='{escape(skill)}'>{escape(skill)}</option>" for skill in data.behavioral_skills)
    return f"""
    <form method="post" action="/employee/upload" enctype="multipart/form-data">
      <input type="hidden" name="emp_code" value="{escape(emp_code)}">
      <label>Behavioural skill</label><select name="skill">{options}</select>
      <label>Screenshot</label><input type="file" name="screenshot" accept="image/*">
      <div class="actions"><button type="submit">Upload screenshot</button></div>
    </form>
    """


def behavioral_status(data: WorkbookData, state: RuntimeState, emp_code: str) -> str:
    rows = []
    for skill in data.behavioral_skills:
        link = data.roleplay_links.get(skill, "")
        score = state.behavioral_scores.get(emp_code, {}).get(skill)
        upload = state.behavioral_uploads.get(emp_code, {}).get(skill)
        status = f"{escape(score)} from {escape(upload)}" if score else "Pending"
        rows.append(f"<tr><td><a href='{escape(link)}' target='_blank'>{escape(skill)}</a></td><td>{status}</td></tr>")
    return f"<table><tr><th>Role-play</th><th>Upload status</th></tr>{''.join(rows)}</table>"


def employee_gaps_table(gaps: list[dict[str, str]]) -> str:
    rows = "".join(f"<tr><td>{escape(gap['skill'])}</td></tr>" for gap in gaps)
    return f"<table><tr><th>Skill gap</th></tr>{rows}</table>"


def context_view(data: WorkbookData, emp_code: str) -> str:
    tna = data.tna.get(emp_code, [])
    appraisal = data.appraisal.get(emp_code, {})
    amber = data.amber.get(emp_code, [])
    tna_rows = "".join(
        f"<tr><td>{escape(row.get('Employee Input'))}</td><td>{escape(row.get('Reporting Manager Input'))}</td></tr>"
        for row in tna[:5]
    )
    appraisal_bits = [
        appraisal.get("What Are The Top 3 Skills & Capabilities Exhibited By Your Team Member In The Current Role?", ""),
        appraisal.get("What Are 2-3 Development Areas Or Skills That Your Team Member Needs To Develop, To Grow Further?", ""),
    ]
    amber_rows = "".join(
        f"<tr><td>{escape(row.get('Question'))}</td><td>{escape(row.get('Answer'))}</td></tr>" for row in amber[:4]
    )
    return f"""
    <h3>TNA</h3><table><tr><th>Employee Input</th><th>Manager Input</th></tr>{tna_rows or '<tr><td colspan="2">No TNA rows</td></tr>'}</table>
    <h3>Annual Feedback</h3><p>{escape(' '.join(appraisal_bits))[:1200]}</p>
    <h3>Amber</h3><table><tr><th>Question</th><th>Answer</th></tr>{amber_rows or '<tr><td colspan="2">No Amber rows</td></tr>'}</table>
    """


def metric(label: str, value: object) -> str:
    return f"<div class='metric'><span>{escape(label)}</span><strong>{escape(value)}</strong></div>"


def source_files_table() -> str:
    sources = [
        ("Employee skill forms", "Captured in app"),
        ("Manager skill forms", "Captured in app"),
        ("Udemy screenshots", str(UPLOAD_DIR)),
        ("Cleaned TNA data", "Cleaned Up TNA data.xlsx"),
        ("Annual feedback", "Appraisal Input.xlsx"),
        ("Amber input", "Agent-a-thon (Amber).xlsx"),
        ("Variable pay scores", "Variable Pay scores.xlsx"),
        ("Demographics", "Employee Darwin.xlsx"),
        ("Ideal proficiency matrix", "MyCareer_Process Flow.xlsx"),
    ]
    rows = "".join(f"<tr><td>{escape(name)}</td><td>{escape(value)}</td></tr>" for name, value in sources)
    return f"<table><tr><th>Input</th><th>Location</th></tr>{rows}</table>"


def dict_table(values: dict[str, int], left: str, right: str) -> str:
    if not values:
        return "<p>No completed profiles yet.</p>"
    rows = "".join(f"<tr><td>{escape(key)}</td><td>{escape(value)}</td></tr>" for key, value in sorted(values.items()))
    return f"<table><tr><th>{escape(left)}</th><th>{escape(right)}</th></tr>{rows}</table>"


def logs_table(state: RuntimeState) -> str:
    if not state.agent_logs:
        return "<p>No agent logs yet.</p>"
    rows = "".join(
        f"<tr><td>{escape(row['time'])}</td><td>{escape(row['employee'])}</td><td>{escape(row['agent'])}</td><td>{escape(row['message'])}</td></tr>"
        for row in state.agent_logs[-120:]
    )
    return f"<table><tr><th>Time</th><th>Employee</th><th>Agent</th><th>Message</th></tr>{rows}</table>"
