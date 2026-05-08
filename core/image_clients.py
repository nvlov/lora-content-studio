"""Провайдеры изображений: Kling AI (text-to-image) и ручная загрузка файла."""
import base64
import hashlib
import hmac
import io
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import httpx
from PIL import Image

import config
from core.logging_utils import log_ai_call

log = logging.getLogger(__name__)


class ImageError(Exception):
    """Ошибка генерации/загрузки изображения, безопасная для показа пользователю."""


# ============================================================
# Базовый интерфейс
# ============================================================

class ImageProvider(ABC):
    """Абстрактный провайдер картинки. Возвращает локальный путь от static/uploads/."""

    @abstractmethod
    def generate(self, prompt: str, aspect_ratio: str = "1:1") -> str:
        ...


# ============================================================
# JWT helper для Kling (HS256, без сторонних библиотек)
# ============================================================

def _b64url(data: bytes) -> bytes:
    """URL-safe base64 без паддинга."""
    return base64.urlsafe_b64encode(data).rstrip(b"=")


def _build_kling_jwt(access_key: str, secret_key: str) -> str:
    """Формирует короткоживущий JWT для Kling AI: iss=AK, exp=+30мин, nbf=-5сек."""
    header = {"alg": "HS256", "typ": "JWT"}
    now = int(time.time())
    payload = {"iss": access_key, "exp": now + 1800, "nbf": now - 5}

    h = _b64url(json.dumps(header, separators=(",", ":"), sort_keys=False).encode())
    p = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=False).encode())
    signing_input = h + b"." + p
    sig = hmac.new(secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return (signing_input + b"." + _b64url(sig)).decode("ascii")


# ============================================================
# Kling AI text-to-image
# ============================================================

class KlingImageProvider(ImageProvider):
    """Генерация картинки через Kling AI v1 (text-to-image)."""

    POLL_INTERVAL_SEC = 3.0
    POLL_TIMEOUT_SEC = 120.0

    def __init__(
        self,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: str = "kling-v1",
    ):
        self.access_key = (access_key or config.KLING_ACCESS_KEY).strip()
        self.secret_key = (secret_key or config.KLING_SECRET_KEY).strip()
        self.base_url = (base_url or config.KLING_BASE_URL).rstrip("/")
        self.model_name = model_name

    def _headers(self) -> dict:
        token = _build_kling_jwt(self.access_key, self.secret_key)
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def generate(self, prompt: str, aspect_ratio: str = "1:1") -> str:
        if not self.access_key or not self.secret_key:
            err = "Не заданы KLING_ACCESS_KEY / KLING_SECRET_KEY в .env."
            log_ai_call(provider="kling", request_type="image", success=False, error=err)
            raise ImageError(err)

        create_url = self.base_url + config.KLING_T2I_CREATE
        body = {
            "model_name": self.model_name,
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "n": 1,
        }

        # 1) создаём задачу
        try:
            with httpx.Client(timeout=30.0) as c:
                r = c.post(create_url, headers=self._headers(), json=body)
        except httpx.HTTPError as e:
            err = f"Сеть недоступна при обращении к Kling: {e}"
            log_ai_call(provider="kling", request_type="image", success=False, error=err)
            raise ImageError(err) from e

        if r.status_code >= 400:
            err = f"Kling вернул ошибку {r.status_code}: {r.text[:500]}"
            log_ai_call(provider="kling", request_type="image", success=False, error=err)
            raise ImageError(err)

        try:
            data = r.json()
            # Kling: { code, message, data: { task_id, task_status, ... } }
            task_id = (data.get("data") or {}).get("task_id")
        except (ValueError, KeyError, TypeError) as e:
            err = f"Не удалось распарсить ответ Kling: {e}"
            log_ai_call(provider="kling", request_type="image", success=False, error=err)
            raise ImageError(err) from e

        if not task_id:
            err = f"Kling не вернул task_id. Ответ: {data}"
            log_ai_call(provider="kling", request_type="image", success=False, error=err)
            raise ImageError(err)

        # 2) поллим статус
        image_url = self._poll_for_image(task_id)

        # 3) скачиваем картинку локально
        local_path = self._download_image(image_url)
        log_ai_call(provider="kling", request_type="image", success=True)
        return local_path

    def _poll_for_image(self, task_id: str) -> str:
        get_url = f"{self.base_url}{config.KLING_T2I_CREATE}/{task_id}"
        deadline = time.time() + self.POLL_TIMEOUT_SEC
        last_status = "?"
        while time.time() < deadline:
            try:
                with httpx.Client(timeout=20.0) as c:
                    r = c.get(get_url, headers=self._headers())
            except httpx.HTTPError as e:
                err = f"Сеть упала при опросе Kling: {e}"
                log_ai_call(provider="kling", request_type="image", success=False, error=err)
                raise ImageError(err) from e

            if r.status_code >= 400:
                err = f"Kling poll {r.status_code}: {r.text[:300]}"
                log_ai_call(provider="kling", request_type="image", success=False, error=err)
                raise ImageError(err)

            payload = (r.json() or {}).get("data") or {}
            last_status = payload.get("task_status", "?")
            if last_status == "succeed":
                images = (payload.get("task_result") or {}).get("images") or []
                if not images:
                    err = "Kling: задача завершена, но картинок нет."
                    log_ai_call(provider="kling", request_type="image", success=False, error=err)
                    raise ImageError(err)
                return images[0].get("url") or ""
            if last_status == "failed":
                msg = payload.get("task_status_msg") or "без описания"
                err = f"Kling: задача завершилась с ошибкой ({msg})."
                log_ai_call(provider="kling", request_type="image", success=False, error=err)
                raise ImageError(err)

            time.sleep(self.POLL_INTERVAL_SEC)

        err = f"Kling: превышен таймаут ожидания (последний статус: {last_status})."
        log_ai_call(provider="kling", request_type="image", success=False, error=err)
        raise ImageError(err)

    def _download_image(self, image_url: str) -> str:
        if not image_url:
            raise ImageError("Kling вернул пустой URL картинки.")
        try:
            with httpx.Client(timeout=60.0, follow_redirects=True) as c:
                r = c.get(image_url)
                r.raise_for_status()
                content = r.content
        except httpx.HTTPError as e:
            raise ImageError(f"Не удалось скачать картинку из Kling: {e}") from e

        filename = f"{uuid.uuid4().hex}.png"
        out_path: Path = config.UPLOADS_DIR / filename
        out_path.write_bytes(content)
        # возвращаем относительный путь от static/uploads/
        return filename


# ============================================================
# Ручная загрузка файла пользователем
# ============================================================

class ManualUploadHandler:
    """Принимает FileStorage из Flask request.files и сохраняет картинку локально."""

    MAX_LONG_SIDE_PX = 2000  # ресайз до этого размера по большей стороне

    def save(self, file_storage) -> str:
        """Возвращает имя файла внутри static/uploads/."""
        if file_storage is None or not getattr(file_storage, "filename", ""):
            raise ImageError("Файл не выбран.")

        ext = (file_storage.filename.rsplit(".", 1)[-1] or "").lower()
        if ext not in config.ALLOWED_IMAGE_EXTENSIONS:
            raise ImageError(
                f"Допустимые форматы: {', '.join(sorted(config.ALLOWED_IMAGE_EXTENSIONS))}."
            )

        raw = file_storage.read()
        if not raw:
            raise ImageError("Пустой файл.")
        if len(raw) > config.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise ImageError(f"Файл больше {config.MAX_UPLOAD_SIZE_MB} МБ.")

        try:
            img = Image.open(io.BytesIO(raw))
            img.load()
        except Exception as e:
            raise ImageError(f"Не похоже на корректное изображение: {e}") from e

        # Ресайз до MAX_LONG_SIDE_PX по большей стороне (если нужно)
        w, h = img.size
        long_side = max(w, h)
        if long_side > self.MAX_LONG_SIDE_PX:
            scale = self.MAX_LONG_SIDE_PX / long_side
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        # Конвертация в RGB для jpg
        out_ext = "jpg" if ext in ("jpg", "jpeg") else ext
        if out_ext == "jpg" and img.mode != "RGB":
            img = img.convert("RGB")

        filename = f"{uuid.uuid4().hex}.{out_ext}"
        out_path: Path = config.UPLOADS_DIR / filename
        save_kwargs = {"quality": 90} if out_ext == "jpg" else {}
        img.save(out_path, **save_kwargs)
        log_ai_call(provider="manual_upload", request_type="image", success=True)
        return filename
