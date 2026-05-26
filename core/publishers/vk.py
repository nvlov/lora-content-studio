"""Клиент VK API для публикации текстовых постов в сообщество.

С v0.3.0 проект публикует только текст: VK с 2025 года не выдаёт scope
wall/photos/video приложениям-третьих-сторон («extended API access no longer
issued» — официальная политика VK), а community-токены не могут загружать
медиа в группу (code 27 на photos.getWallUploadServer / video.save, см.
docs/sessions/2026-05-11-vk-oauth-complete.md).

Используется community access token. Все вызовы синхронные через httpx.
Эндпоинты:
- wall.post — публикация поста

OAuth 2.1 инфраструктура (`core/vk_oauth.py`, `_ensure_fresh_token`)
оставлена в коде как «спящая заготовка» на случай если VK сменит политику
по media scope.

Документация: https://dev.vk.com/method
"""
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

import config
from core.logging_utils import log_ai_call
from core.publishers.base import BasePublisher, PublishResult, PublishError

log = logging.getLogger(__name__)


def _parse_iso_to_utc(s: str) -> Optional[datetime]:
    """Парсит ISO 8601 строку в timezone-aware UTC datetime."""
    if not s:
        return None
    try:
        s2 = s.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class VKAPIError(PublishError):
    """Понятная ошибка VK API, безопасная для показа пользователю.

    Наследуется от PublishError — это позволяет общему коду (scheduler, manage.py)
    ловить любые ошибки публикации через `except PublishError`, а VK-специфичный
    код может явно ловить VKAPIError если нужно.
    """


class VKAuthExpiredError(VKAPIError):
    """Refresh-token истёк/инвалидирован — нужна повторная авторизация через get_vk_token.py."""


# Коды ошибок VK, переведённые на русский для UI.
_VK_ERROR_HINTS = {
    5: "Токен ВК недействителен или истёк. Обнови VK_COMMUNITY_TOKEN в .env "
       "(VK → группа → Управление → Работа с API → Создать ключ).",
    9: "Превышен лимит публикаций. Подожди и попробуй снова.",
    14: "VK требует капчу. Попробуй чуть позже.",
    15: "Доступ запрещён. Проверь права токена (должны быть: стена, управление).",
    100: "Один из параметров VK API не принят (обычно неверный group_id или формат).",
    214: "Запись на стене недоступна (у токена нет права 'стена').",
}


def _check_vk_error(payload: dict, request_type: str) -> None:
    """Бросает VKAPIError, если в ответе VK поле 'error'."""
    err = payload.get("error")
    if not err:
        return
    code = err.get("error_code")
    raw_msg = err.get("error_msg") or "VK API error"
    human = _VK_ERROR_HINTS.get(code, raw_msg)
    full = f"VK API ({request_type}): {human} [code={code}]"
    log_ai_call(provider="vk", request_type=request_type, success=False, error=full)
    raise VKAPIError(full)


class VKClient:
    """Минимальный клиент VK API для текстового постинга в сообщество."""

    HTTP_TIMEOUT = 60.0

    # Один lock на класс — OAuth refresh должен быть взаимоисключающим даже между
    # несколькими экземплярами VKClient в одном процессе (планировщик + API).
    _refresh_lock = threading.Lock()

    def __init__(
        self,
        token: Optional[str] = None,
        group_id: Optional[int] = None,
        api_version: Optional[str] = None,
    ):
        gid = group_id if group_id is not None else config.VK_GROUP_ID
        try:
            self.group_id = int(str(gid).strip().lstrip("-"))
        except (TypeError, ValueError):
            self.group_id = 0
        self.api_version = api_version or config.VK_API_VERSION

        # Источник токена: 'oauth_user' (VK ID, спящая ветка) или 'legacy_community'.
        self.token_source: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self._refresh_token: Optional[str] = None
        self._app_id: Optional[str] = None
        self._device_id: Optional[str] = None

        if token is not None:
            self.token = token.strip()
        elif config.VK_USER_ACCESS_TOKEN and config.VK_USER_REFRESH_TOKEN:
            # Спящая OAuth-ветка — оставлена на случай смены политики VK.
            self.token = config.VK_USER_ACCESS_TOKEN
            self._refresh_token = config.VK_USER_REFRESH_TOKEN
            self.token_expires_at = _parse_iso_to_utc(config.VK_USER_TOKEN_EXPIRES_AT)
            self._app_id = config.VK_OAUTH_APP_ID
            self._device_id = config.VK_OAUTH_DEVICE_ID
            self.token_source = "oauth_user"
        elif config.VK_COMMUNITY_TOKEN:
            self.token = config.VK_COMMUNITY_TOKEN.strip()
            self.token_source = "legacy_community"
        else:
            self.token = ""

    def is_configured(self) -> bool:
        return bool(self.token) and self.group_id > 0

    # ------------------------------------------------------------
    # Auto-refresh OAuth-токена (спящая ветка, используется только если в .env
    # появятся VK_USER_ACCESS_TOKEN + VK_USER_REFRESH_TOKEN)
    # ------------------------------------------------------------

    def _ensure_fresh_token(self) -> None:
        """Если до истечения < 5 мин — рефрешит access_token через refresh_token.

        Для legacy-токена ничего не делает (community-token живёт до отзыва вручную).
        """
        if self.token_source != "oauth_user":
            return
        if not self._refresh_token or not self._app_id or not self._device_id:
            return
        if self.token_expires_at is None:
            return
        now = datetime.now(timezone.utc)
        if now < self.token_expires_at - timedelta(minutes=5):
            return

        with VKClient._refresh_lock:
            if self.token_expires_at and now < self.token_expires_at - timedelta(minutes=5):
                return

            from core.publishers.vk_oauth import refresh_access_token, VKOAuthError

            try:
                tokens = refresh_access_token(
                    refresh_token=self._refresh_token,
                    app_id=self._app_id,
                    device_id=self._device_id,
                )
            except VKOAuthError as e:
                msg = (
                    f"Не удалось обновить VK access_token: {e}. "
                    "Запусти `python scripts/get_vk_token.py` для повторной авторизации."
                )
                log.error(msg)
                raise VKAuthExpiredError(msg) from e

            self.token = tokens["access_token"]
            self.token_expires_at = tokens["expires_at"]
            new_refresh = tokens.get("refresh_token") or ""
            if new_refresh:
                self._refresh_token = new_refresh

            try:
                from pathlib import Path as _Path
                from scripts.get_vk_token import update_env_file
                env_path = _Path(config.BASE_DIR) / ".env"
                update_env_file(env_path, {
                    "VK_USER_ACCESS_TOKEN": self.token,
                    "VK_USER_REFRESH_TOKEN": self._refresh_token or "",
                    "VK_USER_TOKEN_EXPIRES_AT": self.token_expires_at.isoformat(),
                })
            except Exception as e:
                log.warning("Не удалось записать обновлённый VK-токен в .env: %s", e)

            log.info("VK access_token автоматически обновлён (expires_at=%s).",
                     self.token_expires_at.isoformat())

    # ------------------------------------------------------------
    # Низкоуровневый вызов API
    # ------------------------------------------------------------

    def _api(self, method: str, params: dict, request_type: str) -> dict:
        if not self.is_configured():
            raise VKAPIError("VK не настроен. Заполни VK-токен и VK_GROUP_ID в .env.")

        self._ensure_fresh_token()

        body = dict(params)
        body["access_token"] = self.token
        body["v"] = self.api_version
        url = f"{config.VK_API_BASE}/{method}"
        try:
            with httpx.Client(timeout=self.HTTP_TIMEOUT) as c:
                r = c.post(url, data=body)
        except httpx.HTTPError as e:
            err = f"Сеть недоступна при обращении к VK API: {e}"
            log_ai_call(provider="vk", request_type=request_type, success=False, error=err)
            raise VKAPIError(err) from e

        if r.status_code >= 400:
            err = f"VK API HTTP {r.status_code}: {r.text[:300]}"
            log_ai_call(provider="vk", request_type=request_type, success=False, error=err)
            raise VKAPIError(err)

        try:
            data = r.json()
        except ValueError as e:
            err = f"VK API: не JSON-ответ: {e}"
            log_ai_call(provider="vk", request_type=request_type, success=False, error=err)
            raise VKAPIError(err) from e

        _check_vk_error(data, request_type)
        return data.get("response") or {}

    # ------------------------------------------------------------
    # Wall — публикация текстового поста
    # ------------------------------------------------------------

    def post_to_wall(self, message: str) -> dict:
        """Публикует текстовый пост от имени сообщества. Возвращает {vk_post_id, vk_post_url}.

        Только текст. Прикрепление медиа удалено из проекта в v0.3.0 — VK не
        выдаёт media scope, см. docs/sessions/2026-05-11-vk-oauth-complete.md.
        """
        owner_id = -self.group_id
        params = {
            "owner_id": owner_id,
            "from_group": 1,
            "message": message,
        }

        resp = self._api("wall.post", params, "wall_post")
        post_id = resp.get("post_id")
        if post_id is None:
            raise VKAPIError(f"wall.post: нет post_id ({resp})")

        post_url = f"https://vk.com/wall{owner_id}_{post_id}"
        log_ai_call(provider="vk", request_type="wall_post", success=True)
        return {"vk_post_id": str(post_id), "vk_post_url": post_url}


# ----------------------------------------------------------------------------
# Адаптер к BasePublisher — единый интерфейс для scheduler и CLI.
# Тонкая обёртка поверх VKClient (низкоуровневый код менять не надо).
# ----------------------------------------------------------------------------


class VKPublisher(BasePublisher):
    """VK через сообщество. Только текст (v0.3.0 pivot, см. session 2026-05-11)."""

    PLATFORM = "vk"
    IMPLEMENTED = True

    def __init__(self, client: Optional[VKClient] = None):
        self._client = client or VKClient()

    def is_configured(self) -> bool:
        return self._client.is_configured()

    def publish_text(self, message: str) -> PublishResult:
        try:
            result = self._client.post_to_wall(message)
        except VKAPIError as e:
            raise PublishError(str(e)) from e
        return PublishResult(
            platform="vk",
            post_id=result["vk_post_id"],
            post_url=result["vk_post_url"],
        )

    # publish_with_image / publish_with_video — наследуем NotImplementedError.
    # VK не выдаёт media scope с 2025 года, см. docs/sessions/2026-05-11-vk-oauth-complete.md.
