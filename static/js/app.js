// Lora Content Studio v0.2 — клиент на ванильном JS.

// ============================================================
// Иконки (Heroicons / Lucide-style, SVG inline)
// ============================================================
const ICONS = {
  sparkles: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/></svg>',
  refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 1-15.4 6.4L3 16M3 12a9 9 0 0 1 15.4-6.4L21 8"/><path d="M21 3v5h-5M3 21v-5h5"/></svg>',
  image: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/></svg>',
  upload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>',
  folder: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>',
  save: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>',
  send: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>',
  clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
  edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/></svg>',
  trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
  copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
  link: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>',
  plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
  check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
  warn: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0zM12 9v4M12 17h.01"/></svg>',
  x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
  info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>',
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
  imagePath: null,
  imageSource: "none",
  imagePrompt: null,
  videoPath: null,
  mediaKind: "none",
  editingPostId: null,
  parentPostId: null,
  parentInfo: null,           // {id, date}
  activeTab: "create",
  vkConfigured: false,
  vkGroupId: 0,
  isDirty: false,
  klingTimerId: null,
  klingTimerStart: 0,
};

// ============================================================
// helpers
// ============================================================
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

// ----- toast queue -----
function toast(message, kind = "info", duration = 5000) {
  const root = $("#toast-container");
  const t = document.createElement("div");
  t.className = `toast toast--${kind}`;
  const icon = { success: 'check', error: 'warn', warn: 'warn', info: 'info' }[kind] || 'info';
  t.innerHTML = `<span class="icon icon--sm">${ICONS[icon] || ''}</span><span class="toast__msg"></span>`;
  t.querySelector('.toast__msg').textContent = message;
  t.onclick = () => removeToast(t);
  root.appendChild(t);
  // forced reflow для анимации
  void t.offsetWidth;
  t.classList.add('is-shown');
  setTimeout(() => removeToast(t), duration);
}
function removeToast(t) {
  t.classList.remove('is-shown');
  setTimeout(() => t.remove(), 250);
}

// ----- modal confirm (Promise<boolean>) -----
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
      else if (e.key === 'Enter') { cleanup(); resolve(true); }
    };
    okBtn.onclick = () => { cleanup(); resolve(true); };
    cancelBtn.onclick = () => { cleanup(); resolve(false); };
    document.addEventListener('keydown', onKey);
    setTimeout(() => okBtn.focus(), 30);
  });
}

// ----- HTTP helper -----
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

// ----- API -----
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
    const fd = new FormData(); fd.append("file", file);
    const r = await fetch("/api/upload-image", { method: "POST", body: fd });
    let data = null; try { data = await r.json(); } catch (_) {}
    if (!r.ok) throw new Error((data && data.error) || `Ошибка ${r.status}`);
    return data;
  },
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
  mediaUpload: async (file) => {
    const fd = new FormData(); fd.append("file", file);
    const r = await fetch("/api/media/upload", { method: "POST", body: fd });
    let data = null; try { data = await r.json(); } catch (_) {}
    if (!r.ok) throw new Error((data && data.error) || `Ошибка ${r.status}`);
    return data;
  },
  mediaList: (kind) => jsonFetch("/api/media" + (kind ? `?kind=${encodeURIComponent(kind)}` : "")),
  mediaDelete: (id) => jsonFetch(`/api/media/${id}`, { method: "DELETE" }),
  mediaGenPrompts: (body) =>
    jsonFetch("/api/media/generate-prompts", { method: "POST", body: JSON.stringify(body) }),
  mediaPromptsList: () => jsonFetch("/api/media/prompts"),
  mediaPromptSave: (body) =>
    jsonFetch("/api/media/prompts", { method: "POST", body: JSON.stringify(body) }),
  mediaPromptDelete: (id) => jsonFetch(`/api/media/prompts/${id}`, { method: "DELETE" }),
};

function rubricByKey(key) {
  return state.rubrics.find(r => r.key === key) || null;
}

function isFreeTopic(key) { return key === 'free_topic'; }

// ============================================================
// EDITOR
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
      // Переключаем topic <-> free-topic блоки
      const isFree = isFreeTopic(r.key);
      $("#topic-block").hidden = isFree;
      $("#free-topic-block").hidden = !isFree;
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
  const root = $("#preview-media");
  root.innerHTML = "";
  if (state.videoPath) {
    const v = document.createElement('video');
    v.src = `/static/uploads/${state.videoPath}`;
    v.controls = true;
    v.preload = 'metadata';
    root.appendChild(v);
  } else if (state.imagePath) {
    const img = document.createElement("img");
    img.src = `/static/uploads/${state.imagePath}`;
    img.alt = "preview";
    img.onclick = () => openImageFullscreen(img.src);
    root.appendChild(img);
  } else {
    const ph = document.createElement("div");
    ph.className = "vk-post__image-placeholder";
    ph.textContent = "Медиа появится здесь";
    root.appendChild(ph);
  }
}

function openImageFullscreen(src) {
  const ov = document.createElement('div');
  ov.className = 'fullscreen-overlay';
  ov.onclick = () => ov.remove();
  ov.innerHTML = `<img src="${src}" alt="">`;
  document.body.appendChild(ov);
}

function updateCharCounter() {
  const text = $("#post-text").value;
  const len = text.length;
  $("#char-count").textContent = len;
  const cnt = $("#char-counter");
  cnt.classList.remove('is-warn', 'is-error');
  if (len > 4000) cnt.classList.add('is-error');
  else if (len >= 3500) cnt.classList.add('is-warn');
  // блокируем публикацию при переполнении
  const tooLong = len > 4000;
  $("#btn-publish-now").disabled = tooLong || !state.vkConfigured || !state.editingPostId;
  $("#btn-schedule").disabled = tooLong || !state.vkConfigured || !state.editingPostId;
}

function setText(text) {
  state.text = text;
  $("#post-text").value = text;
  state.isDirty = true;
  updateCharCounter();
  renderPreview();
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
    btn.dataset._origHTML = btn.innerHTML;
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

function startKlingTimer() {
  $("#kling-progress").hidden = false;
  state.klingTimerStart = Date.now();
  $("#kling-timer").textContent = "0";
  state.klingTimerId = setInterval(() => {
    const sec = Math.floor((Date.now() - state.klingTimerStart) / 1000);
    $("#kling-timer").textContent = sec;
  }, 1000);
}
function stopKlingTimer() {
  $("#kling-progress").hidden = true;
  if (state.klingTimerId) clearInterval(state.klingTimerId);
  state.klingTimerId = null;
}

async function onGenerateImage() {
  if (!state.selectedRubric) { toast("Выбери рубрику", "error"); return; }
  const full = state.rubricsFull.find(r => r.key === state.selectedRubric);
  if (!full) { toast("Не загружены настройки рубрики", "error"); return; }
  const topic = getCurrentTopic() || "english learning";
  const prompt = (full.image_prompt_template || "").replaceAll("{topic}", topic);
  const btn = $("#btn-generate-image");
  setBusy(btn, true, "Идёт генерация…");
  startKlingTimer();
  $("#image-status").textContent = "";
  try {
    const data = await api.generateImage({ prompt, aspect_ratio: "1:1" });
    state.imagePath = data.image_path;
    state.videoPath = null;
    state.mediaKind = "image";
    state.imageSource = "kling";
    state.imagePrompt = prompt;
    state.isDirty = true;
    $("#image-status").textContent = "Картинка готова";
    renderPreview();
    toast("Картинка готова", "success");
  } catch (e) {
    $("#image-status").textContent = "";
    toast(e.message, "error");
  } finally {
    setBusy(btn, false);
    stopKlingTimer();
  }
}

async function onFileUpload(ev) {
  const file = ev.target.files && ev.target.files[0];
  if (!file) return;
  const isVideo = file.type.startsWith('video/');
  $("#image-status").textContent = `Загружаю ${isVideo ? 'видео' : 'картинку'}…`;
  try {
    const data = await api.mediaUpload(file);
    if (data.kind === 'video') {
      state.videoPath = data.file_path;
      state.imagePath = null;
      state.mediaKind = "video";
    } else {
      state.imagePath = data.file_path;
      state.videoPath = null;
      state.mediaKind = "image";
    }
    state.imageSource = "manual_upload";
    state.imagePrompt = null;
    state.isDirty = true;
    $("#image-status").textContent = `Загружено (${data.kind})`;
    renderPreview();
    toast("Медиа загружено и добавлено в библиотеку", "success");
    if (state.activeTab === 'media') renderMediaLibrary();
  } catch (e) {
    $("#image-status").textContent = "";
    toast(e.message, "error");
  } finally { ev.target.value = ""; }
}

async function onPickFromLibrary() {
  await openMediaPicker((asset) => {
    if (asset.kind === 'video') {
      state.videoPath = asset.file_path;
      state.imagePath = null;
      state.mediaKind = "video";
    } else {
      state.imagePath = asset.file_path;
      state.videoPath = null;
      state.mediaKind = "image";
    }
    state.imageSource = asset.source || "manual_upload";
    state.isDirty = true;
    $("#image-status").textContent = `Из библиотеки: ${asset.original_name || asset.file_path}`;
    renderPreview();
  });
}

async function openMediaPicker(onPick) {
  const ov = $("#picker-overlay");
  ov.hidden = false;
  const grid = $("#picker-grid");
  grid.innerHTML = '<div class="muted">Загрузка…</div>';
  try {
    const items = await api.mediaList();
    grid.innerHTML = "";
    if (!items.length) {
      grid.innerHTML = '<div class="muted center">В библиотеке пусто. Загрузи файлы в разделе «Медиа».</div>';
    }
    items.forEach(a => {
      const card = renderMediaCard(a, /*compact*/ true);
      card.onclick = () => { ov.hidden = true; onPick(a); };
      grid.appendChild(card);
    });
  } catch (e) { toast(e.message, 'error'); }
  $("#picker-close").onclick = () => { ov.hidden = true; };
}

function clearMedia() {
  state.imagePath = null;
  state.videoPath = null;
  state.mediaKind = "none";
  state.imageSource = "none";
  state.imagePrompt = null;
  $("#image-status").textContent = "";
  renderPreview();
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
    image_path: state.imagePath,
    image_prompt: state.imagePrompt,
    image_source: state.imageSource,
    video_path: state.videoPath,
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
    message: 'Опубликовать пост в сообществе ВК прямо сейчас? Удалить или отредактировать после публикации можно только вручную в самом ВК.',
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
    message: 'Пост будет опубликован автоматически в указанное время. Программа должна быть запущена в этот момент (либо она догонит публикацию при следующем запуске).',
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
    const data = await api.postSchedule(state.editingPostId, localDate.toISOString());
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
  state.imagePath = null;
  state.videoPath = null;
  state.mediaKind = "none";
  state.imageSource = "none";
  state.imagePrompt = null;
  state.parentPostId = null;
  state.parentInfo = null;
  state.isDirty = false;
  $("#topic").value = "";
  $("#free-topic").value = "";
  $("#post-text").value = "";
  $("#image-status").textContent = "";
  $("#parent-info").hidden = true;
  $("#topic-block").hidden = false;
  $("#free-topic-block").hidden = true;
  renderRubrics();
  renderPreview();
  updateCharCounter();
}

// ============================================================
// LIBRARY
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
    const d = new Date(p.scheduled_at);
    extra = ` · ${d.toLocaleString('ru-RU')}`;
  } else if (p.status === 'published' && p.published_at) {
    const d = new Date(p.published_at);
    extra = ` · ${d.toLocaleDateString('ru-RU')}`;
  }
  return `<span class="badge ${m.cls}">${m.label}${extra}</span>`;
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
    const mediaHTML = p.video_path
      ? `<div class="lib-card__img lib-card__img--empty">🎬 видео</div>`
      : (p.image_path
          ? `<img class="lib-card__img" src="/static/uploads/${p.image_path}" alt="">`
          : `<div class="lib-card__img lib-card__img--empty">нет медиа</div>`);
    const date = p.created_at ? p.created_at.slice(0, 10) : "";
    const rname = r ? `${r.emoji || ""} ${r.name}` : p.rubric_key;

    const body = document.createElement('div');
    body.className = 'lib-card__body';

    const meta = document.createElement('div');
    meta.className = 'lib-card__meta';
    meta.innerHTML = `<span>${rname}</span><span class="muted">${date}</span>`;
    body.appendChild(meta);

    const badge = document.createElement('div');
    badge.innerHTML = statusBadge(p);
    body.appendChild(badge);

    if (p.topic) {
      const t = document.createElement('div');
      t.className = 'lib-card__topic';
      t.textContent = p.topic.length > 80 ? p.topic.slice(0, 80) + '…' : p.topic;
      body.appendChild(t);
    }

    const txt = document.createElement('div');
    txt.className = 'lib-card__text';
    txt.textContent = (p.text_content || "").slice(0, 180) + '…';
    body.appendChild(txt);

    if (p.last_publish_error) {
      const errEl = document.createElement('div');
      errEl.className = 'lib-card__err';
      errEl.textContent = `Ошибка: ${p.last_publish_error.slice(0, 120)}`;
      body.appendChild(errEl);
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
    body.appendChild(actions);

    card.appendChild(asNode(mediaHTML));
    card.appendChild(body);
    root.appendChild(card);
  });
}

function asNode(html) {
  const t = document.createElement('template');
  t.innerHTML = html.trim();
  return t.content.firstChild;
}

function iconBtn(icon, title, onclick, danger = false) {
  const b = document.createElement('button');
  b.className = 'icon-btn' + (danger ? ' icon-btn--danger' : '');
  b.title = title; b.setAttribute('aria-label', title);
  b.innerHTML = `<span class="icon">${ICONS[icon] || ''}</span>`;
  b.onclick = onclick;
  return b;
}

async function openPostInEditor(id) {
  try {
    const p = await api.postGet(id);
    state.editingPostId = p.id;
    state.selectedRubric = p.rubric_key;
    state.topic = p.topic || "";
    state.text = p.text_content || "";
    state.imagePath = p.image_path || null;
    state.videoPath = p.video_path || null;
    state.mediaKind = p.media_kind || "none";
    state.imageSource = p.image_source || "none";
    state.imagePrompt = p.image_prompt || null;
    state.parentPostId = p.parent_post_id || null;
    state.isDirty = false;

    const isFree = isFreeTopic(p.rubric_key);
    $("#topic-block").hidden = isFree;
    $("#free-topic-block").hidden = !isFree;
    if (isFree) $("#free-topic").value = state.topic;
    else $("#topic").value = state.topic;
    $("#post-text").value = state.text;
    $("#image-status").textContent = state.mediaKind !== 'none' ? `Медиа из черновика (${state.mediaKind})` : "";

    const pi = $("#parent-info");
    if (p.parent_post_id) {
      pi.textContent = `📋 Создан на основе поста #${p.parent_post_id}`;
      pi.hidden = false;
    } else { pi.hidden = true; }

    renderRubrics();
    renderPreview();
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
    message: 'Черновик будет помещён в корзину (soft-delete) — данные остаются в БД, но в библиотеке не отображаются.',
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
// MEDIA tab
// ============================================================
function renderMediaCard(a, compact = false) {
  const card = document.createElement('article');
  card.className = 'media-card' + (compact ? ' media-card--compact' : '');
  const url = a.url || `/static/uploads/${a.file_path}`;
  if (a.kind === 'image') {
    const img = document.createElement('img');
    img.src = url; img.alt = a.original_name || '';
    img.className = 'media-card__thumb';
    card.appendChild(img);
  } else {
    const ph = document.createElement('div');
    ph.className = 'media-card__thumb media-card__thumb--video';
    ph.innerHTML = '🎬 video';
    card.appendChild(ph);
  }
  const body = document.createElement('div');
  body.className = 'media-card__body';
  const name = document.createElement('div');
  name.className = 'media-card__name';
  name.textContent = a.original_name || a.file_path;
  body.appendChild(name);
  const meta = document.createElement('div');
  meta.className = 'media-card__meta muted small';
  meta.textContent = `${(a.size_bytes / 1024 / 1024).toFixed(2)} МБ${a.width ? ` · ${a.width}×${a.height}` : ''}`;
  body.appendChild(meta);
  if (!compact) {
    const actions = document.createElement('div');
    actions.className = 'media-card__actions';
    actions.appendChild(iconBtn('plus', 'Использовать в новом посте', () => useInNewPost(a)));
    actions.appendChild(iconBtn('trash', 'Удалить', () => deleteMedia(a.id), true));
    body.appendChild(actions);
  }
  card.appendChild(body);
  return card;
}

async function renderMediaLibrary() {
  const kind = $("#media-kind-filter").value;
  let items = [];
  try { items = await api.mediaList(kind); } catch (e) { toast(e.message, 'error'); return; }
  const grid = $("#media-grid");
  grid.innerHTML = "";
  $("#media-empty").hidden = items.length > 0;
  items.forEach(a => grid.appendChild(renderMediaCard(a)));
}

function useInNewPost(a) {
  resetEditor();
  if (a.kind === 'video') { state.videoPath = a.file_path; state.mediaKind = 'video'; }
  else { state.imagePath = a.file_path; state.mediaKind = 'image'; }
  state.imageSource = a.source || 'manual_upload';
  switchTab('create');
  renderPreview();
  toast('Медиа добавлено в новый пост', 'success');
}

async function deleteMedia(id) {
  const ok = await confirmModal({
    title: 'Удалить файл?',
    message: 'Файл будет помечен удалённым. Посты, в которых он используется, продолжат показывать его, пока вы не замените медиа.',
    confirmLabel: 'Удалить',
    danger: true,
  });
  if (!ok) return;
  try { await api.mediaDelete(id); toast('Удалено', 'success'); renderMediaLibrary(); }
  catch (e) { toast(e.message, 'error'); }
}

// ----- Drag-n-drop -----
function setupDropzone() {
  const dz = $("#media-dropzone");
  const input = $("#media-file-input");
  ['dragenter', 'dragover'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add('is-active'); }));
  ['dragleave', 'drop'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove('is-active'); }));
  dz.addEventListener('drop', e => {
    const files = Array.from(e.dataTransfer.files || []);
    uploadMediaFiles(files);
  });
  input.addEventListener('change', e => {
    uploadMediaFiles(Array.from(e.target.files || []));
    e.target.value = '';
  });
}

async function uploadMediaFiles(files) {
  if (!files.length) return;
  const status = $("#media-upload-status");
  let ok = 0, fail = 0;
  for (const f of files) {
    status.textContent = `Загружаю: ${f.name}…`;
    try { await api.mediaUpload(f); ok++; }
    catch (e) { fail++; toast(`${f.name}: ${e.message}`, 'error', 7000); }
  }
  status.textContent = `Загружено ${ok}${fail ? `, ошибок ${fail}` : ''}`;
  renderMediaLibrary();
}

// ----- Prompt generator -----
async function onGeneratePrompts() {
  const idea = $("#prompt-idea").value.trim();
  if (!idea) { toast('Опиши идею', 'error'); return; }
  const media_type = document.querySelector('input[name="media-type"]:checked').value;
  const style = $("#prompt-style").value;
  const aspect_ratio = $("#prompt-ratio").value;
  const btn = $("#btn-generate-prompts");
  setBusy(btn, true, 'Генерирую промпты…');
  $("#prompts-status").textContent = "Это занимает ~5–10 секунд…";
  try {
    const data = await api.mediaGenPrompts({ idea, media_type, style, aspect_ratio });
    renderPromptsResult(data.variants, { idea, media_type, style, aspect_ratio });
    $("#prompts-status").textContent = "Готово";
    toast('Промпты сгенерированы', 'success');
  } catch (e) {
    $("#prompts-status").textContent = "";
    toast(e.message, 'error');
  } finally { setBusy(btn, false); }
}

function renderPromptsResult(variants, ctx) {
  const root = $("#prompts-result");
  root.innerHTML = "";
  variants.forEach(v => {
    const card = document.createElement('div');
    card.className = 'prompt-card';
    const head = document.createElement('div');
    head.className = 'prompt-card__head';
    head.innerHTML = `<strong>Вариант ${v.variant}</strong> <span class="muted small">для ${v.best_for || 'Generic'}</span>`;
    const txt = document.createElement('div');
    txt.className = 'prompt-card__text';
    txt.textContent = v.prompt;
    const actions = document.createElement('div');
    actions.className = 'prompt-card__actions';
    const copyBtn = iconBtn('copy', 'Копировать', async () => {
      await navigator.clipboard.writeText(v.prompt);
      toast('Скопировано', 'success', 2000);
    });
    const saveBtn = iconBtn('save', 'Сохранить для повторного использования', async () => {
      try {
        await api.mediaPromptSave({
          idea_ru: ctx.idea, prompt_en: v.prompt, media_type: ctx.media_type,
          style: ctx.style, aspect_ratio: ctx.aspect_ratio, best_for: v.best_for,
        });
        toast('Сохранено', 'success');
        loadSavedPrompts();
      } catch (e) { toast(e.message, 'error'); }
    });
    actions.appendChild(copyBtn);
    actions.appendChild(saveBtn);
    card.appendChild(head); card.appendChild(txt); card.appendChild(actions);
    root.appendChild(card);
  });
}

async function loadSavedPrompts() {
  const root = $("#saved-prompts");
  root.innerHTML = "<div class='muted small'>Загрузка…</div>";
  try {
    const items = await api.mediaPromptsList();
    root.innerHTML = "";
    if (!items.length) {
      root.innerHTML = "<div class='muted small'>Пока ничего не сохранено.</div>";
      return;
    }
    items.forEach(p => {
      const card = document.createElement('div');
      card.className = 'prompt-card prompt-card--saved';
      card.innerHTML = `
        <div class="prompt-card__head"><strong>${p.media_type === 'video' ? '🎬 video' : '🖼 image'}</strong>
          <span class="muted small">${p.style} · ${p.aspect_ratio}${p.best_for ? ' · ' + p.best_for : ''}</span></div>
        <div class="muted small prompt-card__idea"></div>
        <div class="prompt-card__text"></div>
        <div class="prompt-card__actions"></div>`;
      card.querySelector('.prompt-card__idea').textContent = `Идея: ${p.idea_ru}`;
      card.querySelector('.prompt-card__text').textContent = p.prompt_en;
      const actions = card.querySelector('.prompt-card__actions');
      actions.appendChild(iconBtn('copy', 'Копировать', async () => {
        await navigator.clipboard.writeText(p.prompt_en);
        toast('Скопировано', 'success', 2000);
      }));
      actions.appendChild(iconBtn('trash', 'Удалить', async () => {
        const ok = await confirmModal({ title: 'Удалить сохранённый промпт?', message: 'Промпт будет удалён без возможности восстановления.', confirmLabel: 'Удалить', danger: true });
        if (!ok) return;
        try { await api.mediaPromptDelete(p.id); toast('Удалено', 'success'); loadSavedPrompts(); }
        catch (e) { toast(e.message, 'error'); }
      }, true));
      root.appendChild(card);
    });
  } catch (e) { toast(e.message, 'error'); }
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
      <label class="label">Системный промпт (для генерации текста)</label>
      <textarea class="textarea settings-card__sp" rows="14"></textarea>
      <label class="label">Шаблон промпта картинки (для Kling, можно использовать {topic})</label>
      <textarea class="textarea settings-card__ip" rows="4"></textarea>
      <button class="btn btn--primary settings-card__save">Сохранить</button>
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
  if (name === "media") { renderMediaLibrary(); loadSavedPrompts(); }
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

  $("#btn-generate-text").addEventListener("click", onGenerateText);
  $("#btn-regenerate-text").addEventListener("click", onGenerateText);
  $("#btn-generate-image").addEventListener("click", onGenerateImage);
  $("#file-upload").addEventListener("change", onFileUpload);
  $("#btn-pick-from-library").addEventListener("click", onPickFromLibrary);
  $("#btn-save").addEventListener("click", onSavePost);
  $("#btn-publish-now").addEventListener("click", onPublishNow);
  $("#btn-schedule").addEventListener("click", onSchedule);
  $("#btn-new").addEventListener("click", () => { resetEditor(); toast("Редактор очищен", "info", 2000); });

  $("#post-text").addEventListener("input", (e) => {
    state.text = e.target.value;
    state.isDirty = true;
    updateCharCounter();
    renderPreview();
  });
  $("#topic").addEventListener("input", (e) => { state.topic = e.target.value; state.isDirty = true; });
  $("#free-topic").addEventListener("input", (e) => { state.freeTopic = e.target.value; state.isDirty = true; });

  $("#btn-lib-refresh").addEventListener("click", renderLibrary);
  $("#lib-search").addEventListener("input", debounce(renderLibrary, 300));
  $("#lib-rubric").addEventListener("change", renderLibrary);
  $("#lib-status").addEventListener("change", renderLibrary);

  // Media tab
  $("#btn-generate-prompts").addEventListener("click", onGeneratePrompts);
  $("#btn-media-refresh").addEventListener("click", renderMediaLibrary);
  $("#media-kind-filter").addEventListener("change", renderMediaLibrary);
  setupDropzone();

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

  // beforeunload — предупредить о несохранённых изменениях
  window.addEventListener('beforeunload', (e) => {
    if (state.isDirty) {
      e.preventDefault();
      e.returnValue = '';
    }
  });

  loadRubrics();
  loadVKStatus();
  updateCharCounter();
});

function debounce(fn, ms) {
  let t = null;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}
