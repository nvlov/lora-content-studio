"""Утилиты логирования AI-вызовов в JSONL."""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import config

log = logging.getLogger(__name__)


def log_ai_call(
    *,
    provider: str,
    request_type: str,
    model: str | None = None,
    tokens_in: int | None = None,
    tokens_out: int | None = None,
    success: bool = True,
    error: str | None = None,
    post_id: int | None = None,
) -> None:
    """Дописывает одну строку JSON в logs/ai_calls.jsonl."""
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "provider": provider,
        "request_type": request_type,
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "success": success,
        "error": error,
        "post_id": post_id,
    }
    try:
        path: Path = config.AI_LOG_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        # Логирование не должно валить основной поток
        log.warning("Не удалось записать ai_calls.jsonl: %s", e)
