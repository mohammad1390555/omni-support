/**
 * OmniSupport Enterprise Helpdesk & Live Chat Client (Frappe / Linear Style)
 */

let currentConversation = null;
let conversationsList = [];
let agentsList = [];
let currentUser = null;
let activeFilter = 'all';
let isInternalComposerMode = false;
let agentSocket = null;

document.addEventListener("DOMContentLoaded", async () => {
  // Check auth
  await initAuth();

  // Bind navigation
  initNavigation();

  // Initialize features
  initTicketFilters();
  initComposer();
  initTicketActions();
  initCannedResponses();
  initKnowledgeBase();
  initAISettings();
  initTeamManagement();
  initWebSockets();

  // Initial data load
  await loadAgents();
  await loadConversations();
  await loadAnalytics();
});

// --- Auth & Session ---
async function initAuth() {
  const token = localStorage.getItem("omni_token") || localStorage.getItem("token");
  const storedUser = localStorage.getItem("omni_user") || localStorage.getItem("user");

  if (!token) {
    window.location.href = "/login";
    return;
  }

  try {
    currentUser = storedUser ? JSON.parse(storedUser) : null;
    if (!currentUser) {
      const res = await fetch("/api/v1/auth/me", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        currentUser = await res.json();
        localStorage.setItem("user", JSON.stringify(currentUser));
      } else {
        localStorage.clear();
        window.location.href = "/login";
        return;
      }
    }

    // Render User Info in sidebar
    document.getElementById("current-agent-name").textContent = currentUser.display_name || currentUser.username;
    document.getElementById("current-agent-role").textContent = 
      currentUser.role === "admin" ? "مدیر ارشد سیستم (Admin)" : "کارشناس پشتیبانی (Agent)";
    document.getElementById("current-agent-avatar").querySelector("span").textContent = 
      (currentUser.display_name || currentUser.username).charAt(0);

    // Role-based visibility
    if (currentUser.role !== "admin") {
      const adminTabs = ["nav-analytics", "nav-ai-settings", "nav-team"];
      adminTabs.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.style.display = "none";
      });
    }

    document.getElementById("btn-logout").addEventListener("click", () => {
      localStorage.clear();
      window.location.href = "/login";
    });

  } catch (err) {
    console.error("Auth init error:", err);
  }
}

// --- Navigation Tabs ---
function initNavigation() {
  const navItems = document.querySelectorAll(".sidebar-nav .nav-item[data-tab]");
  const contentTabs = document.querySelectorAll(".content-tab");

  navItems.forEach(item => {
    item.addEventListener("click", (e) => {
      e.preventDefault();
      const tabId = item.getAttribute("data-tab");

      navItems.forEach(n => n.classList.remove("active"));
      contentTabs.forEach(t => t.classList.remove("active"));

      item.classList.add("active");
      const target = document.getElementById(`tab-${tabId}`);
      if (target) target.classList.add("active");

      // Auto refresh on tab activation
      if (tabId === "analytics") loadAnalytics();
      if (tabId === "canned") loadCannedList();
      if (tabId === "knowledge") loadKnowledgeList();
      if (tabId === "team") loadTeamList();
    });
  });
}

// --- Helpdesk Tickets List & Filters ---
function initTicketFilters() {
  const filterTabs = document.querySelectorAll(".filter-tab");
  filterTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      filterTabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      activeFilter = tab.getAttribute("data-filter");
      renderConversationsList();
    });
  });

  const searchInput = document.getElementById("conv-search-input");
  searchInput.addEventListener("input", () => {
    renderConversationsList();
  });
}

async function loadAgents() {
  try {
    const token = localStorage.getItem("omni_token") || localStorage.getItem("token");
    const res = await fetch("/api/v1/auth/users", {
      headers: { "Authorization": `Bearer ${token}` }
    });
    if (res.ok) {
      agentsList = await res.json();
      const select = document.getElementById("select-ticket-agent");
      select.innerHTML = '<option value="">بدون مسئول (تخصیص نیافته)</option>' +
        agentsList.map(a => `<option value="${a.id}">${a.display_name} (${a.role})</option>`).join("");
    }
  } catch (err) {
    console.warn("Failed to load agents list:", err);
  }
}

async function loadConversations() {
  try {
    const res = await fetch("/api/v1/chat/conversations");
    if (res.ok) {
      conversationsList = await res.json();
      updateBadgeCounts();
      renderConversationsList();
      if (!currentConversation && conversationsList.length > 0) {
        selectConversation(conversationsList[0].id);
      }
    }
  } catch (err) {
    console.error("Load conversations error:", err);
  }
}

function updateBadgeCounts() {
  const openCount = conversationsList.filter(c => c.status === "open" || c.status === "in_progress").length;
  const badge = document.getElementById("open-tickets-badge");
  if (badge) badge.textContent = openCount;

  const totalCount = document.getElementById("total-tickets-count");
  if (totalCount) totalCount.textContent = `${conversationsList.length} تیکت`;
}

function renderConversationsList() {
  const container = document.getElementById("conv-items-container");
  const searchQuery = (document.getElementById("conv-search-input").value || "").trim().toLowerCase();

  let filtered = conversationsList.filter(c => {
    // 1. Tab Filter
    if (activeFilter === "mine") {
      if (c.assigned_agent_id !== (currentUser ? currentUser.id : null)) return false;
    } else if (activeFilter === "unassigned") {
      if (c.assigned_agent_id) return false;
    } else if (activeFilter === "urgent") {
      if (c.priority !== "urgent") return false;
    } else if (activeFilter === "resolved") {
      if (c.status !== "resolved" && c.status !== "closed") return false;
    }

    // 2. Search Query
    if (searchQuery) {
      const matchNumber = (c.ticket_number || "").toLowerCase().includes(searchQuery);
      const matchSubject = (c.subject || "").toLowerCase().includes(searchQuery);
      const matchCustomer = (c.customer_name || "").toLowerCase().includes(searchQuery);
      const matchEmail = (c.customer_email || "").toLowerCase().includes(searchQuery);
      if (!matchNumber && !matchSubject && !matchCustomer && !matchEmail) return false;
    }

    return true;
  });

  if (filtered.length ==== ) {
    container.innerHTML = `
      <div style="padding: 32px 16px; text-align: center; color: #94a3b8; font-size: 13px;">
        تیکتی در این دسته‌بندی یافت نشد.
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map(c => {
    const isActive = currentConversation && currentConversation.id === c.id;
    const lastMsg = (c.messages && c.messages.length > 0) ? c.messages[c.messages.length - 1].content : "بدون پیام";
    const timeFormatted = new Date(c.last_message_at || c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    // Priority badge
    const prioLabel = c.priority === "urgent" ? "بحرانی 🔥" :
                      c.priority === "high" ? "اولویت بالا" :
                      c.priority === "low" ? "اولویت کم" : "متوسط";

    // Status label
    const statusLabel = c.status === "open" ? "باز" :
                        c.status === "in_progress" ? "در حال بررسی" :
                        c.status === "pending_customer" ? "در انتظار مشتری" :
                        c.status === "resolved" ? "حل‌شده" : "بسته";

    return `
      <div class="ticket-item ${isActive ? 'active' : ''}" data-id="${c.id}">
        <div class="ticket-item-top">
          <span class="ticket-code">${c.ticket_number || 'HD-1000'}</span>
          <span class="ticket-time">${timeFormatted}</span>
        </div>
        <div class="ticket-subject">${c.subject || 'درخواست جدید'}</div>
        <div class="ticket-preview">${c.customer_name}: ${lastMsg}</div>
        <div class="ticket-badges-row">
          <span class="status-pill ${c.status}">${statusLabel}</span>
          <span class="prio-pill ${c.priority}">${prioLabel}</span>
          ${c.sentiment === 'frustrated' ? '<span class="sentiment-badge frustrated">⚠️ شاکی</span>' : ''}
          ${c.assigned_agent_name ? `<span style="font-size: 10.5px; color: #475569;">👤 ${c.assigned_agent_name.split(" ")[0]}</span>` : '<span style="font-size: 10.5px; color: #94a3b8;">(بدون مسئول)</span>'}
        </div>
      </div>
    `;
  }).join("");

  container.querySelectorAll(".ticket-item").forEach(item => {
    item.addEventListener("click", () => {
      const convId = item.getAttribute("data-id");
      selectConversation(convId);
    });
  });
}

// --- Select and View Ticket ---
async function selectConversation(convId) {
  try {
    const res = await fetch(`/api/v1/chat/conversations/${convId}`);
    if (!res.ok) return;

    currentConversation = await res.json();
    renderConversationsList(); // refresh active highlight

    // Header updates
    document.getElementById("active-ticket-code").textContent = currentConversation.ticket_number || "HD-1001";
    document.getElementById("active-ticket-subject").textContent = currentConversation.subject || "درخواست پشتیبانی";
    document.getElementById("active-customer-name").textContent = currentConversation.customer_name || "کاربر مهمان";
    
    // Select dropdowns
    document.getElementById("select-ticket-priority").value = currentConversation.priority || "medium";
    document.getElementById("select-ticket-status").value = currentConversation.status || "open";
    document.getElementById("select-ticket-agent").value = currentConversation.assigned_agent_id || "";

    // SLA display
    const slaEl = document.getElementById("active-sla-status");
    if (currentConversation.priority === "urgent") {
      slaEl.textContent = "مهلت SLA: ۲ ساعت (بحرانی)";
      slaEl.style.color = "#ef4444";
    } else {
      slaEl.textContent = "مهلت SLA: استاندارد (۸ ساعت)";
      slaEl.style.color = "#6366f1";
    }

    // Render Feed (Messages + Timeline)
    renderTicketFeed();

    // Render Inspector Sidebar
    renderInspector();

  } catch (err) {
    console.error("Select conversation error:", err);
  }
}

function renderTicketFeed() {
  const feed = document.getElementById("ticket-feed");
  if (!currentConversation) {
    feed.innerHTML = "";
    return;
  }

  const items = [];

  // 1. Add Messages
  if (currentConversation.messages) {
    currentConversation.messages.forEach(m => {
      items.push({
        type: "message",
        date: new Date(m.created_at),
        data: m
      });
    });
  }

  // 2. Add Activities
  if (currentConversation.activities) {
    currentConversation.activities.forEach(a => {
      items.push({
        type: "activity",
        date: new Date(a.created_at),
        data: a
      });
    });
  }

  // Sort chronologically
  items.sort((a, b) => a.date - b.date);

  feed.innerHTML = items.map(item => {
    if (item.type === "activity") {
      return `
        <div class="timeline-event-row">
          <span>⚙️ ${item.data.details} (${item.date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})</span>
        </div>
      `;
    }

    const m = item.data;
    const isCustomer = m.sender_type === "customer";
    const isAi = m.sender_type === "ai";
    const isInternal = m.is_internal;
    const senderRole = isInternal ? "internal" : isCustomer ? "customer" : isAi ? "ai" : "agent";
    const timeStr = item.date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    return `
      <div class="agent-msg-row ${senderRole}">
        <div class="agent-msg-bubble">
          ${isInternal ? '<div style="font-weight: 700; margin-bottom: 4px; display: flex; align-items: center; gap: 4px;">🔒 یادداشت محرمانه داخلی کارشناسان</div>' : ''}
          <div>${escapeHtml(m.content)}</div>
          <div style="font-size: 10.5px; opacity: 0.75; margin-top: 4px; display: flex; justify-content: space-between;">
            <span>${m.sender_name}</span>
            <span>${timeStr}</span>
          </div>
        </div>
      </div>
    `;
  }).join("");

  feed.scrollTop = feed.scrollHeight;
}

function renderInspector() {
  if (!currentConversation) return;

  const c = currentConversation;
  
  // AI section
  const sentEl = document.getElementById("inspect-sentiment");
  sentEl.className = `sentiment-badge ${c.sentiment}`;
  sentEl.textContent = c.sentiment === "frustrated" ? "ناراضی / عصبانی ⚠️" :
                       c.sentiment === "positive" ? "بسیار راضی 🌟" : "عادی / خنثی";

  document.getElementById("inspect-ai-summary").textContent = 
    c.ai_summary || "هنوز خلاصه‌ای ثبت نشده است. روی دکمه 'خلاصه هوشمند' کلیک کنید.";

  // Ticket info
  document.getElementById("inspect-ticket-num").textContent = c.ticket_number || "HD-1001";
  document.getElementById("inspect-status").textContent = c.status;
  document.getElementById("inspect-priority").textContent = c.priority;
  document.getElementById("inspect-agent-name").textContent = c.assigned_agent_name || "تخصیص نیافته";
  document.getElementById("inspect-created-at").textContent = new Date(c.created_at).toLocaleString("fa-IR");

  // Customer info
  document.getElementById("inspect-customer-name").textContent = c.customer_name;
  document.getElementById("inspect-customer-email").textContent = c.customer_email || "-";
  document.getElementById("inspect-customer-phone").textContent = c.customer_phone || "-";
  document.getElementById("inspect-customer-page").textContent = c.current_page || "/";
  document.getElementById("inspect-customer-device").textContent = c.customer_device || "مرورگر وب";
}

// --- Ticket Actions: Assign, Status, Priority, Summarize ---
function initTicketActions() {
  // 1. Assign Agent
  const selectAgent = document.getElementById("select-ticket-agent");
  selectAgent.addEventListener("change", async () => {
    if (!currentConversation) return;
    const agentId = selectAgent.value;
    if (!agentId) return;

    try {
      const res = await fetch(`/api/v1/chat/conversations/${currentConversation.id}/assign`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent_id: agentId })
      });
      if (res.ok) {
        showToast("تیکت با موفقیت به کارشناس واگذار شد.", "success");
        await selectConversation(currentConversation.id);
        await loadConversations();
      }
    } catch (err) {
      showToast("خطا در واگذاری تیکت: " + err.message, "error");
    }
  });

  // 2. Change Status
  const selectStatus = document.getElementById("select-ticket-status");
  selectStatus.addEventListener("change", async () => {
    if (!currentConversation) return;
    const newStatus = selectStatus.value;

    try {
      const res = await fetch(`/api/v1/chat/conversations/${currentConversation.id}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus })
      });
      if (res.ok) {
        showToast(`وضعیت تیکت به ${newStatus} تغییر یافت.`, "info");
        await selectConversation(currentConversation.id);
        await loadConversations();
      }
    } catch (err) {
      showToast("خطا در تغییر وضعیت: " + err.message, "error");
    }
  });

  // 3. Change Priority
  const selectPriority = document.getElementById("select-ticket-priority");
  selectPriority.addEventListener("change", async () => {
    if (!currentConversation) return;
    const newPrio = selectPriority.value;

    try {
      const res = await fetch(`/api/v1/chat/conversations/${currentConversation.id}/priority`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ priority: newPrio })
      });
      if (res.ok) {
        showToast(`اولویت تیکت تغییر یافت.`, "info");
        await selectConversation(currentConversation.id);
        await loadConversations();
      }
    } catch (err) {
      showToast("خطا در تغییر اولویت: " + err.message, "error");
    }
  });

  // 4. AI Executive Summarize Button
  document.getElementById("btn-ai-summarize").addEventListener("click", async () => {
    if (!currentConversation) return;
    const btn = document.getElementById("btn-ai-summarize");
    btn.textContent = "⏳ در حال تولید خلاصه...";
    btn.disabled = true;

    try {
      const res = await fetch(`/api/v1/chat/conversations/${currentConversation.id}/ai-summarize`, {
        method: "POST"
      });
      if (res.ok) {
        const data = await res.json();
        currentConversation.ai_summary = data.summary;
        document.getElementById("inspect-ai-summary").textContent = data.summary;
        showToast("خلاصه هوشمند با موفقیت تولید شد!", "success");
      }
    } catch (err) {
      showToast("خطا در تولید خلاصه: " + err.message, "error");
    } finally {
      btn.textContent = "🤖 خلاصه هوشمند";
      btn.disabled = false;
    }
  });

  // 5. Learn from Agent response button
  document.getElementById("btn-learn-from-this-ticket").addEventListener("click", async () => {
    if (!currentConversation || !currentConversation.messages || currentConversation.messages.length ==== ) {
      showToast("پیامی برای یادگیری وجود ندارد.", "info");
      return;
    }

    const lastCust = [...currentConversation.messages].reverse().find(m => m.sender_type === "customer");
    const lastAgent = [...currentConversation.messages].reverse().find(m => m.sender_type === "agent" && !m.is_internal);

    if (!lastCust || !lastAgent) {
      showToast("مکالمه باید شامل حداقل یک پیام مشتری و یک پاسخ کارشناس باشد.", "info");
      return;
    }

    try {
      const res = await fetch(`/api/v1/chat/conversations/${currentConversation.id}/learn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversation_id: currentConversation.id,
          customer_question: lastCust.content,
          agent_answer: lastAgent.content,
          title: `پاسخ به: ${lastCust.content.slice(0, 40)}...`,
          category: "agent_learned"
        })
      });
      if (res.ok) {
        showToast("پاسخ شما در پایگاه یادگیری هوش مصنوعی ذخیره شد!", "success");
        await selectConversation(currentConversation.id);
      }
    } catch (err) {
      showToast("خطا در ذخیره یادگیری: " + err.message, "error");
    }
  });
}

// --- Composer: Public Reply vs Internal Note ---
function initComposer() {
  const publicTab = document.getElementById("tab-btn-public");
  const internalTab = document.getElementById("tab-btn-internal");
  const textarea = document.getElementById("agent-reply-input");
  const sendBtn = document.getElementById("btn-send-agent-reply");
  const hint = document.getElementById("composer-hint");

  publicTab.addEventListener("click", () => {
    isInternalComposerMode = false;
    publicTab.classList.add("active");
    internalTab.classList.remove("active");
    textarea.classList.remove("internal-mode");
    textarea.placeholder = "متن پیام خود را بنویسید (برای ارسال Ctrl+Enter بزنید)...";
    sendBtn.classList.remove("internal-send");
    sendBtn.querySelector("span").textContent = "ارسال پاسخ به کاربر";
    hint.textContent = "پیام شما به عنوان پاسخ رسمی برای کاربر ارسال می‌شود.";
  });

  internalTab.addEventListener("click", () => {
    isInternalComposerMode = true;
    internalTab.classList.add("active");
    publicTab.classList.remove("active");
    textarea.classList.add("internal-mode");
    textarea.placeholder = "یادداشت محرمانه داخلی (فقط برای اعضای تیم و مدیران قابل مشاهده است)...";
    sendBtn.classList.add("internal-send");
    sendBtn.querySelector("span").textContent = "ثبت یادداشت داخلی";
    hint.textContent = "این یادداشت برای کاربر نمایش داده نمی‌شود و فقط درون پنل ذخیره می‌گردد.";
  });

  sendBtn.addEventListener("click", sendComposerMessage);
  textarea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      sendComposerMessage();
    }
  });

  // Quick Chips
  document.querySelectorAll(".quick-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const text = chip.getAttribute("data-text");
      textarea.value = text;
      textarea.focus();
    });
  });
}

async function sendComposerMessage() {
  if (!currentConversation) {
    showToast("لطفاً ابتدا یک تیکت را انتخاب کنید.", "info");
    return;
  }

  const textarea = document.getElementById("agent-reply-input");
  const content = textarea.value.trim();
  if (!content) return;

  const btn = document.getElementById("btn-send-agent-reply");
  btn.disabled = true;

  try {
    let url = `/api/v1/chat/conversations/${currentConversation.id}/messages`;
    let body = {
      content: content,
      sender_type: "agent",
      sender_name: currentUser ? currentUser.display_name : "کارشناس پشتیبانی",
      is_internal: isInternalComposerMode
    };

    if (isInternalComposerMode) {
      url = `/api/v1/chat/conversations/${currentConversation.id}/notes`;
      body = { content: content };
    }

    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });

    if (res.ok) {
      textarea.value = "";
      await selectConversation(currentConversation.id);
      await loadConversations();
    }
  } catch (err) {
    showToast("خطا در ارسال: " + err.message, "error");
  } finally {
    btn.disabled = false;
  }
}

// --- WebSocket Live Agent Stream ---
function initWebSockets() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/api/v1/chat/ws/agent`;

  try {
    agentSocket = new WebSocket(wsUrl);

    agentSocket.onopen = () => {
      // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // // console.log("WebSocket connected to agent channel.");
    };

    agentSocket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        const { event: evtType, data } = payload;

        if (evtType === "new_conversation") {
          loadConversations();
          showToast(`تیکت جدید: ${data.ticket_number || ''} از ${data.customer_name}`, "info");
        } else if (evtType === "new_message") {
          if (currentConversation && currentConversation.id === data.conversation_id) {
            selectConversation(currentConversation.id);
          } else {
            loadConversations();
          }
        } else if (evtType === "ticket_updated") {
          if (currentConversation && currentConversation.id === data.id) {
            selectConversation(currentConversation.id);
          }
          loadConversations();
        } else if (evtType === "ai_decision") {
          if (currentConversation && currentConversation.id === data.conversation_id) {
            document.getElementById("inspect-decision").textContent = data.action;
            document.getElementById("inspect-confidence").textContent = `${Math.round(data.confidence * 100)}%`;
          }
        }
      } catch (e) {
        console.error("WS Parse error:", e);
      }
    };

    agentSocket.onclose = () => {
      setTimeout(initWebSockets, 3000);
    };
  } catch (err) {
    console.warn("WebSocket init error:", err);
  }
}

// --- Analytics & SLA ---
async function loadAnalytics() {
  try {
    const res = await fetch("/api/v1/analytics/overview");
    if (!res.ok) return;

    const data = await res.json();
    document.getElementById("stat-total-convs").textContent = data.total_conversations;
    document.getElementById("stat-open-tickets").textContent = data.open_tickets + data.in_progress_tickets;
    document.getElementById("stat-ai-resolved").textContent = `${data.ai_resolved_percent}%`;
    document.getElementById("stat-avg-latency").textContent = `${data.avg_latency_ms} ms`;

    // TypeSafe breakdown
    const b = data.recent_decisions_breakdown || {};
    document.getElementById("stat-action-auto").textContent = b.AUTO_ANSWER || 0;
    document.getElementById("stat-action-suggest").textContent = b.SUGGEST_TO_AGENT || 0;
    document.getElementById("stat-action-transfer").textContent = b.TRANSFER_TO_HUMAN || 0;
    document.getElementById("stat-action-clarify").textContent = b.CLARIFY || 0;

  } catch (err) {
    console.warn("Failed to load analytics:", err);
  }
}

// --- Canned Responses ---
function initCannedResponses() {
  document.getElementById("btn-open-create-canned").addEventListener("click", () => {
    openModal("modal-add-canned");
  });

  document.getElementById("form-create-canned").addEventListener("submit", async (e) => {
    e.preventDefault();
    const title = document.getElementById("canned-input-title").value.trim();
    const shortcut = document.getElementById("canned-input-shortcut").value.trim();
    const content = document.getElementById("canned-input-content").value.trim();

    try {
      const res = await fetch("/api/v1/canned", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, shortcut, content })
      });
      if (res.ok) {
        closeModal("modal-add-canned");
        document.getElementById("form-create-canned").reset();
        showToast("پاسخ آماده ذخیره شد.", "success");
        loadCannedList();
      }
    } catch (err) {
      showToast("خطا در ذخیره پاسخ آماده: " + err.message, "error");
    }
  });
}

async function loadCannedList() {
  const container = document.getElementById("canned-responses-grid");
  try {
    const res = await fetch("/api/v1/canned");
    if (!res.ok) return;
    const items = await res.json();

    container.innerHTML = items.map(c => `
      <div class="kb-card">
        <div class="kb-card-header">
          <span class="kb-card-title">${escapeHtml(c.title)}</span>
          <span class="kb-badge manual">${escapeHtml(c.shortcut || '/')}</span>
        </div>
        <div class="kb-card-content">${escapeHtml(c.content)}</div>
      </div>
    `).join("");
  } catch (err) {
    console.warn("Load canned error:", err);
  }
}

// --- Knowledge Base ---
function initKnowledgeBase() {
  document.getElementById("btn-open-add-kb").addEventListener("click", () => {
    openModal("modal-add-kb");
  });

  document.getElementById("form-create-kb").addEventListener("submit", async (e) => {
    e.preventDefault();
    const title = document.getElementById("kb-input-title").value.trim();
    const content = document.getElementById("kb-input-content").value.trim();
    const category = document.getElementById("kb-input-category").value;

    try {
      const res = await fetch("/api/v1/knowledge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, content, category, source: "manual" })
      });
      if (res.ok) {
        closeModal("modal-add-kb");
        document.getElementById("form-create-kb").reset();
        showToast("دانش جدید با موفقیت ذخیره شد.", "success");
        loadKnowledgeList();
      }
    } catch (err) {
      showToast("خطا در ایجاد دانش: " + err.message, "error");
    }
  });
}

async function loadKnowledgeList() {
  const container = document.getElementById("kb-items-grid");
  try {
    const res = await fetch("/api/v1/knowledge");
    if (!res.ok) return;
    const items = await res.json();

    container.innerHTML = items.map(item => `
      <div class="kb-card">
        <div class="kb-card-header">
          <span class="kb-card-title">${escapeHtml(item.title)}</span>
          <span class="kb-badge ${item.source === 'agent_learned' ? 'learned' : 'manual'}">
            ${item.source === 'agent_learned' ? 'یادگیری از کارشناس' : 'دستی'}
          </span>
        </div>
        <div class="kb-card-content">${escapeHtml(item.content)}</div>
        <div class="kb-card-footer">
          <span>دسته: ${item.category}</span>
          <span>استفاده: ${item.usage_count} بار</span>
        </div>
      </div>
    `).join("");
  } catch (err) {
    console.warn("Load KB error:", err);
  }
}

// --- AI Settings ---
function initAISettings() {
  loadAISettings();

  // Presets
  const presetCards = document.querySelectorAll(".preset-card");
  presetCards.forEach(card => {
    card.addEventListener("click", () => {
      presetCards.forEach(c => c.classList.remove("active"));
      card.classList.add("active");
      const preset = card.getAttribute("data-preset");

      if (preset === "openai") {
        document.getElementById("ai-provider-name").value = "OpenAI";
        document.getElementById("ai-base-url").value = "https://api.openai.com/v1";
        document.getElementById("ai-model-name").value = "gpt-4o-mini";
      } else if (preset === "openrouter") {
        document.getElementById("ai-provider-name").value = "OpenRouter";
        document.getElementById("ai-base-url").value = "https://openrouter.ai/api/v1";
        document.getElementById("ai-model-name").value = "meta-llama/llama-3.3-70b-instruct";
      } else if (preset === "groq") {
        document.getElementById("ai-provider-name").value = "Groq Fast";
        document.getElementById("ai-base-url").value = "https://api.groq.com/openai/v1";
        document.getElementById("ai-model-name").value = "llama-3.3-70b-versatile";
      } else if (preset === "ollama") {
        document.getElementById("ai-provider-name").value = "Ollama Local";
        document.getElementById("ai-base-url").value = "http://localhost:11434/v1";
        document.getElementById("ai-model-name").value = "llama3.2";
      }
    });
  });

  // Test AI Connection
  document.getElementById("btn-test-ai-connection").addEventListener("click", async () => {
    const baseUrl = document.getElementById("ai-base-url").value.trim();
    const apiKey = document.getElementById("ai-api-key").value.trim();
    const modelName = document.getElementById("ai-model-name").value.trim();
    const btn = document.getElementById("btn-test-ai-connection");

    btn.textContent = "در حال تست...";
    btn.disabled = true;

    try {
      const res = await fetch("/api/v1/ai/test-provider", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ base_url: baseUrl, api_key: apiKey, model_name: modelName })
      });
      const data = await res.json();
      if (res.ok && data.success) {
        showToast(`اتصال برقرار شد! پاسخ در ${data.latency_ms}ms`, "success");
      } else {
        showToast("اتصال برقرار نشد: " + (data.message || "خطای نامشخص"), "error");
      }
    } catch (err) {
      showToast("خطای شبکه در تست اتصال: " + err.message, "error");
    } finally {
      btn.textContent = "تست اتصال به ارائه‌دهنده";
      btn.disabled = false;
    }
  });

  // Save AI Settings
  document.getElementById("ai-settings-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      provider_name: document.getElementById("ai-provider-name").value.trim(),
      base_url: document.getElementById("ai-base-url").value.trim(),
      api_key: document.getElementById("ai-api-key").value.trim() || undefined,
      model_name: document.getElementById("ai-model-name").value.trim(),
      system_prompt: document.getElementById("ai-system-prompt").value.trim(),
      enable_typesafe_decision: document.getElementById("ai-toggle-typesafe").checked,
      enable_agent_learning: document.getElementById("ai-toggle-learning").checked
    };

    try {
      const res = await fetch("/api/v1/ai/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        showToast("تنظیمات هوش مصنوعی با موفقیت بروزرسانی شد.", "success");
      }
    } catch (err) {
      showToast("خطا در ذخیره تنظیمات: " + err.message, "error");
    }
  });
}

async function loadAISettings() {
  try {
    const res = await fetch("/api/v1/ai/settings");
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("ai-provider-name").value = data.provider_name || "";
    document.getElementById("ai-base-url").value = data.base_url || "";
    document.getElementById("ai-model-name").value = data.model_name || "";
    document.getElementById("ai-system-prompt").value = data.system_prompt || "";
    document.getElementById("ai-toggle-typesafe").checked = data.enable_typesafe_decision;
    document.getElementById("ai-toggle-learning").checked = data.enable_agent_learning;
  } catch (err) {
    console.warn("Load AI settings error:", err);
  }
}

// --- Team Management ---
function initTeamManagement() {
  document.getElementById("btn-open-create-agent").addEventListener("click", () => {
    openModal("modal-add-agent");
  });

  document.getElementById("form-create-agent").addEventListener("submit", async (e) => {
    e.preventDefault();
    const token = localStorage.getItem("omni_token") || localStorage.getItem("token");
    const display_name = document.getElementById("agent-input-name").value.trim();
    const username = document.getElementById("agent-input-username").value.trim();
    const password = document.getElementById("agent-input-password").value.trim();
    const role = document.getElementById("agent-input-role").value;

    try {
      const res = await fetch("/api/v1/auth/users", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ display_name, username, password, role })
      });
      if (res.ok) {
        closeModal("modal-add-agent");
        document.getElementById("form-create-agent").reset();
        showToast("کارشناس جدید ایجاد شد.", "success");
        loadTeamList();
        loadAgents();
      } else {
        const err = await res.json();
        showToast("خطا: " + (err.detail || "عدم دسترسی"), "error");
      }
    } catch (err) {
      showToast("خطا در ایجاد کاربر: " + err.message, "error");
    }
  });
}

async function loadTeamList() {
  const tbody = document.getElementById("team-table-body");
  const token = localStorage.getItem("omni_token") || localStorage.getItem("token");

  try {
    const res = await fetch("/api/v1/auth/users", {
      headers: { "Authorization": `Bearer ${token}` }
    });
    if (!res.ok) return;
    const users = await res.json();

    tbody.innerHTML = users.map(u => `
      <tr style="border-bottom: 1px solid var(--border);">
        <td style="padding: 12px 10px; font-weight: 700;">${escapeHtml(u.display_name)}</td>
        <td style="padding: 12px 10px; font-family: monospace;">${escapeHtml(u.username)}</td>
        <td style="padding: 12px 10px; color: var(--text-muted);">${escapeHtml(u.email || '-')}</td>
        <td style="padding: 12px 10px;">
          <span class="status-pill ${u.role === 'admin' ? 'resolved' : 'open'}">
            ${u.role === 'admin' ? 'مدیر سیستم' : 'کارشناس پشتیبانی'}
          </span>
        </td>
        <td style="padding: 12px 10px;">
          <span style="color: ${u.is_active ? 'var(--success)' : 'var(--danger)'};">● ${u.is_active ? 'فعال' : 'غیرفعال'}</span>
        </td>
      </tr>
    `).join("");
  } catch (err) {
    console.warn("Load team error:", err);
  }
}

// --- Helpers & Modals ---
function openModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.add("open");
}

function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.remove("open");
}

document.querySelectorAll("[data-close]").forEach(btn => {
  btn.addEventListener("click", () => {
    closeModal(btn.getAttribute("data-close"));
  });
});

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4000);
}

function escapeHtml(text) {
  if (!text) return "";
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
