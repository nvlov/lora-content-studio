"""Реестр визуальных референсов Лоры — эмоций и связанных с ними картинок.

Используется в двух местах:
- Claude prompt-generator: передаём картинку Лоры как image-блок, чтобы модель
  «видела» её внешность и точнее описывала в английском промпте для Kling.
- gpt-image-2 /edits: прикладываем картинку как референс к запросу генерации
  для сохранения консистентности персонажа.

Источник файлов: scripts/optimize_lora_assets.py (оптимизированные JPG 1024×1024).
"""
import base64
from pathlib import Path
from typing import Literal, Optional, TypedDict

import config

ASSETS_DIR: Path = config.BASE_DIR / "core" / "assets" / "optimized"


# Регистр эмоций — короткие ключи → файлы.
# Описание используется в промпте Claude чтобы помочь модели интерпретировать картинку.
EMOTIONS: dict[str, dict] = {
    "greetings": {
        "file": "lora_greetings_v1.jpg",
        "description": "Лора приветствует зрителя — тёплая открытая улыбка, дружелюбный взгляд",
    },
    "praises": {
        "file": "lora_praises_v1.jpg",
        "description": "Лора хвалит — широкая радостная улыбка, поощряющий жест",
    },
    "corrects": {
        "file": "lora_corrects.jpg",
        "description": "Лора мягко поправляет — лёгкая улыбка, акцент на «обрати внимание»",
    },
    "explains": {
        "file": "lora_explains.jpg",
        "description": "Лора объясняет — спокойный сосредоточенный взгляд, поясняющий жест рукой",
    },
    "thinks": {
        "file": "lora_thinks_v1.jpg",
        "description": "Лора размышляет — задумчивое выражение, рука у подбородка",
    },
    "surprise": {
        "file": "lora_surprise.jpg",
        "description": "Лора удивляется — приподнятые брови, лёгкое восхищение",
    },
    "neutral": {
        "file": "lora_var21_var1_2_j2_1.jpg",
        "description": "Лора в нейтральной позе — базовый внешний вид персонажа",
    },
}

DEFAULT_EMOTION: str = "greetings"


# Маппинг ключей рубрик (из core/prompts.py) → эмоций.
# Подобрано смыслово — рубрика про ошибки → «correcting», факт → «explains» и т.п.
RUBRIC_TO_EMOTION: dict[str, str] = {
    "business_english": "explains",
    "common_mistake": "corrects",
    "free_topic": "greetings",
    "grammar_simple": "explains",
    "mini_fact": "surprise",
    "phrase_from_life": "greetings",
    "slang_informal": "praises",
    "word_of_day": "praises",
}


EmotionKey = Literal[
    "greetings", "praises", "corrects", "explains", "thinks", "surprise", "neutral",
]


class ReferencePayload(TypedDict):
    emotion: str
    description: str
    path: Path
    data_b64: str
    media_type: str


def resolve_emotion(
    *,
    rubric_key: Optional[str] = None,
    emotion: Optional[str] = None,
) -> str:
    """Возвращает ключ эмоции по приоритету: явный emotion → маппинг рубрики → дефолт."""
    if emotion and emotion in EMOTIONS:
        return emotion
    if rubric_key and rubric_key in RUBRIC_TO_EMOTION:
        mapped = RUBRIC_TO_EMOTION[rubric_key]
        if mapped in EMOTIONS:
            return mapped
    return DEFAULT_EMOTION


def get_reference_path(
    *,
    rubric_key: Optional[str] = None,
    emotion: Optional[str] = None,
) -> Optional[Path]:
    """Путь до файла. None если оптимизированной картинки нет на диске."""
    key = resolve_emotion(rubric_key=rubric_key, emotion=emotion)
    path = ASSETS_DIR / EMOTIONS[key]["file"]
    return path if path.exists() else None


def load_reference(
    *,
    rubric_key: Optional[str] = None,
    emotion: Optional[str] = None,
) -> Optional[ReferencePayload]:
    """Возвращает b64-данные референсной картинки + описание эмоции.
    None если файла нет (assets не оптимизированы — Lora-режим выключен)."""
    key = resolve_emotion(rubric_key=rubric_key, emotion=emotion)
    meta = EMOTIONS[key]
    path = ASSETS_DIR / meta["file"]
    if not path.exists():
        return None
    raw = path.read_bytes()
    return ReferencePayload(
        emotion=key,
        description=meta["description"],
        path=path,
        data_b64=base64.b64encode(raw).decode("ascii"),
        media_type="image/jpeg",
    )


def list_available_emotions() -> list[dict]:
    """Список доступных эмоций (для UI-дропдауна или диагностики)."""
    out = []
    for key, meta in EMOTIONS.items():
        path = ASSETS_DIR / meta["file"]
        out.append({
            "key": key,
            "description": meta["description"],
            "available": path.exists(),
        })
    return out
