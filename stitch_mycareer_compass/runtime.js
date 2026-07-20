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
      ["admin/leaderboard", "Leaderboard", "leaderboard"],
      ["admin/confidence", "Confidence Scores", "verified"],
      ["admin/audit", "Agent Audit", "manage_search"],
    ],
    zm: [
      ["zm/welcome", "Home", "home"],
      ["zm/dashboard", "Dashboard", "dashboard"],
      ["zm/leaderboard", "Leaderboard", "leaderboard"],
    ],
    rd: [
      ["rd/welcome", "Home", "home"],
      ["rd/dashboard", "Dashboard", "dashboard"],
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

  function render(content, options = {}) {
    const main = qs("#mc-main");
    if (!main) return;
    main.innerHTML = options.flush
      ? content
      : `<div class="max-w-[1440px] mx-auto p-5 md:p-8">${content}</div>`;
  }

  function loading() {
    render('<div class="py-24 text-center text-slate-500">Loading current data…</div>');
  }

  const mmtTheme = (role = session.user?.role) =>
    role === "employee" || role === "zm" || role === "rd" || role === "admin";

  function pageHeader(title, description = "", actions = "") {
    const titleClass = mmtTheme() ? "text-[#df162b]" : "text-blue-800";
    return `<div class="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-7">
      <div><h1 class="text-2xl md:text-3xl font-extrabold ${titleClass}">${esc(title)}</h1>${description ? `<p class="text-slate-600 mt-1">${esc(description)}</p>` : ""}</div>
      ${actions ? `<div class="flex flex-wrap gap-2">${actions}</div>` : ""}
    </div>`;
  }

  function button(label, attributes = "", secondary = false) {
    const primary = mmtTheme()
      ? (secondary ? "border border-[#1464F4] text-[#1464F4] bg-white" : "bg-[#df162b] text-white")
      : (secondary ? "border border-blue-700 text-blue-700 bg-white" : "bg-blue-700 text-white");
    return `<button ${attributes} class="px-4 py-2.5 rounded-lg font-bold text-sm ${primary} disabled:opacity-40">${esc(label)}</button>`;
  }

  // --- Common shell components (shared across all authenticated pages) ---
  function userInitials(user) {
    const name = String(user?.display_name || "").trim();
    return name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase() || "").join("") || "MC";
  }

  function profileDesignation(user) {
    const raw = String(user?.designation || "").trim();
    if (!raw) return "";
    // Backend already maps KAM track → "KAM"; keep alias for older sessions / raw Darwin titles.
    if (/^kam$/i.test(raw)) return "KAM";
    if (/key\s*account/i.test(raw) || /account\s*(&|and)\s*(client|key)/i.test(raw)) return "KAM";
    return raw;
  }

  function commonBrand(mmt, homeRoute) {
    return `<a data-route="${homeRoute}" href="/app/${homeRoute}" class="flex items-center gap-2 min-w-0">
      <img src="/stitch/common/my-logo.png" alt="my" class="h-10 w-10 rounded-lg object-cover shrink-0 shadow-sm" width="40" height="40"/>
      <strong class="block ${mmt ? "text-[#df162b]" : "text-blue-800"} leading-none text-xl md:text-2xl font-extrabold tracking-tight truncate">Career Compass</strong>
    </a>`;
  }

  function avatarStorageKey(user = session.user) {
    return `mycareer_avatar_${user?.role || "unknown"}_${user?.login_id || "anon"}`;
  }

  function ackStorageKey(user = session.user) {
    return `mycareer_ack_${user?.role || "unknown"}_${user?.login_id || "anon"}`;
  }

  function loadAvatar(user = session.user) {
    try {
      return localStorage.getItem(avatarStorageKey(user)) || "";
    } catch (_) {
      return "";
    }
  }

  function saveAvatar(dataUrl, user = session.user) {
    localStorage.setItem(avatarStorageKey(user), dataUrl);
  }

  function hasDisclaimerAck(user = session.user) {
    return localStorage.getItem(ackStorageKey(user)) === "1";
  }

  function setDisclaimerAck(user = session.user) {
    localStorage.setItem(ackStorageKey(user), "1");
  }

  function avatarButtonHtml(user, mmt) {
    const photo = loadAvatar(user);
    const ring = mmt ? "ring-[#e7bdb9] hover:ring-[#df162b]" : "ring-slate-200 hover:ring-blue-600";
    const bg = mmt ? "bg-[#005cab]" : "bg-blue-700";
    if (photo) {
      return `<button type="button" data-open-account class="w-9 h-9 rounded-full overflow-hidden shrink-0 ring-2 ${ring} transition" title="Account settings" aria-label="Account settings">
        <img src="${photo}" alt="" class="w-full h-full object-cover"/>
      </button>`;
    }
    return `<button type="button" data-open-account class="w-9 h-9 rounded-full ${bg} text-white grid place-items-center font-bold text-sm shrink-0 ring-2 ${ring} transition" title="Account settings" aria-label="Account settings">${esc(userInitials(user))}</button>`;
  }

  function commonProfile(user, mmt) {
    const designation = profileDesignation(user);
    return `<div class="flex items-center gap-3 min-w-0">
      <div class="text-right min-w-0">
        <strong class="block text-sm leading-tight truncate">${esc(user.display_name)}</strong>
        ${designation ? `<span class="block text-xs text-slate-500 mt-0.5 leading-tight truncate normal-case tracking-normal">${esc(designation)}</span>` : ""}
      </div>
      ${avatarButtonHtml(user, mmt)}
      <button data-logout type="button" class="text-sm font-bold shrink-0 ${mmt ? "text-[#df162b]" : "text-blue-700"}">Sign out</button>
    </div>`;
  }

  function closeOverlay(id) {
    qs(`#${id}`)?.remove();
  }

  function openAccountModal() {
    closeOverlay("mc-account-modal");
    const user = session.user;
    const mmt = mmtTheme(user.role);
    const photo = loadAvatar(user);
    const primary = mmt ? "bg-[#df162b] text-white" : "bg-blue-700 text-white";
    const border = mmt ? "border-[#e7bdb9]" : "border-slate-200";
    const node = document.createElement("div");
    node.id = "mc-account-modal";
    node.className = "fixed inset-0 z-[80] bg-black/40 grid place-items-center p-4";
    node.innerHTML = `<div class="bg-white rounded-xl shadow-2xl w-full max-w-md border ${border} overflow-hidden" role="dialog" aria-modal="true" aria-labelledby="mc-account-title">
      <div class="px-5 py-4 border-b ${border} flex items-center justify-between">
        <h2 id="mc-account-title" class="text-lg font-extrabold text-[#291716]">Account settings</h2>
        <button type="button" data-close-account class="text-[#5d3f3d] hover:text-[#df162b]"><span class="material-symbols-outlined">close</span></button>
      </div>
      <div class="p-5 space-y-5">
        <section>
          <h3 class="text-sm font-bold text-[#291716] mb-3">Profile photo</h3>
          <div class="flex items-center gap-4">
            <div data-account-preview class="w-16 h-16 rounded-full overflow-hidden ${mmt ? "bg-[#005cab]" : "bg-blue-700"} text-white grid place-items-center font-bold text-lg shrink-0">
              ${photo ? `<img src="${photo}" alt="" class="w-full h-full object-cover"/>` : esc(userInitials(user))}
            </div>
            <div class="min-w-0">
              <input type="file" data-avatar-file accept="image/jpeg,image/png,.jpg,.jpeg,.png" class="block w-full text-xs text-[#5d3f3d]"/>
              <p class="text-[11px] text-[#5d3f3d] mt-1">JPG or PNG only. Stored on this device.</p>
            </div>
          </div>
        </section>
        <button type="button" data-open-password class="w-full ${primary} rounded-lg px-4 py-2.5 text-sm font-bold">Change password</button>
      </div>
    </div>`;
    document.body.appendChild(node);
    const dismiss = () => closeOverlay("mc-account-modal");
    node.addEventListener("click", (event) => { if (event.target === node) dismiss(); });
    qs("[data-close-account]", node).onclick = dismiss;
    qs("[data-open-password]", node).onclick = () => openPasswordModal();
    qs("[data-avatar-file]", node).onchange = (event) => {
      const file = event.target.files?.[0];
      if (!file) return;
      if (!["image/jpeg", "image/png"].includes(file.type)) {
        toast("Use a JPG or PNG image.", "error");
        event.target.value = "";
        return;
      }
      if (file.size > 1024 * 1024) {
        toast("Image must be 1MB or smaller.", "error");
        event.target.value = "";
        return;
      }
      const reader = new FileReader();
      reader.onload = () => {
        const dataUrl = String(reader.result || "");
        saveAvatar(dataUrl, user);
        const preview = qs("[data-account-preview]", node);
        preview.innerHTML = `<img src="${dataUrl}" alt="" class="w-full h-full object-cover"/>`;
        const headerBtn = qs("[data-open-account]");
        if (headerBtn) {
          headerBtn.outerHTML = avatarButtonHtml(user, mmt);
          qs("[data-open-account]").onclick = openAccountModal;
        }
        toast("Profile photo updated.");
      };
      reader.readAsDataURL(file);
    };
  }

  function openPasswordModal() {
    closeOverlay("mc-password-modal");
    const mmt = mmtTheme(session.user?.role);
    const primary = mmt ? "bg-[#df162b] text-white" : "bg-blue-700 text-white";
    const border = mmt ? "border-[#e7bdb9]" : "border-slate-200";
    const bg = mmt ? "bg-[#fff8f7]" : "bg-slate-50";
    const node = document.createElement("div");
    node.id = "mc-password-modal";
    node.className = "fixed inset-0 z-[90] bg-black/40 grid place-items-center p-4";
    node.innerHTML = `<div class="bg-white rounded-xl shadow-2xl w-full max-w-sm border ${border} overflow-hidden" role="dialog" aria-modal="true" aria-labelledby="mc-password-title">
      <div class="px-5 py-4 border-b ${border} ${bg} flex items-center justify-between">
        <h2 id="mc-password-title" class="text-lg font-extrabold text-[#291716]">Change password</h2>
        <button type="button" data-close-password class="text-[#5d3f3d] hover:text-[#df162b]"><span class="material-symbols-outlined">close</span></button>
      </div>
      <form data-password-form class="p-5 space-y-3">
        <label class="block text-xs font-semibold text-[#5d3f3d]">Current password
          <input name="current" type="password" required autocomplete="current-password" class="mt-1 w-full border ${border} rounded-lg px-3 py-2 text-sm bg-white"/>
        </label>
        <label class="block text-xs font-semibold text-[#5d3f3d]">New password
          <input name="next" type="password" required autocomplete="new-password" class="mt-1 w-full border ${border} rounded-lg px-3 py-2 text-sm bg-white"/>
        </label>
        <label class="block text-xs font-semibold text-[#5d3f3d]">Confirm new password
          <input name="confirm" type="password" required autocomplete="new-password" class="mt-1 w-full border ${border} rounded-lg px-3 py-2 text-sm bg-white"/>
        </label>
        <button type="submit" class="w-full ${primary} rounded-lg px-4 py-2.5 text-sm font-bold mt-2">Update password</button>
      </form>
    </div>`;
    document.body.appendChild(node);
    const dismiss = () => closeOverlay("mc-password-modal");
    node.addEventListener("click", (event) => { if (event.target === node) dismiss(); });
    qs("[data-close-password]", node).onclick = dismiss;
    qs("[data-password-form]", node).onsubmit = async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      const current = form.current.value;
      const next = form.next.value;
      const confirm = form.confirm.value;
      if (next !== confirm) {
        toast("New password and confirm do not match.", "error");
        return;
      }
      try {
        await api("/api/auth/password", {
          method: "POST",
          body: JSON.stringify({ current_password: current, new_password: next }),
        });
        form.reset();
        toast("Password updated.");
        dismiss();
      } catch (error) {
        toast(error.message, "error");
      }
    };
  }

  function openDisclaimerModal(onAgree) {
    closeOverlay("mc-disclaimer-modal");
    const node = document.createElement("div");
    node.id = "mc-disclaimer-modal";
    node.className = "fixed inset-0 z-[80] bg-black/40 grid place-items-center p-4";
    node.innerHTML = `<div class="bg-white rounded-xl shadow-2xl w-full max-w-lg border border-[#e7bdb9] overflow-hidden max-h-[90vh] flex flex-col" role="dialog" aria-modal="true" aria-labelledby="mc-ack-title">
      <div class="px-5 py-4 border-b border-[#e7bdb9] flex items-center justify-between shrink-0">
        <h2 id="mc-ack-title" class="text-lg font-extrabold text-[#291716]">Acknowledgement</h2>
        <button type="button" data-close-ack class="text-[#5d3f3d] hover:text-[#df162b]"><span class="material-symbols-outlined">close</span></button>
      </div>
      <div class="p-5 overflow-y-auto text-sm text-[#291716] space-y-3 leading-relaxed">
        <p class="font-semibold">Before you continue, please review and acknowledge the following:</p>
        <p>This Career Journey Portal is designed to support your professional growth through personalized learning, skill development, and career planning. The learning journeys and recommendations provided are intended to help you build capabilities and prepare for future career opportunities.</p>
        <p>Completion of assessments, learning journeys, or other development activities demonstrates your commitment to growth and may enhance your readiness for future roles. However, participation in or completion of these activities does not guarantee promotion, role change, salary revision, or any specific career outcome.</p>
        <p>Career progression decisions are based on a combination of factors, including sustained performance, demonstrated skills and capabilities, business requirements, organizational priorities, role availability, and applicable talent processes.</p>
        <p>By selecting "I Agree," you acknowledge that you have read and understood the purpose of this portal and the criteria governing career progression.</p>
        <label class="flex items-start gap-2 pt-2 border-t border-[#e7bdb9] cursor-pointer">
          <input type="checkbox" data-ack-inner class="mt-1 rounded border-[#e7bdb9] text-[#df162b] focus:ring-[#df162b]"/>
          <span>I have read, understood, and agree to the above terms.</span>
        </label>
      </div>
      <div class="px-5 py-4 border-t border-[#e7bdb9] shrink-0">
        <button type="button" data-ack-agree disabled class="w-full bg-[#df162b] text-white rounded-lg px-4 py-2.5 text-sm font-bold disabled:opacity-40">I Agree</button>
      </div>
    </div>`;
    document.body.appendChild(node);
    const dismiss = () => closeOverlay("mc-disclaimer-modal");
    node.addEventListener("click", (event) => { if (event.target === node) dismiss(); });
    qs("[data-close-ack]", node).onclick = dismiss;
    const inner = qs("[data-ack-inner]", node);
    const agreeBtn = qs("[data-ack-agree]", node);
    inner.onchange = () => { agreeBtn.disabled = !inner.checked; };
    agreeBtn.onclick = () => {
      if (!inner.checked) return;
      dismiss();
      onAgree?.();
    };
  }

  function commonSideNav(user, mmt) {
    return (nav[user.role] || []).map(([route, label, icon]) => {
      const active = page === route;
      const activeClass = mmt ? "bg-[#df162b] text-white" : "bg-blue-700 text-white";
      const idleClass = mmt
        ? "text-[#5d3f3d] hover:bg-[#ffe1df] hover:text-[#df162b]"
        : "text-slate-600 hover:bg-blue-50 hover:text-blue-800";
      return `<a data-route="${route}" href="/app/${route}" class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-bold whitespace-nowrap ${
        active ? activeClass : idleClass
      }"><span class="material-symbols-outlined text-lg">${icon}</span>${esc(label)}</a>`;
    }).join("");
  }

  function commonManagerFooter() {
    return `<footer class="shrink-0 mt-auto border-t border-[#e7bdb9] bg-[#fff0ef] px-5 md:px-8 py-5 flex flex-col lg:flex-row justify-between items-center gap-4">
      <p class="text-sm font-bold text-[#df162b] text-center lg:text-left">Be objective. Use evidence. Give every employee a fair opportunity to grow.</p>
      <div class="flex flex-wrap justify-center gap-5 md:gap-8 text-sm text-[#5d3f3d]">
        <span>Privacy Policy</span>
        <span>Terms of Service</span>
        <span>Support</span>
      </div>
      <p class="text-sm text-[#5d3f3d] text-center lg:text-right">© 2024 MakeMyTrip Talent Development. All rights reserved.</p>
    </footer>`;
  }

  function mountShell(user) {
    const items = nav[user.role] || [];
    const mmt = mmtTheme(user.role);
    const links = commonSideNav(user, mmt);
    const homeRoute = items[0]?.[0] || "login";
    const border = mmt ? "border-[#e7bdb9]" : "border-slate-200";
    const managerChrome = user.role === "zm" || user.role === "rd" || user.role === "admin";
    document.body.className = mmt ? "bg-[#fff8f7] text-slate-900 min-h-screen" : "bg-slate-50 text-slate-900 min-h-screen";
    document.body.innerHTML = `<div class="min-h-screen flex flex-col">
      <header class="h-16 bg-white border-b ${border} px-4 md:px-7 flex items-center justify-between sticky top-0 z-40">
        ${commonBrand(mmt, homeRoute)}
        ${commonProfile(user, mmt)}
      </header>
      <nav class="md:hidden bg-white border-b ${border} p-2 flex gap-2 overflow-x-auto">${links}</nav>
      <div class="md:flex flex-1 min-h-0">
        <aside class="hidden md:flex w-64 shrink-0 ${mmt ? "bg-[#fff0ef]" : "bg-white"} border-r ${border} p-4 flex-col gap-2">${links}</aside>
        <div class="flex-1 min-w-0 flex flex-col min-h-[calc(100vh-4rem)]">
          <main id="mc-main" class="flex-1 min-w-0"></main>
          ${managerChrome ? commonManagerFooter() : ""}
        </div>
      </div>
    </div>`;
    qsa("[data-route]").forEach((link) => {
      link.onclick = (event) => {
        event.preventDefault();
        const route = link.dataset.route;
        if (
          user.role === "employee"
          && route
          && route !== "employee/welcome"
          && !hasDisclaimerAck(user)
        ) {
          toast("Acknowledge the disclaimer on Home before continuing.", "error");
          return;
        }
        go(route);
      };
    });
    qs("[data-logout]").onclick = logout;
    qs("[data-open-account]").onclick = openAccountModal;
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
    if (role === "zm") {
      await initZmWelcome();
      return;
    }
    if (role === "rd") {
      await initRdWelcome();
      return;
    }
    render(`<section class="max-w-4xl py-8 md:py-16">
      <p class="uppercase tracking-[0.2em] text-xs font-bold text-blue-700">${esc(role)} workspace</p>
      <h1 class="text-4xl md:text-5xl font-black text-blue-900 mt-3">Welcome, ${esc(session.user.display_name)}</h1>
    </section>`);
  }

  function welcomeCompassMark() {
    return `<div class="absolute right-0 top-4 md:top-8 opacity-10 pointer-events-none hidden lg:block" aria-hidden="true">
      <span class="material-symbols-outlined text-[280px] md:text-[320px] text-[#df162b] rotate-12 leading-none" style="font-variation-settings:'FILL' 0">explore</span>
    </div>`;
  }

  async function initRdWelcome() {
    const cards = [
      ["balance", "Why this validation matters", "Ensuring every leader is benchmarked against the same corporate standard to drive regional excellence."],
      ["query_stats", "Use evidence, not assumptions", "Move beyond subjective feelings by attaching specific project outcomes and KPI data to each competency."],
      ["military_tech", "Focus on proficiency", "Evaluate the depth of skill rather than just completion. Look for demonstrated mastery in complex scenarios."],
      ["route", "Enable development", "Every validation identifies a 'growth gap'. Use these insights to curate specific learning paths for your team."],
    ];
    const steps = [
      ["1", "#005cab", "Review Peer Input", "Assess how subordinates and colleagues perceive the leader's impact."],
      ["2", "#005cab", "Calibrate Performance", "Compare self-assessments with hard business metrics and MMT standards."],
      ["3", "#df162b", "Finalize Profile", "Cement the competency record and trigger regional development recommendations."],
    ];
    render(`<div class="relative overflow-hidden">
      <div class="absolute top-0 right-0 w-1/2 h-full opacity-20 pointer-events-none" style="background-image:radial-gradient(circle,#e7bdb9 1px,transparent 1px);background-size:20px 20px"></div>
      <div class="absolute -bottom-20 -right-20 w-96 h-96 bg-[#ffdad7] blur-[100px] rounded-full opacity-30 pointer-events-none"></div>
      ${welcomeCompassMark()}
      <div class="relative z-10 max-w-[1200px] mx-auto px-5 md:px-10 py-10 md:py-14 space-y-10 md:space-y-12">
        <section class="max-w-4xl relative">
          <div class="inline-flex items-center gap-2 px-3 py-1 bg-[#ffdad7] text-[#930015] rounded-full text-xs font-bold mb-4">
            <span class="material-symbols-outlined text-[16px]">location_on</span>
            MyCareer Compass
          </div>
          <h1 class="text-3xl md:text-5xl font-black text-[#291716] mb-5 leading-tight">
            Turn evidence into a fair and consistent <span class="text-[#df162b]">competency profile</span>
          </h1>
          <p class="text-lg text-[#5d3f3d] leading-relaxed max-w-2xl mb-8">
            As a Regional Director, your role is to validate proficiency based on observed performance and objective data. Help our talent navigate their professional journey with clarity and rigor.
          </p>
          <div class="flex flex-wrap gap-3">
            <button type="button" data-start="rd/dashboard" class="px-6 py-3 bg-[#df162b] text-white rounded-lg font-bold hover:opacity-90 transition-all inline-flex items-center gap-2">
              Start Competency Validation
              <span class="material-symbols-outlined text-[20px]">arrow_forward</span>
            </button>
          </div>
        </section>
        <section class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5">
          ${cards.map(([icon, title, copy]) => `<article class="bg-white border border-[#e7bdb9] rounded-xl p-5 flex flex-col gap-3 hover:border-[#df162b] transition-colors group">
            <div class="w-12 h-12 rounded-lg bg-[#ffe1df] grid place-items-center text-[#df162b] group-hover:bg-[#df162b] group-hover:text-white transition-colors">
              <span class="material-symbols-outlined">${icon}</span>
            </div>
            <div>
              <h3 class="font-bold text-[#291716] mb-1">${esc(title)}</h3>
              <p class="text-sm text-[#5d3f3d]">${esc(copy)}</p>
            </div>
          </article>`).join("")}
        </section>
        <section class="relative rounded-xl overflow-hidden bg-[#df162b] px-4 py-3 md:px-5 md:py-4 max-w-3xl">
          <div class="absolute inset-0 opacity-10 pointer-events-none" style="background:radial-gradient(circle at center,white,transparent 70%)"></div>
          <div class="relative z-10 text-white">
            <div class="flex items-center gap-1.5 mb-1">
              <span class="material-symbols-outlined text-[18px]" style="font-variation-settings:'FILL' 1">stars</span>
              <span class="text-[10px] font-bold uppercase tracking-widest opacity-80">Scoring Criteria</span>
            </div>
            <h2 class="text-base md:text-lg font-bold mb-1">Your assessment shapes the final competency profile.</h2>
            <p class="text-sm opacity-90">This profile serves as the trusted foundation for organizational planning, talent decisions and leadership placement.</p>
          </div>
        </section>
        <section class="flex flex-col lg:flex-row items-center justify-between gap-10">
          <div class="hidden lg:block w-1/3 shrink-0">
            <div class="aspect-square rounded-2xl overflow-hidden border-8 border-white shadow-xl rotate-3 bg-[#fff0ef] flex items-center justify-center">
              <div class="text-center p-6">
                <span class="material-symbols-outlined text-[#df162b] text-[72px]" style="font-variation-settings:'FILL' 1">account_tree</span>
                <p class="mt-3 font-bold text-[#291716]">Career destinations</p>
                <p class="text-sm text-[#5d3f3d] mt-1">Evidence → calibrated profile → growth path</p>
              </div>
            </div>
          </div>
          <div class="flex-1 space-y-6 w-full">
            ${steps.map(([n, color, title, copy], index) => `<div class="flex items-start gap-4">
              <div class="flex flex-col items-center">
                <div class="w-8 h-8 rounded-full flex items-center justify-center text-white font-bold text-sm" style="background:${color}">${n}</div>
                ${index < steps.length - 1 ? '<div class="w-1 h-12 bg-[#e7bdb9]"></div>' : ""}
              </div>
              <div class="pt-0.5">
                <h4 class="font-bold text-lg text-[#291716]">${esc(title)}</h4>
                <p class="text-[#5d3f3d]">${esc(copy)}</p>
              </div>
            </div>`).join("")}
          </div>
        </section>
      </div>
    </div>`, { flush: true });
    qs("[data-start]")?.addEventListener("click", () => go(qs("[data-start]").dataset.start || "rd/dashboard"));
  }

  async function initZmWelcome() {
    render(`<div class="relative overflow-hidden min-h-[calc(100vh-4rem)]">
      <div class="absolute inset-0 opacity-40 pointer-events-none" style="background-image:url(&quot;data:image/svg+xml,%3Csvg width='100' height='100' viewBox='0 0 100 100' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M50 10L55 45L90 50L55 55L50 90L45 55L10 50L45 45Z' fill='%23b4001d' fill-opacity='0.03'/%3E%3C/svg%3E&quot;)"></div>
      <div class="absolute inset-0 opacity-30 pointer-events-none" style="background-image:radial-gradient(circle at 2px 2px,#e0e0e0 1px,transparent 0);background-size:24px 24px"></div>
      ${welcomeCompassMark()}
      <div class="relative z-10 max-w-[1200px] mx-auto px-5 md:px-10 py-10 md:py-14">
        <div class="inline-flex items-center px-3 py-1 bg-[#ffdad7] text-[#930015] rounded-full mb-4 text-xs font-bold uppercase tracking-wider">MyCareer Compass</div>
        <h1 class="text-3xl md:text-5xl font-black text-[#291716] mb-4 max-w-3xl leading-tight">Empower your team to unlock their full potential through personalized growth and development.</h1>
        <p class="text-lg text-[#5d3f3d] max-w-2xl">As a Manager, your insights define the trajectory of our talent. Provide objective feedback, identify skill gaps, and empower your team to achieve their next milestone.</p>
        <div class="mt-8">${button("Assess Your Team", `data-start="zm/dashboard"`)}</div>
        <section class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-5 mt-12 mb-10">
          ${[
            ["psychology", "Why MyCareer Compass?", "It standardizes the talent framework across MMT, ensuring that growth is measured against clear, consistent benchmarks for everyone."],
            ["school", "Why should employees keep learning?", "The workplace is evolving rapidly, and so are the skills needed to succeed. Continuous learning helps your team stay future-ready, grow in their career, and unlock new opportunities."],
            ["handshake", "Why your support matters?", "You are the bridge between strategy and execution. Your mentorship converts individual potential into collective organizational excellence."],
            ["assignment_turned_in", "What we need from you?", "Honest insights that reflect current proficiency levels while identifying clear areas for future development."],
          ].map(([icon, title, copy]) => `<article class="bg-white border border-[#e7bdb9] p-5 rounded-xl">
            <div class="w-10 h-10 rounded-lg bg-[#ffe1df] grid place-items-center text-[#df162b] mb-3"><span class="material-symbols-outlined">${icon}</span></div>
            <h3 class="font-bold text-[#291716] mb-2">${esc(title)}</h3>
            <p class="text-sm text-[#5d3f3d]">${esc(copy)}</p>
          </article>`).join("")}
        </section>
        <section class="bg-[#d5e3ff] text-[#001c3b] p-6 md:p-8 rounded-xl border border-[#e7bdb9] mb-10">
          <div class="flex flex-col md:flex-row items-center gap-6">
            <div class="w-16 h-16 bg-white/60 rounded-full grid place-items-center shrink-0"><span class="material-symbols-outlined text-3xl text-[#005cab]">star_half</span></div>
            <div>
              <h2 class="text-xl font-bold mb-1">Your rating creates the starting point</h2>
              <p class="max-w-3xl opacity-90">The competency ratings you provide today are the foundation of the Personalized Learning Path for your team. Accuracy here ensures every employee receives the exact training they need to succeed.</p>
            </div>
          </div>
        </section>
      </div>
    </div>`, { flush: true });
    qs("[data-start]")?.addEventListener("click", () => go(qs("[data-start]").dataset.start || "zm/dashboard"));
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
    const completed = roleplays.roleplays.filter((item) => item.status === "completed").length;
    const total = roleplays.roleplays.length || 7;
    const latticeUnlocked = Boolean(roleplays.lattice_unlocked);
    const aspirationLocked = Boolean(career.choice);
    const coursesSelected = Array.isArray(learning.courses) && learning.courses.length > 0;
    const aspirationLabel = career.paths?.find((path) => path.id === career.choice?.aspiration_role)?.label
      || career.choice?.aspiration_role
      || "";

    const steps = [
      {
        key: "roleplays",
        n: "1",
        title: "Assessments",
        done: completed === total && total > 0,
        copy: completed === total && total > 0
          ? `All ${total} competency assessments completed.`
          : `${completed} of ${total} competency assessments completed.`,
        action: "employee/roleplays",
        actionLabel: completed === total && total > 0 ? "Review Assessments" : "Open Assessments",
        locked: false,
      },
      {
        key: "lattice",
        n: "2",
        title: "Career Lattice",
        done: latticeUnlocked,
        copy: latticeUnlocked
          ? "Career Lattice unlocked. Explore eligible paths for your role and grade."
          : "Complete all seven assessments to unlock Career Lattice.",
        action: "employee/career",
        actionLabel: latticeUnlocked ? "Open Lattice" : "Locked",
        locked: !latticeUnlocked,
      },
      {
        key: "aspiration",
        n: "3",
        title: "Aspiration",
        done: aspirationLocked,
        copy: aspirationLocked
          ? `Aspiration locked: ${aspirationLabel}.`
          : latticeUnlocked
            ? "Choose and confirm one career aspiration."
            : "Available after Career Lattice unlocks.",
        action: "employee/career",
        actionLabel: aspirationLocked ? "View Aspiration" : (latticeUnlocked ? "Choose Aspiration" : "Locked"),
        locked: !latticeUnlocked,
      },
      {
        key: "learning",
        n: "4",
        title: "Learning",
        done: coursesSelected,
        copy: coursesSelected
          ? `${learning.courses.length} course${learning.courses.length === 1 ? "" : "s"} selected in your learning journey.`
          : aspirationLocked
            ? "Shop from a list of recommended courses and get started with your personalized learning journey."
            : "Available after aspiration is locked.",
        action: coursesSelected ? "employee/learning" : "employee/courses",
        actionLabel: coursesSelected ? "Open Learning Journey" : (aspirationLocked ? "Open Courses" : "Locked"),
        locked: !aspirationLocked,
      },
    ];

    const features = [
      ["analytics", "Understand where you are", "Assess your current skills and performance through comprehensive data-driven insights and feedback loops."],
      ["visibility", "Explore relevant possibilities", "Discover potential career paths and roles that align with your strengths and the organization's strategic needs."],
      ["school", "Build capability through learning", "Access curated content and training programs designed to bridge your skill gaps and prepare you for the next level."],
      ["rocket_launch", "Turn learning into action", "Apply your new skills in real-world scenarios and unlock your full potential."],
    ];
    const acked = hasDisclaimerAck();

    render(`<div>
      <section class="relative py-10 bg-[#fff0ef] overflow-hidden" style="background-image:radial-gradient(circle at 2px 2px,#df162b22 1px,transparent 0);background-size:24px 24px">
        <div class="max-w-[1200px] mx-auto px-5 md:px-10 relative z-10">
          <div class="max-w-2xl text-left">
            <span class="inline-block px-2 py-1 bg-cyan-50 text-cyan-800 text-xs font-bold rounded-full mb-4">MyCareer Compass · Your Development Journey</span>
            <h2 class="text-3xl md:text-5xl font-black text-[#291716] mb-4">Own your growth. <br/><span class="text-[#0075d7]">Explore what could be next.</span></h2>
            <p class="text-lg text-[#5d3f3d] leading-relaxed">Choose your career aspiration and embark on a personalized learning journey designed to support your growth and help you shape your career.</p>
          </div>
        </div>
        ${welcomeCompassMark()}
      </section>
      <section class="py-4 bg-[#fff0ef]" style="background-image:radial-gradient(circle at 2px 2px,#df162b22 1px,transparent 0);background-size:24px 24px">
        <div class="max-w-[1200px] mx-auto px-5 md:px-10 text-left">
          <aside class="bg-[#ffdad6]/70 border border-[#e7bdb9]/40 rounded-lg px-5 py-4 w-full text-left">
            <div class="flex items-center justify-start gap-1.5 mb-2">
              <span class="material-symbols-outlined text-[#93000a] text-[22px]">info</span>
              <h4 class="font-bold text-[#93000a] text-base">Important to know...</h4>
            </div>
            <p class="text-base leading-relaxed text-[#291716] text-left">Dear Learner,
Before you begin, we encourage you to take a few minutes to understand the philosophy behind this initiative. It has been designed to support your career aspirations and continuous upskilling.</p>
            <div class="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm">
              <p>
                <button type="button" data-open-disclaimer class="text-[#0075d7] font-semibold underline hover:opacity-80">click to read more</button>
                ${acked ? `<span data-ack-badge class="ml-2 text-[#93000a] font-semibold">· Acknowledged</span>` : `<span data-ack-badge class="hidden ml-2 text-[#93000a] font-semibold">· Acknowledged</span>`}
              </p>
              <a href="https://imgak.mmtcdn.com/mmt-careers-ui/assets/static/documents/Career_Progression_Guide.pdf" target="_blank" rel="noopener noreferrer" class="text-[#0075d7] font-semibold underline hover:opacity-80 shrink-0">see more about this</a>
            </div>
          </aside>
        </div>
      </section>
      <section class="py-10 bg-[#ffe9e7]">
        <div class="max-w-[1200px] mx-auto px-5 md:px-10">
          <div class="text-center mb-8">
            <h2 class="text-2xl md:text-3xl font-bold mb-2">Your journey in 4 steps</h2>
            <p class="text-[#5d3f3d]">A structured approach to navigating your development and achieving your professional aspirations.</p>
          </div>
          <div class="relative" data-journey-steps>
            <div class="pointer-events-none absolute top-8 left-[12.5%] right-[12.5%] h-[2px] hidden lg:block opacity-40" style="background:repeating-linear-gradient(90deg,#df162b 0,#df162b 8px,transparent 8px,transparent 16px)" aria-hidden="true"></div>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 relative z-10">
            ${steps.map((step) => `<div class="flex flex-col items-center text-center" data-step="${step.key}">
              <div class="w-16 h-16 rounded-full flex items-center justify-center font-bold text-xl mb-4 border-4 border-white shadow-sm relative z-10 ${
                step.done ? "bg-[#df162b] text-white" : "bg-[#fddbd8] text-[#5d3f3d]"
              }" data-step-badge>${step.done ? "✓" : step.n}</div>
              <h4 class="font-bold mb-1">${esc(step.title)}</h4>
              <p class="text-sm text-[#5d3f3d]" data-step-copy>${esc(step.copy)}</p>
              <button class="mt-4 text-[#0075d7] font-bold text-sm ${step.locked || !acked ? "opacity-40 cursor-not-allowed" : ""}" data-step-action="${step.action}" type="button" ${step.locked || !acked ? "disabled" : ""}>${esc(step.actionLabel)}${!acked && !step.locked ? " · Acknowledge first" : ""}</button>
            </div>`).join("")}
            </div>
          </div>
        </div>
      </section>
      <section class="py-8 max-w-[1200px] mx-auto px-5 md:px-10">
        <div class="border-t border-[#e7bdb9] pt-6">
          <div class="flex justify-between items-end mb-2">
            <span class="font-bold">Assessment Completion Status</span>
            <span class="text-sm text-[#5d3f3d]">${completed}/${total} complete</span>
          </div>
          <div class="w-full h-3 bg-[#fddbd8] rounded-full overflow-hidden">
            <div class="h-full bg-[#0075d7]" style="width:${total ? (completed / total) * 100 : 0}%"></div>
          </div>
        </div>
      </section>
      <section class="py-10 max-w-[1200px] mx-auto px-5 md:px-10">
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          ${features.map(([icon, title, copy]) => `<article class="bg-white p-6 rounded-xl border border-[#e7bdb9]">
            <div class="w-12 h-12 rounded-lg bg-[#ffe1df] grid place-items-center mb-4 text-[#0075d7]"><span class="material-symbols-outlined">${icon}</span></div>
            <h3 class="font-bold mb-2">${esc(title)}</h3>
            <p class="text-sm text-[#5d3f3d]">${esc(copy)}</p>
          </article>`).join("")}
        </div>
      </section>
      <section class="pb-10 max-w-[1200px] mx-auto px-5 md:px-10">
        <div class="rounded-xl overflow-hidden min-h-[220px]">
          <img alt="Welcome to our journey" class="w-full h-full object-cover" src="/stitch/employee_welcome_screen/journey_hero.png"/>
        </div>
      </section>
    </div>`, { flush: true });

    const syncAckUi = () => {
      const badge = qs("[data-ack-badge]");
      if (badge) badge.classList.remove("hidden");
      steps.forEach((step) => {
        const action = qs(`[data-step="${step.key}"] [data-step-action]`);
        if (!action) return;
        action.disabled = step.locked;
        action.classList.toggle("opacity-40", step.locked);
        action.classList.toggle("cursor-not-allowed", step.locked);
        action.textContent = step.actionLabel;
        action.onclick = () => {
          if (action.disabled) return;
          go(step.action);
        };
      });
    };

    qs("[data-open-disclaimer]")?.addEventListener("click", (event) => {
      event.preventDefault();
      openDisclaimerModal(() => {
        if (!hasDisclaimerAck()) {
          setDisclaimerAck();
          syncAckUi();
          toast("Acknowledgement saved.");
        }
      });
    });

    qsa("[data-step-action]").forEach((action) => {
      action.onclick = () => {
        if (action.disabled) {
          if (!hasDisclaimerAck()) toast("Acknowledge the disclaimer before continuing.", "error");
          return;
        }
        go(action.dataset.stepAction);
      };
    });
  }

  async function initTeamDashboard(role) {
    if (role === "zm") {
      await renderZmDashboard();
      return;
    }
    if (role === "rd") {
      await renderRdDashboard();
    }
  }

  async function renderRdDashboard() {
    const rows = await employeeSummaries();
    const total = rows.length;
    const validated = rows.filter((row) => row.rd_status === "submitted").length;
    const drafts = rows.filter((row) => row.rd_status === "draft").length;
    const ready = rows.filter((row) => row.zm_status === "submitted" && row.rd_status !== "submitted").length;
    let filterStatus = "all";
    let sortMode = "name-asc";
    let filterOpen = false;
    let sortOpen = false;

    const statusKey = (row) => {
      if (row.rd_status === "submitted") return "completed";
      if (row.rd_status === "draft") return "draft";
      if (row.zm_status === "submitted") return "ready";
      return "pending";
    };

    const statusBadge = (row) => {
      const key = statusKey(row);
      if (key === "completed") {
        return `<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-cyan-50 text-cyan-800"><span class="material-symbols-outlined text-sm">check_circle</span>Validated</span>`;
      }
      if (key === "draft") {
        return `<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-blue-50 text-blue-800"><span class="material-symbols-outlined text-sm">edit</span>Draft</span>`;
      }
      if (key === "ready") {
        return `<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-800"><span class="material-symbols-outlined text-sm">verified_user</span>Ready for RD</span>`;
      }
      return `<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-red-50 text-red-800"><span class="material-symbols-outlined text-sm">hourglass_empty</span>Awaiting ZM</span>`;
    };

    const filteredSorted = () => {
      let list = rows.filter((row) => filterStatus === "all" || statusKey(row) === filterStatus);
      const rank = { pending: 0, ready: 1, draft: 2, completed: 3 };
      list = [...list].sort((a, b) => {
        if (sortMode === "name-asc") return String(a.name || "").localeCompare(String(b.name || ""));
        if (sortMode === "name-desc") return String(b.name || "").localeCompare(String(a.name || ""));
        if (sortMode === "status-asc") return rank[statusKey(a)] - rank[statusKey(b)] || String(a.name || "").localeCompare(String(b.name || ""));
        if (sortMode === "status-desc") return rank[statusKey(b)] - rank[statusKey(a)] || String(a.name || "").localeCompare(String(b.name || ""));
        return 0;
      });
      return list;
    };

    const filterLabel = {
      all: "All",
      pending: "Awaiting ZM",
      ready: "Ready for RD",
      draft: "Draft",
      completed: "Validated",
    };
    const sortLabel = {
      "name-asc": "Name A–Z",
      "name-desc": "Name Z–A",
      "status-asc": "Status: Awaiting first",
      "status-desc": "Status: Validated first",
    };

    const draw = () => {
      const list = filteredSorted();
      const tableRows = list.map((row) => {
        const key = statusKey(row);
        const initialsRow = String(row.name || "E").split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase() || "").join("") || "E";
        const canOpen = key !== "pending";
        const actionLabel = key === "completed" ? "View Ratings" : key === "draft" ? "Continue Validation" : key === "ready" ? "Start Validation" : "Waiting on ZM";
        const actionClass = canOpen
          ? (key === "completed"
            ? "px-4 py-2 bg-[#005cab] text-white rounded-lg font-bold text-sm hover:opacity-90"
            : "px-4 py-2 bg-[#df162b] text-white rounded-lg font-bold text-sm hover:opacity-90")
          : "px-4 py-2 bg-slate-200 text-slate-500 rounded-lg font-bold text-sm cursor-not-allowed";
        const actionAttr = key === "completed"
          ? `data-view-ratings="${esc(row.employee_code)}"`
          : `data-employee="${esc(row.employee_code)}"`;
        return `<tr class="border-t border-[#e7bdb9] hover:bg-[#fff0ef]">
          <td class="p-4">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-full bg-[#ffe1df] flex items-center justify-center font-bold text-[#df162b]">${esc(initialsRow)}</div>
              <div>
                <p class="font-bold text-[#291716]">${esc(row.name)}</p>
                <p class="text-xs text-[#5d3f3d] mt-0.5">${esc(row.designation || row.role_name || "—")}</p>
                <p class="text-[11px] text-[#926e6c]">${esc(row.employee_code)}</p>
              </div>
            </div>
          </td>
          <td class="p-4">${statusBadge(row)}</td>
          <td class="p-4 text-right">
            <button type="button" ${actionAttr} ${canOpen ? "" : "disabled"} class="${actionClass}">${esc(actionLabel)}</button>
          </td>
        </tr>`;
      }).join("") || empty(filterStatus === "all" ? "No employees in your reporting scope." : "No employees match this filter.", 3);

      const filterActive = filterStatus !== "all";
      const chipBase = "px-3 py-1.5 bg-white border rounded-full text-xs font-bold inline-flex items-center gap-1 cursor-pointer hover:border-[#df162b] hover:text-[#df162b] transition-colors";
      const chipOn = "border-[#df162b] text-[#df162b] bg-[#fff0ef]";
      const chipOff = "border-[#e7bdb9] text-[#5d3f3d]";

      render(`<div class="mb-8">
          <h1 class="text-2xl md:text-3xl font-extrabold text-[#df162b]">Your Dashboard</h1>
          <p class="text-[#5d3f3d] mt-1">Validate proficiency after ZM submission and publish final competency profiles.</p>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <div class="bg-white p-5 rounded-xl border border-[#e7bdb9] flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-[#d5e3ff] flex items-center justify-center"><span class="material-symbols-outlined text-[#005cab]">groups</span></div>
            <div><p class="text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Assigned</p><p class="text-2xl font-bold text-[#291716]">${total}</p></div>
          </div>
          <div class="bg-white p-5 rounded-xl border border-[#e7bdb9] flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-[#c3e8ff] flex items-center justify-center"><span class="material-symbols-outlined text-[#005f81]">verified_user</span></div>
            <div><p class="text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Ready for RD</p><p class="text-2xl font-bold text-[#005f81]">${ready}</p></div>
          </div>
          <div class="bg-white p-5 rounded-xl border border-[#e7bdb9] flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-[#ffe1df] flex items-center justify-center"><span class="material-symbols-outlined text-[#df162b]">edit</span></div>
            <div><p class="text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Drafts</p><p class="text-2xl font-bold text-[#df162b]">${drafts}</p></div>
          </div>
          <div class="bg-white p-5 rounded-xl border border-[#e7bdb9] flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-emerald-50 flex items-center justify-center"><span class="material-symbols-outlined text-emerald-700">check_circle</span></div>
            <div><p class="text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Validated</p><p class="text-2xl font-bold text-emerald-700">${validated}</p></div>
          </div>
        </div>
        <div class="bg-white rounded-xl border border-[#e7bdb9] overflow-hidden mb-8">
          <div class="p-4 bg-[#fff0ef] border-b border-[#e7bdb9] flex justify-between items-center gap-3 flex-wrap">
            <div class="flex gap-2 flex-wrap items-center">
              <div class="relative">
                <button type="button" data-toggle-filter class="${chipBase} ${filterActive || filterOpen ? chipOn : chipOff}">
                  <span class="material-symbols-outlined text-[16px]">filter_list</span>
                  Filter${filterActive ? `: ${esc(filterLabel[filterStatus])}` : ""}
                </button>
                ${filterOpen ? `<div class="absolute left-0 top-full mt-2 z-20 min-w-[180px] bg-white border border-[#e7bdb9] rounded-xl shadow-lg py-1">
                  ${Object.keys(filterLabel).map((key) => `<button type="button" data-filter="${key}" class="w-full text-left px-4 py-2 text-sm font-semibold hover:bg-[#fff0ef] ${filterStatus === key ? "text-[#df162b]" : "text-[#291716]"}">${esc(filterLabel[key])}</button>`).join("")}
                </div>` : ""}
              </div>
              <div class="relative">
                <button type="button" data-toggle-sort class="${chipBase} ${sortMode !== "name-asc" || sortOpen ? chipOn : chipOff}">
                  <span class="material-symbols-outlined text-[16px]">sort</span>
                  Sort: ${esc(sortLabel[sortMode])}
                </button>
                ${sortOpen ? `<div class="absolute left-0 top-full mt-2 z-20 min-w-[210px] bg-white border border-[#e7bdb9] rounded-xl shadow-lg py-1">
                  ${Object.entries(sortLabel).map(([key, label]) => `<button type="button" data-sort="${key}" class="w-full text-left px-4 py-2 text-sm font-semibold hover:bg-[#fff0ef] ${sortMode === key ? "text-[#df162b]" : "text-[#291716]"}">${esc(label)}</button>`).join("")}
                </div>` : ""}
              </div>
            </div>
            <span class="text-xs text-[#5d3f3d]">Showing ${list.length}${filterActive ? ` of ${total}` : ""} Team Member${list.length === 1 ? "" : "s"}</span>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full min-w-[720px] text-left">
              <thead><tr class="border-b border-[#e7bdb9]">
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Employee Name</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Validation Status</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-[#5d3f3d] text-right">Action</th>
              </tr></thead>
              <tbody>${tableRows}</tbody>
            </table>
          </div>
          <div class="p-4 border-t border-[#e7bdb9] text-xs text-[#5d3f3d]">Live statuses from ZM submissions and RD drafts.</div>
        </div>
        <div class="grid grid-cols-1 lg:grid-cols-[1.5fr_1fr] gap-5 mt-6">
          <section class="bg-[#fff0ef] border border-[#e7bdb9] border-l-4 border-l-[#df162b] rounded-xl p-5 md:p-6 flex flex-col">
            <div class="flex items-center gap-3 mb-4">
              <div class="w-10 h-10 bg-[#ffe1df] text-[#df162b] rounded-lg grid place-items-center">
                <span class="material-symbols-outlined">lightbulb</span>
              </div>
              <h3 class="text-lg font-bold text-[#291716]">RD Review Best Practices</h3>
            </div>
            <ul class="space-y-3 flex-1">
              <li class="flex items-start gap-3">
                <span class="material-symbols-outlined text-[#df162b] mt-0.5 text-lg">check_circle</span>
                <p class="text-sm text-[#5d3f3d] leading-relaxed">Validate technical competency evidence before leadership traits for a structured approach.</p>
              </li>
              <li class="flex items-start gap-3">
                <span class="material-symbols-outlined text-[#df162b] mt-0.5 text-lg">check_circle</span>
                <p class="text-sm text-[#5d3f3d] leading-relaxed">Consult ZM comments if a score deviates significantly from the department average.</p>
              </li>
              <li class="flex items-start gap-3">
                <span class="material-symbols-outlined text-[#df162b] mt-0.5 text-lg">check_circle</span>
                <p class="text-sm text-[#5d3f3d] leading-relaxed">Target a 48-hour SLA to maintain organizational career growth velocity.</p>
              </li>
            </ul>
            <div class="mt-4 pt-4 border-t border-[#e7bdb9]">
              <p class="text-xs font-bold text-[#df162b] flex items-center gap-2">
                <span class="material-symbols-outlined text-sm">checklist</span>
                Apply on every validation review
              </p>
            </div>
          </section>
          <section class="bg-[#fff0ef] border border-[#e7bdb9] border-l-4 border-l-[#df162b] rounded-xl p-5 md:p-6 flex flex-col">
            <div class="flex items-center gap-3 mb-4">
              <div class="w-10 h-10 bg-[#ffe1df] text-[#df162b] rounded-lg grid place-items-center">
                <span class="material-symbols-outlined">balance</span>
              </div>
              <h3 class="text-lg font-bold text-[#291716]">Calibration Requirement</h3>
            </div>
            <p class="text-sm text-[#5d3f3d] leading-relaxed flex-1">
              All Regional Directors must attend the monthly calibration session. This ensures consistent scoring across divisions and aligns with MMT talent standards.
            </p>
            <div class="mt-4 pt-4 border-t border-[#e7bdb9]">
              <p class="text-xs font-bold text-[#df162b] flex items-center gap-2">
                <span class="material-symbols-outlined text-sm">event</span>
                Next Session: confirm date with Talent Ops
              </p>
            </div>
          </section>
        </div>`);

      qsa("[data-employee]").forEach((control) => {
        if (control.disabled) return;
        control.onclick = () => go("rd/validation", `?employee=${encodeURIComponent(control.dataset.employee)}`);
      });
      qsa("[data-view-ratings]").forEach((control) => {
        control.onclick = () => openFinalProfile(control.dataset.viewRatings);
      });
      qs("[data-toggle-filter]").onclick = (event) => {
        event.stopPropagation();
        filterOpen = !filterOpen;
        sortOpen = false;
        draw();
      };
      qs("[data-toggle-sort]").onclick = (event) => {
        event.stopPropagation();
        sortOpen = !sortOpen;
        filterOpen = false;
        draw();
      };
      qsa("[data-filter]").forEach((control) => {
        control.onclick = (event) => {
          event.stopPropagation();
          filterStatus = control.dataset.filter;
          filterOpen = false;
          draw();
        };
      });
      qsa("[data-sort]").forEach((control) => {
        control.onclick = (event) => {
          event.stopPropagation();
          sortMode = control.dataset.sort;
          sortOpen = false;
          draw();
        };
      });
    };

    draw();
  }

  async function renderZmDashboard() {
    const rows = await employeeSummaries();
    const total = rows.length;
    const rated = rows.filter((row) => row.zm_status === "submitted").length;
    const remaining = total - rated;
    let filterStatus = "all";
    let sortMode = "name-asc";
    let filterOpen = false;
    let sortOpen = false;

    const statusKey = (row) => {
      if (row.zm_status === "submitted") return "completed";
      if (row.zm_status === "draft") return "draft";
      return "pending";
    };

    const statusBadge = (row) => {
      const key = statusKey(row);
      if (key === "completed") {
        return `<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-cyan-50 text-cyan-800"><span class="material-symbols-outlined text-sm">check_circle</span>Completed</span>`;
      }
      if (key === "draft") {
        return `<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-blue-50 text-blue-800"><span class="material-symbols-outlined text-sm">edit</span>Draft</span>`;
      }
      return `<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-red-50 text-red-800"><span class="material-symbols-outlined text-sm">pending</span>Pending</span>`;
    };

    const filteredSorted = () => {
      let list = rows.filter((row) => filterStatus === "all" || statusKey(row) === filterStatus);
      const rank = { pending: 0, draft: 1, completed: 2 };
      list = [...list].sort((a, b) => {
        if (sortMode === "name-asc") return String(a.name || "").localeCompare(String(b.name || ""));
        if (sortMode === "name-desc") return String(b.name || "").localeCompare(String(a.name || ""));
        if (sortMode === "status-asc") return rank[statusKey(a)] - rank[statusKey(b)] || String(a.name || "").localeCompare(String(b.name || ""));
        if (sortMode === "status-desc") return rank[statusKey(b)] - rank[statusKey(a)] || String(a.name || "").localeCompare(String(b.name || ""));
        return 0;
      });
      return list;
    };

    const filterLabel = { all: "All", pending: "Pending", draft: "Draft", completed: "Completed" };
    const sortLabel = {
      "name-asc": "Name A–Z",
      "name-desc": "Name Z–A",
      "status-asc": "Status: Pending first",
      "status-desc": "Status: Completed first",
    };

    const draw = () => {
      const list = filteredSorted();
      const tableRows = list.map((row) => {
        const done = row.zm_status === "submitted";
        const draft = row.zm_status === "draft";
        const finalReady = row.rd_status === "submitted" || row.final_profile_available;
        const initialsRow = String(row.name || "E").split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase() || "").join("") || "E";
        const actionLabel = done ? "View Assessment" : draft ? "Continue Assessment" : "Start Assessment";
        const actionClass = done
          ? "px-4 py-2 bg-[#005cab] text-white rounded-lg font-bold text-sm hover:opacity-90"
          : "px-4 py-2 bg-[#df162b] text-white rounded-lg font-bold text-sm hover:opacity-90";
        const finalBtn = finalReady
          ? `<button type="button" data-view-ratings="${esc(row.employee_code)}" class="px-4 py-2 bg-emerald-700 text-white rounded-lg font-bold text-sm hover:opacity-90">View Final Rating</button>`
          : "";
        return `<tr class="border-t border-[#e7bdb9] hover:bg-[#fff0ef]">
          <td class="p-4">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 rounded-full bg-[#ffe1df] flex items-center justify-center font-bold text-[#df162b]">${esc(initialsRow)}</div>
              <div>
                <p class="font-bold text-[#291716]">${esc(row.name)}</p>
                <p class="text-xs text-[#5d3f3d] mt-0.5">${esc(row.designation || row.role_name || "—")}</p>
                <p class="text-[11px] text-[#926e6c]">${esc(row.employee_code)}</p>
              </div>
            </div>
          </td>
          <td class="p-4">${statusBadge(row)}</td>
          <td class="p-4 text-right">
            <div class="inline-flex flex-wrap justify-end gap-2">
              <button type="button" data-employee="${esc(row.employee_code)}" class="${actionClass}">${esc(actionLabel)}</button>
              ${finalBtn}
            </div>
          </td>
        </tr>`;
      }).join("") || empty(filterStatus === "all" ? "No employees in your reporting scope." : "No employees match this filter.", 3);

      const filterActive = filterStatus !== "all";
      const chipBase = "px-3 py-1.5 bg-white border rounded-full text-xs font-bold inline-flex items-center gap-1 cursor-pointer hover:border-[#df162b] hover:text-[#df162b] transition-colors";
      const chipOn = "border-[#df162b] text-[#df162b] bg-[#fff0ef]";
      const chipOff = "border-[#e7bdb9] text-[#5d3f3d]";

      render(`<div class="mb-8">
          <h1 class="text-2xl md:text-3xl font-extrabold text-[#df162b]">Your Dashboard</h1>
          <p class="text-[#5d3f3d] mt-1">Select an employee to rate their competencies.</p>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <div class="bg-white p-5 rounded-xl border border-[#e7bdb9] flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-[#d5e3ff] flex items-center justify-center"><span class="material-symbols-outlined text-[#005cab]">groups</span></div>
            <div><p class="text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Total Employees</p><p class="text-2xl font-bold text-[#291716]">${total}</p></div>
          </div>
          <div class="bg-white p-5 rounded-xl border border-[#e7bdb9] flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-[#c3e8ff] flex items-center justify-center"><span class="material-symbols-outlined text-[#005f81]">verified</span></div>
            <div><p class="text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Rated</p><p class="text-2xl font-bold text-[#005f81]">${rated}</p></div>
          </div>
          <div class="bg-white p-5 rounded-xl border border-[#e7bdb9] flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-[#ffe1df] flex items-center justify-center"><span class="material-symbols-outlined text-[#df162b]">hourglass_empty</span></div>
            <div><p class="text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Remaining</p><p class="text-2xl font-bold text-[#df162b]">${remaining}</p></div>
          </div>
        </div>
        <div class="bg-white rounded-xl border border-[#e7bdb9] overflow-hidden mb-8">
          <div class="p-4 bg-[#fff0ef] border-b border-[#e7bdb9] flex justify-between items-center gap-3 flex-wrap">
            <div class="flex gap-2 flex-wrap items-center">
              <div class="relative">
                <button type="button" data-toggle-filter class="${chipBase} ${filterActive || filterOpen ? chipOn : chipOff}">
                  <span class="material-symbols-outlined text-[16px]">filter_list</span>
                  Filter${filterActive ? `: ${esc(filterLabel[filterStatus])}` : ""}
                </button>
                ${filterOpen ? `<div class="absolute left-0 top-full mt-2 z-20 min-w-[160px] bg-white border border-[#e7bdb9] rounded-xl shadow-lg py-1">
                  ${["all", "pending", "draft", "completed"].map((key) => `<button type="button" data-filter="${key}" class="w-full text-left px-4 py-2 text-sm font-semibold hover:bg-[#fff0ef] ${filterStatus === key ? "text-[#df162b]" : "text-[#291716]"}">${esc(filterLabel[key])}</button>`).join("")}
                </div>` : ""}
              </div>
              <div class="relative">
                <button type="button" data-toggle-sort class="${chipBase} ${sortMode !== "name-asc" || sortOpen ? chipOn : chipOff}">
                  <span class="material-symbols-outlined text-[16px]">sort</span>
                  Sort: ${esc(sortLabel[sortMode])}
                </button>
                ${sortOpen ? `<div class="absolute left-0 top-full mt-2 z-20 min-w-[200px] bg-white border border-[#e7bdb9] rounded-xl shadow-lg py-1">
                  ${Object.entries(sortLabel).map(([key, label]) => `<button type="button" data-sort="${key}" class="w-full text-left px-4 py-2 text-sm font-semibold hover:bg-[#fff0ef] ${sortMode === key ? "text-[#df162b]" : "text-[#291716]"}">${esc(label)}</button>`).join("")}
                </div>` : ""}
              </div>
            </div>
            <span class="text-xs text-[#5d3f3d]" data-showing-count>Showing ${list.length}${filterActive ? ` of ${total}` : ""} Team Member${list.length === 1 ? "" : "s"}</span>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full min-w-[720px] text-left">
              <thead><tr class="border-b border-[#e7bdb9]">
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Employee Name</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Assessment Status</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-[#5d3f3d] text-right">Action</th>
              </tr></thead>
              <tbody>${tableRows}</tbody>
            </table>
          </div>
          <div class="p-4 border-t border-[#e7bdb9] text-xs text-[#5d3f3d]">Live statuses from saved drafts and submissions.</div>
        </div>`);

      qsa("[data-employee]").forEach((control) => {
        control.onclick = () => openAssessment(control.dataset.employee);
      });
      qsa("[data-view-ratings]").forEach((control) => {
        control.onclick = () => openFinalProfile(control.dataset.viewRatings);
      });
      qs("[data-toggle-filter]").onclick = (event) => {
        event.stopPropagation();
        filterOpen = !filterOpen;
        sortOpen = false;
        draw();
      };
      qs("[data-toggle-sort]").onclick = (event) => {
        event.stopPropagation();
        sortOpen = !sortOpen;
        filterOpen = false;
        draw();
      };
      qsa("[data-filter]").forEach((control) => {
        control.onclick = (event) => {
          event.stopPropagation();
          filterStatus = control.dataset.filter;
          filterOpen = false;
          draw();
        };
      });
      qsa("[data-sort]").forEach((control) => {
        control.onclick = (event) => {
          event.stopPropagation();
          sortMode = control.dataset.sort;
          sortOpen = false;
          draw();
        };
      });
    };

    draw();
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
      const initials = String(employee.name || "E").split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase() || "").join("") || "E";
      const designation = employee.designation || employee.role_name || "—";
      const modal = document.createElement("div");
      modal.className = "fixed inset-0 z-[80] bg-black/40 flex items-center justify-center p-3 md:p-8";
      modal.innerHTML = `<style>
        .zm-assess-scroll::-webkit-scrollbar { width: 6px; }
        .zm-assess-scroll::-webkit-scrollbar-track { background: #f1f1f1; }
        .zm-assess-scroll::-webkit-scrollbar-thumb { background: #df162b; border-radius: 10px; }
        .zm-assess-radio:checked + .zm-assess-card {
          border-color: #df162b;
          background-color: #fff0ef;
          box-shadow: 0 0 0 1px #df162b;
        }
        .zm-assess-radio:checked + .zm-assess-card .zm-assess-dot {
          border-color: #df162b;
        }
        .zm-assess-radio:checked + .zm-assess-card .zm-assess-dot-inner {
          background-color: #df162b;
          transform: scale(1);
        }
        .zm-assess-radio:disabled + .zm-assess-card { cursor: default; opacity: 0.95; }
      </style>
      <div class="bg-white w-full max-w-5xl h-full max-h-[95vh] rounded-xl shadow-2xl flex flex-col overflow-hidden" role="dialog" aria-modal="true">
        <header class="shrink-0 sticky top-0 z-10 bg-white border-b border-gray-100 px-5 md:px-6 py-4 flex flex-wrap gap-3 justify-between items-center shadow-sm">
          <div class="flex items-center gap-3 md:gap-4 min-w-0">
            <div class="w-11 h-11 md:w-12 md:h-12 bg-[#df162b] text-white rounded-full flex items-center justify-center font-bold text-lg shrink-0">${esc(initials)}</div>
            <div class="min-w-0">
              <h1 class="text-lg md:text-xl font-bold text-[#df162b] leading-none truncate">${esc(employee.name)}</h1>
              <p class="text-sm text-gray-500 mt-1 font-medium truncate">${esc(designation)} <span class="mx-1 text-gray-300">|</span> ${esc(employee.employee_code)} - ZM assessment</p>
            </div>
          </div>
          <div class="flex items-center gap-2 md:gap-3 ml-auto">
            ${locked ? "" : `<button type="button" data-save class="px-3 md:px-4 py-2 text-sm font-semibold text-gray-600 hover:bg-gray-50 rounded-lg transition-colors">Save Progress</button>
            <button type="button" data-submit class="px-4 md:px-5 py-2 bg-[#df162b] text-white text-sm font-semibold rounded-lg hover:bg-red-700 transition-colors shadow-sm">Submit Rating</button>`}
            <button type="button" data-close aria-label="Close" class="p-2 text-gray-400 hover:text-gray-600 transition-colors">
              <span class="material-symbols-outlined">close</span>
            </button>
          </div>
        </header>
        <main class="flex-grow overflow-y-auto zm-assess-scroll p-5 md:p-6 space-y-6 md:space-y-8 bg-gray-50/50">
          ${meta.competencies.map((item) => `<section class="bg-white rounded-xl border border-gray-200 p-5 md:p-6 shadow-sm">
            <div class="mb-5 md:mb-6">
              <h2 class="text-lg font-bold text-gray-900">${esc(item.competency)}</h2>
              <p class="text-sm text-gray-600 mt-1 italic">${esc(item.definition)}</p>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-4 gap-3 md:gap-4 mb-5 md:mb-6">
              ${levels.map((level) => {
                const checked = assessment?.ratings?.[item.competency] === level;
                const rubric = meta.rubric[item.competency]?.[level] || "";
                return `<label class="relative ${locked ? "cursor-default" : "cursor-pointer"} group">
                  <input class="sr-only zm-assess-radio" type="radio" name="rating-${esc(item.competency)}" value="${level}" ${checked ? "checked" : ""} ${locked ? "disabled" : ""}/>
                  <div class="zm-assess-card h-full p-4 border border-gray-200 rounded-lg hover:border-[#df162b]/40 transition-all">
                    <div class="flex items-start gap-3">
                      <div class="zm-assess-dot mt-1 w-4 h-4 rounded-full border-2 border-gray-300 flex items-center justify-center shrink-0">
                        <div class="zm-assess-dot-inner w-2 h-2 rounded-full transform scale-0 transition-transform duration-200"></div>
                      </div>
                      <div>
                        <span class="block font-bold text-sm text-gray-900 mb-1">${esc(level)}</span>
                        <span class="text-xs text-gray-500 leading-relaxed">${esc(rubric)}</span>
                      </div>
                    </div>
                  </div>
                </label>`;
              }).join("")}
            </div>
            <textarea data-note="${esc(item.competency)}" ${locked ? "disabled" : ""} rows="3" class="w-full border border-gray-200 rounded-lg text-sm p-3 focus:ring-[#df162b] focus:border-[#df162b] placeholder:text-gray-400 placeholder:italic disabled:bg-gray-50" placeholder="Add optional evidence notes here...">${esc(assessment?.notes?.[item.competency] || "")}</textarea>
          </section>`).join("")}
          <footer class="py-6 flex flex-col items-center justify-center space-y-3">
            <div class="flex items-center gap-2">
              <img src="/stitch/common/my-logo.png" alt="my" class="w-8 h-8 rounded-lg object-cover"/>
              <span class="text-gray-800 font-bold tracking-tight text-lg">Career Compass</span>
            </div>
            <p class="text-[10px] text-[#df162b]/40 uppercase tracking-widest font-bold">© 2026 MakeMyTrip Talent Development. All rights reserved.</p>
            ${locked ? `<div class="pt-2"><div class="bg-[#df162b]/5 px-6 py-2 rounded-full border border-[#df162b]/10"><p class="text-[#df162b] font-semibold text-sm">Submitted and locked</p></div></div>` : ""}
          </footer>
        </main>
      </div>`;
      document.body.appendChild(modal);
      qs("[data-close]", modal).onclick = () => modal.remove();
      modal.addEventListener("click", (event) => {
        if (event.target === modal) modal.remove();
      });
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
        await renderZmDashboard();
      };
      if (!locked) {
        qs("[data-save]", modal).onclick = () => save(false).catch((error) => toast(error.message, "error"));
        qs("[data-submit]", modal).onclick = () => save(true).catch((error) => toast(error.message, "error"));
      }
    } catch (error) {
      toast(error.message, "error");
    }
  }

  function groupEvidenceBySource(items) {
    const groups = [];
    const index = new Map();
    for (const item of items || []) {
      const source = String(item.source || "Evidence").trim() || "Evidence";
      if (!index.has(source)) {
        index.set(source, groups.length);
        groups.push({ source, items: [] });
      }
      groups[index.get(source)].items.push(item);
    }
    return groups;
  }

  function evidenceSourceTitle(source) {
    return String(source || "").toUpperCase() === "TNA" ? "Learning Input From Employee" : String(source || "");
  }

  function evidenceDisplayLabel(source, label) {
    const text = String(label || "").trim();
    if (!text) return "";
    const src = String(source || "").trim().toLowerCase();
    if (src === "tna" && /standard\s*skill|skill\s*cluster/i.test(text)) return "";
    if (src === "interview" && /^round\s*\d+$/i.test(text)) return "";
    return text;
  }

  function renderEvidencePanel(bundle) {
    const items = bundle?.evidence || [];
    if (!items.length) {
      return `<p class="text-sm text-[#5d3f3d] mt-3">${esc(bundle?.empty_message || "No relevant evidence found.")}</p>`;
    }
    return groupEvidenceBySource(items).map(({ source, items: rows }) => `<div class="mt-4">
      <h4 class="text-xs font-bold uppercase tracking-wider text-[#df162b] mb-2">${esc(evidenceSourceTitle(source))}</h4>
      <div class="space-y-2">${rows.map((item) => {
        const label = evidenceDisplayLabel(source, item.label);
        return `<article class="border border-[#e7bdb9] rounded-lg p-3 bg-[#fff8f7]">
        ${label ? `<p class="text-[11px] font-semibold text-[#926e6c] mb-1">${esc(label)}</p>` : ""}
        <p class="text-sm text-[#291716]">${esc(item.snippet)}</p>
      </article>`;
      }).join("")}</div>
    </div>`).join("");
  }

  async function initRdDetail() {
    const code = params.get("employee");
    if (!code) {
      go("rd/dashboard");
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
    const rubric = context.rubric || {};
    render(`${pageHeader(`${context.employee.name}'s Competency Profile`, `${context.employee.employee_code} · ${context.employee.designation || context.employee.role_name || "—"} · ${context.employee.grade || ""}`, button("Back", "data-back", true))}
      <p class="mb-6 p-4 bg-[#fff0ef] border border-[#e7bdb9] rounded-lg text-sm text-[#5d3f3d]">Evidence supports review; it never determines the RD rating. Only competency-relevant excerpts are shown.</p>
      <div class="space-y-5">${Object.entries(context.evidence).map(([competency, bundle]) => `<section class="bg-white border border-[#e7bdb9] rounded-xl p-5">
        <div class="grid lg:grid-cols-2 gap-6">
          <div>
            <h2 class="text-lg font-bold text-[#291716]">${esc(competency)}</h2>
            <p class="text-sm mt-2 text-[#5d3f3d]">ZM rating: <strong class="text-[#291716]">${esc(context.zm_assessment.ratings?.[competency] || "Not rated")}</strong></p>
            <p class="text-sm text-[#926e6c] mt-1">${esc(context.zm_assessment.notes?.[competency] || "No ZM note.")}</p>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-4">
              ${levels.map((level) => {
                const selected = ratings[competency] === level;
                const definition = rubric[competency]?.[level] || "";
                return `<button type="button" data-rating="${esc(competency)}" data-level="${level}" ${locked ? "disabled" : ""} class="text-left p-3 border rounded-lg transition-colors ${
                  selected ? "bg-[#df162b] text-white border-[#df162b]" : "border-[#e7bdb9] bg-white hover:border-[#df162b]/50"
                }">
                  <strong class="block text-sm">${esc(level)}</strong>
                  ${definition ? `<p class="text-xs mt-1 leading-relaxed ${selected ? "text-white/90" : "text-[#5d3f3d]"}">${esc(definition)}</p>` : ""}
                </button>`;
              }).join("")}
            </div>
            <textarea data-rd-note="${esc(competency)}" ${locked ? "disabled" : ""} class="w-full border border-[#e7bdb9] rounded-lg p-3 mt-4 text-sm" placeholder="Optional RD note">${esc(notes[competency] || "")}</textarea>
          </div>
          <div>
            <h3 class="font-bold text-sm text-[#291716]">Supporting Evidence</h3>
            ${renderEvidencePanel(bundle)}
          </div>
        </div>
      </section>`).join("")}</div>
      <div class="mt-6 flex justify-end gap-3">${locked ? '<strong class="text-emerald-700">Final profile submitted and locked</strong>' : `${button("Save Draft", "data-draft", true)}${button("Submit Final Profile", "data-final")}`}</div>`);
    qs("[data-back]").onclick = () => go("rd/dashboard");
    if (locked) return;
    qsa("[data-rating]").forEach((control) => {
      control.onclick = () => {
        ratings[control.dataset.rating] = control.dataset.level;
        qsa(`[data-rating="${CSS.escape(control.dataset.rating)}"]`).forEach((item) => {
          const active = item.dataset.level === control.dataset.level;
          item.className = `text-left p-3 border rounded-lg transition-colors ${
            active ? "bg-[#df162b] text-white border-[#df162b]" : "border-[#e7bdb9] bg-white hover:border-[#df162b]/50"
          }`;
          const def = qs("p", item);
          if (def) def.className = `text-xs mt-1 leading-relaxed ${active ? "text-white/90" : "text-[#5d3f3d]"}`;
        });
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
      if (submit) go("rd/dashboard");
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
            ? "You have successfully completed all required competency assessments."
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
        <div class="mt-auto flex flex-col gap-2">${row.roleplay_url ? `<a class="w-full text-center px-3 py-2.5 border-2 border-[#1464F4] text-[#1464F4] rounded-lg font-bold text-sm hover:bg-[#1464F4]/5" href="${esc(row.roleplay_url)}" target="_blank" rel="noopener">Open Assessment</a>` : ""}
        <label class="w-full text-center px-3 py-2.5 bg-[#1464F4] text-white rounded-lg font-bold text-sm cursor-pointer hover:opacity-90">Upload Screenshot<input data-upload="${esc(row.competency)}" class="hidden" type="file" accept="image/png,image/jpeg,image/webp"></label></div>
      </section>`;
    }).join("");
    const proTip = `<aside class="md:col-span-1 bg-[#df162b] text-white rounded-xl p-6 flex items-center min-h-[220px]">
      <div class="w-full">
        <span class="bg-white/20 px-2.5 py-1 rounded text-[10px] font-bold uppercase tracking-widest mb-3 inline-block">Pro Tip</span>
        <p class="text-sm leading-relaxed border border-white/40 rounded-lg p-3 bg-black/10">Approach the role-play as you would in a real work scenario. Your responses will shape your personalized development journey. The more authentically you engage with each scenario, the more relevant and impactful your learning recommendations will be.</p>
      </div>
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
    if (!state.unlocked) {
      render(`${pageHeader("Career Lattice", "Available paths derive from your current role, grade, and completed assessments.")}
        <div class="bg-white border border-[#e7bdb9] rounded-xl p-8 text-center">
          <h2 class="text-xl font-bold text-[#291716]">Career lattice locked</h2>
          <p class="text-[#5d3f3d] mt-2">Complete all seven assessments first.</p>
          <div class="mt-5">${button("Open Assessments", "data-roleplays")}</div>
        </div>`);
      qs("[data-roleplays]").onclick = () => go("employee/roleplays");
      return;
    }

    const journey = state.journey || [];
    const insights = state.insights || {};
    const choiceId = state.choice?.aspiration_role || "";
    const byId = Object.fromEntries(journey.map((node) => [node.id, node]));
    const currentNode = byId.current || journey[0];
    const hasKam = Boolean(byId.kam);

    const trackCode = (node) => {
      if (!node) return "—";
      if (node.id === "current") {
        const raw = String(node.short_label || node.label || state.current || "");
        return raw.replace(/\s*RL[\d][\w\-–]*/gi, "").replace(/\s+/g, " ").trim() || (state.current === "KAM" ? "KAM" : "BD");
      }
      return String(node.short_label || node.id || "").toUpperCase();
    };

    const fullTitle = (node) => {
      if (!node) return "";
      if (node.id === "current") {
        if (state.current === "KAM") return "Key Account Manager";
        return "Business Development";
      }
      return node.label || "";
    };

    const nodeStatus = (node) => {
      if (!node) return "missing";
      if (node.state === "current") return "current";
      if (choiceId && node.id === choiceId) return "selected";
      if (node.enabled) return "eligible";
      return "locked";
    };

    const pathStroke = (fromId, toId) => {
      const from = byId[fromId];
      const to = byId[toId];
      if (!to) return { base: "#cfcfcf", glow: "transparent", lit: false };
      const st = nodeStatus(to);
      if (st === "selected") return { base: "#16a34a", glow: "#16a34a", lit: true };
      if (st === "eligible" || (from && nodeStatus(from) === "current" && to.enabled)) {
        return { base: "#1464F4", glow: "#1464F4", lit: true };
      }
      // path into locked role stays muted
      return { base: "#c5c5c5", glow: "transparent", lit: false };
    };

    const pipe = (d, style) => {
      const { base, glow, lit } = style;
      return `${lit ? `<path d="${d}" fill="none" stroke="${glow}" stroke-width="22" stroke-linecap="round" opacity="0.22"/>` : ""}
        <path d="${d}" fill="none" stroke="#e8e8e8" stroke-width="18" stroke-linecap="round"/>
        <path d="${d}" fill="none" stroke="${base}" stroke-width="8" stroke-linecap="round" opacity="${lit ? 0.95 : 0.55}"/>
        ${lit ? `<path d="${d}" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-dasharray="6 10" opacity="0.7"/>` : ""}`;
    };

    // Horizontal lattice coords (viewBox 1000×520): current left → KAM/ZM mid → RD right.
    // Always draw KAM→RD when KAM exists (backend eligibility drives glow).
    let pathsHtml = "";
    if (hasKam) {
      const bdKam = pathStroke("current", "kam");
      const bdZm = pathStroke("current", "zm");
      const kamRd = pathStroke("kam", "rd");
      const zmRd = pathStroke("zm", "rd");
      // Card centers @ x=550; ~220px wide → edges ≈ 440 / 660. Stretch SVG to stage.
      pathsHtml = [
        pipe("M 240 260 C 310 260 340 150 410 150", bdKam),
        pipe("M 240 260 C 310 260 340 370 410 370", bdZm),
        pipe("M 590 150 C 680 150 740 220 780 260", kamRd),
        pipe("M 590 370 C 680 370 740 300 780 260", zmRd),
      ].join("");
    } else {
      const bdZm = pathStroke("current", "zm");
      const zmRd = pathStroke("zm", "rd");
      pathsHtml = [
        pipe("M 240 260 C 320 260 350 370 410 370", bdZm),
        pipe("M 590 370 C 680 370 740 280 780 260", zmRd),
      ].join("");
    }

    const cardHtml = (node, slot) => {
      if (!node) return "";
      const st = nodeStatus(node);
      const code = trackCode(node);
      const title = fullTitle(node);
      const clickable = st === "eligible" && node.selectable && !state.choice;
      const slots = {
        current: "left:18%; top:50%; transform:translate(-50%,-50%)",
        kam: "left:50%; top:26%; transform:translate(-50%,-50%)",
        zm: "left:50%; top:74%; transform:translate(-50%,-50%)",
        rd: "left:82%; top:50%; transform:translate(-50%,-50%)",
      };
      if (!hasKam && node.id === "zm") slots.zm = "left:50%; top:50%; transform:translate(-50%,-50%)";

      let shell = "lattice-card bg-white/80 backdrop-blur-md border-2 shadow-sm";
      let glow = "";
      let statusBlock = "";
      if (st === "current") {
        shell += " border-[#df162b]";
        statusBlock = `<p class="text-xs font-semibold text-[#df162b] mt-2 inline-flex items-center gap-1">
          <span class="material-symbols-outlined text-[16px]" style="font-variation-settings:'FILL' 1">location_on</span>
          You are here
        </p>`;
      } else if (st === "selected") {
        shell += " border-[#16a34a] ring-2 ring-[#16a34a]/25";
        glow = "box-shadow:0 0 0 4px rgba(22,163,74,.12), 0 0 28px rgba(22,163,74,.25);";
        statusBlock = `<p class="text-xs font-bold text-[#16a34a] mt-2 uppercase tracking-wide">Selected</p>`;
      } else if (st === "eligible") {
        shell += " border-[#1464F4]";
        glow = "box-shadow:0 0 0 4px rgba(20,100,244,.10), 0 0 28px rgba(20,100,244,.22);";
        statusBlock = `<p class="text-xs font-bold text-[#1464F4] mt-2 uppercase tracking-wide">Eligible</p>`;
      } else {
        shell += " border-[#c9c9c9] opacity-90";
        statusBlock = `<p class="text-[11px] font-bold text-[#5d3f3d] mt-1.5 uppercase tracking-wide">Locked</p>`;
      }

      const pin = st === "current"
        ? `<div class="absolute -left-7 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-[#df162b] grid place-items-center shadow-md shadow-[#df162b]/35">
            <span class="material-symbols-outlined text-white text-[14px]" style="font-variation-settings:'FILL' 1">location_on</span>
          </div>`
        : "";
      const lockOverlay = st === "locked"
        ? `<div class="absolute inset-0 grid place-items-center pointer-events-none">
            <span class="material-symbols-outlined text-4xl text-[#9ca3af]/85" style="font-variation-settings:'FILL' 1">lock</span>
          </div>`
        : "";
      const corner = st === "current"
        ? `<span class="absolute top-1.5 right-1.5 w-2.5 h-2.5 rounded-full border-2 border-[#df162b]"></span>`
        : st === "locked"
          ? `<span class="absolute top-1.5 right-1.5 text-[9px] font-bold uppercase text-[#5d3f3d] bg-[#f2f2f2] px-1 py-0.5 rounded">Locked</span>`
          : "";

      return `<div class="absolute z-20" style="${slots[slot] || slots.current}">
        <button type="button" data-path="${esc(node.id)}" data-label="${esc(node.label || title)}"
          ${clickable ? "" : "disabled"}
          class="${shell} relative w-[148px] sm:w-[160px] rounded-xl p-3 text-left transition-transform ${clickable ? "cursor-pointer hover:scale-[1.03]" : "cursor-default"}"
          style="${glow}">
          ${pin}${corner}${lockOverlay}
          <p class="text-2xl font-extrabold tracking-tight leading-none ${st === "locked" ? "text-[#9ca3af]" : "text-[#291716]"}">${esc(code)}</p>
          <p class="text-[11px] text-[#5d3f3d] mt-1 leading-snug">${esc(title)}</p>
          ${statusBlock}
        </button>
      </div>`;
    };

    const tips = (insights.tips || []).map((tip) => `<li class="flex items-start gap-2">
      <div class="w-6 h-6 rounded-full bg-[#d5e3ff] grid place-items-center shrink-0 mt-0.5">
        <span class="material-symbols-outlined text-[#1464F4] text-[16px]">info</span>
      </div>
      <p class="text-sm text-[#291716]">${esc(tip)}</p>
    </li>`).join("");

    const cards = [
      cardHtml(currentNode, "current"),
      hasKam ? cardHtml(byId.kam, "kam") : "",
      cardHtml(byId.zm, "zm"),
      cardHtml(byId.rd, "rd"),
    ].join("");

    render(`<style>
      .lattice-stage{
        position:relative;width:100%;min-height:400px;border-radius:1rem;overflow:hidden;
        padding:1.5rem 2.25rem;box-sizing:border-box;
        background:
          linear-gradient(180deg,#fafafa 0%,#f2f2f2 100%);
      }
      .lattice-stage::before{
        content:"";position:absolute;inset:0;opacity:.35;pointer-events:none;
        background-image:
          linear-gradient(#d0d0d0 1px,transparent 1px),
          linear-gradient(90deg,#d0d0d0 1px,transparent 1px);
        background-size:48px 48px;
        mask-image:radial-gradient(ellipse at center, #000 40%, transparent 85%);
      }
      .lattice-card{border-radius:12px}
    </style>
    <section class="bg-white border border-[#e7bdb9] rounded-xl p-5 md:p-6 flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6 shadow-sm">
      <div>
        <h1 class="text-xl md:text-2xl font-extrabold text-[#291716]">My Path</h1>
        <p class="text-sm text-[#5d3f3d] mt-1">Career lattice from Probable Career Paths — blue = eligible, green = selected, grey = locked.</p>
      </div>
      <div class="text-sm font-bold text-[#df162b] bg-[#fff0ef] border border-[#e7bdb9] rounded-lg px-4 py-2">
        ${esc(trackCode(currentNode))}
        ${state.current === "KAM" || /kam/i.test(String(state.current_label || ""))
          ? ` · ${esc(state.designation || "Key Account Manager")}`
          : (state.designation ? ` · ${esc(state.designation)}` : "")}
      </div>
    </section>
    <div class="grid grid-cols-12 gap-6 items-start">
      <div class="col-span-12 xl:col-span-9">
        <div class="lattice-stage border border-[#e0e0e0] shadow-sm">
          <svg class="absolute inset-0 w-full h-full" viewBox="0 0 1000 520" preserveAspectRatio="none" aria-hidden="true">
            ${pathsHtml}
          </svg>
          ${cards}
        </div>
        <div class="flex flex-wrap gap-5 pt-4 mt-3">
          <div class="flex items-center gap-2"><div class="w-4 h-4 rounded-full bg-[#df162b] border-2 border-white shadow-sm"></div><span class="text-xs font-semibold text-[#291716]">You are here</span></div>
          <div class="flex items-center gap-2"><div class="w-4 h-4 rounded-full bg-[#1464F4] border-2 border-white shadow-sm"></div><span class="text-xs font-semibold text-[#291716]">Eligible</span></div>
          <div class="flex items-center gap-2"><div class="w-4 h-4 rounded-full bg-[#16a34a] border-2 border-white shadow-sm"></div><span class="text-xs font-semibold text-[#291716]">Selected</span></div>
          <div class="flex items-center gap-2"><div class="w-4 h-4 rounded-full bg-[#c9c9c9] border-2 border-white shadow-sm"></div><span class="text-xs font-semibold text-[#5d3f3d]">Locked</span></div>
          ${state.choice
            ? `<p class="ml-auto text-xs font-bold text-[#16a34a]">Aspiration locked — Admin reset required</p>`
            : `<p class="ml-auto text-xs font-semibold text-[#5d3f3d]">Tap an eligible role to lock aspiration</p>`}
        </div>
      </div>
      <div class="col-span-12 xl:col-span-3 space-y-5">
        <div class="bg-white border border-[#e7bdb9] rounded-xl p-5 shadow-sm">
          <div class="flex items-center gap-2 mb-3"><span class="material-symbols-outlined text-[#1464F4]">insights</span><h3 class="font-bold text-[#291716]">Role Insight</h3></div>
          <div class="space-y-3">
            <div class="p-3 bg-[#eff6ff] border-l-4 border-[#1464F4] rounded-r-lg">
              <p class="text-[11px] font-bold uppercase text-[#1464F4] mb-1">Growth Potential</p>
              <p class="text-sm text-[#291716]">${esc(insights.growth || "")}</p>
            </div>
            <div class="p-3 bg-[#fff8f7] border-l-4 border-[#e7bdb9] rounded-r-lg">
              <p class="text-[11px] font-bold uppercase text-[#5d3f3d] mb-1">Key Competency</p>
              <p class="text-sm text-[#291716]">${esc(insights.key_competency || "")}</p>
            </div>
          </div>
        </div>
        <div class="bg-white border border-[#e7bdb9] rounded-xl p-5 shadow-sm">
          <div class="flex items-center gap-2 mb-4"><span class="material-symbols-outlined text-[#1464F4]">tips_and_updates</span><h3 class="font-bold text-[#291716]">Route Guide</h3></div>
          <ul class="space-y-3">${tips || `<li class="text-sm text-[#5d3f3d]">No guidance yet.</li>`}</ul>
        </div>
      </div>
    </div>`);

    qsa("[data-path]").forEach((control) => {
      if (control.disabled) return;
      control.onclick = async () => {
        if (!confirm(`Lock aspiration: ${control.dataset.label}? Only Admin can reset it.`)) return;
        try {
          await api("/api/employee/career", { method: "POST", body: JSON.stringify({ aspiration_role: control.dataset.path }) });
          toast("Aspiration locked.");
          go("employee/courses");
        } catch (error) {
          toast(error.message, "error");
        }
      };
    });
  }

  let basket = new Map();
  let curatedOtherSources = {};

  function parseDurationSeconds(value) {
    const text = String(value || "").trim();
    if (!text) return 0;
    if (/^\d+m$/i.test(text)) return Number(text.replace(/m/i, "")) * 60;
    const parts = text.split(":").map((part) => Number(part));
    if (parts.some((part) => Number.isNaN(part))) return 0;
    if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
    if (parts.length === 2) return parts[0] * 60 + parts[1];
    return 0;
  }

  function hoursLeftLabel(course) {
    const status = course.status || "not_started";
    if (status === "completed") return "0.0h left";
    let totalSec = parseDurationSeconds(course.duration);
    if (!totalSec && course.duration_minutes) totalSec = Number(course.duration_minutes) * 60;
    if (!totalSec) return "—";
    const pct = Math.max(0, Math.min(100, Number(course.progress_pct || 0)));
    const leftSec = Math.round(totalSec * (1 - pct / 100));
    return `${(leftSec / 3600).toFixed(1)}h left`;
  }

  function otherSourcesFor(competency) {
    const picks = curatedOtherSources[competency] || [];
    const meta = [
      { kind: "youtube", label: "YouTube", icon: "smart_display", iconClass: "text-[#df162b]" },
      { kind: "case_study", label: "Case Study", icon: "description", iconClass: "text-[#1464F4]" },
      { kind: "tedx", label: "TEDx Talk", icon: "podcasts", iconClass: "text-[#005f81]" },
    ];
    return meta.map((item) => {
      const pick = picks.find((row) => row.kind === item.kind)
        || picks.find((row) => item.kind === "tedx" && ["webinar", "ted", "tedx_talk"].includes(row.kind));
      const title = pick?.title || `${competency} ${item.label}`;
      const url = pick?.url || "";
      return {
        ...item,
        id: pick?.id || `other:${item.kind}:${competency}`,
        competency,
        source: "other",
        title,
        url,
        duration_minutes: pick?.duration_minutes,
      };
    });
  }

  function otherSourcesBlock(competency) {
    return `<div class="mt-5 pt-4 border-t border-[#e7bdb9]/60">
      <div class="flex flex-wrap items-baseline justify-between gap-2 mb-3">
        <h3 class="text-sm font-bold text-[#291716]">Other Sources &amp; Case Studies</h3>
        <span class="text-[10px] font-bold uppercase tracking-wide text-[#5d3f3d]">Optional</span>
      </div>
      <p class="text-xs text-[#5d3f3d] mb-3">Add to your basket anytime. Not required per skill — LinkedIn courses are the only mandatory picks.</p>
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
        ${otherSourcesFor(competency).map((item) => {
          const inBasket = basket.has(item.id);
          const thumb = otherSourceThumb({ ...item, source: "other" });
          return `<div class="bg-[#fff8f7] rounded-lg border border-[#e7bdb9] overflow-hidden flex flex-col ${inBasket ? "ring-1 ring-[#1464F4]" : ""}">
            <div class="h-24 w-full relative bg-[#fff0ef] overflow-hidden">
              <img class="w-full h-full object-cover" alt="" src="${esc(thumb)}" loading="lazy" referrerpolicy="no-referrer"/>
              <div class="absolute bottom-2 left-2 bg-[#5d3f3d]/90 text-white px-2 py-0.5 rounded text-[10px] font-bold uppercase">${esc(item.label)}</div>
            </div>
            <div class="p-3 flex flex-col gap-2 flex-grow">
              <p class="text-sm font-bold text-[#291716] flex-grow">${esc(item.title)}</p>
              <button type="button" data-course="${esc(item.id)}" data-competency="${esc(competency)}" data-title="${esc(item.title)}" data-source="other" data-kind="${esc(item.kind)}" data-url="${esc(item.url || "")}" data-duration-minutes="${esc(item.duration_minutes || "")}"
                class="w-full px-3 py-2 rounded-lg font-bold text-xs ${inBasket ? "bg-[#5d3f3d] text-white cursor-not-allowed" : "bg-[#1464F4] text-white hover:opacity-90"}"
                ${inBasket ? "disabled" : ""}>${inBasket ? "Added" : "Add to Cart"}</button>
            </div>
          </div>`;
        }).join("")}
      </div>
    </div>`;
  }

  function youtubeThumbFromUrl(url) {
    const match = String(url || "").match(/(?:youtube\.com\/(?:watch\?(?:[^#]*&)?v=|embed\/|shorts\/)|youtu\.be\/)([A-Za-z0-9_-]{6,11})/i);
    return match ? `https://img.youtube.com/vi/${match[1]}/hqdefault.jpg` : "";
  }

  function stablePick(seedText, pool) {
    let hash = 0;
    const text = String(seedText || "course");
    for (let i = 0; i < text.length; i += 1) hash = ((hash << 5) - hash) + text.charCodeAt(i);
    const index = Math.abs(hash) % pool.length;
    return pool[index];
  }

  function otherSourceThumb(course) {
    if (course.thumbnail) return course.thumbnail;
    const fromYt = youtubeThumbFromUrl(course.url);
    if (fromYt) return fromYt;
    const kind = String(course.kind || "").toLowerCase().replace(/\s+/g, "_");
    const pools = {
      case_study: [
        "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&w=640&h=360&q=80",
        "https://images.unsplash.com/photo-1553877522-43269d4ea984?auto=format&fit=crop&w=640&h=360&q=80",
        "https://images.unsplash.com/photo-1507679799987-c73779587ccf?auto=format&fit=crop&w=640&h=360&q=80",
        "https://images.unsplash.com/photo-1521737604893-d14cc237f11d?auto=format&fit=crop&w=640&h=360&q=80",
      ],
      tedx: [
        "https://images.unsplash.com/photo-1475721027785-f74eccf877e2?auto=format&fit=crop&w=640&h=360&q=80",
        "https://images.unsplash.com/photo-1540575467063-178a50c2df87?auto=format&fit=crop&w=640&h=360&q=80",
        "https://images.unsplash.com/photo-1505373877841-8d25f7d46678?auto=format&fit=crop&w=640&h=360&q=80",
        "https://images.unsplash.com/photo-1591115765373-5207764f72e7?auto=format&fit=crop&w=640&h=360&q=80",
      ],
      youtube: [
        "https://images.unsplash.com/photo-1611162616475-46b635cb6868?auto=format&fit=crop&w=640&h=360&q=80",
        "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=640&h=360&q=80",
        "https://images.unsplash.com/photo-1485846234645-a62644f84728?auto=format&fit=crop&w=640&h=360&q=80",
        "https://images.unsplash.com/photo-1492619375914-88005aa9e8fb?auto=format&fit=crop&w=640&h=360&q=80",
      ],
    };
    const pool = pools[kind] || pools.case_study;
    return stablePick(`${course.id || ""}|${course.title || ""}|${kind}`, pool);
  }

  function courseThumb(course) {
    const isOther = course.source === "other" || String(course.id || course.course_id || "").startsWith("other:");
    const src = course.thumbnail || (isOther ? otherSourceThumb(course) : "") || youtubeThumbFromUrl(course.url);
    return src
      ? `<img class="w-full h-full object-cover" alt="" src="${esc(src)}" loading="lazy" referrerpolicy="no-referrer">`
      : `<div class="w-full h-full bg-gradient-to-br from-[#ffe1df] to-[#d5e3ff] flex items-center justify-center"><span class="material-symbols-outlined text-4xl text-[#df162b]">school</span></div>`;
  }

  function courseCard(course, competency) {
    const provider = course.provider || course.source_type || "LinkedIn Learning";
    const priceLabel = /mmt|internal/i.test(provider) ? "Internal Course" : "Recommended";
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
      const linkedInCount = lockedCourses.filter((course) => !(course.source === "other" || String(course.id || "").startsWith("other:"))).length;
      const otherCount = lockedCourses.length - linkedInCount;
      render(`<div class="mb-6">
          <h1 class="text-2xl md:text-3xl font-extrabold text-[#df162b]">Shop Your Courses</h1>
          <p class="text-[#5d3f3d] mt-1">Your learning journey is locked. Course selection can no longer be changed.</p>
        </div>
        <div class="bg-white border border-[#e7bdb9] rounded-xl p-8 max-w-2xl">
          <div class="flex items-start gap-4">
            <span class="material-symbols-outlined text-[#df162b] text-4xl" style="font-variation-settings:'FILL' 1">lock</span>
            <div>
              <h2 class="text-xl font-bold text-[#291716]">Journey locked</h2>
              <p class="text-sm text-[#5d3f3d] mt-2">${linkedInCount} LinkedIn course${linkedInCount === 1 ? "" : "s"}${otherCount ? ` · ${otherCount} other source${otherCount === 1 ? "" : "s"}` : ""} locked in your learning journey.</p>
              <p class="text-sm text-[#5d3f3d] mt-2">Ask Admin to reset courses if you need to shop again.</p>
              <div class="mt-5 flex flex-wrap gap-2">
                ${button("Open Learning Journey", "data-open-learning")}
              </div>
            </div>
          </div>
        </div>`);
      qs("[data-open-learning]")?.addEventListener("click", () => go("employee/learning"));
      return;
    }

    const gaps = result.target?.gaps || [];
    const entries = Object.entries(result.competencies || {});
    curatedOtherSources = result.other_sources || {};
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

    const isExplore = result.target?.mode === "future_role";
    const sections = entries.map(([competency, courses]) => {
      return `<section class="mb-8">
        <div class="flex flex-wrap items-center gap-2 mb-4">
          <h2 class="text-xl font-bold text-[#291716]">${esc(competency)}</h2>
          <span class="bg-[#df162b] text-white text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider">${isExplore ? "Explore" : "Gap Identified"}</span>
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
              <p class="text-sm mt-1">${result.target?.mode === "future_role"
                ? "You're thriving in your current role. Now, explore the journey toward your aspiration role. Please add at least <strong>1 LinkedIn course per skill</strong>. Other sources are optional."
                : `You're going great! However, we have identified ${gapCount} focus area${gapCount === 1 ? "" : "s"}. Please add at least <strong>1 LinkedIn course per gap</strong>. Other sources are optional.`}</p>
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
          url: control.dataset.url || "",
          duration_minutes: control.dataset.durationMinutes || "",
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

    // Gap requirements: LinkedIn only. Other sources optional — never block checkout.
    const linkedInItems = items.filter((item) => item.source !== "other" && !String(item.id || "").startsWith("other:"));
    const otherItems = items.filter((item) => item.source === "other" || String(item.id || "").startsWith("other:"));
    const covered = new Set(linkedInItems.map((item) => item.competency));
    if (reqNode) {
      reqNode.innerHTML = `${required.map((competency) => {
        const done = covered.has(competency);
        return `<div class="flex items-center gap-2">
          <span class="material-symbols-outlined text-sm ${done ? "text-green-600" : "text-[#5d3f3d]"}">${done ? "check_circle" : "radio_button_unchecked"}</span>
          <span class="text-sm ${done ? "text-[#291716] font-semibold" : "text-[#5d3f3d]"}">1 LinkedIn · ${esc(competency)}</span>
        </div>`;
      }).join("")}
      <p class="text-xs text-[#5d3f3d] pt-2 border-t border-[#e7bdb9] mt-2">${otherItems.length
        ? `${otherItems.length} other source${otherItems.length === 1 ? "" : "s"} in basket (optional)`
        : "Other sources optional — add from below each skill"}</p>`;
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
        const courseIds = linkedInItems.map((item) => item.id);
        const otherSources = otherItems.map((item) => ({
          id: item.id,
          competency: item.competency,
          title: item.title,
          kind: item.kind || "",
          url: item.url || "",
          duration_minutes: item.duration_minutes || "",
        }));
        await api("/api/employee/learning/checkout", {
          method: "POST",
          body: JSON.stringify({ course_ids: courseIds, other_sources: otherSources }),
        });
        basket = new Map();
        toast(otherSources.length
          ? `Journey locked with ${courseIds.length} LinkedIn + ${otherSources.length} other source(s).`
          : "Journey locked. LinkedIn courses saved.");
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
          <p class="text-[#5d3f3d] mt-1">Track your progress across your identified gaps and unlock your full potential.</p>
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
      const isOther = course.source === "other" || String(courseId || "").startsWith("other:");
      const kindLabel = String(course.kind || "").replaceAll("_", " ");
      const provider = isOther
        ? (kindLabel || course.provider || "Other source")
        : (course.source_type || "LinkedIn Learning");
      const isMmt = !isOther && /mmt|academy|internal/i.test(provider);
      const timeLeft = hoursLeftLabel(course);
      const kindNorm = String(course.kind || "").toLowerCase();
      const providerLabel = isOther
        ? (kindNorm === "tedx" || kindNorm === "ted" || kindNorm === "webinar" ? "TEDx Talk" : (kindLabel || course.provider || "Other source"))
        : provider;
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
      const primaryLabel = status === "in_progress" ? "Continue" : "Start";
      const actions = status === "completed"
        ? (course.url
          ? `<a href="${esc(course.url)}" target="_blank" rel="noopener" class="px-4 py-1.5 border border-[#df162b] text-[#df162b] rounded-lg font-bold text-sm hover:bg-[#df162b]/5">Review</a>`
          : `<span class="text-sm text-[#5d3f3d]">Done</span>`)
        : `<div class="flex flex-wrap gap-2 justify-end">
            <button type="button" data-progress-action="launch" data-course-id="${esc(courseId)}" data-url="${esc(course.url || "")}" class="px-4 py-1.5 bg-[#df162b] text-white rounded-lg font-bold text-sm hover:opacity-90">${primaryLabel}</button>
            ${isOther && status === "in_progress" ? `<button type="button" data-progress-action="complete" data-course-id="${esc(courseId)}" class="px-4 py-1.5 border border-[#1464F4] text-[#1464F4] rounded-lg font-bold text-sm">Mark Complete</button>` : ""}
          </div>`;
      return `<article class="bg-white rounded-xl border border-[#e7bdb9] overflow-hidden hover:shadow-md transition-all">
        <div class="h-36 w-full bg-[#fff0ef] relative overflow-hidden">${courseThumb(course)}
          <div class="absolute top-2 right-2 bg-white/90 px-2 py-1 rounded-lg text-[10px] font-bold text-[#291716] flex items-center gap-1">
            <span class="material-symbols-outlined text-sm">timer</span> ${esc(timeLeft)}
          </div>
          <div class="absolute bottom-2 left-2 ${isOther ? "bg-[#5d3f3d]" : isMmt ? "bg-[#df162b]" : "bg-[#0077b5]"} text-white px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider">${esc(providerLabel)}</div>
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
      const linkedIn = list.filter((course) => !(course.source === "other" || String(course.id || course.course_id || "").startsWith("other:")));
      const others = list.filter((course) => course.source === "other" || String(course.id || course.course_id || "").startsWith("other:"));
      return `<div class="mb-10">
        <div class="flex flex-wrap items-end justify-between gap-3 mb-5 border-b border-[#e7bdb9] pb-3">
          <div>
            <h2 class="text-lg font-bold text-[#291716] flex items-center gap-2">
              <span class="material-symbols-outlined text-[#1464F4]" style="font-variation-settings:'FILL' 1">insights</span>
              ${esc(competency)}
            </h2>
          </div>
          <span class="text-sm text-[#5d3f3d]">${linkedIn.length} LinkedIn${others.length ? ` · ${others.length} other` : ""}</span>
        </div>
        ${linkedIn.length ? `<div class="mb-4"><h3 class="text-sm font-bold text-[#291716] mb-3">LinkedIn courses</h3><div class="grid md:grid-cols-2 gap-5">${journeyCards(linkedIn)}</div></div>` : ""}
        ${others.length ? `<div class="mt-6"><h3 class="text-sm font-bold text-[#291716] mb-3">Other sources</h3><div class="grid md:grid-cols-2 gap-5">${journeyCards(others)}</div></div>` : ""}
      </div>`;
    }).join("");

    render(`<section class="mb-8">
        <h1 class="text-2xl md:text-3xl font-extrabold text-[#df162b] mb-1">Your Learning Journey</h1>
        <p class="text-[#5d3f3d]">Track your progress across your identified gaps and unlock your full potential.</p>
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
            <h3 class="text-xl font-bold text-[#291716] mb-2">Learning Completion Status: ${completed}/${total} Courses</h3>
            <p class="text-sm text-[#5d3f3d] mb-4">${pct === 100
              ? "All locked courses are complete. Keep applying what you learned on the job."
              : `Start courses to track progress.`}</p>
            <div class="w-full bg-[#ffe1df] h-3 rounded-full overflow-hidden">
              <div class="bg-[#df162b] h-full rounded-full" style="width:${pct}%"></div>
            </div>
            <p class="text-xs text-[#5d3f3d] mt-2">Progress from saved course status</p>
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

  function lbInitials(name) {
    return String(name || "?")
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() || "")
      .join("") || "?";
  }

  function lbBadgeIcons(rowBadges, catalog) {
    const list = rowBadges || [];
    if (!list.length) return `<span class="text-[#926e6c]">—</span>`;
    return `<div class="flex flex-wrap gap-1 justify-center">${list.slice(0, 4).map((badge) => {
      const cat = catalog.find((item) => item.id === badge.id);
      return `<span class="inline-flex items-center justify-center w-6 h-6 rounded-full bg-[#eff6ff] text-[#005cab]" title="${esc(badge.title)}">
        <span class="material-symbols-outlined text-[14px]" style="font-variation-settings:'FILL' 1">${esc(cat?.icon || "military_tech")}</span>
      </span>`;
    }).join("")}${list.length > 4 ? `<span class="text-[10px] text-[#5d3f3d]">+${list.length - 4}</span>` : ""}</div>`;
  }

  async function initLeaderboard() {
    const payload = await api("/api/leaderboard");
    const role = session.user?.role;
    if (role === "admin") return initAdminLeaderboard(payload);
    if (role === "zm" || role === "rd") return initManagerLeaderboard(payload, role);
    return initEmployeeLeaderboard(payload);
  }

  function initEmployeeLeaderboard(payload) {
    const rows = payload.leaderboard || [];
    const viewer = payload.viewer || {};
    const badges = payload.badges || [];
    const catalog = payload.badge_catalog || [];
    const earnedIds = new Set(badges.map((badge) => badge.id));
    const meCode = viewer.employee_code || session.user?.employee_code || "";
    const gaps = viewer.gaps || [];
    const intensityWidth = { High: 75, Med: 45, Low: 20 };
    const intensityColor = { High: "bg-[#df162b]", Med: "bg-[#005cab]", Low: "bg-[#926e6c]" };

    const cohortCard = `<div class="bg-white border border-[#e7bdb9] rounded-xl p-5 relative overflow-hidden flex flex-col justify-between">
      <div class="absolute top-0 right-0 w-28 h-28 bg-[#fddbd8] rounded-bl-full opacity-30 -mr-8 -mt-8 pointer-events-none"></div>
      <div>
        <p class="text-[11px] font-bold uppercase tracking-wide text-[#005cab]">Your Cohort</p>
        <h2 class="text-4xl font-extrabold text-[#291716] mt-3 tracking-tight">${viewer.rank != null ? `Rank #${viewer.rank}` : "Unranked"}</h2>
        <p class="text-sm text-[#5d3f3d] mt-2 flex items-center gap-1">
          <span class="material-symbols-outlined text-[16px]">groups</span>
          Competing with peers on LinkedIn hours
        </p>
      </div>
      <div class="mt-6 pt-4 border-t border-[#e7bdb9] flex justify-between items-end gap-3">
        <p class="text-sm text-[#5d3f3d]">Focus areas: <strong class="text-[#291716]">${viewer.focus_areas ?? "—"}</strong></p>
        <div class="text-right">
          <p class="text-[11px] font-bold uppercase text-[#5d3f3d]">Ranked by</p>
          <p class="text-sm font-bold text-[#291716]">LinkedIn hours</p>
        </div>
      </div>
    </div>`;

    const pulseCard = `<div class="bg-white border border-[#e7bdb9] rounded-xl p-5 flex flex-col justify-between">
      <div>
        <p class="text-[11px] font-bold uppercase tracking-wide text-[#5d3f3d] flex items-center gap-1">
          <span class="material-symbols-outlined text-[16px]">show_chart</span> Growth Pulse
        </p>
        <h3 class="text-2xl font-extrabold text-[#291716] mt-2">${Number(viewer.learning_hours || 0).toFixed(1)}h</h3>
        <p class="text-sm text-[#5d3f3d]">LinkedIn learning hours</p>
      </div>
      <svg class="w-full h-14 mt-4 overflow-visible" viewBox="0 0 100 30" aria-hidden="true">
        <path d="M0,25 Q10,20 20,22 T40,15 T60,18 T80,5 T100,2" fill="none" stroke="#005cab" stroke-width="2"></path>
        <circle cx="100" cy="2" fill="#005cab" r="3"></circle>
      </svg>
    </div>`;

    const weakSkills = `<div class="bg-white border border-[#e7bdb9] rounded-xl p-5 flex flex-col">
      <p class="text-[11px] font-bold uppercase tracking-wide text-[#5d3f3d] flex items-center gap-1">
        <span class="material-symbols-outlined text-[16px]">track_changes</span> Weak Skills
      </p>
      <div class="mt-4 space-y-3 flex-1 flex flex-col justify-end">
        ${gaps.length
          ? gaps.slice(0, 3).map((gap) => {
            const intensity = gap.intensity || "Low";
            return `<div>
              <div class="text-[11px] font-semibold mb-1 text-[#291716]">${esc(gap.competency)}</div>
              <div class="w-full bg-[#ffe1df] rounded-full h-1.5 overflow-hidden">
                <div class="${intensityColor[intensity] || intensityColor.Low} h-1.5 rounded-full" style="width:${intensityWidth[intensity] || 20}%"></div>
              </div>
            </div>`;
          }).join("")
          : `<p class="text-sm text-[#5d3f3d]">No focus gaps — keep stacking hours.</p>`}
      </div>
    </div>`;

    const badgeShelf = `<div class="mb-8">
      <h3 class="text-lg font-bold text-[#291716] mb-3">Badge shelf</h3>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        ${catalog.map((badge) => {
          const earned = earnedIds.has(badge.id);
          const mine = badges.find((item) => item.id === badge.id);
          const tier = mine?.meta?.tier;
          return `<div class="bg-white border rounded-xl p-4 flex flex-col items-center text-center ${earned ? "border-[#005cab] bg-[#eff6ff]" : "border-[#e7bdb9] opacity-70"}">
            <div class="w-12 h-12 rounded-full ${earned ? "bg-[#0075d7] text-white" : "bg-[#ffe1df] text-[#5d3f3d]"} flex items-center justify-center mb-3">
              <span class="material-symbols-outlined" style="font-variation-settings:'FILL' ${earned ? 1 : 0}">${esc(badge.icon || "military_tech")}</span>
            </div>
            <strong class="text-sm text-[#291716]">${esc(badge.title)}${tier ? ` ×${tier}` : ""}</strong>
            <p class="text-[11px] text-[#5d3f3d] mt-1">${esc(badge.rule)}</p>
            <span class="text-[10px] font-bold uppercase tracking-wider mt-3 ${earned ? "text-[#005cab]" : "text-[#926e6c]"}">${earned ? "Earned" : "Locked"}</span>
          </div>`;
        }).join("")}
      </div>
    </div>`;

    render(`${pageHeader("Learning Leaderboard", "Compete with peers in your cohort. Focus areas show how many skills need work.")}
      <div class="grid grid-cols-1 md:grid-cols-12 gap-4 mb-8">
        <div class="md:col-span-6">${cohortCard}</div>
        <div class="md:col-span-3">${pulseCard}</div>
        <div class="md:col-span-3">${weakSkills}</div>
      </div>
      ${badgeShelf}
      <h3 class="text-lg font-bold text-[#291716] mb-3">Peer Rankings</h3>
      <div class="overflow-x-auto bg-white border border-[#e7bdb9] rounded-xl">
        <table class="w-full min-w-[640px] text-sm text-left">
          <thead class="bg-[#ffe9e7] text-[11px] uppercase tracking-wider text-[#5d3f3d]">
            <tr>
              <th class="p-4">Rank</th>
              <th class="p-4">Employee</th>
              <th class="p-4">Focus Areas</th>
              <th class="p-4">LinkedIn Hours</th>
              <th class="p-4 hidden sm:table-cell">Courses</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map((row) => {
              const mine = meCode && row.employee_code === meCode;
              return `<tr class="border-t border-[#e7bdb9] ${mine ? "bg-[#eff6ff] border-l-4 border-l-[#005cab]" : "hover:bg-[#fff0ef]"}">
                <td class="p-4 font-bold text-[#005cab]">#${row.rank}</td>
                <td class="p-4">
                  <div class="flex items-center gap-2">
                    <strong class="text-[#291716]">${esc(row.name)}</strong>
                    ${mine ? `<span class="bg-[#df162b] text-white text-[10px] font-bold uppercase px-1.5 py-0.5 rounded">You</span>` : ""}
                  </div>
                  <div class="text-xs text-[#5d3f3d]">${esc(row.employee_code)}</div>
                </td>
                <td class="p-4 ${mine ? "font-bold" : ""}">${row.focus_areas}</td>
                <td class="p-4 font-bold">${Number(row.learning_hours).toFixed(1)}h</td>
                <td class="p-4 hidden sm:table-cell ${mine ? "font-bold" : ""}">${Number(row.completions || 0)}</td>
              </tr>`;
            }).join("") || empty("Leaderboard empty until final profiles exist.", 5)}
          </tbody>
        </table>
      </div>`);
  }

  function initManagerLeaderboard(payload, role) {
    const rows = payload.leaderboard || [];
    const stats = payload.stats || {};
    const catalog = payload.badge_catalog || [];
    const titleScope = role === "rd" ? "Regional" : "Zonal";
    let searchTerm = "";
    let searchRaw = "";

    const draw = () => {
      const list = rows.filter((row) => {
        if (!searchTerm) return true;
        return [row.employee_code, row.name].some((value) => String(value || "").toLowerCase().includes(searchTerm));
      });
      const focusMax = Math.max(1, ...(stats.focus_area_distribution || []).map((row) => row.count), 0);
      const hoursMax = Math.max(1, ...(stats.hours_buckets || []).map((row) => row.count), 0);
      const badgeRows = (stats.badge_distribution || []).slice(0, 5);
      const badgeTotal = badgeRows.reduce((sum, row) => sum + Number(row.count || 0), 0);
      const badgeColors = ["#0075d7", "#df162b", "#7bd0fe", "#005cab", "#926e6c"];

      render(`${pageHeader("Learning Leaderboard", `${titleScope} performance and competency calibration metrics.`)}
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-4 mb-6">
          <div class="lg:col-span-8 bg-white border border-[#e7bdb9] rounded-xl p-5">
            <div class="flex justify-between items-end gap-3 mb-4 flex-wrap">
              <div>
                <h3 class="text-lg font-bold text-[#291716]">${titleScope} Learning Pulse</h3>
                <p class="text-sm text-[#5d3f3d] mt-1">LinkedIn hours mix across your team</p>
              </div>
              <div class="text-right">
                <p class="text-3xl font-extrabold text-[#005cab]">${Number(stats.total_hours || 0).toFixed(0)}</p>
                <p class="text-xs text-[#5d3f3d]">Total hours · ${stats.team_size || 0} people</p>
              </div>
            </div>
            <div class="flex items-end gap-2 h-40">
              ${(stats.hours_buckets || []).map((bucket) => {
                const height = Math.max(8, Math.round((bucket.count / hoursMax) * 100));
                return `<div class="flex-1 flex flex-col items-center gap-2 h-full justify-end">
                  <div class="w-full max-w-[48px] bg-[#a6c8ff] hover:bg-[#0075d7] rounded-t transition-colors relative group" style="height:${height}%">
                    <span class="absolute -top-7 left-1/2 -translate-x-1/2 text-[10px] font-bold text-[#291716] opacity-0 group-hover:opacity-100 whitespace-nowrap">${bucket.count}</span>
                  </div>
                  <span class="text-[10px] text-[#926e6c]">${esc(bucket.label)}</span>
                </div>`;
              }).join("") || `<p class="text-sm text-[#5d3f3d]">No learning activity yet.</p>`}
            </div>
          </div>
          <div class="lg:col-span-4 bg-white border border-[#e7bdb9] rounded-xl p-5 flex flex-col">
            <h3 class="text-lg font-bold text-[#291716]">Milestone Badges</h3>
            <p class="text-sm text-[#5d3f3d] mb-4">Earned badges across your roster</p>
            <div class="flex-1 flex items-center justify-center py-4">
              <div class="relative w-28 h-28 rounded-full border-[14px] border-[#ffe1df] flex items-center justify-center">
                <div class="text-center">
                  <p class="text-2xl font-extrabold text-[#291716]">${badgeTotal}</p>
                  <p class="text-[10px] font-bold uppercase text-[#5d3f3d]">Total</p>
                </div>
              </div>
            </div>
            <div class="space-y-2 mt-2">
              ${badgeRows.map((row, index) => {
                const pct = badgeTotal ? Math.round((row.count / badgeTotal) * 100) : 0;
                return `<div class="flex justify-between items-center text-sm gap-2">
                  <div class="flex items-center gap-2 min-w-0">
                    <span class="w-3 h-3 rounded-full shrink-0" style="background:${badgeColors[index % badgeColors.length]}"></span>
                    <span class="truncate text-[#291716]">${esc(row.name)}</span>
                  </div>
                  <span class="font-bold text-[#5d3f3d] shrink-0">${pct}%</span>
                </div>`;
              }).join("") || `<p class="text-xs text-[#5d3f3d]">No badges earned yet.</p>`}
            </div>
          </div>
          <div class="lg:col-span-12 bg-white border border-[#e7bdb9] rounded-xl p-5">
            <h3 class="text-lg font-bold text-[#291716] mb-4">Focus areas distribution</h3>
            <div class="grid md:grid-cols-2 gap-x-8 gap-y-3">
              ${(stats.focus_area_distribution || []).map((row) => `
                <div>
                  <div class="flex justify-between text-sm mb-1">
                    <span class="text-[#291716]">${row.focus_areas} focus area${row.focus_areas === 1 ? "" : "s"}</span>
                    <span class="font-bold text-[#005cab]">${row.count} people</span>
                  </div>
                  <div class="h-2 bg-[#ffe1df] rounded-full overflow-hidden">
                    <div class="h-full bg-[#0075d7] rounded-full" style="width:${Math.round((row.count / focusMax) * 100)}%"></div>
                  </div>
                </div>`).join("") || `<p class="text-sm text-[#5d3f3d]">No rated profiles yet.</p>`}
            </div>
            <p class="text-xs text-[#5d3f3d] mt-4">${stats.journey_locked_pct || 0}% journeys locked · avg ${Number(stats.avg_hours || 0).toFixed(1)}h</p>
          </div>
        </div>
        <div class="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h3 class="text-lg font-bold text-[#291716]">Team leaderboards</h3>
            <p class="text-xs text-[#5d3f3d] mt-0.5">Separate rankings per gap-severity band · ranked by LinkedIn hours</p>
          </div>
          <label class="relative block">
            <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[#926e6c] text-[18px]">search</span>
            <input data-lb-search value="${esc(searchRaw)}" class="pl-10 pr-4 py-2 border border-[#e7bdb9] rounded-full text-sm w-full sm:w-64 outline-none focus:border-[#005cab]" placeholder="Search employees...">
          </label>
        </div>
        <div class="space-y-6">
          ${(() => {
            const grouped = {};
            for (const row of list) {
              const key = row.severity_band;
              if (!grouped[key]) grouped[key] = [];
              grouped[key].push(row);
            }
            const groupKeys = Object.keys(grouped).map(Number).sort((a, b) => a - b);
            if (!groupKeys.length) {
              return `<div class="bg-white border border-[#e7bdb9] rounded-xl p-8 text-center text-sm text-[#5d3f3d]">No employees in scope yet.</div>`;
            }
            return groupKeys.map((band) => {
              const bandRows = grouped[band].sort((a, b) => a.rank - b.rank || String(a.name).localeCompare(String(b.name)));
              return `<section class="bg-white border border-[#e7bdb9] rounded-xl overflow-hidden">
                <div class="p-4 bg-[#fff8f7] border-b border-[#e7bdb9] flex justify-between items-center gap-3 flex-wrap">
                  <div>
                    <h3 class="text-lg font-bold text-[#291716]">Severity band ${band}</h3>
                    <p class="text-xs text-[#5d3f3d] mt-0.5">${bandRows.length} employee${bandRows.length === 1 ? "" : "s"} · ranked by LinkedIn hours</p>
                  </div>
                  <span class="text-xs font-bold uppercase tracking-wide text-[#df162b] bg-[#fff0ef] border border-[#e7bdb9] px-3 py-1 rounded-full">Gap severity ${band}</span>
                </div>
                <div class="overflow-x-auto">
                  <table class="w-full min-w-[720px] text-sm text-left">
                    <thead class="bg-[#fff0ef] text-[11px] uppercase tracking-wide text-[#5d3f3d]">
                      <tr>
                        <th class="p-4">Rank</th>
                        <th class="p-4">Employee</th>
                        <th class="p-4">Focus areas</th>
                        <th class="p-4 text-right">Hours</th>
                        <th class="p-4">Courses</th>
                        <th class="p-4 text-center">Badges</th>
                      </tr>
                    </thead>
                    <tbody>
                      ${bandRows.map((row) => `<tr class="border-t border-[#e7bdb9] hover:bg-[#fff0ef]">
                        <td class="p-4 font-bold text-[#0075d7]">#${row.rank}</td>
                        <td class="p-4">
                          <div class="flex items-center gap-2">
                            <div class="w-8 h-8 rounded-full bg-[#f4d2d0] text-[#5d3f3d] flex items-center justify-center text-xs font-bold">${esc(lbInitials(row.name))}</div>
                            <div>
                              <strong class="text-[#291716]">${esc(row.name)}</strong>
                              <div class="text-xs text-[#5d3f3d]">${esc(row.employee_code)}</div>
                            </div>
                          </div>
                        </td>
                        <td class="p-4 font-bold">${row.focus_areas}</td>
                        <td class="p-4 text-right font-mono font-bold">${Number(row.learning_hours).toFixed(1)}h</td>
                        <td class="p-4">${Number(row.completions || 0)}</td>
                        <td class="p-4 text-center">${lbBadgeIcons(row.badges, catalog)}</td>
                      </tr>`).join("")}
                    </tbody>
                  </table>
                </div>
              </section>`;
            }).join("");
          })()}
        </div>`);

      qs("[data-lb-search]").oninput = (event) => {
        searchRaw = event.target.value;
        searchTerm = searchRaw.trim().toLowerCase();
        draw();
        const input = qs("[data-lb-search]");
        if (input) {
          input.focus();
          const end = input.value.length;
          input.setSelectionRange(end, end);
        }
      };
    };

    draw();
  }

  function initAdminLeaderboard(payload) {
    const rows = payload.leaderboard || [];
    const catalog = payload.badge_catalog || [];
    const bands = [...new Set(rows.map((row) => row.severity_band))].sort((a, b) => a - b);
    let filterBand = "all";
    let sortMode = "rank-asc";
    let filterOpen = false;
    let sortOpen = false;
    let searchTerm = "";
    let searchRaw = "";

    const filterLabel = {
      all: "All bands",
      ...Object.fromEntries(bands.map((band) => [`band-${band}`, `Severity ${band}`])),
      locked: "Journey locked",
      unlocked: "Journey open",
      focus0: "0 focus areas",
      focus1plus: "1+ focus areas",
    };
    const sortLabel = {
      "rank-asc": "Rank low→high",
      "rank-desc": "Rank high→low",
      "hours-desc": "Hours high→low",
      "hours-asc": "Hours low→high",
      "name-asc": "Name A–Z",
      "name-desc": "Name Z–A",
      "focus-desc": "Focus areas high→low",
      "severity-asc": "Severity low→high",
    };

    const filtered = () => {
      let list = rows.filter((row) => {
        if (filterBand.startsWith("band-") && String(row.severity_band) !== filterBand.slice(5)) return false;
        if (filterBand === "locked" && !row.journey_locked) return false;
        if (filterBand === "unlocked" && row.journey_locked) return false;
        if (filterBand === "focus0" && Number(row.focus_areas) !== 0) return false;
        if (filterBand === "focus1plus" && Number(row.focus_areas) < 1) return false;
        if (!searchTerm) return true;
        return [row.employee_code, row.name].some((value) => String(value || "").toLowerCase().includes(searchTerm));
      });
      list = [...list].sort((a, b) => {
        if (sortMode === "rank-asc") return (a.rank - b.rank) || (a.severity_band - b.severity_band) || String(a.name).localeCompare(String(b.name));
        if (sortMode === "rank-desc") return (b.rank - a.rank) || (a.severity_band - b.severity_band);
        if (sortMode === "hours-desc") return b.learning_hours - a.learning_hours;
        if (sortMode === "hours-asc") return a.learning_hours - b.learning_hours;
        if (sortMode === "name-asc") return String(a.name || "").localeCompare(String(b.name || ""));
        if (sortMode === "name-desc") return String(b.name || "").localeCompare(String(a.name || ""));
        if (sortMode === "focus-desc") return b.focus_areas - a.focus_areas;
        if (sortMode === "severity-asc") return a.severity_band - b.severity_band || a.rank - b.rank;
        return 0;
      });
      return list;
    };

    const draw = () => {
      const list = filtered();
      const filterActive = filterBand !== "all";
      const chipBase = "px-3 py-1.5 bg-white border rounded-full text-xs font-bold inline-flex items-center gap-1 cursor-pointer hover:border-[#df162b] hover:text-[#df162b] transition-colors";
      const chipOn = "border-[#df162b] text-[#df162b] bg-[#fff0ef]";
      const chipOff = "border-[#e7bdb9] text-[#5d3f3d]";
      const grouped = {};
      for (const row of list) {
        const key = row.severity_band;
        if (!grouped[key]) grouped[key] = [];
        grouped[key].push(row);
      }
      const groupKeys = Object.keys(grouped).map(Number).sort((a, b) => a - b);

      render(`${pageHeader("Learning Leaderboard", "All employees ranked within gap-severity cohorts. Search, filter, and sort across bands.")}
        <label class="block mb-4"><span class="sr-only">Search employees</span>
          <input data-lb-search value="${esc(searchRaw)}" class="w-full md:w-96 border border-slate-200 rounded-lg px-4 py-3" placeholder="Search code or name">
        </label>
        <div class="bg-white rounded-xl border border-[#e7bdb9] overflow-hidden mb-6">
          <div class="p-4 bg-[#fff0ef] border-b border-[#e7bdb9] flex justify-between items-center gap-3 flex-wrap">
            <div class="flex gap-2 flex-wrap items-center">
              <div class="relative">
                <button type="button" data-toggle-filter class="${chipBase} ${filterActive || filterOpen ? chipOn : chipOff}">
                  <span class="material-symbols-outlined text-[16px]">filter_list</span>
                  Filter${filterActive ? `: ${esc(filterLabel[filterBand] || filterBand)}` : ""}
                </button>
                ${filterOpen ? `<div class="absolute left-0 top-full mt-2 z-20 min-w-[200px] max-h-72 overflow-y-auto bg-white border border-[#e7bdb9] rounded-xl shadow-lg py-1">
                  ${Object.entries(filterLabel).map(([key, label]) => `<button type="button" data-filter="${key}" class="w-full text-left px-4 py-2 text-sm font-semibold hover:bg-[#fff0ef] ${filterBand === key ? "text-[#df162b]" : "text-[#291716]"}">${esc(label)}</button>`).join("")}
                </div>` : ""}
              </div>
              <div class="relative">
                <button type="button" data-toggle-sort class="${chipBase} ${sortMode !== "rank-asc" || sortOpen ? chipOn : chipOff}">
                  <span class="material-symbols-outlined text-[16px]">sort</span>
                  Sort: ${esc(sortLabel[sortMode])}
                </button>
                ${sortOpen ? `<div class="absolute left-0 top-full mt-2 z-20 min-w-[220px] bg-white border border-[#e7bdb9] rounded-xl shadow-lg py-1">
                  ${Object.entries(sortLabel).map(([key, label]) => `<button type="button" data-sort="${key}" class="w-full text-left px-4 py-2 text-sm font-semibold hover:bg-[#fff0ef] ${sortMode === key ? "text-[#df162b]" : "text-[#291716]"}">${esc(label)}</button>`).join("")}
                </div>` : ""}
              </div>
            </div>
            <span class="text-xs text-[#5d3f3d]">Showing ${list.length} of ${rows.length} · ${groupKeys.length} band${groupKeys.length === 1 ? "" : "s"}</span>
          </div>
        </div>
        <div class="space-y-6">
          ${groupKeys.map((band) => {
            const bandRows = grouped[band];
            return `<section class="bg-white border border-[#e7bdb9] rounded-xl overflow-hidden">
              <div class="p-4 bg-[#fff8f7] border-b border-[#e7bdb9] flex justify-between items-center gap-3 flex-wrap">
                <div>
                  <h3 class="text-lg font-bold text-[#291716]">Severity band ${band}</h3>
                  <p class="text-xs text-[#5d3f3d] mt-0.5">${bandRows.length} employee${bandRows.length === 1 ? "" : "s"} · ranked by LinkedIn hours</p>
                </div>
                <span class="text-xs font-bold uppercase tracking-wide text-[#df162b] bg-[#fff0ef] border border-[#e7bdb9] px-3 py-1 rounded-full">Gap severity ${band}</span>
              </div>
              <div class="overflow-x-auto">
                <table class="w-full min-w-[720px] text-sm text-left">
                  <thead class="bg-[#fff0ef] text-[11px] uppercase tracking-wide text-[#5d3f3d]">
                    <tr>
                      <th class="p-4">Rank</th>
                      <th class="p-4">Employee</th>
                      <th class="p-4">Focus areas</th>
                      <th class="p-4">Hours</th>
                      <th class="p-4">Courses</th>
                      <th class="p-4 text-center">Badges</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${bandRows.map((row) => `<tr class="border-t border-[#e7bdb9] hover:bg-[#fff0ef]">
                      <td class="p-4 font-bold text-[#005cab]">#${row.rank}</td>
                      <td class="p-4"><strong>${esc(row.name)}</strong><div class="text-xs text-[#5d3f3d]">${esc(row.employee_code)}</div></td>
                      <td class="p-4 font-bold">${row.focus_areas}</td>
                      <td class="p-4 font-bold">${Number(row.learning_hours).toFixed(1)}h</td>
                      <td class="p-4">${Number(row.completions || 0)}</td>
                      <td class="p-4 text-center">${lbBadgeIcons(row.badges, catalog)}</td>
                    </tr>`).join("")}
                  </tbody>
                </table>
              </div>
            </section>`;
          }).join("") || `<div class="bg-white border border-[#e7bdb9] rounded-xl p-8 text-center text-sm text-[#5d3f3d]">No matching employees.</div>`}
        </div>`);

      qs("[data-toggle-filter]")?.addEventListener("click", (event) => {
        event.stopPropagation();
        filterOpen = !filterOpen;
        sortOpen = false;
        draw();
      });
      qs("[data-toggle-sort]")?.addEventListener("click", (event) => {
        event.stopPropagation();
        sortOpen = !sortOpen;
        filterOpen = false;
        draw();
      });
      qsa("[data-filter]").forEach((control) => {
        control.onclick = (event) => {
          event.stopPropagation();
          filterBand = control.dataset.filter;
          filterOpen = false;
          draw();
        };
      });
      qsa("[data-sort]").forEach((control) => {
        control.onclick = (event) => {
          event.stopPropagation();
          sortMode = control.dataset.sort;
          sortOpen = false;
          draw();
        };
      });
      qs("[data-lb-search]").oninput = (event) => {
        searchRaw = event.target.value;
        searchTerm = searchRaw.trim().toLowerCase();
        filterOpen = false;
        sortOpen = false;
        draw();
        const input = qs("[data-lb-search]");
        if (input) {
          input.focus();
          const end = input.value.length;
          input.setSelectionRange(end, end);
        }
      };
    };

    draw();
  }

  async function initAdminOverview() {
    const result = await api("/api/admin/overview");
    const insights = result.insights || {};
    const phaseLabel = { zm: "ZM Assessment", rd: "RD Validation", employee: "Employee Experience" };
    const phaseBars = (result.phases || []).map((phase) => {
      const pct = Math.min(100, Number(phase.progress.percentage || 0));
      return `<div class="space-y-2">
        <div class="flex justify-between items-center gap-3">
          <span class="text-sm font-bold text-[#291716]">${esc(phaseLabel[phase.phase] || phase.phase)}</span>
          <span class="text-xs font-semibold text-[#5d3f3d]">${pct}% · ${phase.progress.completed}/${phase.progress.total}</span>
        </div>
        <div class="w-full h-3 bg-[#ffe1df] rounded-full overflow-hidden">
          <div class="h-full bg-[#005cab] rounded-full" style="width:${pct}%"></div>
        </div>
      </div>`;
    }).join("");
    const rated = Number(insights.rated_employees) || 0;
    const rdDone = Number(result.metrics?.rd_completed) || 0;
    const insightRows = insights.competencies || [];
    const maxGaps = Math.max(1, ...insightRows.map((row) => Number(row.gap_count) || 0), 0);
    const insightBars = insightRows.length && (rated > 0 || insightRows.some((row) => "gap_count" in row))
      ? insightRows.map((item) => {
          const count = Number(item.gap_count) || 0;
          const barPct = Math.round((count / maxGaps) * 100);
          const share = Number(item.percentage) || 0;
          const people = count === 1 ? "1 person" : `${count} people`;
          return `<div class="space-y-1.5">
            <div class="flex justify-between items-center gap-3">
              <span class="text-sm font-bold text-[#291716]">${esc(item.competency)}</span>
              <span class="text-xs font-semibold text-[#df162b]">${people} · ${share}% </span>
            </div>
            <div class="w-full h-2 bg-[#ffe1df] rounded-full overflow-hidden">
              <div class="h-full bg-[#df162b] rounded-full" style="width:${barPct}%"></div>
            </div>
          </div>`;
        }).join("")
      : rdDone > 0
        ? `<p class="py-10 text-center text-sm text-[#5d3f3d]">${rdDone} RD-validated profile${rdDone === 1 ? "" : "s"} found, but gap insights did not load. Hard-refresh after restarting the server.</p>`
        : `<p class="py-10 text-center text-sm text-[#5d3f3d]">No RD-validated profiles yet. Skill gaps appear after RD submissions.</p>`;
    const metricCard = (label, value, tone = "blue") => {
      const valueClass = tone === "red" ? "text-[#df162b]" : tone === "teal" ? "text-[#005f81]" : "text-[#005cab]";
      return `<div class="bg-white border border-[#e0e0e0] rounded-lg p-4 flex flex-col justify-between min-h-[110px] hover:shadow-[0_4px_12px_rgba(0,0,0,0.05)] transition-shadow">
        <span class="text-[11px] font-semibold uppercase tracking-wider text-[#5d3f3d]">${esc(label)}</span>
        <span class="text-3xl font-extrabold ${valueClass} mt-3 leading-none">${esc(value)}</span>
      </div>`;
    };
    const withGaps = Number(insights.employees_with_gaps) || 0;
    const ratedLabel = rated || rdDone;

    render(`<section class="flex flex-col md:flex-row md:items-end justify-between gap-4 mb-8">
      <div>
        <h1 class="text-3xl md:text-4xl font-extrabold tracking-tight text-[#291716]">Admin Overview</h1>
        <p class="text-base text-[#5d3f3d] mt-2 max-w-2xl">All metrics are calculated from persisted workflow records in real-time, providing an aggregate view of talent mobility and LinkedIn integration health.</p>
      </div>
      <div class="flex flex-wrap gap-2 shrink-0">
        <button type="button" data-export class="px-5 py-2.5 bg-white border border-[#005cab] text-[#005cab] rounded-lg font-bold text-sm hover:bg-[#fff0ef] active:scale-95 transition">Export Report</button>
        <button type="button" data-sync class="px-5 py-2.5 bg-[#005cab] text-white rounded-lg font-bold text-sm hover:opacity-90 active:scale-95 transition inline-flex items-center gap-1.5">
          <span class="material-symbols-outlined text-[20px]">sync</span>Sync LinkedIn
        </button>
      </div>
    </section>
    <section class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3 mb-8">
      ${metricCard("Total Employees", result.metrics.total_employees, "red")}
      ${metricCard("ZM Submitted", result.metrics.zm_completed)}
      ${metricCard("RD Submitted", result.metrics.rd_completed)}
      ${metricCard("Assessments Complete", result.metrics.roleplays_completed)}
      ${metricCard("Locked Aspirations", result.metrics.locked_aspirations)}
      ${metricCard("Active Journeys", result.metrics.active_journeys)}
      ${metricCard("LinkedIn Hours", `${Number(result.metrics.learning_hours).toFixed(1)}h`, "teal")}
    </section>
    <div class="grid grid-cols-1 lg:grid-cols-12 gap-6">
      <section class="lg:col-span-5 bg-white border border-[#e0e0e0] rounded-lg overflow-hidden flex flex-col">
        <div class="p-5 border-b border-[#e7bdb9] bg-[#fff0ef]">
          <h2 class="text-lg font-bold text-[#291716]">Phase progress</h2>
          <p class="text-sm text-[#5d3f3d] mt-0.5">Real-time completion tracking across active modules.</p>
        </div>
        <div class="p-5 space-y-6 flex-1">
          ${phaseBars || `<p class="text-sm text-[#5d3f3d]">No phase data.</p>`}
        </div>
      </section>
      <section class="lg:col-span-7 bg-white border border-[#e0e0e0] rounded-lg overflow-hidden flex flex-col">
        <div class="p-5 border-b border-[#e7bdb9] bg-[#fff0ef] flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 class="text-lg font-bold text-[#291716]">Talent Intelligence Insights</h2>
            <p class="text-sm text-[#5d3f3d] mt-0.5">People with a gap vs current-role ideal${ratedLabel ? ` · ${withGaps}/${ratedLabel} RD-validated ` : ""}</p>
          </div>
          <button type="button" data-analytics class="text-[#005cab] font-bold text-xs hover:underline shrink-0">Detailed Analytics</button>
        </div>
        <div class="p-5 flex-1 space-y-4">${insightBars}</div>
      </section>
    </div>`);
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
    qs("[data-analytics]").onclick = () => go("admin/confidence");
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
    const total = rows.length;
    let filterStatus = "all";
    let sortMode = "name-asc";
    let filterOpen = false;
    let sortOpen = false;
    let searchTerm = "";
    let searchRaw = "";

    const filterLabel = {
      all: "All",
      zm_pending: "ZM pending",
      zm_draft: "ZM draft",
      zm_submitted: "ZM submitted",
      rd_pending: "RD pending",
      rd_draft: "RD draft",
      rd_submitted: "RD validated",
      aspiration: "Aspiration locked",
    };
    const sortLabel = {
      "name-asc": "Name A–Z",
      "name-desc": "Name Z–A",
      "code-asc": "Employee code A–Z",
      "code-desc": "Employee code Z–A",
      "zm-asc": "ZM status",
      "rd-asc": "RD status",
      "assessments-desc": "Assessments high→low",
      "assessments-asc": "Assessments low→high",
    };
    const statusRank = { not_started: 0, pending: 0, draft: 1, submitted: 2 };

    const matchesFilter = (row) => {
      if (filterStatus === "all") return true;
      if (filterStatus === "zm_pending") return row.zm_status !== "draft" && row.zm_status !== "submitted";
      if (filterStatus === "zm_draft") return row.zm_status === "draft";
      if (filterStatus === "zm_submitted") return row.zm_status === "submitted";
      if (filterStatus === "rd_pending") return row.rd_status !== "draft" && row.rd_status !== "submitted";
      if (filterStatus === "rd_draft") return row.rd_status === "draft";
      if (filterStatus === "rd_submitted") return row.rd_status === "submitted";
      if (filterStatus === "aspiration") return Boolean(row.aspiration);
      return true;
    };

    const filteredSorted = () => {
      let list = rows.filter((row) => {
        if (!matchesFilter(row)) return false;
        if (!searchTerm) return true;
        return [row.employee_code, row.name, row.designation, row.zm_name, row.rd_name]
          .some((value) => String(value || "").toLowerCase().includes(searchTerm));
      });
      list = [...list].sort((a, b) => {
        if (sortMode === "name-asc") return String(a.name || "").localeCompare(String(b.name || ""));
        if (sortMode === "name-desc") return String(b.name || "").localeCompare(String(a.name || ""));
        if (sortMode === "code-asc") return String(a.employee_code || "").localeCompare(String(b.employee_code || ""), undefined, { numeric: true });
        if (sortMode === "code-desc") return String(b.employee_code || "").localeCompare(String(a.employee_code || ""), undefined, { numeric: true });
        if (sortMode === "zm-asc") {
          return (statusRank[a.zm_status] ?? 0) - (statusRank[b.zm_status] ?? 0)
            || String(a.name || "").localeCompare(String(b.name || ""));
        }
        if (sortMode === "rd-asc") {
          return (statusRank[a.rd_status] ?? 0) - (statusRank[b.rd_status] ?? 0)
            || String(a.name || "").localeCompare(String(b.name || ""));
        }
        if (sortMode === "assessments-desc") return (b.roleplays_completed || 0) - (a.roleplays_completed || 0);
        if (sortMode === "assessments-asc") return (a.roleplays_completed || 0) - (b.roleplays_completed || 0);
        return 0;
      });
      return list;
    };

    const bindRowActions = () => {
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

    const draw = () => {
      const list = filteredSorted();
      const filterActive = filterStatus !== "all";
      const chipBase = "px-3 py-1.5 bg-white border rounded-full text-xs font-bold inline-flex items-center gap-1 cursor-pointer hover:border-[#df162b] hover:text-[#df162b] transition-colors";
      const chipOn = "border-[#df162b] text-[#df162b] bg-[#fff0ef]";
      const chipOff = "border-[#e7bdb9] text-[#5d3f3d]";

      render(`${pageHeader("Employee Master", "Workbook identity plus persisted workflow status.", button("Export CSV", "data-export", true))}
        <label class="block mb-4"><span class="sr-only">Search employees</span>
          <input data-search value="${esc(searchRaw)}" class="w-full md:w-96 border border-slate-200 rounded-lg px-4 py-3" placeholder="Search code, name, role, manager">
        </label>
        <div class="bg-white rounded-xl border border-[#e7bdb9] overflow-hidden mb-8">
          <div class="p-4 bg-[#fff0ef] border-b border-[#e7bdb9] flex justify-between items-center gap-3 flex-wrap">
            <div class="flex gap-2 flex-wrap items-center">
              <div class="relative">
                <button type="button" data-toggle-filter class="${chipBase} ${filterActive || filterOpen ? chipOn : chipOff}">
                  <span class="material-symbols-outlined text-[16px]">filter_list</span>
                  Filter${filterActive ? `: ${esc(filterLabel[filterStatus])}` : ""}
                </button>
                ${filterOpen ? `<div class="absolute left-0 top-full mt-2 z-20 min-w-[180px] bg-white border border-[#e7bdb9] rounded-xl shadow-lg py-1">
                  ${Object.entries(filterLabel).map(([key, label]) => `<button type="button" data-filter="${key}" class="w-full text-left px-4 py-2 text-sm font-semibold hover:bg-[#fff0ef] ${filterStatus === key ? "text-[#df162b]" : "text-[#291716]"}">${esc(label)}</button>`).join("")}
                </div>` : ""}
              </div>
              <div class="relative">
                <button type="button" data-toggle-sort class="${chipBase} ${sortMode !== "name-asc" || sortOpen ? chipOn : chipOff}">
                  <span class="material-symbols-outlined text-[16px]">sort</span>
                  Sort: ${esc(sortLabel[sortMode])}
                </button>
                ${sortOpen ? `<div class="absolute left-0 top-full mt-2 z-20 min-w-[220px] bg-white border border-[#e7bdb9] rounded-xl shadow-lg py-1">
                  ${Object.entries(sortLabel).map(([key, label]) => `<button type="button" data-sort="${key}" class="w-full text-left px-4 py-2 text-sm font-semibold hover:bg-[#fff0ef] ${sortMode === key ? "text-[#df162b]" : "text-[#291716]"}">${esc(label)}</button>`).join("")}
                </div>` : ""}
              </div>
            </div>
            <span class="text-xs text-[#5d3f3d]">Showing ${list.length}${filterActive || searchTerm ? ` of ${total}` : ""} employee${list.length === 1 ? "" : "s"}</span>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full min-w-[1000px] text-sm text-left">
              <thead class="bg-slate-50"><tr>
                <th class="p-4">Employee</th><th class="p-4">Role</th><th class="p-4">ZM</th><th class="p-4">RD</th>
                <th class="p-4">Assessment status</th><th class="p-4">Assessments</th><th class="p-4">Aspiration</th>
                <th class="p-4">Courses</th><th class="p-4">Actions</th>
              </tr></thead>
              <tbody>
                ${list.map((row) => `<tr class="border-t border-[#e7bdb9] hover:bg-[#fff0ef]">
                  <td class="p-4"><strong>${esc(row.name)}</strong><div class="text-xs text-[#5d3f3d]">${esc(row.employee_code)}</div></td>
                  <td class="p-4">${esc(row.designation)}<div class="text-xs text-[#5d3f3d]">${esc(row.grade)}</div></td>
                  <td class="p-4">${esc(row.zm_name)}</td>
                  <td class="p-4">${esc(row.rd_name)}</td>
                  <td class="p-4">${statusChip(row.zm_status)} ${statusChip(row.rd_status)}</td>
                  <td class="p-4">${row.roleplays_completed}/${row.roleplays_total}</td>
                  <td class="p-4">${esc(row.aspiration?.aspiration_role ? String(row.aspiration.aspiration_role).toUpperCase() : "Not selected")}</td>
                  <td class="p-4">${row.learning_locked ? statusChip("locked") : statusChip("open")}</td>
                  <td class="p-4 flex flex-wrap gap-2">${button("Profile", `data-profile="${row.employee_code}"`, true)}${button("Assessments", `data-roleplay-review="${row.employee_code}"`, true)}${row.learning_locked ? button("Reset Courses", `data-reset-courses="${row.employee_code}"`, true) : ""}${row.aspiration ? button("Reset Aspiration", `data-reset="${row.employee_code}"`, true) : ""}</td>
                </tr>`).join("") || empty("No matching employees.", 9)}
              </tbody>
            </table>
          </div>
          <div class="p-4 border-t border-[#e7bdb9] text-xs text-[#5d3f3d]">Filter and sort apply with live search across the employee master.</div>
        </div>`);

      bindRowActions();
      qs("[data-export]").onclick = () => exportEmployees(list);
      qs("[data-toggle-filter]").onclick = (event) => {
        event.stopPropagation();
        filterOpen = !filterOpen;
        sortOpen = false;
        draw();
      };
      qs("[data-toggle-sort]").onclick = (event) => {
        event.stopPropagation();
        sortOpen = !sortOpen;
        filterOpen = false;
        draw();
      };
      qsa("[data-filter]").forEach((control) => {
        control.onclick = (event) => {
          event.stopPropagation();
          filterStatus = control.dataset.filter;
          filterOpen = false;
          draw();
        };
      });
      qsa("[data-sort]").forEach((control) => {
        control.onclick = (event) => {
          event.stopPropagation();
          sortMode = control.dataset.sort;
          sortOpen = false;
          draw();
        };
      });
      qs("[data-search]").oninput = (event) => {
        searchRaw = event.target.value;
        searchTerm = searchRaw.trim().toLowerCase();
        filterOpen = false;
        sortOpen = false;
        draw();
        const input = qs("[data-search]");
        if (input) {
          input.focus();
          const len = input.value.length;
          input.setSelectionRange(len, len);
        }
      };
    };

    draw();
  }

  async function openFinalProfile(employeeCode) {
    try {
      const result = await api(`/api/final-profile?employee_code=${encodeURIComponent(employeeCode)}`);
      const emp = result.employee || {};
      const name = emp.name || "Employee";
      const isAdmin = session.user?.role === "admin";
      const ideals = result.ideal_ratings || {};
      const competencies = Object.keys(result.ratings || {}).length
        ? Object.keys(result.ratings)
        : Object.keys(ideals);
      const ratingRows = competencies.length
        ? (isAdmin
          ? `<div class="grid grid-cols-[1.4fr_1fr_1fr] gap-2 text-[11px] font-bold uppercase tracking-wider text-[#5d3f3d] pb-2 border-b border-[#e7bdb9]">
              <span>Competency</span><span>Final rating</span><span>Ideal rating</span>
            </div>
            ${competencies.map((competency) => `<div class="py-3 grid grid-cols-[1.4fr_1fr_1fr] gap-2 items-center border-b border-[#e7bdb9] last:border-0">
              <span class="text-sm text-[#291716]">${esc(competency)}</span>
              <strong class="text-sm text-[#005cab]">${esc(result.ratings?.[competency] || "—")}</strong>
              <strong class="text-sm text-[#5d3f3d]">${esc(ideals[competency] || "—")}</strong>
            </div>`).join("")}`
          : Object.entries(result.ratings || {}).map(([competency, rating]) =>
            `<div class="py-3 flex justify-between gap-3 border-b border-[#e7bdb9] last:border-0"><span class="text-sm text-[#291716]">${esc(competency)}</span><strong class="text-sm text-[#005cab]">${esc(rating)}</strong></div>`
          ).join(""))
        : '<p class="py-8 text-center text-sm text-[#5d3f3d]">Final rating not available yet.</p>';
      const modal = document.createElement("div");
      modal.className = "fixed inset-0 z-[80] bg-slate-900/50 p-4 grid place-items-center";
      modal.innerHTML = `<section class="bg-white rounded-xl p-6 ${isAdmin ? "max-w-2xl" : "max-w-xl"} w-full border border-[#e7bdb9] shadow-2xl max-h-[90vh] overflow-y-auto" role="dialog" aria-modal="true">
        <div class="flex justify-between gap-3">
          <div>
            <h2 class="text-xl font-extrabold text-[#291716]">Final rating of ${esc(name)}</h2>
            <p class="text-sm text-[#5d3f3d] mt-1">${esc(emp.employee_code || "")}${emp.designation ? ` · ${esc(emp.designation)}` : ""}</p>
          </div>
          <button type="button" data-close class="material-symbols-outlined text-[#5d3f3d] hover:text-[#df162b]">close</button>
        </div>
        <div class="mt-5">${ratingRows}</div>
      </section>`;
      document.body.appendChild(modal);
      qs("[data-close]", modal).onclick = () => modal.remove();
      modal.addEventListener("click", (event) => {
        if (event.target === modal) modal.remove();
      });
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
    const employees = overview.employees || [];
    if (!employees.length) {
      render(`${pageHeader("Confidence Scores")}<p class="bg-white border rounded-xl p-8">No employees available.</p>`);
      return;
    }

    let selected = params.get("employee") || employees[0].employee_code;
    if (!employees.some((row) => row.employee_code === selected)) selected = employees[0].employee_code;
    let searchTerm = "";
    let searchRaw = "";
    let result = null;

    const bandTone = (band) => {
      if (band === "High") return "bg-emerald-50 text-emerald-800 border-emerald-200";
      if (band === "Low") return "bg-[#fff0ef] text-[#df162b] border-[#e7bdb9]";
      return "bg-[#fff4e8] text-[#9a5b1a] border-[#f0d4b0]";
    };

    const loadResult = async () => {
      result = await api(`/api/admin/confidence?employee_code=${encodeURIComponent(selected)}`);
    };

    const draw = () => {
      const selectedEmp = employees.find((row) => row.employee_code === selected) || employees[0];
      const label = `${selectedEmp.name} (${selectedEmp.employee_code})`;
      const filtered = employees.filter((row) => {
        if (!searchTerm) return true;
        return [row.name, row.employee_code, row.designation]
          .some((value) => String(value || "").toLowerCase().includes(searchTerm));
      });
      const score = result?.score;
      const band = result?.band || "";
      const scoreLabel = score == null ? "Pending" : `${score}%`;
      const pct = score == null ? 0 : Math.max(0, Math.min(100, Number(score)));
      const ringStyle = `background: conic-gradient(#005cab ${pct * 3.6}deg, #fddbd8 0)`;

      render(`<div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <aside class="lg:col-span-3 bg-white border border-[#e7bdb9] rounded-xl overflow-hidden sticky top-4">
          <div class="p-4 border-b border-[#e7bdb9]">
            <h2 class="text-base font-extrabold text-[#291716]">Employees</h2>
            <label class="relative block mt-3">
              <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[#926e6c] text-[18px]">search</span>
              <input data-conf-search value="${esc(searchRaw)}" class="w-full pl-10 pr-3 py-2.5 border border-[#e7bdb9] rounded-full text-sm outline-none focus:border-[#df162b] bg-[#fff8f7]" placeholder="Search team...">
            </label>
          </div>
          <div class="max-h-[70vh] overflow-y-auto p-2 space-y-1">
            ${filtered.map((row) => {
              const active = row.employee_code === selected;
              return `<button type="button" data-conf-emp="${esc(row.employee_code)}" class="w-full text-left px-3 py-2.5 rounded-lg text-sm font-semibold flex items-center justify-between gap-2 transition-colors ${active ? "bg-[#df162b] text-white shadow-sm" : "text-[#291716] hover:bg-[#fff0ef]"}">
                <span class="truncate">${esc(row.name)} <span class="${active ? "text-white/80" : "text-[#5d3f3d]"} font-normal">(${esc(row.employee_code)})</span></span>
                ${active ? `<span class="material-symbols-outlined text-[18px] shrink-0" style="font-variation-settings:'FILL' 1">check</span>` : ""}
              </button>`;
            }).join("") || `<p class="p-3 text-sm text-[#5d3f3d]">No matches.</p>`}
          </div>
        </aside>

        <section class="lg:col-span-9 min-w-0">
          <div class="mb-6">
            <h1 class="text-3xl md:text-4xl font-extrabold tracking-tight text-[#df162b]">Confidence Score Details</h1>
            <p class="text-base text-[#5d3f3d] mt-2 max-w-3xl">Reviewing assessment consensus for <strong class="text-[#291716]">${esc(label)}</strong>. Calculated only when ZM, RD, and all seven AI assessment ratings exist.</p>
          </div>

          <div class="bg-white border border-[#e7bdb9] rounded-xl p-5 md:p-6 mb-6 flex flex-col md:flex-row md:items-center gap-6">
            <div class="flex-1 min-w-0">
              <p class="text-[11px] font-bold uppercase tracking-wider text-[#5d3f3d]">Overall confidence</p>
              <div class="flex flex-wrap items-center gap-3 mt-2">
                <p class="text-5xl font-extrabold text-[#005cab] leading-none">${esc(scoreLabel)}</p>
                ${band ? `<span class="px-3 py-1 rounded-full text-xs font-bold border ${bandTone(band)}">${esc(band)}</span>` : ""}
              </div>
              <p class="text-sm text-[#5d3f3d] mt-4 leading-relaxed">Calculated based on the agreement between Zonal Manager (ZM), Regional Director (RD), and AI assessment ratings across all core competencies.</p>
            </div>
            <div class="shrink-0 mx-auto md:mx-0">
              <div class="relative w-28 h-28 rounded-full" style="${ringStyle}">
                <div class="absolute inset-[12px] rounded-full bg-white flex items-center justify-center">
                  <span class="material-symbols-outlined text-[#005cab] text-[28px]">analytics</span>
                </div>
              </div>
            </div>
          </div>

          <div class="overflow-x-auto bg-white border border-[#e7bdb9] rounded-xl">
            <table class="w-full min-w-[900px] text-sm text-left">
              <thead class="bg-[#fff0ef] text-[#5d3f3d]">
                <tr>
                  <th class="p-4 font-bold">Competency</th>
                  <th class="p-4 font-bold">RD's Rating</th>
                  <th class="p-4 font-bold">ZM's Rating</th>
                  <th class="p-4 font-bold">Assessment Score</th>
                  <th class="p-4 font-bold">RD vs ZM Rating</th>
                  <th class="p-4 font-bold">RD vs Assessment Rating</th>
                </tr>
              </thead>
              <tbody>
                ${(result?.competencies || []).map((row, index) => `<tr class="border-t border-[#e7bdb9] ${index % 2 ? "bg-[#f8fbff]" : "bg-white"}">
                  <td class="p-4 font-bold text-[#291716]">${esc(row.competency)}</td>
                  <td class="p-4">${esc(row.rd_rating || "Pending")}</td>
                  <td class="p-4">${esc(row.zm_rating || "Pending")}</td>
                  <td class="p-4">${esc(row.ai_rating || "Pending")}</td>
                  <td class="p-4 font-bold text-[#005cab]">${row.zm_agreement == null ? "—" : `${row.zm_agreement}%`}</td>
                  <td class="p-4 font-bold text-[#005cab]">${row.ai_agreement == null ? "—" : `${row.ai_agreement}%`}</td>
                </tr>`).join("") || empty("Confidence pending. Required assessment inputs are incomplete.", 6)}
              </tbody>
            </table>
          </div>
        </section>
      </div>`);

      qs("[data-conf-search]").oninput = (event) => {
        searchRaw = event.target.value;
        searchTerm = searchRaw.trim().toLowerCase();
        draw();
        const input = qs("[data-conf-search]");
        if (input) {
          input.focus();
          const end = input.value.length;
          input.setSelectionRange(end, end);
        }
      };
      qsa("[data-conf-emp]").forEach((control) => {
        control.onclick = async () => {
          selected = control.dataset.confEmp;
          history.replaceState({}, "", `/app/admin/confidence?employee=${encodeURIComponent(selected)}`);
          await loadResult();
          draw();
        };
      });
    };

    await loadResult();
    draw();
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
    if (
      session.user.role === "employee"
      && page.startsWith("employee/")
      && page !== "employee/welcome"
      && !hasDisclaimerAck()
    ) {
      toast("Acknowledge the disclaimer on Home before continuing.", "error");
      go("employee/welcome");
      return;
    }
    const handlers = {
      "zm/welcome": () => initWelcome("zm"),
      "zm/dashboard": () => initTeamDashboard("zm"),
      "zm/assessments": () => go("zm/dashboard"),
      "zm/leaderboard": initLeaderboard,
      "rd/welcome": () => initWelcome("rd"),
      "rd/dashboard": () => initTeamDashboard("rd"),
      "rd/validations": () => go("rd/dashboard"),
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
      "admin/leaderboard": initLeaderboard,
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
