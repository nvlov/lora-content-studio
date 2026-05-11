"""VK ID OAuth 2.1 helper — PKCE, exchange, refresh.

Public client flow (без client_secret). Эндпоинты подтверждены исходниками
VKCOM/vkid-android-sdk; см. docs/vk-oauth-research.md.

Архитектура: manual-paste flow. Браузер открывается локально, VK редиректит
на https://oauth.vk.com/blank.html, пользователь копирует полный URL и
вставляет в терминал — мы парсим code/state/device_id и обмениваем на токены.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode, urlparse, parse_qs

import httpx

import config
from core.logging_utils import log_ai_call

log = logging.getLogger(__name__)

# RFC 7636: 43-128 символов из unreserved set.
_PKCE_VERIFIER_BYTES = 64  # → 86 base64url-символов (в пределах 128)


class VKOAuthError(Exception):
    """Понятная ошибка VK ID OAuth, безопасная для показа пользователю."""


def _b64url_no_pad(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def generate_pkce_pair() -> tuple[str, str]:
    """Возвращает (code_verifier, code_challenge). Алгоритм s256.

    code_verifier — base64url-no-padding от 64 случайных байт.
    code_challenge — base64url-no-padding(sha256(verifier)).
    """
    verifier = _b64url_no_pad(secrets.token_bytes(_PKCE_VERIFIER_BYTES))
    challenge = _b64url_no_pad(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def generate_state() -> str:
    """CSRF-state: 32 hex-символа."""
    return secrets.token_hex(16)


def build_authorize_url(
    app_id: str,
    redirect_uri: str,
    scope: str,
    code_challenge: str,
    state: str,
) -> str:
    """Собирает URL для GET https://id.vk.com/authorize.

    device_id в URL НЕ передаётся (он только в POST на /oauth2/auth).
    """
    params = {
        "client_id": app_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": "s256",  # нижний регистр — обязательно
        "state": state,
        "scope": scope,
    }
    return f"{config.VK_OAUTH_AUTHORIZE_URL}?{urlencode(params)}"


def parse_callback_url(url: str, expected_state: str) -> dict:
    """Разбирает URL вида https://oauth.vk.com/blank.html?code=...&state=...&device_id=...

    Возвращает {'code', 'state', 'device_id'}. Бросает VKOAuthError при ошибке VK
    или несовпадении state (CSRF).
    """
    if not url or not url.strip():
        raise VKOAuthError("Пустой URL.")
    try:
        parsed = urlparse(url.strip())
    except ValueError as e:
        raise VKOAuthError(f"Не удалось разобрать URL: {e}") from e

    # VK кладёт параметры в query (?...), но на всякий случай поддержим и fragment (#...).
    qs = parsed.query or parsed.fragment
    if not qs:
        raise VKOAuthError("В URL нет query-параметров — проверь, что скопировал полный адрес из адресной строки.")
    q = parse_qs(qs)

    err = (q.get("error") or [None])[0]
    if err:
        desc = (q.get("error_description") or [""])[0]
        raise VKOAuthError(f"VK вернул ошибку авторизации: {err} ({desc})")

    code = (q.get("code") or [None])[0]
    state = (q.get("state") or [None])[0]
    device_id = (q.get("device_id") or [None])[0]

    if not code:
        raise VKOAuthError("В URL нет параметра 'code'.")
    if not state:
        raise VKOAuthError("В URL нет параметра 'state' (защита от CSRF).")
    if state != expected_state:
        raise VKOAuthError(
            "state в callback URL не совпадает с ожидаемым — возможна атака CSRF "
            "или ты вставил URL от другой попытки авторизации."
        )
    if not device_id:
        raise VKOAuthError("В URL нет параметра 'device_id' — VK ID должен его прислать.")

    return {"code": code, "state": state, "device_id": device_id}


def _post_token_endpoint(form: dict, request_type: str) -> dict:
    """POST на /oauth2/auth с form-body, парсинг ответа, нормализация в dict."""
    try:
        with httpx.Client(timeout=30.0) as c:
            r = c.post(
                config.VK_OAUTH_TOKEN_URL,
                data=form,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except httpx.HTTPError as e:
        msg = f"Сеть недоступна при обращении к VK ID: {e}"
        log_ai_call(provider="vk_oauth", request_type=request_type, success=False, error=msg)
        raise VKOAuthError(msg) from e

    try:
        data = r.json()
    except ValueError as e:
        msg = f"VK ID: не JSON-ответ (HTTP {r.status_code}): {r.text[:300]}"
        log_ai_call(provider="vk_oauth", request_type=request_type, success=False, error=msg)
        raise VKOAuthError(msg) from e

    if r.status_code >= 400 or "error" in data:
        err = data.get("error") or f"HTTP {r.status_code}"
        desc = data.get("error_description") or data.get("error_msg") or ""
        msg = f"VK ID вернул ошибку: {err} ({desc})"
        log_ai_call(provider="vk_oauth", request_type=request_type, success=False, error=msg)
        raise VKOAuthError(msg)

    if "access_token" not in data:
        msg = f"VK ID: в ответе нет access_token. Ответ: {data}"
        log_ai_call(provider="vk_oauth", request_type=request_type, success=False, error=msg)
        raise VKOAuthError(msg)

    expires_in = int(data.get("expires_in") or 0)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in or 86400)

    result = {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "expires_at": expires_at,
        "expires_in": expires_in,
        "user_id": data.get("user_id"),
        "scope": data.get("scope", ""),
        "id_token": data.get("id_token"),
    }
    log_ai_call(provider="vk_oauth", request_type=request_type, success=True)
    return result


def exchange_code_for_tokens(
    code: str,
    code_verifier: str,
    app_id: str,
    redirect_uri: str,
    device_id: str,
    state: str,
) -> dict:
    """POST grant_type=authorization_code → пара (access_token, refresh_token)."""
    form = {
        "grant_type": "authorization_code",
        "code": code,
        "code_verifier": code_verifier,
        "client_id": app_id,
        "device_id": device_id,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return _post_token_endpoint(form, "exchange")


def refresh_access_token(
    refresh_token: str,
    app_id: str,
    device_id: str,
    state: str | None = None,
) -> dict:
    """POST grant_type=refresh_token → новый access_token (+ часто новый refresh_token)."""
    form = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": app_id,
        "device_id": device_id,
        "state": state or generate_state(),
    }
    return _post_token_endpoint(form, "refresh")
