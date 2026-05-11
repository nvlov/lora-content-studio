"""Клиент VK API для публикации в сообщество (фото, видео, стена).

Использует community access token. Все методы синхронные через httpx.
Эндпоинты:
- photos.getWallUploadServer / photos.saveWallPhoto
- video.save (отдельный upload-url)
- wall.post

Документация: https://dev.vk.com/method
"""
import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import httpx

import config
from core.logging_utils import log_ai_call

log = logging.getLogger(__name__)


def _parse_iso_to_utc(s: str) -> Optional[datetime]:
    """Парсит ISO 8601 строку в timezone-aware UTC datetime."""
    if not s:
        return None
    try:
        # Поддержка 'Z' и offsets
        s2 = s.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class VKAPIError(Exception):
    """Понятная ошибка VK API, безопасная для показа пользователю."""


class VKAuthExpiredError(VKAPIError):
    """Refresh-token истёк/инвалидирован — нужна повторная авторизация через get_vk_token.py."""


# Часто встречающиеся коды ошибок VK с переводом на человеческий русский.
_VK_ERROR_HINTS = {
    5: "Токен ВК недействителен или истёк. Получи новый user-токен через OAuth (см. README) и обнови .env.",
    7: "У токена нет прав на это действие. Нужны права wall, photos, video, manage.",
    9: "Превышен лимит публикаций. Подожди и попробуй снова.",
    14: "VK требует капчу. Попробуй чуть позже.",
    15: "Доступ запрещён: токен не имеет нужного scope. В Self Service VK-приложения "
        "(id.vk.com → твоё приложение → раздел разрешений) включи wall, photos, video, "
        "groups, offline и пройди OAuth заново через scripts/get_vk_token.py.",
    27: "Метод недоступен с community-токеном. Для постов с медиа нужен USER-токен админа (см. README, OAuth-flow).",
    100: "Один из параметров VK API не принят (обычно неверный group_id или формат).",
    214: "Запись на стене недоступна (нужны права wall в токене).",
    1051: "Метод недоступен для текущего типа VK-приложения. У VK ID Standalone-приложений "
          "доступ к video.save/photos.* выдаётся только после расширенной верификации "
          "в VK Бизнес ID. См. id.vk.com → Self Service → Верификация.",
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
    """Минимальный клиент VK API для постинга в сообщество."""

    HTTP_TIMEOUT = 60.0
    UPLOAD_TIMEOUT = 300.0  # видео могут грузиться долго

    # Один lock на класс — refresh должен быть взаимоисключающим даже между
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

        # Источник токена: 'oauth_user' (новый VK ID) или 'legacy_community' (старый).
        self.token_source: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self._refresh_token: Optional[str] = None
        self._app_id: Optional[str] = None
        self._device_id: Optional[str] = None

        if token is not None:
            # Явно переданный токен — используем как есть, без auto-refresh.
            self.token = token.strip()
        elif config.VK_USER_ACCESS_TOKEN and config.VK_USER_REFRESH_TOKEN:
            self.token = config.VK_USER_ACCESS_TOKEN
            self._refresh_token = config.VK_USER_REFRESH_TOKEN
            self.token_expires_at = _parse_iso_to_utc(config.VK_USER_TOKEN_EXPIRES_AT)
            self._app_id = config.VK_OAUTH_APP_ID
            self._device_id = config.VK_OAUTH_DEVICE_ID
            self.token_source = "oauth_user"
        elif config.VK_COMMUNITY_TOKEN:
            self.token = config.VK_COMMUNITY_TOKEN.strip()
            self.token_source = "legacy_community"
            log.info(
                "VK client использует community-токен. Фото и текст работают; "
                "видео через API недоступно (video.save → code 27 для community)."
            )
        else:
            self.token = ""

    def is_configured(self) -> bool:
        return bool(self.token) and self.group_id > 0

    def media_publish_supported(self) -> bool:
        """True если токен может загружать фото (через любую из рабочих ветвей).

        - oauth_user: фото и видео (стандартный путь photos.getWallUploadServer/video.save)
        - legacy_community: только фото через photos.getMessagesUploadServer-обход
        """
        return self.token_source in ("oauth_user", "legacy_community")

    def video_publish_supported(self) -> bool:
        """True только для oauth_user — community-токены не могут вызывать video.save."""
        return self.token_source == "oauth_user"

    # ------------------------------------------------------------
    # Auto-refresh OAuth-токена
    # ------------------------------------------------------------

    def _ensure_fresh_token(self) -> None:
        """Если до истечения < 5 мин — рефрешит access_token через refresh_token.

        Для legacy-токена ничего не делает (старый токен живёт пока живёт).
        """
        if self.token_source != "oauth_user":
            return
        if not self._refresh_token or not self._app_id or not self._device_id:
            return
        if self.token_expires_at is None:
            return  # без срока — не трогаем
        now = datetime.now(timezone.utc)
        if now < self.token_expires_at - timedelta(minutes=5):
            return  # ещё свежий

        with VKClient._refresh_lock:
            # Повторная проверка — другой поток мог уже обновить.
            if self.token_expires_at and now < self.token_expires_at - timedelta(minutes=5):
                return

            # Импорт внутри функции — чтобы не было циклической зависимости при импорте модуля.
            from core.vk_oauth import refresh_access_token, VKOAuthError

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

            # Сохраняем в .env, чтобы пережить рестарт.
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
                # Если запись в .env не удалась — токен в памяти всё равно свежий, продолжаем.
                log.warning("Не удалось записать обновлённый VK-токен в .env: %s", e)

            log.info("VK access_token автоматически обновлён (expires_at=%s).",
                     self.token_expires_at.isoformat())

    # ------------------------------------------------------------
    # Низкоуровневый вызов API
    # ------------------------------------------------------------

    def _api(self, method: str, params: dict, request_type: str) -> dict:
        if not self.is_configured():
            raise VKAPIError("VK не настроен. Заполни VK-токен и VK_GROUP_ID в .env.")

        # Авто-рефреш OAuth-токена (для legacy — no-op).
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
    # Photos
    # ------------------------------------------------------------

    def upload_photo(self, image_abs_path: str) -> str:
        """Загружает фото и возвращает attachment-строку 'photo{owner}_{id}'.

        Использует messages-upload-server (а не getWallUploadServer): этот путь
        работает с community-токеном, тогда как классический getWallUploadServer
        VK закрыл для group-auth (code 27). Полученный photo-attachment
        универсален и корректно прикрепляется к wall.post.
        """
        path = Path(image_abs_path)
        if not path.exists() or not path.is_file():
            raise VKAPIError(f"Файл не найден: {image_abs_path}")

        # 1) получаем upload_url через messages-upload-server для сообщества
        srv = self._api("photos.getMessagesUploadServer",
                        {"group_id": self.group_id}, "upload_photo")
        upload_url = srv.get("upload_url")
        if not upload_url:
            raise VKAPIError("VK не вернул upload_url для фото.")

        # 2) грузим файл в upload_url полем 'photo'
        try:
            with httpx.Client(timeout=self.UPLOAD_TIMEOUT) as c:
                with path.open("rb") as f:
                    files = {"photo": (path.name, f, "application/octet-stream")}
                    r = c.post(upload_url, files=files)
        except httpx.HTTPError as e:
            raise VKAPIError(f"Сеть упала при загрузке фото в VK: {e}") from e
        if r.status_code >= 400:
            raise VKAPIError(f"VK upload фото вернул HTTP {r.status_code}: {r.text[:200]}")
        try:
            up = r.json()
        except ValueError as e:
            raise VKAPIError(f"VK upload фото: не JSON: {e}") from e

        if not up.get("photo") or up.get("photo") == "[]":
            raise VKAPIError("VK upload фото: пустой ответ (возможно, файл некорректный).")

        # 3) сохраняем фото — saveMessagesPhoto, парный к getMessagesUploadServer
        saved = self._api("photos.saveMessagesPhoto", {
            "server": up.get("server"),
            "photo": up.get("photo"),
            "hash": up.get("hash"),
        }, "upload_photo")

        if not saved or not isinstance(saved, list):
            raise VKAPIError(f"photos.saveMessagesPhoto: неожиданный ответ {saved}")
        first = saved[0]
        owner = first.get("owner_id")
        pid = first.get("id")
        if owner is None or pid is None:
            raise VKAPIError(f"photos.saveMessagesPhoto: нет owner_id/id в ответе ({first})")

        log_ai_call(provider="vk", request_type="upload_photo", success=True)
        return f"photo{owner}_{pid}"

    # ------------------------------------------------------------
    # Video
    # ------------------------------------------------------------

    def upload_video(self, video_abs_path: str, name: str = "post video", description: str = "") -> str:
        """Загружает видео в сообщество, возвращает attachment 'video{owner}_{id}'.

        ⚠ Для community-токенов VK блокирует video.save с code 27. Бросаем
        понятную ошибку до похода в VK, чтобы пользователь сразу понял что
        делать. Когда (и если) у нас появится user-token с media scope —
        этот early-return можно убрать.
        """
        if self.token_source == "legacy_community":
            raise VKAPIError(
                "Загрузка видео в группу через VK API заблокирована для "
                "community-токенов (video.save → code 27). Опубликуй пост с "
                "текстом, потом добавь видео в VK вручную через «Изменить запись»."
            )

        path = Path(video_abs_path)
        if not path.exists() or not path.is_file():
            raise VKAPIError(f"Файл не найден: {video_abs_path}")

        # 1) video.save — получаем upload_url + owner_id + video_id
        save = self._api("video.save", {
            "group_id": self.group_id,
            "name": name[:128],
            "description": description[:500] if description else "",
            "wallpost": 0,
            "is_private": 0,
        }, "upload_video")

        upload_url = save.get("upload_url")
        owner = save.get("owner_id")
        vid = save.get("video_id")
        if not upload_url or owner is None or vid is None:
            raise VKAPIError(f"video.save: нет upload_url/owner_id/video_id ({save})")

        # 2) грузим файл полем 'video_file'
        try:
            with httpx.Client(timeout=self.UPLOAD_TIMEOUT) as c:
                with path.open("rb") as f:
                    files = {"video_file": (path.name, f, "application/octet-stream")}
                    r = c.post(upload_url, files=files)
        except httpx.HTTPError as e:
            raise VKAPIError(f"Сеть упала при загрузке видео в VK: {e}") from e
        if r.status_code >= 400:
            raise VKAPIError(f"VK upload видео вернул HTTP {r.status_code}: {r.text[:200]}")
        # ответ обычно {"size":..., "video_id":...} — не критичен; видео обработается асинхронно

        log_ai_call(provider="vk", request_type="upload_video", success=True)
        return f"video{owner}_{vid}"

    # ------------------------------------------------------------
    # Wall
    # ------------------------------------------------------------

    def post_to_wall(self, message: str, attachments: Optional[list[str]] = None) -> dict:
        """Публикует пост от имени сообщества. Возвращает {vk_post_id, vk_post_url}."""
        owner_id = -self.group_id
        params = {
            "owner_id": owner_id,
            "from_group": 1,
            "message": message,
        }
        if attachments:
            params["attachments"] = ",".join(a for a in attachments if a)

        resp = self._api("wall.post", params, "wall_post")
        post_id = resp.get("post_id")
        if post_id is None:
            raise VKAPIError(f"wall.post: нет post_id ({resp})")

        post_url = f"https://vk.com/wall{owner_id}_{post_id}"
        log_ai_call(provider="vk", request_type="wall_post", success=True)
        return {"vk_post_id": str(post_id), "vk_post_url": post_url}
