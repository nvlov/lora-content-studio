"""Генерация промптов для внешних AI-сервисов (image / video) через Claude."""
import json
import logging
import re
from typing import Literal

from core.llm_client import ClaudeClient, LLMError

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """Ты — эксперт по prompt engineering для AI-генераторов изображений и видео (Kling AI, utopy.ai, MidJourney, DALL-E).

Задача: пользователь даёт идею на русском — ты возвращаешь 3 варианта детального английского промпта в указанном стиле и соотношении сторон.

БРЕНДОВЫЕ ОГРАНИЧЕНИЯ (обязательны для стиля pixar_3d_brand):
— Палитра: кремовый (#F5EFE0), горчичный (#C8862C), тёмно-зелёный (#1F3A2E), тёплый коричневый (#3D2817)
— Стиль: soft Pixar-3D, тёплый, дружелюбный
— Если изображается персонаж Лоры: молодая девушка с кудрявыми рыжими волосами, в горчичном свитере, тёплая улыбка
— Никакого текста внутри картинки (no readable text, no overlays, no captions)
— Тёплое освещение (warm soft lighting)

СТРУКТУРА КАЖДОГО ПРОМПТА:
1. Subject (что/кто в кадре)
2. Setting (где, окружение)
3. Style descriptor (стиль)
4. Lighting (освещение)
5. Color palette (палитра)
6. Mood (настроение)
7. Aspect ratio (в конце)

Для ВИДЕО дополнительно: указание на движение/действие (camera slowly pans, character gestures, leaves move in soft breeze).

ВЫХОД: верни строго JSON-массив из 3 объектов:
[
  {"variant": "A", "prompt": "...", "best_for": "Kling AI"},
  {"variant": "B", "prompt": "...", "best_for": "utopy.ai"},
  {"variant": "C", "prompt": "...", "best_for": "MidJourney"}
]

Промпты должны отличаться: например, A — более минималистичный, B — более детальный, C — с альтернативной композицией.
Никакого текста до или после JSON."""


STYLE_LABELS = {
    "pixar_3d_brand": "Soft Pixar-3D, фирменная палитра Лоры (кремовый/горчичный/тёмно-зелёный)",
    "photo_realistic": "Photo-realistic, естественное освещение",
    "flat_illustration": "Flat 2D illustration, чистые линии",
    "watercolor": "Watercolor painting style",
    "cinematic": "Cinematic, кинематографический",
}


def generate_media_prompts(
    idea_ru: str,
    media_type: Literal["image", "video"] = "image",
    style: str = "pixar_3d_brand",
    aspect_ratio: str = "1:1",
) -> list[dict]:
    """Возвращает список из 3 dict: {variant, prompt, best_for}."""
    if not idea_ru.strip():
        raise LLMError("Опишите идею для промпта.")

    style_label = STYLE_LABELS.get(style, style)
    user_msg = (
        f"Идея на русском: {idea_ru.strip()}\n"
        f"Тип медиа: {media_type}\n"
        f"Стиль: {style_label}\n"
        f"Соотношение сторон: {aspect_ratio}\n\n"
        f"Верни ТОЛЬКО JSON-массив из 3 промптов."
    )

    client = ClaudeClient()
    result = client.generate(system_prompt=SYSTEM_PROMPT, user_message=user_msg, max_tokens=2000)
    raw = result["text"].strip()

    # Иногда модель оборачивает JSON в ```json ... ``` — снимаем обёртку
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if not m:
        raise LLMError("Не удалось извлечь JSON-массив из ответа модели.")
    try:
        variants = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise LLMError(f"Ответ модели не является валидным JSON: {e}") from e

    if not isinstance(variants, list) or len(variants) < 1:
        raise LLMError("Модель вернула пустой список вариантов.")

    # Нормализуем
    out = []
    for i, v in enumerate(variants[:3]):
        if not isinstance(v, dict):
            continue
        out.append({
            "variant": str(v.get("variant") or chr(65 + i)),
            "prompt": str(v.get("prompt") or "").strip(),
            "best_for": str(v.get("best_for") or "Generic"),
        })
    if not out:
        raise LLMError("Не удалось распарсить ни одного варианта.")
    return out
