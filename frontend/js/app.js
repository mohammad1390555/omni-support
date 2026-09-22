// OmniSupport App State & Core Utilities
const API_BASE = window.location.origin;

const state = {
  activeTab: "tab-chat",
  conversations: [],
  activeConversationId: null,
  activeConversation: null,
  aiSettings: null,
  sites: [],
  knowledgeItems: [],
  agentSocket: null
};

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

// --- Tab Navigation ---
document.addEventListener("DOMContentLoaded", () => {
  const navItems = document.querySelectorAll(".sidebar-nav .nav-item[data-tab]");
  navItems.forEach(item => {
    item.addEventListener("click", () => {
      const targetTabId = item.getAttribute("data-tab");
      switchTab(targetTabId);
    });
  });

  // Init sections
  initChatModule();
  initAISettingsModule();
  initKnowledgeModule();
  initSitesModule();
  initDocsModule();
});

function switchTab(tabId) {
  state.activeTab = tabId;

  // Update nav UI
  document.querySelectorAll(".sidebar-nav .nav-item[data-tab]").forEach(el => {
    el.classList.toggle("active", el.getAttribute("data-tab") === tabId);
  });

  // Update tab content panes
  document.querySelectorAll(".content-tab").forEach(tab => {
    tab.classList.toggle("active", tab.id === tabId);
  });

  // Tab specific refreshes
  if (tabId === "tab-chat") {
    loadConversations();
  } else if (tabId === "tab-ai-settings") {
    loadAISettings();
    loadDecisionLogs();
  } else if (tabId === "tab-knowledge") {
    loadKnowledgeItems();
  } else if (tabId === "tab-sites") {
    loadSitesData();
  }
}

// Utility: Copy text to clipboard
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
