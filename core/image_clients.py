"""Провайдеры изображений: Kling AI (text-to-image), OpenAI gpt-image-2 через
ProxyAPI и ручная загрузка файла."""
import base64
import io
import logging
import time
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import httpx
import jwt as pyjwt
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
# JWT helper для Kling (HS256, через библиотеку PyJWT)
# ============================================================

def _build_kling_jwt(access_key: str, secret_key: str) -> str:
    """Формирует короткоживущий JWT для Kling AI: iss=AK, exp=+30мин, nbf=-5сек."""
    now = int(time.time())
    payload = {"iss": access_key, "exp": now + 1800, "nbf": now - 5}
    return pyjwt.encode(payload, secret_key, algorithm="HS256", headers={"typ": "JWT"})


# ============================================================
# Kling AI text-to-image
# ============================================================

class KlingImageProvider(ImageProvider):
    """Генерация картинки через Kling AI v1 (text-to-image)."""

    POLL_INTERVAL_SEC = 5.0
    POLL_TIMEOUT_SEC = 180.0

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
        out_path: Path = config.IMAGES_DIR / filename
        out_path.write_bytes(content)
        # возвращаем относительный путь от static/uploads/
        return f"images/{filename}"


# ============================================================
# OpenAI gpt-image-2 через ProxyAPI
# ============================================================

class OpenAIImageProvider:
    """Генерация картинки через ProxyAPI → OpenAI Images API (gpt-image-2).

    Синхронный POST: ProxyAPI блокирует ответ, возвращает base64 готовой картинки.
    Не наследует ImageProvider — иной интерфейс (size в пикселях, quality).
    """

    REQUEST_TIMEOUT_SEC = 360.0  # gpt-image-2 на high+1024 может занимать 3-5 минут

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = (api_key or config.PROXYAPI_KEY).strip()
        self.model = (model or config.OPENAI_IMAGE_MODEL).strip()

    def generate(
        self,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "high",
        output_format: str = "png",
    ) -> dict:
        """Делает запрос на генерацию, сохраняет файл локально, возвращает метаданные.

        Возвращает: {
            "file_path": "images/<uuid>.png",
            "width": int, "height": int,
            "size_bytes": int,
            "mime_type": "image/png",
            "tokens_in": int | None,
            "tokens_out": int | None,
        }
        """
        if not self.api_key:
            err = "Не задан PROXYAPI_KEY в .env."
            log_ai_call(provider="proxyapi_openai", request_type="image",
                        model=self.model, success=False, error=err)
            raise ImageError(err)
        if not prompt.strip():
            raise ImageError("Пустой промпт картинки.")
        if quality not in config.GPT_IMAGE_QUALITY_LEVELS:
            raise ImageError(f"quality должен быть одним из {config.GPT_IMAGE_QUALITY_LEVELS}.")
        if output_format not in ("png", "jpeg", "webp"):
            raise ImageError("output_format должен быть png/jpeg/webp.")

        body = {
            "model": self.model,
            "prompt": prompt,
            "n": 1,
            "size": size,
            "quality": quality,
            "output_format": output_format,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.REQUEST_TIMEOUT_SEC) as c:
                r = c.post(config.PROXYAPI_OPENAI_IMAGES_URL, headers=headers, json=body)
        except httpx.HTTPError as e:
            err = f"Сеть недоступна при обращении к ProxyAPI: {e}"
            log_ai_call(provider="proxyapi_openai", request_type="image",
                        model=self.model, success=False, error=err)
            raise ImageError(err) from e

        if r.status_code >= 400:
            err = f"ProxyAPI вернул {r.status_code}: {r.text[:500]}"
            log_ai_call(provider="proxyapi_openai", request_type="image",
                        model=self.model, success=False, error=err)
            raise ImageError(err)

        try:
            data = r.json()
        except ValueError as e:
            err = f"Ответ ProxyAPI не JSON: {e}"
            log_ai_call(provider="proxyapi_openai", request_type="image",
                        model=self.model, success=False, error=err)
            raise ImageError(err) from e

        items = data.get("data") or []
        if not items or not items[0].get("b64_json"):
            err = f"ProxyAPI не вернул b64_json. Ответ: {str(data)[:400]}"
            log_ai_call(provider="proxyapi_openai", request_type="image",
                        model=self.model, success=False, error=err)
            raise ImageError(err)

        # Декодируем base64 → bytes → файл
        try:
            raw = base64.b64decode(items[0]["b64_json"])
        except (ValueError, TypeError) as e:
            err = f"Не удалось декодировать base64 от ProxyAPI: {e}"
            log_ai_call(provider="proxyapi_openai", request_type="image",
                        model=self.model, success=False, error=err)
            raise ImageError(err) from e

        ext = "jpg" if output_format == "jpeg" else output_format
        filename = f"{uuid.uuid4().hex}.{ext}"
        out_path: Path = config.IMAGES_DIR / filename
        out_path.write_bytes(raw)

        # Размеры — открываем через PIL (для последующего показа)
        width = height = None
        try:
            with Image.open(out_path) as img:
                width, height = img.size
        except Exception:
            pass

        usage = data.get("usage") or {}
        tokens_in = usage.get("input_tokens")
        tokens_out = usage.get("output_tokens")

        log_ai_call(
            provider="proxyapi_openai",
            request_type="image",
            model=self.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            success=True,
        )

        return {
            "file_path": f"images/{filename}",
            "width": width,
            "height": height,
            "size_bytes": len(raw),
            "mime_type": f"image/{output_format if output_format != 'jpeg' else 'jpeg'}",
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }

    def generate_with_reference(
        self,
        prompt: str,
        reference_paths: list,
        size: str = "1024x1024",
        quality: str = "high",
        output_format: str = "png",
    ) -> dict:
        """Генерация через /v1/images/edits с приложенными референсами.

        OpenAI /edits принимает до 16 файлов в поле image[]. Возвращает b64_json
        как и /generations. Используется для сохранения внешности Лоры.
        """
        if not self.api_key:
            err = "Не задан PROXYAPI_KEY в .env."
            log_ai_call(provider="proxyapi_openai", request_type="image",
                        model=self.model, success=False, error=err)
            raise ImageError(err)
        if not prompt.strip():
            raise ImageError("Пустой промпт картинки.")
        if not reference_paths:
            raise ImageError("Нужен хотя бы один референс для /edits.")
        if quality not in config.GPT_IMAGE_QUALITY_LEVELS:
            raise ImageError(f"quality должен быть одним из {config.GPT_IMAGE_QUALITY_LEVELS}.")
        if output_format not in ("png", "jpeg", "webp"):
            raise ImageError("output_format должен быть png/jpeg/webp.")

        edits_url = config.PROXYAPI_OPENAI_IMAGES_URL.replace("/generations", "/edits")

        files = []
        opened = []
        try:
            for p in reference_paths:
                f = open(p, "rb")
                opened.append(f)
                mime = "image/jpeg" if str(p).lower().endswith((".jpg", ".jpeg")) else "image/png"
                files.append(("image[]", (Path(p).name, f, mime)))

            data = {
                "model": self.model,
                "prompt": prompt,
                "n": "1",
                "size": size,
                "quality": quality,
                "output_format": output_format,
            }
            headers = {"Authorization": f"Bearer {self.api_key}"}

            try:
                with httpx.Client(timeout=self.REQUEST_TIMEOUT_SEC) as c:
                    r = c.post(edits_url, headers=headers, files=files, data=data)
            except httpx.HTTPError as e:
                err = f"Сеть недоступна при обращении к ProxyAPI /edits: {e}"
                log_ai_call(provider="proxyapi_openai", request_type="image",
                            model=self.model, success=False, error=err)
                raise ImageError(err) from e
        finally:
            for f in opened:
                try:
                    f.close()
                except OSError:
                    pass

        if r.status_code >= 400:
            err = f"ProxyAPI /edits вернул {r.status_code}: {r.text[:500]}"
            log_ai_call(provider="proxyapi_openai", request_type="image",
                        model=self.model, success=False, error=err)
            raise ImageError(err)

        try:
            data = r.json()
        except ValueError as e:
            err = f"Ответ ProxyAPI /edits не JSON: {e}"
            log_ai_call(provider="proxyapi_openai", request_type="image",
                        model=self.model, success=False, error=err)
            raise ImageError(err) from e

        items = data.get("data") or []
        if not items or not items[0].get("b64_json"):
            err = f"ProxyAPI /edits не вернул b64_json. Ответ: {str(data)[:400]}"
            log_ai_call(provider="proxyapi_openai", request_type="image",
                        model=self.model, success=False, error=err)
            raise ImageError(err)

        try:
            raw = base64.b64decode(items[0]["b64_json"])
        except (ValueError, TypeError) as e:
            err = f"Не удалось декодировать base64 от ProxyAPI: {e}"
            raise ImageError(err) from e

        ext = "jpg" if output_format == "jpeg" else output_format
        filename = f"{uuid.uuid4().hex}.{ext}"
        out_path: Path = config.IMAGES_DIR / filename
        out_path.write_bytes(raw)

        width = height = None
        try:
            with Image.open(out_path) as img:
                width, height = img.size
        except Exception:
            pass

        usage = data.get("usage") or {}
        tokens_in = usage.get("input_tokens")
        tokens_out = usage.get("output_tokens")

        log_ai_call(
            provider="proxyapi_openai", request_type="image", model=self.model,
            tokens_in=tokens_in, tokens_out=tokens_out, success=True,
        )

        return {
            "file_path": f"images/{filename}",
            "width": width,
            "height": height,
            "size_bytes": len(raw),
            "mime_type": f"image/{output_format if output_format != 'jpeg' else 'jpeg'}",
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }


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
        out_path: Path = config.IMAGES_DIR / filename
        save_kwargs = {"quality": 90} if out_ext == "jpg" else {}
        img.save(out_path, **save_kwargs)
        log_ai_call(provider="manual_upload", request_type="image", success=True)
        return f"images/{filename}"
