# Lora Content Studio

## Что это
Локальный одностраничный веб-инструмент для подготовки маркетинговых постов VK-сообщества «Лора | Английский с AI-репетитором» (продвижение продукта **LinguaAI**, лендинг lora-aitutor.ru). Текст генерируется Claude Sonnet 4.5 через ProxyAPI, иллюстрация — Kling AI или ручная загрузка. Все черновики хранятся локально в SQLite.

## Системные требования
- Windows 11
- Python 3.10 или новее ([установить с python.org](https://www.python.org/downloads/))
- Браузер (Chrome, Edge, Firefox)
- Интернет-соединение для вызовов ProxyAPI и Kling AI

## Установка

Открой PowerShell или cmd и выполни команды по очереди:

```cmd
cd C:\Users\nlovt\lora-content-studio

:: создать виртуальное окружение Python (изолированные зависимости)
python -m venv venv

:: активировать окружение (после этого python и pip — из .\venv)
venv\Scripts\activate

:: установить зависимости
pip install -r requirements.txt

:: создать файл с ключами на основе шаблона
copy .env.example .env
```

После этого открой `.env` в любом редакторе и подставь реальные ключи (см. ниже).

## Где взять API-ключи

1. **ProxyAPI** (для Claude Sonnet 4.5) — https://proxyapi.ru
   - Зарегистрируйся, пополни баланс, получи API-ключ в личном кабинете.
   - Вставь в `.env` как `PROXYAPI_KEY=...`.

2. **Kling AI** (для генерации картинок) — https://app.klingai.com → раздел dev/API
   - Получи Access Key и Secret Key.
   - Вставь в `.env` как `KLING_ACCESS_KEY=...` и `KLING_SECRET_KEY=...`.

3. **FLASK_SECRET_KEY** — любая случайная строка (32+ символа). Можно сгенерировать:
   ```cmd
   python -c "import secrets; print(secrets.token_hex(24))"
   ```

4. **VK API** (для публикации постов в сообщество) — см. отдельный раздел ниже.

## Настройка VK API (для публикации в сообщество)

Начиная с **v0.3** используем **VK ID OAuth 2.1** (новая система авторизации
VK, OAuth 2.0 Implicit Flow удалён в 2025). Без этого медиа-публикация будет
падать с VK code 27 — текстовые посты на старом community-токене работают, но
фото и видео нет.

### Шаг A. Настроить VK-приложение перед первой авторизацией

1. Зайди на [id.vk.com](https://id.vk.com) → твоё **Standalone-приложение**
   (App ID = `54587420`). Если приложения ещё нет — создай новое именно через
   id.vk.com (НЕ мини-приложение).
2. В разделе **Доверенные redirect URI** добавь:
   ```
   https://oauth.vk.com/blank.html
   ```
   (это blank-страница самого VK; manual-paste flow — мы её используем чтобы не
   возиться с локальным HTTPS, который требует VK ID).
3. В разделе **Разрешения / Scope** убедись, что включены:
   `wall`, `photos`, `video`, `groups`, `offline`. Без них токен будет урезанным.
   (Расширенные scope требуют пройти бизнес-верификацию в VK Бизнес ID — у Dr.
   Nik это уже сделано.)
4. Сохрани настройки. **Защищённый ключ (client_secret) копировать НЕ нужно** —
   PKCE-flow его не использует.

### Шаг B. Получить токены (один раз)

В `.env` должны быть заполнены `VK_OAUTH_APP_ID=54587420` и
`VK_OAUTH_REDIRECT_URI=https://oauth.vk.com/blank.html` (см. `.env.example`).
После этого:

```cmd
python scripts/get_vk_token.py
```

Скрипт:
1. Откроет браузер на странице авторизации VK ID.
2. Авторизуйся **под личным аккаунтом админа группы** (НЕ под группой).
3. Подтверди запрашиваемые разрешения.
4. VK редиректит на `https://oauth.vk.com/blank.html?code=...&state=...&device_id=...`
   — страница будет почти пустая.
5. Скопируй ПОЛНЫЙ URL из адресной строки и вставь в терминал по запросу
   скрипта.

Скрипт обменяет `code` на пару токенов и автоматически запишет в `.env`:
- `VK_OAUTH_DEVICE_ID` (UUID, генерируется один раз)
- `VK_USER_ACCESS_TOKEN` (живёт 24 часа)
- `VK_USER_REFRESH_TOKEN` (долгоживущий — для авто-обновления)
- `VK_USER_TOKEN_EXPIRES_AT`

После этого приложение **само рефрешит** access-токен по мере необходимости —
руками больше ничего не трогать.

### Шаг C. Узнать `group_id` и прописать в `.env`

Через [regvk.com/id](https://regvk.com/id/) — введи короткое имя сообщества,
получи число.

```
VK_GROUP_ID=12345678
VK_API_VERSION=5.199
```

Постинг происходит **от имени сообщества** благодаря
`wall.post(owner_id=-group_id, from_group=1)` — VK сам подставляет
автора-сообщество, если автор-человек админ группы.

### Шаг D. Проверить

Перезапусти приложение (`Ctrl+C` → `python app.py`) и открой
http://127.0.0.1:5000/api/vk/status — должно вернуться:
```json
{"configured": true, "token_source": "oauth_user", "media_publish_supported": true, ...}
```

Если `media_publish_supported: false` или `token_source: "legacy_community"` —
OAuth не настроен, медиа-публикация упадёт с code 27. Возвращайся к Шагу B.

### Деплой на сервер

См. [docs/server-deployment-vk.md](docs/server-deployment-vk.md) — токены
получаются локально, переносятся на сервер один раз, дальше сервер сам
обновляет access-токен через refresh-токен.

### Старая переменная VK_COMMUNITY_TOKEN

Сохранена как fallback: если `VK_USER_ACCESS_TOKEN` пуст, приложение откатится
на `VK_COMMUNITY_TOKEN` (текстовая публикация будет работать, медиа — нет).
Это deprecation-путь для совместимости с v0.2 настройками.

## Запуск

```cmd
cd C:\Users\nlovt\lora-content-studio
venv\Scripts\activate
python app.py
```

Сервер стартует на http://127.0.0.1:5000 — открой этот адрес в браузере.

При первом запуске автоматически создаётся `data/lora.db` и заполняется четырьмя стартовыми рубриками.

## Структура (v0.4.0)

```
lora-content-studio/
├── app.py                    точка входа Flask
├── manage.py                 CLI (status / list-posts / generate-post / publish / schedule)
├── config.py                 загрузка .env и константы (пути, лимиты, базовые URL)
│
├── core/
│   ├── scheduler.py          APScheduler + мультиплатформенная публикация
│   ├── logging_utils.py
│   ├── publishers/           публикаторы постов (общий интерфейс BasePublisher)
│   │   ├── base.py           BasePublisher + PublishResult + PublishError
│   │   ├── vk.py             VKClient + VKPublisher (только текст с v0.3.0)
│   │   ├── vk_oauth.py       OAuth 2.1 спящая ветка (если VK вернёт media scope)
│   │   ├── telegram.py       Bot API (заглушка пока канала нет)
│   │   ├── youtube.py        placeholder (требует Google OAuth + app review)
│   │   └── tiktok.py         placeholder (требует Content Posting API access)
│   ├── generators/           генераторы контента
│   │   ├── llm_client.py     Claude через ProxyAPI
│   │   ├── prompts.py        рубрики и системные промпты
│   │   ├── prompt_generator.py   Kling-промпт-генератор
│   │   ├── image_clients.py  gpt-image-2 через ProxyAPI (/edits с референсом)
│   │   └── lora_references.py    7 эмоций Лоры
│   ├── storage/              SQLAlchemy
│   │   ├── db.py             engine, миграции v0.2 → v0.4
│   │   └── models.py         Post, Rubric, MediaAsset, MediaPrompt, PostPublication
│   ├── ingest/               (пусто, под автосбор источников)
│   └── analytics/            (пусто, под аналитику VK/Telegram)
│
├── routes/                   Flask blueprints
│
├── assets/lora/              бренд-ассеты Лоры (PNG-оригиналы gitignored, JPG в репо)
│   └── optimized/            JPG 1024×1024 для Claude Vision и gpt-image-2 /edits
│
├── templates/                один HTML-шаблон
├── static/css/  static/js/   фронтенд
├── static/uploads/           сгенерированные/загруженные пользователем медиа
│
├── data/                     рабочие данные (gitignored)
│   ├── lora.db               SQLite
│   ├── inbox/video/          видео из Kling (внешний workflow)
│   ├── inbox/text/           тексты-источники для автосбора
│   ├── exports/              отчёты аналитики
│   └── content_calendar/     контент-план
│
├── references/               бренд-материалы (тон голоса, гайдлайны рубрик)
├── briefs/                   короткие записки для Claude в чате
├── tasks/active/             текущее ТЗ для Claude Code-агента
├── tasks/archive/            закрытые ТЗ
├── tmp/                      эфемерные файлы (gitignored)
├── tests/                    pytest + fixtures
│
├── docs/sessions/            отчёты по рабочим сессиям
├── docs/research/            research-документы по внешним API
├── docs/deployment/          заметки по серверной части
└── logs/                     app.log + ai_calls.jsonl
```

## CLI (терминальная работа без UI)

```cmd
venv\Scripts\python manage.py status
venv\Scripts\python manage.py list-posts --status draft
venv\Scripts\python manage.py show-post 42
venv\Scripts\python manage.py generate-post word_of_day
venv\Scripts\python manage.py generate-post free_topic --topic "идиома piece of cake"
venv\Scripts\python manage.py publish 42                  # default: vk
venv\Scripts\python manage.py publish 42 --platform telegram
venv\Scripts\python manage.py publish 42 --platform all   # все настроенные
venv\Scripts\python manage.py schedule 42 2026-05-27T10:00:00
venv\Scripts\python manage.py show-rubric word_of_day     # для использования из Skill
venv\Scripts\python manage.py import-from-json <file>     # импорт из Skill lora-post-builder
venv\Scripts\python manage.py import-from-json <file> --no-image       # только текст
venv\Scripts\python manage.py import-from-json <file> --quality low    # быстрая картинка для теста
```

Все команды работают параллельно с Flask UI — общая БД, общие модули, разные интерфейсы.

## Skill `lora-post-builder` (Claude Code)

Hybrid-workflow для обхода задержки ProxyAPI с новыми моделями Claude. Skill живёт в `~/.claude/skills/lora-post-builder/SKILL.md` (личный, доступен в любом проекте) и применяется когда пишешь Claude'у в чате:

- «Сделай пост Лоры про X»
- «Преврати эту статью в пост, рубрика mini_fact» (с URL — Claude дёрнет WebFetch)
- «Оформи идею в формат поста»

**Что делает Skill:**

1. Принимает идею / текст / URL
2. Определяет рубрику (или спрашивает)
3. Подбирает эмоцию Лоры из маппинга
4. Читает актуальный `system_prompt` рубрики из `core/generators/prompts.py` через `manage.py show-rubric`
5. Генерирует VK-текст (опционально Telegram, опционально kling_prompt)
6. Собирает JSON по схеме `docs/schemas/lora-post-v1.json`
7. Сохраняет в `data/inbox/text/YYYY-MM-DD-<rubric>-<slug>.json`

**Дальше — твоя команда:**

```cmd
venv\Scripts\python manage.py import-from-json data\inbox\text\<file>.json
```

CLI парсит JSON, создаёт `Post` в БД (status=draft), генерирует картинку через `gpt-image-2 /v1/images/edits` с референсом эмоции Лоры (1–3 минуты на high quality), сохраняет в `static/uploads/images/`, привязывает к посту через `MediaAsset`.

После этого — ревью в Flask UI или CLI, публикация по обычному флоу (`publish-now`, `schedule`).

**Бренд-голос** — в `references/lora-voice-guide.md`. Skill ссылается на него; обновляй документ когда тон голоса или эмоции меняются.

## Что в этой версии (v0.2)

**Новое в v0.2:**
- **Публикация в VK** — «Опубликовать сейчас» и «Запланировать» (через APScheduler, фоновые задачи). Поддержка пропущенных публикаций при выключенном сервере: догоняет автоматически при следующем старте.
- **8 рубрик** — добавлены: Деловой английский 💼, Сленг и неформальное 🎭, Минифакт 🤔, Свободная тема ✨ (со своим описанием задачи).
- **Медиа-студия** — отдельная вкладка: drag-n-drop загрузка изображений (до 10 МБ) и видео (до 200 МБ); медиа-библиотека с фильтрами; генератор промптов для внешних AI (3 варианта на английском от Claude — Kling AI / utopy.ai / MidJourney); сохранение и повторное использование промптов.
- **Видео в постах** — к посту можно прикрепить ИЛИ изображение, ИЛИ видео.
- **Soft-delete** черновиков и медиа — удалённое не теряется, лежит в БД.
- **«Создать на основе»** — дублирование любого поста как нового черновика.
- **UX-полировка:** иконочные кнопки, единая модалка подтверждения, очередь тостов в правом нижнем углу, прогресс-индикатор Kling с таймером, счётчик символов VK (4096) с цветовой индикацией, hot-keys (`Ctrl+Enter` — генерировать, `Ctrl+S` — сохранить, `Ctrl+P` — опубликовать, `Esc` — закрыть модалку), фокус-стили для accessibility.

**Из v0.1 сохранено:**
- Генерация текста через Claude Sonnet 4.5 и картинок через Kling AI
- Превью «как будет выглядеть в ВК»
- Библиотека черновиков с поиском и фильтрами (включая фильтр по статусу)
- Редактирование промптов рубрик
- Логирование AI-вызовов в `logs/ai_calls.jsonl` (теперь и VK API)

## Что в v0.4.0 (2026-05-26)

Структурный рефакторинг под расширение SMM:
- Декомпозиция `core/` на подпакеты `publishers/`, `generators/`, `storage/`, `ingest/`, `analytics/`. Базовый интерфейс `BasePublisher`.
- **Telegram** через Bot API — модуль готов, активируется по добавлению `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHANNEL_ID` в `.env`.
- **YouTube / TikTok** — placeholder-модули с docstrings, описывающими план подключения (OAuth, app review).
- **CLI** `manage.py` — терминальный интерфейс для генерации и публикации.
- **Мультиплатформенная публикация** — `Post.target_platforms` (JSON-список) + таблица `post_publications` для истории по каждой платформе.
- Бренд-ассеты Лоры вынесены из кодовой папки в `assets/lora/`.

## Roadmap (после v0.4.0)

- **Контент-план** на месяц с календарной сеткой
- **Аналитика VK / Telegram** — охваты, лайки, комментарии (модуль `core/analytics/`)
- **Автосбор источников** — RSS-фиды, Reddit, англоязычные блоги (модуль `core/ingest/`)
- **Structured output** от Claude (JSON-schema) для надёжной интеграции с автопостингом
- **VPS deploy** — Docker, GitHub Actions, миграция SQLite → PostgreSQL
