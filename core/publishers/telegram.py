"""Telegram-публикатор через Bot API.

Контракт совместим с VKPublisher: один метод на тип публикации, возвращает
PublishResult с post_url. Используется через `core.publishers.get_publisher("telegram")`.

Документация: https://core.telegram.org/bots/api
Лимиты:
- sendMessage: до 4096 символов в тексте
- sendPhoto, sendVideo, sendDocument: до 1024 символов в caption
- sendMediaGroup (альбом): до 10 элементов
- 30 сообщений/сек глобально для бота, 1 сообщение/сек в один чат

Настройка:
1. Чат с @BotFather → /newbot → следовать инструкциям → запомнить token.
2. Создать канал, добавить бота админом с правом «Publish Messages».
3. Положить токен в TELEGRAM_BOT_TOKEN, имя канала (@username или числовой -100...)
   в TELEGRAM_CHANNEL_ID.

Без настроенных ключей публикатор отвечает «не настроен» — это позволяет
держать стаб в проекте пока канал не создан.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import httpx

import config
from core.logging_utils import log_ai_call
from core.publishers.base import BasePublisher, PublishResult, PublishError

log = logging.getLogger(__name__)


class TelegramAPIError(PublishError):
    """Ошибка Telegram API с понятным сообщением для пользователя."""


# Карта типичных описаний ошибок Bot API для UI.
_TG_ERROR_HINTS = {
    400: "Telegram отверг запрос (неверный chat_id, слишком длинный текст или caption).",
    401: "Telegram-токен невалиден. Проверь TELEGRAM_BOT_TOKEN в .env.",
    403: "Бот не имеет права публиковать в этом канале. Сделай бота админом с правом «Публиковать сообщения».",
    404: "Канал не найден. Проверь TELEGRAM_CHANNEL_ID (формат: @channelname или -100...).",
    429: "Telegram попросил замедлиться (rate limit). Попробуй позже.",
}


def _call_method(method: str, files: Optional[dict] = None, **params) -> dict:
    """Низкоуровневый POST к Bot API. Возвращает поле `result` или бросает TelegramAPIError."""
    token = config.TELEGRAM_BOT_TOKEN
    if not token:
        raise TelegramAPIError("Telegram не настроен (нет TELEGRAM_BOT_TOKEN в .env).")
    url = f"{config.TELEGRAM_API_BASE}/bot{token}/{method}"
    try:
        with httpx.Client(timeout=60.0) as c:
            r = c.post(url, data=params, files=files)
    except httpx.HTTPError as e:
        msg = f"Сеть недоступна при обращении к Telegram: {e}"
        log_ai_call(provider="telegram", request_type=method, success=False, error=msg)
        raise TelegramAPIError(msg) from e

    try:
        data = r.json()
    except ValueError as e:
        msg = f"Telegram API: не JSON-ответ ({r.status_code}): {r.text[:200]}"
        log_ai_call(provider="telegram", request_type=method, success=False, error=msg)
        raise TelegramAPIError(msg) from e

    if not data.get("ok"):
        code = r.status_code
        description = data.get("description") or "unknown error"
        hint = _TG_ERROR_HINTS.get(code, description)
        full = f"Telegram API ({method}): {hint} [code={code}]"
        log_ai_call(provider="telegram", request_type=method, success=False, error=full)
        raise TelegramAPIError(full)

    log_ai_call(provider="telegram", request_type=method, success=True)
    return data["result"]


def _build_post_url(result: dict, chat_id: str) -> str:
    """Собирает прямую ссылку на пост в формате https://t.me/<channel>/<message_id>.

    Для приватных каналов (-100xxx) ссылка вида https://t.me/c/<short_id>/<message_id>.
    Telegram API возвращает chat.id и message_id.
    """
    message_id = result.get("message_id")
    if message_id is None:
        return ""
    if chat_id.startswith("@"):
        return f"https://t.me/{chat_id[1:]}/{message_id}"
    # -100xxxxxxxxxx → внутренний chat_id для https://t.me/c/<short>/<id>.
    short = chat_id.lstrip("-").removeprefix("100")
    if short:
        return f"https://t.me/c/{short}/{message_id}"
    return ""


class TelegramPublisher(BasePublisher):
    """Публикатор в канал/группу Telegram через Bot API."""

    PLATFORM = "telegram"
    IMPLEMENTED = True

    def __init__(self):
        self.bot_token = config.TELEGRAM_BOT_TOKEN
        self.channel_id = config.TELEGRAM_CHANNEL_ID

    def is_configured(self) -> bool:
        return bool(self.bot_token) and bool(self.channel_id)

    def _require_config(self) -> None:
        if not self.is_configured():
            raise PublishError(
                "Telegram не настроен. Заполни TELEGRAM_BOT_TOKEN и "
                "TELEGRAM_CHANNEL_ID в .env (бот создаётся через @BotFather, "
                "добавляется в канал админом)."
            )

    def publish_text(self, message: str) -> PublishResult:
        self._require_config()
        if len(message) > config.TELEGRAM_TEXT_LIMIT:
            raise PublishError(
                f"Текст длиннее {config.TELEGRAM_TEXT_LIMIT} символов — Telegram не примет."
            )
        result = _call_method(
            "sendMessage",
            chat_id=self.channel_id,
            text=message,
            disable_web_page_preview="true",
        )
        return PublishResult(
            platform="telegram",
            post_id=str(result.get("message_id", "")),
            post_url=_build_post_url(result, self.channel_id),
        )

    def publish_with_image(self, message: str, image_path: Path) -> PublishResult:
        self._require_config()
        if not image_path.exists():
            raise PublishError(f"Файл картинки не найден: {image_path}")
        if len(message) > config.TELEGRAM_CAPTION_LIMIT:
            raise PublishError(
                f"Caption длиннее {config.TELEGRAM_CAPTION_LIMIT} символов — "
                "разбей текст или используй publish_text + публикацию картинки отдельно."
            )
        with image_path.open("rb") as f:
            result = _call_method(
                "sendPhoto",
                files={"photo": (image_path.name, f)},
                chat_id=self.channel_id,
                caption=message,
            )
        return PublishResult(
            platform="telegram",
            post_id=str(result.get("message_id", "")),
            post_url=_build_post_url(result, self.channel_id),
        )

    def publish_with_video(self, message: str, video_path: Path) -> PublishResult:
        self._require_config()
        if not video_path.exists():
            raise PublishError(f"Файл видео не найден: {video_path}")
        if len(message) > config.TELEGRAM_CAPTION_LIMIT:
            raise PublishError(
                f"Caption длиннее {config.TELEGRAM_CAPTION_LIMIT} символов."
            )
        with video_path.open("rb") as f:
            result = _call_method(
                "sendVideo",
                files={"video": (video_path.name, f)},
                chat_id=self.channel_id,
                caption=message,
                supports_streaming="true",
            )
        return PublishResult(
            platform="telegram",
            post_id=str(result.get("message_id", "")),
            post_url=_build_post_url(result, self.channel_id),
        )
