// AI Settings, Presets & TypeSafe Engine Module
let presetsData = [];

function initAISettingsModule() {
  loadPresets();
  loadAISettings();
  loadDecisionLogs();

  // Slider display listeners
  const tempSlider = document.getElementById("ai-temp");
  const tempDisplay = document.getElementById("temp-display");
  if (tempSlider && tempDisplay) {
    tempSlider.addEventListener("input", (e) => {
      tempDisplay.textContent = e.target.value;
    });
  }

  const threshSlider = document.getElementById("ai-threshold");
  const threshDisplay = document.getElementById("threshold-display");
  if (threshSlider && threshDisplay) {
    threshSlider.addEventListener("input", (e) => {
      threshDisplay.textContent = Math.round(e.target.value * 100) + "%";
    });
  }

  // Toggle API key visibility
  const toggleKeyBtn = document.getElementById("btn-toggle-key-vis");
  const keyInput = document.getElementById("ai-api-key");
  if (toggleKeyBtn && keyInput) {
    toggleKeyBtn.addEventListener("click", () => {
      if (keyInput.type === "password") {
        keyInput.type = "text";
        toggleKeyBtn.textContent = "🔒";
      } else {
        keyInput.type = "password";
        toggleKeyBtn.textContent = "👁";
      }
    });
  }

  // Save Settings Form
  const form = document.getElementById("form-ai-settings");
  if (form) {
    form.addEventListener("submit", saveAISettings);
  }

  // Test Connection Button
  const testBtn = document.getElementById("btn-test-connection");
  if (testBtn) {
    testBtn.addEventListener("click", testAIConnection);
  }
}

async function loadPresets() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/ai/presets`);
    if (!res.ok) return;
    presetsData = await res.json();
    renderPresets();
  } catch (err) {
    console.error("Presets err:", err);
  }
}

function renderPresets() {
  const container = document.getElementById("preset-grid-container");
  if (!container) return;

  container.innerHTML = presetsData.map(p => `
    <div class="preset-card" onclick="applyPreset('${p.id}')" id="preset-card-${p.id}">
      <h4>${p.name}</h4>
      <p>${p.description}</p>
      <div style="font-size: 10.5px; color: var(--primary); font-family: monospace; margin-top: 6px;">
        مدل پیش‌فرض: ${p.default_model}
      </div>
    </div>
  `).join("");
}

function applyPreset(presetId) {
  const p = presetsData.find(x => x.id === presetId);
  if (!p) return;

  document.querySelectorAll(".preset-card").forEach(c => c.classList.remove("active"));
  const card = document.getElementById(`preset-card-${presetId}`);
  if (card) card.classList.add("active");

  document.getElementById("ai-provider-name").value = p.name;
  document.getElementById("ai-base-url").value = p.base_url;
  document.getElementById("ai-model-name").value = p.default_model;

  showToast(`تنظیمات ارائه‌دهنده ${p.name} با موفقیت بارگذاری شد.`, "info");
}

async function loadAISettings() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/ai/settings`);
    if (!res.ok) return;
    const data = await res.json();
    state.aiSettings = data;

    document.getElementById("ai-provider-name").value = data.provider_name || "";
    document.getElementById("ai-base-url").value = data.base_url || "";
    document.getElementById("ai-api-key").value = data.masked_api_key || "";
    document.getElementById("ai-model-name").value = data.model_name || "";
    document.getElementById("ai-temp").value = data.temperature;
    document.getElementById("temp-display").textContent = data.temperature;
    document.getElementById("ai-max-tokens").value = data.max_tokens;

    document.getElementById("ai-threshold").value = data.auto_answer_threshold;
    document.getElementById("threshold-display").textContent = Math.round(data.auto_answer_threshold * 100) + "%";

    document.getElementById("ai-enable-typesafe").checked = data.enable_typesafe_decision;
    document.getElementById("ai-enable-learning").checked = data.enable_agent_learning;
    document.getElementById("ai-handoff-complaint").checked = data.auto_handoff_on_complaint;

    document.getElementById("ai-system-prompt").value = data.system_prompt || "";

  } catch (err) {
    console.error("Load AI settings err:", err);
  }
}

async function saveAISettings(e) {
  e.preventDefault();
  const saveBtn = document.getElementById("btn-save-ai");
  saveBtn.disabled = true;
  saveBtn.textContent = "در حال ذخیره...";

  const payload = {
    provider_name: document.getElementById("ai-provider-name").value.trim(),
    base_url: document.getElementById("ai-base-url").value.trim(),
    model_name: document.getElementById("ai-model-name").value.trim(),
    temperature: parseFloat(document.getElementById("ai-temp").value),
    max_tokens: parseInt(document.getElementById("ai-max-tokens").value, 10),
    auto_answer_threshold: parseFloat(document.getElementById("ai-threshold").value),
    enable_typesafe_decision: document.getElementById("ai-enable-typesafe").checked,
    enable_agent_learning: document.getElementById("ai-enable-learning").checked,
    auto_handoff_on_complaint: document.getElementById("ai-handoff-complaint").checked,
    system_prompt: document.getElementById("ai-system-prompt").value.trim()
  };

  const keyVal = document.getElementById("ai-api-key").value.trim();
  // Only update api_key if user entered an unmasked key
  if (keyVal && !keyVal.includes("••")) {
    payload.api_key = keyVal;
  }

  try {
    const res = await fetch(`${API_BASE}/api/v1/ai/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      showToast("تنظیمات هوش مصنوعی با موفقیت بروزرسانی شد!", "success");
      loadAISettings();
    } else {
      showToast("خطا در ذخیره تنظیمات.", "error");
    }
  } catch (err) {
    showToast("خطای شبکه در ذخیره تنظیمات.", "error");
  } finally {
    saveBtn.disabled = false;
    saveBtn.innerHTML = `
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
      <span>ذخیره تنظیمات</span>
    `;
  }
}

async function testAIConnection() {
  const box = document.getElementById("test-result-box");
  const testBtn = document.getElementById("btn-test-connection");
  
  box.style.display = "block";
  box.className = "test-result-box";
  box.style.background = "#f1f5f9";
  box.style.color = "var(--text-main)";
  box.style.border = "1px solid var(--border)";
  box.textContent = "در حال ارسال پینگ آزمایشی به ارائه‌دهنده هوش مصنوعی...";

  testBtn.disabled = true;

  const payload = {
    base_url: document.getElementById("ai-base-url").value.trim(),
    api_key: document.getElementById("ai-api-key").value.trim(),
    model_name: document.getElementById("ai-model-name").value.trim(),
    provider_name: document.getElementById("ai-provider-name").value.trim()
  };

  try {
    const res = await fetch(`${API_BASE}/api/v1/ai/test-connection`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (data.success) {
      box.className = "test-result-box success";
      box.innerHTML = `
        <strong>✓ ${data.message}</strong><br>
        <span style="font-size: 11.5px; opacity: 0.9;">پاسخ مدل: ${data.sample_response || 'OK'}</span>
      `;
      showToast("تست اتصال با موفقیت انجام شد!", "success");
    } else {
      box.className = "test-result-box error";
      box.innerHTML = `
        <strong>✕ تست ناموفق (${data.latency_ms}ms):</strong><br>
        <span>${data.message}</span>
      `;
      showToast("خطا در برقراری ارتباط با ارائه‌دهنده هوش مصنوعی.", "error");
    }
  } catch (err) {
    box.className = "test-result-box error";
    box.textContent = `خطای ارتباطی سرور: ${err.message}`;
  } finally {
    testBtn.disabled = false;
  }
}

async function loadDecisionLogs() {
  const tbody = document.getElementById("decision-audit-tbody");
  if (!tbody) return;

  try {
    const res = await fetch(`${API_BASE}/api/v1/ai/decisions?limit=15`);
    if (!res.ok) return;
    const logs = await res.json();

    if (logs.length ==== ) {
      tbody.innerHTML = `<tr><td colspan="7" style="padding: 20px; text-align: center; color: var(--text-light);">هنوز تصمیمی ثبت نشده است. با ارسال پیام در چت، اولین لاگ ایجاد می‌شود.</td></tr>`;
      return;
    }

    tbody.innerHTML = logs.map(l => {
      const timeStr = new Date(l.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const confPct = Math.round(l.confidence * 100);

      let actionBadgeCls = "status-pill active";
      if (l.action === "TRANSFER_TO_HUMAN") actionBadgeCls = "status-pill pending_human";
      if (l.action === "SUGGEST_TO_AGENT") actionBadgeCls = "status-pill resolved";

      return `
        <tr style="border-bottom: 1px solid var(--border);">
          <td style="padding: 10px 12px; color: var(--text-light);">${timeStr}</td>
          <td style="padding: 10px 12px; font-weight: 500; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(l.customer_message)}</td>
          <td style="padding: 10px 12px;"><span style="background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 11px;">${l.intent}</span></td>
          <td style="padding: 10px 12px; font-weight: 700; color: ${confPct >= 75 ? 'var(--success)' : 'var(--warning)'};">${confPct}%</td>
          <td style="padding: 10px 12px;"><span class="${actionBadgeCls}">${l.action}</span></td>
          <td style="padding: 10px 12px; color: var(--text-muted); font-size: 11.5px; max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${escapeHtml(l.reason || '')}">${escapeHtml(l.reason || '-')}</td>
          <td style="padding: 10px 12px; font-family: monospace; font-size: 11px;">${l.latency_ms}ms</td>
        </tr>
      `;
    }).join("");

  } catch (err) {
    console.error("Decision logs err:", err);
  }
}
