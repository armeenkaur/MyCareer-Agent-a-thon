from __future__ import annotations

from pathlib import Path

from ..core.config import PROFICIENCY_ORDER, UPLOAD_DIR
from ..core.utils import escape, slug
from ..data_sources import WorkbookData
from ..profile_pipeline import analytics, compute_or_get_profile, inputs_ready
from ..state import RuntimeState


def home(data: WorkbookData) -> str:
    return f"""
    <div class="shell">
      <section class="grid">
        <div class="span-7">
          <h1>MyCareer Compass</h1>
          <p>BD skill profiling with agent pipeline: behavioural evidence, context rating, profile adjustment, confidence, and gap matrix.</p>
        </div>
        <div class="span-5 card">
          <h2>Portals</h2>
          <div class="actions">
            <a class="button" href="/employee">Employee</a>
            <a class="button secondary" href="/manager">Manager</a>
            <a class="button ghost" href="/admin">Admin</a>
          </div>
        </div>
        <div class="span-12 card">
          <h2>Reference data loaded for pipeline</h2>
          <table><tr><th>Source</th><th>Status</th></tr>
            <tr><td>Competency / ideal matrix</td><td><span class="pill">Loaded</span></td></tr>
            <tr><td>Darwin demographics</td><td><span class="pill">Loaded {len(data.employees)} employees</span></td></tr>
            <tr><td>TNA / Appraisal / Amber / Variable</td><td><span class="pill">Loaded</span></td></tr>
          </table>
        </div>
      </section>
    </div>
    """


def employee_dashboard(data: WorkbookData, state: RuntimeState, query: dict[str, str]) -> str:
    emp_code = query.get("emp") or next(iter(data.employees))
    employee = data.employees.get(emp_code) or next(iter(data.employees.values()))
    emp_code = employee["code"]
    profile = state.profiles.get(emp_code) or compute_or_get_profile(data, state, emp_code)
    self_locked = emp_code in state.employee_forms
    manager_locked = emp_code in state.manager_forms
    ready = inputs_ready(data, state, emp_code) and profile is not None
    section = query.get("section") or ("functional" if not self_locked else "overview")

    if section == "behavioral" and not self_locked:
        section = "functional"
    if section == "results" and not ready:
        section = "overview"

    pane = {
        "overview": _employee_overview(self_locked, manager_locked, ready, profile, data, state, emp_code),
        "functional": _employee_functional(data, state, emp_code, self_locked, manager_locked),
        "behavioral": _employee_behavioral(data, state, emp_code),
        "results": _employee_results(profile) if ready else _employee_overview(self_locked, manager_locked, ready, profile, data, state, emp_code),
    }.get(section, _employee_overview(self_locked, manager_locked, ready, profile, data, state, emp_code))

    return f"""
    <div class="layout">
      {employee_sidebar(emp_code, section, self_locked, ready)}
      <div class="content-pane">
        {employee_picker(data, "/employee", emp_code, section)}
        {profile_card(employee)}
        {pane}
      </div>
    </div>
    """


def employee_sidebar(emp_code: str, section: str, self_locked: bool, ready: bool) -> str:
    base = f"/employee?emp={escape(emp_code)}"
    items = [
        ("overview", "Overview", True),
        ("functional", "Functional skills", True),
        ("behavioral", "Behavioural assessment", self_locked),
        ("results", "My profile & gaps", ready),
    ]
    links = []
    for key, label, enabled in items:
        active = "active" if section == key else ""
        disabled = "disabled" if not enabled else ""
        href = f"{base}&section={key}" if enabled else "#"
        links.append(f"<a class='{active} {disabled}' href='{href}'>{escape(label)}</a>")
    return f"""
    <aside class="sidebar">
      <p class="sidebar-title">Employee workspace</p>
      <nav class="sidebar-nav">{''.join(links)}</nav>
    </aside>
    """


def _employee_overview(
    self_locked: bool,
    manager_locked: bool,
    ready: bool,
    profile: dict | None,
    data: WorkbookData,
    state: RuntimeState,
    emp_code: str,
) -> str:
    uploads = state.behavioral_uploads.get(emp_code, {})
    beh_done = sum(1 for skill in data.behavioral_skills if skill in uploads)
    beh_total = len(data.behavioral_skills)
    notices = []
    if not self_locked:
        notices.append("<div class='notice'>Start with <strong>Functional skills</strong>. Submit once — then it locks.</div>")
    elif not manager_locked:
        notices.append("<div class='notice warn'>Waiting for manager response.</div>")
    elif beh_done < beh_total:
        notices.append(f"<div class='notice warn'>Upload remaining behavioural screenshots ({beh_done}/{beh_total}).</div>")
    elif ready:
        notices.append("<div class='notice'>Pipeline complete. Open <strong>My profile & gaps</strong>.</div>")
    else:
        notices.append("<div class='notice warn'>Inputs ready — profile processing pending. Refresh shortly.</div>")

    return f"""
    <section class="card section-head">
      <h2>Overview</h2>
      <p>Fill functional skills once. Complete behavioural uploads. After manager submit + all uploads, your BD profile and gaps appear.</p>
      {''.join(notices)}
      <table>
        <tr><th>Step</th><th>Status</th></tr>
        <tr><td>Functional self-rating</td><td><span class="{'status-done' if self_locked else 'status-todo'}">{'Locked' if self_locked else 'To do'}</span></td></tr>
        <tr><td>Manager rating</td><td><span class="{'status-done' if manager_locked else 'status-todo'}">{'Done' if manager_locked else 'Waiting'}</span></td></tr>
        <tr><td>Behavioural uploads</td><td><span class="{'status-done' if beh_done==beh_total and beh_total else 'status-todo'}">{beh_done}/{beh_total}</span></td></tr>
        <tr><td>BD profile + gaps</td><td><span class="{'status-done' if ready else 'status-todo'}">{'Ready' if ready else 'Pending'}</span></td></tr>
      </table>
    </section>
    """


def _employee_functional(
    data: WorkbookData,
    state: RuntimeState,
    emp_code: str,
    self_locked: bool,
    manager_locked: bool,
) -> str:
    body = ["<section class='card section-head'><h2>Functional skills</h2>"]
    if self_locked:
        body.append("<div class='notice locked'>Your response is locked.</div>")
        if not manager_locked:
            body.append("<div class='notice warn'>Waiting for manager response.</div>")
        body.append(ratings_table(state.employee_forms[emp_code], "Your submitted rating"))
    else:
        body.append("<p>Pick one level per skill. No defaults. Submit once — locks immediately.</p>")
        body.append(rating_form("/employee/submit", emp_code, data.functional_skills, "Submit self-rating"))
    body.append("</section>")
    return "".join(body)


def _employee_behavioral(data: WorkbookData, state: RuntimeState, emp_code: str) -> str:
    cards = [behavioral_card(data, state, emp_code, skill) for skill in data.behavioral_skills]
    return f"""
    <section class="section-head">
      <h2>Behavioural assessment</h2>
      <p>Complete each role-play, then upload the screenshot. Status shows upload progress.</p>
    </section>
    <div class="assess-stack">{''.join(cards)}</div>
    """


def _employee_results(profile: dict) -> str:
    coaching = profile.get("coaching") or {}
    good = coaching.get("good_skills") or profile.get("good_skills") or []
    work_on = coaching.get("work_on_skills") or profile.get("work_on_skills") or []
    good_list = "".join(f"<li>{escape(skill)}</li>" for skill in good) or "<li>None listed yet</li>"
    body = [
        "<section class='card section-head'>",
        "<h2>Your development snapshot</h2>",
        f"<p>{escape(coaching.get('good_intro') or 'These are the skills you are good in:')}</p>",
        f"<ul class='skill-list'>{good_list}</ul>",
    ]
    if work_on:
        work_list = "".join(f"<li>{escape(skill)}</li>" for skill in work_on)
        body.append(f"<p>{escape(coaching.get('work_intro') or 'These are the skills you need to work on:')}</p>")
        body.append(f"<ul class='skill-list'>{work_list}</ul>")
    else:
        on_track = coaching.get("on_track_message") or "You're on track for your role and level."
        body.append(f"<div class='notice'>{escape(on_track)}</div>")
    if coaching.get("closing"):
        body.append(f"<p>{escape(coaching['closing'])}</p>")
    body.append("</section>")
    return "".join(body)


def behavioral_card(data: WorkbookData, state: RuntimeState, emp_code: str, skill: str) -> str:
    note = competency_note(data, skill) or "Complete the role-play scenario, then upload a screenshot of your result."
    link = data.roleplay_links.get(skill, "")
    upload = state.behavioral_uploads.get(emp_code, {}).get(skill)
    done = bool(upload)
    status = "<span class='status-done'>Uploaded</span>" if done else "<span class='status-todo'>To do</span>"
    start = (
        f"<a class='button' href='{escape(link)}' target='_blank' rel='noopener'>Start role-play</a>"
        if link
        else "<span class='button ghost'>Role-play link unavailable</span>"
    )
    upload_hint = f"<p class='prompt-text'>File: {escape(upload)}</p>" if upload else ""
    return f"""
    <article class="assess-card">
      <span class="badge">Behavioural skill</span>
      <h2>{escape(skill)}</h2>
      <p class="desc">{escape(note)}</p>
      <div class="prompt-box">
        <div class="prompt-label">Role-play prompt</div>
        <p class="prompt-text">Open the role-play for <strong>{escape(skill)}</strong>, complete the scenario, then upload your screenshot evidence below.</p>
        <div class="assess-actions">{start}{status}</div>
        {upload_hint}
        <form method="post" action="/employee/upload" enctype="multipart/form-data" class="upload-row">
          <input type="hidden" name="emp_code" value="{escape(emp_code)}">
          <input type="hidden" name="skill" value="{escape(skill)}">
          <div>
            <label>Upload screenshot</label>
            <input type="file" name="screenshot" accept="image/*" required>
          </div>
          <button type="submit">Upload file</button>
        </form>
      </div>
    </article>
    """


def competency_note(data: WorkbookData, skill: str) -> str:
    for row in data.competencies:
        if row["skill"] == skill:
            return str(row.get("sales_note") or row.get("product_note") or "")
    return ""


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
    <div class="shell">
      <section class="grid">
        <div class="span-4 card">{manager_picker(data, manager)}</div>
        <div class="span-8 card">
          <h2>Team Members</h2>
          <table><tr><th>Code</th><th>Name</th><th>Role</th><th>Level</th><th>Your form</th><th></th></tr>{''.join(rows)}</table>
        </div>
      </section>
    </div>
    """


def manager_employee(data: WorkbookData, state: RuntimeState, query: dict[str, str]) -> str:
    emp_code = query.get("emp") or next(iter(data.employees))
    employee = data.employees.get(emp_code) or next(iter(data.employees.values()))
    emp_code = employee["code"]
    locked = emp_code in state.manager_forms
    body = [f"<div class='shell'>{profile_card(employee)}<section class='grid'>"]
    body.append("<div class='span-5 card'><h2>Manager functional rating</h2>")
    if locked:
        body.append("<div class='notice locked'>Your response is locked.</div>")
        body.append(ratings_table(state.manager_forms[emp_code], "Your submitted rating"))
    else:
        body.append("<p>Rate each skill. No defaults. Submit once — locks immediately.</p>")
        body.append(rating_form("/manager/submit", emp_code, data.functional_skills, "Submit manager rating"))
    body.append("</div>")
    body.append("<div class='span-7 card'><h2>Supporting context</h2>")
    body.append("<p>TNA and annual feedback for this employee.</p>")
    body.append(context_view(data, emp_code, include_amber=False))
    body.append("</div></section></div>")
    return "".join(body)


def admin_dashboard(data: WorkbookData, state: RuntimeState, query: dict[str, str] | None = None) -> str:
    query = query or {}
    stats = analytics(data, state)
    emp_code = query.get("emp") or ""
    detail = admin_employee_detail(data, state, emp_code) if emp_code else "<p class='muted'>Pick an employee to inspect forms and pipeline output.</p>"
    return f"""
    <div class="shell">
      <section class="grid">
        <div class="span-12"><h1>Admin Dashboard</h1><p>Uploaded artifacts, pipeline logs, confidence explanations, and gap analytics.</p></div>
        <div class="span-4 card"><h2>Pipeline</h2>
          {metric("Employees", stats["employee_count"])}
          {metric("Employee forms", stats["employee_forms"])}
          {metric("Manager forms", stats["manager_forms"])}
          {metric("Screenshots uploaded", stats["uploaded_screenshots"])}
          {metric("Completed profiles", stats["completed_profiles"])}
        </div>
        <div class="span-8 card"><h2>Uploaded artifacts</h2>{uploaded_artifacts_table(state)}</div>
        <div class="span-4 card"><h2>Gap by role</h2>{dict_table(stats["gap_by_role"], "Role", "Gap count")}</div>
        <div class="span-4 card"><h2>Gap by level</h2>{dict_table(stats["gap_by_level"], "Level", "Gap count")}</div>
        <div class="span-4 card"><h2>Gap by manager</h2>{dict_table(stats["gap_by_manager"], "Manager", "Gap count")}</div>
        <div class="span-6 card"><h2>Missing inputs</h2>
          <p>Employee forms pending: {len(stats["missing_employee_form"])}</p>
          <p>Manager forms pending: {len(stats["missing_manager_form"])}</p>
          <p>Behavioural incomplete: {len(stats["missing_behavioral"])}</p>
          <p>Outdated annual feedback: 0 (all treated recent)</p>
        </div>
        <div class="span-6 card"><h2>Low confidence profiles</h2><p>{escape(', '.join(stats["low_confidence"]) or 'None')}</p></div>
        <div class="span-12 card">
          <h2>Per-employee inspection</h2>
          {admin_employee_picker(data, emp_code)}
          {detail}
        </div>
        <div class="span-12 card"><h2>LLM API calls</h2>
          <p class="muted">Also see file log: <code>logs/skillsync.log</code></p>
          <div class="scroll">{api_calls_table(state)}</div>
        </div>
        <div class="span-12 card"><h2>Agent pipeline logs</h2><div class="scroll">{logs_table(state)}</div></div>
        <div class="span-12 card"><h2>Agent decision memory (few-shot log)</h2><div class="scroll">{decisions_table(state)}</div></div>
      </section>
    </div>
    """


def admin_employee_picker(data: WorkbookData, selected: str) -> str:
    options = ["<option value=''>Select employee</option>"]
    options.extend(
        f"<option value='{escape(emp['code'])}' {'selected' if emp['code']==selected else ''}>{escape(emp['code'])} - {escape(emp['name'])}</option>"
        for emp in data.employee_options()
    )
    return f"""
    <form method="get" action="/admin" class="picker-inline">
      <div><label>Employee</label><select name="emp" onchange="this.form.submit()">{''.join(options)}</select></div>
    </form>
    """


def admin_employee_detail(data: WorkbookData, state: RuntimeState, emp_code: str) -> str:
    employee = data.employees.get(emp_code)
    if not employee:
        return "<p>Unknown employee.</p>"
    blocks = [profile_card(employee)]
    blocks.append("<h3>Demographics</h3>")
    blocks.append(
        "<table>"
        f"<tr><td>Code</td><td>{escape(employee.get('code'))}</td></tr>"
        f"<tr><td>Designation</td><td>{escape(employee.get('designation'))}</td></tr>"
        f"<tr><td>Level</td><td>{escape(employee.get('level'))}</td></tr>"
        f"<tr><td>Location</td><td>{escape(employee.get('location'))}</td></tr>"
        f"<tr><td>Manager</td><td>{escape(employee.get('manager'))}</td></tr>"
        f"<tr><td>Total exp (years)</td><td>{escape(employee.get('total_exp_years'))}</td></tr>"
        f"<tr><td>Cohort</td><td>{escape(employee.get('cohort'))}</td></tr>"
        "</table>"
    )
    if emp_code in state.employee_forms:
        blocks.append(ratings_table(state.employee_forms[emp_code], "Employee functional form"))
    else:
        blocks.append("<p>Employee form: not submitted</p>")
    if emp_code in state.manager_forms:
        blocks.append(ratings_table(state.manager_forms[emp_code], "Manager functional form"))
    else:
        blocks.append("<p>Manager form: not submitted</p>")
    uploads = state.behavioral_uploads.get(emp_code, {})
    scores = state.behavioral_scores.get(emp_code, {})
    rationales = state.behavioral_rationales.get(emp_code, {})
    if uploads:
        rows = "".join(
            f"<tr><td>{escape(skill)}</td><td>{escape(name)}</td>"
            f"<td>{escape(scores.get(skill, ''))}</td>"
            f"<td>{escape((rationales.get(skill) or {}).get('rationale', ''))}</td></tr>"
            for skill, name in uploads.items()
        )
        blocks.append(
            "<h3>Behavioural screenshots</h3>"
            f"<table><tr><th>Skill</th><th>File</th><th>Agent A score</th><th>Rationale</th></tr>{rows}</table>"
        )
    variable = data.variable.get(emp_code, {})
    blocks.append(
        "<h3>Variable pay</h3>"
        f"<p>Avg: {escape(variable.get('avg'))} · Cohort: {escape(variable.get('cohort'))} · Level: {escape(variable.get('level'))}</p>"
    )
    blocks.append("<h3>TNA / Appraisal / Amber</h3>")
    blocks.append(context_view(data, emp_code, include_amber=True))
    profile = state.profiles.get(emp_code)
    if profile:
        conf = profile.get("confidence") or {}
        blocks.append(ratings_table(profile.get("profile_v0") or {}, "Profile v0"))
        blocks.append(ratings_table(profile.get("scores") or {}, "Profile v1 (final)"))
        if profile.get("ideal"):
            blocks.append(ratings_table(profile["ideal"], "Ideal matrix for role/level"))
        blocks.append(
            f"<p><strong>Confidence:</strong> {escape(conf.get('band'))} ({escape(conf.get('score'))}%) — {escape(conf.get('explanation'))}</p>"
            f"<p><strong>Peer note:</strong> {escape(conf.get('peer_note') or 'n/a')}</p>"
            f"<h3>Adjustments</h3><p>{escape('; '.join(profile.get('adjustments') or []) or 'None')}</p>"
        )
        gaps = profile.get("gaps") or []
        if gaps:
            gap_rows = "".join(
                f"<tr><td>{escape(g['skill'])}</td><td>{escape(g.get('current'))}</td><td>{escape(g.get('ideal'))}</td></tr>"
                for g in gaps
            )
            blocks.append(
                f"<h3>Gaps</h3><table><tr><th>Skill</th><th>Current</th><th>Ideal</th></tr>{gap_rows}</table>"
            )
        coaching = profile.get("coaching") or {}
        blocks.append(
            "<h3>Employee coaching output (Agent E)</h3>"
            f"<p>Good: {escape(', '.join(coaching.get('good_skills') or []))}</p>"
            f"<p>Work on: {escape(', '.join(coaching.get('work_on_skills') or []))}</p>"
        )
        emp_logs = [row for row in state.agent_logs if row.get("employee") == emp_code]
        if emp_logs:
            log_rows = "".join(
                f"<tr><td>{escape(row['time'])}</td><td>{escape(row['agent'])}</td><td>{escape(row['message'])}</td></tr>"
                for row in emp_logs[-40:]
            )
            blocks.append(
                f"<h3>Agent logs for this employee</h3><table><tr><th>Time</th><th>Agent</th><th>Message</th></tr>{log_rows}</table>"
            )
    return "".join(blocks)


def uploaded_artifacts_table(state: RuntimeState) -> str:
    rows = []
    rows.append(
        f"<tr><td>Employee skill forms</td><td>{len(state.employee_forms)} submitted</td></tr>"
    )
    rows.append(
        f"<tr><td>Manager skill forms</td><td>{len(state.manager_forms)} submitted</td></tr>"
    )
    upload_count = sum(len(v) for v in state.behavioral_uploads.values())
    sample = []
    if UPLOAD_DIR.exists():
        sample = sorted(p.name for p in UPLOAD_DIR.iterdir() if p.is_file())[:12]
    files = ", ".join(sample) if sample else "none yet"
    rows.append(f"<tr><td>Udemy / role-play screenshots</td><td>{upload_count} files · {escape(files)}</td></tr>")
    return f"<table><tr><th>Artifact</th><th>Status</th></tr>{''.join(rows)}</table>"


def employee_picker(data: WorkbookData, path: str, selected: str, section: str = "overview") -> str:
    options = "".join(
        f"<option value='{escape(emp['code'])}' {'selected' if emp['code']==selected else ''}>{escape(emp['code'])} - {escape(emp['name'])}</option>"
        for emp in data.employee_options()
    )
    return f"""
    <form class="card picker-inline" method="get" action="{path}">
      <input type="hidden" name="section" value="{escape(section)}">
      <div>
        <label>Employee</label>
        <select name="emp" onchange="this.form.submit()">{options}</select>
      </div>
    </form>
    """


def manager_picker(data: WorkbookData, selected: str) -> str:
    options = "".join(
        f"<option value='{escape(name)}' {'selected' if name==selected else ''}>{escape(name)}</option>"
        for name in data.managers()
    )
    return f"<h2>Manager</h2><form method='get' action='/manager'><select name='manager' onchange='this.form.submit()'>{options}</select></form>"


def profile_card(employee: dict[str, object]) -> str:
    return f"""
    <section class="card profile-bar">
      <div>
        <h1>{escape(employee['name'])}</h1>
        <p class="meta">{escape(employee['designation'])} · {escape(employee['level'])} · {escape(employee['location'])} · Manager: {escape(employee['manager'])}</p>
      </div>
    </section>
    """


def rating_form(action: str, emp_code: str, skills: list[str], label: str) -> str:
    fields = [f"<input type='hidden' name='emp_code' value='{escape(emp_code)}'>"]
    for skill in skills:
        bubbles = []
        for value in PROFICIENCY_ORDER:
            bubbles.append(
                f"<label class='bubble'><input type='radio' name='{slug(skill)}' value='{escape(value)}' required>"
                f"<span>{escape(value)}</span></label>"
            )
        fields.append(
            f"<div class='skill-block'><div class='skill-name'>{escape(skill)}</div>"
            f"<div class='bubble-row'>{''.join(bubbles)}</div></div>"
        )
    fields.append(f"<div class='actions'><button type='submit'>{escape(label)}</button></div>")
    return f"<form method='post' action='{action}'>{''.join(fields)}</form>"


def ratings_table(values: dict[str, str], heading: str) -> str:
    rows = "".join(f"<tr><td>{escape(skill)}</td><td>{escape(score)}</td></tr>" for skill, score in values.items())
    return f"<h3>{escape(heading)}</h3><table><tr><th>Skill</th><th>Rating</th></tr>{rows}</table>"


def context_view(data: WorkbookData, emp_code: str, include_amber: bool = True) -> str:
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
    parts = [
        f"<h3>TNA</h3><table><tr><th>Employee Input</th><th>Manager Input</th></tr>{tna_rows or '<tr><td colspan=\"2\">No TNA rows</td></tr>'}</table>",
        f"<h3>Annual Feedback</h3><p>{escape(' '.join(str(b) for b in appraisal_bits if b))[:1200] or 'No appraisal row'}</p>",
    ]
    if include_amber:
        amber_rows = "".join(
            f"<tr><td>{escape(row.get('Question'))}</td><td>{escape(row.get('Answer'))}</td></tr>" for row in amber[:4]
        )
        parts.append(
            f"<h3>Amber</h3><table><tr><th>Question</th><th>Answer</th></tr>{amber_rows or '<tr><td colspan=\"2\">No Amber rows</td></tr>'}</table>"
        )
    return "".join(parts)


def metric(label: str, value: object) -> str:
    return f"<div class='metric'><span>{escape(label)}</span><strong>{escape(value)}</strong></div>"


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


def api_calls_table(state: RuntimeState) -> str:
    if not state.api_calls:
        return "<p>No LLM API calls recorded yet. Calls appear when agents run (after forms + 4 uploads).</p>"
    ok = sum(1 for row in state.api_calls if row.get("status") == "ok")
    err = sum(1 for row in state.api_calls if row.get("status") == "error")
    skip = sum(1 for row in state.api_calls if row.get("status") == "skipped")
    summary = f"<p><span class='pill'>ok {ok}</span> <span class='pill'>error {err}</span> <span class='pill'>skipped {skip}</span></p>"
    rows = "".join(
        f"<tr><td>{escape(row.get('time'))}</td><td>{escape(row.get('employee'))}</td>"
        f"<td>{escape(row.get('agent'))}</td><td>{escape(row.get('provider') or '-')}</td>"
        f"<td>{escape(row.get('status'))}</td><td>{escape(row.get('detail'))}</td></tr>"
        for row in state.api_calls[-100:]
    )
    return (
        summary
        + "<table><tr><th>Time</th><th>Employee</th><th>Agent</th><th>Provider</th>"
        + f"<th>Status</th><th>Detail</th></tr>{rows}</table>"
    )


def decisions_table(state: RuntimeState) -> str:
    if not state.agent_decisions:
        path = Path("agent_decisions.jsonl")
        note = f" (disk log: {path})" if path.exists() else ""
        return f"<p>No decisions logged yet{note}.</p>"
    rows = "".join(
        f"<tr><td>{escape(row.get('time'))}</td><td>{escape(row.get('employee'))}</td>"
        f"<td>{escape(row.get('agent'))}</td><td>{escape(str(row.get('output'))[:240])}</td></tr>"
        for row in state.agent_decisions[-80:]
    )
    return f"<table><tr><th>Time</th><th>Employee</th><th>Agent</th><th>Output</th></tr>{rows}</table>"
