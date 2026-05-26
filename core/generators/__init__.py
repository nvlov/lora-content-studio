"""Генераторы контента — слой, который превращает идею/рубрику в готовый артефакт.

Модули:
- `llm_client.py` — клиент Claude через ProxyAPI.
- `prompts.py` — системные промпты и реестр рубрик.
- `prompt_generator.py` — Kling-промпт-генератор (текстовый промпт для видео-генерации).
- `image_clients.py` — клиенты для генерации изображений (gpt-image-2 через ProxyAPI, Kling — legacy).
- `lora_references.py` — реестр визуальных эмоций Лоры для Claude Vision и gpt-image-2 /edits.

В перспективе сюда же:
- `structured_output.py` — Claude с JSON-schema response (если потребуется автопостинг по плану).
- `video_pipeline.py` — связка с внешним Kling Web (`data/inbox/video/` → пост).
"""
