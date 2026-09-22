(function () {
  "use strict";

  // Prevent multiple initializations
  if (window.__OmniSupportLoaded) return;
  window.__OmniSupportLoaded = true;

  // 1. Configuration detection
  const scriptTag = document.currentScript || document.querySelector('script[data-site-id]');
  const siteId = (scriptTag && scriptTag.getAttribute('data-site-id')) || 
                 (window.OmniSupportConfig && window.OmniSupportConfig.siteId) || 'site_default';
  
  let apiUrl = (scriptTag && scriptTag.getAttribute('data-api-url')) || 
               (window.OmniSupportConfig && window.OmniSupportConfig.apiUrl);

  if (!apiUrl) {
    // Infer API URL from the script src
    if (scriptTag && scriptTag.src) {
      const urlObj = new URL(scriptTag.src);
      apiUrl = `${urlObj.protocol}//${urlObj.host}`;
    } else {
      apiUrl = window.location.origin;
    }
  }
  apiUrl = apiUrl.replace(/\/$/, "");

  // 2. Persistent Customer ID
  let customerId = localStorage.getItem("omni_customer_id");
  if (!customerId) {
    customerId = "cust_" + Math.random().toString(36).substring(2, 11) + Date.now().toString(36);
    localStorage.setItem("omni_customer_id", customerId);
  }

  let conversationId = localStorage.getItem("omni_conv_id_" + siteId) || null;
  let socket = null;
  let isOpen = false;
  let siteConfig = {
    title: "پشتیبانی آنلاین",
    primaryColor: "#4f46e5",
    welcomeMessage: "سلام! چطور می‌توانیم امروز به شما کمک کنیم؟",
    position: "right"
  };

  // 3. Load CSS
  const cssUrl = `${apiUrl}/static/widget.css`;
  if (!document.querySelector(`link[href="${cssUrl}"]`)) {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = cssUrl;
    document.head.appendChild(link);
  }

  // 4. Inject HTML Elements
  const container = document.createElement("div");
  container.className = "omni-widget-container";
  container.id = "omni-widget-root";

  container.innerHTML = `
    <!-- Launcher Button -->
    <button class="omni-launcher" id="omni-launcher-btn" aria-label="چت با پشتیبانی">
      <span class="omni-badge"></span>
      <svg class="omni-icon-chat" viewBox="0 0 24 24">
        <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/>
      </svg>
      <svg class="omni-icon-close" viewBox="0 0 24 24">
        <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
      </svg>
    </button>

    <!-- Chat Box Window -->
    <div class="omni-window" id="omni-window">
      <div class="omni-header">
        <div class="omni-header-info">
          <div class="omni-header-avatar">🤖</div>
          <div class="omni-header-text">
            <h3 id="omni-title">پشتیبانی آنلاین</h3>
            <div class="omni-header-status">
              <span class="omni-status-dot"></span>
              <span id="omni-status-text">پاسخگویی سریع با هوش مصنوعی و کارشناس</span>
            </div>
            <div id="omni-ticket-badge" style="display: none; font-size: 11px; margin-top: 2px; color: #e0e7ff;">
              <span>شماره تیکت شما: <strong id="omni-ticket-num" style="background: rgba(255,255,255,0.2); padding: 1px 5px; border-radius: 4px;">HD-1001</strong></span>
              <a href="/portal" target="_blank" style="color: #fff; text-decoration: underline; margin-right: 6px;">پیگیری در پورتال ↗</a>
            </div>
          </div>
        </div>
        <button class="omni-close-btn" id="omni-close-btn" title="بستن">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
          </svg>
        </button>
      </div>

      <div class="omni-messages" id="omni-messages-box">
        <div class="omni-typing" id="omni-typing" style="display: none;">
          <div class="omni-dot"></div>
          <div class="omni-dot"></div>
          <div class="omni-dot"></div>
        </div>
      </div>

      <form class="omni-input-area" id="omni-input-form">
        <textarea class="omni-input-field" id="omni-input-field" placeholder="پیام خود را بنویسید..." rows="1"></textarea>
        <button type="submit" class="omni-send-btn" id="omni-send-btn" aria-label="ارسال">
          <svg viewBox="0 0 24 24">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
        </button>
      </form>
      <div class="omni-footer-note">قدرت گرفته از هوش مصنوعی OmniSupport</div>
    </div>
  `;
  document.body.appendChild(container);

  // 5. Elements
  const launcherBtn = document.getElementById("omni-launcher-btn");
  const chatWindow = document.getElementById("omni-window");
  const closeBtn = document.getElementById("omni-close-btn");
  const messagesBox = document.getElementById("omni-messages-box");
  const inputForm = document.getElementById("omni-input-form");
  const inputField = document.getElementById("omni-input-field");
  const typingIndicator = document.getElementById("omni-typing");
  const titleEl = document.getElementById("omni-title");

  // 6. Fetch Site Branding & Settings
  async function fetchSiteSettings() {
    try {
      const res = await fetch(`${apiUrl}/api/v1/sites/${siteId}`);
      if (res.ok) {
        const data = await res.json();
        siteConfig.title = data.widget_title || siteConfig.title;
        siteConfig.primaryColor = data.primary_color || siteConfig.primaryColor;
        siteConfig.welcomeMessage = data.welcome_message || siteConfig.welcomeMessage;
        siteConfig.position = data.widget_position || siteConfig.position;

        titleEl.textContent = siteConfig.title;
        document.documentElement.style.setProperty("--omni-primary", siteConfig.primaryColor);
        if (siteConfig.position === "left") {
          container.classList.add("left-aligned");
        }
      }
    } catch (err) {
      console.warn("[OmniSupport] Site settings load fallback", err);
    }
  }

  // 7. Toggle Open/Close
  function toggleChat() {
    isOpen = !isOpen;
    if (isOpen) {
      launcherBtn.classList.add("open");
      chatWindow.classList.add("open");
      initConversation();
      inputField.focus();
    } else {
      launcherBtn.classList.remove("open");
      chatWindow.classList.remove("open");
    }
  }

  launcherBtn.addEventListener("click", toggleChat);
  closeBtn.addEventListener("click", toggleChat);

  // 8. Auto-expand textarea
  inputField.addEventListener("input", function () {
    this.style.height = "auto";
    this.style.height = Math.min(this.scrollHeight, 100) + "px";
  });

  inputField.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      inputForm.dispatchEvent(new Event("submit"));
    }
  });

  // 9. Init or Resume Conversation
  async function initConversation() {
    if (conversationId && messagesBox.children.length > 1) {
      connectWebSocket();
      return;
    }

    try {
      const res = await fetch(`${apiUrl}/api/v1/chat/conversations`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          site_id: siteId,
          customer_id: customerId,
          customer_device: navigator.userAgent.substring(0, 200),
          current_page: window.location.href
        })
      });

      if (res.ok) {
        const data = await res.json();
        conversationId = data.id;
        localStorage.setItem("omni_conv_id_" + siteId, conversationId);
        
        // Show ticket badge
        if (data.ticket_number) {
          const badge = document.getElementById("omni-ticket-badge");
          const numEl = document.getElementById("omni-ticket-num");
          if (badge && numEl) {
            numEl.textContent = data.ticket_number;
            badge.style.display = "block";
          }
        }

        // Render existing messages
        messagesBox.innerHTML = "";
        messagesBox.appendChild(typingIndicator);

        if (data.messages && data.messages.length > 0) {
          data.messages.forEach(msg => appendMessage(msg));
        }
        connectWebSocket();
      }
    } catch (err) {
      console.error("[OmniSupport] Init conversation error:", err);
    }
  }

  // 10. WebSocket Connection
  function connectWebSocket() {
    if (!conversationId || (socket && socket.readyState === WebSocket.OPEN)) return;

    const wsProto = apiUrl.startsWith("https") ? "wss" : "ws";
    const host = apiUrl.replace(/^https?:\/\//, "");
    const wsUrl = `${wsProto}://${host}/api/v1/chat/ws/chat/${conversationId}`;

    socket = new WebSocket(wsUrl);

    socket.onmessage = function (event) {
      try {
        const data = JSON.parse(event.data);
        if (data.event === "new_message") {
          const msg = data.data;
          // Ignore internal agent notes
          if (!msg.is_internal) {
            hideTyping();
            appendMessage(msg);
          }
        }
      } catch (err) {
        console.error("[OmniSupport] WS parse err", err);
      }
    };

    socket.onclose = function () {
      // Reconnect after 3 seconds
      setTimeout(connectWebSocket, 3000);
    };
  }

  function showTyping() {
    typingIndicator.style.display = "flex";
    messagesBox.appendChild(typingIndicator);
    messagesBox.scrollTop = messagesBox.scrollHeight;
  }

  function hideTyping() {
    typingIndicator.style.display = "none";
  }

  // 11. Append Message Bubble
  function appendMessage(msg) {
    // Avoid duplicate render
    if (document.getElementById(`omni-msg-${msg.id}`)) return;

    const msgDiv = document.createElement("div");
    msgDiv.id = `omni-msg-${msg.id}`;
    
    let cls = "omni-msg-customer";
    let badgeText = "شما";
    let badgeClass = "";

    if (msg.sender_type === "ai") {
      cls = "omni-msg-ai";
      badgeText = "هوش مصنوعی";
      badgeClass = "ai-badge";
    } else if (msg.sender_type === "agent") {
      cls = "omni-msg-agent";
      badgeText = msg.sender_name || "پشتیبان";
    } else if (msg.sender_type === "system") {
      cls = "omni-msg-system";
      badgeText = "سیستم";
    }

    msgDiv.className = `omni-msg ${cls}`;

    const date = msg.created_at ? new Date(msg.created_at) : new Date();
    const timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    msgDiv.innerHTML = `
      <div class="omni-msg-bubble">${escapeHtml(msg.content)}</div>
      <div class="omni-msg-meta">
        <span class="omni-sender-badge ${badgeClass}">${badgeText}</span>
        <span>${timeStr}</span>
      </div>
    `;

    messagesBox.insertBefore(msgDiv, typingIndicator);
    messagesBox.scrollTop = messagesBox.scrollHeight;
  }

  function escapeHtml(text) {
    if (!text) return "";
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;")
      .replace(/\n/g, "<br>");
  }

  // 12. Send Message
  inputForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    const text = inputField.value.trim();
    if (!text) return;

    inputField.value = "";
    inputField.style.height = "auto";

    // Immediate optimistic render
    const tempId = "temp_" + Date.now();
    appendMessage({
      id: tempId,
      content: text,
      sender_type: "customer",
      created_at: new Date().toISOString()
    });

    showTyping();

    try {
      if (!conversationId) {
        await initConversation();
      }

      const res = await fetch(`${apiUrl}/api/v1/chat/conversations/${conversationId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content: text,
          sender_type: "customer"
        })
      });

      if (!res.ok) {
        hideTyping();
      }
    } catch (err) {
      console.error("[OmniSupport] Send message error:", err);
      hideTyping();
    }
  });

  // Initialize
  fetchSiteSettings();
})();
