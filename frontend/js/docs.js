// Sites & Interactive Documentation Module

function initSitesModule() {
  loadSitesData();

  // Color picker sync
  const picker = document.getElementById("site-color-picker");
  const hex = document.getElementById("site-color-hex");
  if (picker && hex) {
    picker.addEventListener("input", (e) => hex.value = e.target.value);
    hex.addEventListener("input", (e) => picker.value = e.target.value);
  }

  // Save site theme button
  const saveBtn = document.getElementById("btn-save-site-theme");
  if (saveBtn) {
    saveBtn.addEventListener("click", saveSiteTheme);
  }
}

async function loadSitesData() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/sites`);
    if (!res.ok) return;
    const sites = await res.json();
    if (sites.length > 0) {
      const site = sites[0];
      state.sites = sites;

      document.getElementById("site-id-display").value = site.id;
      document.getElementById("site-title-input").value = site.widget_title || "پشتیبانی آنلاین";
      document.getElementById("site-welcome-input").value = site.welcome_message || "";
      document.getElementById("site-color-picker").value = site.primary_color || "#4f46e5";
      document.getElementById("site-color-hex").value = site.primary_color || "#4f46e5";
      document.getElementById("site-position-select").value = site.widget_position || "right";

      // Update snippet code in pre
      const origin = window.location.origin;
      const snippet = `<!-- OmniSupport AI Live Chat Widget -->\n<script src="${origin}/static/widget.js" data-site-id="${site.id}" data-api-url="${origin}" async></script>`;
      const preEl = document.getElementById("embed-code-text");
      if (preEl) preEl.textContent = snippet;
    }
  } catch (err) {
    console.error("Load sites err:", err);
  }
}

async function saveSiteTheme() {
  const siteId = document.getElementById("site-id-display").value;
  const payload = {
    name: "سایت اصلی",
    widget_title: document.getElementById("site-title-input").value.trim(),
    welcome_message: document.getElementById("site-welcome-input").value.trim(),
    primary_color: document.getElementById("site-color-hex").value.trim(),
    widget_position: document.getElementById("site-position-select").value
  };

  try {
    const res = await fetch(`${API_BASE}/api/v1/sites/${siteId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      showToast("تنظیمات ویجت و تم با موفقیت ذخیره شد!", "success");
    }
  } catch (err) {
    showToast("خطا در ذخیره مشخصات ویجت.", "error");
  }
}

// --- Interactive Docs Code Switchers ---
function initDocsModule() {
  const ticketBtn = document.getElementById("btn-run-api-ticket");
  if (ticketBtn) {
    ticketBtn.addEventListener("click", runApiTicketTest);
  }
}

function switchCodeTab(targetId) {
  document.querySelectorAll(".code-tab-btn").forEach(btn => {
    btn.classList.toggle("active", btn.getAttribute("onclick").includes(targetId));
  });
  document.querySelectorAll(".code-content-pane").forEach(pane => {
    pane.style.display = pane.id === targetId ? "block" : "none";
  });
}

function switchApiTab(targetId) {
  document.querySelectorAll(".docs-section .code-tabs .code-tab-btn").forEach(btn => {
    if (btn.getAttribute("onclick").includes("switchApiTab")) {
      btn.classList.toggle("active", btn.getAttribute("onclick").includes(targetId));
    }
  });
  document.querySelectorAll(".api-content-pane").forEach(pane => {
    pane.style.display = pane.id === targetId ? "block" : "none";
  });
}

async function runApiTicketTest() {
  const nameInput = document.getElementById("api-test-name");
  const msgInput = document.getElementById("api-test-msg");
  const feedback = document.getElementById("api-test-feedback");

  const name = nameInput.value.trim() || "کاربر تستی";
  const message = msgInput.value.trim();
  if (!message) return;

  feedback.innerHTML = "در حال ارسال تیکت مستقیم از طریق REST API...";

  try {
    const res = await fetch(`${API_BASE}/api/v1/external/tickets`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Site-Key": "omni_live_k8s92f8a129d38c71e041"
      },
      body: JSON.stringify({
        site_id: "site_default",
        customer_id: "api_user_" + Math.random().toString(36).substring(2, 7),
        customer_name: name,
        message: message,
        current_page: "/checkout/order-success"
      })
    });

    const data = await res.json();
    if (res.ok) {
      feedback.innerHTML = `
        <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 6px; padding: 10px; color: #065f46;">
          <strong>✓ تیکت با موفقیت ثبت شد! (HTTP 200 OK)</strong><br>
          <span>شناسه گفتگو: <code>${data.conversation_id}</code></span><br>
          <span style="font-size: 11.5px; opacity: 0.9;">موتور TypeSafe AI پیام را دریافت کرد و در تب <strong>«چت زنده»</strong> هم‌اکنون در دسترس است!</span>
        </div>
      `;
      showToast("تیکت از طریق REST API ثبت شد!", "success");
      loadConversations();
    } else {
      feedback.innerHTML = `<div style="color: var(--danger);">خطا در ثبت: ${data.detail || 'نامشخص'}</div>`;
    }
  } catch (err) {
    feedback.textContent = `خطای شبکه: ${err.message}`;
  }
}
