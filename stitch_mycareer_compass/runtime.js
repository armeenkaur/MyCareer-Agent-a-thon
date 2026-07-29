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

  const levelBarColors = {
    Beginner: "#df162b",
    Intermediate: "#e89b96",
    Proficient: "#1464F4",
    Advanced: "#0d9488",
  };

  function renderSkillProficiencyMatrix({
    skills,
    employees,
    getRatings,
    emptyMessage,
    compact = false,
    embedded = false,
  }) {
    const skillsList = (skills || []).filter(Boolean);
    const rated = (employees || []).filter((emp) => Object.keys(getRatings(emp) || {}).length > 0);
    const legend = levels.map((level) => (
      `<span class="inline-flex items-center gap-1.5 ${compact ? "text-xs" : "text-sm"} font-semibold text-[#5d3f3d]">`
      + `<span class="${compact ? "w-2 h-2" : "w-2.5 h-2.5"} rounded-full shrink-0" style="background:${levelBarColors[level]}"></span>`
      + `${esc(level)}</span>`
    )).join("");

    const title = "Skill Proficiency Matrix";
    const subtitle = "Employees in each proficiency level per skill.";
    const header = embedded
      ? `<h3 class="text-lg font-bold text-[#291716] mb-0.5">${esc(title)}</h3>`
        + `<p class="text-xs text-[#5d3f3d] mb-3">${esc(subtitle)}</p>`
        + `<div class="flex flex-wrap gap-x-4 gap-y-1 mb-3">${legend}</div>`
      : `<h2 class="${compact ? "text-lg" : "text-2xl"} font-extrabold text-[#291716]">${esc(title)}</h2>`
        + `<p class="${compact ? "text-xs" : "text-sm"} text-[#5d3f3d] mt-1">${esc(subtitle)}</p>`
        + `<div class="flex flex-wrap gap-x-4 gap-y-1 mt-3">${legend}</div>`;

    const shell = (body) => embedded
      ? `<div>${header}${body}</div>`
      : `<section class="bg-white rounded-xl border border-[#e7bdb9] overflow-hidden mb-8">`
        + `<div class="${compact ? "p-4" : "p-6 md:p-8"}">${header}${body}</div></section>`;

    if (!rated.length || !skillsList.length) {
      return shell(`<p class="text-xs text-[#5d3f3d]">${esc(emptyMessage || "No ratings yet.")}</p>`);
    }

    const barH = compact ? "h-6" : "h-10";
    const barText = compact ? "text-[11px]" : "text-sm";
    const minW = compact ? "1.25rem" : "2rem";
    const labelText = compact ? "text-[10px] md:text-xs" : "text-sm md:text-base";
    const skillRows = skillsList.map((skill) => {
      const counts = Object.fromEntries(levels.map((level) => [level, 0]));
      for (const emp of rated) {
        const level = (getRatings(emp) || {})[skill];
        if (level && counts[level] !== undefined) counts[level] += 1;
      }
      const total = levels.reduce((sum, level) => sum + counts[level], 0) || 1;
      const segments = levels.map((level) => {
        const n = counts[level];
        if (!n) return "";
        const pct = (n / total) * 100;
        return `<div class="${barH} flex items-center justify-center text-white ${barText} font-bold" style="flex:${n};width:${pct}%;background:${levelBarColors[level]};min-width:${minW}">${n}</div>`;
      }).join("");
      const labels = levels.map((level) => {
        const n = counts[level];
        if (!n) return "";
        return `<span class="text-center ${labelText} font-semibold text-[#5d3f3d]" style="flex:${n}">${esc(level)}</span>`;
      }).join("");
      return `<div class="${compact ? "py-2.5" : "py-5"} ${skill === skillsList[0] ? "" : "border-t border-[#e7bdb9]"}">
        <div class="grid grid-cols-1 ${compact ? "lg:grid-cols-[150px_1fr] gap-2 lg:gap-4" : "lg:grid-cols-[220px_1fr] gap-4 lg:gap-8"} items-center">
          <div>
            <p class="font-bold text-[#291716] ${compact ? "text-sm" : "text-base"}">${esc(skill)}</p>
          </div>
          <div class="min-w-0">
            <div class="flex w-full overflow-hidden rounded-full">${segments}</div>
            <div class="flex w-full mt-1">${labels}</div>
          </div>
        </div>
      </div>`;
    }).join("");

    return shell(`<div class="${compact ? "mt-1" : "mt-6"}">${skillRows}</div>`);
  }

  const nav = {
    admin: [
      ["admin/overview", "Overview", "dashboard"],
      ["admin/phases", "Phase Control", "account_tree"],
      ["admin/employees", "Employees", "group"],
      ["admin/leaderboard", "Leaderboard", "leaderboard"],
      ["admin/confidence", "Confidence Scores", "verified"],
      ["admin/audit", "Agent Audit", "manage_search"],
    ],
    lteam: [
      ["lteam/dashboard", "L-Team Dashboard", "monitoring"],
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

  async function apiBlob(path) {
    const headers = {};
    if (session.token) headers.Authorization = `Bearer ${session.token}`;
    const response = await fetch(path, { headers });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.error?.message || `Download failed (${response.status})`);
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = /filename="([^"]+)"/i.exec(disposition);
    return { blob, filename: match?.[1] || "download.xlsx" };
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  function nextIncompleteEmployee(rows, currentCode, role) {
    const statusKey = role === "rd" ? "rd_status" : "zm_status";
    const sorted = [...(rows || [])].sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")));
    const isIncomplete = (row) => {
      if (row[statusKey] === "submitted") return false;
      if (role === "rd" && row.zm_status !== "submitted") return false;
      return true;
    };
    const currentIndex = sorted.findIndex((row) => row.employee_code === currentCode);
    const start = currentIndex >= 0 ? currentIndex + 1 : 0;
    for (let index = start; index < sorted.length; index += 1) {
      if (isIncomplete(sorted[index])) return sorted[index];
    }
    return null;
  }

  function careerPathCell(row) {
    const label = String(row.rd_career_recommendation_label || row.rd_career_recommendation || "").trim();
    if (row.rd_status === "submitted" && label) {
      return `<span class="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold bg-[#d5e3ff] text-[#005cab]">${esc(label)}</span>`;
    }
    return `<span class="text-sm text-[#926e6c]">Pending</span>`;
  }

  async function bindAssessmentBulkActions(role) {
    const downloadBtn = qs("[data-download-template]");
    const uploadBtn = qs("[data-upload-template]");
    const fileInput = qs("[data-upload-file]");
    if (downloadBtn) {
      downloadBtn.onclick = async () => {
        try {
          const { blob, filename } = await apiBlob("/api/assessment/template");
          downloadBlob(blob, filename || `${String(role || "ratings").toUpperCase()}_ratings_template.xlsx`);
          toast("Template downloaded.");
        } catch (error) {
          toast(error.message, "error");
        }
      };
    }
    if (uploadBtn && fileInput) {
      uploadBtn.onclick = () => fileInput.click();
      fileInput.onchange = async () => {
        const file = fileInput.files?.[0];
        fileInput.value = "";
        if (!file) return;
        try {
          const buffer = await file.arrayBuffer();
          const bytes = new Uint8Array(buffer);
          let binary = "";
          bytes.forEach((b) => { binary += String.fromCharCode(b); });
          const content_base64 = btoa(binary);
          const result = await api("/api/assessment/upload", {
            method: "POST",
            body: JSON.stringify({ filename: file.name, content_base64 }),
          });
          const summary = result.summary || {};
          toast(`Applied ${summary.applied || 0}, skipped ${summary.skipped || 0}, errors ${summary.errors || 0}.`);
          if (role === "zm") await renderZmDashboard();
          else if (role === "rd") await renderRdDashboard();
        } catch (error) {
          toast(error.message, "error");
        }
      };
    }
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
    const label = normalized
      .replaceAll("_", " ")
      .replace(/\b\w/g, (ch) => ch.toUpperCase());
    return `<span class="inline-flex px-2.5 py-1 rounded-md text-xs font-bold ${color}">${esc(label)}</span>`;
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
    render(`<style>
      .mc-loader-wrap{max-width:40rem;margin:0 auto}
      .mc-loader-dot{animation:mc-pulse-dot 1.2s ease-in-out infinite}
      .mc-loader-dot:nth-child(2){animation-delay:.2s}
      .mc-loader-dot:nth-child(3){animation-delay:.4s}
      @keyframes mc-pulse-dot{0%,100%{opacity:.35;transform:scale(1)}50%{opacity:1;transform:scale(1.15)}}
    </style>
    <div class="py-12 md:py-20 flex flex-col items-center justify-center text-center px-4" role="status" aria-live="polite" aria-label="Loading">
      <div class="mc-loader-wrap w-full" aria-hidden="true">
        <svg class="w-full h-auto" viewBox="0 0 800 400" xmlns="http://www.w3.org/2000/svg">
          <g opacity="0.08">
            <circle cx="100" cy="100" fill="#df162b" r="40">
              <animate attributeName="cy" dur="8s" repeatCount="indefinite" values="100;120;100"/>
            </circle>
            <rect fill="#005cab" height="60" rx="10" width="60" x="650" y="50">
              <animateTransform attributeName="transform" dur="20s" from="0 680 80" repeatCount="indefinite" to="360 680 80" type="rotate"/>
            </rect>
            <circle cx="400" cy="300" fill="#df162b" r="30">
              <animate attributeName="r" dur="10s" repeatCount="indefinite" values="30;45;30"/>
            </circle>
          </g>
          <path d="M 50 320 Q 200 280 400 320 T 750 320" fill="none" stroke="#e7bdb9" stroke-dasharray="10,10" stroke-width="4">
            <animate attributeName="stroke-dashoffset" dur="1.4s" from="20" repeatCount="indefinite" to="0"/>
          </path>
          <g transform="translate(650, 220)">
            <rect fill="#5d3f3d" height="100" rx="3" width="6" x="0" y="0"/>
            <g>
              <path d="M 6 0 L 86 0 Q 96 25 86 50 L 6 50 Z" fill="#df162b">
                <animate attributeName="d" dur="2s" repeatCount="indefinite" values="M 6 0 L 86 0 Q 96 25 86 50 L 6 50 Z; M 6 0 L 86 5 Q 76 30 86 55 L 6 50 Z; M 6 0 L 86 0 Q 96 25 86 50 L 6 50 Z"/>
              </path>
              <text fill="white" font-family="Arial, sans-serif" font-size="12" font-weight="bold" text-anchor="middle" x="43" y="32">GOAL</text>
            </g>
          </g>
          <g>
            <circle fill="#df162b" opacity="0.8" r="6">
              <animateMotion begin="0s" dur="4.5s" path="M 650 250 Q 500 220 320 280" repeatCount="indefinite"/>
              <animate attributeName="r" begin="0s" dur="4.5s" repeatCount="indefinite" values="0;6;0"/>
            </circle>
            <circle fill="#005cab" opacity="0.6" r="4">
              <animateMotion begin="1.2s" dur="5.5s" path="M 650 250 Q 550 180 320 280" repeatCount="indefinite"/>
              <animate attributeName="r" begin="1.2s" dur="5.5s" repeatCount="indefinite" values="0;4;0"/>
            </circle>
            <circle fill="#df162b" opacity="0.7" r="5">
              <animateMotion begin="2.4s" dur="5s" path="M 650 250 Q 450 350 320 280" repeatCount="indefinite"/>
              <animate attributeName="r" begin="2.4s" dur="5s" repeatCount="indefinite" values="0;5;0"/>
            </circle>
          </g>
          <g>
            <animateTransform attributeName="transform" type="translate" from="40 240" to="560 240" dur="14s" fill="freeze" calcMode="linear"/>
            <g>
              <animateTransform attributeName="transform" type="translate" values="0 0; 0 -5; 0 0" dur="1.1s" repeatCount="indefinite"/>
              <g>
                <path d="M 20 50 L 10 80" stroke="#2d3748" stroke-linecap="round" stroke-width="8">
                  <animateTransform attributeName="transform" dur="1.1s" repeatCount="indefinite" type="rotate" values="-20 20 50; 20 20 50; -20 20 50"/>
                </path>
                <path d="M 20 50 L 30 80" stroke="#2d3748" stroke-linecap="round" stroke-width="8">
                  <animateTransform attributeName="transform" dur="1.1s" repeatCount="indefinite" type="rotate" values="20 20 50; -20 20 50; 20 20 50"/>
                </path>
              </g>
              <rect fill="#4a5568" height="40" rx="10" width="20" x="10" y="20"/>
              <circle cx="20" cy="10" fill="#2d3748" r="10"/>
              <g transform="translate(30, 45)">
                <rect fill="#2d3748" height="12" rx="2" width="15" x="0" y="0"/>
                <animateTransform attributeName="transform" dur="1.1s" repeatCount="indefinite" type="rotate" values="-5; 5; -5"/>
              </g>
            </g>
          </g>
        </svg>
      </div>
      <p class="text-base font-bold text-[#291716] mt-2">Heading to your next milestone…</p>
      <div class="flex items-center justify-center gap-1.5 mt-3" aria-hidden="true">
        <span class="mc-loader-dot w-2 h-2 rounded-full bg-[#df162b]"></span>
        <span class="mc-loader-dot w-2 h-2 rounded-full bg-[#df162b]"></span>
        <span class="mc-loader-dot w-2 h-2 rounded-full bg-[#df162b]"></span>
      </div>
    </div>`);
  }

  const mmtTheme = (role = session.user?.role) =>
    role === "employee" || role === "zm" || role === "rd" || role === "admin" || role === "lteam";

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
      <strong class="block text-[#291716] leading-none text-xl md:text-2xl font-extrabold tracking-tight truncate">CareerCompass</strong>
    </a>`;
  }

  function avatarStorageKey(user = session.user) {
    return `mycareer_avatar_${user?.login_id || "anon"}`;
  }

  function ackStorageKey(user = session.user) {
    return `mycareer_ack_${user?.role || "unknown"}_${user?.login_id || "anon"}`;
  }

  function loadAvatar(user = session.user) {
    try {
      const key = avatarStorageKey(user);
      const current = localStorage.getItem(key) || "";
      if (current) return current;
      // Migrate legacy role-scoped avatar keys once.
      const legacy = localStorage.getItem(`mycareer_avatar_${user?.role || "unknown"}_${user?.login_id || "anon"}`) || "";
      if (legacy) {
        localStorage.setItem(key, legacy);
        return legacy;
      }
      return "";
    } catch (_) {
      return "";
    }
  }

  function saveAvatar(dataUrl, user = session.user) {
    localStorage.setItem(avatarStorageKey(user), dataUrl);
  }

  function hasDisclaimerAck(user = session.user) {
    if (user?.disclaimer_acknowledged) return true;
    return localStorage.getItem(ackStorageKey(user)) === "1";
  }

  async function setDisclaimerAck(user = session.user) {
    localStorage.setItem(ackStorageKey(user), "1");
    if (user) {
      user.disclaimer_acknowledged = true;
    }
    if (session.user) {
      session.user.disclaimer_acknowledged = true;
    }
    if (user?.role === "employee") {
      try {
        const result = await api("/api/employee/disclaimer", { method: "POST", body: "{}" });
        if (session.user) {
          session.user.disclaimer_acknowledged = true;
          session.user.disclaimer_acknowledged_at = result.acknowledged_at || null;
        }
      } catch (error) {
        console.warn("Disclaimer DB save failed; kept local ack", error);
      }
    }
  }

  async function syncDisclaimerAckFromServer(user = session.user) {
    if (!user || user.role !== "employee") return;
    try {
      const result = await api("/api/employee/disclaimer");
      if (result.acknowledged) {
        localStorage.setItem(ackStorageKey(user), "1");
        user.disclaimer_acknowledged = true;
        user.disclaimer_acknowledged_at = result.acknowledged_at || null;
        if (session.user) {
          session.user.disclaimer_acknowledged = true;
          session.user.disclaimer_acknowledged_at = result.acknowledged_at || null;
        }
        return;
      }
      // Migrate browser-only ack into DB once.
      if (localStorage.getItem(ackStorageKey(user)) === "1") {
        await setDisclaimerAck(user);
      }
    } catch (_) {
      /* offline / older deploy — localStorage still works */
    }
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

  function formatFeedbackWhen(iso) {
    if (!iso) return "—";
    try {
      const date = new Date(iso);
      if (Number.isNaN(date.getTime())) return String(iso);
      return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
    } catch {
      return String(iso);
    }
  }

  async function openFeedbackLogbook(employeeCode) {
    closeOverlay("mc-feedback-modal");
    const result = await api(`/api/feedback?employee_code=${encodeURIComponent(employeeCode)}`);
    const employee = result.employee || {};
    const entries = result.entries || [];
    const canWrite = Boolean(result.can_write);
    const question = result.question || "";
    const node = document.createElement("div");
    node.id = "mc-feedback-modal";
    node.className = "fixed inset-0 z-[80] bg-black/40 flex items-center justify-center p-3 md:p-8";
    const history = entries.length
      ? entries.map((entry) => `<article class="border border-[#e7bdb9] rounded-xl p-4 bg-[#fff0ef]/space-y-2">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <p class="text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">${esc(formatFeedbackWhen(entry.created_at))}</p>
            <p class="text-xs text-[#926e6c]">ZM: ${esc(entry.zm_name || entry.zm_login_id || "—")}</p>
          </div>
          <p class="text-sm text-[#291716] whitespace-pre-wrap leading-relaxed">${esc(entry.answer)}</p>
        </article>`).join("")
      : `<p class="text-sm text-[#5d3f3d] py-4 text-center">No feedback entries yet.</p>`;
    const writeBlock = canWrite
      ? `<div class="border border-[#e7bdb9] rounded-xl p-4 space-y-3 bg-white">
          <p class="text-xs font-bold uppercase tracking-wider text-[#df162b]">New quarterly entry</p>
          <p class="text-sm text-[#291716] leading-relaxed">${esc(question)}</p>
          <textarea data-feedback-answer rows="5" maxlength="4000" class="w-full border border-[#e7bdb9] rounded-lg px-3 py-2 text-sm text-[#291716] focus:outline-none focus:ring-2 focus:ring-[#df162b]" placeholder="Describe whether they started the journey and any behaviour change you have seen…"></textarea>
          <div class="flex justify-end gap-2">
            <button type="button" data-submit-feedback class="px-4 py-2 bg-[#df162b] text-white rounded-lg font-bold text-sm hover:opacity-90">Save to logbook</button>
          </div>
        </div>`
      : `<div class="border border-dashed border-[#e7bdb9] rounded-xl p-4 bg-white">
          <p class="text-sm text-[#5d3f3d] leading-relaxed"><span class="font-bold text-[#291716]">Question:</span> ${esc(question)}</p>
          ${result.phase_open ? "" : `<p class="text-xs text-[#df162b] font-semibold mt-2">Feedback phase is closed. Admin can reopen it for the next quarterly cycle.</p>`}
        </div>`;
    node.innerHTML = `<div class="bg-white w-full max-w-2xl max-h-[92vh] rounded-xl shadow-2xl flex flex-col overflow-hidden border border-[#e7bdb9]" role="dialog" aria-modal="true">
      <div class="px-5 py-4 border-b border-[#e7bdb9] bg-[#fff0ef] flex items-start justify-between gap-3">
        <div>
          <h2 class="text-lg font-extrabold text-[#291716]">Journey feedback logbook</h2>
          <p class="text-sm text-[#5d3f3d] mt-1">${esc(employee.name || "Employee")} · ${esc(employee.employee_code || employeeCode)}</p>
        </div>
        <button type="button" data-close class="text-[#5d3f3d] hover:text-[#df162b]"><span class="material-symbols-outlined">close</span></button>
      </div>
      <div class="p-5 space-y-4 overflow-y-auto flex-1">
        ${writeBlock}
        <div>
          <h3 class="text-sm font-bold text-[#291716] mb-3">Past entries (${entries.length})</h3>
          <div class="space-y-3" data-feedback-history>${history}</div>
        </div>
      </div>
    </div>`;
    document.body.appendChild(node);
    const dismiss = () => node.remove();
    qs("[data-close]", node).onclick = dismiss;
    node.addEventListener("click", (event) => {
      if (event.target === node) dismiss();
    });
    const submit = qs("[data-submit-feedback]", node);
    if (submit) {
      submit.onclick = async () => {
        const answer = qs("[data-feedback-answer]", node)?.value || "";
        try {
          submit.disabled = true;
          await api("/api/feedback", {
            method: "POST",
            body: JSON.stringify({ employee_code: employeeCode, answer }),
          });
          toast("Feedback saved to logbook.");
          dismiss();
          if (session.user?.role === "zm") await renderZmDashboard();
          else if (session.user?.role === "rd") await renderRdDashboard();
          else if (session.user?.role === "admin") await initAdminEmployees();
        } catch (error) {
          toast(error.message, "error");
          submit.disabled = false;
        }
      };
    }
  }

  function openAccountModal() {
    closeOverlay("mc-account-modal");
    const user = session.user;
    const mmt = mmtTheme(user.role);
    const photo = loadAvatar(user);
    const primary = mmt ? "bg-[#df162b] text-white" : "bg-blue-700 text-white";
    const border = mmt ? "border-[#e7bdb9]" : "border-slate-200";
    const available = user.available_roles || [user.role];
    const canSwitch = available.includes("zm") && available.includes("rd");
    const switchTarget = user.role === "zm" ? "rd" : user.role === "rd" ? "zm" : "";
    const switchLabel = switchTarget === "rd" ? "Switch to RD dashboard" : "Switch to ZM dashboard";
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
        ${canSwitch && switchTarget ? `<button type="button" data-switch-role="${switchTarget}" class="w-full border ${border} text-[#291716] rounded-lg px-4 py-2.5 text-sm font-bold hover:bg-[#fff0ef] inline-flex items-center justify-center gap-2">
          <span class="material-symbols-outlined text-[18px]">swap_horiz</span>${esc(switchLabel)}
        </button>` : ""}
        <button type="button" data-open-password class="w-full ${primary} rounded-lg px-4 py-2.5 text-sm font-bold">Change password</button>
      </div>
    </div>`;
    document.body.appendChild(node);
    const dismiss = () => closeOverlay("mc-account-modal");
    node.addEventListener("click", (event) => { if (event.target === node) dismiss(); });
    qs("[data-close-account]", node).onclick = dismiss;
    qs("[data-open-password]", node).onclick = () => openPasswordModal();
    qs("[data-switch-role]", node)?.addEventListener("click", async () => {
      const target = qs("[data-switch-role]", node).dataset.switchRole;
      try {
        const result = await api("/api/auth/switch-role", {
          method: "POST",
          body: JSON.stringify({ role: target }),
        });
        session.token = result.token;
        session.user = result.user;
        localStorage.setItem(tokenKey, result.token);
        localStorage.setItem(userKey, JSON.stringify(result.user));
        dismiss();
        go(result.user.role === "admin" ? "admin/overview" : result.user.role === "lteam" ? "lteam/dashboard" : `${result.user.role}/welcome`);
      } catch (error) {
        if (error.code === "phase_closed") {
          dismiss();
          showPhaseNotOpenYet(target);
        } else {
          toast(error.message, "error");
        }
      }
    });
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

  function showPhaseNotOpenYet(role) {
    closeOverlay("mc-phase-closed");
    const label = role === "rd" ? "RD" : role === "zm" ? "ZM" : String(role || "This").toUpperCase();
    const node = document.createElement("div");
    node.id = "mc-phase-closed";
    node.className = "fixed inset-0 z-[90] bg-black/40 grid place-items-center p-4";
    node.innerHTML = `<div class="bg-white rounded-xl shadow-2xl w-full max-w-sm border border-[#e7bdb9] p-6 text-center">
      <div class="w-16 h-16 mx-auto rounded-full bg-[#fff0ef] grid place-items-center text-[#df162b] mb-4">
        <span class="material-symbols-outlined text-[36px]">lock_clock</span>
      </div>
      <h2 class="text-xl font-extrabold text-[#291716] mb-2">${esc(label)} portal not open yet</h2>
      <p class="text-sm text-[#5d3f3d] mb-5">This phase is not open yet. You will be notified when access becomes available.</p>
      <button type="button" data-close-phase class="px-6 py-2.5 border border-[#e7bdb9] rounded-full text-sm font-bold text-[#291716] hover:bg-[#fff0ef]">OK</button>
    </div>`;
    document.body.appendChild(node);
    const dismiss = () => closeOverlay("mc-phase-closed");
    node.addEventListener("click", (event) => { if (event.target === node) dismiss(); });
    qs("[data-close-phase]", node).onclick = dismiss;
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
    agreeBtn.onclick = async () => {
      if (!inner.checked) return;
      dismiss();
      await onAgree?.();
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
      <p class="text-sm text-[#5d3f3d] text-center lg:text-right">© 2000 MakeMyTrip Talent Development. All rights reserved.</p>
    </footer>`;
  }

  function mountShell(user) {
    const items = nav[user.role] || [];
    const mmt = mmtTheme(user.role);
    const links = commonSideNav(user, mmt);
    const homeRoute = items[0]?.[0] || "login";
    const border = mmt ? "border-[#e7bdb9]" : "border-slate-200";
    const managerChrome = user.role === "zm" || user.role === "rd" || user.role === "admin" || user.role === "lteam";
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
          body: JSON.stringify({ login_id: inputs[0].value.trim(), password: inputs[1].value }),
        });
        session.token = result.token;
        session.user = result.user;
        localStorage.setItem(tokenKey, result.token);
        localStorage.setItem(userKey, JSON.stringify(result.user));
        const role = result.user.role;
        go(role === "admin" ? "admin/overview" : role === "lteam" ? "lteam/dashboard" : `${role}/welcome`);
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
      await syncDisclaimerAckFromServer(session.user);
      const expectedRole = page.split("/")[0];
      if (expectedRole !== session.user.role) {
        go(session.user.role === "admin" ? "admin/overview" : session.user.role === "lteam" ? "lteam/dashboard" : `${session.user.role}/welcome`);
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
    // Keep full glyph in view (rotate + huge type otherwise clips under overflow-hidden).
    return `<div class="absolute right-[-0.5rem] top-1/2 -translate-y-[55%] opacity-10 pointer-events-none hidden lg:block" aria-hidden="true">
      <span class="material-symbols-outlined text-[260px] md:text-[300px] text-[#df162b] rotate-12 leading-none block" style="font-variation-settings:'FILL' 0">explore</span>
    </div>`;
  }

  async function initRdWelcome() {
    const cards = [
      ["balance", "Why this validation matters", "Ensuring every team member is evaluated on a common set of competencies, so their learning journey is focused, fair, and growth-oriented."],
      ["query_stats", "Use evidence, not assumptions", "Incorporate data-backed scenarios, measurable KPIs, and project-specific examples to make competency assessments more objective and actionable."],
      ["military_tech", "Focus on proficiency", "Each skill has defined proficiency levels. Assess each team member’s demonstrated skill before finalizing their level."],
      ["route", "Enable development", "Every input identifies a growth opportunity which will curate specific learning path of each team member."],
    ];
    const steps = [
      ["1", "#005cab", "Review ZM's Input", "Assess the competency profile of the team member submitted by the ZM."],
      ["2", "#005cab", "Calibrate Performance", "Callibrate the competency profile of the team member with the observed performance and objective data."],
      ["3", "#df162b", "Finalize Profile", "Help the team member navigate their professional journey."],
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
            Turn evidence into a fair and consistent <span class="text-[#df162b]">competency profile for your team</span>
          </h1>
          <p class="text-lg text-[#5d3f3d] leading-relaxed max-w-2xl mb-8">
            As a Regional Director, your role is to validate proficiencies based on observed performance and objective data. Help the talent navigate their professional journey with clarity and rigor.
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
            <p class="text-sm opacity-90">Your assessment will be considered as a foundation for organizational planning and talent decisions.</p>
          </div>
        </section>
        <section class="flex flex-col lg:flex-row items-center justify-between gap-10">
          <div class="hidden lg:block w-1/3 shrink-0">
            <div class="aspect-square rounded-2xl overflow-hidden border-8 border-white shadow-xl bg-[#fff0ef] flex items-center justify-center">
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
              <h2 class="text-xl font-bold mb-1">Your feedback input creates the starting point</h2>
              <p class="max-w-3xl opacity-90">The competency assessments you provide today will form the foundation of your team’s Personalized Learning Path. Accurate inputs help identify the right focus areas for each employee to hone their skills and grow with confidence.</p>
            </div>
          </div>
        </section>
      </div>
    </div>`, { flush: true });
    qs("[data-start]")?.addEventListener("click", () => go(qs("[data-start]").dataset.start || "zm/dashboard"));
  }

  async function initEmployeeWelcome() {
    await syncDisclaimerAckFromServer();
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
    const completed = Number(roleplays.completed ?? (roleplays.sessions || []).filter((item) => item.status === "completed").length);
    const total = Number(roleplays.total ?? (roleplays.sessions || []).length ?? 2);
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
          ? `Both voice roleplay sessions completed.`
          : `${completed} of ${total} voice roleplay sessions completed.`,
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
          : "Complete both voice roleplays to unlock Career Lattice.",
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
          ? `Aspiration Selected: ${aspirationLabel}.`
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
      <section class="relative py-12 md:py-14 bg-[#fff0ef] overflow-x-hidden" style="background-image:radial-gradient(circle at 2px 2px,#df162b22 1px,transparent 0);background-size:24px 24px">
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
                <button type="button" data-open-disclaimer class="text-[#0075d7] font-semibold underline hover:opacity-80">Click to read more</button>
                ${acked ? `<span data-ack-badge class="ml-2 text-[#93000a] font-semibold">· Acknowledged</span>` : `<span data-ack-badge class="hidden ml-2 text-[#93000a] font-semibold">· Acknowledged</span>`}
              </p>
              <a href="https://imgak.mmtcdn.com/mmt-careers-ui/assets/static/documents/Career_Progression_Guide.pdf" target="_blank" rel="noopener noreferrer" class="text-[#0075d7] font-semibold underline hover:opacity-80 shrink-0">See more about this</a>
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
      openDisclaimerModal(async () => {
        if (!hasDisclaimerAck()) {
          await setDisclaimerAck();
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
        return `<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-cyan-50 text-cyan-800"><span class="material-symbols-outlined text-sm">check_circle</span>Completed</span>`;
      }
      if (key === "draft") {
        return `<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-blue-50 text-blue-800"><span class="material-symbols-outlined text-sm">edit</span>Draft</span>`;
      }
      if (key === "ready") {
        return `<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-emerald-50 text-emerald-800"><span class="material-symbols-outlined text-sm">verified_user</span>Ready for RD</span>`;
      }
      return `<span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-red-50 text-red-800"><span class="material-symbols-outlined text-sm">hourglass_empty</span>Waiting for ZM's Input</span>`;
    };

    const filteredSorted = () => {
      let list = rows.filter((row) => filterStatus === "all" || statusKey(row) === filterStatus);
      const rank = { pending: 0, ready: 1, draft: 2, completed: 3 };
      list = [...list].sort((a, b) => {
        if (sortMode === "name-asc") return String(a.name || "").localeCompare(String(b.name || ""));
        if (sortMode === "name-desc") return String(b.name || "").localeCompare(String(a.name || ""));
        if (sortMode === "code-asc") return String(a.employee_code || "").localeCompare(String(b.employee_code || ""), undefined, { numeric: true });
        if (sortMode === "code-desc") return String(b.employee_code || "").localeCompare(String(a.employee_code || ""), undefined, { numeric: true });
        if (sortMode === "status-asc") return rank[statusKey(a)] - rank[statusKey(b)] || String(a.name || "").localeCompare(String(b.name || ""));
        if (sortMode === "status-desc") return rank[statusKey(b)] - rank[statusKey(a)] || String(a.name || "").localeCompare(String(b.name || ""));
        return 0;
      });
      return list;
    };

    const filterLabel = {
      all: "All",
      pending: "Waiting for ZM's Input",
      ready: "Ready for Assessment",
      draft: "Draft",
      completed: "Completed",
    };
    const sortLabel = {
      "name-asc": "Name A–Z",
      "name-desc": "Name Z–A",
      "code-asc": "Employee code A–Z",
      "code-desc": "Employee code Z–A",
      "status-asc": "Status: Awaiting first",
      "status-desc": "Status: Completed first",
    };

    const draw = () => {
      const list = filteredSorted();
      const tableRows = list.map((row) => {
        const key = statusKey(row);
        const initialsRow = String(row.name || "E").split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase() || "").join("") || "E";
        const canOpen = key !== "pending";
        const actionLabel = key === "completed" ? "View Assessment" : key === "draft" ? "Continue Validation" : key === "ready" ? "Start Validation" : "Waiting for ZM's Input";
        const actionClass = canOpen
          ? (key === "completed"
            ? "px-4 py-2 bg-[#005cab] text-white rounded-lg font-bold text-sm hover:opacity-90"
            : "px-4 py-2 bg-[#df162b] text-white rounded-lg font-bold text-sm hover:opacity-90")
          : "px-4 py-2 bg-slate-200 text-slate-500 rounded-lg font-bold text-sm cursor-not-allowed";
        const actionAttr = key === "completed"
          ? `data-view-ratings="${esc(row.employee_code)}"`
          : `data-employee="${esc(row.employee_code)}"`;
        const fbCount = Number(row.feedback_count) || 0;
        const feedbackBtn = `<button type="button" data-feedback="${esc(row.employee_code)}" class="px-3 py-2 border border-[#005cab] text-[#005cab] rounded-lg font-bold text-sm hover:bg-[#d5e3ff]">${fbCount ? `View entry (${fbCount})` : "View entry"}</button>`;
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
          <td class="p-4">${careerPathCell(row)}</td>
          <td class="p-4">${feedbackBtn}</td>
          <td class="p-4 text-right">
            <button type="button" ${actionAttr} ${canOpen ? "" : "disabled"} class="${actionClass}">${esc(actionLabel)}</button>
          </td>
        </tr>`;
      }).join("") || empty(filterStatus === "all" ? "No employees in your reporting scope." : "No employees match this filter.", 5);

      const filterActive = filterStatus !== "all";
      const chipBase = "px-3 py-1.5 bg-white border rounded-full text-xs font-bold inline-flex items-center gap-1 cursor-pointer hover:border-[#df162b] hover:text-[#df162b] transition-colors";
      const chipOn = "border-[#df162b] text-[#df162b] bg-[#fff0ef]";
      const chipOff = "border-[#e7bdb9] text-[#5d3f3d]";

      render(`<div class="mb-8 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
          <div>
            <h1 class="text-2xl md:text-3xl font-extrabold text-[#df162b]">Your Dashboard</h1>
            <p class="text-[#5d3f3d] mt-1">Validate proficiency after ZM submission and finalize competency profiles.</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <button type="button" data-download-template class="px-4 py-2 border border-[#005cab] text-[#005cab] rounded-lg font-bold text-sm hover:bg-[#d5e3ff] inline-flex items-center gap-1">
              <span class="material-symbols-outlined text-[18px]">download</span> Download template
            </button>
            <button type="button" data-upload-template class="px-4 py-2 bg-[#005cab] text-white rounded-lg font-bold text-sm hover:opacity-90 inline-flex items-center gap-1">
              <span class="material-symbols-outlined text-[18px]">upload</span> Upload Excel
            </button>
            <input type="file" data-upload-file accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv" class="hidden"/>
          </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <div class="bg-white p-5 rounded-xl border border-[#e7bdb9] flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-[#d5e3ff] flex items-center justify-center"><span class="material-symbols-outlined text-[#005cab]">groups</span></div>
            <div><p class="text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Total Assessment to Take</p><p class="text-2xl font-bold text-[#291716]">${total}</p></div>
          </div>
          <div class="bg-white p-5 rounded-xl border border-[#e7bdb9] flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-[#c3e8ff] flex items-center justify-center"><span class="material-symbols-outlined text-[#005f81]">verified_user</span></div>
            <div><p class="text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Yet to Start</p><p class="text-2xl font-bold text-[#005f81]">${ready}</p></div>
          </div>
          <div class="bg-white p-5 rounded-xl border border-[#e7bdb9] flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-[#ffe1df] flex items-center justify-center"><span class="material-symbols-outlined text-[#df162b]">edit</span></div>
            <div><p class="text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">In Progress</p><p class="text-2xl font-bold text-[#df162b]">${drafts}</p></div>
          </div>
          <div class="bg-white p-5 rounded-xl border border-[#e7bdb9] flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-emerald-50 flex items-center justify-center"><span class="material-symbols-outlined text-emerald-700">check_circle</span></div>
            <div><p class="text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Completed</p><p class="text-2xl font-bold text-emerald-700">${validated}</p></div>
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
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Status</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Career path (RD)</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Feedback</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-[#5d3f3d] text-right">Action</th>
              </tr></thead>
              <tbody>${tableRows}</tbody>
            </table>
          </div>
        </div>`);

      qsa("[data-employee]").forEach((control) => {
        if (control.disabled) return;
        control.onclick = () => go("rd/validation", `?employee=${encodeURIComponent(control.dataset.employee)}`);
      });
      qsa("[data-feedback]").forEach((control) => {
        control.onclick = () => openFeedbackLogbook(control.dataset.feedback).catch((error) => toast(error.message, "error"));
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
      bindAssessmentBulkActions("rd");
    };

    draw();
  }

  async function renderZmDashboard() {
    const [rows, meta] = await Promise.all([employeeSummaries(), api("/api/meta")]);
    const competencies = (meta.competencies || []).map((item) => item.competency).filter(Boolean);
    const total = rows.length;
    const rated = rows.filter((row) => row.zm_status === "submitted").length;
    const draftCount = rows.filter((row) => row.zm_status === "draft").length;
    const remaining = total - rated - draftCount;
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

    const levelChip = (level) => {
      if (!level) return `<span class="text-sm text-[#926e6c]">—</span>`;
      const colors = {
        Beginner: "bg-red-50 text-red-800",
        Intermediate: "bg-amber-50 text-amber-900",
        Proficient: "bg-cyan-50 text-cyan-900",
        Advanced: "bg-emerald-50 text-emerald-900",
      };
      return `<span class="inline-block px-2.5 py-1 rounded-md text-sm font-bold whitespace-nowrap ${colors[level] || "bg-slate-50 text-slate-700"}">${esc(level)}</span>`;
    };

    const filteredSorted = () => {
      let list = rows.filter((row) => filterStatus === "all" || statusKey(row) === filterStatus);
      const rank = { pending: 0, draft: 1, completed: 2 };
      list = [...list].sort((a, b) => {
        if (sortMode === "name-asc") return String(a.name || "").localeCompare(String(b.name || ""));
        if (sortMode === "name-desc") return String(b.name || "").localeCompare(String(a.name || ""));
        if (sortMode === "code-asc") return String(a.employee_code || "").localeCompare(String(b.employee_code || ""), undefined, { numeric: true });
        if (sortMode === "code-desc") return String(b.employee_code || "").localeCompare(String(a.employee_code || ""), undefined, { numeric: true });
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
      "code-asc": "Employee code A–Z",
      "code-desc": "Employee code Z–A",
      "status-asc": "Status: Pending first",
      "status-desc": "Status: Completed first",
    };

    const draw = () => {
      const list = filteredSorted();
      const ratedEmployees = rows.filter((row) => {
        const ratings = row.zm_ratings || {};
        return (row.zm_status === "draft" || row.zm_status === "submitted") && Object.keys(ratings).length > 0;
      });
      const tableRows = list.map((row) => {
        const done = row.zm_status === "submitted";
        const draft = row.zm_status === "draft";
        const finalReady = row.rd_status === "submitted" || row.final_profile_available;
        const initialsRow = String(row.name || "E").split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase() || "").join("") || "E";
        const actionBtn = done
          ? ""
          : draft
            ? `<button type="button" data-employee="${esc(row.employee_code)}" class="px-4 py-2 bg-[#df162b] text-white rounded-lg font-bold text-sm hover:opacity-90">Continue Assessment</button>`
            : `<button type="button" data-employee="${esc(row.employee_code)}" class="px-4 py-2 bg-[#df162b] text-white rounded-lg font-bold text-sm hover:opacity-90">Start Assessment</button>`;
        const finalBtn = finalReady
          ? `<button type="button" data-view-ratings="${esc(row.employee_code)}" class="px-4 py-2 bg-emerald-700 text-white rounded-lg font-bold text-sm hover:opacity-90">View Final Assessment</button>`
          : "";
        const fbCount = Number(row.feedback_count) || 0;
        const fbOpen = Boolean(row.feedback_phase_open);
        const feedbackBtn = fbOpen
          ? `<button type="button" data-feedback="${esc(row.employee_code)}" class="px-3 py-2 border border-[#005cab] text-[#005cab] rounded-lg font-bold text-sm hover:bg-[#d5e3ff]">${fbCount ? `Add feedback (${fbCount})` : "Add feedback"}</button>`
          : `<button type="button" data-feedback="${esc(row.employee_code)}" class="px-3 py-2 border border-[#e7bdb9] text-[#5d3f3d] rounded-lg font-bold text-sm hover:bg-[#fff0ef]">${fbCount ? `View entry (${fbCount})` : "View entry"}</button>`;
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
          <td class="p-4">${careerPathCell(row)}</td>
          <td class="p-4">${feedbackBtn}</td>
          <td class="p-4 text-right">
            <div class="inline-flex flex-wrap justify-end gap-2">
              ${actionBtn}
              ${finalBtn}
            </div>
          </td>
        </tr>`;
      }).join("") || empty(filterStatus === "all" ? "No employees in your reporting scope." : "No employees match this filter.", 5);

      const matrixSection = `<section class="bg-white rounded-xl border border-[#e7bdb9] overflow-hidden mb-8">
        <div class="p-4 bg-[#fff0ef] border-b border-[#e7bdb9]">
          <h2 class="text-lg font-extrabold text-[#291716]">Your Team's Competency Profile</h2>
        </div>
        ${ratedEmployees.length && competencies.length ? `<div class="overflow-x-auto">
          <table class="w-full min-w-[880px] text-left">
            <thead>
              <tr class="border-b border-[#e7bdb9] bg-[#fafafa]">
                <th class="p-3 text-xs font-bold uppercase tracking-wider text-[#5d3f3d] sticky left-0 bg-[#fafafa] z-10 min-w-[180px]">Employee</th>
                ${competencies.map((skill) => `<th class="p-3 text-xs font-bold text-[#5d3f3d] text-center min-w-[120px]">${esc(skill)}</th>`).join("")}
              </tr>
            </thead>
            <tbody>
              ${ratedEmployees.map((row, index) => `<tr class="border-t border-[#e7bdb9] ${index % 2 ? "bg-[#f8fbff]" : "bg-white"}">
                <td class="p-3 sticky left-0 ${index % 2 ? "bg-[#f8fbff]" : "bg-white"} z-10">
                  <p class="text-sm font-bold text-[#291716]">${esc(row.name)}</p>
                  <p class="text-[10px] text-[#926e6c]">${esc(row.employee_code)}</p>
                </td>
                ${competencies.map((skill) => `<td class="p-3 text-center">${levelChip((row.zm_ratings || {})[skill])}</td>`).join("")}
              </tr>`).join("")}
            </tbody>
          </table>
        </div>` : `<p class="p-6 text-sm text-[#5d3f3d]">No ratings yet. Start or continue an assessment to populate this matrix.</p>`}
      </section>`;

      const filterActive = filterStatus !== "all";
      const chipBase = "px-3 py-1.5 bg-white border rounded-full text-xs font-bold inline-flex items-center gap-1 cursor-pointer hover:border-[#df162b] hover:text-[#df162b] transition-colors";
      const chipOn = "border-[#df162b] text-[#df162b] bg-[#fff0ef]";
      const chipOff = "border-[#e7bdb9] text-[#5d3f3d]";

      render(`<div class="mb-8 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
          <div>
            <h1 class="text-2xl md:text-3xl font-extrabold text-[#df162b]">Your Dashboard</h1>
            <p class="text-[#5d3f3d] mt-1">Complete skill competency assessment of your team member.</p>
          </div>
          <div class="flex flex-wrap gap-2">
            <button type="button" data-download-template class="px-4 py-2 border border-[#005cab] text-[#005cab] rounded-lg font-bold text-sm hover:bg-[#d5e3ff] inline-flex items-center gap-1">
              <span class="material-symbols-outlined text-[18px]">download</span> Download template
            </button>
            <button type="button" data-upload-template class="px-4 py-2 bg-[#005cab] text-white rounded-lg font-bold text-sm hover:opacity-90 inline-flex items-center gap-1">
              <span class="material-symbols-outlined text-[18px]">upload</span> Upload Excel
            </button>
            <input type="file" data-upload-file accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv" class="hidden"/>
          </div>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 mb-8">
          <div class="bg-white p-5 rounded-xl border border-[#e7bdb9] flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-[#d5e3ff] flex items-center justify-center"><span class="material-symbols-outlined text-[#005cab]">groups</span></div>
            <div><p class="text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Total Assessments to Take</p><p class="text-2xl font-bold text-[#291716]">${total}</p></div>
          </div>
          <div class="bg-white p-5 rounded-xl border border-[#e7bdb9] flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-[#c3e8ff] flex items-center justify-center"><span class="material-symbols-outlined text-[#005f81]">verified</span></div>
            <div><p class="text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Completed</p><p class="text-2xl font-bold text-[#005f81]">${rated}</p></div>
          </div>
          <div class="bg-white p-5 rounded-xl border border-[#e7bdb9] flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-blue-50 flex items-center justify-center"><span class="material-symbols-outlined text-[#005cab]">edit</span></div>
            <div><p class="text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">In Progress</p><p class="text-2xl font-bold text-[#005cab]">${draftCount}</p></div>
          </div>
          <div class="bg-white p-5 rounded-xl border border-[#e7bdb9] flex items-center gap-4">
            <div class="w-12 h-12 rounded-full bg-[#ffe1df] flex items-center justify-center"><span class="material-symbols-outlined text-[#df162b]">hourglass_empty</span></div>
            <div><p class="text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Yet to Start</p><p class="text-2xl font-bold text-[#df162b]">${remaining}</p></div>
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
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Career path (RD)</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-[#5d3f3d]">Feedback</th>
                <th class="p-4 text-xs font-bold uppercase tracking-wider text-[#5d3f3d] text-right">Action</th>
              </tr></thead>
              <tbody>${tableRows}</tbody>
            </table>
          </div>
        </div>
        ${matrixSection}`);

      qsa("[data-employee]").forEach((control) => {
        control.onclick = () => openAssessment(control.dataset.employee);
      });
      qsa("[data-feedback]").forEach((control) => {
        control.onclick = () => openFeedbackLogbook(control.dataset.feedback).catch((error) => toast(error.message, "error"));
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
      bindAssessmentBulkActions("zm");
    };

    draw();
    if (params.get("employee")) openAssessment(params.get("employee"));
  }

  async function openAssessment(employeeCode) {
    loading();
    try {
      const [meta, existing, rows, evidenceCtx] = await Promise.all([
        api("/api/meta"),
        api(`/api/assessment?employee_code=${encodeURIComponent(employeeCode)}`),
        employeeSummaries(),
        api(`/api/zm/evidence?employee_code=${encodeURIComponent(employeeCode)}`).catch(() => ({ evidence: {} })),
      ]);
      const employee = rows.find((row) => row.employee_code === employeeCode);
      if (!employee) throw new Error("Employee not found in your reporting scope.");
      const assessment = existing.assessment;
      const locked = assessment?.status === "submitted";
      const evidenceBySkill = evidenceCtx.evidence || {};
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
      <div class="bg-white w-full max-w-6xl h-full max-h-[95vh] rounded-xl shadow-2xl flex flex-col overflow-hidden" role="dialog" aria-modal="true">
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
          ${meta.competencies.map((item) => {
            const bundle = evidenceBySkill[item.competency] || {};
            const suggested = String(bundle.suggested_rating || "").trim();
            const savedRating = assessment?.ratings?.[item.competency] || "";
            const activeRating = savedRating || suggested || "";
            const noteRequired = Boolean(suggested && activeRating && activeRating !== suggested);
            return `<section class="bg-white rounded-xl border border-gray-200 p-5 md:p-6 shadow-sm" data-zm-skill="${esc(item.competency)}" data-suggested="${esc(suggested)}">
            <div class="grid lg:grid-cols-2 gap-6">
              <div>
                <div class="mb-5 md:mb-6">
                  <h2 class="text-lg font-bold text-gray-900">${esc(item.competency)}</h2>
                  <p class="text-sm text-gray-600 mt-1 italic">${esc(item.definition)}</p>
                  ${suggested ? `<div class="mt-3 p-3 rounded-lg border border-[#d5e3ff] bg-[#f5f8ff]">
                    <p class="text-xs font-bold uppercase tracking-wide text-[#1464F4]">AI suggested rating</p>
                    <p class="text-sm font-bold text-[#291716] mt-1">${esc(suggested)}</p>
                    <p class="text-[10px] text-[#926e6c] mt-2">Pre-filled from supporting evidence — edit if needed. A note is required if you choose a different level.</p>
                  </div>` : ""}
                </div>
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 md:gap-4 mb-5 md:mb-6">
                  ${levels.map((level) => {
                    const checked = activeRating === level;
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
                <label class="block text-xs font-bold uppercase tracking-wide text-gray-500 mb-1" data-note-label="${esc(item.competency)}">
                  ${noteRequired ? 'Note <span class="text-[#df162b]">(required — differs from AI suggestion)</span>' : "Note (optional)"}
                </label>
                <textarea data-note="${esc(item.competency)}" ${locked ? "disabled" : ""} rows="3" class="w-full border border-gray-200 rounded-lg text-sm p-3 focus:ring-[#df162b] focus:border-[#df162b] placeholder:text-gray-400 placeholder:italic disabled:bg-gray-50 ${noteRequired ? "border-[#df162b]/50" : ""}" placeholder="${noteRequired ? "Explain why your rating differs from the AI suggestion…" : "Add optional evidence notes here..."}">${esc(assessment?.notes?.[item.competency] || "")}</textarea>
              </div>
              <div>
                <h3 class="font-bold text-sm text-[#291716]">Supporting Evidence From Previous Feedbacks</h3>
                ${renderEvidencePanel(bundle)}
              </div>
            </div>
          </section>`;
          }).join("")}
          ${(() => {
            const careerMove = evidenceCtx.career_move || {};
            const options = careerMove.options || [];
            const selected = assessment?.career_recommendation || "";
            if (!options.length) return "";
            return `<section class="bg-white rounded-xl border border-gray-200 p-5 md:p-6 shadow-sm">
              <h2 class="text-lg font-bold text-gray-900">${esc(careerMove.question || "What career move do you recommend for the employee?")}</h2>
              <p class="text-sm text-gray-500 mt-1">Required before submit. Your choice is private to Admin.</p>
              <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mt-4">
                ${options.map((opt) => {
                  const checked = selected === opt.id;
                  return `<label class="relative ${locked ? "cursor-default" : "cursor-pointer"}">
                    <input class="sr-only zm-assess-radio" type="radio" name="career-move" value="${esc(opt.id)}" ${checked ? "checked" : ""} ${locked ? "disabled" : ""}/>
                    <div class="zm-assess-card h-full p-4 border border-gray-200 rounded-lg hover:border-[#df162b]/40 transition-all">
                      <div class="flex items-center gap-3">
                        <div class="zm-assess-dot w-4 h-4 rounded-full border-2 border-gray-300 flex items-center justify-center shrink-0">
                          <div class="zm-assess-dot-inner w-2 h-2 rounded-full transform scale-0 transition-transform duration-200"></div>
                        </div>
                        <span class="font-bold text-sm text-gray-900">${esc(opt.label)}</span>
                      </div>
                    </div>
                  </label>`;
                }).join("")}
              </div>
            </section>`;
          })()}
          <footer class="py-6 flex flex-col items-center justify-center space-y-3">
            <div class="flex items-center gap-2">
              <img src="/stitch/common/my-logo.png" alt="my" class="w-8 h-8 rounded-lg object-cover"/>
              <span class="text-gray-800 font-bold tracking-tight text-lg">CareerCompass</span>
            </div>
            <p class="text-[10px] text-[#df162b]/40 uppercase tracking-widest font-bold">© 2026 MakeMyTrip Talent Development. All rights reserved.</p>
            ${locked ? `<div class="pt-2"><div class="bg-[#df162b]/5 px-6 py-2 rounded-full border border-[#df162b]/10"><p class="text-[#df162b] font-semibold text-sm">Submitted and locked</p></div></div>` : ""}
          </footer>
        </main>
      </div>`;
      document.body.appendChild(modal);
      const syncZmNoteRequirement = (skill) => {
        const section = qs(`[data-zm-skill="${CSS.escape(skill)}"]`, modal);
        if (!section) return;
        const suggested = String(section.dataset.suggested || "").trim();
        const selected = qs(`input[name="rating-${CSS.escape(skill)}"]:checked`, modal);
        const rating = selected ? selected.value : "";
        const required = Boolean(suggested && rating && rating !== suggested);
        const label = qs(`[data-note-label="${CSS.escape(skill)}"]`, modal);
        const note = qs(`[data-note="${CSS.escape(skill)}"]`, modal);
        if (label) {
          label.innerHTML = required
            ? 'Note <span class="text-[#df162b]">(required — differs from AI suggestion)</span>'
            : "Note (optional)";
        }
        if (note) {
          note.placeholder = required
            ? "Explain why your rating differs from the AI suggestion…"
            : "Add optional evidence notes here...";
          note.classList.toggle("border-[#df162b]/50", required);
        }
      };
      if (!locked) {
        qsa(".zm-assess-radio[name^='rating-']", modal).forEach((input) => {
          input.addEventListener("change", () => {
            const skill = String(input.name || "").replace(/^rating-/, "");
            if (skill) syncZmNoteRequirement(skill);
          });
        });
        meta.competencies.forEach((item) => syncZmNoteRequirement(item.competency));
      }
      const closeAssessment = () => {
        modal.remove();
        renderZmDashboard().catch((err) => toast(err.message, "error"));
      };
      qs("[data-close]", modal).onclick = () => closeAssessment();
      modal.addEventListener("click", (event) => {
        if (event.target === modal) closeAssessment();
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
        const careerPick = qs('input[name="career-move"]:checked', modal);
        if (submit && !careerPick) {
          toast("Select a career move recommendation before submission.", "error");
          return;
        }
        const notes = Object.fromEntries(qsa("[data-note]", modal).map((node) => [node.dataset.note, node.value]));
        if (submit) {
          const missingNotes = meta.competencies
            .map((item) => item.competency)
            .filter((skill) => {
              const suggested = String(evidenceBySkill[skill]?.suggested_rating || "").trim();
              if (!suggested || !ratings[skill] || ratings[skill] === suggested) return false;
              return !String(notes[skill] || "").trim();
            });
          if (missingNotes.length) {
            toast(`Add a note where your rating differs from AI: ${missingNotes.join(", ")}`, "error");
            return;
          }
        }
        if (submit && !confirm("Submit and lock this assessment?")) return;
        await api("/api/assessment", {
          method: "POST",
          body: JSON.stringify({
            employee_code: employeeCode,
            ratings,
            notes,
            submit,
            career_recommendation: careerPick ? careerPick.value : (assessment?.career_recommendation || ""),
          }),
        });
        if (!submit) {
          toast("Draft saved.");
          return;
        }
        modal.remove();
        toast("Assessment submitted.");
        const refreshed = await employeeSummaries();
        const next = nextIncompleteEmployee(refreshed, employeeCode, "zm");
        if (!next) {
          toast("All eligible employees assessed.");
          await renderZmDashboard();
          return;
        }
        const nextModal = document.createElement("div");
        nextModal.className = "fixed inset-0 z-[80] bg-black/40 flex items-center justify-center p-4";
        nextModal.innerHTML = `<div class="bg-white rounded-xl shadow-2xl border border-[#e7bdb9] w-full max-w-md p-6">
          <h2 class="text-lg font-extrabold text-[#291716]">Assessment submitted</h2>
          <p class="text-sm text-[#5d3f3d] mt-2">Continue with <strong>${esc(next.name)}</strong> (${esc(next.employee_code)})?</p>
          <div class="mt-5 flex flex-wrap justify-end gap-2">
            <button type="button" data-back-dash class="px-4 py-2 border border-[#e7bdb9] rounded-lg font-bold text-sm text-[#5d3f3d]">Back to dashboard</button>
            <button type="button" data-next-emp class="px-4 py-2 bg-[#df162b] text-white rounded-lg font-bold text-sm">Next employee</button>
          </div>
        </div>`;
        document.body.appendChild(nextModal);
        qs("[data-back-dash]", nextModal).onclick = async () => {
          nextModal.remove();
          await renderZmDashboard();
        };
        qs("[data-next-emp]", nextModal).onclick = async () => {
          nextModal.remove();
          await renderZmDashboard();
          openAssessment(next.employee_code);
        };
      };
      if (!locked) {
        qs("[data-save]", modal).onclick = () => save(false).catch((error) => toast(error.message, "error"));
        qs("[data-submit]", modal).onclick = () => save(true).catch((error) => toast(error.message, "error"));
      }
    } catch (error) {
      toast(error.message, "error");
      await renderZmDashboard();
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
    // Hide legacy "Amber Question 31" / "Amber Answer 12" style labels.
    if (src === "amber" && /^amber\s+(question|answer|follow-up comments|driver\(element name\)|mood)\s+\d+$/i.test(text)) {
      return "";
    }
    if (/^employee\s+input\s*\d*$/i.test(text)) return "Employee learning need";
    return text.replace(/^amber\s+/i, "").trim();
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
    const careerMove = context.career_move || {};
    const careerOptions = careerMove.options || [];
    let careerRecommendation = context.rd_assessment?.career_recommendation || "";
    const careerMoveHtml = careerOptions.length
      ? `<section class="bg-white border border-[#e7bdb9] rounded-xl p-5">
        <h2 class="text-lg font-bold text-[#291716]">${esc(careerMove.question || "What career move do you recommend for the employee?")}</h2>
        <p class="text-sm text-[#5d3f3d] mt-1">Required before submit. Your choice is private to Admin.</p>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 mt-4">
          ${careerOptions.map((opt) => {
            const selected = careerRecommendation === opt.id;
            return `<button type="button" data-career-move="${esc(opt.id)}" ${locked ? "disabled" : ""} class="text-left p-3 border rounded-lg transition-colors ${
              selected ? "bg-[#df162b] text-white border-[#df162b]" : "border-[#e7bdb9] bg-white hover:border-[#df162b]/50"
            }"><strong class="block text-sm">${esc(opt.label)}</strong></button>`;
          }).join("")}
        </div>
      </section>`
      : "";
    render(`${pageHeader(`${context.employee.name}'s Competency Profile`, `${context.employee.employee_code} · ${context.employee.designation || context.employee.role_name || "—"} · ${context.employee.grade || ""}`, button("Back", "data-back", true))}
      <div class="space-y-5">${Object.entries(context.evidence).map(([competency, bundle]) => {
        const suggested = String(bundle.suggested_rating || "").trim();
        const activeRating = ratings[competency] || "";
        return `<section class="bg-white border border-[#e7bdb9] rounded-xl p-5" data-rd-skill="${esc(competency)}" data-suggested="${esc(suggested)}">
        <div class="grid lg:grid-cols-2 gap-6">
          <div>
            <h2 class="text-lg font-bold text-[#291716]">${esc(competency)}</h2>
            <p class="text-sm mt-2 text-[#5d3f3d]">ZM rating: <strong class="text-[#291716]">${esc(context.zm_assessment.ratings?.[competency] || "Not rated")}</strong></p>
            <p class="text-sm text-[#926e6c] mt-1">${esc(context.zm_assessment.notes?.[competency] || "No ZM note.")}</p>
            ${suggested ? `<div class="mt-3 p-3 rounded-lg border border-[#d5e3ff] bg-[#f5f8ff]">
              <p class="text-xs font-bold uppercase tracking-wide text-[#1464F4]">Suggested rating</p>
              <p class="text-sm font-bold text-[#291716] mt-1">${esc(suggested)}</p>
              <p class="text-[10px] text-[#926e6c] mt-2">Advisory only — final rating is yours. Notes are optional.</p>
            </div>` : ""}
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
            <label class="block text-xs font-bold uppercase tracking-wide text-[#926e6c] mt-4 mb-1">RD note (optional)</label>
            <textarea data-rd-note="${esc(competency)}" ${locked ? "disabled" : ""} class="w-full border border-[#e7bdb9] rounded-lg p-3 text-sm" placeholder="Optional RD note">${esc(notes[competency] || "")}</textarea>
          </div>
          <div>
            <h3 class="font-bold text-sm text-[#291716]">Supporting Evidence From Previous Feedbacks</h3>
            ${renderEvidencePanel(bundle)}
          </div>
        </div>
      </section>`;
      }).join("")}${careerMoveHtml}</div>
      <div class="mt-6 flex justify-end gap-3">${locked ? '<strong class="text-emerald-700">Final profile submitted and locked</strong>' : `${button("Save Draft", "data-draft", true)}${button("Submit Final Profile", "data-final")}`}</div>`);
    qs("[data-back]").onclick = () => go("rd/dashboard");
    if (locked) return;
    qsa("[data-career-move]").forEach((control) => {
      control.onclick = () => {
        careerRecommendation = control.dataset.careerMove;
        qsa("[data-career-move]").forEach((item) => {
          const active = item.dataset.careerMove === careerRecommendation;
          item.className = `text-left p-3 border rounded-lg transition-colors ${
            active ? "bg-[#df162b] text-white border-[#df162b]" : "border-[#e7bdb9] bg-white hover:border-[#df162b]/50"
          }`;
        });
      };
    });
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
      if (submit && !careerRecommendation) {
        toast("Select a career move recommendation before submission.", "error");
        return;
      }
      qsa("[data-rd-note]").forEach((node) => { notes[node.dataset.rdNote] = node.value; });
      if (submit && !confirm("Submit and lock final RD profile?")) return;
      await api("/api/assessment", {
        method: "POST",
        body: JSON.stringify({
          employee_code: code,
          ratings,
          notes,
          submit,
          career_recommendation: careerRecommendation,
        }),
      });
      if (!submit) {
        toast("Draft saved.");
        return;
      }
      toast("Final profile submitted.");
      const refreshed = await employeeSummaries();
      const next = nextIncompleteEmployee(refreshed, code, "rd");
      if (!next) {
        toast("All eligible validations complete.");
        go("rd/dashboard");
        return;
      }
      const nextModal = document.createElement("div");
      nextModal.className = "fixed inset-0 z-[80] bg-black/40 flex items-center justify-center p-4";
      nextModal.innerHTML = `<div class="bg-white rounded-xl shadow-2xl border border-[#e7bdb9] w-full max-w-md p-6">
        <h2 class="text-lg font-extrabold text-[#291716]">Profile submitted</h2>
        <p class="text-sm text-[#5d3f3d] mt-2">Continue with <strong>${esc(next.name)}</strong> (${esc(next.employee_code)})?</p>
        <div class="mt-5 flex flex-wrap justify-end gap-2">
          <button type="button" data-back-dash class="px-4 py-2 border border-[#e7bdb9] rounded-lg font-bold text-sm text-[#5d3f3d]">Back to dashboard</button>
          <button type="button" data-next-emp class="px-4 py-2 bg-[#df162b] text-white rounded-lg font-bold text-sm">Next employee</button>
        </div>
      </div>`;
      document.body.appendChild(nextModal);
      qs("[data-back-dash]", nextModal).onclick = () => {
        nextModal.remove();
        go("rd/dashboard");
      };
      qs("[data-next-emp]", nextModal).onclick = () => {
        nextModal.remove();
        go("rd/validation", `?employee=${encodeURIComponent(next.employee_code)}`);
      };
    };
    qs("[data-draft]").onclick = () => save(false).catch((error) => toast(error.message, "error"));
    qs("[data-final]").onclick = () => save(true).catch((error) => toast(error.message, "error"));
  }

  const ROLEPLAY_BRIEFS = {
    functional: {
      title: "Consultative Partnership Pitch With Hotel Chain",
      about: "You are a MakeMyTrip Business Development Manager meeting a hotel chain (18 properties) that wants more demand but worries about commission leakage and discount-led business. Diagnose first — do not push a package immediately. Ask for the right data, propose a sharp partnership approach, and build trust.",
      success: [
        "Diagnose the demand problem before pitching product.",
        "Use occupancy, cancellation, and commercial data to guide the ask.",
        "Differentiate weekday corporate vs weekend leisure plans.",
        "Align GM, revenue, and leadership priorities.",
        "Propose a 90-day pilot with owners, metrics, and guardrails.",
      ],
      aiName: "Priya Nair",
      aiRole: "Regional Partnerships Lead",
      aiPersona: "Commercially sharp, collaborative, and time-pressed. Open to MakeMyTrip but skeptical of generic OTA pitches. Challenges vague claims and expects proof without heavy discounts.",
    },
    behavioural: {
      title: "Leading a Cross-Functional Strategic Project",
      about: "You are a MakeMyTrip Business Development Manager leading a high-value enterprise partnership implementation (go-live in 6 weeks; ~INR 3.5 crore signed value). Customer added reporting, SLA, and approval-workflow asks after signing. Product and Engineering are stretched. Align teams without formal authority.",
      success: [
        "Clarify the 6-week objective and success metrics.",
        "Define ownership, decision rights, and escalation.",
        "Show what weekly leadership numbers prove on-track status.",
        "Phase post-signing scope against ~30% Engineering capacity.",
        "Summarise plan, owners, risks, timelines, and next steps.",
      ],
      aiName: "Sarah Patel",
      aiRole: "Senior Product Manager",
      aiPersona: "Collaborative but cautious. Represents Product, Engineering, and Delivery. Pushes back on fuzzy scope, unclear ownership, and unrealistic timelines. Needs confidence before committing capacity.",
    },
  };

  async function initRoleplays() {
    const result = await api("/api/employee/roleplays");
    const sessions = result.sessions || [];
    const total = result.total || 2;
    const completed = result.completed || 0;
    const pct = total ? Math.round((completed / total) * 100) : 0;
    const meName = session.user?.display_name || session.user?.name || "You";
    const meRole = session.user?.designation || session.user?.role_name || "Business Development Manager";
    const meAvatar = loadAvatar(session.user);
    const briefings = ROLEPLAY_BRIEFS;
    const banner = `<div class="bg-white border border-[#e7bdb9] rounded-xl p-6 mb-7 relative overflow-hidden flex flex-col md:flex-row md:items-center justify-between gap-6">
      <div class="absolute top-0 left-0 w-1.5 h-full bg-[#1464F4]"></div>
      <div class="flex flex-col md:flex-row md:items-center gap-6">
        <div><p class="uppercase tracking-widest text-xs font-bold text-[#5d3f3d] mb-1">Completed</p>
          <div class="flex items-baseline gap-2"><span class="text-4xl font-extrabold text-[#df162b] leading-none">${completed}/${total}</span><span class="text-lg font-bold text-[#5d3f3d]">Sessions</span></div>
        </div>
        <div class="hidden md:block h-14 w-px bg-[#e7bdb9]"></div>
        <div>
          <div class="flex items-center gap-2 text-[#1464F4] font-bold">${result.lattice_unlocked
            ? '<span class="material-symbols-outlined" style="font-variation-settings:\'FILL\' 1">verified</span> Career lattice unlocked'
            : '<span class="material-symbols-outlined">lock</span> Career lattice locked'}</div>
          <p class="text-sm text-[#5d3f3d] mt-1">${result.lattice_unlocked
            ? "Both voice roleplay sessions are complete."
            : "Complete both voice roleplay sessions to unlock Career Lattice."}</p>
        </div>
      </div>
      <div class="flex items-center gap-4">
        <div class="hidden sm:block h-2 w-40 bg-[#ffe1df] rounded-full overflow-hidden"><div class="h-full bg-[#1464F4]" style="width:${pct}%"></div></div>
        ${result.lattice_unlocked ? button("View Lattice", "data-career") : ""}
      </div>
    </div>`;
    const cards = sessions.map((row, index) => {
      const done = row.status === "completed";
      const brief = briefings[row.kind] || {};
      const sessionLabel = `Session ${index + 1}`;
      const successList = (brief.success || []).map((item) =>
        `<li class="text-sm text-[#5d3f3d] leading-snug">${esc(item)}</li>`
      ).join("");
      const avatarHtml = meAvatar
        ? `<img src="${meAvatar}" alt="" class="w-10 h-10 rounded-full object-cover border border-[#e7bdb9]">`
        : `<div class="w-10 h-10 rounded-full bg-[#ffe1df] text-[#df162b] grid place-items-center text-sm font-bold">${esc((meName || "Y").split(/\s+/).map((p) => p[0]).slice(0, 2).join("").toUpperCase() || "ME")}</div>`;
      return `<section class="bg-white border border-[#e7bdb9] rounded-xl p-5 flex flex-col shadow-sm" data-voice-card="${esc(row.kind)}">
        <div class="flex justify-between items-start gap-3 mb-3">
          <div class="min-w-0">
            <div class="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-[#5d3f3d] mb-1">
              <span class="material-symbols-outlined text-base text-[#df162b]">apartment</span>
              MakeMyTrip · ${esc(sessionLabel)}
            </div>
            <h2 class="font-bold text-xl text-[#291716] leading-tight">${esc(brief.title || sessionLabel)}</h2>
          </div>
          <span class="shrink-0 px-2.5 py-1 rounded-full text-[10px] font-bold uppercase tracking-wide ${done ? "bg-green-100 text-green-700" : "bg-[#ffe1df] text-[#5d3f3d]"}">${esc(String(row.status || "not_started").replaceAll("_", " "))}</span>
        </div>
        <div class="space-y-4 mb-4">
          <div>
            <h3 class="text-sm font-bold text-[#291716] mb-1">What this conversation is about</h3>
            <p class="text-sm text-[#5d3f3d] leading-relaxed">${esc(brief.about || "")}</p>
          </div>
          <div>
            <h3 class="text-sm font-bold text-[#291716] mb-1">What makes it successful</h3>
            <ul class="list-disc pl-5 space-y-1">${successList}</ul>
          </div>
          <div>
            <h3 class="text-sm font-bold text-[#291716] mb-2">Who the conversation is between</h3>
            <div class="rounded-xl border border-[#e7bdb9] divide-y divide-[#e7bdb9] overflow-hidden">
              <div class="flex items-start gap-3 p-3 bg-[#fffaf9]">
                ${avatarHtml}
                <div class="min-w-0">
                  <div class="flex items-center gap-2 flex-wrap">
                    <p class="font-bold text-[#291716] text-sm">${esc(meName)}</p>
                    <span class="text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded bg-slate-200 text-slate-600">Me</span>
                  </div>
                  <p class="text-xs text-[#5d3f3d] mt-0.5">${esc(meRole)}</p>
                </div>
              </div>
              <div class="flex items-start gap-3 p-3">
                <div class="w-10 h-10 rounded-full bg-[#e8f1ff] text-[#1464F4] grid place-items-center shrink-0">
                  <span class="material-symbols-outlined text-[22px]">auto_awesome</span>
                </div>
                <div class="min-w-0">
                  <p class="font-bold text-[#291716] text-sm">${esc(brief.aiName || "AI counterpart")}</p>
                  <p class="text-xs text-[#5d3f3d] mt-0.5">${esc(brief.aiRole || "")}</p>
                  <p class="text-xs text-[#5d3f3d] mt-2 leading-relaxed">${esc(brief.aiPersona || "")}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
        ${row.error ? `<p class="text-sm text-[#df162b] mb-3">${esc(row.error)}</p>` : ""}
        <p class="text-xs text-[#5d3f3d] mb-3" data-voice-status="${esc(row.kind)}">Ready when you are.</p>
        <div class="mt-auto flex flex-col gap-2">
          ${done ? '<p class="text-sm font-bold text-emerald-700">Session complete</p>' : `
          <button type="button" data-voice-start="${esc(row.kind)}" class="w-full px-3 py-2.5 bg-[#1464F4] text-white rounded-lg font-bold text-sm hover:opacity-90">Start mic session</button>
          <button type="button" data-voice-end="${esc(row.kind)}" disabled class="w-full px-3 py-2.5 border border-[#e7bdb9] text-[#5d3f3d] rounded-lg font-bold text-sm disabled:opacity-40">End</button>`}
        </div>
      </section>`;
    }).join("");
    render(`${pageHeader("Competency Assessments", "Two in-app voice roleplays unlock the career lattice.")}
      ${banner}
      <div class="grid lg:grid-cols-2 gap-5">${cards}</div>`);
    if (qs("[data-career]")) qs("[data-career]").onclick = () => go("employee/career");
    qsa("[data-voice-start]").forEach((btn) => {
      btn.onclick = () => startVoiceRoleplay(btn.dataset.voiceStart).catch((err) => toast(err.message, "error"));
    });
    qsa("[data-voice-end]").forEach((btn) => {
      btn.onclick = () => endVoiceRoleplay(btn.dataset.voiceEnd);
    });
  }

  const voiceRuntime = {
    kind: null,
    ws: null,
    capture: null,
    playCtx: null,
    nextPlay: 0,
    sources: [],
    acceptAudio: false,
    playbackSampleRate: 24000,
    inputSampleRate: 16000,
    stage: null,
    transcriptOpen: false,
  };

  function floatTo16BitPCM(float32) {
    const out = new Int16Array(float32.length);
    for (let i = 0; i < float32.length; i += 1) {
      const s = Math.max(-1, Math.min(1, float32[i]));
      out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return out;
  }

  function downsampleToRate(float32, inputRate, targetRate) {
    const target = Number(targetRate) || 16000;
    if (inputRate === target) return float32;
    const ratio = inputRate / target;
    const newLen = Math.max(1, Math.floor(float32.length / ratio));
    const result = new Float32Array(newLen);
    for (let i = 0; i < newLen; i += 1) {
      const idx = Math.floor(i * ratio);
      result[i] = float32[idx] || 0;
    }
    return result;
  }

  function pcm16ToBase64(pcm) {
    const bytes = new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength);
    let binary = "";
    const chunk = 0x8000;
    for (let i = 0; i < bytes.length; i += chunk) {
      binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
    }
    return btoa(binary);
  }

  function stopBotPlayback() {
    voiceRuntime.acceptAudio = false;
    (voiceRuntime.sources || []).forEach((src) => {
      try { src.stop(0); } catch {}
      try { src.disconnect(); } catch {}
    });
    voiceRuntime.sources = [];
    voiceRuntime.nextPlay = 0;
    if (voiceRuntime.playCtx) {
      try { voiceRuntime.playCtx.close(); } catch {}
      voiceRuntime.playCtx = null;
    }
  }

  function stopMicCapture() {
    const capture = voiceRuntime.capture;
    if (!capture) return;
    try { capture.processor.disconnect(); } catch {}
    try { capture.source.disconnect(); } catch {}
    try { capture.stream.getTracks().forEach((t) => t.stop()); } catch {}
    try { capture.audioCtx.close(); } catch {}
    voiceRuntime.capture = null;
  }

  function playPcm16Base64(b64) {
    if (!voiceRuntime.acceptAudio) return;
    const playRate = Number(voiceRuntime.playbackSampleRate) || 24000;
    if (!voiceRuntime.playCtx) {
      voiceRuntime.playCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: playRate });
      voiceRuntime.nextPlay = 0;
      voiceRuntime.sources = [];
    }
    const ctx = voiceRuntime.playCtx;
    const binary = atob(b64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    const pcm = new Int16Array(bytes.buffer);
    const float32 = new Float32Array(pcm.length);
    for (let i = 0; i < pcm.length; i += 1) float32[i] = pcm[i] / 32768;
    const buffer = ctx.createBuffer(1, float32.length, playRate);
    buffer.copyToChannel(float32, 0);
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(ctx.destination);
    const startAt = Math.max(ctx.currentTime, voiceRuntime.nextPlay);
    src.start(startAt);
    voiceRuntime.nextPlay = startAt + buffer.duration;
    voiceRuntime.sources.push(src);
    src.onended = () => {
      voiceRuntime.sources = (voiceRuntime.sources || []).filter((item) => item !== src);
    };
  }

  function setVoiceStatus(kind, text) {
    const node = qs(`[data-voice-status="${CSS.escape(kind)}"]`);
    if (node && text) node.textContent = text;
    // Never show status on the live stage header.
    const stageStatus = qs("[data-voice-stage-status]");
    if (stageStatus) stageStatus.textContent = "";
  }

  function setVoiceSpeaking(who) {
    const stage = voiceRuntime.stage;
    if (!stage) return;
    const youBar = qs("[data-voice-you-bar]", stage);
    const aiBar = qs("[data-voice-ai-bar]", stage);
    const aiDots = qs("[data-voice-ai-dots]", stage);
    if (youBar) youBar.classList.toggle("opacity-100", who === "user");
    if (youBar) youBar.classList.toggle("opacity-0", who !== "user");
    if (aiBar) aiBar.classList.toggle("opacity-100", who === "assistant");
    if (aiBar) aiBar.classList.toggle("opacity-0", who !== "assistant");
    if (aiDots) aiDots.classList.toggle("animate-pulse", who === "assistant");
  }

  function openVoiceStage(kind) {
    closeVoiceStage();
    const brief = ROLEPLAY_BRIEFS[kind] || {};
    const meName = session.user?.display_name || session.user?.name || "You";
    const meRole = session.user?.designation || session.user?.role_name || "Business Development Manager";
    const meAvatar = loadAvatar(session.user);
    const avatarHtml = meAvatar
      ? `<img src="${meAvatar}" alt="" class="w-20 h-20 md:w-24 md:h-24 rounded-full object-cover border-2 border-white shadow-md">`
      : `<div class="w-20 h-20 md:w-24 md:h-24 rounded-full bg-[#ffe1df] text-[#df162b] grid place-items-center text-2xl font-bold shadow-md">${esc((meName || "Y").split(/\s+/).map((p) => p[0]).slice(0, 2).join("").toUpperCase() || "ME")}</div>`;
    const stage = document.createElement("div");
    stage.id = "voice-roleplay-stage";
    stage.className = "fixed inset-0 z-[100] bg-[#f4f6f8] flex flex-col";
    stage.innerHTML = `
      <header class="shrink-0 px-4 md:px-8 py-4 border-b border-[#e7bdb9] bg-white">
        <div class="min-w-0">
          <p class="text-[11px] font-bold uppercase tracking-wider text-[#5d3f3d]">Live roleplay</p>
          <h1 class="text-lg md:text-xl font-extrabold text-[#291716] truncate">${esc(brief.title || "Voice assessment")}</h1>
        </div>
        <p class="hidden sm:block text-sm text-[#5d3f3d] mt-1" data-voice-stage-status></p>
      </header>
      <div class="flex-1 min-h-0 grid lg:grid-cols-[minmax(0,1.1fr)_minmax(280px,0.9fr)]">
        <section class="flex items-center justify-center p-6 md:p-10">
          <div class="w-full max-w-3xl bg-white rounded-2xl border border-[#e7bdb9] shadow-xl px-6 py-10 md:px-10 md:py-12">
            <div class="grid grid-cols-2 gap-6 md:gap-10 items-start">
              <div class="flex flex-col items-center text-center">
                ${avatarHtml}
                <p class="mt-4 font-extrabold text-[#291716] text-lg">You</p>
                <p class="text-sm text-[#5d3f3d] mt-1">${esc(meRole)}</p>
                <div data-voice-you-bar class="mt-3 h-1.5 w-16 rounded-full bg-[#1464F4] opacity-0 transition-opacity"></div>
              </div>
              <div class="flex flex-col items-center text-center">
                <div data-voice-ai-dots class="w-20 h-20 md:w-24 md:h-24 rounded-full bg-[#e8f1ff] text-[#1464F4] grid place-items-center shadow-md">
                  <span class="flex gap-1.5">
                    <span class="w-2.5 h-2.5 rounded-full bg-[#1464F4]"></span>
                    <span class="w-2.5 h-2.5 rounded-full bg-[#1464F4]"></span>
                    <span class="w-2.5 h-2.5 rounded-full bg-[#1464F4]"></span>
                  </span>
                </div>
                <p class="mt-4 font-extrabold text-[#291716] text-lg">${esc(brief.aiName || "AI counterpart")}</p>
                <p class="text-sm text-[#5d3f3d] mt-1">${esc(brief.aiRole || "")}</p>
                <div data-voice-ai-bar class="mt-3 h-1.5 w-16 rounded-full bg-[#1464F4] opacity-0 transition-opacity"></div>
              </div>
            </div>
            <p class="text-center text-xs text-[#926e6c] mt-8 max-w-xl mx-auto leading-relaxed">${esc(brief.aiPersona || "")}</p>
          </div>
        </section>
        <aside class="border-t lg:border-t-0 lg:border-l border-[#e7bdb9] bg-white flex flex-col min-h-0">
          <div class="px-4 py-3 border-b border-[#e7bdb9]">
            <h2 class="text-sm font-bold text-[#291716]">Live transcript</h2>
            <p class="text-xs text-[#5d3f3d] mt-0.5">What ${esc(brief.aiName || "the assessor")} is saying</p>
          </div>
          <div data-voice-transcript class="flex-1 overflow-y-auto p-4 space-y-3 text-sm text-[#291716] leading-relaxed">
            <p class="text-[#926e6c] italic" data-voice-transcript-empty>Transcript appears here as the voicebot speaks…</p>
          </div>
        </aside>
      </div>
      <footer class="shrink-0 px-4 md:px-8 py-4 border-t border-[#e7bdb9] bg-white flex justify-center">
        <button type="button" data-voice-stage-end class="w-full max-w-sm px-4 py-3 bg-[#df162b] text-white rounded-lg font-bold text-sm hover:opacity-90">End</button>
      </footer>`;
    document.body.appendChild(stage);
    document.body.style.overflow = "hidden";
    voiceRuntime.stage = stage;
    voiceRuntime.transcriptOpen = false;
    qs("[data-voice-stage-end]", stage).onclick = () => endVoiceRoleplay(kind);
  }

  function closeVoiceStage() {
    if (voiceRuntime.stage) {
      voiceRuntime.stage.remove();
      voiceRuntime.stage = null;
    }
    voiceRuntime.transcriptOpen = false;
    document.body.style.overflow = "";
  }

  function appendVoiceTranscript(delta) {
    const stage = voiceRuntime.stage;
    if (!stage || !delta) return;
    const box = qs("[data-voice-transcript]", stage);
    if (!box) return;
    const empty = qs("[data-voice-transcript-empty]", stage);
    if (empty) empty.remove();
    let current = qs("[data-voice-transcript-current]", stage);
    if (!current) {
      current = document.createElement("p");
      current.setAttribute("data-voice-transcript-current", "");
      current.className = "whitespace-pre-wrap";
      box.appendChild(current);
    }
    current.textContent = `${current.textContent || ""}${delta}`;
    box.scrollTop = box.scrollHeight;
    voiceRuntime.transcriptOpen = true;
  }

  function finalizeVoiceTranscriptTurn() {
    const stage = voiceRuntime.stage;
    if (!stage) return;
    const current = qs("[data-voice-transcript-current]", stage);
    if (!current || !String(current.textContent || "").trim()) return;
    current.removeAttribute("data-voice-transcript-current");
    current.classList.add("text-[#5d3f3d]");
  }

  function openVoicePrepModal() {
    return new Promise((resolve) => {
      closeOverlay("mc-voice-prep-modal");
      const node = document.createElement("div");
      node.id = "mc-voice-prep-modal";
      node.className = "fixed inset-0 z-[80] bg-black/40 grid place-items-center p-4";
      node.innerHTML = `<div class="bg-white rounded-xl shadow-2xl w-full max-w-md border border-[#e7bdb9] overflow-hidden" role="dialog" aria-modal="true" aria-labelledby="mc-voice-prep-title">
        <div class="px-5 py-4 border-b border-[#e7bdb9] flex items-center justify-between">
          <h2 id="mc-voice-prep-title" class="text-lg font-extrabold text-[#291716]">Before you start</h2>
          <button type="button" data-voice-prep-cancel class="text-[#5d3f3d] hover:text-[#df162b]"><span class="material-symbols-outlined">close</span></button>
        </div>
        <div class="p-5 text-sm text-[#291716] space-y-3 leading-relaxed">
          <p>Please be in an environment with <strong>no background noise</strong> so the mic session can hear you clearly.</p>
          <p>When the session is over, click the <strong>End</strong> button to end the conversation.</p>
        </div>
        <div class="px-5 py-4 border-t border-[#e7bdb9] flex gap-3 justify-end">
          <button type="button" data-voice-prep-cancel class="px-4 py-2.5 rounded-lg font-bold text-sm border border-[#e7bdb9] text-[#5d3f3d]">Cancel</button>
          <button type="button" data-voice-prep-ok class="px-4 py-2.5 rounded-lg font-bold text-sm bg-[#df162b] text-white">Got it — Start</button>
        </div>
      </div>`;
      document.body.appendChild(node);
      const finish = (ok) => {
        closeOverlay("mc-voice-prep-modal");
        resolve(ok);
      };
      node.addEventListener("click", (event) => { if (event.target === node) finish(false); });
      qsa("[data-voice-prep-cancel]", node).forEach((btn) => { btn.onclick = () => finish(false); });
      qs("[data-voice-prep-ok]", node).onclick = () => finish(true);
    });
  }

  async function startVoiceRoleplay(kind) {
    if (voiceRuntime.ws) {
      toast("End the current session first.", "error");
      return;
    }
    const ready = await openVoicePrepModal();
    if (!ready) return;
    openVoiceStage(kind);
    setVoiceStatus(kind, "");
    let started;
    try {
      started = await api("/api/employee/voice-roleplay/start", {
        method: "POST",
        body: JSON.stringify({ kind }),
      });
    } catch (error) {
      closeVoiceStage();
      throw error;
    }
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${proto}//${location.host}${started.ws_path}&token=${encodeURIComponent(session.token)}`;
    const ws = new WebSocket(wsUrl);
    voiceRuntime.kind = kind;
    voiceRuntime.ws = ws;
    voiceRuntime.acceptAudio = true;
    voiceRuntime.playbackSampleRate = Number(started.playback_sample_rate) || 24000;
    voiceRuntime.inputSampleRate = Number(started.input_sample_rate) || 16000;
    const startBtn = qs(`[data-voice-start="${CSS.escape(kind)}"]`);
    const endBtn = qs(`[data-voice-end="${CSS.escape(kind)}"]`);
    if (startBtn) startBtn.disabled = true;
    if (endBtn) endBtn.disabled = false;

    ws.onmessage = (event) => {
      let msg;
      try { msg = JSON.parse(event.data); } catch { return; }
      if (msg.type === "ready") setVoiceStatus(kind, "");
      else if (msg.type === "audio" && msg.data) playPcm16Base64(msg.data);
      else if (msg.type === "transcript" && msg.delta) {
        setVoiceSpeaking("assistant");
        appendVoiceTranscript(msg.delta);
      } else if (msg.type === "transcript_done") {
        finalizeVoiceTranscriptTurn();
      } else if (msg.type === "speech") {
        setVoiceSpeaking(msg.who || "idle");
      } else if (msg.type === "status") {
        // Do not show timing / continue / voice status to the employee.
      } else if (msg.type === "complete") {
        toast("Roleplay session complete.");
        cleanupVoiceRuntime();
        initRoleplays().catch((err) => toast(err.message, "error"));
      } else if (msg.type === "incomplete") {
        toast(msg.message || "Session ended early — not saved. Start again when ready.");
        cleanupVoiceRuntime();
        initRoleplays().catch((err) => toast(err.message, "error"));
      } else if (msg.type === "error") {
        toast(msg.message || "Voice session error", "error");
        setVoiceStatus(kind, "");
        cleanupVoiceRuntime();
        initRoleplays().catch(() => {});
      }
    };
    ws.onerror = () => {
      toast("Voice WebSocket failed.", "error");
      cleanupVoiceRuntime();
    };
    ws.onclose = () => {
      if (voiceRuntime.ws === ws) cleanupVoiceRuntime();
    };

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioCtx.createMediaStreamSource(stream);
      const processor = audioCtx.createScriptProcessor(4096, 1, 1);
      const inputTargetRate = Number(voiceRuntime.inputSampleRate) || 16000;
      processor.onaudioprocess = (e) => {
        if (!voiceRuntime.ws || voiceRuntime.ws.readyState !== WebSocket.OPEN) return;
        if (!voiceRuntime.acceptAudio) return;
        const input = e.inputBuffer.getChannelData(0);
        const down = downsampleToRate(input, audioCtx.sampleRate, inputTargetRate);
        const pcm = floatTo16BitPCM(down);
        voiceRuntime.ws.send(JSON.stringify({ type: "audio", data: pcm16ToBase64(pcm) }));
      };
      source.connect(processor);
      const mute = audioCtx.createGain();
      mute.gain.value = 0;
      processor.connect(mute);
      mute.connect(audioCtx.destination);
      voiceRuntime.capture = { stream, audioCtx, source, processor };
      setVoiceStatus(kind, "Mic live — waiting for assessor…");
    } catch (error) {
      cleanupVoiceRuntime();
      throw error;
    }
  }

  function endVoiceRoleplay(kind) {
    if (!voiceRuntime.ws || voiceRuntime.kind !== kind) return;
    setVoiceStatus(kind, "");
    setVoiceSpeaking("idle");
    stopMicCapture();
    stopBotPlayback();
    try {
      voiceRuntime.ws.send(JSON.stringify({ type: "end" }));
    } catch {
      cleanupVoiceRuntime();
    }
    const endBtn = qs(`[data-voice-end="${CSS.escape(kind)}"]`);
    if (endBtn) endBtn.disabled = true;
    const stageEnd = qs("[data-voice-stage-end]");
    if (stageEnd) stageEnd.disabled = true;
  }

  function cleanupVoiceRuntime() {
    stopMicCapture();
    stopBotPlayback();
    if (voiceRuntime.ws && voiceRuntime.ws.readyState <= 1) {
      try { voiceRuntime.ws.close(); } catch {}
    }
    voiceRuntime.ws = null;
    voiceRuntime.kind = null;
    voiceRuntime.acceptAudio = false;
    closeVoiceStage();
  }

  async function initCareer() {
    const state = await api("/api/employee/career");
    if (!state.unlocked) {
      render(`${pageHeader("Career Lattice", "Available paths derive from your current role, grade, and completed assessments.")}
        <div class="bg-white border border-[#e7bdb9] rounded-xl p-8 text-center">
          <h2 class="text-xl font-bold text-[#291716]">Career lattice locked</h2>
          <p class="text-[#5d3f3d] mt-2">Complete both voice roleplay sessions first.</p>
          <div class="mt-5">${button("Open Assessments", "data-roleplays")}</div>
        </div>`);
      qs("[data-roleplays]").onclick = () => go("employee/roleplays");
      return;
    }

    const journey = state.journey || [];
    const skillSummary = state.skill_summary || {};
    const idealMet = Boolean(skillSummary.ideal_met);
    const choiceId = state.choice?.aspiration_role || "";
    const byId = Object.fromEntries(journey.map((node) => [node.id, node]));
    const isKamCurrent = state.current === "KAM";
    const currentNode = byId.current || journey[0];

    // Always show full lattice: BD → KAM/ZM/BDFE/Category, KAM → ZM → RD.
    const bdNode = isKamCurrent
      ? {
          id: "bd",
          label: "Business Development",
          short_label: "BD",
          enabled: false,
          state: "prior",
          selectable: false,
        }
      : currentNode;
    const kamNode = isKamCurrent
      ? currentNode
      : (byId.kam || {
          id: "kam",
          label: "Key Account Manager",
          short_label: "KAM",
          enabled: false,
          state: "locked_future",
          selectable: false,
        });
    const bdfeNode = byId.bdfe || {
      id: "bdfe",
      label: "Business Development Fieldforce Effectiveness",
      short_label: "BDFE",
      enabled: false,
      state: "locked_future",
      selectable: false,
    };
    const categoryNode = byId.category || {
      id: "category",
      label: "Category",
      short_label: "Category",
      enabled: false,
      state: "locked_future",
      selectable: false,
    };

    const trackCode = (node) => {
      if (!node) return "—";
      if (node.id === "current") {
        const raw = String(node.short_label || node.label || state.current || "");
        return raw.replace(/\s*RL[\d][\w\-–]*/gi, "").replace(/\s+/g, " ").trim() || (isKamCurrent ? "KAM" : "BD");
      }
      if (node.id === "bdfe") return "BDFE";
      if (node.id === "category") return "Category";
      if (node.id === "bd") return "BD";
      return String(node.short_label || node.id || "").toUpperCase();
    };

    const fullTitle = (node) => {
      if (!node) return "";
      if (node.id === "current") {
        if (isKamCurrent) return "Key Account Manager";
        return "Business Development";
      }
      if (node.id === "bd") return "Business Development";
      if (node.id === "bdfe") return "Business Development Fieldforce Effectiveness";
      if (node.id === "category") return "Category";
      return node.label || "";
    };

    const nodeStatus = (node) => {
      if (!node) return "missing";
      if (node.state === "current") return "current";
      if (node.state === "prior") return "prior";
      if (choiceId && node.id === choiceId) return "selected";
      if (node.enabled) return "eligible";
      return "locked";
    };

    const resolveNode = (id) => {
      if (id === "bd") return bdNode;
      if (id === "kam") return kamNode;
      if (id === "current") return currentNode;
      return byId[id];
    };

    // Lit edges only on the route from current seat → aspiration/eligible targets.
    // Never light BD→ZM when seat is KAM (that spine is a BD-only hop).
    const currentSeat = isKamCurrent ? "kam" : "bd";
    const routeEdgesFor = (targetId) => {
      const routes = {
        kam: currentSeat === "bd" ? [["bd", "kam"]] : [],
        zm: currentSeat === "bd" ? [["bd", "zm"]] : currentSeat === "kam" ? [["kam", "zm"]] : [],
        rd: currentSeat === "bd"
          ? [["bd", "zm"], ["zm", "rd"]]
          : currentSeat === "kam"
            ? [["kam", "zm"], ["zm", "rd"]]
            : [["zm", "rd"]],
        bdfe: currentSeat === "bd" ? [["bd", "bdfe"]] : [],
        category: currentSeat === "bd" ? [["bd", "category"]] : [],
      };
      return routes[targetId] || [];
    };
    const greenEdges = (() => {
      if (!choiceId) return new Set();
      return new Set(routeEdgesFor(choiceId).map(([from, to]) => `${from}|${to}`));
    })();
    const blueEdges = (() => {
      if (choiceId) return new Set();
      const edges = new Set();
      for (const node of journey) {
        if (!node?.enabled || node.id === "current") continue;
        for (const [from, to] of routeEdgesFor(node.id)) {
          edges.add(`${from}|${to}`);
        }
      }
      return edges;
    })();

    const pathStroke = (fromId, toId) => {
      const key = `${fromId}|${toId}`;
      if (greenEdges.has(key)) {
        return { base: "#16a34a", glow: "#16a34a", lit: true };
      }
      if (blueEdges.has(key)) {
        return { base: "#1464F4", glow: "#1464F4", lit: true };
      }
      return { base: "#c5c5c5", glow: "transparent", lit: false };
    };

    const pipe = (d, style) => {
      const { base, glow, lit } = style;
      return `${lit ? `<path d="${d}" fill="none" stroke="${glow}" stroke-width="22" stroke-linecap="round" opacity="0.22"/>` : ""}
        <path d="${d}" fill="none" stroke="#e8e8e8" stroke-width="18" stroke-linecap="round"/>
        <path d="${d}" fill="none" stroke="${base}" stroke-width="8" stroke-linecap="round" opacity="${lit ? 0.95 : 0.55}"/>
        ${lit ? `<path d="${d}" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-dasharray="6 10" opacity="0.7"/>` : ""}`;
    };

    // viewBox 1200×640 — KAM nests in BD fork (above blue spine).
    // Grey paths approach BDFE/Category from the left so tips point into the cards.
    const bdKam = pathStroke("bd", "kam");
    const bdZm = pathStroke("bd", "zm");
    const kamZm = pathStroke("kam", "zm");
    const zmRd = pathStroke("zm", "rd");
    const bdBdfe = pathStroke("bd", "bdfe");
    const bdCat = pathStroke("bd", "category");
    // Centers: BD(144,282) KAM(456,154) ZM(720,282) RD(1056,282) BDFE(288,422) Cat(288,550)
    const pathsHtml = [
      // BD → KAM: into KAM left (card sits in fork between this and blue spine)
      pipe("M 222 255 C 300 230 340 170 378 160", bdKam),
      // BD → ZM: spine under KAM
      pipe("M 222 282 C 420 282 560 282 642 282", bdZm),
      // KAM → ZM: from KAM right into ZM upper-left
      pipe("M 534 160 C 600 160 620 240 642 258", kamZm),
      // ZM → RD
      pipe("M 798 282 C 880 282 940 282 978 282", zmRd),
      // BD → BDFE / Category: same curve as BD→KAM, flipped across y=282 (Category = deeper scale)
      pipe("M 222 309 C 300 334 340 394 378 404", bdBdfe),
      pipe("M 222 320 C 300 370 340 490 378 510", bdCat),
    ].join("");

    const cardHtml = (node, slot) => {
      if (!node) return "";
      const st = nodeStatus(node);
      const code = trackCode(node);
      const title = fullTitle(node);
      const clickable = st === "eligible" && node.selectable && !state.choice;
      const slots = {
        bd: "left:12%; top:44%; transform:translate(-50%,-50%)",
        kam: "left:38%; top:24%; transform:translate(-50%,-50%)",
        zm: "left:60%; top:44%; transform:translate(-50%,-50%)",
        rd: "left:88%; top:44%; transform:translate(-50%,-50%)",
        bdfe: "left:38%; top:63%; transform:translate(-50%,-50%)",
        category: "left:38%; top:80%; transform:translate(-50%,-50%)",
      };

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
        statusBlock = `<p class="text-xs font-bold text-[#16a34a] mt-2 uppercase tracking-wide">Career path</p>`;
      } else if (st === "eligible") {
        shell += " border-[#1464F4]";
        glow = "box-shadow:0 0 0 4px rgba(20,100,244,.10), 0 0 28px rgba(20,100,244,.22);";
        statusBlock = `<p class="text-xs font-bold text-[#1464F4] mt-2 uppercase tracking-wide">Career path</p>`;
      } else if (st === "prior") {
        shell += " border-[#c9c9c9] opacity-80";
        statusBlock = `<p class="text-[11px] font-bold text-[#5d3f3d] mt-1.5 uppercase tracking-wide">Prior role</p>`;
      } else {
        shell += " border-[#c9c9c9] opacity-90";
        statusBlock = "";
      }

      const pin = st === "current"
        ? `<div class="absolute -left-7 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full bg-[#df162b] grid place-items-center shadow-md shadow-[#df162b]/35">
            <span class="material-symbols-outlined text-white text-[14px]" style="font-variation-settings:'FILL' 1">location_on</span>
          </div>`
        : "";
      const lockOverlay = "";
      const corner = st === "current"
        ? `<span class="absolute top-1.5 right-1.5 w-2.5 h-2.5 rounded-full border-2 border-[#df162b]"></span>`
        : "";

      const pathId = node.id === "current"
        ? (isKamCurrent ? "kam" : "bd")
        : node.id;

      const sideTooltip = (slot === "bdfe" || slot === "category")
        ? (idealMet
          ? "This career aspiration is currently locked. Please reach out to your HRBP to know more about this."
          : "This career aspiration is currently locked. Continue developing your current skills and competencies to unlock this opportunity.")
        : "";

      return `<div class="absolute z-20" style="${slots[slot] || slots.bd}">
        <button type="button" data-path="${esc(pathId)}" data-label="${esc(node.label || title)}"
          ${clickable ? "" : "disabled"}
          ${sideTooltip ? `title="${esc(sideTooltip)}"` : ""}
          class="${shell} relative w-[132px] sm:w-[148px] rounded-xl p-3 text-left transition-transform ${clickable ? "cursor-pointer hover:scale-[1.03]" : "cursor-default"}"
          style="${glow}">
          ${pin}${corner}${lockOverlay}
          <p class="text-xl sm:text-2xl font-extrabold tracking-tight leading-none ${st === "locked" || st === "prior" ? "text-[#9ca3af]" : "text-[#291716]"}">${esc(code)}</p>
          <p class="text-[11px] text-[#5d3f3d] mt-1 leading-snug">${esc(title)}</p>
          ${statusBlock}
        </button>
      </div>`;
    };

    const cards = [
      cardHtml(bdNode, "bd"),
      cardHtml(kamNode, "kam"),
      cardHtml(byId.zm, "zm"),
      cardHtml(byId.rd, "rd"),
      cardHtml(bdfeNode, "bdfe"),
      cardHtml(categoryNode, "category"),
    ].join("");

    render(`<style>
      .lattice-stage{
        position:relative;width:100%;min-height:0;aspect-ratio:1200/640;border-radius:1rem;overflow:hidden;
        padding:1.25rem 1.5rem 2rem;box-sizing:border-box;
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
        <h1 class="text-xl md:text-2xl font-extrabold text-[#291716]">My Career Lattice</h1>
      </div>
      <div class="text-sm font-bold text-[#df162b] bg-[#fff0ef] border border-[#e7bdb9] rounded-lg px-4 py-2">
        ${esc(trackCode(currentNode))}
        ${isKamCurrent || /kam/i.test(String(state.current_label || ""))
          ? ` · ${esc(state.designation || "Key Account Manager")}`
          : (state.designation ? ` · ${esc(state.designation)}` : "")}
      </div>
    </section>
    <div class="space-y-6">
      ${skillSummary.has_profile
        ? (idealMet
          ? `<div class="bg-white border border-[#e7bdb9] rounded-xl p-5 shadow-sm">
        <p class="text-base font-bold text-[#291716]">You're doing great in your current role.</p>
        <p class="text-sm text-[#5d3f3d] mt-2">Explore the skills towards your aspiration role.</p>
      </div>`
          : `<div class="bg-white border border-[#e7bdb9] rounded-xl p-5 shadow-sm grid md:grid-cols-2 gap-6">
        <div>
          <h3 class="font-bold text-[#291716] mb-2">You're doing great in the below mentioned skills:</h3>
          ${(skillSummary.good_at || []).length
            ? `<ul class="space-y-1.5">${(skillSummary.good_at || []).map((skill) => `<li class="text-sm text-[#291716] flex items-start gap-2"><span class="material-symbols-outlined text-[#16a34a] text-[18px]">check_circle</span>${esc(skill)}</li>`).join("")}</ul>`
            : `<p class="text-sm text-[#5d3f3d]">No strengths mapped yet against your role ideal.</p>`}
        </div>
        <div>
          <h3 class="font-bold text-[#291716] mb-2">You need to hone your skills in the following areas:</h3>
          ${(skillSummary.improve || []).length
            ? `<ul class="space-y-1.5">${(skillSummary.improve || []).map((skill) => `<li class="text-sm text-[#291716] flex items-start gap-2"><span class="material-symbols-outlined text-[#df162b] text-[18px]">trending_up</span>${esc(skill)}</li>`).join("")}</ul>`
            : `<p class="text-sm text-[#5d3f3d]">No focus areas listed.</p>`}
        </div>
      </div>`)
        : `<div class="bg-white border border-[#e7bdb9] rounded-xl p-5 shadow-sm">
        <p class="text-sm text-[#5d3f3d]">Skill strengths and focus areas appear here after your RD final profile is submitted.</p>
      </div>`}
      <div>
        <div class="lattice-stage border border-[#e0e0e0] shadow-sm">
          <svg class="absolute inset-0 w-full h-full" viewBox="0 0 1200 640" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
            ${pathsHtml}
          </svg>
          ${cards}
        </div>
        <div class="flex flex-wrap gap-5 pt-4 mt-3">
          <div class="flex items-center gap-2"><div class="w-4 h-4 rounded-full bg-[#df162b] border-2 border-white shadow-sm"></div><span class="text-xs font-semibold text-[#291716]">You are here</span></div>
          <div class="flex items-center gap-2"><div class="w-4 h-4 rounded-full bg-[#1464F4] border-2 border-white shadow-sm"></div><span class="text-xs font-semibold text-[#291716]">Career path</span></div>
          <div class="flex items-center gap-2"><div class="w-4 h-4 rounded-full bg-[#16a34a] border-2 border-white shadow-sm"></div><span class="text-xs font-semibold text-[#291716]">Selected aspiration</span></div>
          <div class="flex items-center gap-2"><div class="w-4 h-4 rounded-full bg-[#c9c9c9] border-2 border-white shadow-sm"></div><span class="text-xs font-semibold text-[#5d3f3d]">Future aspiration</span></div>
          ${state.choice
            ? `<p class="ml-auto text-xs font-bold text-[#16a34a]">Aspiration Selected</p>`
            : `<p class="ml-auto text-xs font-semibold text-[#5d3f3d]">Tap an eligible role to lock aspiration</p>`}
        </div>
      </div>
    </div>`);

    qsa("[data-path]").forEach((control) => {
      if (control.disabled) return;
      control.onclick = async () => {
        if (!confirm(`Lock aspiration: ${control.dataset.label}? Only Admin can reset it.`)) return;
        try {
          await api("/api/employee/career", { method: "POST", body: JSON.stringify({ aspiration_role: control.dataset.path }) });
          toast("Aspiration Selected.");
          go("employee/courses");
        } catch (error) {
          toast(error.message, "error");
        }
      };
    });
  }

  let basket = new Map();
  let curatedOtherSources = {};
  /** Persists across admin employee table reloads (reset actions, etc.). */
  const adminEmployeesView = {
    sortMode: "code-asc",
    filterStatus: "all",
    searchRaw: "",
    selectedCode: "",
  };

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
    const [career, roleplays] = await Promise.all([
      api("/api/employee/career"),
      api("/api/employee/roleplays"),
    ]);
    const latticeUnlocked = Boolean(roleplays.lattice_unlocked);
    const aspirationLocked = Boolean(career.choice);
    if (!latticeUnlocked || !aspirationLocked) {
      const needAssessments = !latticeUnlocked;
      render(`${pageHeader("Select Your Courses", "Complete earlier steps before shopping courses.")}
        <div class="bg-white border border-[#e7bdb9] rounded-xl p-8 max-w-2xl">
          <div class="flex items-start gap-4">
            <span class="material-symbols-outlined text-[#df162b] text-4xl" style="font-variation-settings:'FILL' 1">lock</span>
            <div>
              <h2 class="text-xl font-bold text-[#291716]">Courses locked</h2>
              <p class="text-sm text-[#5d3f3d] mt-2">${needAssessments
                ? "Finish both voice roleplay assessments, unlock Career Lattice, then lock an aspiration."
                : "Choose and lock a career aspiration on the Career Lattice first."}</p>
              <div class="mt-5 flex flex-wrap gap-2">
                ${needAssessments
                  ? button("Open Assessments", "data-open-prior")
                  : button("Open Career Lattice", "data-open-prior")}
              </div>
            </div>
          </div>
        </div>`);
      qs("[data-open-prior]")?.addEventListener("click", () => {
        go(needAssessments ? "employee/roleplays" : "employee/career");
      });
      return;
    }

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
          <h1 class="text-2xl md:text-3xl font-extrabold text-[#df162b]">Select Your Courses</h1>
          <p class="text-[#5d3f3d] mt-1">Your learning journey is already selected. Course selection can no longer be changed.</p>
        </div>
        <div class="bg-white border border-[#e7bdb9] rounded-xl p-8 max-w-2xl">
          <div class="flex items-start gap-4">
            <span class="material-symbols-outlined text-[#df162b] text-4xl" style="font-variation-settings:'FILL' 1">lock</span>
            <div>
              <h2 class="text-xl font-bold text-[#291716]">Journey Already Selected</h2>
              <p class="text-sm text-[#5d3f3d] mt-2">${linkedInCount} LinkedIn course${linkedInCount === 1 ? "" : "s"}${otherCount ? ` · ${otherCount} other source${otherCount === 1 ? "" : "s"}` : ""} locked in your learning journey.</p>
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
      render(`${pageHeader("Select Your Courses", "AI-Powered Learning Recommendations based on your skill gaps.")}
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
          <h1 class="text-2xl md:text-3xl font-extrabold text-[#df162b]">Select Your Courses</h1>
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
                ? "You're thriving in your current role. Now, explore the journey towards your aspiration role. Please add at least <strong>1 LinkedIn course per skill</strong>. Other sources are optional."
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
          ? `Journey Already Selected with ${courseIds.length} LinkedIn + ${otherSources.length} other source(s).`
          : "Journey Already Selected. LinkedIn courses saved.");
        go("employee/learning");
      } catch (error) {
        toast(error.message, "error");
      }
    };
  }

  function mentorcloudUrl(payload) {
    return String(payload?.mentorcloud_url || "https://makemytrip.mentorcloud.com/").trim();
  }

  function mentorTileHtml(payload) {
    const url = mentorcloudUrl(payload);
    return `<section id="mc-mentor-tile" class="mb-8 scroll-mt-24">
      <div class="bg-white rounded-xl border border-[#e7bdb9] p-6 flex flex-col md:flex-row md:items-center gap-5">
        <div class="w-12 h-12 rounded-full bg-[#fff0ef] text-[#df162b] flex items-center justify-center shrink-0">
          <span class="material-symbols-outlined text-[28px]" style="font-variation-settings:'FILL' 1">handshake</span>
        </div>
        <div class="flex-1 min-w-0">
          <h3 class="text-lg font-bold text-[#291716]">Connect with your mentor</h3>
          <p class="text-sm text-[#5d3f3d] mt-1">Get coaching support as you progress through your courses. Open MyMentorCloud to schedule and continue the conversation.</p>
        </div>
        <a href="${esc(url)}" target="_blank" rel="noopener" class="inline-flex items-center justify-center gap-2 px-5 py-2.5 bg-[#df162b] text-white rounded-lg font-bold text-sm hover:opacity-90 shrink-0">
          <span class="material-symbols-outlined text-[18px]">open_in_new</span>
          Open MyMentorCloud
        </a>
      </div>
    </section>`;
  }

  function wireMentorControls(payload) {
    qs("[data-connect-mentor]")?.addEventListener("click", () => {
      const tile = document.getElementById("mc-mentor-tile");
      if (tile) tile.scrollIntoView({ behavior: "smooth", block: "start" });
      else window.open(mentorcloudUrl(payload), "_blank", "noopener");
    });
  }

  async function initLearning() {
    let result;
    try {
      result = await api("/api/employee/learning");
    } catch (error) {
      const mentorPayload = { mentorcloud_url: "https://makemytrip.mentorcloud.com/" };
      const [career, roleplays] = await Promise.all([
        api("/api/employee/career").catch(() => ({ choice: null })),
        api("/api/employee/roleplays").catch(() => ({ lattice_unlocked: false })),
      ]);
      const latticeUnlocked = Boolean(roleplays.lattice_unlocked);
      const aspirationLocked = Boolean(career.choice);
      const needAssessments = !latticeUnlocked;
      const needAspiration = latticeUnlocked && !aspirationLocked;
      render(`<div class="mb-6 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
          <div>
            <h1 class="text-2xl md:text-3xl font-extrabold text-[#df162b]">Your Learning Journey</h1>
            <p class="text-[#5d3f3d] mt-1">Track your progress across your identified gaps and unlock your full potential.</p>
          </div>
          <button type="button" data-connect-mentor class="inline-flex items-center justify-center gap-2 px-4 py-2.5 border border-[#df162b] text-[#df162b] rounded-lg font-bold text-sm hover:bg-[#df162b]/5 shrink-0">
            <span class="material-symbols-outlined text-[18px]">handshake</span>
            Connect with your mentor
          </button>
        </div>
        ${mentorTileHtml(mentorPayload)}
        <div class="bg-white border border-[#e7bdb9] rounded-xl p-8 text-center max-w-2xl mx-auto">
          <span class="material-symbols-outlined text-5xl text-[#e7bdb9]">${needAssessments || needAspiration ? "lock" : "menu_book"}</span>
          <h2 class="text-xl font-bold text-[#291716] mt-3">${needAssessments || needAspiration ? "Learning journey locked" : "No courses locked yet"}</h2>
          <p class="text-sm text-[#5d3f3d] mt-2">${needAssessments
            ? "Complete both voice roleplays, unlock Career Lattice, and lock an aspiration first."
            : needAspiration
              ? "Lock a career aspiration on the Career Lattice before selecting courses."
              : (error?.message || "Shop recommended courses and checkout to lock your learning journey.")}</p>
          <div class="mt-5">${needAssessments
            ? button("Open Assessments", "data-open-prior")
            : needAspiration
              ? button("Open Career Lattice", "data-open-prior")
              : button("Open Course Shop", "data-open-courses")}</div>
        </div>`);
      wireMentorControls(mentorPayload);
      qs("[data-open-prior]")?.addEventListener("click", () => {
        go(needAssessments ? "employee/roleplays" : "employee/career");
      });
      qs("[data-open-courses]")?.addEventListener("click", () => go("employee/courses"));
      return;
    }
    const courses = result.courses || [];
    if (!courses.length) {
      const [career, roleplays] = await Promise.all([
        api("/api/employee/career").catch(() => ({ choice: null })),
        api("/api/employee/roleplays").catch(() => ({ lattice_unlocked: false })),
      ]);
      const latticeUnlocked = Boolean(roleplays.lattice_unlocked);
      const aspirationLocked = Boolean(career.choice);
      const needAssessments = !latticeUnlocked;
      const needAspiration = latticeUnlocked && !aspirationLocked;
      render(`<div class="mb-6 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
          <div>
            <h1 class="text-2xl md:text-3xl font-extrabold text-[#df162b]">Your Learning Journey</h1>
            <p class="text-[#5d3f3d] mt-1">Track your progress across your identified gaps and unlock your full potential.</p>
          </div>
          <button type="button" data-connect-mentor class="inline-flex items-center justify-center gap-2 px-4 py-2.5 border border-[#df162b] text-[#df162b] rounded-lg font-bold text-sm hover:bg-[#df162b]/5 shrink-0">
            <span class="material-symbols-outlined text-[18px]">handshake</span>
            Connect with your mentor
          </button>
        </div>
        ${mentorTileHtml(result)}
        <div class="bg-white border border-[#e7bdb9] rounded-xl p-8 text-center max-w-2xl mx-auto">
          <span class="material-symbols-outlined text-5xl text-[#e7bdb9]">${needAssessments || needAspiration ? "lock" : "menu_book"}</span>
          <h2 class="text-xl font-bold text-[#291716] mt-3">${needAssessments || needAspiration ? "Learning journey locked" : "No courses locked yet"}</h2>
          <p class="text-sm text-[#5d3f3d] mt-2">${needAssessments
            ? "Complete both voice roleplays, unlock Career Lattice, and lock an aspiration first."
            : needAspiration
              ? "Lock a career aspiration on the Career Lattice before selecting courses."
              : "Shop recommended courses and checkout to lock your learning journey."}</p>
          <div class="mt-5">${needAssessments
            ? button("Open Assessments", "data-open-prior")
            : needAspiration
              ? button("Open Career Lattice", "data-open-prior")
              : button("Open Course Shop", "data-open-courses")}</div>
        </div>`);
      wireMentorControls(result);
      qs("[data-open-prior]")?.addEventListener("click", () => {
        go(needAssessments ? "employee/roleplays" : "employee/career");
      });
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
      const displayPct = status === "completed" ? 100 : progressPct;
      const progressBlock = (status === "in_progress" || status === "completed")
        ? `<div class="mb-3">
            <div class="flex items-center justify-between gap-2 mb-1.5">
              <span class="text-xs font-bold text-[#5d3f3d]">${displayPct}% complete</span>
            </div>
            <div class="w-full bg-[#ffe1df] h-2 rounded-full overflow-hidden">
              <div class="bg-[#1464F4] h-full rounded-full transition-all" style="width:${displayPct}%"></div>
            </div>
          </div>`
        : "";
      const footer = status === "completed"
        ? `<span class="text-[#5d3f3d] text-sm flex items-center gap-1"><span class="material-symbols-outlined text-base">check_circle</span> Completed</span>`
        : status === "in_progress"
          ? `<span class="text-[#5d3f3d] text-sm">In progress</span>`
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
          ${progressBlock}
          <div class="flex items-end justify-between gap-3">${footer}${actions}</div>
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

    render(`<section class="mb-8 flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h1 class="text-2xl md:text-3xl font-extrabold text-[#df162b] mb-1">Your Learning Journey</h1>
          <p class="text-[#5d3f3d]">Track your progress across your identified gaps and unlock your full potential.</p>
        </div>
        <button type="button" data-connect-mentor class="inline-flex items-center justify-center gap-2 px-4 py-2.5 border border-[#df162b] text-[#df162b] rounded-lg font-bold text-sm hover:bg-[#df162b]/5 shrink-0">
          <span class="material-symbols-outlined text-[18px]">handshake</span>
          Connect with your mentor
        </button>
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
      ${mentorTileHtml(result)}
      <section>${sections}</section>
      <p class="text-center text-xs text-[#926e6c] mt-8">Journey already Selected after checkout</p>`);

    wireMentorControls(result);
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
    if (role === "zm" || role === "rd") return await initManagerLeaderboard(payload, role);
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

    const cohortCard = `<div class="bg-white border border-[#e7bdb9] rounded-xl p-5 relative overflow-hidden flex flex-col justify-between w-full h-full min-w-0">
      <div class="absolute top-0 right-0 w-28 h-28 bg-[#fddbd8] rounded-bl-full opacity-30 -mr-8 -mt-8 pointer-events-none"></div>
      <div>
        <p class="text-[11px] font-bold uppercase tracking-wide text-[#005cab]">Your Cohort</p>
        <h2 class="text-4xl font-extrabold text-[#291716] mt-3 tracking-tight">${viewer.rank != null ? `Rank #${viewer.rank}` : "Unranked"}</h2>
        <p class="text-sm text-[#5d3f3d] mt-2 flex items-center gap-1">
          <span class="material-symbols-outlined text-[16px]">groups</span>
          Ranked by journey hours completed %
        </p>
      </div>
      <div class="mt-6 pt-4 border-t border-[#e7bdb9] flex justify-between items-end gap-3">
        <p class="text-sm text-[#5d3f3d]">Progress: <strong class="text-[#291716]">${viewer.hours_pct != null ? `${Number(viewer.hours_pct).toFixed(0)}%` : "—"}</strong></p>
        <div class="text-right">
          <p class="text-[11px] font-bold uppercase text-[#5d3f3d]">Ranked by</p>
          <p class="text-sm font-bold text-[#291716]">Hours · Courses</p>
        </div>
      </div>
    </div>`;

    const hoursPct = Math.max(0, Math.min(100, Number(viewer.hours_pct) || 0));
    const pulseSvg = (() => {
      const W = 120;
      const H = 36;
      const samples = 56;
      const pointAt = (t) => {
        const x = t * W;
        // Upward journey: start low-left, finish high-right, with soft waves.
        const climb = 30 - t * 22;
        const wave = Math.sin(t * Math.PI * 3.4) * (2.8 + t * 1.4);
        const settle = Math.sin(t * Math.PI * 1.1) * 1.2;
        return [x, Math.max(3, Math.min(H - 3, climb + wave + settle))];
      };
      const all = [];
      for (let i = 0; i <= samples; i += 1) all.push(pointAt(i / samples));
      const toPath = (pts) => {
        if (!pts.length) return "";
        if (pts.length === 1) return `M ${pts[0][0].toFixed(2)} ${pts[0][1].toFixed(2)}`;
        let d = `M ${pts[0][0].toFixed(2)} ${pts[0][1].toFixed(2)}`;
        for (let i = 1; i < pts.length; i += 1) {
          const [x0, y0] = pts[i - 1];
          const [x1, y1] = pts[i];
          const mx = (x0 + x1) / 2;
          const my = (y0 + y1) / 2;
          d += ` Q ${x0.toFixed(2)} ${y0.toFixed(2)} ${mx.toFixed(2)} ${my.toFixed(2)}`;
          if (i === pts.length - 1) d += ` L ${x1.toFixed(2)} ${y1.toFixed(2)}`;
        }
        return d;
      };
      const progN = hoursPct <= 0 ? 0 : Math.max(1, Math.round((hoursPct / 100) * samples));
      const prog = all.slice(0, progN + 1);
      const tip = prog[prog.length - 1] || all[0];
      const ghostD = toPath(all);
      const progD = toPath(prog);
      const areaD = prog.length > 1
        ? `${progD} L ${tip[0].toFixed(2)} ${H} L ${prog[0][0].toFixed(2)} ${H} Z`
        : "";
      const tipLeft = (tip[0] / W) * 100;
      const tipTop = (tip[1] / H) * 100;
      const finish = all[all.length - 1];
      const flagLeft = (finish[0] / W) * 100;
      const flagTop = (finish[1] / H) * 100;
      const uid = `pulse-${String(meCode || "me").replace(/[^a-zA-Z0-9_-]/g, "")}`;
      return `<div class="relative w-full h-16 mt-3">
        <svg class="absolute inset-0 w-full h-full overflow-visible" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="${uid}-fill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#005cab" stop-opacity="0.28"/>
              <stop offset="100%" stop-color="#005cab" stop-opacity="0.02"/>
            </linearGradient>
            <linearGradient id="${uid}-stroke" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stop-color="#5ba3e0"/>
              <stop offset="100%" stop-color="#005cab"/>
            </linearGradient>
          </defs>
          <path d="${ghostD}" fill="none" stroke="#d5e3ff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
          ${areaD ? `<path d="${areaD}" fill="url(#${uid}-fill)" stroke="none"/>` : ""}
          ${prog.length > 1 ? `<path d="${progD}" fill="none" stroke="url(#${uid}-stroke)" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>` : ""}
        </svg>
        <span class="absolute w-3 h-3 rounded-full bg-[#005cab] ring-2 ring-white shadow-sm pointer-events-none"
          style="left:${tipLeft.toFixed(2)}%; top:${tipTop.toFixed(2)}%; transform:translate(-50%,-50%)"></span>
        <span class="absolute pointer-events-none text-[#df162b] leading-none"
          style="left:${flagLeft.toFixed(2)}%; top:${flagTop.toFixed(2)}%; transform:translate(-20%,-95%)"
          title="Journey goal">
          <span class="material-symbols-outlined text-[26px]" style="font-variation-settings:'FILL' 1">flag</span>
        </span>
      </div>`;
    })();

    const pulseCard = `<div class="bg-white border border-[#e7bdb9] rounded-xl p-5 flex flex-col justify-between w-full h-full min-w-0">
      <div>
        <p class="text-[11px] font-bold uppercase tracking-wide text-[#5d3f3d] flex items-center gap-1">
          <span class="material-symbols-outlined text-[16px]">show_chart</span> Growth Pulse
        </p>
        <h3 class="text-2xl font-extrabold text-[#291716] mt-2">${hoursPct.toFixed(0)}%</h3>
        <p class="text-sm text-[#5d3f3d]">${Number(viewer.completed_hours || 0).toFixed(1)}h / ${Number(viewer.total_hours || 0).toFixed(1)}h journey</p>
      </div>
      ${pulseSvg}
    </div>`;

    const focusList = gaps.length
      ? gaps.slice(0, 3).map((gap, index) => `<li class="flex items-start gap-2.5">
          <span class="mt-0.5 w-6 h-6 rounded-full bg-[#fff0ef] text-[#df162b] text-xs font-extrabold grid place-items-center shrink-0">${index + 1}</span>
          <span class="text-[15px] font-bold text-[#291716] leading-snug break-words">${esc(gap.competency)}</span>
        </li>`).join("")
      : `<li class="text-sm text-[#5d3f3d] leading-relaxed">No focus gaps — keep stacking hours.</li>`;

    const weakSkills = `<div class="bg-white border border-[#e7bdb9] rounded-xl p-5 flex flex-col w-full h-full min-w-0">
      <p class="text-[11px] font-bold uppercase tracking-wide text-[#5d3f3d] flex items-center gap-1">
        <span class="material-symbols-outlined text-[16px]">track_changes</span> Focus Areas
      </p>
      <ul class="mt-6 space-y-3.5 min-w-0">${focusList}</ul>
    </div>`;

    const badgeShelf = `<div class="mb-8">
      <h3 class="text-lg font-bold text-[#291716] mb-3">Badge shelf</h3>
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-2">
        ${catalog.map((badge) => {
          const earned = earnedIds.has(badge.id);
          const mine = badges.find((item) => item.id === badge.id);
          const tier = mine?.meta?.tier;
          return `<div class="bg-white border rounded-lg p-2.5 flex flex-col items-center text-center ${earned ? "border-[#005cab] bg-[#eff6ff]" : "border-[#e7bdb9] opacity-70"}">
            <div class="w-9 h-9 rounded-full ${earned ? "bg-[#0075d7] text-white" : "bg-[#ffe1df] text-[#5d3f3d]"} flex items-center justify-center mb-2">
              <span class="material-symbols-outlined text-[20px]" style="font-variation-settings:'FILL' ${earned ? 1 : 0}">${esc(badge.icon || "military_tech")}</span>
            </div>
            <strong class="text-xs text-[#291716] leading-tight">${esc(badge.title)}${tier ? ` ×${tier}` : ""}</strong>
            <p class="text-[10px] text-[#5d3f3d] mt-1 leading-snug">${esc(badge.rule)}</p>
            <span class="text-[9px] font-bold uppercase tracking-wider mt-2 ${earned ? "text-[#005cab]" : "text-[#926e6c]"}">${earned ? "Earned" : "Locked"}</span>
          </div>`;
        }).join("")}
      </div>
    </div>`;

    render(`${pageHeader("Leaderboard", "Your learning journey completion decides your ranking.")}
      <div class="flex flex-col md:flex-row gap-4 mb-8">
        <div class="md:flex-1 md:basis-0 min-w-0">${cohortCard}</div>
        <div class="md:flex-1 md:basis-0 min-w-0">${pulseCard}</div>
        <div class="md:flex-1 md:basis-0 min-w-0">${weakSkills}</div>
      </div>
      ${badgeShelf}
      ${(() => {
        const kudos = viewer.kudos || [];
        if (!kudos.length) return "";
        return `<div class="mb-8">
          <h3 class="text-lg font-bold text-[#291716] mb-3">Recognition from Abhishek Logani</h3>
          <div class="space-y-2">
            ${kudos.map((entry) => `<article class="bg-white border border-[#e7bdb9] rounded-xl p-4 flex items-start gap-3">
              <div class="w-9 h-9 rounded-full bg-[#fff0ef] text-[#df162b] flex items-center justify-center shrink-0">
                <span class="material-symbols-outlined text-[20px]" style="font-variation-settings:'FILL' 1">celebration</span>
              </div>
              <div class="min-w-0">
                <p class="text-sm font-semibold text-[#291716]">${esc(entry.message)}</p>
                <p class="text-xs text-[#5d3f3d] mt-1">From ${esc(entry.from_name || "L-Team")} · ${esc(formatFeedbackWhen(entry.created_at))}</p>
              </div>
            </article>`).join("")}
          </div>
        </div>`;
      })()}
      <h3 class="text-lg font-bold text-[#291716] mb-3">Peer Rankings</h3>
      <div class="overflow-x-auto bg-white border border-[#e7bdb9] rounded-xl">
        <table class="w-full min-w-[640px] text-sm text-left">
          <thead class="bg-[#ffe9e7] text-[11px] uppercase tracking-wider text-[#5d3f3d]">
            <tr>
              <th class="p-4">Rank</th>
              <th class="p-4">Employee</th>
              <th class="p-4">Progress</th>
              <th class="p-4 hidden sm:table-cell">Courses done</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map((row) => {
              const mine = meCode && row.employee_code === meCode;
              const pct = Number(row.hours_pct || 0);
              return `<tr class="border-t border-[#e7bdb9] ${mine ? "bg-[#eff6ff] border-l-4 border-l-[#005cab]" : "hover:bg-[#fff0ef]"}">
                <td class="p-4 font-bold text-[#005cab]">#${row.rank}</td>
                <td class="p-4">
                  <div class="flex items-center gap-2">
                    <strong class="text-[#291716]">${esc(row.name)}</strong>
                    ${mine ? `<span class="bg-[#df162b] text-white text-[10px] font-bold uppercase px-1.5 py-0.5 rounded">You</span>` : ""}
                  </div>
                  <div class="text-xs text-[#5d3f3d]">${esc(row.employee_code)}</div>
                </td>
                <td class="p-4 ${mine ? "font-bold" : ""}">${pct.toFixed(pct % 1 ? 1 : 0)}%</td>
                <td class="p-4 hidden sm:table-cell ${mine ? "font-bold" : ""}">${Number(row.courses_completed || 0)}${row.courses_total ? `/${row.courses_total}` : ""}</td>
              </tr>`;
            }).join("") || empty("Leaderboard empty until final profiles exist.", 4)}
          </tbody>
        </table>
      </div>`);
  }

  async function initManagerLeaderboard(payload, role) {
    const rows = payload.leaderboard || [];
    const stats = payload.stats || {};
    const catalog = payload.badge_catalog || [];
    const [summaries, meta] = await Promise.all([employeeSummaries(), api("/api/meta")]);
    const competencies = (meta.competencies || []).map((item) => item.competency).filter(Boolean);
    let searchTerm = "";
    let searchRaw = "";

    const draw = () => {
      const list = rows.filter((row) => {
        if (!searchTerm) return true;
        return [row.employee_code, row.name].some((value) => String(value || "").toLowerCase().includes(searchTerm));
      });
      const hoursMax = Math.max(1, ...(stats.hours_buckets || []).map((row) => row.count), 0);
      const badgeRows = stats.badge_distribution?.length
        ? stats.badge_distribution
        : catalog.map((badge) => ({
          id: badge.id,
          name: badge.title,
          rule: badge.rule,
          icon: badge.icon,
          count: 0,
        }));
      const badgeEarners = badgeRows.reduce((sum, row) => sum + Number(row.count || 0), 0);
      const gapSkillsList = (row) => {
        const names = (row.gaps || []).map((gap) => gap.competency).filter(Boolean);
        if (!names.length) return `<span class="text-[#926e6c]">—</span>`;
        return `<div class="flex flex-wrap gap-1.5 max-w-[280px]">${names.map((name) =>
          `<span class="inline-block px-2 py-0.5 rounded-md bg-[#fff0ef] border border-[#e7bdb9] text-[11px] font-semibold text-[#291716]">${esc(name)}</span>`
        ).join("")}</div>`;
      };
      const matrixHtml = renderSkillProficiencyMatrix({
        skills: competencies,
        employees: summaries,
        getRatings: (row) => {
          if (role === "rd") {
            const rdRatings = row.rd_ratings || {};
            if (Object.keys(rdRatings).length) return rdRatings;
            if (row.zm_status === "submitted") return row.zm_ratings || {};
            return {};
          }
          return row.zm_ratings || {};
        },
        emptyMessage: "No ratings yet. Matrix fills as assessments are saved.",
        compact: true,
        embedded: true,
      });

      render(`${pageHeader("Leaderboard", `Learning Journey Completion Status.`)}
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-4 mb-6">
          <div class="lg:col-span-7 bg-white border border-[#e7bdb9] rounded-xl p-5">
            <div class="flex justify-between items-end gap-3 mb-4 flex-wrap">
              <div>
                <h3 class="text-lg font-bold text-[#291716]">Learning Pulse</h3>
                <p class="text-sm text-[#5d3f3d] mt-1">LinkedIn hours mix across your team</p>
              </div>
              <div class="text-right">
                <p class="text-3xl font-extrabold text-[#005cab]">${Number(stats.total_hours || 0).toFixed(0)}</p>
                <p class="text-xs text-[#5d3f3d]">Total hours · ${stats.team_size || 0} ${(stats.team_size || 0) === 1 ? "person" : "people"}</p>
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
          <div class="lg:col-span-5 bg-white border border-[#e7bdb9] rounded-xl p-5 flex flex-col">
            <h3 class="text-lg font-bold text-[#291716]">Team badges</h3>
            <p class="text-sm text-[#5d3f3d] mb-4">All badges available to earn · ${badgeEarners} earned</p>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 flex-1 content-start">
              ${badgeRows.map((row) => {
                const earned = Number(row.count || 0) > 0;
                return `<div class="rounded-lg border p-2.5 flex items-start gap-2 ${earned ? "border-[#005cab] bg-[#eff6ff]" : "border-[#e7bdb9] bg-white"}">
                  <div class="w-8 h-8 rounded-full shrink-0 ${earned ? "bg-[#0075d7] text-white" : "bg-[#ffe1df] text-[#5d3f3d]"} flex items-center justify-center">
                    <span class="material-symbols-outlined text-[16px]" style="font-variation-settings:'FILL' ${earned ? 1 : 0}">${esc(row.icon || "military_tech")}</span>
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center justify-between gap-2">
                      <strong class="text-xs text-[#291716] truncate">${esc(row.name)}</strong>
                      <span class="text-[10px] font-bold ${earned ? "text-[#005cab]" : "text-[#926e6c]"} shrink-0">${earned ? `${row.count} earned` : "Available"}</span>
                    </div>
                    <p class="text-[10px] text-[#5d3f3d] mt-0.5 leading-snug">${esc(row.rule || "")}</p>
                  </div>
                </div>`;
              }).join("")}
            </div>
          </div>
          <div class="lg:col-span-12 bg-white border border-[#e7bdb9] rounded-xl p-4">
            ${matrixHtml}
          </div>
        </div>
        <div class="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h3 class="text-lg font-bold text-[#291716]">Team leaderboard</h3>
          </div>
          <label class="relative block">
            <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[#926e6c] text-[18px]">search</span>
            <input data-lb-search value="${esc(searchRaw)}" class="pl-10 pr-4 py-2 border border-[#e7bdb9] rounded-full text-sm w-full sm:w-64 outline-none focus:border-[#005cab]" placeholder="Search employees...">
          </label>
        </div>
        <div class="bg-white border border-[#e7bdb9] rounded-xl overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full min-w-[920px] text-sm text-left">
              <thead class="bg-[#fff0ef] text-[11px] uppercase tracking-wide text-[#5d3f3d]">
                <tr>
                  <th class="p-4">Rank</th>
                  <th class="p-4">Employee</th>
                  <th class="p-4">Progress</th>
                  <th class="p-4">Courses done</th>
                  <th class="p-4">Focus Areas</th>
                  <th class="p-4 text-center">Badges</th>
                </tr>
              </thead>
              <tbody>
                ${list.length
                  ? [...list].sort((a, b) => (a.rank - b.rank) || String(a.name || "").localeCompare(String(b.name || ""))).map((row) => {
                    const pct = Number(row.hours_pct || 0);
                    const doneH = Number(row.completed_hours || 0);
                    const totalH = Number(row.total_hours || 0);
                    return `<tr class="border-t border-[#e7bdb9] hover:bg-[#fff0ef]">
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
                      <td class="p-4 min-w-[120px]">
                        <div class="font-bold text-[#291716]">${pct.toFixed(pct % 1 ? 1 : 0)}%</div>
                        <div class="text-[10px] text-[#926e6c] mt-0.5">${doneH.toFixed(1)}h / ${totalH.toFixed(1)}h</div>
                      </td>
                      <td class="p-4 font-bold text-[#291716]">${Number(row.courses_completed || 0)}${row.courses_total ? `<span class="text-[#926e6c] font-normal">/${row.courses_total}</span>` : ""}</td>
                      <td class="p-4">${gapSkillsList(row)}</td>
                      <td class="p-4 text-center">${lbBadgeIcons(row.badges, catalog)}</td>
                    </tr>`;
                  }).join("")
                  : empty("No employees in scope yet.", 6)}
              </tbody>
            </table>
          </div>
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

  async function initLteamDashboard() {
    const KUDOS_TEXT = "Kudos, you're learning curve is going good.";
    const [payload, summaryPayload] = await Promise.all([
      api("/api/leaderboard"),
      api("/api/employee-summaries"),
    ]);
    const stats = payload.stats || {};
    const catalog = payload.badge_catalog || [];
    const lbByCode = Object.fromEntries((payload.leaderboard || []).map((row) => [row.employee_code, row]));
    const rows = (summaryPayload.employees || []).map((row) => ({
      ...row,
      ...(lbByCode[row.employee_code] || {}),
    }));
    let searchTerm = "";
    let searchRaw = "";

    const draw = () => {
      const list = rows.filter((row) => {
        if (!searchTerm) return true;
        return [row.employee_code, row.name, row.zm_name, row.rd_name]
          .some((value) => String(value || "").toLowerCase().includes(searchTerm));
      });
      const skillGaps = stats.skill_gap_distribution || [];
      const skillMax = Math.max(1, ...skillGaps.map((row) => row.count), 0);
      const hoursMax = Math.max(1, ...(stats.hours_buckets || []).map((row) => row.count), 0);
      const badgeRows = stats.badge_distribution?.length
        ? stats.badge_distribution
        : catalog.map((badge) => ({
          id: badge.id,
          name: badge.title,
          rule: badge.rule,
          icon: badge.icon,
          count: 0,
        }));
      const badgeEarners = badgeRows.reduce((sum, row) => sum + Number(row.count || 0), 0);
      const gapSkillsList = (row) => {
        const names = (row.gaps || []).map((gap) => gap.competency).filter(Boolean);
        if (!names.length) return `<span class="text-[#926e6c]">—</span>`;
        return `<div class="flex flex-wrap gap-1.5 max-w-[240px]">${names.map((name) =>
          `<span class="inline-block px-2 py-0.5 rounded-md bg-[#fff0ef] border border-[#e7bdb9] text-[11px] font-semibold text-[#291716]">${esc(name)}</span>`
        ).join("")}</div>`;
      };

      render(`${pageHeader("L-Team Dashboard", "Org-wide learning pulse and journey visibility for every employee.")}
        <div class="grid grid-cols-1 lg:grid-cols-12 gap-4 mb-6">
          <div class="lg:col-span-7 bg-white border border-[#e7bdb9] rounded-xl p-5">
            <div class="flex justify-between items-end gap-3 mb-4 flex-wrap">
              <div>
                <h3 class="text-lg font-bold text-[#291716]">Learning Pulse</h3>
                <p class="text-sm text-[#5d3f3d] mt-1">LinkedIn hours mix across all employees</p>
              </div>
              <div class="text-right">
                <p class="text-3xl font-extrabold text-[#005cab]">${Number(stats.total_hours || 0).toFixed(0)}</p>
                <p class="text-xs text-[#5d3f3d]">Total hours · ${stats.team_size || rows.length} ${(Number(stats.team_size || rows.length) === 1) ? "person" : "people"}</p>
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
          <div class="lg:col-span-5 bg-white border border-[#e7bdb9] rounded-xl p-5 flex flex-col">
            <h3 class="text-lg font-bold text-[#291716]">Team badges</h3>
            <p class="text-sm text-[#5d3f3d] mb-4">All badges available · ${badgeEarners} earned</p>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 flex-1 content-start">
              ${badgeRows.map((row) => {
                const earned = Number(row.count || 0) > 0;
                return `<div class="rounded-lg border p-2.5 flex items-start gap-2 ${earned ? "border-[#005cab] bg-[#eff6ff]" : "border-[#e7bdb9] bg-white"}">
                  <div class="w-8 h-8 rounded-full shrink-0 ${earned ? "bg-[#0075d7] text-white" : "bg-[#ffe1df] text-[#5d3f3d]"} flex items-center justify-center">
                    <span class="material-symbols-outlined text-[16px]" style="font-variation-settings:'FILL' ${earned ? 1 : 0}">${esc(row.icon || "military_tech")}</span>
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center justify-between gap-2">
                      <strong class="text-xs text-[#291716] truncate">${esc(row.name)}</strong>
                      <span class="text-[10px] font-bold ${earned ? "text-[#005cab]" : "text-[#926e6c]"} shrink-0">${earned ? `${row.count} earned` : "Available"}</span>
                    </div>
                    <p class="text-[10px] text-[#5d3f3d] mt-0.5 leading-snug">${esc(row.rule || "")}</p>
                  </div>
                </div>`;
              }).join("")}
            </div>
          </div>
          <div class="lg:col-span-12 bg-white border border-[#e7bdb9] rounded-xl p-5">
            <h3 class="text-lg font-bold text-[#291716] mb-1">Skill gap distribution</h3>
            <p class="text-sm text-[#5d3f3d] mb-4">People with a gap in each competency</p>
            <div class="flex items-end gap-2 h-44 overflow-x-auto pb-1">
              ${skillGaps.length
                ? skillGaps.map((row) => {
                  const height = Math.max(10, Math.round((row.count / skillMax) * 100));
                  return `<div class="flex-1 min-w-[72px] flex flex-col items-center gap-2 h-full justify-end">
                    <span class="text-xs font-bold text-[#005cab]">${row.count}</span>
                    <div class="w-full max-w-[56px] bg-[#a6c8ff] hover:bg-[#0075d7] rounded-t transition-colors" style="height:${height}%" title="${esc(row.competency)}: ${row.count}"></div>
                    <span class="text-[10px] text-[#5d3f3d] text-center leading-tight line-clamp-2 min-h-[2.5rem]">${esc(row.competency)}</span>
                  </div>`;
                }).join("")
                : `<p class="text-sm text-[#5d3f3d]">No skill gaps yet.</p>`}
            </div>
          </div>
        </div>
        <div class="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h3 class="text-lg font-bold text-[#291716]">All employees</h3>
            <p class="text-xs text-[#5d3f3d] mt-0.5">Journey status · send preset kudos</p>
          </div>
          <label class="relative block">
            <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[#926e6c] text-[18px]">search</span>
            <input data-lb-search value="${esc(searchRaw)}" class="pl-10 pr-4 py-2 border border-[#e7bdb9] rounded-full text-sm w-full sm:w-64 outline-none focus:border-[#005cab]" placeholder="Search employees...">
          </label>
        </div>
        <div class="bg-white border border-[#e7bdb9] rounded-xl overflow-hidden">
          <div class="overflow-x-auto">
            <table class="w-full min-w-[980px] text-sm text-left">
              <thead class="bg-[#fff0ef] text-[11px] uppercase tracking-wide text-[#5d3f3d]">
                <tr>
                  <th class="p-4">Employee</th>
                  <th class="p-4">Journey</th>
                  <th class="p-4">Progress</th>
                  <th class="p-4">Focus Areas</th>
                  <th class="p-4 text-right">Kudos</th>
                </tr>
              </thead>
              <tbody>
                ${list.map((row) => {
                  const pct = Number(row.hours_pct || 0);
                  const locked = Boolean(row.journey_locked || row.learning_locked);
                  const aspiration = row.aspiration?.aspiration_role
                    ? String(row.aspiration.aspiration_role).toUpperCase()
                    : "Not selected";
                  return `<tr class="border-t border-[#e7bdb9] hover:bg-[#fff0ef]">
                    <td class="p-4">
                      <strong class="text-[#291716]">${esc(row.name)}</strong>
                      <div class="text-xs text-[#5d3f3d]">${esc(row.employee_code)} · ${esc(row.designation || "—")}</div>
                      <div class="text-[11px] text-[#926e6c]">ZM ${esc(row.zm_name || "—")} · RD ${esc(row.rd_name || "—")}</div>
                    </td>
                    <td class="p-4">
                      <div class="text-sm font-semibold text-[#291716]">${locked ? "Locked" : "Open"}</div>
                      <div class="text-xs text-[#5d3f3d]">Aspiration: ${esc(aspiration)}</div>
                      <div class="text-xs text-[#5d3f3d]">${Number(row.courses_completed || 0)}/${Number(row.courses_total || 0)} courses done</div>
                    </td>
                    <td class="p-4">
                      <div class="font-bold text-[#291716]">${pct.toFixed(pct % 1 ? 1 : 0)}%</div>
                      <div class="text-[10px] text-[#926e6c]">${Number(row.completed_hours || 0).toFixed(1)}h / ${Number(row.total_hours || 0).toFixed(1)}h</div>
                    </td>
                    <td class="p-4">${gapSkillsList(row)}</td>
                    <td class="p-4 text-right">
                      <button type="button" data-kudos="${esc(row.employee_code)}" class="px-3 py-2 bg-[#df162b] text-white rounded-lg font-bold text-xs hover:opacity-90">Send kudos</button>
                    </td>
                  </tr>`;
                }).join("") || empty("No employees found.", 5)}
              </tbody>
            </table>
          </div>
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
      qsa("[data-kudos]").forEach((control) => {
        control.onclick = async () => {
          if (!confirm(`Send to this employee?\n\n"${KUDOS_TEXT}"`)) return;
          try {
            control.disabled = true;
            await api("/api/kudos", {
              method: "POST",
              body: JSON.stringify({ employee_code: control.dataset.kudos }),
            });
            toast("Kudos sent.");
          } catch (error) {
            toast(error.message, "error");
          } finally {
            control.disabled = false;
          }
        };
      });
    };

    draw();
  }

  function initAdminLeaderboard(payload) {
    const rows = payload.leaderboard || [];
    const catalog = payload.badge_catalog || [];
    let filterBand = "all";
    let sortMode = "rank-asc";
    let filterOpen = false;
    let sortOpen = false;
    let searchTerm = "";
    let searchRaw = "";

    const filterLabel = {
      all: "All",
      locked: "Journey Already Selected",
      unlocked: "Journey open",
    };
    const sortLabel = {
      "rank-asc": "Rank low→high",
      "rank-desc": "Rank high→low",
      "pct-desc": "Progress % high→low",
      "pct-asc": "Progress % low→high",
      "courses-desc": "Courses done high→low",
      "name-asc": "Name A–Z",
      "name-desc": "Name Z–A",
      "code-asc": "Employee code A–Z",
      "code-desc": "Employee code Z–A",
    };

    const filtered = () => {
      let list = rows.filter((row) => {
        if (filterBand === "locked" && !row.journey_locked) return false;
        if (filterBand === "unlocked" && row.journey_locked) return false;
        if (!searchTerm) return true;
        return [row.employee_code, row.name].some((value) => String(value || "").toLowerCase().includes(searchTerm));
      });
      list = [...list].sort((a, b) => {
        if (sortMode === "rank-asc") return (a.rank - b.rank) || String(a.name).localeCompare(String(b.name));
        if (sortMode === "rank-desc") return (b.rank - a.rank) || String(a.name).localeCompare(String(b.name));
        if (sortMode === "pct-desc") return (b.hours_pct - a.hours_pct) || (b.courses_completed - a.courses_completed);
        if (sortMode === "pct-asc") return (a.hours_pct - b.hours_pct) || (a.courses_completed - b.courses_completed);
        if (sortMode === "courses-desc") return (b.courses_completed - a.courses_completed) || (b.hours_pct - a.hours_pct);
        if (sortMode === "name-asc") return String(a.name || "").localeCompare(String(b.name || ""));
        if (sortMode === "name-desc") return String(b.name || "").localeCompare(String(a.name || ""));
        if (sortMode === "code-asc") return String(a.employee_code || "").localeCompare(String(b.employee_code || ""), undefined, { numeric: true });
        if (sortMode === "code-desc") return String(b.employee_code || "").localeCompare(String(a.employee_code || ""), undefined, { numeric: true });
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

      render(`${pageHeader("Leaderboard", "Flat ranking by journey hours completed %")}
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
            <span class="text-xs text-[#5d3f3d]">Showing ${list.length} of ${rows.length}</span>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full min-w-[820px] text-sm text-left">
              <thead class="bg-[#fff0ef] text-[11px] uppercase tracking-wide text-[#5d3f3d]">
                <tr>
                  <th class="p-4">Rank</th>
                  <th class="p-4">Employee</th>
                  <th class="p-4">Progress</th>
                  <th class="p-4">Courses done</th>
                  <th class="p-4 text-center">Badges</th>
                </tr>
              </thead>
              <tbody>
                ${list.map((row) => {
                  const pct = Number(row.hours_pct || 0);
                  return `<tr class="border-t border-[#e7bdb9] hover:bg-[#fff0ef]">
                    <td class="p-4 font-bold text-[#005cab]">#${row.rank}</td>
                    <td class="p-4"><strong>${esc(row.name)}</strong><div class="text-xs text-[#5d3f3d]">${esc(row.employee_code)}</div></td>
                    <td class="p-4">
                      <div class="font-bold">${pct.toFixed(pct % 1 ? 1 : 0)}%</div>
                      <div class="text-[10px] text-[#926e6c]">${Number(row.completed_hours || 0).toFixed(1)}h / ${Number(row.total_hours || 0).toFixed(1)}h</div>
                    </td>
                    <td class="p-4 font-bold">${Number(row.courses_completed || 0)}${row.courses_total ? `<span class="font-normal text-[#926e6c]">/${row.courses_total}</span>` : ""}</td>
                    <td class="p-4 text-center">${lbBadgeIcons(row.badges, catalog)}</td>
                  </tr>`;
                }).join("") || empty("No matching employees.", 5)}
              </tbody>
            </table>
          </div>
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
    const phaseLabel = { zm: "ZM Assessment", rd: "RD Validation", employee: "Employee Experience", feedback: "ZM Journey Feedback" };
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
    const names = {
      zm: "ZM Competency Assessment",
      rd: "RD Competency Validation",
      employee: "Employee Career & Learning",
      feedback: "ZM Quarterly Journey Feedback",
    };
    const blurbs = {
      zm: "Open when ZMs should rate team competencies.",
      rd: "Open after ZM work; RDs validate final profiles.",
      employee: "Open when employees may run roleplays, lattice, and learning.",
      feedback: "Independent quarterly window. ZMs log whether journeys started and behaviour changed. Does not close other phases.",
    };
    render(`${pageHeader("Phase Control", "Assessment phases gate login and workflow. Feedback is a separate quarterly logbook toggle.")}
      <div class="space-y-4">${phases.map((phase) => {
        const open = phase.status === "open";
        return `<section class="bg-white border border-slate-200 rounded-xl p-6">
        <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div class="flex items-center gap-3"><h2 class="text-xl font-bold">${esc(names[phase.phase] || phase.phase)}</h2>${statusChip(phase.status)}</div>
            <p class="text-sm text-slate-500 mt-2">${esc(blurbs[phase.phase] || "")}</p>
            <p class="text-sm text-slate-500 mt-1">${phase.progress.completed}/${phase.progress.total} complete · ${phase.progress.percentage}%${phase.override_used ? " · opened by override" : ""}</p>
          </div>
          <label class="inline-flex items-center gap-3 cursor-pointer select-none shrink-0">
            <span class="text-xs font-bold uppercase tracking-wide ${open ? "text-emerald-700" : "text-slate-500"}">${open ? "Open" : "Closed"}</span>
            <button type="button" role="switch" aria-checked="${open ? "true" : "false"}" data-phase="${phase.phase}" data-status="${phase.status}"
              class="relative w-14 h-8 rounded-full transition-colors ${open ? "bg-emerald-600" : "bg-slate-300"} focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-600">
              <span class="absolute top-1 left-1 w-6 h-6 rounded-full bg-white shadow transition-transform ${open ? "translate-x-6" : "translate-x-0"}"></span>
            </button>
          </label>
        </div>
        <div class="h-2 bg-slate-100 rounded mt-5 overflow-hidden"><div class="h-full bg-blue-700" style="width:${phase.progress.percentage}%"></div></div>
      </section>`;
      }).join("")}</div>`);
    qsa("[data-phase]").forEach((control) => {
      control.onclick = async () => {
        const phase = phases.find((item) => item.phase === control.dataset.phase);
        try {
          if (phase.status === "open") {
            if (!confirm(`Close ${names[phase.phase] || phase.phase}?`)) return;
            await api("/api/admin/phases/close", { method: "POST", body: JSON.stringify({ phase: phase.phase }) });
          } else {
            const previousIndex = phases.findIndex((item) => item.phase === phase.phase) - 1;
            const needsGate = phase.phase !== "feedback" && previousIndex >= 0;
            const previousIncomplete = needsGate && !phases[previousIndex].progress.is_complete;
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
          await initPhases();
        }
      };
    });
  }

  async function initAdminEmployees() {
    const rows = await employeeSummaries();
    const total = rows.length;
    if (!total) {
      render(`${pageHeader("Employee Master")}<p class="bg-white border rounded-xl p-8">No employees available.</p>`);
      return;
    }

    let filterStatus = adminEmployeesView.filterStatus || "all";
    let sortMode = adminEmployeesView.sortMode || "code-asc";
    let filterOpen = false;
    let sortOpen = false;
    let searchRaw = adminEmployeesView.searchRaw || "";
    let searchTerm = searchRaw.trim().toLowerCase();
    let selected = params.get("employee") || adminEmployeesView.selectedCode || rows[0].employee_code;
    if (!rows.some((row) => row.employee_code === selected)) selected = rows[0].employee_code;

    const filterLabel = {
      all: "All",
      zm_pending: "ZM pending",
      zm_draft: "ZM draft",
      zm_submitted: "ZM submitted",
      rd_pending: "RD pending",
      rd_draft: "RD draft",
      rd_submitted: "RD validated",
      aspiration: "Aspiration Selected",
    };
    const sortLabel = {
      "code-asc": "Employee code A–Z",
      "code-desc": "Employee code Z–A",
      "name-asc": "Name A–Z",
      "name-desc": "Name Z–A",
      "zm-asc": "ZM status",
      "rd-asc": "RD status",
      "assessments-desc": "Assessments high→low",
      "assessments-asc": "Assessments low→high",
    };
    const statusRank = { not_started: 0, pending: 0, draft: 1, submitted: 2 };
    const careerMoveLabel = {
      kam: "KAM", zm: "ZM", bdfe: "BDFE", category: "Category", continue: "Continue in Current Profile",
    };

    const persistView = () => {
      adminEmployeesView.sortMode = sortMode;
      adminEmployeesView.filterStatus = filterStatus;
      adminEmployeesView.searchRaw = searchRaw;
      adminEmployeesView.selectedCode = selected;
    };

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

    const bindDetailActions = () => {
      qsa("[data-profile]").forEach((control) => { control.onclick = () => openFinalProfile(control.dataset.profile); });
      qsa("[data-feedback]").forEach((control) => {
        control.onclick = () => openFeedbackLogbook(control.dataset.feedback).catch((error) => toast(error.message, "error"));
      });
      qsa("[data-roleplay-review]").forEach((control) => {
        control.onclick = () => openAdminRoleplays(control.dataset.roleplayReview);
      });
      qsa("[data-reset-assessments]").forEach((control) => {
        control.onclick = async () => {
          if (!confirm("Reset this employee's BDM voice assessments (Functional + Behavioural)? They can retake both sessions. Scores will be cleared.")) return;
          try {
            await api("/api/admin/roleplays/reset", {
              method: "POST",
              body: JSON.stringify({ employee_code: control.dataset.resetAssessments }),
            });
            toast("BDM assessments reset.");
            await initAdminEmployees();
          } catch (error) {
            toast(error.message, "error");
          }
        };
      });
      qsa("[data-reset-zm-rd]").forEach((control) => {
        control.onclick = async () => {
          const scope = control.dataset.resetZmRdScope || "both";
          const labels = {
            both: "ZM and RD inputs (drafts + submissions)? RD final profile and course recs tied to it are cleared. Aspiration stays.",
            zm: "ZM input? RD validation will also be cleared (depends on ZM). Aspiration stays.",
            rd: "RD input only? ZM submission stays. Final profile and course recs are cleared. Aspiration stays.",
          };
          if (!confirm(`Reset this employee's ${labels[scope] || labels.both}`)) return;
          try {
            await api("/api/admin/assessments/reset", {
              method: "POST",
              body: JSON.stringify({ employee_code: control.dataset.resetZmRd, scope }),
            });
            toast(scope === "rd" ? "RD input reset." : scope === "zm" ? "ZM (+ RD) input reset." : "ZM/RD inputs reset.");
            await initAdminEmployees();
          } catch (error) {
            toast(error.message, "error");
          }
        };
      });
      qsa("[data-reset-courses]").forEach((control) => {
        control.onclick = async () => {
          if (!confirm("Reset this employee's Select Your Courses / learning journey? They can select courses again. Aspiration stays locked.")) return;
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

    const detailMeta = (label, valueHtml) => `
      <div class="bg-[#fff8f7] border border-[#e7bdb9] rounded-xl p-4 min-h-[88px]">
        <p class="text-[11px] font-bold uppercase tracking-wider text-[#5d3f3d]">${esc(label)}</p>
        <div class="mt-2 text-sm font-semibold text-[#291716]">${valueHtml}</div>
      </div>`;

    const draw = () => {
      const list = filteredSorted();
      if (list.length && !list.some((row) => row.employee_code === selected)) {
        selected = list[0].employee_code;
      }
      persistView();
      history.replaceState({}, "", `/app/admin/employees?employee=${encodeURIComponent(selected)}`);

      const row = list.find((item) => item.employee_code === selected) || rows.find((item) => item.employee_code === selected);
      const filterActive = filterStatus !== "all";
      const chipBase = "px-3 py-1.5 bg-white border rounded-full text-xs font-bold inline-flex items-center gap-1 cursor-pointer hover:border-[#df162b] hover:text-[#df162b] transition-colors";
      const chipOn = "border-[#df162b] text-[#df162b] bg-[#fff0ef]";
      const chipOff = "border-[#e7bdb9] text-[#5d3f3d]";
      const fbCount = Number(row?.feedback_count) || 0;
      const zmMove = careerMoveLabel[row?.zm_career_recommendation] || row?.zm_career_recommendation || "—";
      const rdMove = careerMoveLabel[row?.rd_career_recommendation] || row?.rd_career_recommendation || "—";
      const aspiration = row?.aspiration?.aspiration_role
        ? String(row.aspiration.aspiration_role).toUpperCase()
        : "Not selected";
      const code = row?.employee_code || selected;

      const actionButtons = row ? [
        button("View profile", `data-profile="${esc(code)}"`, true),
        button("Assessments", `data-roleplay-review="${esc(code)}"`, true),
        button(fbCount ? `Feedback log (${fbCount})` : "Feedback log", `data-feedback="${esc(code)}"`, true),
        (row.roleplays_completed || 0) > 0
          ? button("Reset assessments", `data-reset-assessments="${esc(code)}"`, true)
          : "",
        (row.zm_status === "draft" || row.zm_status === "submitted")
          ? button("Reset ZM", `data-reset-zm-rd="${esc(code)}" data-reset-zm-rd-scope="zm"`, true)
          : "",
        (row.rd_status === "draft" || row.rd_status === "submitted")
          ? button("Reset RD", `data-reset-zm-rd="${esc(code)}" data-reset-zm-rd-scope="rd"`, true)
          : "",
        row.learning_locked
          ? button("Reset courses", `data-reset-courses="${esc(code)}"`, true)
          : "",
        row.aspiration
          ? button("Reset aspiration", `data-reset="${esc(code)}"`, true)
          : "",
      ].filter(Boolean).join("") : "";

      render(`<div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <aside class="lg:col-span-3 bg-white border border-[#e7bdb9] rounded-xl overflow-hidden sticky top-4">
          <div class="p-4 border-b border-[#e7bdb9] space-y-3">
            <div class="flex items-center justify-between gap-2">
              <h2 class="text-base font-extrabold text-[#291716]">Employees</h2>
              <span class="text-[11px] font-semibold text-[#5d3f3d]">${list.length}${filterActive || searchTerm ? `/${total}` : ""}</span>
            </div>
            <label class="relative block">
              <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-[#926e6c] text-[18px]">search</span>
              <input data-search value="${esc(searchRaw)}" class="w-full pl-10 pr-3 py-2.5 border border-[#e7bdb9] rounded-full text-sm outline-none focus:border-[#df162b] bg-[#fff8f7]" placeholder="Search team...">
            </label>
            <div class="flex gap-2 flex-wrap">
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
                <button type="button" data-toggle-sort class="${chipBase} ${sortMode !== "code-asc" || sortOpen ? chipOn : chipOff}">
                  <span class="material-symbols-outlined text-[16px]">sort</span>
                  Sort
                </button>
                ${sortOpen ? `<div class="absolute left-0 top-full mt-2 z-20 min-w-[220px] bg-white border border-[#e7bdb9] rounded-xl shadow-lg py-1">
                  ${Object.entries(sortLabel).map(([key, label]) => `<button type="button" data-sort="${key}" class="w-full text-left px-4 py-2 text-sm font-semibold hover:bg-[#fff0ef] ${sortMode === key ? "text-[#df162b]" : "text-[#291716]"}">${esc(label)}</button>`).join("")}
                </div>` : ""}
              </div>
            </div>
          </div>
          <div class="max-h-[70vh] overflow-y-auto p-2 space-y-1">
            ${list.map((item) => {
              const active = item.employee_code === selected;
              return `<button type="button" data-emp="${esc(item.employee_code)}" class="w-full text-left px-3 py-2.5 rounded-lg text-sm font-semibold flex items-center justify-between gap-2 transition-colors ${active ? "bg-[#df162b] text-white shadow-sm" : "text-[#291716] hover:bg-[#fff0ef]"}">
                <span class="truncate">${esc(item.name)} <span class="${active ? "text-white/80" : "text-[#5d3f3d]"} font-normal">(${esc(item.employee_code)})</span></span>
                ${active ? `<span class="material-symbols-outlined text-[18px] shrink-0" style="font-variation-settings:'FILL' 1">check</span>` : ""}
              </button>`;
            }).join("") || `<p class="p-3 text-sm text-[#5d3f3d]">No matches.</p>`}
          </div>
        </aside>

        <section class="lg:col-span-9 min-w-0">
          <div class="flex flex-col md:flex-row md:items-start md:justify-between gap-4 mb-6">
            <div>
              <h1 class="text-3xl md:text-4xl font-extrabold tracking-tight text-[#df162b]">Employee Master</h1>
              <p class="text-base text-[#5d3f3d] mt-2 max-w-3xl">Workbook identity plus persisted workflow status for the selected employee.</p>
            </div>
            ${button("Export CSV", "data-export", true)}
          </div>

          ${row ? `
          <div class="bg-white border border-[#e7bdb9] rounded-xl p-5 md:p-6 mb-6">
            <div class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
              <div class="min-w-0">
                <p class="text-[11px] font-bold uppercase tracking-wider text-[#5d3f3d]">Selected employee</p>
                <h2 class="text-2xl md:text-3xl font-extrabold text-[#291716] mt-1 truncate">${esc(row.name)}</h2>
                <p class="text-sm text-[#5d3f3d] mt-1">${esc(row.employee_code)}${row.designation ? ` · ${esc(row.designation)}` : ""}${row.grade ? ` · ${esc(row.grade)}` : ""}</p>
              </div>
              <div class="flex flex-wrap gap-2 shrink-0">
                ${statusChip(row.zm_status)}
                ${statusChip(row.rd_status)}
                ${row.learning_locked ? statusChip("locked") : statusChip("open")}
              </div>
            </div>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 mb-6">
            ${detailMeta("ZM", esc(row.zm_name || "—"))}
            ${detailMeta("RD", esc(row.rd_name || "—"))}
            ${detailMeta("Assessment status", `${statusChip(row.zm_status)} <span class="inline-block w-2"></span> ${statusChip(row.rd_status)}`)}
            ${detailMeta("ZM career move", esc(zmMove))}
            ${detailMeta("RD career move", esc(rdMove))}
            ${detailMeta("Voice assessments", `${esc(String(row.roleplays_completed || 0))}/${esc(String(row.roleplays_total || 0))}`)}
            ${detailMeta("Aspiration", esc(aspiration))}
            ${detailMeta("Courses", row.learning_locked ? statusChip("locked") : statusChip("open"))}
            ${detailMeta("Feedback entries", esc(String(fbCount)))}
          </div>

          <div class="bg-white border border-[#e7bdb9] rounded-xl p-5 md:p-6">
            <h3 class="text-lg font-extrabold text-[#291716]">Actions</h3>
            <p class="text-sm text-[#5d3f3d] mt-1 mb-5">Review profile and assessments, or reset workflow steps for this employee.</p>
            <div class="flex flex-wrap gap-3">${actionButtons}</div>
          </div>
          ` : `<div class="bg-white border border-[#e7bdb9] rounded-xl p-8 text-[#5d3f3d]">No employee selected.</div>`}
        </section>
      </div>`);

      bindDetailActions();
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
          persistView();
          draw();
        };
      });
      qsa("[data-sort]").forEach((control) => {
        control.onclick = (event) => {
          event.stopPropagation();
          sortMode = control.dataset.sort;
          sortOpen = false;
          persistView();
          draw();
        };
      });
      qsa("[data-emp]").forEach((control) => {
        control.onclick = () => {
          selected = control.dataset.emp;
          persistView();
          draw();
        };
      });
      qs("[data-search]").oninput = (event) => {
        searchRaw = event.target.value;
        searchTerm = searchRaw.trim().toLowerCase();
        filterOpen = false;
        sortOpen = false;
        persistView();
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
        ${isAdmin ? `<div class="mt-6 pt-4 border-t border-[#e7bdb9] grid sm:grid-cols-2 gap-4">
          <div>
            <p class="text-[11px] font-bold uppercase tracking-wider text-[#5d3f3d]">ZM career move</p>
            <p class="text-sm font-bold text-[#291716] mt-1">${esc(result.zm_career_recommendation_label || result.zm_career_recommendation || "—")}</p>
          </div>
          <div>
            <p class="text-[11px] font-bold uppercase tracking-wider text-[#5d3f3d]">RD career move</p>
            <p class="text-sm font-bold text-[#291716] mt-1">${esc(result.rd_career_recommendation_label || result.rd_career_recommendation || "—")}</p>
          </div>
        </div>` : ""}
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
      const sessions = result.sessions || [];
      const sessionBlock = sessions.length
        ? `<div class="grid md:grid-cols-2 gap-4 mt-6">${sessions.map((row) => {
          const scores = row.scores || {};
          const scoreLines = Object.keys(scores).length
            ? Object.entries(scores).map(([k, v]) => {
              if (v == null) return `<p class="text-sm text-slate-500"><strong>${esc(k)}:</strong> —</p>`;
              if (typeof v === "object") {
                const conf = Number(v.confidence);
                const confLabel = Number.isFinite(conf) ? ` · conf ${Math.round(conf * 100)}%` : "";
                return `<p class="text-sm text-slate-700"><strong>${esc(k)}:</strong> ${esc(v.level || "—")}<span class="text-slate-500">${esc(confLabel)}</span></p>`;
              }
              return `<p class="text-sm text-slate-700"><strong>${esc(k)}:</strong> ${esc(v)}</p>`;
            }).join("")
            : '<p class="text-sm text-slate-500">No scores yet.</p>';
          return `<article class="border border-slate-200 rounded-xl p-5 bg-slate-50">
            <div class="flex justify-between gap-3"><h3 class="font-bold">${esc(row.label || row.kind)}</h3>${statusChip(row.status)}</div>
            <div class="mt-3 space-y-1">${scoreLines}</div>
          </article>`;
        }).join("")}</div>`
        : "";
      const modal = document.createElement("div");
      modal.className = "fixed inset-0 z-[80] bg-slate-900/50 p-4 overflow-y-auto";
      modal.innerHTML = `<section class="bg-white rounded-xl p-6 max-w-5xl mx-auto my-6">
        <div class="flex justify-between gap-4 flex-wrap">
          <div>
            <h2 class="text-2xl font-bold">${esc(result.employee.name)} · Assessments</h2>
            <p class="text-sm text-slate-500">${esc(result.employee.employee_code)} · Admin-only scores (hidden from employee)</p>
          </div>
          <div class="flex items-start gap-2">
            ${(sessions.some((s) => s.status === "completed" || Object.keys(s.scores || {}).length) || (result.roleplays || []).some((r) => r.status === "completed"))
              ? button("Reset Assessments", `data-reset-assessments-modal="${esc(employeeCode)}"`, true)
              : ""}
            <button data-close class="material-symbols-outlined">close</button>
          </div>
        </div>
        <h3 class="font-bold text-lg mt-6">Voice sessions</h3>
        ${sessionBlock || '<p class="text-sm text-slate-500 mt-2">No voice sessions yet.</p>'}
        <div data-screenshot-preview class="hidden mt-6"></div>
        <h3 class="font-bold text-lg mt-8">Competency scores</h3>
        <div class="grid md:grid-cols-2 gap-4 mt-4">${result.roleplays.map((row) => `<article class="border border-slate-200 rounded-xl p-5">
          <div class="flex justify-between gap-3"><h3 class="font-bold">${esc(row.competency)}</h3>${statusChip(row.status)}</div>
          <p class="text-sm mt-3">Assessed level: <strong>${esc(row.ai_proficiency || "Pending")}</strong></p>
          <p class="text-sm text-slate-600 mt-2">${esc(row.rationale || "No assessed behavior available.")}</p>
          ${row.ocr_text ? `<details class="mt-3"><summary class="text-sm font-bold text-blue-700 cursor-pointer">Extracted behavior text</summary><p class="text-xs whitespace-pre-wrap mt-2 text-slate-600">${esc(row.ocr_text)}</p></details>` : ""}
          ${row.screenshot_available ? `<div class="mt-4">${button("View Screenshot", `data-view-screenshot="${esc(row.competency)}"`, true)}</div>` : ""}
        </article>`).join("")}</div>
      </section>`;
      document.body.appendChild(modal);
      qs("[data-close]", modal).onclick = () => modal.remove();
      const resetBtn = qs("[data-reset-assessments-modal]", modal);
      if (resetBtn) {
        resetBtn.onclick = async () => {
          if (!confirm("Reset this employee's BDM voice assessments? They can retake both sessions.")) return;
          try {
            await api("/api/admin/roleplays/reset", {
              method: "POST",
              body: JSON.stringify({ employee_code: employeeCode }),
            });
            toast("BDM assessments reset.");
            modal.remove();
            if (typeof initAdminEmployees === "function") await initAdminEmployees();
          } catch (error) {
            toast(error.message, "error");
          }
        };
      }
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
      "lteam/dashboard": initLteamDashboard,
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
