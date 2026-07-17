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
      ["employee/roleplays", "Assessments", "record_voice_over"],
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
        : ["locked"].includes(normalized)
          ? "bg-red-100 text-red-800"
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

  const employeeTheme = () => session.user?.role === "employee";

  function pageHeader(title, description = "", actions = "") {
    const titleClass = employeeTheme() ? "text-[#df162b]" : "text-blue-800";
    return `<div class="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-7">
      <div><h1 class="text-2xl md:text-3xl font-extrabold ${titleClass}">${esc(title)}</h1>${description ? `<p class="text-slate-600 mt-1">${esc(description)}</p>` : ""}</div>
      ${actions ? `<div class="flex flex-wrap gap-2">${actions}</div>` : ""}
    </div>`;
  }

  function button(label, attributes = "", secondary = false) {
    const primary = employeeTheme()
      ? (secondary ? "border border-[#1464F4] text-[#1464F4] bg-white" : "bg-[#1464F4] text-white")
      : (secondary ? "border border-blue-700 text-blue-700 bg-white" : "bg-blue-700 text-white");
    return `<button ${attributes} class="px-4 py-2.5 rounded-lg font-bold text-sm ${primary} disabled:opacity-40">${esc(label)}</button>`;
  }

  function mountShell(user) {
    const items = nav[user.role] || [];
    const mmt = user.role === "employee";
    const links = items.map(([route, label, icon]) => {
      const active = page === route;
      const activeClass = mmt
        ? "bg-[#df162b] text-white"
        : "bg-blue-700 text-white";
      const idleClass = mmt
        ? "text-slate-600 hover:bg-[#fff0ef] hover:text-[#df162b]"
        : "text-slate-600 hover:bg-blue-50 hover:text-blue-800";
      return `<a data-route="${route}" href="/app/${route}" class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-bold whitespace-nowrap ${
        active ? activeClass : idleClass
      }"><span class="material-symbols-outlined text-lg">${icon}</span>${esc(label)}</a>`;
    }).join("");
    document.body.className = mmt ? "bg-[#fff8f7] text-slate-900 min-h-screen" : "bg-slate-50 text-slate-900 min-h-screen";
    document.body.innerHTML = `<div class="min-h-screen">
      <header class="h-16 bg-white border-b border-slate-200 px-4 md:px-7 flex items-center justify-between sticky top-0 z-40">
        <a href="/app/${items[0]?.[0] || "login"}" class="flex items-center gap-3">
          <span class="w-9 h-9 rounded-lg ${mmt ? "bg-[#df162b]" : "bg-blue-700"} text-white grid place-items-center font-black">MC</span>
          <span><strong class="block ${mmt ? "text-[#df162b]" : "text-blue-800"} leading-none">MyCareer Compass</strong><small class="text-slate-500">Enterprise Edition</small></span>
        </a>
        <div class="flex items-center gap-4"><div class="hidden sm:block text-right"><strong class="block text-sm">${esc(user.display_name)}</strong><small class="uppercase text-slate-500">${esc(user.role)}</small></div><button data-logout class="text-sm font-bold ${mmt ? "text-[#1464F4]" : "text-blue-700"}">Sign out</button></div>
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

  async function authenticate(options = {}) {
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
      if (!options.skipShell) mountShell(session.user);
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
    if (role === "employee") {
      await initEmployeeWelcome();
      return;
    }
    const phases = (await api("/api/phases")).phases;
    const phase = phases.find((item) => item.phase === role);
    const employees = await employeeSummaries();
    const total = employees.length;
    const completed = employees.filter((item) => item[`${role}_status`] === "submitted").length;
    const nextRoute = role === "zm" ? "zm/assessments" : "rd/validations";
    const workLabel = role === "zm" ? "Open Assessments" : "Open Validations";
    const descriptions = {
      zm: "Assess employees in your reporting scope using the seven-competency rubric.",
      rd: "Review submitted ZM assessments and publish final competency profiles.",
    };
    render(`<section class="max-w-4xl py-8 md:py-16">
      <p class="uppercase tracking-[0.2em] text-xs font-bold text-blue-700">${esc(role)} workspace</p>
      <h1 class="text-4xl md:text-5xl font-black text-blue-900 mt-3">Welcome, ${esc(session.user.display_name)}</h1>
      <p class="text-lg text-slate-600 mt-5 max-w-2xl">${esc(descriptions[role])}</p>
      <div class="mt-9 flex gap-3">${button(workLabel, `data-start="${nextRoute}"`)}${button("View Dashboard", `data-dashboard="${role}/dashboard"`, true)}</div>
      <section class="mt-12 border-t border-slate-200 pt-7">
        <div class="flex justify-between"><strong>Current progress</strong><span>${completed}/${total} complete</span></div>
        <div class="h-3 bg-slate-200 rounded mt-3 overflow-hidden"><div class="h-full bg-blue-700" style="width:${total ? (completed / total) * 100 : 0}%"></div></div>
        <p class="text-sm text-slate-500 mt-3">Phase status: ${esc(phase?.status || "closed")}. Values come from persisted submissions only.</p>
      </section>
    </section>`);
    qs("[data-start]").onclick = () => go(qs("[data-start]").dataset.start);
    qs("[data-dashboard]").onclick = () => go(qs("[data-dashboard]").dataset.dashboard);
  }

  async function initEmployeeWelcome() {
    const [phases, roleplays, career] = await Promise.all([
      api("/api/phases"),
      api("/api/employee/roleplays"),
      api("/api/employee/career"),
    ]);
    let learning = { courses: [] };
    try {
      learning = await api("/api/employee/learning");
    } catch (_) {
      learning = { courses: [] };
    }
    const phase = phases.phases.find((item) => item.phase === "employee");
    const completed = roleplays.roleplays.filter((item) => item.status === "completed").length;
    const total = roleplays.roleplays.length || 7;
    const latticeUnlocked = Boolean(roleplays.lattice_unlocked);
    const aspirationLocked = Boolean(career.choice);
    const coursesSelected = Array.isArray(learning.courses) && learning.courses.length > 0;
    const aspirationLabel = career.paths?.find((path) => path.id === career.choice?.aspiration_role)?.label
      || career.choice?.aspiration_role
      || "";

    const name = session.user.display_name || "Employee";
    const initials = name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase() || "").join("") || "MC";
    const nameNode = qs("[data-user-name]");
    const initialsNode = qs("[data-user-initials]");
    if (nameNode) nameNode.textContent = name;
    if (initialsNode) initialsNode.textContent = initials;

    const progressCount = qs("[data-progress-count]");
    const progressBar = qs("[data-progress-bar]");
    const phaseStatus = qs("[data-phase-status]");
    if (progressCount) progressCount.textContent = `${completed}/${total} complete`;
    if (progressBar) progressBar.style.width = `${total ? (completed / total) * 100 : 0}%`;
    if (phaseStatus) {
      phaseStatus.textContent = `Phase status: ${phase?.status || "closed"}. Values come from persisted submissions only.`;
    }

    const steps = [
      {
        key: "roleplays",
        done: completed === total && total > 0,
        copy: completed === total && total > 0
          ? `All ${total} competency assessments completed.`
          : `${completed} of ${total} competency assessments completed.`,
        action: "employee/roleplays",
        actionLabel: completed === total && total > 0 ? "Review Assessments" : "Open Assessments",
      },
      {
        key: "lattice",
        done: latticeUnlocked,
        copy: latticeUnlocked
          ? "Career Lattice unlocked. Explore eligible paths for your role and grade."
          : "Complete all seven assessments to unlock Career Lattice.",
        action: "employee/career",
        actionLabel: latticeUnlocked ? "Open Lattice" : "Locked until assessments complete",
      },
      {
        key: "aspiration",
        done: aspirationLocked,
        copy: aspirationLocked
          ? `Aspiration locked: ${aspirationLabel}. Admin reset required to change it.`
          : latticeUnlocked
            ? "Choose and confirm one career aspiration."
            : "Available after Career Lattice unlocks.",
        action: "employee/career",
        actionLabel: aspirationLocked ? "View Aspiration" : (latticeUnlocked ? "Choose Aspiration" : "Locked"),
      },
      {
        key: "learning",
        done: coursesSelected,
        copy: coursesSelected
          ? `${learning.courses.length} course${learning.courses.length === 1 ? "" : "s"} selected in your learning journey.`
          : aspirationLocked
            ? "Shop recommended courses and finalize your learning journey."
            : "Available after aspiration is locked.",
        action: coursesSelected ? "employee/learning" : "employee/courses",
        actionLabel: coursesSelected ? "Open Learning Journey" : (aspirationLocked ? "Open Courses" : "Locked"),
      },
    ];

    steps.forEach((step) => {
      const card = qs(`[data-step="${step.key}"]`);
      if (!card) return;
      const badge = qs("[data-step-badge]", card);
      const copy = qs("[data-step-copy]", card);
      const action = qs("[data-step-action]", card);
      if (badge) {
        badge.textContent = step.done ? "✓" : badge.textContent;
        badge.className = `w-16 h-16 rounded-full flex items-center justify-center font-bold text-xl mb-md border-4 border-white shadow-sm ${
          step.done ? "bg-primary text-white" : "bg-surface-container-highest text-on-surface-variant"
        }`;
      }
      if (copy) copy.textContent = step.copy;
      if (action) {
        action.textContent = step.actionLabel;
        action.dataset.stepAction = step.action;
        action.disabled = !step.done && ["lattice", "aspiration", "learning"].includes(step.key) && (
          (step.key === "lattice" && !latticeUnlocked && completed < total)
          || (step.key === "aspiration" && !latticeUnlocked)
          || (step.key === "learning" && !aspirationLocked)
        );
        action.classList.toggle("opacity-40", action.disabled);
        action.classList.toggle("cursor-not-allowed", action.disabled);
        action.onclick = () => {
          if (action.disabled) return;
          go(action.dataset.stepAction);
        };
      }
    });

    const continueTarget = !latticeUnlocked
      ? "employee/roleplays"
      : !aspirationLocked
        ? "employee/career"
        : coursesSelected
          ? "employee/learning"
          : "employee/courses";
    const continueButton = qs("[data-dashboard]");
    if (continueButton) {
      continueButton.dataset.dashboard = continueTarget;
      continueButton.textContent = !latticeUnlocked
        ? "Continue Assessments"
        : !aspirationLocked
          ? "Continue to Lattice"
          : coursesSelected
            ? "Open Learning Journey"
            : "Open Courses";
    }

    qsa("[data-route]").forEach((link) => {
      link.onclick = (event) => {
        event.preventDefault();
        go(link.dataset.route);
      };
    });
    qs("[data-logout]")?.addEventListener("click", logout);
    qs("[data-start]")?.addEventListener("click", () => go(qs("[data-start]").dataset.start));
    qs("[data-dashboard]")?.addEventListener("click", () => go(qs("[data-dashboard]").dataset.dashboard));
  }

  function employeeTable(rows, role) {
    return `<div class="overflow-x-auto bg-white border border-slate-200 rounded-xl"><table class="w-full min-w-[760px] text-sm">
      <thead class="bg-slate-50 text-left"><tr><th class="p-4">Employee</th><th class="p-4">Role</th><th class="p-4">ZM</th><th class="p-4">RD</th><th class="p-4">Assessments</th><th class="p-4">Action</th></tr></thead>
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
    const total = result.roleplays.length || 7;
    const completed = result.roleplays.filter((row) => row.status === "completed").length;
    const pct = total ? Math.round((completed / total) * 100) : 0;
    const icons = {
      Communication: "chat_bubble",
      "Stakeholder Management": "handshake",
      "Ownership & Accountability": "task_alt",
      "Team Management": "groups",
      "Executive Presence": "person_pin",
      "Consultative Selling": "local_offer",
      "Data Analytics": "bar_chart",
    };
    const banner = `<div class="bg-white border border-[#e7bdb9] rounded-xl p-6 mb-7 relative overflow-hidden flex flex-col md:flex-row md:items-center justify-between gap-6">
      <div class="absolute top-0 left-0 w-1.5 h-full bg-[#1464F4]"></div>
      <div class="flex flex-col md:flex-row md:items-center gap-6">
        <div><p class="uppercase tracking-widest text-xs font-bold text-[#5d3f3d] mb-1">Completed</p>
          <div class="flex items-baseline gap-2"><span class="text-4xl font-extrabold text-[#df162b] leading-none">${completed}/${total}</span><span class="text-lg font-bold text-[#5d3f3d]">Roles</span></div>
        </div>
        <div class="hidden md:block h-14 w-px bg-[#e7bdb9]"></div>
        <div>
          <div class="flex items-center gap-2 text-[#1464F4] font-bold">${result.lattice_unlocked
            ? '<span class="material-symbols-outlined" style="font-variation-settings:\'FILL\' 1">verified</span> Career lattice unlocked'
            : '<span class="material-symbols-outlined">lock</span> Career lattice locked'}</div>
          <p class="text-sm text-[#5d3f3d] mt-1">${result.lattice_unlocked
            ? "You have successfully achieved all required competency benchmarks for your current role grade."
            : "Complete all competency assessments to unlock Career Lattice."}</p>
        </div>
      </div>
      <div class="flex items-center gap-4">
        <div class="hidden sm:block h-2 w-40 bg-[#ffe1df] rounded-full overflow-hidden"><div class="h-full bg-[#1464F4]" style="width:${pct}%"></div></div>
        ${result.lattice_unlocked ? button("View Lattice", "data-career") : ""}
      </div>
    </div>`;
    const cards = result.roleplays.map((row) => {
      const done = row.status === "completed";
      return `<section class="bg-white border border-[#e7bdb9] rounded-xl p-5 flex flex-col min-h-[220px]">
        <div class="flex justify-between items-start mb-4">
          <div class="p-2 bg-[#fff0ef] text-[#df162b] rounded-lg"><span class="material-symbols-outlined">${icons[row.competency] || "assignment"}</span></div>
          <span class="px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wide ${done ? "bg-green-100 text-green-700" : "bg-[#ffe1df] text-[#5d3f3d]"}">${esc(row.status || "pending")}</span>
        </div>
        <h2 class="font-bold text-lg text-[#291716] mb-4">${esc(row.competency)}</h2>
        ${row.error ? `<p class="text-sm text-[#df162b] mb-3">${esc(row.error)}</p>` : ""}
        <div class="mt-auto flex flex-col gap-2">${row.link_available ? `<a class="w-full text-center px-3 py-2.5 border-2 border-[#1464F4] text-[#1464F4] rounded-lg font-bold text-sm hover:bg-[#1464F4]/5" href="${esc(row.roleplay_url)}" target="_blank" rel="noopener">Open Assessment</a>` : ""}
        <label class="w-full text-center px-3 py-2.5 bg-[#1464F4] text-white rounded-lg font-bold text-sm cursor-pointer hover:opacity-90">Upload Screenshot<input data-upload="${esc(row.competency)}" class="hidden" type="file" accept="image/png,image/jpeg,image/webp"></label></div>
      </section>`;
    }).join("");
    const proTip = `<aside class="md:col-span-2 xl:col-span-2 bg-[#df162b] text-white rounded-xl p-6 flex items-center relative overflow-hidden min-h-[220px]">
      <div class="relative z-10 w-full md:w-2/3">
        <span class="bg-white/20 px-2.5 py-1 rounded text-[10px] font-bold uppercase tracking-widest mb-3 inline-block">Pro Tip</span>
        <h3 class="text-xl font-extrabold mb-3">Master Advanced Data Viz</h3>
        <p class="text-sm leading-relaxed border border-white/40 rounded-lg p-3 bg-black/10">Achieve the 'Analytics Expert' badge by completing the next set of advanced quizes. Unlocks Senior Management paths.</p>
      </div>
      <div class="absolute right-0 top-0 h-full w-1/3 opacity-30 pointer-events-none bg-cover bg-center" style="background-image:url('https://lh3.googleusercontent.com/aida-public/AB6AXuAMRe1ecIWDJfz5HO1YY-dIqMoN8_BlifA0za3XOiU_V5xQICPcvOTFCW4P5pYo44f9jV-bOkg8WVH-jfkv6_DZOm8oueTbAoUMh2WrPHGRy4lJDRqAFcBhCG5otfA1MLdp0VtXV3eLoh3vy3mn5Yq1dllDN7K_awOmCGnJKGjycszgxoPiNXHInmhTIReAbooJG_dcio7rnCr56GgS_rZ82aPgk9t3EONe9SlZxGLSXV7tBN6U9ioYGA')"></div>
    </aside>`;
    render(`${pageHeader("Competency Assessments", "Only successfully assessed screenshots count as completed.")}
      ${banner}
      <div class="grid md:grid-cols-2 xl:grid-cols-3 gap-4">${cards}${proTip}</div>`);
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
    render(`${pageHeader("Career Lattice", "Available paths derive from your current role, grade, and completed assessments.")}
      ${!state.unlocked ? '<div class="bg-white border border-slate-200 rounded-xl p-8 text-center"><h2 class="text-xl font-bold">Career lattice locked</h2><p class="text-slate-500 mt-2">Complete all seven assessments first.</p><div class="mt-5">' + button("Open Assessments", "data-roleplays") + "</div></div>" : `
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

  function otherSourcesFor(competency) {
    const slug = String(competency || "Skill");
    return [
      { kind: "youtube", label: "YouTube", icon: "smart_display", iconClass: "text-[#df162b]", title: `${slug} Strategies 2024` },
      { kind: "case_study", label: "Case Study", icon: "description", iconClass: "text-[#1464F4]", title: `${slug} in Practice` },
      { kind: "webinar", label: "Internal Webinar", icon: "podcasts", iconClass: "text-[#005f81]", title: `${slug} Excellence Clinic` },
    ].map((item) => ({
      ...item,
      id: `other:${item.kind}:${competency}`,
      competency,
      source: "other",
    }));
  }

  function otherSourcesBlock(competency) {
    return `<div class="mt-5 pt-4 border-t border-[#e7bdb9]/60">
      <h3 class="text-sm font-bold text-[#291716] mb-3">Other Sources &amp; Case Studies</h3>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        ${otherSourcesFor(competency).map((item) => {
          const inBasket = basket.has(item.id);
          return `<div class="bg-[#fff8f7] p-3 rounded-lg border border-[#e7bdb9] flex flex-col gap-2 ${inBasket ? "ring-1 ring-[#1464F4]" : ""}">
            <div class="flex items-center gap-2"><span class="material-symbols-outlined ${item.iconClass} text-lg">${item.icon}</span><span class="text-[10px] font-bold uppercase text-[#5d3f3d]">${esc(item.label)}</span></div>
            <p class="text-sm font-bold text-[#291716] flex-grow">${esc(item.title)}</p>
            <button type="button" data-course="${esc(item.id)}" data-competency="${esc(competency)}" data-title="${esc(item.title)}" data-source="other" data-kind="${esc(item.kind)}"
              class="w-full px-3 py-2 rounded-lg font-bold text-xs ${inBasket ? "bg-[#5d3f3d] text-white cursor-not-allowed" : "bg-[#1464F4] text-white hover:opacity-90"}"
              ${inBasket ? "disabled" : ""}>${inBasket ? "Added" : "Add to Cart"}</button>
          </div>`;
        }).join("")}
      </div>
    </div>`;
  }

  function courseThumb(course) {
    return course.thumbnail
      ? `<img class="w-full h-full object-cover" alt="" src="${esc(course.thumbnail)}">`
      : `<div class="w-full h-full bg-gradient-to-br from-[#ffe1df] to-[#d5e3ff] flex items-center justify-center"><span class="material-symbols-outlined text-4xl text-[#df162b]">school</span></div>`;
  }

  function courseCard(course, competency) {
    const provider = course.provider || course.source_type || "LinkedIn Learning";
    const priceLabel = /mmt|internal/i.test(provider) ? "Internal Course" : "Free for Employee";
    const inBasket = basket.has(String(course.id));
    return `<article class="bg-white border border-[#e7bdb9] p-4 rounded-xl hover:shadow-md transition-shadow flex flex-col h-full">
      <div class="h-36 w-full mb-3 rounded-lg overflow-hidden relative bg-[#fff0ef]">${courseThumb(course)}
        <div class="absolute top-2 left-2 bg-white/95 px-2 py-1 rounded text-[10px] font-bold text-[#291716]">${esc(provider)}</div>
      </div>
      <h3 class="font-bold text-[#291716] mb-1 leading-tight">${esc(course.title)}</h3>
      <p class="text-sm text-[#5d3f3d] mb-3 flex-grow line-clamp-3">${esc(course.reason || course.description || course.duration || "")}</p>
      <div class="flex items-center justify-between gap-2 mt-auto">
        <span class="text-[#1464F4] font-bold text-sm">${esc(priceLabel)}</span>
        <button data-course="${esc(course.id)}" data-competency="${esc(competency)}" data-title="${esc(course.title)}" type="button"
          class="px-3 py-2 rounded-lg font-bold text-sm ${inBasket ? "bg-[#5d3f3d] text-white cursor-not-allowed" : "bg-[#1464F4] text-white hover:opacity-90"}"
          ${inBasket ? "disabled" : ""}>${inBasket ? "Added" : "Add to Cart"}</button>
      </div>
    </article>`;
  }

  async function initCourses() {
    const [result, learning] = await Promise.all([
      api("/api/employee/courses"),
      api("/api/employee/learning").catch(() => ({ courses: [], locked: false })),
    ]);
    const locked = Boolean(learning.locked || (learning.courses && learning.courses.length));
    if (locked) {
      const lockedCourses = learning.courses || [];
      const competencies = [...new Set(lockedCourses.map((course) => course.competency).filter(Boolean))];
      const existingOther = new Set(
        lockedCourses.filter((course) => course.source === "other" || String(course.id || "").startsWith("other:")).map((course) => String(course.id)),
      );
      basket = new Map();
      existingOther.forEach((id) => {
        const course = lockedCourses.find((item) => String(item.id) === id);
        if (course) {
          basket.set(id, {
            id,
            competency: course.competency,
            title: course.title,
            source: "other",
            kind: course.kind || "",
          });
        }
      });
      render(`<div class="mb-6">
          <h1 class="text-2xl md:text-3xl font-extrabold text-[#df162b]">Shop Your Courses</h1>
          <p class="text-[#5d3f3d] mt-1">LinkedIn courses are locked. You can still add Other Sources to your journey.</p>
        </div>
        <div class="bg-white border border-[#e7bdb9] rounded-xl p-5 mb-6 flex flex-wrap items-center justify-between gap-3">
          <div class="flex items-start gap-3">
            <span class="material-symbols-outlined text-[#df162b]" style="font-variation-settings:'FILL' 1">lock</span>
            <div>
              <h2 class="font-bold text-[#291716]">Journey locked</h2>
              <p class="text-sm text-[#5d3f3d] mt-1">${lockedCourses.filter((course) => course.source !== "other").length} LinkedIn course(s) locked. Add supplemental sources below, then save.</p>
            </div>
          </div>
          ${button("Open Learning Journey", "data-open-learning", true)}
        </div>
        <div class="grid lg:grid-cols-12 gap-6 items-start">
          <div class="lg:col-span-8 space-y-6">
            ${competencies.map((competency) => `<section>
              <h2 class="text-xl font-bold text-[#291716] mb-3">${esc(competency)}</h2>
              ${otherSourcesBlock(competency)}
            </section>`).join("")}
          </div>
          <aside class="lg:col-span-4 space-y-4 lg:sticky lg:top-20">
            <div class="bg-white border border-[#e7bdb9] rounded-xl p-5 shadow-sm">
              <div class="flex items-center justify-between mb-4">
                <h3 class="font-bold text-lg text-[#291716]">Other Sources</h3>
                <span class="font-bold text-[#df162b]" data-cart-count>0</span>
              </div>
              <div data-basket class="min-h-[80px] border-b border-[#e7bdb9] pb-4 mb-4 text-sm text-[#5d3f3d]">No other sources selected.</div>
              <button data-save-other disabled class="w-full bg-[#1464F4] text-white py-3 rounded-lg font-bold flex items-center justify-center gap-2 disabled:opacity-50">
                Save Other Sources
              </button>
            </div>
          </aside>
        </div>`);
      qs("[data-open-learning]")?.addEventListener("click", () => go("employee/learning"));
      qsa("[data-course]").forEach((control) => {
        control.onclick = () => {
          basket.set(control.dataset.course, {
            id: control.dataset.course,
            competency: control.dataset.competency,
            title: control.dataset.title,
            source: "other",
            kind: control.dataset.kind || "",
          });
          control.textContent = "Added";
          control.disabled = true;
          control.className = "w-full px-3 py-2 rounded-lg font-bold text-xs bg-[#5d3f3d] text-white cursor-not-allowed";
          renderOtherBasket();
        };
      });
      const renderOtherBasket = () => {
        const items = [...basket.values()].filter((item) => item.source === "other");
        const basketNode = qs("[data-basket]");
        const countNode = qs("[data-cart-count]");
        const saveBtn = qs("[data-save-other]");
        if (countNode) countNode.textContent = String(items.length);
        if (basketNode) {
          basketNode.innerHTML = items.length
            ? items.map((item) => `<div class="py-2 border-t border-[#e7bdb9] first:border-0"><strong class="block text-[#291716]">${esc(item.title)}</strong><p class="text-xs text-[#1464F4]">${esc(item.competency)}</p></div>`).join("")
            : `<p class="text-center py-6 text-[#5d3f3d]">No other sources selected.</p>`;
        }
        if (saveBtn) {
          const pending = items.filter((item) => !existingOther.has(item.id));
          saveBtn.disabled = pending.length === 0;
          saveBtn.onclick = async () => {
            try {
              await api("/api/employee/learning/checkout", {
                method: "POST",
                body: JSON.stringify({
                  course_ids: [],
                  other_sources: pending.map((item) => ({
                    id: item.id,
                    competency: item.competency,
                    title: item.title,
                    kind: item.kind,
                  })),
                }),
              });
              toast("Other sources saved to your learning journey.");
              go("employee/learning");
            } catch (error) {
              toast(error.message, "error");
            }
          };
        }
      };
      renderOtherBasket();
      return;
    }

    const gaps = result.target?.gaps || [];
    const entries = Object.entries(result.competencies || {});
    const required = entries.map(([competency]) => competency);
    const gapCount = gaps.length || entries.length;

    if (!entries.length) {
      const emptyMsg = result.target?.mode === "aspiration_required"
        ? "Choose a career aspiration to activate its precomputed courses."
        : !result.ready && gaps.length
          ? "Course recommendations are being prepared from the final RD profile."
          : "No proficiency gaps currently require courses.";
      render(`${pageHeader("Shop Your Courses", "AI-Powered Learning Recommendations based on your skill gaps.")}
        <div class="bg-white border border-[#e7bdb9] rounded-xl p-8 text-[#5d3f3d]">${esc(emptyMsg)}</div>`);
      return;
    }

    const sections = entries.map(([competency, courses]) => {
      return `<section class="mb-8">
        <div class="flex flex-wrap items-center gap-2 mb-4">
          <h2 class="text-xl font-bold text-[#291716]">${esc(competency)}</h2>
          <span class="bg-[#df162b] text-white text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">Gap Identified</span>
        </div>
        <div class="grid md:grid-cols-2 gap-4">${(courses || []).map((course) => courseCard(course, competency)).join("")}</div>
        ${otherSourcesBlock(competency)}
      </section>`;
    }).join("");

    render(`<div class="mb-6 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 class="text-2xl md:text-3xl font-extrabold text-[#df162b]">Shop Your Courses</h1>
          <p class="text-[#5d3f3d] mt-1">AI-Powered Learning Recommendations based on your skill gaps.</p>
        </div>
        <div class="bg-[#df162b] text-white px-4 py-2 rounded-lg flex items-center gap-2 text-sm font-bold">
          <span class="material-symbols-outlined text-base" style="font-variation-settings:'FILL' 1">bolt</span>
          Personalized for your final profile gaps
        </div>
      </div>
      <div class="grid lg:grid-cols-12 gap-6 items-start">
        <div class="lg:col-span-8 space-y-2">
          <div class="bg-[#ffdad6] text-[#93000a] p-4 rounded-xl flex items-start gap-3 border border-[#df162b]/40 mb-6">
            <span class="material-symbols-outlined">warning</span>
            <div>
              <p class="font-bold">Action Required</p>
              <p class="text-sm mt-1">You have ${gapCount} critical competency gap${gapCount === 1 ? "" : "s"}. You must add at least <strong>1 course per gap</strong> to finalize your learning journey.</p>
            </div>
          </div>
          ${sections}
        </div>
        <aside class="lg:col-span-4 space-y-4 lg:sticky lg:top-20">
          <div class="bg-white border border-[#e7bdb9] rounded-xl p-5 shadow-sm">
            <div class="flex items-center justify-between mb-4">
              <h3 class="font-bold text-lg text-[#291716]">Your Selection</h3>
              <div class="flex items-center gap-1 text-[#df162b]"><span class="material-symbols-outlined" style="font-variation-settings:'FILL' 1">shopping_cart</span><span class="font-bold" data-cart-count>0</span></div>
            </div>
            <div data-basket class="min-h-[80px] border-b border-[#e7bdb9] pb-4 mb-4 text-sm text-[#5d3f3d]">No courses selected yet.</div>
            <div class="space-y-2 mb-4 text-sm">
              <div class="flex justify-between"><span class="text-[#5d3f3d]">Subtotal:</span><span class="font-bold">₹0.00</span></div>
              <div class="flex justify-between"><span class="text-[#5d3f3d]">Employee Credits Applied:</span><span class="text-[#1464F4] font-bold">-₹100%</span></div>
              <div class="flex justify-between font-bold border-t border-[#e7bdb9] pt-2"><span>Total Due:</span><span class="text-[#df162b]">₹0.00</span></div>
            </div>
            <button data-checkout disabled class="w-full bg-[#1464F4] text-white py-3 rounded-lg font-bold flex items-center justify-center gap-2 disabled:opacity-50">
              <span class="material-symbols-outlined text-base">lock</span> Checkout &amp; Lock Journey
            </button>
            <p class="text-[11px] text-[#5d3f3d] mt-3 text-center">By clicking Checkout, you commit to completing these courses within the next 90 days as part of your performance goals.</p>
          </div>
          <div class="bg-[#fff8f7] p-4 rounded-xl border border-[#e7bdb9]">
            <h4 class="text-xs font-bold uppercase tracking-wide text-[#291716] mb-3">Requirement Tracker</h4>
            <div data-requirements class="space-y-2"></div>
          </div>
        </aside>
      </div>`);

    qsa("[data-course]").forEach((control) => {
      control.onclick = () => {
        basket.set(control.dataset.course, {
          id: control.dataset.course,
          competency: control.dataset.competency,
          title: control.dataset.title,
          source: control.dataset.source || "linkedin",
          kind: control.dataset.kind || "",
        });
        control.textContent = "Added";
        control.disabled = true;
        control.className = control.className.includes("text-xs")
          ? "w-full px-3 py-2 rounded-lg font-bold text-xs bg-[#5d3f3d] text-white cursor-not-allowed"
          : "px-3 py-2 rounded-lg font-bold text-sm bg-[#5d3f3d] text-white cursor-not-allowed";
        renderBasket(required);
      };
    });
    renderBasket(required);
  }

  function renderBasket(required) {
    const basketNode = qs("[data-basket]");
    const countNode = qs("[data-cart-count]");
    const reqNode = qs("[data-requirements]");
    const checkout = qs("[data-checkout]");
    if (!basketNode || !checkout) return;

    const items = [...basket.values()];
    if (countNode) countNode.textContent = String(items.length);
    basketNode.innerHTML = items.length
      ? items.map((item) => `<div class="flex justify-between items-start gap-2 py-2 border-t border-[#e7bdb9] first:border-0">
          <div><strong class="block text-[#291716]">${esc(item.title)}</strong><p class="text-xs text-[#1464F4]">${esc(item.competency)}${item.source === "other" ? " · Other source" : ""}</p></div>
          <button type="button" data-remove="${esc(item.id)}" class="text-[#df162b]"><span class="material-symbols-outlined text-base">delete</span></button>
        </div>`).join("")
      : `<p class="text-center py-6 text-[#5d3f3d]">No courses selected yet.</p>`;

    // Gap requirements: LinkedIn/catalog courses only — other sources are supplemental.
    const covered = new Set(items.filter((item) => item.source !== "other").map((item) => item.competency));
    if (reqNode) {
      reqNode.innerHTML = required.map((competency) => {
        const done = covered.has(competency);
        return `<div class="flex items-center gap-2">
          <span class="material-symbols-outlined text-sm ${done ? "text-green-600" : "text-[#5d3f3d]"}">${done ? "check_circle" : "radio_button_unchecked"}</span>
          <span class="text-sm ${done ? "text-[#291716] font-semibold" : "text-[#5d3f3d]"}">1 ${esc(competency)} course</span>
        </div>`;
      }).join("");
    }

    qsa("[data-remove]", basketNode).forEach((control) => {
      control.onclick = () => {
        basket.delete(control.dataset.remove);
        initCourses();
      };
    });

    checkout.disabled = required.some((competency) => !covered.has(competency));
    checkout.onclick = async () => {
      try {
        const courseIds = items.filter((item) => item.source !== "other").map((item) => item.id);
        const otherSources = items.filter((item) => item.source === "other").map((item) => ({
          id: item.id,
          competency: item.competency,
          title: item.title,
          kind: item.kind,
        }));
        await api("/api/employee/learning/checkout", {
          method: "POST",
          body: JSON.stringify({ course_ids: courseIds, other_sources: otherSources }),
        });
        basket = new Map();
        go("employee/learning");
      } catch (error) {
        toast(error.message, "error");
      }
    };
  }

  async function initLearning() {
    const result = await api("/api/employee/learning");
    const courses = result.courses || [];
    if (!courses.length) {
      render(`<div class="mb-6">
          <h1 class="text-2xl md:text-3xl font-extrabold text-[#df162b]">Your Learning Journey</h1>
          <p class="text-[#5d3f3d] mt-1">Track your progress across your identified competency gaps and unlock new career opportunities.</p>
        </div>
        <div class="bg-white border border-[#e7bdb9] rounded-xl p-8 text-center">
          <span class="material-symbols-outlined text-5xl text-[#e7bdb9]">menu_book</span>
          <h2 class="text-xl font-bold text-[#291716] mt-3">No courses locked yet</h2>
          <p class="text-sm text-[#5d3f3d] mt-2">Shop recommended courses and checkout to lock your learning journey.</p>
          <div class="mt-5">${button("Open Course Shop", "data-open-courses")}</div>
        </div>`);
      qs("[data-open-courses]")?.addEventListener("click", () => go("employee/courses"));
      return;
    }

    const gaps = result.target?.gaps || [];
    const gapByCompetency = Object.fromEntries(gaps.map((gap) => [gap.competency, gap]));
    const completed = Number(result.progress?.completed ?? courses.filter((course) => course.status === "completed").length);
    const total = Number(result.progress?.total ?? courses.length);
    const pct = Number(result.progress?.percentage ?? (total ? Math.round((completed / total) * 100) : 0));
    const hours = Number(result.linkedin?.learning_hours || 0);
    const circumference = 364.4;
    const offset = circumference - (circumference * pct) / 100;

    const groups = courses.reduce((output, course) => {
      const competency = course.competency || "General";
      (output[competency] ||= []).push(course);
      return output;
    }, {});

    const focusGap = Object.keys(groups).find((name) => {
      return groups[name].some((course) => course.status !== "completed");
    }) || Object.keys(groups)[0];

    const journeyCards = (list) => list.map((course) => {
      const status = course.status || "not_started";
      const progressPct = Math.max(0, Math.min(100, Number(course.progress_pct || 0)));
      const courseId = course.id || course.course_id;
      const provider = course.provider || (course.source === "other" ? "Other source" : "LinkedIn Learning");
      const isOther = course.source === "other" || String(courseId || "").startsWith("other:");
      const isMmt = !isOther && /mmt|academy|internal/i.test(provider);
      const duration = course.duration || "—";
      const badge = status === "completed"
        ? '<span class="px-2 py-0.5 bg-green-100 text-green-800 rounded-full text-[10px] font-bold uppercase whitespace-nowrap">Completed</span>'
        : status === "in_progress"
          ? '<span class="px-2 py-0.5 bg-[#d5e3ff] text-[#004786] rounded-full text-[10px] font-bold uppercase whitespace-nowrap">In Progress</span>'
          : '<span class="px-2 py-0.5 bg-[#ffe1df] text-[#5d3f3d] rounded-full text-[10px] font-bold uppercase whitespace-nowrap">Not Started</span>';
      const footer = status === "completed"
        ? `<span class="text-[#5d3f3d] text-sm flex items-center gap-1"><span class="material-symbols-outlined text-base">check_circle</span> Completed</span>`
        : status === "in_progress"
          ? (progressPct > 0
            ? `<div class="flex-1 min-w-0"><div class="w-full bg-[#ffe1df] h-1.5 rounded-full overflow-hidden mb-1"><div class="bg-[#1464F4] h-full rounded-full" style="width:${progressPct}%"></div></div><span class="text-[#5d3f3d] text-sm">${progressPct}% through</span></div>`
            : `<span class="text-[#5d3f3d] text-sm">In progress</span>`)
          : `<span class="text-[#5d3f3d] text-sm">Available</span>`;
      const actions = status === "completed"
        ? (course.url
          ? `<a href="${esc(course.url)}" target="_blank" rel="noopener" class="px-4 py-1.5 border border-[#df162b] text-[#df162b] rounded-lg font-bold text-sm hover:bg-[#df162b]/5">Review</a>`
          : `<span class="text-sm text-[#5d3f3d]">Done</span>`)
        : `<div class="flex flex-wrap gap-2 justify-end">
            <button type="button" data-progress-action="launch" data-course-id="${esc(courseId)}" data-url="${esc(course.url || "")}" class="px-4 py-1.5 bg-[#df162b] text-white rounded-lg font-bold text-sm hover:opacity-90">${status === "in_progress" ? "Continue" : "Launch"}</button>
            ${status === "in_progress" ? `<button type="button" data-progress-action="complete" data-course-id="${esc(courseId)}" class="px-4 py-1.5 border border-[#1464F4] text-[#1464F4] rounded-lg font-bold text-sm">Mark Complete</button>` : ""}
          </div>`;
      return `<article class="bg-white rounded-xl border border-[#e7bdb9] overflow-hidden hover:shadow-md transition-all">
        <div class="h-36 w-full bg-[#fff0ef] relative overflow-hidden">${courseThumb(course)}
          <div class="absolute top-2 right-2 bg-white/90 px-2 py-1 rounded-lg text-[10px] font-bold text-[#291716] flex items-center gap-1">
            <span class="material-symbols-outlined text-sm">timer</span> ${esc(duration)}
          </div>
          <div class="absolute bottom-2 left-2 ${isOther ? "bg-[#5d3f3d]" : isMmt ? "bg-[#df162b]" : "bg-[#0077b5]"} text-white px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider">${esc(isOther ? (course.kind || provider) : provider)}</div>
        </div>
        <div class="p-4">
          <div class="flex justify-between items-start gap-3 mb-3">
            <h4 class="font-bold text-[#291716] leading-tight">${esc(course.title)}</h4>
            ${badge}
          </div>
          <div class="flex items-end justify-between gap-3 mt-4">${footer}${actions}</div>
        </div>
      </article>`;
    }).join("");

    const sections = Object.entries(groups).map(([competency, list]) => {
      const gap = gapByCompetency[competency];
      const gapLabel = gap ? `Gap: ${gap.current} to ${gap.target}` : "Selected for your path";
      return `<div class="mb-10">
        <div class="flex flex-wrap items-end justify-between gap-3 mb-5 border-b border-[#e7bdb9] pb-3">
          <div>
            <h2 class="text-lg font-bold text-[#291716] flex items-center gap-2">
              <span class="material-symbols-outlined text-[#1464F4]" style="font-variation-settings:'FILL' 1">insights</span>
              ${esc(competency)}
            </h2>
            <span class="inline-block mt-2 px-2 py-1 bg-[#ffe1df] text-[#930015] rounded-full text-[10px] font-bold">${esc(gapLabel)}</span>
          </div>
          <span class="text-sm text-[#5d3f3d]">${list.length} Course${list.length === 1 ? "" : "s"} Total</span>
        </div>
        <div class="grid md:grid-cols-2 gap-5">${journeyCards(list)}</div>
      </div>`;
    }).join("");

    render(`<section class="mb-8">
        <h1 class="text-2xl md:text-3xl font-extrabold text-[#df162b] mb-1">Your Learning Journey</h1>
        <p class="text-[#5d3f3d]">Track your progress across your identified competency gaps and unlock new career opportunities.</p>
      </section>
      <section class="mb-8">
        <div class="bg-white rounded-xl border border-[#e7bdb9] p-6 flex flex-col md:flex-row items-center gap-6">
          <div class="relative w-32 h-32 flex items-center justify-center shrink-0">
            <svg class="w-full h-full transform -rotate-90" viewBox="0 0 128 128">
              <circle cx="64" cy="64" r="58" fill="transparent" stroke="#ffe1df" stroke-width="8"></circle>
              <circle cx="64" cy="64" r="58" fill="transparent" stroke="#df162b" stroke-width="10" stroke-linecap="round"
                stroke-dasharray="${circumference}" stroke-dashoffset="${offset}"></circle>
            </svg>
            <div class="absolute inset-0 flex flex-col items-center justify-center">
              <span class="text-2xl font-extrabold text-[#291716]">${pct}%</span>
              <span class="text-[10px] uppercase font-bold text-[#5d3f3d]">Complete</span>
            </div>
          </div>
          <div class="flex-1 text-center md:text-left">
            <h3 class="text-xl font-bold text-[#291716] mb-2">Current Progress: ${completed}/${total} Courses</h3>
            <p class="text-sm text-[#5d3f3d] mb-4">${pct === 100
              ? "All locked courses are complete. Keep applying what you learned on the job."
              : `Launch courses to track progress. Focus next on <span class="font-bold text-[#291716]">${esc(focusGap)}</span>.`}</p>
            <div class="w-full bg-[#ffe1df] h-3 rounded-full overflow-hidden">
              <div class="bg-[#df162b] h-full rounded-full" style="width:${pct}%"></div>
            </div>
            <p class="text-xs text-[#5d3f3d] mt-2">Progress from saved course status · LinkedIn hours from admin sync</p>
          </div>
          <div class="bg-[#fff0ef] p-4 rounded-lg border border-[#e7bdb9]/50 text-center min-w-[110px]">
            <div class="text-[#df162b] font-bold text-xl">${hours.toFixed(1)}h</div>
            <div class="text-xs font-bold uppercase text-[#5d3f3d]">Learning Hours</div>
          </div>
        </div>
      </section>
      <section>${sections}</section>
      <p class="text-center text-xs text-[#926e6c] mt-8">Journey locked after checkout · Admin reset required to change selections</p>`);

    qsa("[data-progress-action]").forEach((control) => {
      control.onclick = async () => {
        try {
          await api("/api/employee/learning/progress", {
            method: "POST",
            body: JSON.stringify({ course_id: control.dataset.courseId, action: control.dataset.progressAction }),
          });
          if (control.dataset.progressAction === "launch" && control.dataset.url) {
            window.open(control.dataset.url, "_blank", "noopener");
          }
          await initLearning();
        } catch (error) {
          toast(error.message, "error");
        }
      };
    });
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
        ${metric("Assessments complete", result.metrics.roleplays_completed)}
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
      qs("[data-table]").innerHTML = `<div class="overflow-x-auto bg-white border rounded-xl"><table class="w-full min-w-[1000px] text-sm"><thead class="bg-slate-50 text-left"><tr><th class="p-4">Employee</th><th class="p-4">Role</th><th class="p-4">ZM</th><th class="p-4">RD</th><th class="p-4">Assessment status</th><th class="p-4">Assessments</th><th class="p-4">Aspiration</th><th class="p-4">Courses</th><th class="p-4">Actions</th></tr></thead><tbody>
        ${filtered.map((row) => `<tr class="border-t"><td class="p-4"><strong>${esc(row.name)}</strong><div class="text-xs">${esc(row.employee_code)}</div></td><td class="p-4">${esc(row.designation)}<div class="text-xs">${esc(row.grade)}</div></td><td class="p-4">${esc(row.zm_name)}</td><td class="p-4">${esc(row.rd_name)}</td><td class="p-4">${statusChip(row.zm_status)} ${statusChip(row.rd_status)}</td><td class="p-4">${row.roleplays_completed}/${row.roleplays_total}</td><td class="p-4">${esc(row.aspiration?.aspiration_role || "Not selected")}</td><td class="p-4">${row.learning_locked ? statusChip("locked") : statusChip("open")}</td><td class="p-4 flex flex-wrap gap-2">${button("Profile", `data-profile="${row.employee_code}"`, true)}${button("Assessments", `data-roleplay-review="${row.employee_code}"`, true)}${row.learning_locked ? button("Reset Courses", `data-reset-courses="${row.employee_code}"`, true) : ""}${row.aspiration ? button("Reset Aspiration", `data-reset="${row.employee_code}"`, true) : ""}</td></tr>`).join("") || empty("No matching employees.", 9)}</tbody></table></div>`;
      qsa("[data-profile]").forEach((control) => { control.onclick = () => openFinalProfile(control.dataset.profile); });
      qsa("[data-roleplay-review]").forEach((control) => {
        control.onclick = () => openAdminRoleplays(control.dataset.roleplayReview);
      });
      qsa("[data-reset-courses]").forEach((control) => {
        control.onclick = async () => {
          if (!confirm("Reset this employee's Shop Your Courses / learning journey? They can select courses again. Aspiration stays locked.")) return;
          try {
            await api("/api/admin/learning/reset", { method: "POST", body: JSON.stringify({ employee_code: control.dataset.resetCourses }) });
            toast("Course shop unlocked for employee.");
            await initAdminEmployees();
          } catch (error) {
            toast(error.message, "error");
          }
        };
      });
      qsa("[data-reset]").forEach((control) => {
        control.onclick = async () => {
          if (!confirm("Reset this employee's aspiration and learning selections?")) return;
          try {
            await api("/api/admin/career/reset", { method: "POST", body: JSON.stringify({ employee_code: control.dataset.reset }) });
            toast("Aspiration and courses reset.");
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
        <div class="flex justify-between gap-4"><div><h2 class="text-2xl font-bold">${esc(result.employee.name)} · Assessments</h2><p class="text-sm text-slate-500">${esc(result.employee.employee_code)} · Admin-only assessment evidence</p></div><button data-close class="material-symbols-outlined">close</button></div>
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
            preview.innerHTML = `<div class="border rounded-xl p-4 bg-slate-50"><div class="flex justify-between gap-3 mb-3"><strong>${esc(screenshot.competency)} screenshot</strong><button data-hide-preview class="material-symbols-outlined">close</button></div><img class="max-h-[65vh] mx-auto rounded border" src="data:${esc(screenshot.content_type)};base64,${screenshot.content_base64}" alt="${esc(screenshot.competency)} assessment screenshot"></div>`;
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
    render(`${pageHeader("Confidence Scores", "Calculated only when ZM, RD, and all seven AI assessment ratings exist.", `<select data-employee-select class="border rounded-lg px-3 py-2 bg-white">${options}</select>`)}
      <div class="mb-7">${metric("Overall confidence", result.score == null ? "Pending" : `${result.score}%`, result.band || `${result.completed || 0}/${result.total || 7} competencies complete`)}</div>
      <div class="overflow-x-auto bg-white border rounded-xl"><table class="w-full min-w-[850px] text-sm"><thead class="bg-slate-50 text-left"><tr><th class="p-4">Competency</th><th class="p-4">RD</th><th class="p-4">ZM</th><th class="p-4">AI</th><th class="p-4">ZM agreement</th><th class="p-4">AI agreement</th><th class="p-4">Confidence</th></tr></thead><tbody>
      ${(result.competencies || []).map((row) => `<tr class="border-t"><td class="p-4 font-bold">${esc(row.competency)}</td><td class="p-4">${esc(row.rd_rating || "Pending")}</td><td class="p-4">${esc(row.zm_rating || "Pending")}</td><td class="p-4">${esc(row.ai_rating || "Pending")}</td><td class="p-4">${row.zm_agreement == null ? "—" : `${row.zm_agreement}%`}</td><td class="p-4">${row.ai_agreement == null ? "—" : `${row.ai_agreement}%`}</td><td class="p-4">${row.confidence == null ? "Pending" : `${row.confidence}%`}</td></tr>`).join("") || empty("Confidence pending. Required assessment inputs are incomplete.", 7)}</tbody></table></div>`);
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
    const preserveBody = page === "employee/welcome";
    if (!(await authenticate({ skipShell: preserveBody }))) return;
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
      if (preserveBody) toast(error.message || "Unable to load page.", "error");
      else render(`${pageHeader("Unable to load page")}<div class="bg-white border border-red-200 rounded-xl p-6 text-red-800">${esc(error.message || "Unknown error")}</div>`);
    }
  }

  boot();
})();
