# core/ingest/ — автоматический сбор источников

Пустой пакет под перспективу. Сейчас не используется в работе.

## Идея

Автопостинг и контент-фабрика требуют не только генерации, но и **подачи идей** на вход. Сейчас Dr. Nik диктует темы — это узкое место. Хочется чтобы система сама приносила свежие материалы, а Claude отбирал из них идеи.

## Возможные источники (в порядке простоты)

1. **RSS-фиды** англоязычных блогов про английский для русскоязычных (BBC Learning English, FluentU, Antimoon, Olly Richards, Engsim, Cambridge Dictionary blog)
2. **Reddit** (r/EnglishLearning, r/grammar, r/AskEnglish) через PRAW
3. **Twitter/X** — топовые посты учителей английского (требует API access)
4. **Telegram-каналы** конкурентов — мониторинг через telethon
5. **YouTube** — транскрипты популярных видео по english-teaching
6. **Курс LinguaAI** — ошибки реальных учеников из `student-progress.json` (когда будет интеграция)

## Что сюда класть

Каждый источник — отдельный модуль `core/ingest/<source>.py`:
- `class XxxIngestor`: `fetch_new()` → список raw items
- хранение «что уже видели» — таблица в БД или файл-маркер

Pipeline: `core/ingest/<source>.py` → `data/inbox/text/` (сырые материалы) → отдельный модуль `core/generators/idea_extractor.py` (Claude отбирает идеи) → `data/content_calendar/` (плановые посты).

## Что НЕ сюда

- Картинки/видео из Kling — это пользовательский inbox, идёт в `data/inbox/video/` руками, не через автосбор
- Внешние API публикаторов — это `core/publishers/`
