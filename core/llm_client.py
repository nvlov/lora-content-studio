"""Клиент для Claude через ProxyAPI (проксирует Anthropic Messages API)."""
import logging
from typing import Optional

import httpx

import config
from core.logging_utils import log_ai_call

log = logging.getLogger(__name__)


class LLMError(Exception):
    """Понятная ошибка LLM-вызова, безопасная для показа пользователю."""


class ClaudeClient:
    """Минимальный клиент Anthropic Messages API через ProxyAPI."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.api_key = (api_key or config.PROXYAPI_KEY).strip()
        self.model = model or config.LLM_MODEL
        self.url = base_url or config.PROXYAPI_ANTHROPIC_URL
        self.timeout = timeout

    def generate(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 2000,
    ) -> dict:
        """Возвращает {'text': str, 'tokens_in': int, 'tokens_out': int}."""
        if not self.api_key:
            err = "Не задан PROXYAPI_KEY в .env. Добавьте ключ ProxyAPI и перезапустите."
            log_ai_call(
                provider="claude", request_type="text", model=self.model,
                success=False, error=err,
            )
            raise LLMError(err)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "x-api-key": self.api_key,
            "anthropic-version": config.ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
        }

        try:
            with httpx.Client(timeout=self.timeout) as c:
                resp = c.post(self.url, headers=headers, json=body)
        except httpx.HTTPError as e:
            err = f"Сеть недоступна или таймаут при обращении к ProxyAPI: {e}"
            log_ai_call(
                provider="claude", request_type="text", model=self.model,
                success=False, error=err,
            )
            raise LLMError(err) from e

        if resp.status_code >= 400:
            err = f"ProxyAPI вернул ошибку {resp.status_code}: {resp.text[:500]}"
            log_ai_call(
                provider="claude", request_type="text", model=self.model,
                success=False, error=err,
            )
            raise LLMError(err)

        try:
            data = resp.json()
            # Anthropic Messages API: data["content"] = [{"type":"text","text":"..."}, ...]
            parts = data.get("content") or []
            text = "".join(p.get("text", "") for p in parts if p.get("type") == "text").strip()
            usage = data.get("usage") or {}
            tokens_in = int(usage.get("input_tokens") or 0) or None
            tokens_out = int(usage.get("output_tokens") or 0) or None
        except (ValueError, KeyError, TypeError) as e:
            err = f"Не удалось распарсить ответ ProxyAPI: {e}"
            log_ai_call(
                provider="claude", request_type="text", model=self.model,
                success=False, error=err,
            )
            raise LLMError(err) from e

        if not text:
            err = "ProxyAPI вернул пустой текст. Попробуйте ещё раз."
            log_ai_call(
                provider="claude", request_type="text", model=self.model,
                success=False, error=err,
            )
            raise LLMError(err)

        log_ai_call(
            provider="claude", request_type="text", model=self.model,
            tokens_in=tokens_in, tokens_out=tokens_out, success=True,
        )
        return {"text": text, "tokens_in": tokens_in, "tokens_out": tokens_out}
