// Knowledge Base & Memory Module

function initKnowledgeModule() {
  loadKnowledgeItems();

  const openAddBtn = document.getElementById("btn-open-add-kb");
  if (openAddBtn) {
    openAddBtn.addEventListener("click", () => openModal("modal-add-kb"));
  }

  const createForm = document.getElementById("form-create-kb");
  if (createForm) {
    createForm.addEventListener("submit", submitNewKnowledgeItem);
  }

  const searchInput = document.getElementById("kb-search-input");
  if (searchInput) {
    searchInput.addEventListener("input", (e) => filterKnowledge(e.target.value.trim()));
  }

  const catSelect = document.getElementById("kb-filter-cat");
  if (catSelect) {
    catSelect.addEventListener("change", (e) => filterKnowledge("", e.target.value));
  }

  // Knowledge Retrieval Tester
  const testBtn = document.getElementById("btn-run-kb-test");
  if (testBtn) {
    testBtn.addEventListener("click", runKnowledgeRetrievalTest);
  }
}

async function loadKnowledgeItems() {
  try {
    const res = await fetch(`${API_BASE}/api/v1/knowledge`);
    if (!res.ok) return;
    const items = await res.json();
    state.knowledgeItems = items;
    renderKnowledgeGrid(items);
  } catch (err) {
    console.error("Load KB err:", err);
  }
}

function filterKnowledge(searchTerm = "", cat = "") {
  let filtered = state.knowledgeItems;
  if (!cat) {
    const catSelect = document.getElementById("kb-filter-cat");
    if (catSelect) cat = catSelect.value;
  }
  if (!searchTerm) {
    const searchInput = document.getElementById("kb-search-input");
    if (searchInput) searchTerm = searchInput.value.trim().toLowerCase();
  }

  if (cat) {
    filtered = filtered.filter(i => i.category === cat);
  }

  if (searchTerm) {
    filtered = filtered.filter(i => 
      i.title.toLowerCase().includes(searchTerm) || 
      i.content.toLowerCase().includes(searchTerm) ||
      (i.tags && i.tags.toLowerCase().includes(searchTerm))
    );
  }

  renderKnowledgeGrid(filtered);
}

function renderKnowledgeGrid(items) {
  const container = document.getElementById("kb-grid-list");
  if (!container) return;

  if (items.length === 0) {
    container.innerHTML = `
      <div style="grid-column: span 3; padding: 40px; text-align: center; color: var(--text-light);">
        هیچ آیتم دانشی با این مشخصات یافت نشد. می‌توانید با دکمه بالا یک آیتم جدید اضافه کنید.
      </div>
    `;
    return;
  }

  container.innerHTML = items.map(item => {
    const isLearned = item.source === "agent_learned" || item.category === "agent_learned";
    const badgeText = isLearned ? "🎓 یادگرفته‌شده از پشتیبان" : "پرسش متداول دستی";
    const badgeCls = isLearned ? "kb-badge learned" : "kb-badge manual";

    return `
      <div class="kb-card" id="kb-card-${item.id}">
        <div class="kb-card-header">
          <h4 class="kb-card-title">${escapeHtml(item.title)}</h4>
          <span class="${badgeCls}">${badgeText}</span>
        </div>
        <div class="kb-card-content">${escapeHtml(item.content)}</div>
        <div class="kb-card-footer">
          <div>
            <span>استفاده توسط AI: <strong>${item.usage_count}</strong> بار</span>
            ${item.tags ? `<span style="margin-right: 8px; color: var(--text-light); font-size: 11px;">#${escapeHtml(item.tags)}</span>` : ''}
          </div>
          <div class="kb-actions">
            <button class="chat-action-btn" style="padding: 3px 8px; font-size: 11px; color: var(--danger); border-color: #fecaca;" onclick="deleteKnowledgeItem('${item.id}')">حذف</button>
          </div>
        </div>
      </div>
    `;
  }).join("");
}

async function submitNewKnowledgeItem(e) {
  e.preventDefault();
  const title = document.getElementById("new-kb-title").value.trim();
  const category = document.getElementById("new-kb-category").value;
  const content = document.getElementById("new-kb-content").value.trim();
  const tags = document.getElementById("new-kb-tags").value.trim();

  try {
    const res = await fetch(`${API_BASE}/api/v1/knowledge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title,
        content,
        category,
        tags,
        source: "manual"
      })
    });

    if (res.ok) {
      closeModal("modal-add-kb");
      document.getElementById("form-create-kb").reset();
      showToast("آیتم جدید با موفقیت به پایگاه دانش اضافه شد!", "success");
      loadKnowledgeItems();
    }
  } catch (err) {
    showToast("خطا در ایجاد آیتم دانش.", "error");
  }
}

async function deleteKnowledgeItem(id) {
  if (!confirm("آیا از حذف این آیتم از پایگاه دانش اطمینان دارید؟")) return;

  try {
    const res = await fetch(`${API_BASE}/api/v1/knowledge/${id}`, {
      method: "DELETE"
    });
    if (res.ok) {
      showToast("آیتم با موفقیت حذف شد.", "info");
      loadKnowledgeItems();
    }
  } catch (err) {
    showToast("خطا در حذف آیتم.", "error");
  }
}

async function runKnowledgeRetrievalTest() {
  const input = document.getElementById("test-kb-input");
  const output = document.getElementById("test-kb-output");
  const query = input.value.trim();
  if (!query) return;

  output.innerHTML = "در حال جستجو و ارزیابی تشابه در پایگاه دانش...";

  try {
    const res = await fetch(`${API_BASE}/api/v1/knowledge/test-retrieval?query=${encodeURIComponent(query)}`, {
      method: "POST"
    });
    const data = await res.json();

    if (data.results.length === 0) {
      output.innerHTML = `<div style="color: #b91c1c;">هیچ سندی تطابق کافی نداشت. در این حالت سیستم مکالمه را به پشتیبان انسانی منتقل می‌کند.</div>`;
      return;
    }

    output.innerHTML = `
      <div style="font-weight: 700; color: #065f46; margin-bottom: 6px;">
        تعداد ${data.matched_count} سند متناسب استخراج شد:
      </div>
      <div style="display: flex; flex-direction: column; gap: 8px;">
        ${data.results.map(r => `
          <div style="background: #ffffff; border: 1px solid #a7f3d0; border-radius: 6px; padding: 10px;">
            <div style="display: flex; justify-content: space-between; font-weight: 600; color: #047857;">
              <span>${escapeHtml(r.title)}</span>
              <span>درصد تطابق: ${r.relevance_percent}</span>
            </div>
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">${escapeHtml(r.content)}</div>
          </div>
        `).join("")}
      </div>
    `;

  } catch (err) {
    output.textContent = `خطا در اجرای تست: ${err.message}`;
  }
}
