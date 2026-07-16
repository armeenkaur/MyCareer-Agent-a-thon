(() => {
  "use strict";

  const page = window.MYCAREER_PAGE || "login";
  const tokenKey = "mycareer_token";
  const userKey = "mycareer_user";
  const levels = ["Beginner", "Intermediate", "Proficient", "Advanced"];
  const session = {
    token: localStorage.getItem(tokenKey) || "",
    user: JSON.parse(localStorage.getItem(userKey) || "null"),
  };
  const qs = (selector, root = document) => root.querySelector(selector);
  const qsa = (selector, root = document) => [...root.querySelectorAll(selector)];
  const params = new URLSearchParams(location.search);
  const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[character]);

  const nav = {
    admin: [
      ["admin/overview", "Overview", "dashboard"],
      ["admin/phases", "Phase Control", "account_tree"],
      ["admin/employees", "Employees", "group"],
      ["admin/confidence", "Confidence Scores", "verified"],
      ["admin/audit", "Agent Audit", "manage_search"],
    ],
    zm: [
      ["zm/welcome", "Home", "home"],
      ["zm/dashboard", "Dashboard", "dashboard"],
      ["zm/assessments", "Assessments", "fact_check"],
      ["zm/leaderboard", "Leaderboard", "leaderboard"],
    ],
    rd: [
      ["rd/welcome", "Home", "home"],
      ["rd/dashboard", "Dashboard", "dashboard"],
      ["rd/validations", "Validations", "verified_user"],
      ["rd/leaderboard", "Leaderboard", "leaderboard"],
    ],
    employee: [
      ["employee/welcome", "Home", "home"],
      ["employee/roleplays", "Role Plays", "record_voice_over"],
      ["employee/career", "Career Lattice", "route"],
      ["employee/courses", "Courses", "school"],
      ["employee/learning", "Learning Journey", "menu_book"],
      ["employee/leaderboard", "Leaderboard", "leaderboard"],
    ],
  };

  async function api(path, options = {}) {
    const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
    if (session.token) headers.Authorization = `Bearer ${session.token}`;
    const response = await fetch(path, { ...options, headers });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(payload.error?.message || `Request failed (${response.status})`);
      error.code = payload.error?.code;
      error.status = response.status;
      throw error;
    }
    return payload;
  }

  function go(route, query = "") {
    location.href = `/app/${route}${query}`;
  }

  function toast(message, type = "info") {
    qs("#mycareer-toast")?.remove();
    const node = document.createElement("div");
    node.id = "mycareer-toast";
    node.className = `fixed top-5 right-5 z-[100] max-w-md rounded-lg border px-5 py-4 shadow-xl text-sm ${
      type === "error" ? "bg-red-50 text-red-800 border-red-200" : "bg-white text-slate-800 border-slate-200"
    }`;
    node.textContent = message;
    document.body.appendChild(node);
    setTimeout(() => node.remove(), 5000);
  }

  function statusChip(status) {
    const normalized = status || "not_started";
    const color = ["submitted", "completed", "complete", "open"].includes(normalized)
      ? "bg-emerald-100 text-emerald-800"
      : ["draft", "processing"].includes(normalized)
        ? "bg-blue-100 text-blue-800"
        : "bg-slate-100 text-slate-700";
    return `<span class="inline-flex px-2.5 py-1 rounded-md text-xs font-bold ${color}">${esc(normalized.replaceAll("_", " "))}</span>`;
  }

  function empty(message, colspan = 1) {
    return `<tr><td colspan="${colspan}" class="px-6 py-12 text-center text-slate-500">${esc(message)}</td></tr>`;
  }

  function metric(label, value, detail = "") {
    return `<section class="border border-slate-200 bg-white p-5 rounded-xl">
      <p class="text-xs uppercase tracking-wider font-bold text-slate-500">${esc(label)}</p>
      <p class="text-3xl font-extrabold text-blue-700 mt-2">${esc(value)}</p>
      ${detail ? `<p class="text-xs text-slate-500 mt-1">${esc(detail)}</p>` : ""}
    </section>`;
  }

  function progress(label, phase) {
    const percentage = Number(phase.progress.percentage || 0);
    return `<section class="py-3">
      <div class="flex justify-between gap-3 text-sm"><strong>${esc(label)}</strong><span>${percentage}% · ${phase.progress.completed}/${phase.progress.total}</span></div>
      <div class="h-2 bg-slate-100 rounded mt-2 overflow-hidden"><div class="h-full bg-blue-600" style="width:${Math.min(100, percentage)}%"></div></div>
    </section>`;
  }

  function render(content) {
    const main = qs("#mc-main");
    if (main) main.innerHTML = `<div class="max-w-[1440px] mx-auto p-5 md:p-8">${content}</div>`;
  }

  function loading() {
    render('<div class="py-24 text-center text-slate-500">Loading current data…</div>');
  }

  function pageHeader(title, description = "", actions = "") {
    return `<div class="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-7">
      <div><h1 class="text-2xl md:text-3xl font-extrabold text-blue-800">${esc(title)}</h1>${description ? `<p class="text-slate-600 mt-1">${esc(description)}</p>` : ""}</div>
      ${actions ? `<div class="flex flex-wrap gap-2">${actions}</div>` : ""}
    </div>`;
  }

  function button(label, attributes = "", secondary = false) {
    return `<button ${attributes} class="px-4 py-2.5 rounded-lg font-bold text-sm ${
      secondary ? "border border-blue-700 text-blue-700 bg-white" : "bg-blue-700 text-white"
    } disabled:opacity-40">${esc(label)}</button>`;
  }

  function mountShell(user) {
    const items = nav[user.role] || [];
    const links = items.map(([route, label, icon]) => {
      const active = page === route;
      return `<a data-route="${route}" href="/app/${route}" class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-bold whitespace-nowrap ${
        active ? "bg-blue-700 text-white" : "text-slate-600 hover:bg-blue-50 hover:text-blue-800"
      }"><span class="material-symbols-outlined text-lg">${icon}</span>${esc(label)}</a>`;
    }).join("");
    document.body.className = "bg-slate-50 text-slate-900 min-h-screen";
    document.body.innerHTML = `<div class="min-h-screen">
      <header class="h-16 bg-white border-b border-slate-200 px-4 md:px-7 flex items-center justify-between sticky top-0 z-40">
        <a href="/app/${items[0]?.[0] || "login"}" class="flex items-center gap-3">
          <span class="w-9 h-9 rounded-lg bg-blue-700 text-white grid place-items-center font-black">MC</span>
          <span><strong class="block text-blue-800 leading-none">MyCareer Compass</strong><small class="text-slate-500">Enterprise Edition</small></span>
        </a>
        <div class="flex items-center gap-4"><div class="hidden sm:block text-right"><strong class="block text-sm">${esc(user.display_name)}</strong><small class="uppercase text-slate-500">${esc(user.role)}</small></div><button data-logout class="text-sm font-bold text-blue-700">Sign out</button></div>
      </header>
      <nav class="md:hidden bg-white border-b border-slate-200 p-2 flex gap-2 overflow-x-auto">${links}</nav>
      <div class="md:flex min-h-[calc(100vh-4rem)]">
        <aside class="hidden md:flex w-64 shrink-0 bg-white border-r border-slate-200 p-4 flex-col gap-2">${links}</aside>
        <main id="mc-main" class="flex-1 min-w-0"></main>
      </div>
    </div>`;
    qsa("[data-route]").forEach((link) => {
      link.onclick = (event) => { event.preventDefault(); go(link.dataset.route); };
    });
    qs("[data-logout]").onclick = logout;
    loading();
  }

  async function logout() {
    try {
      if (session.token) await api("/api/auth/logout", { method: "POST", body: "{}" });
    } catch (_) {
      // Local logout must still complete.
    }
    localStorage.removeItem(tokenKey);
    localStorage.removeItem(userKey);
    go("login");
  }

  function initLogin() {
    let selectedRole = "employee";
    window.selectRole = (role) => {
      selectedRole = role.toLowerCase();
      qsa(".role-btn").forEach((candidate) => {
        const label = candidate.querySelector("span:last-child")?.textContent.trim().toLowerCase();
        const active = label === selectedRole;
        candidate.classList.toggle("active-role", active);
        candidate.classList.toggle("border-2", active);
        candidate.classList.toggle("border-secondary", active);
        candidate.classList.toggle("bg-secondary/5", active);
        candidate.classList.toggle("border", !active);
        candidate.classList.toggle("border-outline-variant", !active);
        qsa("span", candidate).forEach((child) => {
          child.classList.toggle("text-secondary", active);
          child.classList.toggle("text-on-surface-variant", !active);
        });
      });
    };
    window.selectRole("Employee");
    window.togglePassword = (event) => {
      const input = qs("#password-input");
      input.type = input.type === "password" ? "text" : "password";
      if (event?.target) event.target.textContent = input.type === "password" ? "visibility" : "visibility_off";
    };
    window.handleLogin = async (event) => {
      event.preventDefault();
      const inputs = qsa("input", event.currentTarget);
      const errorBox = qs("#error-message");
      errorBox?.classList.add("hidden");
      try {
        const result = await api("/api/auth/login", {
          method: "POST",
          body: JSON.stringify({ login_id: inputs[0].value.trim(), role: selectedRole, password: inputs[1].value }),
        });
        session.token = result.token;
        session.user = result.user;
        localStorage.setItem(tokenKey, result.token);
        localStorage.setItem(userKey, JSON.stringify(result.user));
        go(selectedRole === "admin" ? "admin/overview" : `${selectedRole}/welcome`);
      } catch (error) {
        if (error.code === "phase_closed") {
          qs("#portal-closed-card")?.classList.remove("hidden");
          qs("#login-card")?.classList.add("opacity-10", "blur-sm", "pointer-events-none");
        } else {
          errorBox?.classList.remove("hidden");
          const message = qs("span:last-child", errorBox);
          if (message) message.textContent = error.message;
        }
      }
    };
  }

  async function authenticate() {
    if (!session.token) {
      go("login");
      return false;
    }
    try {
      session.user = (await api("/api/me")).user;
      localStorage.setItem(userKey, JSON.stringify(session.user));
      const expectedRole = page.split("/")[0];
      if (expectedRole !== session.user.role) {
        go(session.user.role === "admin" ? "admin/overview" : `${session.user.role}/welcome`);
        return false;
      }
      mountShell(session.user);
      return true;
    } catch (_) {
      localStorage.removeItem(tokenKey);
      localStorage.removeItem(userKey);
      go("login");
      return false;
    }
  }

  async function employeeSummaries() {
    return (await api("/api/employee-summaries")).employees;
  }

  async function initWelcome(role) {
    const phases = (await api("/api/phases")).phases;
    const phase = phases.find((item) => item.phase === role);
    let completed = 0;
    let total = 0;
    let nextRoute = `${role}/dashboard`;
    let workLabel = "Open Dashboard";
    if (role === "employee") {
      const result = await api("/api/employee/roleplays");
      completed = result.roleplays.filter((item) => item.status === "completed").length;
      total = result.roleplays.length;
      nextRoute = "employee/roleplays";
      workLabel = "Open Role Plays";
    } else {
      const employees = await employeeSummaries();
      total = employees.length;
      completed = employees.filter((item) => item[`${role}_status`] === "submitted").length;
      nextRoute = role === "zm" ? "zm/assessments" : "rd/validations";
      workLabel = role === "zm" ? "Open Assessments" : "Open Validations";
    }
    const descriptions = {
      zm: "Assess employees in your reporting scope using the seven-competency rubric.",
      rd: "Review submitted ZM assessments and publish final competency profiles.",
      employee: "Complete role plays, choose an aspiration, and build your learning journey.",
    };
    render(`<section class="max-w-4xl py-8 md:py-16">
      <p class="uppercase tracking-[0.2em] text-xs font-bold text-blue-700">${esc(role)} workspace</p>
      <h1 class="text-4xl md:text-5xl font-black text-blue-900 mt-3">Welcome, ${esc(session.user.display_name)}</h1>
      <p class="text-lg text-slate-600 mt-5 max-w-2xl">${esc(descriptions[role])}</p>
      <div class="mt-9 flex gap-3">${button(workLabel, `data-start="${nextRoute}"`)}${button("View Dashboard", `data-dashboard="${role === "employee" ? "employee/roleplays" : `${role}/dashboard`}"`, true)}</div>
      <section class="mt-12 border-t border-slate-200 pt-7">
        <div class="flex justify-between"><strong>Current progress</strong><span>${completed}/${total} complete</span></div>
        <div class="h-3 bg-slate-200 rounded mt-3 overflow-hidden"><div class="h-full bg-blue-700" style="width:${total ? (completed / total) * 100 : 0}%"></div></div>
        <p class="text-sm text-slate-500 mt-3">Phase status: ${esc(phase?.status || "closed")}. Values come from persisted submissions only.</p>
      </section>
    </section>`);
    qs("[data-start]").onclick = () => go(qs("[data-start]").dataset.start);
    qs("[data-dashboard]").onclick = () => go(qs("[data-dashboard]").dataset.dashboard);
  }

  function employeeTable(rows, role) {
    return `<div class="overflow-x-auto bg-white border border-slate-200 rounded-xl"><table class="w-full min-w-[760px] text-sm">
      <thead class="bg-slate-50 text-left"><tr><th class="p-4">Employee</th><th class="p-4">Role</th><th class="p-4">ZM</th><th class="p-4">RD</th><th class="p-4">Role plays</th><th class="p-4">Action</th></tr></thead>
      <tbody>${rows.map((row) => `<tr class="border-t border-slate-100">
        <td class="p-4"><strong>${esc(row.name)}</strong><div class="text-xs text-slate-500">${esc(row.employee_code)}</div></td>
        <td class="p-4">${esc(row.designation || row.role_name)}<div class="text-xs text-slate-500">${esc(row.grade)}</div></td>
        <td class="p-4">${statusChip(row.zm_status)}</td><td class="p-4">${statusChip(row.rd_status)}</td>
        <td class="p-4">${row.roleplays_completed}/${row.roleplays_total}</td>
        <td class="p-4">${button(role === "zm" ? (row.zm_status === "submitted" ? "View" : "Assess") : (row.rd_status === "submitted" ? "View" : "Validate"), `data-employee="${esc(row.employee_code)}"`, true)}</td>
      </tr>`).join("") || empty("No employees in your reporting scope.", 6)}</tbody></table></div>`;
  }

  async function initTeamDashboard(role) {
    const rows = await employeeSummaries();
    const key = `${role}_status`;
    const completed = rows.filter((row) => row[key] === "submitted").length;
    const drafts = rows.filter((row) => row[key] === "draft").length;
    render(`${pageHeader(`${role.toUpperCase()} Dashboard`, "Live workflow state for your reporting scope.")}
      <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-7">
        ${metric("Assigned employees", rows.length)}
        ${metric("Submitted", completed)}
        ${metric("Drafts", drafts)}
        ${metric("Not started", rows.length - completed - drafts)}
      </div>${employeeTable(rows, role)}`);
    qsa("[data-employee]").forEach((control) => {
      control.onclick = () => role === "zm"
        ? openAssessment(control.dataset.employee)
        : go("rd/validation", `?employee=${encodeURIComponent(control.dataset.employee)}`);
    });
  }

  async function initZmList() {
    const rows = await employeeSummaries();
    render(`${pageHeader("Competency Assessments", "Only saved drafts and submitted assessments affect these statuses.")}
      ${employeeTable(rows, "zm")}`);
    qsa("[data-employee]").forEach((control) => {
      control.onclick = () => openAssessment(control.dataset.employee);
    });
    if (params.get("employee")) openAssessment(params.get("employee"));
  }

  async function openAssessment(employeeCode) {
    try {
      const [meta, existing, rows] = await Promise.all([
        api("/api/meta"),
        api(`/api/assessment?employee_code=${encodeURIComponent(employeeCode)}`),
        employeeSummaries(),
      ]);
      const employee = rows.find((row) => row.employee_code === employeeCode);
      if (!employee) throw new Error("Employee not found in your reporting scope.");
      const assessment = existing.assessment;
      const locked = assessment?.status === "submitted";
      const modal = document.createElement("div");
      modal.className = "fixed inset-0 z-[80] bg-slate-900/50 overflow-y-auto p-3 md:p-8";
      modal.innerHTML = `<div class="max-w-5xl mx-auto bg-white rounded-xl">
        <header class="sticky top-0 z-10 bg-white border-b p-5 flex justify-between"><div><h2 class="text-2xl font-extrabold text-blue-800">${esc(employee.name)}</h2><p class="text-sm text-slate-500">${esc(employee.employee_code)} · ZM assessment</p></div><button data-close class="material-symbols-outlined">close</button></header>
        <div class="p-5 space-y-5">${meta.competencies.map((item) => `<section class="border border-slate-200 rounded-xl p-5">
          <h3 class="font-bold text-lg">${esc(item.competency)}</h3><p class="text-sm text-slate-500 mt-1">${esc(item.definition)}</p>
          <div class="grid md:grid-cols-4 gap-2 mt-4">${levels.map((level) => `<label class="border border-slate-200 rounded-lg p-3"><input type="radio" name="rating-${esc(item.competency)}" value="${level}" ${assessment?.ratings?.[item.competency] === level ? "checked" : ""} ${locked ? "disabled" : ""}><strong class="ml-2">${level}</strong><p class="text-xs text-slate-500 mt-2">${esc(meta.rubric[item.competency]?.[level] || "")}</p></label>`).join("")}</div>
          <textarea data-note="${esc(item.competency)}" ${locked ? "disabled" : ""} class="w-full border border-slate-200 rounded-lg p-3 mt-4" placeholder="Optional evidence note">${esc(assessment?.notes?.[item.competency] || "")}</textarea>
        </section>`).join("")}</div>
        <footer class="sticky bottom-0 bg-white border-t p-5 flex justify-end gap-3">${locked ? '<strong class="text-emerald-700">Submitted and locked</strong>' : `${button("Save Draft", "data-save", true)}${button("Submit & Lock", "data-submit")}`}</footer>
      </div>`;
      document.body.appendChild(modal);
      qs("[data-close]", modal).onclick = () => modal.remove();
      const save = async (submit) => {
        const ratings = {};
        meta.competencies.forEach((item) => {
          const selected = qs(`input[name="rating-${CSS.escape(item.competency)}"]:checked`, modal);
          if (selected) ratings[item.competency] = selected.value;
        });
        if (submit && Object.keys(ratings).length !== meta.competencies.length) {
          toast("Rate all seven competencies before submission.", "error");
          return;
        }
        if (submit && !confirm("Submit and lock this assessment?")) return;
        const notes = Object.fromEntries(qsa("[data-note]", modal).map((node) => [node.dataset.note, node.value]));
        await api("/api/assessment", { method: "POST", body: JSON.stringify({ employee_code: employeeCode, ratings, notes, submit }) });
        modal.remove();
        toast(submit ? "Assessment submitted." : "Draft saved.");
        await initZmList();
      };
      if (!locked) {
        qs("[data-save]", modal).onclick = () => save(false).catch((error) => toast(error.message, "error"));
        qs("[data-submit]", modal).onclick = () => save(true).catch((error) => toast(error.message, "error"));
      }
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function initRdList() {
    const all = await employeeSummaries();
    const eligible = all.filter((row) => row.zm_status === "submitted");
    render(`${pageHeader("RD Validations", "Employees appear only after ZM submission.")}
      <div class="grid sm:grid-cols-3 gap-4 mb-7">${metric("Assigned", all.length)}${metric("Ready for RD", eligible.filter((row) => row.rd_status !== "submitted").length)}${metric("RD submitted", eligible.filter((row) => row.rd_status === "submitted").length)}</div>
      ${employeeTable(eligible, "rd")}`);
    qsa("[data-employee]").forEach((control) => {
      control.onclick = () => go("rd/validation", `?employee=${encodeURIComponent(control.dataset.employee)}`);
    });
  }

  async function initRdDetail() {
    const code = params.get("employee");
    if (!code) {
      go("rd/validations");
      return;
    }
    const context = await api(`/api/rd/validation?employee_code=${encodeURIComponent(code)}`);
    if (!context.zm_assessment || context.zm_assessment.status !== "submitted") {
      render(`${pageHeader("Validation unavailable")}<div class="bg-white border rounded-xl p-8">ZM assessment has not been submitted.</div>`);
      return;
    }
    const locked = context.rd_assessment?.status === "submitted";
    const ratings = { ...(context.rd_assessment?.ratings || {}) };
    const notes = { ...(context.rd_assessment?.notes || {}) };
    render(`${pageHeader(`Validate ${context.employee.name}`, `${context.employee.employee_code} · ${context.employee.designation} · ${context.employee.grade}`, button("Back", "data-back", true))}
      <p class="mb-6 p-4 bg-blue-50 border border-blue-100 rounded-lg text-sm">Evidence supports review; it never determines the RD rating.</p>
      <div class="space-y-5">${Object.entries(context.evidence).map(([competency, bundle]) => `<section class="bg-white border border-slate-200 rounded-xl p-5">
        <div class="grid lg:grid-cols-2 gap-6"><div><h2 class="text-lg font-bold">${esc(competency)}</h2><p class="text-sm mt-2">ZM rating: <strong>${esc(context.zm_assessment.ratings?.[competency] || "Not rated")}</strong></p>
        <p class="text-sm text-slate-500 mt-1">${esc(context.zm_assessment.notes?.[competency] || "No ZM note.")}</p>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-2 mt-4">${levels.map((level) => `<button data-rating="${esc(competency)}" data-level="${level}" ${locked ? "disabled" : ""} class="p-2 border rounded-lg text-xs ${ratings[competency] === level ? "bg-blue-700 text-white border-blue-700" : "border-slate-200"}">${level}</button>`).join("")}</div>
        <textarea data-rd-note="${esc(competency)}" ${locked ? "disabled" : ""} class="w-full border rounded-lg p-3 mt-4" placeholder="Optional RD note">${esc(notes[competency] || "")}</textarea></div>
        <div><h3 class="font-bold text-sm">Supporting evidence</h3>${(bundle.evidence || []).map((item) => `<article class="border border-slate-200 rounded-lg p-3 mt-3"><strong class="text-xs text-blue-700">${esc(item.source)}</strong><p class="text-sm mt-1">${esc(item.snippet)}</p></article>`).join("") || '<p class="text-sm text-slate-500 mt-3">No relevant evidence found.</p>'}</div></div>
      </section>`).join("")}</div>
      <div class="mt-6 flex justify-end gap-3">${locked ? '<strong class="text-emerald-700">Final profile submitted and locked</strong>' : `${button("Save Draft", "data-draft", true)}${button("Submit Final Profile", "data-final")}`}</div>`);
    qs("[data-back]").onclick = () => go("rd/validations");
    if (locked) return;
    qsa("[data-rating]").forEach((control) => {
      control.onclick = () => {
        ratings[control.dataset.rating] = control.dataset.level;
        qsa(`[data-rating="${CSS.escape(control.dataset.rating)}"]`).forEach((item) => item.classList.remove("bg-blue-700", "text-white", "border-blue-700"));
        control.classList.add("bg-blue-700", "text-white", "border-blue-700");
      };
    });
    const save = async (submit) => {
      if (submit && Object.keys(ratings).length !== Object.keys(context.evidence).length) {
        toast("Rate all seven competencies before submission.", "error");
        return;
      }
      if (submit && !confirm("Submit and lock final RD profile?")) return;
      qsa("[data-rd-note]").forEach((node) => { notes[node.dataset.rdNote] = node.value; });
      await api("/api/assessment", { method: "POST", body: JSON.stringify({ employee_code: code, ratings, notes, submit }) });
      toast(submit ? "Final profile submitted." : "Draft saved.");
      if (submit) go("rd/validations");
    };
    qs("[data-draft]").onclick = () => save(false).catch((error) => toast(error.message, "error"));
    qs("[data-final]").onclick = () => save(true).catch((error) => toast(error.message, "error"));
  }

  async function initRoleplays() {
    const result = await api("/api/employee/roleplays");
    const completed = result.roleplays.filter((row) => row.status === "completed").length;
    render(`${pageHeader("Competency Role Plays", "Only successfully assessed screenshots count as completed.")}
      <div class="mb-7">${metric("Completed", `${completed}/${result.roleplays.length}`, result.lattice_unlocked ? "Career lattice unlocked" : "Complete all role plays to unlock career lattice")}</div>
      <div class="grid md:grid-cols-2 xl:grid-cols-3 gap-4">${result.roleplays.map((row) => `<section class="bg-white border border-slate-200 rounded-xl p-5 flex flex-col min-h-[220px]">
        <h2 class="font-bold text-lg">${esc(row.competency)}</h2><div class="mt-2">${statusChip(row.status)}</div>
        ${row.error ? `<p class="text-sm text-red-700 mt-3">${esc(row.error)}</p>` : ""}
        <div class="mt-auto pt-5 flex flex-wrap gap-2">${row.link_available ? `<a class="px-3 py-2 border border-blue-700 text-blue-700 rounded-lg font-bold text-sm" href="${esc(row.roleplay_url)}" target="_blank" rel="noopener">Open Role Play</a>` : ""}
        <label class="px-3 py-2 bg-blue-700 text-white rounded-lg font-bold text-sm cursor-pointer">Upload Screenshot<input data-upload="${esc(row.competency)}" class="hidden" type="file" accept="image/png,image/jpeg,image/webp"></label></div>
      </section>`).join("")}</div>
      ${result.lattice_unlocked ? `<div class="mt-7">${button("Open Career Lattice", "data-career")}</div>` : ""}`);
    qsa("[data-upload]").forEach((input) => {
      input.onchange = () => uploadRoleplay(input.dataset.upload, input.files[0]);
    });
    if (qs("[data-career]")) qs("[data-career]").onclick = () => go("employee/career");
  }

  function fileBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result).split(",")[1]);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  async function uploadRoleplay(competency, file) {
    if (!file) return;
    try {
      toast(`Uploading ${competency} screenshot…`);
      const result = await api("/api/employee/roleplays", {
        method: "POST",
        body: JSON.stringify({ competency, filename: file.name, content_base64: await fileBase64(file) }),
      });
      toast(result.status === "completed" ? "Screenshot assessed." : (result.error || "Screenshot requires re-upload"), result.status === "completed" ? "info" : "error");
      await initRoleplays();
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function initCareer() {
    const state = await api("/api/employee/career");
    render(`${pageHeader("Career Lattice", "Available paths derive from your current role, grade, and completed role plays.")}
      ${!state.unlocked ? '<div class="bg-white border border-slate-200 rounded-xl p-8 text-center"><h2 class="text-xl font-bold">Career lattice locked</h2><p class="text-slate-500 mt-2">Complete all seven role plays first.</p><div class="mt-5">' + button("Open Role Plays", "data-roleplays") + "</div></div>" : `
      <section class="bg-white border border-slate-200 rounded-xl p-6"><p class="text-sm text-slate-500">Current track</p><h2 class="text-2xl font-bold mt-1">${esc(state.current)}</h2>
      <div class="grid md:grid-cols-3 gap-4 mt-7">${state.paths.map((path) => `<button data-path="${esc(path.id)}" ${!path.enabled || state.choice ? "disabled" : ""} class="border rounded-xl p-5 text-left ${path.enabled ? "border-blue-300" : "border-slate-200 opacity-50"}"><strong>${esc(path.label)}</strong><p class="text-sm text-slate-500 mt-2">${path.enabled ? "Available" : "Locked for current grade"}</p></button>`).join("")}</div>
      ${state.choice ? `<p class="mt-6 p-4 bg-blue-50 rounded-lg font-bold">Locked aspiration: ${esc(state.paths.find((path) => path.id === state.choice.aspiration_role)?.label || state.choice.aspiration_role)}</p>` : ""}</section>`}`);
    if (qs("[data-roleplays]")) qs("[data-roleplays]").onclick = () => go("employee/roleplays");
    qsa("[data-path]").forEach((control) => {
      control.onclick = async () => {
        if (!confirm("Lock this aspiration? Only Admin can reset it.")) return;
        try {
          await api("/api/employee/career", { method: "POST", body: JSON.stringify({ aspiration_role: control.dataset.path }) });
          go("employee/courses");
        } catch (error) {
          toast(error.message, "error");
        }
      };
    });
  }

  let basket = new Map();
  async function initCourses() {
    const result = await api("/api/employee/courses");
    const entries = Object.entries(result.competencies || {});
    render(`${pageHeader("Recommended Courses", "Recommendations are generated only from persisted final-profile gaps.")}
      <div class="grid lg:grid-cols-[1fr_300px] gap-6"><div>${entries.map(([competency, courses]) => {
        const gap = result.target.gaps.find((item) => item.competency === competency);
        return `<section class="mb-8"><h2 class="text-xl font-bold">${esc(competency)}</h2><p class="text-sm text-slate-500 mt-1">${esc(gap?.current)} → ${esc(gap?.target)}</p>
          <div class="grid md:grid-cols-2 gap-4 mt-4">${courses.map((course) => `<article class="bg-white border border-slate-200 rounded-xl p-5"><h3 class="font-bold">${esc(course.title)}</h3><p class="text-xs text-slate-500 mt-2">${esc(course.provider)} · ${esc(course.duration)}</p><p class="text-sm mt-3">${esc(course.reason || course.description || "")}</p><div class="flex justify-between mt-5"><a href="${esc(course.url)}" target="_blank" rel="noopener" class="text-blue-700 font-bold">Preview</a>${button("Add", `data-course="${esc(course.id)}" data-competency="${esc(competency)}" data-title="${esc(course.title)}"`)}</div></article>`).join("")}</div></section>`;
      }).join("") || `<div class="bg-white border border-slate-200 rounded-xl p-8">${result.target?.mode === "aspiration_required" ? "Choose a career aspiration to activate its precomputed courses." : !result.ready && result.target?.gaps?.length ? "Course recommendations are being prepared from the final RD profile." : "No proficiency gaps currently require courses."}</div>`}</div>
      <aside class="bg-white border border-slate-200 rounded-xl p-5 h-fit"><h2 class="font-bold text-lg">Learning Basket</h2><div data-basket class="text-sm text-slate-500 py-5">No courses selected.</div>${button("Finalize Journey", "data-checkout disabled")}</aside></div>`);
    qsa("[data-course]").forEach((control) => {
      control.onclick = () => {
        basket.set(control.dataset.course, { id: control.dataset.course, competency: control.dataset.competency, title: control.dataset.title });
        renderBasket(entries.map(([competency]) => competency));
      };
    });
  }

  function renderBasket(required) {
    qs("[data-basket]").innerHTML = [...basket.values()].map((item) => `<div class="border-t py-2"><strong>${esc(item.title)}</strong><p class="text-xs text-blue-700">${esc(item.competency)}</p></div>`).join("") || "No courses selected.";
    const covered = new Set([...basket.values()].map((item) => item.competency));
    const checkout = qs("[data-checkout]");
    checkout.disabled = required.some((competency) => !covered.has(competency));
    checkout.onclick = async () => {
      try {
        await api("/api/employee/learning/checkout", { method: "POST", body: JSON.stringify({ course_ids: [...basket.keys()] }) });
        go("employee/learning");
      } catch (error) {
        toast(error.message, "error");
      }
    };
  }

  async function initLearning() {
    const result = await api("/api/employee/learning");
    const groups = result.courses.reduce((output, course) => {
      (output[course.competency] ||= []).push(course);
      return output;
    }, {});
    render(`${pageHeader("My Learning Journey", "Selected courses and LinkedIn Learning activity only.")}
      <div class="grid sm:grid-cols-3 gap-4 mb-7">${metric("Selected courses", result.courses.length)}${metric("LinkedIn hours", `${Number(result.linkedin.learning_hours || 0).toFixed(1)}h`)}${metric("LinkedIn completions", result.linkedin.completions || 0, result.linkedin.synced_at ? `Synced ${result.linkedin.synced_at}` : "Not synced")}</div>
      ${Object.entries(groups).map(([competency, courses]) => `<section class="mb-7"><h2 class="text-xl font-bold mb-3">${esc(competency)}</h2><div class="bg-white border rounded-xl divide-y">${courses.map((course) => `<div class="p-4 flex flex-col sm:flex-row sm:justify-between gap-2"><a href="${esc(course.url)}" target="_blank" rel="noopener" class="font-bold text-blue-700">${esc(course.title)}</a><span class="text-sm text-slate-500">${esc(course.provider)} · ${esc(course.duration)}</span></div>`).join("")}</div></section>`).join("") || '<div class="bg-white border rounded-xl p-8 text-center text-slate-500">No courses selected yet.</div>'}`);
  }

  async function initLeaderboard() {
    const rows = (await api("/api/leaderboard")).leaderboard;
    render(`${pageHeader("Learning Leaderboard", "Employees are compared only within equal proficiency-gap cohorts; rank uses synced LinkedIn hours.")}
      <div class="overflow-x-auto bg-white border rounded-xl"><table class="w-full min-w-[600px] text-sm"><thead class="bg-slate-50 text-left"><tr><th class="p-4">Rank</th><th class="p-4">Employee</th><th class="p-4">Gap cohort</th><th class="p-4">LinkedIn hours</th></tr></thead>
      <tbody>${rows.map((row) => `<tr class="border-t"><td class="p-4 font-bold text-blue-700">#${row.rank}</td><td class="p-4"><strong>${esc(row.name)}</strong><div class="text-xs text-slate-500">${esc(row.employee_code)}</div></td><td class="p-4">${row.gap_cohort}</td><td class="p-4 font-bold">${Number(row.learning_hours).toFixed(1)}h</td></tr>`).join("") || empty("Leaderboard is empty until final profiles and synced LinkedIn activity exist.", 4)}</tbody></table></div>`);
  }

  async function initAdminOverview() {
    const [result, audit, meta] = await Promise.all([
      api("/api/admin/overview"),
      api("/api/admin/audit?limit=8"),
      api("/api/meta"),
    ]);
    const actions = `${button("Export Employees", "data-export", true)}${button("Sync LinkedIn", "data-sync")}`;
    render(`${pageHeader("Admin Overview", "All metrics are calculated from persisted workflow records.", actions)}
      <div class="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3 mb-7">
        ${metric("Total employees", result.metrics.total_employees)}
        ${metric("ZM submitted", result.metrics.zm_completed)}
        ${metric("RD submitted", result.metrics.rd_completed)}
        ${metric("Role plays complete", result.metrics.roleplays_completed)}
        ${metric("Locked aspirations", result.metrics.locked_aspirations)}
        ${metric("Active journeys", result.metrics.active_journeys)}
        ${metric("LinkedIn hours", `${Number(result.metrics.learning_hours).toFixed(1)}h`)}
      </div>
      <div class="grid lg:grid-cols-2 gap-6"><section class="bg-white border rounded-xl p-6"><h2 class="text-xl font-bold">Phase progress</h2>${result.phases.map((phase) => progress(phase.phase === "zm" ? "ZM Assessment" : phase.phase === "rd" ? "RD Validation" : "Employee Experience", phase)).join("")}</section>
      <section class="bg-white border rounded-xl p-6"><h2 class="text-xl font-bold">Recent agent activity</h2><div class="mt-3 divide-y">${audit.audit.map((row) => `<div class="py-3"><strong class="text-sm">${esc(row.agent)}</strong><p class="text-xs text-slate-500">${esc(row.employee_code)} · ${esc(row.competency || "General")} · ${esc(row.created_at)}</p></div>`).join("") || '<p class="py-8 text-center text-slate-500">No agent activity recorded yet.</p>'}</div></section></div>
      <section class="bg-white border rounded-xl p-6 mt-6"><h2 class="text-xl font-bold">Competency framework</h2><div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 mt-4">${meta.competencies.map((item) => `<div class="border rounded-lg p-3"><strong>${esc(item.competency)}</strong><p class="text-xs text-slate-500 mt-1">${esc(item.definition)}</p></div>`).join("")}</div></section>`);
    qs("[data-sync]").onclick = async () => {
      try {
        const response = await api("/api/admin/linkedin/sync", { method: "POST", body: "{}" });
        toast(response.message || `LinkedIn sync: ${response.status}`);
        await initAdminOverview();
      } catch (error) {
        toast(error.message, "error");
      }
    };
    qs("[data-export]").onclick = () => exportEmployees(result.employees);
  }

  function exportEmployees(rows) {
    const fields = ["employee_code", "name", "designation", "grade", "location", "zm_name", "rd_name", "zm_status", "rd_status", "roleplays_completed"];
    const csv = [fields.join(","), ...rows.map((row) => fields.map((field) => `"${String(row[field] ?? "").replaceAll('"', '""')}"`).join(","))].join("\n");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    link.download = "mycareer-employees.csv";
    link.click();
    URL.revokeObjectURL(link.href);
  }

  async function initPhases() {
    const phases = (await api("/api/phases")).phases;
    const names = { zm: "ZM Competency Assessment", rd: "RD Competency Validation", employee: "Employee Career & Learning" };
    render(`${pageHeader("Phase Control", "Opening a later phase requires 100% prior completion or explicit Admin override.")}
      <div class="space-y-4">${phases.map((phase) => `<section class="bg-white border border-slate-200 rounded-xl p-6">
        <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4"><div><div class="flex items-center gap-3"><h2 class="text-xl font-bold">${esc(names[phase.phase])}</h2>${statusChip(phase.status)}</div><p class="text-sm text-slate-500 mt-2">${phase.progress.completed}/${phase.progress.total} complete · ${phase.progress.percentage}%${phase.override_used ? " · opened by override" : ""}</p></div>
        ${button(phase.status === "open" ? "Close Phase" : "Open Phase", `data-phase="${phase.phase}" data-status="${phase.status}"`)}</div>
        <div class="h-2 bg-slate-100 rounded mt-5 overflow-hidden"><div class="h-full bg-blue-700" style="width:${phase.progress.percentage}%"></div></div>
      </section>`).join("")}</div>`);
    qsa("[data-phase]").forEach((control) => {
      control.onclick = async () => {
        const phase = phases.find((item) => item.phase === control.dataset.phase);
        try {
          if (phase.status === "open") {
            if (!confirm(`Close ${names[phase.phase]}?`)) return;
            await api("/api/admin/phases/close", { method: "POST", body: JSON.stringify({ phase: phase.phase }) });
          } else {
            const previousIndex = phases.findIndex((item) => item.phase === phase.phase) - 1;
            const previousIncomplete = previousIndex >= 0 && !phases[previousIndex].progress.is_complete;
            let override = false;
            if (previousIncomplete) {
              override = confirm("Previous phase is below 100%. Open with explicit Admin override?");
              if (!override) return;
            }
            await api("/api/admin/phases/open", { method: "POST", body: JSON.stringify({ phase: phase.phase, override }) });
          }
          await initPhases();
        } catch (error) {
          toast(error.message, "error");
        }
      };
    });
  }

  async function initAdminEmployees() {
    const rows = await employeeSummaries();
    render(`${pageHeader("Employee Master", "Workbook identity plus persisted workflow status.", button("Export CSV", "data-export", true))}
      <label class="block mb-4"><span class="sr-only">Search employees</span><input data-search class="w-full md:w-96 border border-slate-200 rounded-lg px-4 py-3" placeholder="Search code, name, role, manager"></label>
      <div data-table></div>`);
    const draw = (filtered) => {
      qs("[data-table]").innerHTML = `<div class="overflow-x-auto bg-white border rounded-xl"><table class="w-full min-w-[1000px] text-sm"><thead class="bg-slate-50 text-left"><tr><th class="p-4">Employee</th><th class="p-4">Role</th><th class="p-4">ZM</th><th class="p-4">RD</th><th class="p-4">Assessment status</th><th class="p-4">Role plays</th><th class="p-4">Aspiration</th><th class="p-4">Actions</th></tr></thead><tbody>
        ${filtered.map((row) => `<tr class="border-t"><td class="p-4"><strong>${esc(row.name)}</strong><div class="text-xs">${esc(row.employee_code)}</div></td><td class="p-4">${esc(row.designation)}<div class="text-xs">${esc(row.grade)}</div></td><td class="p-4">${esc(row.zm_name)}</td><td class="p-4">${esc(row.rd_name)}</td><td class="p-4">${statusChip(row.zm_status)} ${statusChip(row.rd_status)}</td><td class="p-4">${row.roleplays_completed}/${row.roleplays_total}</td><td class="p-4">${esc(row.aspiration?.aspiration_role || "Not selected")}</td><td class="p-4 flex flex-wrap gap-2">${button("Profile", `data-profile="${row.employee_code}"`, true)}${button("Role Plays", `data-roleplay-review="${row.employee_code}"`, true)}${row.aspiration ? button("Reset", `data-reset="${row.employee_code}"`, true) : ""}</td></tr>`).join("") || empty("No matching employees.", 8)}</tbody></table></div>`;
      qsa("[data-profile]").forEach((control) => { control.onclick = () => openFinalProfile(control.dataset.profile); });
      qsa("[data-roleplay-review]").forEach((control) => {
        control.onclick = () => openAdminRoleplays(control.dataset.roleplayReview);
      });
      qsa("[data-reset]").forEach((control) => {
        control.onclick = async () => {
          if (!confirm("Reset this employee's aspiration and learning selections?")) return;
          try {
            await api("/api/admin/career/reset", { method: "POST", body: JSON.stringify({ employee_code: control.dataset.reset }) });
            await initAdminEmployees();
          } catch (error) {
            toast(error.message, "error");
          }
        };
      });
    };
    draw(rows);
    qs("[data-search]").oninput = (event) => {
      const term = event.target.value.trim().toLowerCase();
      draw(rows.filter((row) => [row.employee_code, row.name, row.designation, row.zm_name, row.rd_name].some((value) => String(value || "").toLowerCase().includes(term))));
    };
    qs("[data-export]").onclick = () => exportEmployees(rows);
  }

  async function openFinalProfile(employeeCode) {
    try {
      const result = await api(`/api/final-profile?employee_code=${encodeURIComponent(employeeCode)}`);
      const modal = document.createElement("div");
      modal.className = "fixed inset-0 z-[80] bg-slate-900/50 p-4 grid place-items-center";
      modal.innerHTML = `<section class="bg-white rounded-xl p-6 max-w-xl w-full"><div class="flex justify-between"><div><h2 class="text-2xl font-bold">${esc(result.employee.name)}</h2><p class="text-sm text-slate-500">${esc(result.employee.employee_code)} · ${esc(result.status)}</p></div><button data-close class="material-symbols-outlined">close</button></div>
        <div class="mt-5 divide-y">${Object.entries(result.ratings).map(([competency, rating]) => `<div class="py-3 flex justify-between gap-3"><span>${esc(competency)}</span><strong>${esc(rating)}</strong></div>`).join("") || '<p class="py-8 text-center text-slate-500">Final RD profile pending.</p>'}</div></section>`;
      document.body.appendChild(modal);
      qs("[data-close]", modal).onclick = () => modal.remove();
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function openAdminRoleplays(employeeCode) {
    try {
      const result = await api(`/api/admin/roleplays?employee_code=${encodeURIComponent(employeeCode)}`);
      const modal = document.createElement("div");
      modal.className = "fixed inset-0 z-[80] bg-slate-900/50 p-4 overflow-y-auto";
      modal.innerHTML = `<section class="bg-white rounded-xl p-6 max-w-5xl mx-auto my-6">
        <div class="flex justify-between gap-4"><div><h2 class="text-2xl font-bold">${esc(result.employee.name)} · Role Plays</h2><p class="text-sm text-slate-500">${esc(result.employee.employee_code)} · Admin-only assessment evidence</p></div><button data-close class="material-symbols-outlined">close</button></div>
        <div data-screenshot-preview class="hidden mt-6"></div>
        <div class="grid md:grid-cols-2 gap-4 mt-6">${result.roleplays.map((row) => `<article class="border border-slate-200 rounded-xl p-5">
          <div class="flex justify-between gap-3"><h3 class="font-bold">${esc(row.competency)}</h3>${statusChip(row.status)}</div>
          <p class="text-sm mt-3">Assessed level: <strong>${esc(row.ai_proficiency || "Pending")}</strong></p>
          <p class="text-sm text-slate-600 mt-2">${esc(row.rationale || "No assessed behavior available.")}</p>
          ${row.ocr_text ? `<details class="mt-3"><summary class="text-sm font-bold text-blue-700 cursor-pointer">Extracted behavior text</summary><p class="text-xs whitespace-pre-wrap mt-2 text-slate-600">${esc(row.ocr_text)}</p></details>` : ""}
          ${row.screenshot_available ? `<div class="mt-4">${button("View Screenshot", `data-view-screenshot="${esc(row.competency)}"`, true)}</div>` : ""}
        </article>`).join("")}</div>
      </section>`;
      document.body.appendChild(modal);
      qs("[data-close]", modal).onclick = () => modal.remove();
      qsa("[data-view-screenshot]", modal).forEach((control) => {
        control.onclick = async () => {
          try {
            const detail = await api(`/api/admin/roleplays?employee_code=${encodeURIComponent(employeeCode)}&competency=${encodeURIComponent(control.dataset.viewScreenshot)}`);
            const screenshot = detail.screenshot;
            const preview = qs("[data-screenshot-preview]", modal);
            preview.classList.remove("hidden");
            preview.innerHTML = `<div class="border rounded-xl p-4 bg-slate-50"><div class="flex justify-between gap-3 mb-3"><strong>${esc(screenshot.competency)} screenshot</strong><button data-hide-preview class="material-symbols-outlined">close</button></div><img class="max-h-[65vh] mx-auto rounded border" src="data:${esc(screenshot.content_type)};base64,${screenshot.content_base64}" alt="${esc(screenshot.competency)} role-play screenshot"></div>`;
            qs("[data-hide-preview]", preview).onclick = () => preview.classList.add("hidden");
            preview.scrollIntoView({ behavior: "smooth" });
          } catch (error) {
            toast(error.message, "error");
          }
        };
      });
    } catch (error) {
      toast(error.message, "error");
    }
  }

  async function initConfidence() {
    const overview = await api("/api/admin/overview");
    const selected = params.get("employee") || overview.employees[0]?.employee_code || "";
    const options = overview.employees.map((row) => `<option value="${esc(row.employee_code)}" ${row.employee_code === selected ? "selected" : ""}>${esc(row.name)} (${esc(row.employee_code)})</option>`).join("");
    if (!selected) {
      render(`${pageHeader("Confidence Scores")}<p class="bg-white border rounded-xl p-8">No employees available.</p>`);
      return;
    }
    const result = await api(`/api/admin/confidence?employee_code=${encodeURIComponent(selected)}`);
    render(`${pageHeader("Confidence Scores", "Calculated only when ZM, RD, and all seven AI role-play ratings exist.", `<select data-employee-select class="border rounded-lg px-3 py-2 bg-white">${options}</select>`)}
      <div class="mb-7">${metric("Overall confidence", result.score == null ? "Pending" : `${result.score}%`, result.band || `${result.completed || 0}/${result.total || 7} competencies complete`)}</div>
      <div class="overflow-x-auto bg-white border rounded-xl"><table class="w-full min-w-[850px] text-sm"><thead class="bg-slate-50 text-left"><tr><th class="p-4">Competency</th><th class="p-4">RD</th><th class="p-4">ZM</th><th class="p-4">AI</th><th class="p-4">ZM agreement</th><th class="p-4">AI agreement</th><th class="p-4">Confidence</th></tr></thead><tbody>
      ${(result.competencies || []).map((row) => `<tr class="border-t"><td class="p-4 font-bold">${esc(row.competency)}</td><td class="p-4">${esc(row.rd_rating || "Pending")}</td><td class="p-4">${esc(row.zm_rating || "Pending")}</td><td class="p-4">${esc(row.ai_rating || "Pending")}</td><td class="p-4">${row.zm_agreement == null ? "—" : `${row.zm_agreement}%`}</td><td class="p-4">${row.ai_agreement == null ? "—" : `${row.ai_agreement}%`}</td><td class="p-4">${row.confidence == null ? "Pending" : `${row.confidence}%`}</td></tr>`).join("") || empty("Confidence pending. Required assessment and role-play inputs are incomplete.", 7)}</tbody></table></div>`);
    qs("[data-employee-select]").onchange = (event) => go("admin/confidence", `?employee=${encodeURIComponent(event.target.value)}`);
  }

  async function initAudit() {
    const rows = (await api("/api/admin/audit?limit=100")).audit;
    render(`${pageHeader("Agent Audit", "Persisted decisions from the three active agents only.")}
      <div class="mb-7">${metric("Recorded decisions", rows.length)}</div>
      <div class="overflow-x-auto bg-white border rounded-xl"><table class="w-full min-w-[900px] text-sm"><thead class="bg-slate-50 text-left"><tr><th class="p-4">Time</th><th class="p-4">Employee</th><th class="p-4">Agent</th><th class="p-4">Competency</th><th class="p-4">Input</th><th class="p-4">Status</th></tr></thead><tbody>
      ${rows.map((row) => `<tr class="border-t"><td class="p-4 text-xs">${esc(row.created_at)}</td><td class="p-4">${esc(row.employee_code)}</td><td class="p-4 font-bold">${esc(row.agent)}</td><td class="p-4">${esc(row.competency || "—")}</td><td class="p-4">${esc(row.input_summary)}</td><td class="p-4">${statusChip(row.status)}</td></tr>`).join("") || empty("No agent activity recorded yet.", 6)}</tbody></table></div>`);
  }

  async function boot() {
    if (page === "login") {
      initLogin();
      return;
    }
    if (!(await authenticate())) return;
    const handlers = {
      "zm/welcome": () => initWelcome("zm"),
      "zm/dashboard": () => initTeamDashboard("zm"),
      "zm/assessments": initZmList,
      "zm/leaderboard": initLeaderboard,
      "rd/welcome": () => initWelcome("rd"),
      "rd/dashboard": () => initTeamDashboard("rd"),
      "rd/validations": initRdList,
      "rd/validation": initRdDetail,
      "rd/leaderboard": initLeaderboard,
      "employee/welcome": () => initWelcome("employee"),
      "employee/roleplays": initRoleplays,
      "employee/career": initCareer,
      "employee/courses": initCourses,
      "employee/learning": initLearning,
      "employee/leaderboard": initLeaderboard,
      "admin/overview": initAdminOverview,
      "admin/phases": initPhases,
      "admin/employees": initAdminEmployees,
      "admin/confidence": initConfidence,
      "admin/audit": initAudit,
    };
    try {
      await handlers[page]();
    } catch (error) {
      console.error(error);
      render(`${pageHeader("Unable to load page")}<div class="bg-white border border-red-200 rounded-xl p-6 text-red-800">${esc(error.message || "Unknown error")}</div>`);
    }
  }

  boot();
})();
