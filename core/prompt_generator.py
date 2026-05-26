"""Генератор Kling-промптов через Claude (v0.3.2).

Один промпт под Kling AI (image или video). Возвращает структурированный
английский промпт + negative_prompt + подсказку для пользователя «что выбрать
в Kling Web UI».

Поддерживаемые режимы:
- image — t2i для Kling 1.5/2.0/2.1
- video_silent — t2v без звука для Kling 2.6/3.0 Standard
- video_audio_en — t2v с нативным lip-sync для Kling 3.0 Omni (только английский)

Источник параметров: docs research 2026-05-19 (kling.ai, fal.ai, klingapi.com).
Звуковая речь поддерживается нативно только для zh/en/ja/ko/es — для RU нужен
двухэтапный LipSync (вне scope этой версии).
"""
import json
import logging
import re
from typing import Literal, Optional

from core.llm_client import ClaudeClient, LLMError
from core.lora_references import load_reference

log = logging.getLogger(__name__)


# Дополнительный блок системного промпта когда передаётся реальный референс Лоры —
# заставляет Claude использовать визуальные детали с картинки, а не общий шаблон.
_REFERENCE_BLOCK = """REFERENCE IMAGE PROVIDED:
The first content block in the user message is a reference image of Lora — the brand character.
You MUST look at the image and ground the character description in what you see:
- Hair color/shape, eye color, skin tone, age, body language
- Outfit details (colors, style, accessories)
- Facial expression and emotional tone visible in the reference

When writing the Subject part of the prompt, replace any generic Lora-template wording with
specific visual traits from the reference image. Keep the brand palette consistent."""


# ============================================================
# Бренд-константы Лоры (фиксированный системный промпт-блок)
# ============================================================

BRAND_BLOCK = """BRAND CONSTRAINTS for "pixar_3d_brand" style:
- Color palette: cream (#F5EFE0), mustard (#C8862C), dark green (#1F3A2E), warm brown (#3D2817)
- Soft Pixar-3D rendering style, warm and friendly mood
- Lora character: young female, red curly hair, mustard sweater, warm gentle smile
- No readable text or overlays inside the image
- Warm soft lighting"""


STYLE_HINTS = {
    "pixar_3d_brand": "Soft Pixar-3D, brand palette (cream/mustard/dark green), warm soft lighting",
    "photo_realistic": "Photo-realistic, natural lighting, shallow depth of field",
    "flat_illustration": "Flat 2D illustration, clean vector lines, minimal shading",
    "watercolor": "Watercolor painting, soft edges, paper texture",
    "cinematic": "Cinematic, anamorphic lens, dramatic lighting, film grain",
}


CAMERA_HINTS = {
    "static": "static medium shot, no camera movement",
    "pan_left": "camera slowly pans left",
    "pan_right": "camera slowly pans right",
    "dolly_in": "camera slowly dollies in toward subject (slow push-in)",
    "dolly_out": "camera slowly dollies out from subject (slow pull-back)",
    "tilt_up": "camera tilts upward",
    "tracking": "tracking shot, camera follows subject",
    "rotate_360": "camera slowly rotates 360 around subject",
}


# ============================================================
# Системные промпты по типу медиа
# ============================================================

_SYSTEM_IMAGE = f"""You are a prompt engineer for Kling AI text-to-image generation (kling-v1.5 / v2.0 / v2.1).

Your task: turn a Russian idea into ONE production-ready English prompt that follows Kling's expected structure.

{BRAND_BLOCK}

KLING t2i PROMPT STRUCTURE (in this order):
1. Subject — what/who is in frame
2. Setting — where, environment, props
3. Style descriptor — selected style (see below)
4. Lighting — explicit lighting direction
5. Color palette — explicit palette
6. Mood — emotional atmosphere

PROMPT BUDGET: 30-60 English words. No more than 7 distinct visual elements (Kling morphs above that).
AVOID: conflicting lighting (e.g. golden hour + studio), text inside the image, overly long negative-style descriptions in the main prompt.

OUTPUT FORMAT — return ONLY valid JSON, nothing before or after:
{{"prompt": "<the English prompt>", "negative_prompt": "<short English negative — face morphing, distorted hands, etc>", "kling_hint": "<one-line Russian hint: which Kling model + aspect to choose>"}}"""


_SYSTEM_VIDEO_SILENT = f"""You are a prompt engineer for Kling AI text-to-video generation (kling-v1.6, v2.6 std/pro, v3.0 standard — no audio).

Your task: turn a Russian idea into ONE production-ready English prompt with motion description.

{BRAND_BLOCK}

KLING t2v PROMPT STRUCTURE (in this order):
1. Subject — character/object in frame
2. Action / motion — what is happening, gestures, movement (REQUIRED for video)
3. Setting — environment
4. Style descriptor
5. Camera — explicit camera behavior (use the camera hint provided)
6. Lighting / mood

PROMPT BUDGET: 30-60 English words. Max 7 visual elements. ALWAYS include a motion phrase (gestures, camera movement, or scene motion like "leaves move in soft breeze").
AVOID: conflicting motions (slow-mo + time-lapse), simultaneous rotation+zoom, conflicting lighting.

OUTPUT FORMAT — return ONLY valid JSON, nothing before or after:
{{"prompt": "<the English prompt>", "negative_prompt": "<short English negative — face morphing, distorted hands, blur, text overlays>", "kling_hint": "<one-line Russian hint: which Kling model + duration + aspect to choose>"}}"""


_SYSTEM_GPT_IMAGE_2 = f"""You are a prompt engineer for OpenAI gpt-image-2 (reasoning-based text-to-image model).

Your task: turn a Russian idea into ONE production-ready English prompt written as fluent natural language (NOT a Kling-style attribute list). gpt-image-2 reasons over descriptive prose and renders text faithfully.

{BRAND_BLOCK}

PROMPT STYLE for gpt-image-2:
- Write 2-4 natural English sentences describing the scene as a photographer or art director would.
- Lead with the subject, then setting, then explicit style, then lighting/mood. Embed the brand color palette inside the prose.
- If user listed things to avoid, integrate them as positive instructions ("clean background without text overlays", "natural hands with five fingers"). gpt-image-2 does NOT accept a separate negative_prompt API parameter.
- Aspect/size is controlled outside the prompt (size parameter), so DO NOT write "16:9" or "vertical format" inside the prompt unless the framing itself matters.
- If readable text should appear in the image, quote the exact wording.

PROMPT BUDGET: 40-90 English words. Concrete and visual, no marketing fluff.

OUTPUT FORMAT — return ONLY valid JSON, nothing before or after:
{{"prompt": "<the English natural-language prompt>", "negative_prompt": "", "kling_hint": "<one-line Russian hint about which size/quality preset suits this scene best>"}}"""


_SYSTEM_VIDEO_AUDIO_EN = f"""You are a prompt engineer for Kling 3.0 Omni — video model with native synchronized speech and ambient audio (motion_has_audio: true).

Your task: turn a Russian idea + an English dialogue line into ONE production-ready Kling 3.0 Omni prompt with character speech tags.

{BRAND_BLOCK}

KLING 3.0 OMNI PROMPT STRUCTURE:
1. [Character: <visual description>, <voice tone>]: "<exact English dialogue line>"
2. [Scene: <setting + style + lighting + mood>]
3. [Camera: <camera behavior>]
4. (optional) [Sound: <ambient sound description, e.g. soft classroom ambience>]

EXAMPLE:
[Character: young red-haired female teacher in mustard sweater, warm friendly voice]: "Hi friends! Let's start today's lesson."
[Scene: cozy Pixar-3D classroom, cream walls and mustard accents, soft daylight from a side window, warm encouraging mood]
[Camera: static medium shot, 5 seconds, 16:9]

PROMPT BUDGET: 40-80 English words total. Speech line must be in English (Kling Omni native audio supports: zh, en, ja, ko, es — NOT Russian).
AVOID: dialogue longer than the chosen duration in seconds can fit (rule of thumb: ~2 words per second of video).

OUTPUT FORMAT — return ONLY valid JSON, nothing before or after:
{{"prompt": "<the Kling 3.0 Omni prompt with tags>", "negative_prompt": "<short English negative — face morphing, lip de-sync, distorted hands>", "kling_hint": "<one-line Russian hint: «выбери Kling 3.0 Omni, motion_has_audio: ON»>"}}"""


# ============================================================
# Главная функция
# ============================================================

VideoMode = Literal["silent", "audio_en"]
PromptTarget = Literal["kling", "gpt_image_2"]


def generate_kling_prompt(
    *,
    idea_ru: str,
    media_type: Literal["image", "video"],
    style: str = "pixar_3d_brand",
    aspect_ratio: str = "1:1",
    duration: Optional[int] = None,             # 5 или 10, только для video
    camera_movement: Optional[str] = None,      # ключ из CAMERA_HINTS, только для video
    video_mode: VideoMode = "silent",            # silent | audio_en
    dialog_en: str = "",                         # текст реплики, только для audio_en
    voice_tone: str = "warm friendly",           # интонация, только для audio_en
    user_negative_ru: str = "",                  # дополнительные «что избегать» от пользователя
    target: PromptTarget = "kling",              # kling | gpt_image_2 (только для image)
    rubric_key: Optional[str] = None,            # рубрика поста — для авто-выбора эмоции Лоры
    emotion: Optional[str] = None,               # явный ключ эмоции (перекрывает rubric_key)
    use_reference: bool = True,                  # выключить если нужно сгенерировать без референса
) -> dict:
    """Возвращает {'prompt', 'negative_prompt', 'kling_hint', 'meta'}.

    meta — что пользователь выбрал (вход), для сохранения в БД.
    Для target='gpt_image_2' промпт пишется как natural language под gpt-image-2;
    negative_prompt всегда пустой (модель не принимает его как параметр).
    """
    if not idea_ru.strip():
        raise LLMError("Опишите идею.")

    if media_type == "image" and target == "gpt_image_2":
        system_prompt = _SYSTEM_GPT_IMAGE_2
    elif media_type == "image":
        system_prompt = _SYSTEM_IMAGE
    elif media_type == "video" and video_mode == "audio_en":
        if not dialog_en.strip():
            raise LLMError("Для режима «с речью» нужна английская реплика.")
        system_prompt = _SYSTEM_VIDEO_AUDIO_EN
    elif media_type == "video":
        system_prompt = _SYSTEM_VIDEO_SILENT
    else:
        raise LLMError(f"Неизвестный media_type: {media_type}")

    style_hint = STYLE_HINTS.get(style, style)
    parts = [
        f"Idea (Russian): {idea_ru.strip()}",
        f"Style: {style_hint}",
        f"Aspect ratio: {aspect_ratio}",
    ]
    if media_type == "video":
        parts.append(f"Duration: {duration or 5} seconds")
        if camera_movement:
            cam_hint = CAMERA_HINTS.get(camera_movement, camera_movement)
            parts.append(f"Camera behavior: {cam_hint}")
        if video_mode == "audio_en":
            parts.append(f'Dialogue line (English, must appear verbatim): "{dialog_en.strip()}"')
            parts.append(f"Voice tone: {voice_tone}")
    if user_negative_ru.strip():
        parts.append(f"User wants to avoid (Russian, translate to English in negative_prompt): {user_negative_ru.strip()}")

    # Подгружаем референс Лоры (если включён и есть на диске)
    reference = load_reference(rubric_key=rubric_key, emotion=emotion) if use_reference else None
    if reference is not None:
        system_prompt = system_prompt + "\n\n" + _REFERENCE_BLOCK
        parts.insert(0, f"Emotion context: {reference['description']}")

    parts.append("\nReturn ONLY the JSON object, no markdown fence.")
    user_msg = "\n".join(parts)

    client = ClaudeClient()
    if reference is not None:
        result = client.generate(
            system_prompt=system_prompt,
            user_message=user_msg,
            max_tokens=1200,
            image_b64=reference["data_b64"],
            image_media_type=reference["media_type"],
        )
    else:
        result = client.generate(system_prompt=system_prompt, user_message=user_msg, max_tokens=1200)
    raw = result["text"].strip()

    # модель может обернуть в ```json … ``` — снимаем
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        raise LLMError("Не удалось извлечь JSON из ответа модели.")
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise LLMError(f"Ответ модели не является валидным JSON: {e}") from e

    out_prompt = str(data.get("prompt") or "").strip()
    out_negative = str(data.get("negative_prompt") or "").strip()
    out_hint = str(data.get("kling_hint") or "").strip()

    if not out_prompt:
        raise LLMError("Модель вернула пустой prompt.")

    # дефолтная подсказка если модель не дала
    if not out_hint:
        out_hint = _default_hint(media_type, aspect_ratio, duration, video_mode)

    # gpt-image-2 не принимает negative_prompt — игнорируем что вернула модель
    if target == "gpt_image_2":
        out_negative = ""

    return {
        "prompt": out_prompt,
        "negative_prompt": out_negative,
        "kling_hint": out_hint,
        "reference_emotion": reference["emotion"] if reference else None,
        "meta": {
            "idea_ru": idea_ru.strip(),
            "media_type": media_type,
            "style": style,
            "aspect_ratio": aspect_ratio,
            "duration": duration,
            "camera_movement": camera_movement,
            "video_mode": video_mode if media_type == "video" else None,
            "dialog_en": dialog_en.strip() if media_type == "video" and video_mode == "audio_en" else "",
            "voice_tone": voice_tone if media_type == "video" and video_mode == "audio_en" else "",
            "target": target,
            "reference_emotion": reference["emotion"] if reference else None,
        },
    }


def _default_hint(media_type: str, aspect_ratio: str, duration: Optional[int], video_mode: str) -> str:
    if media_type == "image":
        return f"В Kling Web UI: t2i, aspect {aspect_ratio}"
    if video_mode == "audio_en":
        return f"В Kling Web UI: выбери Kling 3.0 Omni, motion_has_audio: ON, {duration or 5}s, {aspect_ratio}"
    return f"В Kling Web UI: Kling 2.6 или 3.0 Standard, {duration or 5}s, {aspect_ratio}"
