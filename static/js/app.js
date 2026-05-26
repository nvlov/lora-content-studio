// Lora Content Studio — клиент на ванильном JS (v0.3.2).
// Новая структура: Создать пост / Видео / Изображение / Библиотека / Настройки.
// Видео и Изображение — workflow: промпт → копируешь → внешний Kling → загрузка результата → оценка.

// ============================================================
// Иконки (inline SVG, Lucide-style)
// ============================================================
const ICONS = {
  sparkles: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/></svg>',
  refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 1-15.4 6.4L3 16M3 12a9 9 0 0 1 15.4-6.4L21 8"/><path d="M21 3v5h-5M3 21v-5h5"/></svg>',
  upload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>',
  download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
  save: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>',
  send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>',
  clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
  edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
  copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
  link: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>',
  external: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>',
  plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
  warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01"/></svg>',
  x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
  info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
  settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
  star: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
  starEmpty: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
};

function applyIcons() {
  document.querySelectorAll('[data-icon]').forEach(el => {
    const name = el.dataset.icon;
    if (ICONS[name] && !el.dataset.iconApplied) {
      el.innerHTML = ICONS[name];
      el.dataset.iconApplied = '1';
    }
  });
}

// ============================================================
// state
// ============================================================
const state = {
  rubrics: [],
  rubricsFull: [],
  selectedRubric: null,
  topic: "",
  freeTopic: "",
  text: "",
  editingPostId: null,
  parentPostId: null,
  parentInfo: null,
  activeTab: "create",
  vkConfigured: false,
  vkGroupId: 0,
  isDirty: false,
  // последние сгенерированные промпты (для привязки к загружаемым файлам)
  currentVideoPrompt: null,   // {prompt_id, prompt, negative_prompt, kling_hint}
  currentImagePrompt: null,
  videoMode: "silent",
};

// ============================================================
// helpers
// ============================================================
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

function toast(message, kind = "info", duration = 5000) {
  const root = $("#toast-container");
  const t = document.createElement("div");
  t.className = `toast toast--${kind}`;
  const icon = { success: 'check', error: 'warn', warn: 'warn', info: 'info' }[kind] || 'info';
  t.innerHTML = `<span class="icon icon--sm">${ICONS[icon] || ''}</span><span class="toast__msg"></span>`;
  t.querySelector('.toast__msg').textContent = message;
  t.onclick = () => removeToast(t);
  root.appendChild(t);
  void t.offsetWidth;
  t.classList.add('is-shown');
  setTimeout(() => removeToast(t), duration);
}
function removeToast(t) {
  t.classList.remove('is-shown');
  setTimeout(() => t.remove(), 250);
}

function confirmModal({ title = 'Подтверждение', message = '', confirmLabel = 'OK', cancelLabel = 'Отмена', extraHTML = '', danger = false } = {}) {
  return new Promise((resolve) => {
    const overlay = $("#modal-overlay");
    $("#modal-title").textContent = title;
    $("#modal-message").textContent = message;
    $("#modal-extra").innerHTML = extraHTML;
    const okBtn = $("#modal-confirm");
    const cancelBtn = $("#modal-cancel");
    okBtn.textContent = confirmLabel;
    cancelBtn.textContent = cancelLabel;
    okBtn.classList.toggle('btn--danger-solid', danger);
    overlay.hidden = false;

    const cleanup = () => {
      overlay.hidden = true;
      okBtn.onclick = cancelBtn.onclick = null;
      document.removeEventListener('keydown', onKey);
    };
    const onKey = (e) => {
      if (e.key === 'Escape') { cleanup(); resolve(false); }
      else if (e.key === 'Enter' && !e.target.matches('textarea')) { cleanup(); resolve(true); }
    };
    okBtn.onclick = () => { cleanup(); resolve(true); };
    cancelBtn.onclick = () => { cleanup(); resolve(false); };
    document.addEventListener('keydown', onKey);
    setTimeout(() => okBtn.focus(), 30);
  });
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

function debounce(fn, ms) {
  let t = null;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

async function copyToClipboard(text, successMsg = 'Скопировано') {
  try {
    await navigator.clipboard.writeText(text);
    toast(successMsg, 'success', 2000);
  } catch (e) {
    toast('Не удалось скопировать: ' + e.message, 'error');
  }
}

// ============================================================
// API
// ============================================================
const api = {
  rubrics: () => jsonFetch("/api/rubrics"),
  rubricsFull: () => jsonFetch("/api/settings/rubrics"),
  rubricUpdate: (key, body) =>
    jsonFetch(`/api/settings/rubrics/${encodeURIComponent(key)}`, {
      method: "PATCH", body: JSON.stringify(body),
    }),
  generateText: (body) =>
    jsonFetch("/api/generate-text", { method: "POST", body: JSON.stringify(body) }),
  postsList: (q) => {
    const params = new URLSearchParams();
    Object.entries(q || {}).forEach(([k, v]) => { if (v) params.set(k, v); });
    return jsonFetch("/api/posts?" + params.toString());
  },
  postCreate: (body) => jsonFetch("/api/posts", { method: "POST", body: JSON.stringify(body) }),
  postUpdate: (id, body) => jsonFetch(`/api/posts/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  postGet: (id) => jsonFetch(`/api/posts/${id}`),
  postDelete: (id) => jsonFetch(`/api/posts/${id}`, { method: "DELETE" }),
  postDuplicate: (id) => jsonFetch(`/api/posts/${id}/duplicate`, { method: "POST" }),
  postPublishNow: (id) => jsonFetch(`/api/posts/${id}/publish-now`, { method: "POST" }),
  postSchedule: (id, scheduled_at) =>
    jsonFetch(`/api/posts/${id}/schedule`, { method: "POST", body: JSON.stringify({ scheduled_at }) }),
  postUnschedule: (id) => jsonFetch(`/api/posts/${id}/schedule`, { method: "DELETE" }),
  vkStatus: () => jsonFetch("/api/vk/status"),
  generateKlingPrompt: (body) =>
    jsonFetch("/api/media/generate-kling-prompt", { method: "POST", body: JSON.stringify(body) }),
  generateImageDirect: (body) =>
    jsonFetch("/api/media/generate-image", { method: "POST", body: JSON.stringify(body) }),
  mediaUpload: async (file, sourcePromptId) => {
    const fd = new FormData();
    fd.append("file", file);
    if (sourcePromptId) fd.append("source_prompt_id", String(sourcePromptId));
    const r = await fetch("/api/media/upload", { method: "POST", body: fd });
    let data = null; try { data = await r.json(); } catch (_) {}
    if (!r.ok) throw new Error((data && data.error) || `Ошибка ${r.status}`);
    return data;
  },
  mediaList: (kind) => jsonFetch("/api/media" + (kind ? `?kind=${encodeURIComponent(kind)}` : "")),
  mediaGet: (id) => jsonFetch(`/api/media/${id}`),
  mediaUpdate: (id, body) =>
    jsonFetch(`/api/media/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  mediaDelete: (id) => jsonFetch(`/api/media/${id}`, { method: "DELETE" }),
  loraEmotions: () => jsonFetch("/api/media/lora-emotions"),
};

function rubricByKey(key) {
  return state.rubrics.find(r => r.key === key) || null;
}
function isFreeTopic(key) { return key === 'free_topic'; }

// ============================================================
// EDITOR — Создать пост (только текст)
// ============================================================
function renderRubrics() {
  const root = $("#rubrics-list");
  root.innerHTML = "";
  state.rubrics.forEach(r => {
    const btn = document.createElement("button");
    btn.className = "rubric" + (state.selectedRubric === r.key ? " is-selected" : "");
    const nameSpan = document.createElement('span');
    nameSpan.className = 'rubric__name';
    nameSpan.textContent = r.name;
    btn.innerHTML = `<span class="rubric__emoji">${r.emoji || ""}</span>`;
    btn.appendChild(nameSpan);
    btn.onclick = () => {
      state.selectedRubric = r.key;
      const isFree = isFreeTopic(r.key);
      $("#topic-block").hidden = isFree;
      $("#free-topic-block").hidden = !isFree;
      renderRubrics();
    };
    root.appendChild(btn);
  });
}

function updateCharCounter() {
  const text = $("#post-text").value;
  const len = text.length;
  $("#char-count").textContent = len;
  const cnt = $("#char-counter");
  cnt.classList.remove('is-warn', 'is-error');
  if (len > 4000) cnt.classList.add('is-error');
  else if (len >= 3500) cnt.classList.add('is-warn');
  const tooLong = len > 4000;
  $("#btn-publish-now").disabled = tooLong || !state.vkConfigured || !state.editingPostId;
  $("#btn-schedule").disabled = tooLong || !state.vkConfigured || !state.editingPostId;
}

function setText(text) {
  state.text = text;
  $("#post-text").value = text;
  state.isDirty = true;
  updateCharCounter();
}

function getCurrentTopic() {
  return isFreeTopic(state.selectedRubric)
    ? $("#free-topic").value.trim()
    : $("#topic").value.trim();
}

async function onGenerateText() {
  if (!state.selectedRubric) { toast("Выбери рубрику", "error"); return; }
  const topic = getCurrentTopic();
  if (isFreeTopic(state.selectedRubric) && !topic) {
    toast("Опиши задачу для свободной рубрики", "error"); return;
  }
  state.topic = topic;
  const btn = $("#btn-generate-text");
  setBusy(btn, true, "Генерирую…");
  try {
    const data = await api.generateText({ rubric_key: state.selectedRubric, topic });
    setText(data.text);
    toast("Текст сгенерирован", "success");
  } catch (e) {
    toast(e.message, "error");
  } finally { setBusy(btn, false); }
}

function setBusy(btn, busy, label) {
  if (busy) {
    if (!btn.dataset._origHTML) btn.dataset._origHTML = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span><span>${label || 'Идёт операция…'}</span>`;
  } else {
    btn.disabled = false;
    if (btn.dataset._origHTML) {
      btn.innerHTML = btn.dataset._origHTML;
      delete btn.dataset._origHTML;
    }
  }
}

async function onSavePost() {
  if (!state.selectedRubric) { toast("Выбери рубрику", "error"); return; }
  state.text = $("#post-text").value.trim();
  if (!state.text) { toast("Текст пуст", "error"); return; }
  if (state.text.length > 4096) { toast("Текст длиннее 4096 символов — VK не примет", "error"); return; }

  const body = {
    rubric_key: state.selectedRubric,
    topic: getCurrentTopic() || null,
    text_content: state.text,
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
    state.isDirty = false;
    updateCharCounter();
  } catch (e) { toast(e.message, "error"); }
}

async function onPublishNow() {
  if (!state.editingPostId) { toast("Сначала сохрани черновик", "warn"); return; }
  const ok = await confirmModal({
    title: 'Опубликовать в VK?',
    message: 'Опубликовать пост в сообществе прямо сейчас? Редактировать после публикации можно только в самом VK.',
    confirmLabel: 'Опубликовать',
  });
  if (!ok) return;
  const btn = $("#btn-publish-now");
  setBusy(btn, true, "Публикую…");
  try {
    const data = await api.postPublishNow(state.editingPostId);
    toast(`Опубликовано: ${data.vk_post_url}`, "success", 8000);
    window.open(data.vk_post_url, '_blank');
  } catch (e) { toast(e.message, "error", 8000); }
  finally { setBusy(btn, false); }
}

async function onSchedule() {
  if (!state.editingPostId) { toast("Сначала сохрани черновик", "warn"); return; }
  const minDt = new Date(Date.now() + 10 * 60 * 1000);
  const minIso = toLocalDatetimeInput(minDt);
  const html = `
    <label class="label">Когда опубликовать (минимум +10 минут)</label>
    <input type="datetime-local" id="schedule-input" class="input" value="${minIso}" min="${minIso}">
  `;
  const ok = await confirmModal({
    title: 'Запланировать публикацию',
    message: 'Пост опубликуется автоматически в указанное время. Программа должна быть запущена (либо догонит при следующем запуске).',
    confirmLabel: 'Запланировать',
    extraHTML: html,
  });
  if (!ok) return;
  const val = $("#schedule-input")?.value;
  if (!val) { toast("Не указана дата", "error"); return; }
  const localDate = new Date(val);
  if (isNaN(localDate)) { toast("Некорректная дата", "error"); return; }
  if (localDate.getTime() < Date.now() + 5 * 60 * 1000) {
    toast("Время должно быть минимум через 5 минут", "error"); return;
  }
  try {
    await api.postSchedule(state.editingPostId, localDate.toISOString());
    toast(`Запланировано на ${localDate.toLocaleString('ru-RU')}`, "success");
    if (state.activeTab === 'library') renderLibrary();
  } catch (e) { toast(e.message, "error"); }
}

function toLocalDatetimeInput(d) {
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}

function resetEditor() {
  state.editingPostId = null;
  state.selectedRubric = null;
  state.topic = "";
  state.freeTopic = "";
  state.text = "";
  state.parentPostId = null;
  state.parentInfo = null;
  state.isDirty = false;
  $("#topic").value = "";
  $("#free-topic").value = "";
  $("#post-text").value = "";
  $("#parent-info").hidden = true;
  $("#topic-block").hidden = false;
  $("#free-topic-block").hidden = true;
  renderRubrics();
  updateCharCounter();
}

// ============================================================
// LIBRARY (posts)
// ============================================================
function statusBadge(p) {
  const map = {
    draft: { cls: 'badge--draft', label: 'Черновик' },
    scheduled: { cls: 'badge--scheduled', label: 'Запланировано' },
    published: { cls: 'badge--published', label: 'Опубликовано' },
    publish_failed: { cls: 'badge--failed', label: 'Ошибка' },
  };
  const m = map[p.status] || map.draft;
  let extra = '';
  if (p.status === 'scheduled' && p.scheduled_at) {
    extra = ` · ${new Date(p.scheduled_at).toLocaleString('ru-RU')}`;
  } else if (p.status === 'published' && p.published_at) {
    extra = ` · ${new Date(p.published_at).toLocaleDateString('ru-RU')}`;
  }
  return `<span class="badge ${m.cls}">${m.label}${extra}</span>`;
}

function iconBtn(icon, title, onclick, danger = false) {
  const b = document.createElement('button');
  b.className = 'icon-btn' + (danger ? ' icon-btn--danger' : '');
  b.title = title; b.setAttribute('aria-label', title);
  b.innerHTML = `<span class="icon">${ICONS[icon] || ''}</span>`;
  b.onclick = onclick;
  return b;
}

async function renderLibrary() {
  const search = $("#lib-search").value.trim();
  const rubric_key = $("#lib-rubric").value;
  const status = $("#lib-status").value;
  let items = [];
  try { items = await api.postsList({ search, rubric_key, status }); }
  catch (e) { toast(e.message, "error"); return; }
  const root = $("#library-grid");
  root.innerHTML = "";
  $("#library-empty").hidden = items.length > 0;
  items.forEach(p => {
    const r = rubricByKey(p.rubric_key);
    const card = document.createElement("article");
    card.className = "lib-card";
    const date = p.created_at ? p.created_at.slice(0, 10) : "";
    const rname = r ? `${r.emoji || ""} ${r.name}` : p.rubric_key;

    const meta = document.createElement('div');
    meta.className = 'lib-card__meta';
    meta.innerHTML = `<span>${rname}</span><span>${date}</span>`;
    card.appendChild(meta);

    const badge = document.createElement('div');
    badge.innerHTML = statusBadge(p);
    card.appendChild(badge);

    if (p.topic) {
      const t = document.createElement('div');
      t.className = 'lib-card__topic';
      t.textContent = p.topic.length > 80 ? p.topic.slice(0, 80) + '…' : p.topic;
      card.appendChild(t);
    }

    const txt = document.createElement('div');
    txt.className = 'lib-card__text';
    txt.textContent = (p.text_content || "").slice(0, 220) + ((p.text_content || "").length > 220 ? '…' : '');
    card.appendChild(txt);

    if (p.last_publish_error) {
      const errEl = document.createElement('div');
      errEl.className = 'lib-card__err';
      errEl.textContent = `Ошибка: ${p.last_publish_error.slice(0, 120)}`;
      card.appendChild(errEl);
    }

    const actions = document.createElement('div');
    actions.className = 'lib-card__actions';
    actions.appendChild(iconBtn('edit', 'Открыть', () => openPostInEditor(p.id)));
    actions.appendChild(iconBtn('copy', 'Создать на основе', () => duplicatePost(p.id)));
    if (p.vk_post_url) {
      const a = document.createElement('a');
      a.className = 'icon-btn';
      a.href = p.vk_post_url; a.target = '_blank';
      a.title = 'Открыть в ВК';
      a.innerHTML = `<span class="icon">${ICONS.link}</span>`;
      actions.appendChild(a);
    }
    if (p.status === 'publish_failed') {
      actions.appendChild(iconBtn('refresh', 'Повторить публикацию', () => retryPublish(p.id)));
    }
    if (p.status === 'scheduled') {
      actions.appendChild(iconBtn('x', 'Отменить расписание', () => cancelSchedule(p.id)));
    }
    actions.appendChild(iconBtn('trash', 'Удалить', () => deletePostFromLib(p.id), true));
    card.appendChild(actions);

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
    state.parentPostId = p.parent_post_id || null;
    state.isDirty = false;

    const isFree = isFreeTopic(p.rubric_key);
    $("#topic-block").hidden = isFree;
    $("#free-topic-block").hidden = !isFree;
    if (isFree) $("#free-topic").value = state.topic;
    else $("#topic").value = state.topic;
    $("#post-text").value = state.text;

    const pi = $("#parent-info");
    if (p.parent_post_id) {
      pi.textContent = `Создан на основе поста #${p.parent_post_id}`;
      pi.hidden = false;
    } else { pi.hidden = true; }

    renderRubrics();
    updateCharCounter();
    switchTab("create");
  } catch (e) { toast(e.message, "error"); }
}

async function duplicatePost(id) {
  try {
    const data = await api.postDuplicate(id);
    toast("Создан новый черновик на основе", "success");
    await openPostInEditor(data.id);
  } catch (e) { toast(e.message, "error"); }
}

async function deletePostFromLib(id) {
  const ok = await confirmModal({
    title: 'Удалить черновик?',
    message: 'Черновик помечается удалённым (soft-delete) — данные остаются в БД, в библиотеке не отображаются.',
    confirmLabel: 'Удалить',
    danger: true,
  });
  if (!ok) return;
  try { await api.postDelete(id); toast("Удалено", "success"); renderLibrary(); }
  catch (e) { toast(e.message, "error"); }
}

async function cancelSchedule(id) {
  try { await api.postUnschedule(id); toast("Расписание отменено", "success"); renderLibrary(); }
  catch (e) { toast(e.message, "error"); }
}

async function retryPublish(id) {
  try {
    const data = await api.postPublishNow(id);
    toast(`Опубликовано: ${data.vk_post_url}`, "success", 8000);
    renderLibrary();
  } catch (e) { toast(e.message, "error", 8000); }
}

// ============================================================
// VIDEO TAB
// ============================================================
function setupVideoTab() {
  // Переключатель режима
  $$('input[name="video-mode"]').forEach(r => {
    r.addEventListener('change', () => {
      state.videoMode = r.value;
      $("#video-speech-block").hidden = r.value !== 'audio_en';
      $$('#video-mode-radio .mode-radio__option').forEach(opt => opt.classList.remove('is-selected'));
      r.closest('.mode-radio__option').classList.add('is-selected');
    });
  });

  $("#btn-generate-video-prompt").addEventListener('click', onGenerateVideoPrompt);
  $("#btn-copy-video-prompt").addEventListener('click', () => {
    if (state.currentVideoPrompt) copyToClipboard(state.currentVideoPrompt.prompt, 'Промпт скопирован');
  });
  $("#btn-copy-video-negative").addEventListener('click', () => {
    if (state.currentVideoPrompt && state.currentVideoPrompt.negative_prompt) {
      copyToClipboard(state.currentVideoPrompt.negative_prompt, 'Negative скопирован');
    } else { toast('Negative пустой', 'info', 2000); }
  });

  setupDropzone($("#video-dropzone"), $("#video-file-input"), 'video');
  $("#btn-video-refresh").addEventListener('click', renderVideoHistory);
  $("#video-history-filter").addEventListener('change', renderVideoHistory);
}


const EMOTION_LABELS_RU = {
  greetings: 'Приветствие',
  praises:   'Похвала',
  corrects:  'Поправка',
  explains:  'Объяснение',
  thinks:    'Размышление',
  surprise:  'Удивление',
  neutral:   'Нейтральная поза',
};

async function populateLoraEmotionDropdowns() {
  let emotions = [];
  try { emotions = await api.loraEmotions(); }
  catch (e) { console.warn('Эмоции Лоры недоступны:', e.message); return; }

  const selects = document.querySelectorAll('select[data-lora-emotion]');
  selects.forEach(sel => {
    sel.innerHTML = '';
    const noneOpt = document.createElement('option');
    noneOpt.value = '__none__';
    noneOpt.textContent = '— без референса —';
    sel.appendChild(noneOpt);
    emotions.forEach(e => {
      if (!e.available) return;
      const opt = document.createElement('option');
      opt.value = e.key;
      opt.textContent = EMOTION_LABELS_RU[e.key] || e.key;
      opt.title = e.description;
      if (e.key === 'greetings') opt.selected = true;
      sel.appendChild(opt);
    });
  });
}

function readEmotionFromSelect(selectId) {
  const v = $(selectId)?.value || '';
  if (v === '__none__' || !v) return { emotion: null, use_reference: false };
  return { emotion: v, use_reference: true };
}

async function onGenerateVideoPrompt() {
  const idea = $("#video-idea").value.trim();
  if (!idea) { toast('Опиши идею', 'error'); return; }
  const mode = state.videoMode;
  let dialog_en = '';
  let voice_tone = '';
  if (mode === 'audio_en') {
    dialog_en = $("#video-dialog").value.trim();
    voice_tone = $("#video-voice-tone").value;
    if (!dialog_en) { toast('Введи реплику на английском', 'error'); return; }
  }
  const emo = readEmotionFromSelect('#video-emotion');
  const body = {
    idea_ru: idea,
    media_type: 'video',
    style: $("#video-style").value,
    aspect_ratio: $("#video-aspect").value,
    duration: parseInt($("#video-duration").value, 10),
    camera_movement: $("#video-camera").value,
    video_mode: mode,
    dialog_en,
    voice_tone,
    user_negative_ru: $("#video-negative").value.trim(),
    emotion: emo.emotion,
    use_reference: emo.use_reference,
  };
  const btn = $("#btn-generate-video-prompt");
  setBusy(btn, true, 'Генерирую промпт…');
  $("#video-prompt-status").textContent = 'Это занимает 5-15 секунд…';
  try {
    const data = await api.generateKlingPrompt(body);
    state.currentVideoPrompt = data;
    $("#video-prompt-text").textContent = data.prompt;
    $("#video-prompt-hint").textContent = _hintWithEmotion(data);
    $("#video-prompt-result").hidden = false;
    $("#video-prompt-status").textContent = '';
    toast('Промпт готов', 'success');
  } catch (e) {
    $("#video-prompt-status").textContent = '';
    toast(e.message, 'error');
  } finally { setBusy(btn, false); }
}

function _hintWithEmotion(data) {
  const base = data.kling_hint || '';
  if (!data.reference_emotion) return base;
  const ru = EMOTION_LABELS_RU[data.reference_emotion] || data.reference_emotion;
  return `Референс: ${ru}` + (base ? ` · ${base}` : '');
}

async function renderVideoHistory() {
  const filter = $("#video-history-filter").value;  // '', 'silent', 'audio_en'
  let items = [];
  try { items = await api.mediaList('video'); }
  catch (e) { toast(e.message, 'error'); return; }
  // Подтягиваем source_prompt для фильтрации по video_mode
  // Для простоты — если фильтр пустой, показываем всё.
  // Если фильтр выставлен — оставляем те, чей source_prompt.video_mode совпадает.
  let filtered = items;
  if (filter) {
    const detailed = await Promise.all(items.map(async a => {
      if (!a.source_prompt_id) return null;
      try {
        const full = await api.mediaGet(a.id);
        return full;
      } catch (_) { return null; }
    }));
    filtered = detailed.filter(d => d && d.source_prompt && d.source_prompt.video_mode === filter);
  }
  const grid = $("#video-history-grid");
  grid.innerHTML = '';
  $("#video-history-empty").hidden = filtered.length > 0;
  filtered.forEach(a => grid.appendChild(renderMediaCardWithRating(a, 'video')));
}

// ============================================================
// IMAGE TAB
// ============================================================
function setupImageTab() {
  $("#btn-generate-image-prompt").addEventListener('click', onGenerateImagePrompt);
  $("#btn-generate-image-direct").addEventListener('click', () => onGenerateImageDirect({ fromPrompt: false }));
  $("#btn-render-from-prompt").addEventListener('click', () => onGenerateImageDirect({ fromPrompt: true }));
  $("#btn-copy-image-prompt").addEventListener('click', () => {
    if (state.currentImagePrompt) copyToClipboard(state.currentImagePrompt.prompt, 'Промпт скопирован');
  });

  $("#btn-image-refresh").addEventListener('click', renderImageHistory);
}

// Получает aspect_ratio из текущего size-preset (для запроса промпта у Claude).
function _sizePresetToAspect(preset) {
  switch (preset) {
    case 'vertical':   return '2:3';
    case 'horizontal': return '3:2';
    case 'auto':       return '1:1';
    default:           return '1:1';
  }
}

async function onGenerateImagePrompt() {
  const idea = $("#image-idea").value.trim();
  if (!idea) { toast('Опиши идею', 'error'); return; }
  const sizePreset = $("#image-size").value;
  const emo = readEmotionFromSelect('#image-emotion');
  const body = {
    idea_ru: idea,
    media_type: 'image',
    target: 'gpt_image_2',
    style: $("#image-style").value,
    aspect_ratio: _sizePresetToAspect(sizePreset),
    user_negative_ru: $("#image-negative").value.trim(),
    emotion: emo.emotion,
    use_reference: emo.use_reference,
  };
  const btn = $("#btn-generate-image-prompt");
  setBusy(btn, true, 'Генерирую промпт…');
  $("#image-prompt-status").textContent = 'Это занимает 5-10 секунд…';
  try {
    const data = await api.generateKlingPrompt(body);
    state.currentImagePrompt = data;
    $("#image-prompt-text").textContent = data.prompt;
    $("#image-prompt-hint").textContent = _hintWithEmotion(data);
    $("#image-prompt-result").hidden = false;
    $("#image-prompt-status").textContent = '';
    toast('Промпт готов — можно скопировать или сразу сгенерировать изображение', 'success');
  } catch (e) {
    $("#image-prompt-status").textContent = '';
    toast(e.message, 'error');
  } finally { setBusy(btn, false); }
}

// Прямая генерация через gpt-image-2.
// fromPrompt=true → используем сохранённый state.currentImagePrompt.prompt_id
// fromPrompt=false → сначала генерим промпт из идеи (если ещё нет), затем картинку
async function onGenerateImageDirect({ fromPrompt }) {
  const sizePreset = $("#image-size").value;
  const quality = $("#image-quality").value;
  const btn = fromPrompt ? $("#btn-render-from-prompt") : $("#btn-generate-image-direct");

  let promptId = null;
  let rawPrompt = '';

  if (fromPrompt) {
    if (!state.currentImagePrompt || !state.currentImagePrompt.prompt_id) {
      toast('Сначала сгенерируй промпт', 'error');
      return;
    }
    promptId = state.currentImagePrompt.prompt_id;
  } else {
    // Если промпт уже есть — переиспользуем; иначе генерим
    if (state.currentImagePrompt && state.currentImagePrompt.prompt_id) {
      promptId = state.currentImagePrompt.prompt_id;
    } else {
      const idea = $("#image-idea").value.trim();
      if (!idea) { toast('Опиши идею или сгенерируй промпт', 'error'); return; }
      setBusy(btn, true, 'Готовлю промпт…');
      $("#image-prompt-status").textContent = 'Шаг 1/2: генерирую промпт…';
      const emo = readEmotionFromSelect('#image-emotion');
      try {
        const data = await api.generateKlingPrompt({
          idea_ru: idea,
          media_type: 'image',
          target: 'gpt_image_2',
          style: $("#image-style").value,
          aspect_ratio: _sizePresetToAspect(sizePreset),
          user_negative_ru: $("#image-negative").value.trim(),
          emotion: emo.emotion,
          use_reference: emo.use_reference,
        });
        state.currentImagePrompt = data;
        $("#image-prompt-text").textContent = data.prompt;
        $("#image-prompt-hint").textContent = _hintWithEmotion(data);
        $("#image-prompt-result").hidden = false;
        promptId = data.prompt_id;
      } catch (e) {
        $("#image-prompt-status").textContent = '';
        toast(e.message, 'error');
        setBusy(btn, false);
        return;
      }
    }
  }

  setBusy(btn, true, 'Генерирую изображение…');
  $("#image-prompt-status").textContent = `Шаг 2/2: gpt-image-2, качество «${quality}» — может занять до 5 минут…`;
  const emo2 = readEmotionFromSelect('#image-emotion');
  try {
    const asset = await api.generateImageDirect({
      prompt_id: promptId,
      size_preset: sizePreset,
      quality: quality,
      emotion: emo2.emotion,
      use_reference: emo2.use_reference,
    });
    $("#image-prompt-status").textContent = '';
    toast('Изображение готово', 'success');
    await renderImageHistory();
    // Прокручиваем к истории, чтобы сразу видеть результат
    const grid = $("#image-history-grid");
    if (grid) grid.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) {
    $("#image-prompt-status").textContent = '';
    toast(e.message, 'error');
  } finally { setBusy(btn, false); }
}

async function renderImageHistory() {
  let items = [];
  try { items = await api.mediaList('image'); }
  catch (e) { toast(e.message, 'error'); return; }
  const grid = $("#image-history-grid");
  grid.innerHTML = '';
  $("#image-history-empty").hidden = items.length > 0;
  items.forEach(a => grid.appendChild(renderMediaCardWithRating(a, 'image')));
}

// ============================================================
// Media card (с inline-рейтингом, ссылкой на промпт, скачиванием)
// ============================================================
function renderMediaCardWithRating(asset, kind) {
  const card = document.createElement('article');
  card.className = 'media-card';
  const url = asset.url || `/static/uploads/${asset.file_path}`;

  if (asset.kind === 'image') {
    const img = document.createElement('img');
    img.src = url; img.alt = asset.original_name || '';
    img.className = 'media-card__thumb';
    card.appendChild(img);
  } else {
    const v = document.createElement('video');
    v.src = url; v.className = 'media-card__thumb';
    v.preload = 'metadata'; v.muted = true;
    v.style.objectFit = 'cover';
    card.appendChild(v);
  }

  const body = document.createElement('div');
  body.className = 'media-card__body';

  const name = document.createElement('div');
  name.className = 'media-card__name';
  name.textContent = asset.original_name || asset.file_path;
  body.appendChild(name);

  const meta = document.createElement('div');
  meta.className = 'media-card__meta';
  const sizeMB = (asset.size_bytes / 1024 / 1024).toFixed(2);
  const dims = asset.width ? `${asset.width}×${asset.height}` : '';
  const datePart = asset.created_at ? asset.created_at.slice(0, 10) : '';
  meta.textContent = [sizeMB + ' МБ', dims, datePart].filter(Boolean).join(' · ');
  body.appendChild(meta);

  // Оценка качества: шкала -2..+2
  const rating = createRatingControl(asset.rating, async (val) => {
    try {
      await api.mediaUpdate(asset.id, { rating: val });
      asset.rating = val;
      toast(val === null ? 'Оценка снята' : 'Оценка сохранена', 'success', 2000);
    } catch (e) { toast(e.message, 'error'); }
  });
  body.appendChild(rating);

  // Заметки (textarea с debounce-сохранением)
  const notes = document.createElement('textarea');
  notes.className = 'textarea';
  notes.rows = 2;
  notes.placeholder = 'Заметка к результату…';
  notes.value = asset.feedback_notes || '';
  notes.style.fontSize = '0.82rem';
  notes.style.padding = '0.4rem 0.55rem';
  const saveNotes = debounce(async () => {
    try {
      await api.mediaUpdate(asset.id, { feedback_notes: notes.value });
      asset.feedback_notes = notes.value;
    } catch (e) { toast(e.message, 'error'); }
  }, 600);
  notes.addEventListener('input', saveNotes);
  body.appendChild(notes);

  // Действия
  const actions = document.createElement('div');
  actions.className = 'media-card__actions';

  // Скачать
  const dl = document.createElement('a');
  dl.className = 'icon-btn';
  dl.href = `/api/media/${asset.id}/download`;
  dl.title = 'Скачать';
  dl.setAttribute('aria-label', 'Скачать');
  dl.innerHTML = `<span class="icon">${ICONS.download}</span>`;
  actions.appendChild(dl);

  // Показать промпт (если есть)
  if (asset.source_prompt_id) {
    actions.appendChild(iconBtn('info', 'Показать промпт', () => showSourcePrompt(asset.id)));
  }

  actions.appendChild(iconBtn('trash', 'Удалить', async () => {
    const ok = await confirmModal({
      title: 'Удалить файл?',
      message: 'Файл пометится удалённым. Историю можно будет восстановить через БД.',
      confirmLabel: 'Удалить', danger: true,
    });
    if (!ok) return;
    try {
      await api.mediaDelete(asset.id);
      toast('Удалено', 'success');
      if (kind === 'video') renderVideoHistory(); else renderImageHistory();
    } catch (e) { toast(e.message, 'error'); }
  }, true));

  body.appendChild(actions);
  card.appendChild(body);
  return card;
}

const RATING_OPTIONS = [
  { value: -2, label: '−2', tone: 'neg-strong', title: '−2 — неприемлемо' },
  { value: -1, label: '−1', tone: 'neg',        title: '−1 — плохо' },
  { value:  0, label:  '0', tone: 'neutral',    title:  '0 — нейтрально' },
  { value:  1, label: '+1', tone: 'pos',        title: '+1 — хорошо' },
  { value:  2, label: '+2', tone: 'pos-strong', title: '+2 — в канал' },
];

function createRatingControl(currentValue, onChange) {
  const wrap = document.createElement('div');
  wrap.className = 'rating-control';
  wrap.setAttribute('role', 'radiogroup');
  wrap.setAttribute('aria-label', 'Оценка от −2 до +2');

  let value = (currentValue === undefined || currentValue === null) ? null : Number(currentValue);

  const render = () => {
    wrap.innerHTML = '';
    for (const opt of RATING_OPTIONS) {
      const btn = document.createElement('button');
      btn.type = 'button';
      const selected = (value === opt.value);
      btn.className = `rating-control__btn rating-control__btn--${opt.tone}` + (selected ? ' is-selected' : '');
      btn.setAttribute('role', 'radio');
      btn.setAttribute('aria-checked', selected ? 'true' : 'false');
      btn.title = selected ? `${opt.title} (клик — снять)` : opt.title;
      btn.textContent = opt.label;
      btn.onclick = async () => {
        const next = selected ? null : opt.value;
        value = next;
        render();
        await onChange(next);
      };
      wrap.appendChild(btn);
    }
  };

  render();
  return wrap;
}

async function showSourcePrompt(assetId) {
  try {
    const full = await api.mediaGet(assetId);
    const p = full.source_prompt;
    if (!p) { toast('Промпт не найден', 'warn'); return; }
    const meta = [];
    if (p.media_type === 'video') {
      meta.push(`${p.duration}с · ${p.aspect_ratio} · ${p.style}`);
      if (p.video_mode === 'audio_en') meta.push(`речь (${p.voice_tone || 'EN'})`);
      if (p.camera_movement) meta.push(`камера: ${p.camera_movement}`);
    } else {
      meta.push(`${p.aspect_ratio} · ${p.style}`);
    }
    const extraHTML = `
      <div class="muted small" style="margin-bottom:0.4rem;">${meta.join(' · ')}</div>
      <div class="muted small" style="margin-bottom:0.4rem;"><strong>Идея:</strong> ${escapeHtml(p.idea_ru)}</div>
      <div class="prompt-output" style="margin-bottom:0.5rem;">${escapeHtml(p.prompt_en)}</div>
      ${p.negative_prompt_en ? `<div class="muted small"><strong>Negative:</strong> ${escapeHtml(p.negative_prompt_en)}</div>` : ''}
    `;
    await confirmModal({
      title: 'Промпт',
      message: '',
      extraHTML,
      confirmLabel: 'Копировать промпт',
      cancelLabel: 'Закрыть',
    }).then(async (ok) => {
      if (ok) await copyToClipboard(p.prompt_en, 'Промпт скопирован');
    });
  } catch (e) { toast(e.message, 'error'); }
}

function escapeHtml(s) {
  return String(s || '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

// ============================================================
// Generic dropzone (используется для video и image upload)
// ============================================================
function setupDropzone(zone, fileInput, kind) {
  if (!zone) return;
  ['dragenter', 'dragover'].forEach(ev =>
    zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.add('is-active'); })
  );
  ['dragleave', 'drop'].forEach(ev =>
    zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.remove('is-active'); })
  );
  zone.addEventListener('drop', e => {
    const files = Array.from(e.dataTransfer.files || []);
    uploadMediaFiles(files, kind);
  });
  fileInput.addEventListener('change', e => {
    uploadMediaFiles(Array.from(e.target.files || []), kind);
    e.target.value = '';
  });
}

async function uploadMediaFiles(files, kind) {
  if (!files.length) return;
  const statusEl = $(kind === 'video' ? '#video-upload-status' : '#image-upload-status');
  const promptObj = kind === 'video' ? state.currentVideoPrompt : state.currentImagePrompt;
  const sourcePromptId = promptObj ? promptObj.prompt_id : null;
  let ok = 0, fail = 0;
  for (const f of files) {
    statusEl.textContent = `Загружаю: ${f.name}…`;
    try {
      await api.mediaUpload(f, sourcePromptId);
      ok++;
    } catch (e) {
      fail++; toast(`${f.name}: ${e.message}`, 'error', 7000);
    }
  }
  statusEl.textContent = `Загружено ${ok}${fail ? `, ошибок ${fail}` : ''}${sourcePromptId ? ' · привязано к текущему промпту' : ''}`;
  if (kind === 'video') renderVideoHistory(); else renderImageHistory();
}

// ============================================================
// SETTINGS
// ============================================================
async function renderSettings() {
  let items = [];
  try { items = await api.rubricsFull(); state.rubricsFull = items; }
  catch (e) { toast(e.message, "error"); return; }
  const root = $("#settings-list");
  root.innerHTML = "";
  items.forEach(r => {
    const card = document.createElement("article");
    card.className = "settings-card";
    card.innerHTML = `
      <header class="settings-card__head">
        <input class="input settings-card__emoji" maxlength="4">
        <input class="input settings-card__name">
        <code class="muted small">${r.key}</code>
      </header>
      <label class="label">Системный промпт</label>
      <textarea class="textarea settings-card__sp" rows="14"></textarea>
      <label class="label">Шаблон промпта картинки (legacy, можно использовать {topic})</label>
      <textarea class="textarea settings-card__ip" rows="3"></textarea>
      <div style="margin-top:0.6rem;">
        <button class="btn btn--primary settings-card__save">Сохранить</button>
      </div>
    `;
    card.querySelector(".settings-card__emoji").value = r.emoji || "";
    card.querySelector(".settings-card__name").value = r.name;
    card.querySelector(".settings-card__sp").value = r.system_prompt || "";
    card.querySelector(".settings-card__ip").value = r.image_prompt_template || "";
    card.querySelector(".settings-card__save").onclick = async () => {
      const body = {
        emoji: card.querySelector(".settings-card__emoji").value,
        name: card.querySelector(".settings-card__name").value.trim(),
        system_prompt: card.querySelector(".settings-card__sp").value,
        image_prompt_template: card.querySelector(".settings-card__ip").value,
      };
      try { await api.rubricUpdate(r.key, body); toast("Сохранено", "success"); await loadRubrics(); }
      catch (e) { toast(e.message, "error"); }
    };
    root.appendChild(card);
  });
}

// ============================================================
// TABS
// ============================================================
function switchTab(name) {
  state.activeTab = name;
  $$(".tab").forEach(t => {
    const active = t.dataset.tab === name;
    t.classList.toggle("is-active", active);
    t.setAttribute('aria-selected', String(active));
  });
  $$(".view").forEach(v => v.classList.toggle("is-active", v.dataset.view === name));
  if (name === "library") renderLibrary();
  if (name === "settings") renderSettings();
  if (name === "video") renderVideoHistory();
  if (name === "image") renderImageHistory();
}

// ============================================================
// INIT
// ============================================================
async function loadRubrics() {
  try {
    state.rubrics = await api.rubrics();
    state.rubricsFull = await api.rubricsFull();
    const sel = $("#lib-rubric");
    sel.innerHTML = '<option value="">Все рубрики</option>' +
      state.rubrics.map(r => `<option value="${r.key}">${r.emoji || ""} ${r.name}</option>`).join("");
    renderRubrics();
  } catch (e) { toast(e.message, "error"); }
}

async function loadVKStatus() {
  try {
    const data = await api.vkStatus();
    state.vkConfigured = !!data.configured;
    state.vkGroupId = data.group_id || 0;
    $("#vk-not-configured").hidden = state.vkConfigured;
    updateCharCounter();
  } catch (e) { /* silent */ }
}

document.addEventListener("DOMContentLoaded", () => {
  applyIcons();

  $$(".tab").forEach(t => t.addEventListener("click", () => switchTab(t.dataset.tab)));

  // Editor (post)
  $("#btn-generate-text").addEventListener("click", onGenerateText);
  $("#btn-regenerate-text").addEventListener("click", onGenerateText);
  $("#btn-save").addEventListener("click", onSavePost);
  $("#btn-publish-now").addEventListener("click", onPublishNow);
  $("#btn-schedule").addEventListener("click", onSchedule);
  $("#btn-new").addEventListener("click", () => { resetEditor(); toast("Редактор очищен", "info", 2000); });

  $("#post-text").addEventListener("input", (e) => {
    state.text = e.target.value;
    state.isDirty = true;
    updateCharCounter();
  });
  $("#topic").addEventListener("input", (e) => { state.topic = e.target.value; state.isDirty = true; });
  $("#free-topic").addEventListener("input", (e) => { state.freeTopic = e.target.value; state.isDirty = true; });

  // Library
  $("#btn-lib-refresh").addEventListener("click", renderLibrary);
  $("#lib-search").addEventListener("input", debounce(renderLibrary, 300));
  $("#lib-rubric").addEventListener("change", renderLibrary);
  $("#lib-status").addEventListener("change", renderLibrary);

  // Video & Image
  setupVideoTab();
  setupImageTab();

  // Hotkeys
  document.addEventListener('keydown', (e) => {
    if (e.target.matches('input, textarea, select') && !e.ctrlKey && !e.metaKey) return;
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && state.activeTab === 'create') {
      e.preventDefault(); onGenerateText();
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's' && state.activeTab === 'create') {
      e.preventDefault(); onSavePost();
    } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'p' && state.activeTab === 'create') {
      e.preventDefault(); onPublishNow();
    }
  });

  // beforeunload — предупреждение о несохранённых изменениях
  window.addEventListener('beforeunload', (e) => {
    if (state.isDirty) {
      e.preventDefault();
      e.returnValue = '';
    }
  });

  loadRubrics();
  loadVKStatus();
  populateLoraEmotionDropdowns();
  updateCharCounter();
});
