"""Клиент VK API для публикации в сообщество (фото, видео, стена).

Использует community access token. Все методы синхронные через httpx.
Эндпоинты:
- photos.getWallUploadServer / photos.saveWallPhoto
- video.save (отдельный upload-url)
- wall.post

Документация: https://dev.vk.com/method
"""
import logging
from pathlib import Path
from typing import Optional

import httpx

import config
from core.logging_utils import log_ai_call

log = logging.getLogger(__name__)


class VKAPIError(Exception):
    """Понятная ошибка VK API, безопасная для показа пользователю."""


# Часто встречающиеся коды ошибок VK с переводом на человеческий русский.
_VK_ERROR_HINTS = {
    5: "Токен ВК недействителен или истёк. Получи новый user-токен через OAuth (см. README) и обнови .env.",
    7: "У токена нет прав на это действие. Нужны права wall, photos, video, manage.",
    9: "Превышен лимит публикаций. Подожди и попробуй снова.",
    14: "VK требует капчу. Попробуй чуть позже.",
    15: "Доступ запрещён. Проверь, что ты — админ группы и group_id в .env корректный.",
    27: "Метод недоступен с community-токеном. Для постов с медиа нужен USER-токен админа (см. README, OAuth-flow).",
    100: "Один из параметров VK API не принят (обычно неверный group_id или формат).",
    214: "Запись на стене недоступна (нужны права wall в токене).",
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

    def __init__(
        self,
        token: Optional[str] = None,
        group_id: Optional[int] = None,
        api_version: Optional[str] = None,
    ):
        self.token = (token or config.VK_COMMUNITY_TOKEN).strip()
        gid = group_id if group_id is not None else config.VK_GROUP_ID
        try:
            self.group_id = int(str(gid).strip().lstrip("-"))
        except (TypeError, ValueError):
            self.group_id = 0
        self.api_version = api_version or config.VK_API_VERSION

    def is_configured(self) -> bool:
        return bool(self.token) and self.group_id > 0

    # ------------------------------------------------------------
    # Низкоуровневый вызов API
    # ------------------------------------------------------------

    def _api(self, method: str, params: dict, request_type: str) -> dict:
        if not self.is_configured():
            raise VKAPIError("VK не настроен. Заполни VK_COMMUNITY_TOKEN и VK_GROUP_ID в .env.")

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
        """Загружает фото на стену сообщества, возвращает attachment-строку 'photo{owner}_{id}'."""
        path = Path(image_abs_path)
        if not path.exists() or not path.is_file():
            raise VKAPIError(f"Файл не найден: {image_abs_path}")

        # 1) получаем upload_url
        srv = self._api("photos.getWallUploadServer",
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

        # 3) сохраняем фото на стену
        saved = self._api("photos.saveWallPhoto", {
            "group_id": self.group_id,
            "server": up.get("server"),
            "photo": up.get("photo"),
            "hash": up.get("hash"),
        }, "upload_photo")

        if not saved or not isinstance(saved, list):
            raise VKAPIError(f"photos.saveWallPhoto: неожиданный ответ {saved}")
        first = saved[0]
        owner = first.get("owner_id")
        pid = first.get("id")
        if owner is None or pid is None:
            raise VKAPIError(f"photos.saveWallPhoto: нет owner_id/id в ответе ({first})")

        log_ai_call(provider="vk", request_type="upload_photo", success=True)
        return f"photo{owner}_{pid}"

    # ------------------------------------------------------------
    # Video
    # ------------------------------------------------------------

    def upload_video(self, video_abs_path: str, name: str = "post video", description: str = "") -> str:
        """Загружает видео в сообщество, возвращает attachment 'video{owner}_{id}'."""
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
