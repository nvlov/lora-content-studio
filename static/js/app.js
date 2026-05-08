// Lora Content Studio — клиентская логика на ванильном JS.

// ============================================================
// state
// ============================================================
const state = {
  rubrics: [],          // [{key, name, emoji}]
  rubricsFull: [],      // [{key, name, emoji, system_prompt, image_prompt_template}]
  selectedRubric: null, // key
  topic: "",
  text: "",
  imagePath: null,      // имя файла в static/uploads/
  imageSource: "none",  // kling | manual_upload | none
  imagePrompt: null,
  editingPostId: null,  // id поста, если открыли из библиотеки
  activeTab: "create",
};

// ============================================================
// helpers
// ============================================================
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

function toast(message, kind = "info") {
  const el = $("#toast");
  el.textContent = message;
  el.className = `toast toast--${kind}`;
  el.hidden = false;
  clearTimeout(el._t);
  el._t = setTimeout(() => { el.hidden = true; }, 4000);
}

async function jsonFetch(url, options = {}) {
  const opts = { headers: { "Content-Type": "application/json" }, ...options };
  const r = await fetch(url, opts);
  let data = null;
  try { data = await r.json(); } catch (_) {}
  if (!r.ok) {
    const msg = (data && data.error) || `Ошибка ${r.status}`;
    throw new Error(msg);
  }
  return data;
}

const api = {
  rubrics: () => jsonFetch("/api/rubrics"),
  rubricsFull: () => jsonFetch("/api/settings/rubrics"),
  rubricUpdate: (key, body) =>
    jsonFetch(`/api/settings/rubrics/${encodeURIComponent(key)}`, {
      method: "PATCH", body: JSON.stringify(body),
    }),
  generateText: (body) =>
    jsonFetch("/api/generate-text", { method: "POST", body: JSON.stringify(body) }),
  generateImage: (body) =>
    jsonFetch("/api/generate-image", { method: "POST", body: JSON.stringify(body) }),
  uploadImage: async (file) => {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch("/api/upload-image", { method: "POST", body: fd });
    let data = null; try { data = await r.json(); } catch (_) {}
    if (!r.ok) throw new Error((data && data.error) || `Ошибка ${r.status}`);
    return data;
  },
  postsList: (q) => {
    const params = new URLSearchParams();
    if (q.search) params.set("search", q.search);
    if (q.rubric_key) params.set("rubric_key", q.rubric_key);
    return jsonFetch("/api/posts?" + params.toString());
  },
  postCreate: (body) =>
    jsonFetch("/api/posts", { method: "POST", body: JSON.stringify(body) }),
  postUpdate: (id, body) =>
    jsonFetch(`/api/posts/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  postGet: (id) => jsonFetch(`/api/posts/${id}`),
  postDelete: (id) => jsonFetch(`/api/posts/${id}`, { method: "DELETE" }),
};

// ============================================================
// editor (вкладка «Создать пост»)
// ============================================================
function rubricByKey(key) {
  return state.rubrics.find(r => r.key === key) || null;
}

function renderRubrics() {
  const root = $("#rubrics-list");
  root.innerHTML = "";
  state.rubrics.forEach(r => {
    const btn = document.createElement("button");
    btn.className = "rubric" + (state.selectedRubric === r.key ? " is-selected" : "");
    btn.innerHTML = `<span class="rubric__emoji">${r.emoji || ""}</span><span class="rubric__name">${r.name}</span>`;
    btn.onclick = () => {
      state.selectedRubric = r.key;
      renderRubrics();
      renderPreview();
    };
    root.appendChild(btn);
  });
}

function renderPreview() {
  const r = rubricByKey(state.selectedRubric);
  $("#preview-rubric").textContent = r ? `${r.emoji || ""} ${r.name}` : "—";
  $("#preview-text").textContent = state.text || "Текст поста появится здесь…";
  const imgRoot = $("#preview-image");
  imgRoot.innerHTML = "";
  if (state.imagePath) {
    const img = document.createElement("img");
    img.src = `/static/uploads/${state.imagePath}`;
    img.alt = "preview";
    imgRoot.appendChild(img);
  } else {
    const ph = document.createElement("div");
    ph.className = "vk-post__image-placeholder";
    ph.textContent = "Картинка появится здесь";
    imgRoot.appendChild(ph);
  }
}

function setText(text) {
  state.text = text;
  $("#post-text").value = text;
  renderPreview();
}

async function onGenerateText() {
  if (!state.selectedRubric) {
    toast("Выберите рубрику", "error");
    return;
  }
  state.topic = $("#topic").value.trim();
  const btn = $("#btn-generate-text");
  btn.disabled = true; btn.textContent = "Генерирую…";
  try {
    const data = await api.generateText({
      rubric_key: state.selectedRubric,
      topic: state.topic,
    });
    setText(data.text);
    toast("Текст сгенерирован", "success");
  } catch (e) {
    toast(e.message, "error");
  } finally {
    btn.disabled = false; btn.textContent = "Сгенерировать текст";
  }
}

async function onGenerateImage() {
  if (!state.selectedRubric) {
    toast("Выберите рубрику", "error");
    return;
  }
  // Подставим тему в шаблон промпта картинки
  const full = state.rubricsFull.find(r => r.key === state.selectedRubric);
  if (!full) {
    toast("Не загружены настройки рубрики, обновите страницу", "error");
    return;
  }
  const topic = state.topic || "english learning";
  const prompt = (full.image_prompt_template || "").replaceAll("{topic}", topic);

  $("#image-status").textContent = "Генерирую картинку через Kling (до 1–2 минут)…";
  const btn = $("#btn-generate-image");
  btn.disabled = true;
  try {
    const data = await api.generateImage({ prompt, aspect_ratio: "1:1" });
    state.imagePath = data.image_path;
    state.imageSource = "kling";
    state.imagePrompt = prompt;
    $("#image-status").textContent = "Готово";
    renderPreview();
    toast("Картинка готова", "success");
  } catch (e) {
    $("#image-status").textContent = "";
    toast(e.message, "error");
  } finally {
    btn.disabled = false;
  }
}

async function onUploadImage(ev) {
  const file = ev.target.files && ev.target.files[0];
  if (!file) return;
  $("#image-status").textContent = "Загружаю…";
  try {
    const data = await api.uploadImage(file);
    state.imagePath = data.image_path;
    state.imageSource = "manual_upload";
    state.imagePrompt = null;
    $("#image-status").textContent = "Загружено";
    renderPreview();
    toast("Картинка загружена", "success");
  } catch (e) {
    $("#image-status").textContent = "";
    toast(e.message, "error");
  } finally {
    ev.target.value = "";
  }
}

async function onSavePost() {
  if (!state.selectedRubric) { toast("Выберите рубрику", "error"); return; }
  state.text = $("#post-text").value.trim();
  if (!state.text) { toast("Текст пуст", "error"); return; }

  const body = {
    rubric_key: state.selectedRubric,
    topic: $("#topic").value.trim() || null,
    text_content: state.text,
    image_path: state.imagePath,
    image_prompt: state.imagePrompt,
    image_source: state.imageSource,
  };

  try {
    let data;
    if (state.editingPostId) {
      data = await api.postUpdate(state.editingPostId, body);
      toast("Черновик обновлён", "success");
    } else {
      data = await api.postCreate(body);
      state.editingPostId = data.id;
      toast("Черновик сохранён", "success");
    }
  } catch (e) {
    toast(e.message, "error");
  }
}

function resetEditor() {
  state.editingPostId = null;
  state.selectedRubric = null;
  state.topic = "";
  state.text = "";
  state.imagePath = null;
  state.imageSource = "none";
  state.imagePrompt = null;
  $("#topic").value = "";
  $("#post-text").value = "";
  $("#image-status").textContent = "";
  renderRubrics();
  renderPreview();
}

// ============================================================
// library (вкладка «Библиотека»)
// ============================================================
async function renderLibrary() {
  const search = $("#lib-search").value.trim();
  const rubric_key = $("#lib-rubric").value;
  let items = [];
  try {
    items = await api.postsList({ search, rubric_key });
  } catch (e) {
    toast(e.message, "error");
    return;
  }
  const root = $("#library-grid");
  root.innerHTML = "";
  $("#library-empty").hidden = items.length > 0;
  items.forEach(p => {
    const r = rubricByKey(p.rubric_key);
    const card = document.createElement("article");
    card.className = "lib-card";
    const img = p.image_path
      ? `<img class="lib-card__img" src="/static/uploads/${p.image_path}" alt="">`
      : `<div class="lib-card__img lib-card__img--empty">нет картинки</div>`;
    const date = p.created_at ? p.created_at.slice(0, 10) : "";
    const rname = r ? `${r.emoji || ""} ${r.name}` : p.rubric_key;
    const preview = (p.text_content || "").slice(0, 180).replaceAll("<", "&lt;");
    card.innerHTML = `
      ${img}
      <div class="lib-card__body">
        <div class="lib-card__meta"><span>${rname}</span><span class="muted">${date}</span></div>
        <div class="lib-card__topic">${p.topic ? p.topic.replaceAll("<","&lt;") : ""}</div>
        <div class="lib-card__text">${preview}…</div>
        <div class="lib-card__actions">
          <button class="btn btn--ghost btn--sm" data-act="open">Открыть</button>
          <button class="btn btn--ghost btn--sm btn--danger" data-act="delete">Удалить</button>
        </div>
      </div>`;
    card.querySelector('[data-act="open"]').onclick = () => openPostInEditor(p.id);
    card.querySelector('[data-act="delete"]').onclick = () => deletePostFromLib(p.id);
    root.appendChild(card);
  });
}

async function openPostInEditor(id) {
  try {
    const p = await api.postGet(id);
    state.editingPostId = p.id;
    state.selectedRubric = p.rubric_key;
    state.topic = p.topic || "";
    state.text = p.text_content || "";
    state.imagePath = p.image_path || null;
    state.imageSource = p.image_source || "none";
    state.imagePrompt = p.image_prompt || null;
    $("#topic").value = state.topic;
    $("#post-text").value = state.text;
    $("#image-status").textContent = state.imagePath ? "Картинка из черновика" : "";
    renderRubrics();
    renderPreview();
    switchTab("create");
  } catch (e) {
    toast(e.message, "error");
  }
}

async function deletePostFromLib(id) {
  if (!confirm("Удалить черновик? Это действие нельзя отменить.")) return;
  try {
    await api.postDelete(id);
    toast("Удалено", "success");
    renderLibrary();
  } catch (e) {
    toast(e.message, "error");
  }
}

// ============================================================
// settings (вкладка «Настройки»)
// ============================================================
async function renderSettings() {
  let items = [];
  try {
    items = await api.rubricsFull();
    state.rubricsFull = items;
  } catch (e) {
    toast(e.message, "error");
    return;
  }
  const root = $("#settings-list");
  root.innerHTML = "";
  items.forEach(r => {
    const card = document.createElement("article");
    card.className = "settings-card";
    card.innerHTML = `
      <header class="settings-card__head">
        <input class="input settings-card__emoji" value="${r.emoji || ""}" maxlength="4">
        <input class="input settings-card__name" value="${r.name.replaceAll('"','&quot;')}">
        <code class="muted small">${r.key}</code>
      </header>
      <label class="label">Системный промпт (для генерации текста)</label>
      <textarea class="textarea settings-card__sp" rows="14"></textarea>
      <label class="label">Шаблон промпта картинки (для Kling, можно использовать {topic})</label>
      <textarea class="textarea settings-card__ip" rows="4"></textarea>
      <button class="btn btn--primary settings-card__save">Сохранить</button>
    `;
    card.querySelector(".settings-card__sp").value = r.system_prompt || "";
    card.querySelector(".settings-card__ip").value = r.image_prompt_template || "";
    card.querySelector(".settings-card__save").onclick = async () => {
      const body = {
        emoji: card.querySelector(".settings-card__emoji").value,
        name: card.querySelector(".settings-card__name").value.trim(),
        system_prompt: card.querySelector(".settings-card__sp").value,
        image_prompt_template: card.querySelector(".settings-card__ip").value,
      };
      try {
        await api.rubricUpdate(r.key, body);
        toast("Сохранено", "success");
        await loadRubrics();
      } catch (e) { toast(e.message, "error"); }
    };
    root.appendChild(card);
  });
}

// ============================================================
// tabs
// ============================================================
function switchTab(name) {
  state.activeTab = name;
  $$(".tab").forEach(t => t.classList.toggle("is-active", t.dataset.tab === name));
  $$(".view").forEach(v => v.classList.toggle("is-active", v.dataset.view === name));
  if (name === "library") renderLibrary();
  if (name === "settings") renderSettings();
}

// ============================================================
// init
// ============================================================
async function loadRubrics() {
  try {
    state.rubrics = await api.rubrics();
    state.rubricsFull = await api.rubricsFull();
    // заполняем select в библиотеке
    const sel = $("#lib-rubric");
    sel.innerHTML = '<option value="">Все рубрики</option>' +
      state.rubrics.map(r => `<option value="${r.key}">${r.emoji || ""} ${r.name}</option>`).join("");
    renderRubrics();
  } catch (e) {
    toast(e.message, "error");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  $$(".tab").forEach(t => t.addEventListener("click", () => switchTab(t.dataset.tab)));

  $("#btn-generate-text").addEventListener("click", onGenerateText);
  $("#btn-regenerate-text").addEventListener("click", onGenerateText);
  $("#btn-generate-image").addEventListener("click", onGenerateImage);
  $("#file-upload").addEventListener("change", onUploadImage);
  $("#btn-save").addEventListener("click", onSavePost);
  $("#post-text").addEventListener("input", (e) => {
    state.text = e.target.value;
    renderPreview();
  });
  $("#topic").addEventListener("input", (e) => { state.topic = e.target.value; });

  $("#btn-lib-refresh").addEventListener("click", renderLibrary);
  $("#lib-search").addEventListener("input", debounce(renderLibrary, 300));
  $("#lib-rubric").addEventListener("change", renderLibrary);

  loadRubrics();
});

function debounce(fn, ms) {
  let t = null;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}
