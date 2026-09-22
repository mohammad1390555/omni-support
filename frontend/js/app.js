// OmniSupport App State & Core Utilities
const API_BASE = window.location.origin;

const state = {
  activeTab: "tab-chat",
  currentUser: null,
  token: null,
  conversations: [],
  activeConversationId: null,
  activeConversation: null,
  aiSettings: null,
  sites: [],
  knowledgeItems: [],
  cannedResponses: [],
  users: [],
  agentSocket: null
};

// --- Auth Helper Headers ---
function getAuthHeaders() {
  const headers = { "Content-Type": "application/json" };
  const token = localStorage.getItem("omni_token");
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

// --- Toast Notifications ---
function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}</span>
    <span>${message}</span>
  `;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// --- Modals ---
function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add("open");
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove("open");
}

// --- Init Application ---
document.addEventListener("DOMContentLoaded", async () => {
  // Check auth user
  initAuthSession();

  const navItems = document.querySelectorAll(".sidebar-nav .nav-item[data-tab]");
  navItems.forEach(item => {
    item.addEventListener("click", () => {
      const targetTabId = item.getAttribute("data-tab");
      switchTab(targetTabId);
    });
  });

  // Logout listener
  const logoutBtn = document.getElementById("btn-logout");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", handleLogout);
  }

  // Init Modules
  initChatModule();
  initAnalyticsModule();
  initCannedModule();
  initTeamModule();
  initAISettingsModule();
  initKnowledgeModule();
  initSitesModule();
  initDocsModule();
});

// --- Auth & Role Management ---
function initAuthSession() {
  const storedUser = localStorage.getItem("omni_user");
  const storedToken = localStorage.getItem("omni_token");

  if (storedUser && storedToken) {
    try {
      state.currentUser = JSON.parse(storedUser);
      state.token = storedToken;
    } catch (e) {
      state.currentUser = { username: "admin", display_name: "مدیر ارشد", role: "admin" };
    }
  } else {
    // Default to demo admin for seamless preview
    state.currentUser = { username: "admin", display_name: "مدیر ارشد (Admin)", role: "admin" };
  }

  renderUserProfile();
}

function renderUserProfile() {
  const user = state.currentUser;
  if (!user) return;

  const nameEl = document.getElementById("sidebar-user-name");
  const roleEl = document.getElementById("sidebar-user-role");
  const avatarEl = document.getElementById("sidebar-user-avatar");
  const adminNavGroup = document.getElementById("admin-nav-group");

  if (nameEl) nameEl.textContent = user.display_name || user.username;
  
  if (roleEl) {
    if (user.role === "admin") {
      roleEl.textContent = "👑 مدیر ارشد (Admin)";
      roleEl.style.color = "#818cf8";
    } else {
      roleEl.textContent = "🎧 اپراتور پشتیبان (Member)";
      roleEl.style.color = "#34d399";
    }
  }

  if (avatarEl) {
    const initial = (user.display_name || user.username || "A").charAt(0).toUpperCase();
    avatarEl.querySelector("span").textContent = initial;
  }

  // Hide admin tabs if role is not admin!
  if (adminNavGroup) {
    if (user.role !== "admin") {
      adminNavGroup.style.display = "none";
    } else {
      adminNavGroup.style.display = "block";
    }
  }
}

function handleLogout() {
  if (confirm("آیا مایل به خروج از حساب کاربری هستید؟")) {
    localStorage.removeItem("omni_token");
    localStorage.removeItem("omni_user");
    window.location.href = "/login";
  }
}

function switchTab(tabId) {
  state.activeTab = tabId;

  document.querySelectorAll(".sidebar-nav .nav-item[data-tab]").forEach(el => {
    el.classList.toggle("active", el.getAttribute("data-tab") === tabId);
  });

  document.querySelectorAll(".content-tab").forEach(tab => {
    tab.classList.toggle("active", tab.id === tabId);
  });

  if (tabId === "tab-chat") {
    loadConversations();
  } else if (tabId === "tab-analytics") {
    loadAnalytics();
  } else if (tabId === "tab-canned") {
    loadCannedResponses();
  } else if (tabId === "tab-team") {
    loadTeamUsers();
  } else if (tabId === "tab-ai-settings") {
    loadAISettings();
    loadDecisionLogs();
  } else if (tabId === "tab-knowledge") {
    loadKnowledgeItems();
  } else if (tabId === "tab-sites") {
    loadSitesData();
  }
}

// --- Analytics Module ---
function initAnalyticsModule() {
  const refreshBtn = document.getElementById("btn-refresh-analytics");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", loadAnalytics);
  }
}

async function loadAnalytics() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/analytics/overview`);
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("kpi-ai-rate").textContent = `${data.ai_resolved_percent}%`;
    document.getElementById("kpi-total-convs").textContent = data.total_conversations;
    document.getElementById("kpi-pending-human").textContent = data.pending_human;
    document.getElementById("kpi-avg-latency").textContent = `${data.avg_latency_ms}ms`;

    const b = data.recent_decisions_breakdown || {};
    document.getElementById("count-auto-answer").textContent = b.AUTO_ANSWER || 0;
    document.getElementById("count-suggest").textContent = b.SUGGEST_TO_AGENT || 0;
    document.getElementById("count-transfer").textContent = b.TRANSFER_TO_HUMAN || 0;
  } catch (err) {
    console.error("Analytics load error:", err);
  }
}

// --- Canned Responses Module ---
function initCannedModule() {
  const openBtn = document.getElementById("btn-open-add-canned");
  if (openBtn) {
    openBtn.addEventListener("click", () => openModal("modal-add-canned"));
  }

  const form = document.getElementById("form-create-canned");
  if (form) {
    form.addEventListener("submit", submitCannedResponse);
  }

  loadCannedResponses();
}

async function loadCannedResponses() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/canned-responses`);
    if (!res.ok) return;
    const items = await res.json();
    state.cannedResponses = items;
    renderCannedGrid(items);
    renderChatQuickReplies(items);
  } catch (err) {
    console.error("Canned err:", err);
  }
}

function renderCannedGrid(items) {
  const container = document.getElementById("canned-grid-list");
  if (!container) return;

  if (items.length === 0) {
    container.innerHTML = `<div style="grid-column: span 3; text-align: center; color: var(--text-light); padding: 30px;">پاسخ آماده‌ای تعریف نشده است.</div>`;
    return;
  }

  container.innerHTML = items.map(i => `
    <div class="kb-card">
      <div class="kb-card-header">
        <h4 class="kb-card-title">${escapeHtml(i.title)}</h4>
        ${i.shortcut ? `<span class="kb-badge manual">${escapeHtml(i.shortcut)}</span>` : ''}
      </div>
      <div class="kb-card-content">${escapeHtml(i.content)}</div>
      <div class="kb-card-footer">
        <button class="chat-action-btn" style="padding: 2px 8px; font-size: 11px; color: var(--danger); border-color: #fecaca;" onclick="deleteCannedResponse('${i.id}')">حذف</button>
      </div>
    </div>
  `).join("");
}

function renderChatQuickReplies(items) {
  const container = document.getElementById("chat-quick-replies-list");
  if (!container) return;

  container.innerHTML = `
    <span style="font-size: 11px; color: var(--text-muted); align-self: center;">پاسخ‌های آماده:</span>
  ` + items.map(i => `
    <div class="quick-chip" onclick="insertQuickReply('${escapeQuote(i.content)}')">${escapeHtml(i.title)}</div>
  `).join("");
}

async function submitCannedResponse(e) {
  e.preventDefault();
  const title = document.getElementById("canned-title").value.trim();
  const shortcut = document.getElementById("canned-shortcut").value.trim();
  const content = document.getElementById("canned-content").value.trim();

  try {
    const res = await fetch(`${API_BASE}/api/v1/canned-responses`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, shortcut, content })
    });
    if (res.ok) {
      closeModal("modal-add-canned");
      document.getElementById("form-create-canned").reset();
      showToast("پاسخ آماده جدید ذخیره شد!", "success");
      loadCannedResponses();
    }
  } catch (err) {
    showToast("خطا در ذخیره پاسخ آماده.", "error");
  }
}

async function deleteCannedResponse(id) {
  if (!confirm("آیا از حذف این پاسخ آماده اطمینان دارید؟")) return;
  try {
    await fetch(`${API_BASE}/api/v1/canned-responses/${id}`, { method: "DELETE" });
    showToast("حذف شد.", "info");
    loadCannedResponses();
  } catch (err) {
    showToast("خطا در حذف.", "error");
  }
}

// --- Team & Users Management Module ---
function initTeamModule() {
  const openBtn = document.getElementById("btn-open-add-user");
  if (openBtn) {
    openBtn.addEventListener("click", () => openModal("modal-add-user"));
  }

  const form = document.getElementById("form-create-user");
  if (form) {
    form.addEventListener("submit", submitNewUser);
  }
}

async function loadTeamUsers() {
  const tbody = document.getElementById("team-users-tbody");
  if (!tbody) return;

  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/users`, {
      headers: getAuthHeaders()
    });
    if (!res.ok) {
      tbody.innerHTML = `<tr><td colspan="6" style="padding: 20px; text-align: center; color: var(--danger);">نیاز به دسترسی مدیر سیستم (Admin) است.</td></tr>`;
      return;
    }
    const users = await res.json();
    state.users = users;

    tbody.innerHTML = users.map(u => {
      const isSelf = state.currentUser && state.currentUser.username === u.username;
      const roleBadge = u.role === "admin" ? 
        '<span style="background: #e0e7ff; color: #4338ca; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 11px;">👑 مدیر ارشد (Admin)</span>' : 
        '<span style="background: #ecfdf5; color: #047857; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 11px;">🎧 اپراتور (Agent Member)</span>';

      const statusBadge = u.is_active ? 
        '<span style="color: #10b981; font-weight: 600;">● فعال</span>' : 
        '<span style="color: #ef4444; font-weight: 600;">● غیرفعال</span>';

      return `
        <tr style="border-bottom: 1px solid var(--border);">
          <td style="padding: 12px 14px; font-weight: 600;">${escapeHtml(u.display_name)} ${isSelf ? '<small style="color: var(--primary);">(شما)</small>' : ''}</td>
          <td style="padding: 12px 14px; font-family: monospace;">${escapeHtml(u.username)}</td>
          <td style="padding: 12px 14px; color: var(--text-muted);">${escapeHtml(u.email || '-')}</td>
          <td style="padding: 12px 14px;">${roleBadge}</td>
          <td style="padding: 12px 14px;">${statusBadge}</td>
          <td style="padding: 12px 14px;">
            ${!isSelf ? `<button class="chat-action-btn" style="padding: 2px 8px; font-size: 11px; color: var(--danger); border-color: #fecaca;" onclick="deleteTeamUser('${u.id}')">حذف</button>` : '-'}
          </td>
        </tr>
      `;
    }).join("");

  } catch (err) {
    console.error("Team load err:", err);
  }
}

async function submitNewUser(e) {
  e.preventDefault();
  const username = document.getElementById("new-user-username").value.trim();
  const display_name = document.getElementById("new-user-name").value.trim();
  const email = document.getElementById("new-user-email").value.trim();
  const role = document.getElementById("new-user-role").value;
  const password = document.getElementById("new-user-password").value;

  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/users`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ username, display_name, email, role, password })
    });

    if (res.ok) {
      closeModal("modal-add-user");
      document.getElementById("form-create-user").reset();
      showToast("عضو جدید تیم پشتیبانی با موفقیت اضافه شد!", "success");
      loadTeamUsers();
    } else {
      const err = await res.json();
      showToast(err.detail || "خطا در ایجاد کاربر.", "error");
    }
  } catch (err) {
    showToast("خطای ارتباط با سرور.", "error");
  }
}

async function deleteTeamUser(id) {
  if (!confirm("آیا از حذف این کاربر اطمینان دارید؟")) return;
  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/users/${id}`, {
      method: "DELETE",
      headers: getAuthHeaders()
    });
    if (res.ok) {
      showToast("عضو تیم با موفقیت حذف گردید.", "info");
      loadTeamUsers();
    }
  } catch (err) {
    showToast("خطا در حذف کاربر.", "error");
  }
}

async function copySnippet(elementId) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const text = el.innerText || el.textContent;
  try {
    await navigator.clipboard.writeText(text);
    showToast("کد با موفقیت کپی شد!", "success");
  } catch (err) {
    showToast("خطا در کپی کردن متن.", "error");
  }
}
