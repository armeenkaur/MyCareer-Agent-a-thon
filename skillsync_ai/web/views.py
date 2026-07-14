from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from ..agents.course_recommendation import build_recommendations, duration_hours, gap_levels
from ..agents.external_learning import populate_external_resources
from ..agents.feedback import TARGETS
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


def feedback_page(data: WorkbookData, state: RuntimeState, query: dict[str, str]) -> str:
    role = query.get("role") or "employee"
    actor_id = query.get("actor") or query.get("emp") or query.get("manager") or ""
    if role == "employee" and not actor_id:
        actor_id = next(iter(data.employees))
    target_options = "".join(f"<option value='{escape(label)}'>{escape(label)}</option>" for label in TARGETS)
    status = query.get("status")
    notice = ""
    if status == "accepted":
        notice = "<div class='notice'>Feedback accepted and added to agent guidance.</div>"
    elif status == "rejected":
        notice = "<div class='notice warn'>Feedback stored but not applied because it was not relevant or safe.</div>"
    elif query.get("error"):
        notice = f"<div class='notice warn'>{escape(query['error'])}</div>"
    visible = state.feedback if role == "admin" else [row for row in state.feedback if row.get("actor_id") == actor_id]
    rows = "".join(
        f"<tr><td>{escape(row.get('time'))}</td><td>{escape(row.get('target_label'))}</td>"
        f"<td>{escape(row.get('message'))}</td><td><span class='pill'>{'Applied' if row.get('relevant') else 'Not applied'}</span></td>"
        f"<td>{escape(row.get('reason'))}</td></tr>" for row in visible[-30:]
    )
    return f"""
    <div class="shell"><section class="grid">
      <div class="span-12"><h1>Feedback</h1><p>Share specific feedback about an agent output or decision.</p></div>
      <div class="span-5 card">{notice}<form method="post" action="/feedback/submit">
        <input type="hidden" name="actor_role" value="{escape(role)}"><input type="hidden" name="actor_id" value="{escape(actor_id)}">
        <label>Agent or task</label><select name="target_agent" required>{target_options}</select>
        <label>Feedback</label><textarea name="message" rows="8" required placeholder="Describe output, expected improvement, and why."></textarea>
        <div class="actions"><button type="submit">Submit feedback</button></div></form></div>
      <div class="span-7 card"><h2>{'All feedback' if role == 'admin' else 'Your feedback'}</h2>
        <div class="scroll"><table><tr><th>Time</th><th>Target</th><th>Feedback</th><th>Status</th><th>Reason</th></tr>{rows or '<tr><td colspan="5">No feedback yet.</td></tr>'}</table></div></div>
    </section></div>"""


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
        "behavioral": _employee_behavioral(data, state, emp_code, query),
        "results": _employee_results(profile, emp_code) if ready else _employee_overview(self_locked, manager_locked, ready, profile, data, state, emp_code),
    }.get(section, _employee_overview(self_locked, manager_locked, ready, profile, data, state, emp_code))

    return f"""
    <div class="layout">
      <div class="content-pane">
        {employee_picker(data, "/employee", emp_code, section)}
        {profile_card(employee)}
        {pane}
      </div>
    </div>
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
    beh_submitted = emp_code in state.behavioral_submitted
    notices = []
    if not self_locked:
        notices.append("<div class='notice'>Start with <strong>Functional skills</strong>. Submit once — then it locks.</div>")
    elif not beh_submitted:
        notices.append(f"<div class='notice'>Continue to <strong>Behavioural assessment</strong> ({beh_done}/{beh_total} uploaded).</div><a class='button' href='/employee?emp={escape(emp_code)}&section=behavioral'>Continue to behavioural assessment</a>")
    elif not manager_locked:
        notices.append("<div class='notice warn'>Waiting for manager response.</div>")
    elif ready:
        notices.append("<div class='notice'>Pipeline complete. Open <strong>My profile & gaps</strong>.</div>")
    else:
        notices.append("<div class='notice warn'>Inputs ready — profile processing pending. Refresh shortly.</div>")

    return f"""
    <section class="card section-head">
      <h2>Overview</h2>
      <p>Fill functional skills once. Complete behavioural uploads.</p>
      {''.join(notices)}
      <table>
        <tr><th>Step</th><th>Status</th></tr>
        <tr><td>Functional self-rating</td><td><span class="{'status-done' if self_locked else 'status-todo'}">{'Locked' if self_locked else 'To do'}</span></td></tr>
        <tr><td>Manager rating</td><td><span class="{'status-done' if manager_locked else 'status-todo'}">{'Done' if manager_locked else 'Waiting'}</span></td></tr>
        <tr><td>Behavioural response</td><td><span class="{'status-done' if beh_submitted else 'status-todo'}">{'Submitted & locked' if beh_submitted else f'{beh_done}/{beh_total} uploaded'}</span></td></tr>
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
        body.append(ratings_table(state.employee_forms[emp_code], "Your submitted rating"))
        body.append(f"<div class='actions'><a class='button' href='/employee?emp={escape(emp_code)}&section=behavioral'>Continue to behavioural assessment</a></div>")
    else:
        body.append("<p>Pick one level per skill. No defaults. Submit once — locks immediately.</p>")
        body.append(rating_form("/employee/submit", emp_code, data.functional_skills, "Submit self-rating"))
    body.append("</section>")
    return "".join(body)


def _employee_behavioral(data: WorkbookData, state: RuntimeState, emp_code: str, query: dict[str, str]) -> str:
    locked = emp_code in state.behavioral_submitted
    cards = [behavioral_card(data, state, emp_code, skill, locked) for skill in data.behavioral_skills]
    uploads = state.behavioral_uploads.get(emp_code, {})
    all_uploaded = all(skill in uploads for skill in data.behavioral_skills)
    error = f"<div class='notice warn'>{escape(query.get('error'))}</div>" if query.get("error") else ""
    if locked:
        action = "<div class='notice locked'>Behavioural response submitted and locked.</div>"
    elif all_uploaded:
        action = f"<form method='post' action='/employee/behavioral-submit' class='card submit-panel'><input type='hidden' name='emp_code' value='{escape(emp_code)}'><div><h2>Ready to submit?</h2><p>Submitting runs one assessment call and locks all behavioural responses.</p></div><button type='submit'>Submit behavioural assessment</button></form>"
    else:
        action = "<div class='notice'>Upload all four screenshots. Submit button appears after final upload.</div>"
    return f"""
    <section class="section-head">
      <h2>Behavioural assessment</h2>
      <p>Complete each role-play, then upload the screenshot. Status shows upload progress.</p>
    </section>
    {error}<div class="assess-stack">{''.join(cards)}</div>{action}
    """


def _employee_results(profile: dict, emp_code: str) -> str:
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
    body.append(f"<div class='actions'><a class='button' href='/employee/shop?emp={escape(emp_code)}'>Shop your courses</a></div>")
    body.append("</section>")
    return "".join(body)


def course_shop(data: WorkbookData, state: RuntimeState, query: dict[str, str]) -> str:
    emp_code = query.get("emp") or next(iter(data.employees))
    employee = data.employees.get(emp_code) or next(iter(data.employees.values()))
    emp_code = employee["code"]
    profile = state.profiles.get(emp_code) or compute_or_get_profile(data, state, emp_code)
    if not profile:
        return f"<div class='shell'>{profile_card(employee)}<div class='notice warn'>Your skill profile is not ready yet.</div></div>"
    recommendation = build_recommendations(data, state, emp_code, profile)
    career_options = recommendation.get("career_options", [])
    choice_id = state.career_choices.get(emp_code, "")
    chosen_path = next((row for row in career_options if str(row.get("id")) == choice_id), None)
    if recommendation.get("ideal_reached") and career_options and (not chosen_path or query.get("choose") == "1"):
        return career_choice_gate(data, employee, recommendation, query)
    populate_external_resources(recommendation, employee, state, emp_code)
    active_skills = set(chosen_path.get("skills", [])) if chosen_path else set(recommendation.get("skills", {}))
    selected = set(state.learning_selections.get(emp_code, []))
    external_selected = set(state.external_selections.get(emp_code, []))
    missing_skills = set(filter(None, query.get("missing", "").split("|")))
    sections = []
    for skill, courses in recommendation.get("skills", {}).items():
        if skill not in active_skills:
            continue
        cards = []
        for course in courses:
            course_id = str(course.get("id"))
            checked = "checked" if course_id in selected else ""
            cards.append(
                f"<label class='product-card'><input type='checkbox' name='course' value='{escape(course_id)}' {checked}>"
                f"<span class='course-choice'>Select</span><h3>{escape(course.get('title'))}</h3>"
                f"<p>{escape(course.get('description'))}</p></label>"
            )
        external = recommendation.get("external", {}).get(skill, [])
        external_cards = "".join(
            f"<label class='resource-card selectable'><input type='checkbox' name='external' value='{escape(row['id'])}' {'checked' if row['id'] in external_selected else ''}>"
            f"<span class='resource-type'>{escape(row['type'])}</span><span class='course-choice'>Select</span>"
            f"<h3>{escape(row['title'])}</h3><p>{escape(row['description'])}</p>"
            f"<a target='_blank' rel='noopener' href='/employee/resource?emp={escape(emp_code)}&id={escape(row['id'])}'>Open resource</a></label>"
            for row in external
        )
        sections.append(
            f"<section class='shop-section {'skill-missing' if skill in missing_skills else ''}'><div class='shop-heading'><div><span class='badge'>Skill focus</span><h2>{escape(skill)}</h2></div>"
            f"<span class='muted'>Choose at least one LinkedIn course</span></div><div class='product-grid'>{''.join(cards)}</div>"
            f"<h3 class='resource-title'>Other learning sources</h3><div class='resource-grid'>{external_cards}</div></section>"
        )
    ideal_note = ""
    if recommendation.get("ideal_reached") and chosen_path:
        ideal_note = (
            f"<div class='notice'><strong>Career goal: {escape(chosen_path.get('label'))}</strong><br>"
            f"Your mentor is {escape(recommendation.get('mentor'))}. "
            f"<a href='/employee/shop?emp={escape(emp_code)}&choose=1'>Change career goal</a></div>"
        )
    error = f"<div class='notice warn'>{escape(query.get('error'))}</div>" if query.get("error") else ""
    return f"""
    <div class="layout">
      <main class="content-pane shop-page">
        {employee_picker(data, "/employee/shop", emp_code, "shop")}
        <section class="shop-hero"><div><span class="eyebrow">Personal learning catalogue</span><h1>Shop your courses</h1><p>Build a focused learning basket around your skill priorities.</p></div><div class="cart-mark">{len(selected) + len(external_selected)} selected</div></section>
        {ideal_note}{error}
        <form method="post" action="/employee/checkout"><input type="hidden" name="emp_code" value="{escape(emp_code)}">{''.join(sections)}
          <div class="checkout-bar"><div><strong>Your learning basket</strong><span>At least one LinkedIn course per skill</span></div><button type="submit">Start learning journey</button></div>
        </form>
      </main>
    </div>"""


def career_choice_gate(data: WorkbookData, employee: dict, recommendation: dict, query: dict[str, str]) -> str:
    emp_code = str(employee["code"])
    current = query.get("career_choice", "")
    cards = "".join(
        f"<label class='career-choice-card'><input type='radio' name='career_choice' value='{escape(option.get('id'))}' "
        f"{'checked' if str(option.get('id')) == current else ''} required>"
        f"<span class='career-choice-mark'>Select</span><strong>{escape(option.get('label'))}</strong>"
        f"<p>{escape(', '.join(option.get('skills', [])))}</p></label>"
        for option in recommendation.get("career_options", [])
    )
    error = f"<div class='notice warn'>{escape(query.get('error'))}</div>" if query.get("error") else ""
    return f"""
    <div class="layout">
      <main class="content-pane shop-page">
        {employee_picker(data, "/employee/shop", emp_code, "shop")}
        <section class="shop-hero"><div><span class="eyebrow">Career exploration</span><h1>Choose your next role</h1><p>Your choice personalizes courses and learning resources.</p></div></section>
        {error}
        <form method="post" action="/employee/career-choice" class="career-choice-form">
          <input type="hidden" name="emp_code" value="{escape(emp_code)}">
          <section class="card section-head"><h2>Which role do you want to become?</h2><p>Choose one role to build your learning catalogue.</p><div class="career-choice-grid">{cards}</div></section>
          <div class="actions"><button type="submit">Continue to Shop your courses</button></div>
        </form>
      </main>
    </div>"""


def learning_journey(data: WorkbookData, state: RuntimeState, query: dict[str, str]) -> str:
    emp_code = query.get("emp") or next(iter(data.employees))
    employee = data.employees.get(emp_code) or next(iter(data.employees.values()))
    emp_code = employee["code"]
    selected = set(state.learning_selections.get(emp_code, []))
    recommendation = state.recommendations.get(emp_code, {})
    if not selected:
        return f"<div class='layout'><main class='content-pane'>{profile_card(employee)}<div class='notice warn'>Choose your courses before starting the learning journey.</div><a class='button' href='/employee/shop?emp={escape(emp_code)}'>Shop your courses</a></main></div>"
    completed = state.learning_completed.get(emp_code, set())
    external_selected = set(state.external_selections.get(emp_code, []))
    external_completed = state.external_completed.get(emp_code, set())
    items = []
    total_hours = 0.0
    completed_hours = 0.0
    for skill, courses in recommendation.get("skills", {}).items():
        chosen = [course for course in courses if str(course.get("id")) in selected]
        rows = []
        for course in chosen:
            course_id = str(course.get("id"))
            hours = duration_hours(course.get("duration", ""))
            total_hours += hours
            done = course_id in completed
            if done:
                completed_hours += hours
            rows.append(
                f"<article class='journey-item {'complete' if done else ''}'><form method='post' action='/employee/complete'>"
                f"<input type='hidden' name='emp_code' value='{escape(emp_code)}'><input type='hidden' name='course_id' value='{escape(course_id)}'>"
                f"<button class='check-button' type='submit' aria-label='Toggle completion'>{'✓' if done else ''}</button></form>"
                f"<div><h3>{escape(course.get('title'))}</h3><p>{escape(course.get('description'))}</p>"
                f"<a target='_blank' rel='noopener' href='{escape(course.get('url'))}'>Open LinkedIn Learning</a></div></article>"
            )
        selected_resource_rows = []
        other_resource_rows = []
        for resource in recommendation.get("external", {}).get(skill, []):
            resource_id = str(resource.get("id"))
            open_link = f"/employee/resource?emp={escape(emp_code)}&id={escape(resource_id)}"
            if resource_id in external_selected:
                done = resource_id in external_completed
                selected_resource_rows.append(
                    f"<article class='journey-item {'complete' if done else ''}'><form method='post' action='/employee/external-complete'>"
                    f"<input type='hidden' name='emp_code' value='{escape(emp_code)}'><input type='hidden' name='resource_id' value='{escape(resource_id)}'>"
                    f"<button class='check-button' type='submit' aria-label='Toggle resource completion'>{'✓' if done else ''}</button></form>"
                    f"<div><span class='badge'>{escape(resource.get('type'))}</span><h3>{escape(resource.get('title'))}</h3>"
                    f"<p>{escape(resource.get('description'))}</p><a target='_blank' rel='noopener' href='{open_link}'>Open resource</a></div></article>"
                )
            else:
                other_resource_rows.append(
                    f"<a class='recommended-row' target='_blank' rel='noopener' href='{open_link}'><span>{escape(resource.get('type'))}</span>"
                    f"<div><h3>{escape(resource.get('title'))}</h3><p>{escape(resource.get('description'))}</p></div></a>"
                )
        selected_block = f"<h3 class='journey-subhead'>Selected supporting material</h3>{''.join(selected_resource_rows)}" if selected_resource_rows else ""
        other_block = f"<div class='recommended-material'><h3 class='journey-subhead'>Other recommended material</h3><p>Optional resources.</p>{''.join(other_resource_rows)}</div>" if other_resource_rows else ""
        items.append(f"<section class='journey-skill'><h2>{escape(skill)}</h2>{''.join(rows)}{selected_block}{other_block}</section>")
    completed_hours = employee_learning_hours(state, emp_code)
    profile = state.profiles.get(emp_code, {})
    cohort = gap_levels(profile)
    position, cohort_size = leaderboard_position(data, state, emp_code)
    mentor = recommendation.get("mentor")
    mentor_card = ""
    if mentor:
        mentor_card = f"<section class='card mentor-card'><span class='badge'>Your mentor</span><h2>{escape(mentor)}</h2><p>Your manager will support your next-role exploration and learning application.</p></section>"
    return f"""
    <div class="layout"><main class="content-pane">
      {employee_picker(data, "/employee/journey", emp_code, "journey")}
      <section class="journey-hero"><div><span class="eyebrow">Active plan</span><h1>Learning journey</h1><p>Your selected learning, all in one place.</p></div>
        <div class="journey-metrics"><div><strong>{completed_hours:.2f}</strong><span>hours complete</span></div><div><strong>{cohort}</strong><span>gap-level cohort</span></div><div><strong>#{position}</strong><span>of {cohort_size}</span></div></div></section>
      {mentor_card}{''.join(items)}
    </main></div>"""


def employee_learning_hours(state: RuntimeState, emp_code: str) -> float:
    if emp_code in state.linkedin_hours:
        return float(state.linkedin_hours[emp_code])
    selected = set(state.learning_selections.get(emp_code, []))
    completed = state.learning_completed.get(emp_code, set())
    recommendation = state.recommendations.get(emp_code, {})
    return round(sum(
        duration_hours(course.get("duration", ""))
        for rows in recommendation.get("skills", {}).values()
        for course in rows
        if str(course.get("id")) in selected and str(course.get("id")) in completed
    ), 2)


def leaderboard_rows(data: WorkbookData, state: RuntimeState, cohort: int | None = None) -> list[dict[str, object]]:
    rows = []
    for code, profile in state.profiles.items():
        row_cohort = gap_levels(profile)
        if cohort is not None and row_cohort != cohort:
            continue
        employee = data.employees.get(code, {})
        rows.append({"code": code, "name": employee.get("name", code), "manager": employee.get("manager", ""), "cohort": row_cohort, "hours": employee_learning_hours(state, code)})
    rows.sort(key=lambda row: (int(row["cohort"]), -float(row["hours"]), str(row["name"])))
    rank = 0
    previous = None
    previous_cohort = None
    for index, row in enumerate(rows, 1):
        if row["cohort"] != previous_cohort:
            rank = 1
            previous = None
            previous_cohort = row["cohort"]
        elif row["hours"] != previous:
            rank += 1
        if row["hours"] != previous:
            previous = row["hours"]
        row["rank"] = rank
    return rows


def leaderboard_position(data: WorkbookData, state: RuntimeState, emp_code: str) -> tuple[int, int]:
    profile = state.profiles.get(emp_code, {})
    rows = leaderboard_rows(data, state, gap_levels(profile))
    row = next((item for item in rows if item["code"] == emp_code), None)
    return (int(row["rank"]) if row else 1, len(rows) or 1)


def behavioral_card(data: WorkbookData, state: RuntimeState, emp_code: str, skill: str, locked: bool = False) -> str:
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
    upload_form = "" if locked else f"""
        <form method="post" action="/employee/upload" enctype="multipart/form-data" class="upload-row">
          <input type="hidden" name="emp_code" value="{escape(emp_code)}">
          <input type="hidden" name="skill" value="{escape(skill)}">
          <div><label>Upload screenshot</label><input type="file" name="screenshot" accept="image/*" required></div>
          <button type="submit">Upload file</button>
        </form>"""
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
        {upload_form}
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
        position, cohort_size = leaderboard_position(data, state, emp["code"]) if emp["code"] in state.profiles else (0, 0)
        rank = f"#{position} of {cohort_size}" if position else "Pending"
        rows.append(
            f"<tr><td>{escape(emp['code'])}</td><td>{escape(emp['name'])}</td><td>{escape(emp['designation'])}</td>"
            f"<td>{escape(emp['level'])}</td><td>{employee_learning_hours(state, emp['code']):.2f}</td><td>{escape(rank)}</td><td><span class='pill'>{status}</span></td>"
            f"<td><a class='button ghost' href='/manager/employee?emp={escape(emp['code'])}'>Open</a></td></tr>"
        )
    team_codes = {emp["code"] for emp in data.team_for_manager(manager)}
    board_rows = [row for row in leaderboard_rows(data, state) if row["code"] in team_codes]
    board = "".join(f"<tr><td>{escape(row['cohort'])}</td><td>#{escape(row['rank'])}</td><td>{escape(row['name'])}</td><td>{float(row['hours']):.2f}</td></tr>" for row in board_rows)
    return f"""
    <div class="shell">
      <section class="grid">
        <div class="span-4 card">{manager_picker(data, manager)}<div class="actions"><a class="button ghost" href="/feedback?role=manager&manager={escape(manager)}">Give feedback</a></div></div>
        <div class="span-8 card">
          <h2>Team Members</h2>
          <table><tr><th>Code</th><th>Name</th><th>Role</th><th>Level</th><th>Learning hours</th><th>Leaderboard</th><th>Your form</th><th></th></tr>{''.join(rows)}</table>
        </div>
        <div class="span-12 card"><h2>Team leaderboard</h2><p>Employees are compared only within equal total gap-level cohorts. Rank uses LinkedIn Learning hours only.</p>
          <table><tr><th>Cohort</th><th>Rank</th><th>Employee</th><th>Hours</th></tr>{board or '<tr><td colspan="4">No learning activity yet.</td></tr>'}</table></div>
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
        <div class="span-12 actions"><a class="button ghost" href="/feedback?role=admin&actor=admin">Feedback center</a></div>
        <div class="span-4 card"><h2>Pipeline</h2>
          {metric("Employees", stats["employee_count"])}
          {metric("Employee forms", stats["employee_forms"])}
          {metric("Manager forms", stats["manager_forms"])}
          {metric("Screenshots uploaded", stats["uploaded_screenshots"])}
          {metric("Completed profiles", stats["completed_profiles"])}
        </div>
        <div class="span-8 card"><h2>Uploaded artifacts</h2>{uploaded_artifacts_table(state)}</div>
        <div class="span-12 card"><h2>LinkedIn Learning sync</h2>{linkedin_sync_panel(state)}</div>
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
        <div class="span-12 card"><h2>Learning leaderboard</h2>{admin_leaderboard(data, state)}</div>
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
        recommendation = state.recommendations.get(emp_code, {})
        if recommendation:
            blocks.append("<h3>Course recommendation audit</h3>")
            blocks.append(course_audit_table(recommendation))
            blocks.append(
                f"<p><strong>Ideal reached:</strong> {escape(recommendation.get('ideal_reached'))} · "
                f"<strong>Exploration path:</strong> {escape(recommendation.get('exploration_path') or 'n/a')} · "
                f"<strong>Mentor:</strong> {escape(recommendation.get('mentor') or 'not assigned')}</p>"
            )
            blocks.append(f"<p><strong>Completed LinkedIn hours:</strong> {employee_learning_hours(state, emp_code):.2f}</p>")
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
    interview = data.interview.get(emp_code, {})
    amber = data.amber.get(emp_code, [])
    tna_rows = "".join(
        f"<tr><td>{escape(row.get('Employee Input'))}</td><td>{escape(row.get('Reporting Manager Input'))}</td></tr>"
        for row in tna[:5]
    )
    if appraisal:
        feedback_label = "Annual Feedback"
        appraisal_bits = [
            appraisal.get("What Are The Top 3 Skills & Capabilities Exhibited By Your Team Member In The Current Role?", ""),
            appraisal.get("What Are 2-3 Development Areas Or Skills That Your Team Member Needs To Develop, To Grow Further?", ""),
        ]
    else:
        feedback_label = "Interview Feedback (appraisal unavailable)"
        appraisal_bits = [value for key, value in interview.items() if key.startswith("Round") and value]
    parts = [
        f"<h3>TNA</h3><table><tr><th>Employee Input</th><th>Manager Input</th></tr>{tna_rows or '<tr><td colspan=\"2\">No TNA rows</td></tr>'}</table>",
        f"<h3>{feedback_label}</h3><p>{escape(' '.join(str(b) for b in appraisal_bits if b))[:1200] or 'No appraisal or interview row'}</p>",
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


def linkedin_sync_panel(state: RuntimeState) -> str:
    sync = state.linkedin_sync or {}
    status = sync.get("status") or "Not synced"
    message = sync.get("message") or "Use Reporting API to import latest 14-day LinkedIn Learning hours and completions."
    return (
        f"<p><span class='pill'>{escape(status)}</span> {escape(message)}</p>"
        f"<p class='muted'>Reporting window: latest 14 days · Last sync: {escape(sync.get('time') or 'never')} · Matched learners: {escape(sync.get('matched') or 0)}</p>"
        "<form method='post' action='/admin/linkedin/sync'><button type='submit'>Sync LinkedIn Learning</button></form>"
    )


def course_audit_table(recommendation: dict) -> str:
    rows = "".join(
        f"<tr><td>{escape(skill)}</td><td>{escape(course.get('id'))}</td><td>{escape(course.get('title'))}</td>"
        f"<td>{escape(course.get('level'))}</td><td>{escape(course.get('release_date'))}</td>"
        f"<td>{escape(course.get('relevance'))}</td><td>{escape(course.get('reason'))}</td>"
        f"<td>{escape(course.get('bd_application'))}</td><td>{escape(course.get('evidence'))}</td></tr>"
        for skill, courses in recommendation.get("skills", {}).items() for course in courses
    )
    return "<div class='scroll'><table><tr><th>Skill</th><th>ID</th><th>Course</th><th>Level</th><th>Released</th><th>Relevance</th><th>Reason</th><th>BD application</th><th>Evidence</th></tr>" + rows + "</table></div>"


def admin_leaderboard(data: WorkbookData, state: RuntimeState) -> str:
    rows = leaderboard_rows(data, state)
    body = "".join(
        f"<tr><td>{escape(row['cohort'])}</td><td>#{escape(row['rank'])}</td><td>{escape(row['code'])}</td><td>{escape(row['name'])}</td><td>{escape(row['manager'])}</td><td>{float(row['hours']):.2f}</td></tr>"
        for row in rows
    )
    return f"<table><tr><th>Gap cohort</th><th>Rank</th><th>Code</th><th>Employee</th><th>Manager</th><th>LinkedIn hours</th></tr>{body or '<tr><td colspan="6">No completed profiles yet.</td></tr>'}</table>"
