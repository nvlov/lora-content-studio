# docs/schemas/ — JSON-схемы данных проекта

Формальные схемы (JSON Schema draft-07) для обменных форматов между Skill'ами, CLI и БД.

## Файлы

### `lora-post-v1.json`

Схема черновика поста, который генерирует Skill [`lora-post-builder`](../../.claude/skills/lora-post-builder/SKILL.md) и импортирует CLI-команда `manage.py import-from-json`.

**Где живут файлы по этой схеме:** `data/inbox/text/YYYY-MM-DD-<rubric>-<slug>.json` (папка в `.gitignore`, рабочий буфер между Skill и БД).

**Жизненный цикл:**

```
[пользователь даёт идею или URL в Claude Code]
        ↓
[Skill lora-post-builder → собирает контекст, читает рубрики из core/generators/prompts.py]
        ↓
data/inbox/text/<file>.json   (по этой схеме)
        ↓
[manage.py import-from-json + gpt-image-2 /edits с референсом эмоции]
        ↓
БД (Post.draft + MediaAsset) + static/uploads/images/<uuid>.png
        ↓
[ревью + публикация через Flask UI или manage.py publish]
```

**Обязательные поля:** `schema_version`, `rubric_key`, `topic`, `emotion`, `platforms.vk.content`, `image_prompt`.

**Опциональные:** `source`, `platforms.telegram.content`, `kling_prompt`, `notes`.

## Принципы

- Schema-version в каждом файле (`schema_version: "lora-post/v1"`) — для будущих миграций формата.
- Поля строго ограничены через `additionalProperties: false` (исключение — `source` для гибкости источников).
- Лимиты длины платформ-контента указаны в схеме (`vk.content` max 4096 — VK-лимит; `telegram.content` тоже 4096 для совместимости).
- Enum-списки (`rubric_key`, `emotion`) фиксируют валидные значения — расширение требует обновления и схемы, и кода (`core/storage/models.py`, `core/generators/lora_references.py`).

## Валидация

Сейчас `manage.py import-from-json` делает минимальную проверку обязательных полей. Полная валидация по схеме (через библиотеку `jsonschema`) — backlog, добавится когда формат расширится до v2.
