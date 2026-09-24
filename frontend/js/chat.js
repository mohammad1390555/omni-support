// Live Chat & Agent Inbox Module
let currentFilter = "all";

function initChatModule() {
  // Filter tabs
  const filterTabs = document.querySelectorAll(".conv-filter-tabs .filter-tab");
  filterTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      filterTabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      currentFilter = tab.getAttribute("data-filter");
      renderConversationList();
    });
  });

  // Search input
  const searchInput = document.getElementById("conv-search");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      renderConversationList(e.target.value.trim());
    });
  }

  // Refresh button
  const refreshBtn = document.getElementById("btn-refresh-convs");
  if (refreshBtn) {
    refreshBtn.addEventListener("click", () => loadConversations());
  }

  // Agent send message
  const sendBtn = document.getElementById("btn-agent-send");
  const msgInput = document.getElementById("agent-msg-input");

  if (sendBtn && msgInput) {
    sendBtn.addEventListener("click", sendAgentMessage);
    msgInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendAgentMessage();
      }
    });
  }

  // AI Mode buttons
  const modeBtns = document.querySelectorAll(".mode-btn");
  modeBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      const mode = btn.getAttribute("data-mode");
      updateConversationAIMode(mode);
    });
  });

  // Resolve button
  const resolveBtn = document.getElementById("btn-resolve-conv");
  if (resolveBtn) {
    resolveBtn.addEventListener("click", resolveCurrentConversation);
  }

  // Learn form submit
  const learnForm = document.getElementById("form-learn-agent");
  if (learnForm) {
    learnForm.addEventListener("submit", submitLearnFromAgent);
  }

  // Connect Agent WebSocket
  connectAgentWebSocket();
  loadConversations();
}

function connectAgentWebSocket() {
  const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${wsProto}//${window.location.host}/api/v1/chat/ws/agent`;

  try {
    state.agentSocket = new WebSocket(wsUrl);

    state.agentSocket.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        handleAgentSocketEvent(payload);
      } catch (err) {
        console.error("Agent WS parse error:", err);
      }
    };

    state.agentSocket.onclose = () => {
      setTimeout(connectAgentWebSocket, 3000);
    };
  } catch (err) {
    console.warn("WS connect fail, falling back to polling", err);
  }
}

function handleAgentSocketEvent(event) {
  const { event: eventType, data } = event;

  if (eventType === "new_conversation") {
    showToast(`گفتگوی جدید از ${data.customer_name}`, "info");
    loadConversations();
  } else if (eventType === "new_message") {
    // If it belongs to currently active conversation, append it
    if (state.activeConversationId === data.conversation_id) {
      appendChatMessage(data);
    }
    // Update preview in conversation list
    updateConversationPreview(data.conversation_id, data.content);
  } else if (eventType === "ai_decision") {
    if (state.activeConversationId === data.conversation_id) {
      updateTypeSafeInspector(data);
    }
  } else if (eventType === "conversation_updated") {
    if (state.activeConversationId === data.id) {
      updateAIModeUI(data.ai_mode);
    }
    loadConversations();
  } else if (eventType === "ai_memory_updated") {
    showToast(data.message, "success");
  }
}

async function loadConversations() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/chat/conversations`);
    if (!res.ok) return;
    const data = await res.json();
    state.conversations = data;
    
    // Count active
    const activeCount = data.filter(c => c.status === "active" || c.status === "pending_human").length;
    const badge = document.getElementById("active-convs-count");
    if (badge) badge.textContent = activeCount;

    renderConversationList();

    // If no active selected yet and we have conversations, select the first
    if (!state.activeConversationId && data.length > 0) {
      selectConversation(data[0].id);
    }
  } catch (err) {
    console.error("Load convs err:", err);
  }
}

function renderConversationList(searchTerm = "") {
  const container = document.getElementById("conv-items-list");
  if (!container) return;

  let items = state.conversations;

  if (currentFilter !== "all") {
    items = items.filter(c => c.status === currentFilter);
  }

  if (searchTerm) {
    const term = searchTerm.toLowerCase();
    items = items.filter(c => 
      c.customer_name.toLowerCase().includes(term) ||
      (c.customer_email && c.customer_email.toLowerCase().includes(term)) ||
      c.id.toLowerCase().includes(term)
    );
  }

  if (items.length ==== ) {
    container.innerHTML = `
      <div style="padding: 30px 16px; text-align: center; color: var(--text-light); font-size: 13px;">
        هیچ گفتگویی در این بخش وجود ندارد.
      </div>
    `;
    return;
  }

  container.innerHTML = items.map(c => {
    const isSelected = c.id === state.activeConversationId;
    const lastMsg = c.messages && c.messages.length > 0 ? c.messages[c.messages.length - 1].content : "پیامی ارسال نشده";
    const dateStr = formatDateTime(c.last_message_at);

    let statusText = "در حال چت";
    if (c.status === "pending_human") statusText = "نیاز به پشتیبان";
    if (c.status === "resolved") statusText = "حل‌شده";

    let aiModeLabel = "خودکار AI";
    if (c.ai_mode === "copilot") aiModeLabel = "دستیار هوشمند";
    if (c.ai_mode === "human_only") aiModeLabel = "فقط انسان";

    const initial = c.customer_name ? c.customer_name.charAt(0).toUpperCase() : "ک";

    return `
      <div class="conv-item ${isSelected ? 'active' : ''}" onclick="selectConversation('${c.id}')">
        <div class="conv-item-avatar">${initial}</div>
        <div class="conv-item-details">
          <div class="conv-item-top">
            <span class="conv-customer-name">${escapeHtml(c.customer_name)}</span>
            <span class="conv-time">${dateStr}</span>
          </div>
          <div class="conv-preview">${escapeHtml(lastMsg)}</div>
          <div class="conv-tags">
            <span class="status-pill ${c.status}">${statusText}</span>
            <span class="ai-mode-pill">${aiModeLabel}</span>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

async function selectConversation(convId) {
  state.activeConversationId = convId;
  renderConversationList();

  try {
    const res = await fetch(`${API_BASE}/api/v1/chat/conversations/${convId}`);
    if (!res.ok) return;
    const conv = await res.json();
    state.activeConversation = conv;

    // Show header & input
    document.getElementById("chat-header-bar").style.display = "flex";
    document.getElementById("chat-input-bar").style.display = "flex";

    // Set header info
    document.getElementById("active-conv-title").textContent = conv.customer_name || "کاربر مهمان";
    document.getElementById("active-conv-avatar").textContent = (conv.customer_name || "ک").charAt(0).toUpperCase();
    document.getElementById("active-conv-page").textContent = conv.current_page ? `صفحه: ${conv.current_page}` : "صفحه اصلی";
    document.getElementById("active-conv-device").textContent = conv.customer_device ? conv.customer_device.substring(0, 30) + "..." : "وب";

    // Set AI mode UI
    updateAIModeUI(conv.ai_mode);

    // Render messages
    const feed = document.getElementById("chat-feed");
    feed.innerHTML = "";

    if (conv.messages && conv.messages.length > 0) {
      conv.messages.forEach(m => appendChatMessage(m));
    } else {
      feed.innerHTML = `<div style="text-align: center; color: var(--text-light); padding: 40px;">گفتگو تازه آغاز شده است.</div>`;
    }

    // Scroll to bottom
    feed.scrollTop = feed.scrollHeight;

  } catch (err) {
    console.error("Select conv error:", err);
  }
}

function appendChatMessage(msg) {
  const feed = document.getElementById("chat-feed");
  if (!feed) return;

  // Prevent duplicate
  if (document.getElementById(`agent-msg-${msg.id}`)) return;

  const row = document.createElement("div");
  row.id = `agent-msg-${msg.id}`;

  const isInternal = msg.is_internal;
  const isCustomer = msg.sender_type === "customer";
  const isAI = msg.sender_type === "ai";
  const isAgent = msg.sender_type === "agent";

  let rowCls = "customer";
  if (isAgent) rowCls = "agent";
  else if (isAI) rowCls = "ai";
  if (isInternal) rowCls = "internal";

  row.className = `agent-msg-row ${rowCls}`;

  const timeStr = formatDateTime(msg.created_at);

  if (isInternal) {
    // Internal AI Draft / Copilot suggestion
    row.innerHTML = `
      <div class="agent-msg-bubble">
        <div class="internal-draft-header">
          <span>💡 پیش‌نویس پیشنهادی هوش مصنوعی (فقط برای شما قابل رویت است)</span>
          <span style="font-weight: normal; opacity: 0.8;">${timeStr}</span>
        </div>
        <div>${escapeHtml(msg.content)}</div>
        <div class="internal-draft-actions">
          <button class="btn-draft-accept" onclick="acceptAIDraft('${escapeQuote(msg.content)}')">✓ تایید و ارسال به کاربر</button>
          <button class="btn-secondary" style="padding: 4px 10px; font-size: 11.5px;" onclick="editAIDraft('${escapeQuote(msg.content)}')">✏ ویرایش متن</button>
        </div>
      </div>
    `;
  } else {
    // Regular bubble
    let senderBadge = "کاربر";
    if (isAgent) senderBadge = msg.sender_name || "شما (پشتیبان)";
    if (isAI) senderBadge = msg.sender_name || "هوش مصنوعی";

    let learnBtnHtml = "";
    if (isAgent) {
      // Find previous customer question
      const prevQuestion = findPreviousCustomerQuestion(msg.id);
      learnBtnHtml = `
        <button class="agent-learn-trigger" onclick="openLearnModal('${escapeQuote(prevQuestion)}', '${escapeQuote(msg.content)}')">
          🎓 آموزش به هوش مصنوعی
        </button>
      `;
    }

    row.innerHTML = `
      <div class="agent-msg-bubble">
        <div>${escapeHtml(msg.content)}</div>
        <div class="agent-msg-meta">
          <span>${senderBadge}</span>
          <span>•</span>
          <span>${timeStr}</span>
          ${learnBtnHtml}
        </div>
      </div>
    `;
  }

  feed.appendChild(row);
  feed.scrollTop = feed.scrollHeight;
}

function findPreviousCustomerQuestion(msgId) {
  if (!state.activeConversation || !state.activeConversation.messages) return "سوال کاربر";
  const msgs = state.activeConversation.messages;
  for (let i = msgs.length - 1; i >= 0; i--) {
    if (msgs[i].sender_type === "customer") {
      return msgs[i].content;
    }
  }
  return "سوال مشتری";
}

async function sendAgentMessage() {
  const input = document.getElementById("agent-msg-input");
  const text = input.value.trim();
  if (!text || !state.activeConversationId) return;

  input.value = "";

  try {
    const res = await fetch(`${API_BASE}/api/v1/chat/conversations/${state.activeConversationId}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: text,
        sender_type: "agent",
        sender_name: "پشتیبان ارشد"
      })
    });

    if (res.ok) {
      const savedMsg = await res.json();
      appendChatMessage(savedMsg);
      // Auto-update conversation state to active if it was pending
      if (state.activeConversation && state.activeConversation.status === "pending_human") {
        state.activeConversation.status = "active";
        renderConversationList();
      }
    }
  } catch (err) {
    showToast("خطا در ارسال پیام پشتیبان.", "error");
  }
}

function acceptAIDraft(draftContent) {
  const input = document.getElementById("agent-msg-input");
  input.value = draftContent;
  sendAgentMessage();
}

function editAIDraft(draftContent) {
  const input = document.getElementById("agent-msg-input");
  input.value = draftContent;
  input.focus();
}

function insertQuickReply(text) {
  const input = document.getElementById("agent-msg-input");
  if (input) {
    input.value = text;
    input.focus();
  }
}

async function updateConversationAIMode(mode) {
  if (!state.activeConversationId) return;
  try {
    const res = await fetch(`${API_BASE}/api/v1/chat/conversations/${state.activeConversationId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ai_mode: mode })
    });
    if (res.ok) {
      updateAIModeUI(mode);
      if (state.activeConversation) state.activeConversation.ai_mode = mode;
      renderConversationList();
      showToast(`حالت پاسخ به '${mode === 'auto' ? 'خودکار AI' : mode === 'copilot' ? 'دستیار' : 'فقط انسان'}' تغییر کرد.`, "info");
    }
  } catch (err) {
    showToast("خطا در تغییر وضعیت هوش مصنوعی", "error");
  }
}

function updateAIModeUI(mode) {
  document.querySelectorAll(".mode-btn").forEach(btn => {
    btn.classList.toggle("active", btn.getAttribute("data-mode") === mode);
  });
}

async function resolveCurrentConversation() {
  if (!state.activeConversationId) return;
  try {
    const res = await fetch(`${API_BASE}/api/v1/chat/conversations/${state.activeConversationId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: "resolved" })
    });
    if (res.ok) {
      showToast("گفتگو با موفقیت پایان یافت و بسته شد.", "success");
      loadConversations();
    }
  } catch (err) {
    showToast("خطا در بستن گفتگو.", "error");
  }
}

// --- TypeSafe Inspector Real-Time Update ---
function updateTypeSafeInspector(decision) {
  const intentEl = document.getElementById("insp-intent");
  const confEl = document.getElementById("insp-confidence");
  const barEl = document.getElementById("insp-conf-bar");
  const actionEl = document.getElementById("insp-action");
  const reasonEl = document.getElementById("insp-reason");
  const optionsListEl = document.getElementById("insp-options-list");
  const metaEl = document.getElementById("insp-model-meta");

  if (intentEl) intentEl.textContent = decision.intent;
  
  const pct = Math.round(decision.confidence * 100);
  if (confEl) confEl.textContent = `${pct}%`;
  if (barEl) barEl.style.width = `${pct}%`;

  if (actionEl) {
    actionEl.textContent = decision.action;
    if (decision.action === "AUTO_ANSWER") actionEl.style.color = "var(--success)";
    else if (decision.action === "TRANSFER_TO_HUMAN") actionEl.style.color = "var(--danger)";
    else actionEl.style.color = "var(--warning)";
  }

  if (reasonEl) reasonEl.textContent = decision.reason;

  if (optionsListEl && decision.evaluated_options) {
    optionsListEl.innerHTML = decision.evaluated_options.map(opt => {
      const isChosen = opt.action === decision.action;
      return `
        <div class="option-eval-item ${isChosen ? 'chosen' : ''}">
          <div class="option-eval-top">
            <span>${opt.action}</span>
            <span>${Math.round(opt.score * 100)}%</span>
          </div>
          <div class="option-eval-reason">${escapeHtml(opt.reasoning)}</div>
        </div>
      `;
    }).join("");
  }

  if (metaEl) {
    metaEl.textContent = `مدل: ${decision.model || 'OpenAI API'} | تاخیر: ${decision.latency_ms || 24}ms`;
  }
}

// --- Learn from Agent Modal ---
function openLearnModal(question, answer) {
  document.getElementById("learn-conv-id").value = state.activeConversationId;
  document.getElementById("learn-question").value = question;
  document.getElementById("learn-answer").value = answer;
  openModal("modal-learn-agent");
}

async function submitLearnFromAgent(e) {
  e.preventDefault();
  const convId = document.getElementById("learn-conv-id").value;
  const question = document.getElementById("learn-question").value.trim();
  const answer = document.getElementById("learn-answer").value.trim();
  const tags = document.getElementById("learn-tags").value.trim();

  try {
    const res = await fetch(`${API_BASE}/api/v1/chat/conversations/${convId}/learn`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: convId,
        customer_question: question,
        agent_answer: answer,
        tags: tags,
        category: "agent_learned"
      })
    });

    if (res.ok) {
      closeModal("modal-learn-agent");
      showToast("پاسخ شما با موفقیت به پایگاه یادگیری هوش مصنوعی افزوده شد!", "success");
    }
  } catch (err) {
    showToast("خطا در ذخیره یادگیری هوش مصنوعی.", "error");
  }
}

function updateConversationPreview(convId, content) {
  const item = state.conversations.find(c => c.id === convId);
  if (item) {
    item.last_message_at = new Date().toISOString();
    renderConversationList();
  }
}

function formatDateTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function escapeHtml(text) {
  if (!text) return "";
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function escapeQuote(text) {
  if (!text) return "";
  return text.replace(/'/g, "\\'").replace(/"/g, "&quot;").replace(/\n/g, " ");
}
