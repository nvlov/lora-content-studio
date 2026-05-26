"""JSON API: рубрики, генерация текста, CRUD постов (только текст с v0.3.1),
медиа-лаборатория (отдельный workflow для генерации промптов и сохранения файлов),
публикация в VK."""
import logging
import mimetypes
import re
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from flask import Blueprint, jsonify, request, send_from_directory
from sqlalchemy import or_

import config
from core.storage.db import SessionLocal
from core.storage.models import Post, Rubric, MediaAsset, MediaPrompt
from core.generators.llm_client import ClaudeClient, LLMError
from core.generators.image_clients import KlingImageProvider, OpenAIImageProvider, ImageError
from core.generators.prompt_generator import generate_kling_prompt
from core.generators.lora_references import get_reference_path, resolve_emotion, list_available_emotions
from core.publishers.vk import VKClient, VKAPIError
from core.publishers import PublishError
from core.scheduler import schedule_post, cancel_scheduled_post, publish_now

log = logging.getLogger(__name__)
bp = Blueprint("api", __name__, url_prefix="/api")


# ============================================================
# helpers
# ============================================================

def _err(message: str, status: int = 400):
    return jsonify({"error": message}), status


# VK не рендерит markdown — `**bold**` и `__italic__` показываются сырьём со
# звёздочками и подчёркиваниями. Снимаем парные маркеры из текста поста,
# оставляя содержимое. Одиночные `*` и `_` не трогаем (URL, идиомы).
_MD_BOLD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_MD_UNDERLINE = re.compile(r"__(.+?)__", re.DOTALL)


def _strip_vk_unfriendly_markdown(text: str) -> str:
    text = _MD_BOLD.sub(r"\1", text)
    text = _MD_UNDERLINE.sub(r"\1", text)
    return text


def _parse_iso_utc(s: str) -> datetime | None:
    """Парсит ISO 8601 (с/без Z) в naive UTC datetime."""
    if not s:
        return None
    raw = s.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    # vk-launch-001 фикс: правильная конвертация в UTC (раньше ошибочно уходило в локальную TZ)
    if dt.tzinfo is not None:
        from datetime import timezone as _tz
        dt = dt.astimezone(_tz.utc).replace(tzinfo=None)
    return dt


# ============================================================
# rubrics (read-only list)
# ============================================================

@bp.get("/rubrics")
def list_rubrics():
    s = SessionLocal()
    try:
        items = s.query(Rubric).all()
        # Сортируем по фиксированному порядку: основные → новые
        order = ["word_of_day", "common_mistake", "phrase_from_life", "grammar_simple",
                 "business_english", "slang_informal", "mini_fact", "free_topic"]
        items.sort(key=lambda r: order.index(r.key) if r.key in order else 999)
        return jsonify([
            {"key": r.key, "name": r.name, "emoji": r.emoji,
             "is_free_topic": r.key == "free_topic"}
            for r in items
        ])
    finally:
        s.close()


# ============================================================
# text generation
# ============================================================

@bp.post("/generate-text")
def generate_text():
    data = request.get_json(silent=True) or {}
    rubric_key = (data.get("rubric_key") or "").strip()
    topic = (data.get("topic") or "").strip()

    if not rubric_key:
        return _err("Не выбрана рубрика.")

    s = SessionLocal()
    try:
        rubric = s.get(Rubric, rubric_key)
        if not rubric:
            return _err("Рубрика не найдена.", 404)
        system_prompt = rubric.system_prompt
    finally:
        s.close()

    # Для свободной рубрики topic = описание задачи (большой текст)
    if rubric_key == "free_topic":
        if not topic:
            return _err("Опиши задачу для свободной рубрики.")
        user_message = topic
    else:
        user_message = f"Тема: {topic}" if topic else "Тема не задана — выбери сам."

    try:
        client = ClaudeClient()
        result = client.generate(
            system_prompt=system_prompt,
            user_message=user_message,
            max_tokens=config.LLM_MAX_TOKENS,
        )
    except LLMError as e:
        return _err(str(e), 502)

    return jsonify({"text": _strip_vk_unfriendly_markdown(result["text"])})


# ============================================================
# image generation (Kling)
# ============================================================

@bp.post("/generate-image")
def generate_image():
    data = request.get_json(silent=True) or {}
    prompt = (data.get("prompt") or "").strip()
    aspect_ratio = (data.get("aspect_ratio") or "1:1").strip()

    if not prompt:
        return _err("Пустой промпт картинки.")

    try:
        provider = KlingImageProvider()
        filename = provider.generate(prompt=prompt, aspect_ratio=aspect_ratio)
    except ImageError as e:
        return _err(str(e), 502)

    return jsonify({
        "image_path": filename,
        "image_url": f"/static/uploads/{filename}",
        "image_source": "kling",
    })


# ============================================================
# posts CRUD (только текст с v0.3.1; медиа из формы поста удалены)
# ============================================================

@bp.post("/posts")
def create_post():
    data = request.get_json(silent=True) or {}
    rubric_key = (data.get("rubric_key") or "").strip()
    text_content = (data.get("text_content") or "").strip()
    if not rubric_key:
        return _err("Не выбрана рубрика.")
    if not text_content:
        return _err("Текст поста пуст.")

    s = SessionLocal()
    try:
        post = Post(
            rubric_key=rubric_key,
            topic=(data.get("topic") or None),
            text_content=text_content,
            status="draft",
        )
        s.add(post)
        s.commit()
        s.refresh(post)
        return jsonify(post.to_dict()), 201
    finally:
        s.close()


@bp.get("/posts")
def list_posts():
    search = (request.args.get("search") or "").strip()
    status = (request.args.get("status") or "").strip()
    rubric_key = (request.args.get("rubric_key") or "").strip()

    s = SessionLocal()
    try:
        q = s.query(Post).filter(Post.deleted_at.is_(None))
        if search:
            like = f"%{search}%"
            q = q.filter(or_(Post.text_content.ilike(like), Post.topic.ilike(like)))
        if status:
            q = q.filter(Post.status == status)
        if rubric_key:
            q = q.filter(Post.rubric_key == rubric_key)
        q = q.order_by(Post.updated_at.desc())
        items = [p.to_dict() for p in q.all()]
        return jsonify(items)
    finally:
        s.close()


@bp.get("/posts/<int:post_id>")
def get_post(post_id: int):
    s = SessionLocal()
    try:
        p = s.get(Post, post_id)
        if not p or p.deleted_at is not None:
            return _err("Пост не найден.", 404)
        return jsonify(p.to_dict())
    finally:
        s.close()


@bp.patch("/posts/<int:post_id>")
def update_post(post_id: int):
    data = request.get_json(silent=True) or {}
    s = SessionLocal()
    try:
        p = s.get(Post, post_id)
        if not p or p.deleted_at is not None:
            return _err("Пост не найден.", 404)
        for field in ("rubric_key", "topic", "text_content", "status"):
            if field in data:
                setattr(p, field, data[field])
        p.updated_at = datetime.utcnow()
        s.commit()
        s.refresh(p)
        return jsonify(p.to_dict())
    finally:
        s.close()


@bp.delete("/posts/<int:post_id>")
def delete_post(post_id: int):
    """Soft-delete: проставляем deleted_at, физически не удаляем."""
    s = SessionLocal()
    try:
        p = s.get(Post, post_id)
        if not p:
            return _err("Пост не найден.", 404)
        if p.status == "scheduled":
            cancel_scheduled_post(p.id)
        p.deleted_at = datetime.utcnow()
        if p.status == "scheduled":
            p.status = "draft"
            p.scheduled_at = None
        s.commit()
        return jsonify({"deleted": True})
    finally:
        s.close()


@bp.post("/posts/<int:post_id>/restore")
def restore_post(post_id: int):
    s = SessionLocal()
    try:
        p = s.get(Post, post_id)
        if not p:
            return _err("Пост не найден.", 404)
        p.deleted_at = None
        s.commit()
        s.refresh(p)
        return jsonify(p.to_dict())
    finally:
        s.close()


@bp.post("/posts/<int:post_id>/duplicate")
def duplicate_post(post_id: int):
    s = SessionLocal()
    try:
        src = s.get(Post, post_id)
        if not src or src.deleted_at is not None:
            return _err("Исходный пост не найден.", 404)
        new = Post(
            rubric_key=src.rubric_key,
            topic=src.topic,
            text_content=src.text_content,
            status="draft",
            parent_post_id=src.id,
        )
        s.add(new)
        s.commit()
        s.refresh(new)
        return jsonify(new.to_dict()), 201
    finally:
        s.close()


# ============================================================
# settings: rubrics edit
# ============================================================

@bp.get("/settings/rubrics")
def list_rubrics_full():
    s = SessionLocal()
    try:
        items = s.query(Rubric).all()
        order = ["word_of_day", "common_mistake", "phrase_from_life", "grammar_simple",
                 "business_english", "slang_informal", "mini_fact", "free_topic"]
        items.sort(key=lambda r: order.index(r.key) if r.key in order else 999)
        return jsonify([r.to_dict() for r in items])
    finally:
        s.close()


@bp.patch("/settings/rubrics/<string:key>")
def update_rubric(key: str):
    data = request.get_json(silent=True) or {}
    s = SessionLocal()
    try:
        r = s.get(Rubric, key)
        if not r:
            return _err("Рубрика не найдена.", 404)
        for field in ("name", "emoji", "system_prompt", "image_prompt_template"):
            if field in data and data[field] is not None:
                setattr(r, field, data[field])
        s.commit()
        s.refresh(r)
        return jsonify(r.to_dict())
    finally:
        s.close()


# ============================================================
# Media library
# ============================================================

def _is_image_ext(ext: str) -> bool:
    return ext.lower() in config.ALLOWED_IMAGE_EXTENSIONS


def _is_video_ext(ext: str) -> bool:
    return ext.lower() in config.ALLOWED_VIDEO_EXTENSIONS


@bp.post("/media/upload")
def media_upload():
    """Загрузка файла (image или video) в медиа-библиотеку.

    Опционально привязывает к промпту через `source_prompt_id` (multipart field).
    """
    f = request.files.get("file")
    if f is None or not getattr(f, "filename", ""):
        return _err("Файл не выбран.")

    original_name = f.filename
    ext = (original_name.rsplit(".", 1)[-1] or "").lower()

    is_image = _is_image_ext(ext)
    is_video = _is_video_ext(ext)
    if not (is_image or is_video):
        return _err(
            "Неподдерживаемый формат. Изображения: jpg/png/webp. Видео: mp4/webm/mov."
        )

    # Размерные лимиты
    raw = f.read()
    size = len(raw)
    if size == 0:
        return _err("Пустой файл.")
    if is_image and size > config.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        return _err(f"Изображение больше {config.MAX_UPLOAD_SIZE_MB} МБ.")
    if is_video and size > config.MAX_VIDEO_SIZE_MB * 1024 * 1024:
        return _err(f"Видео больше {config.MAX_VIDEO_SIZE_MB} МБ.")

    # Сохраняем
    target_dir: Path = config.IMAGES_DIR if is_image else config.VIDEOS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    safe_ext = ext if ext != "jpeg" else "jpg"
    filename = f"{uuid.uuid4().hex}.{safe_ext}"
    full_path = target_dir / filename
    full_path.write_bytes(raw)

    rel_path = f"{'images' if is_image else 'videos'}/{filename}"
    mime = (mimetypes.guess_type(filename)[0]
            or ("image/" + safe_ext if is_image else "video/" + safe_ext))

    width = height = None
    if is_image:
        try:
            from PIL import Image
            with Image.open(full_path) as img:
                width, height = img.size
        except Exception:
            pass

    # Опциональная привязка к промпту (multipart-форма)
    source_prompt_id = None
    raw_prompt_id = request.form.get("source_prompt_id")
    if raw_prompt_id:
        try:
            source_prompt_id = int(raw_prompt_id)
        except ValueError:
            source_prompt_id = None

    s = SessionLocal()
    try:
        # Валидируем что промпт существует и тип совпадает
        if source_prompt_id is not None:
            p = s.get(MediaPrompt, source_prompt_id)
            expected_kind = "image" if is_image else "video"
            if p is None or p.media_type != expected_kind:
                source_prompt_id = None

        asset = MediaAsset(
            kind="image" if is_image else "video",
            file_path=rel_path,
            original_name=original_name[:500],
            mime_type=mime,
            size_bytes=size,
            width=width, height=height,
            source="manual_upload",
            source_prompt_id=source_prompt_id,
        )
        s.add(asset)
        s.commit()
        s.refresh(asset)
        return jsonify(asset.to_dict()), 201
    finally:
        s.close()


@bp.get("/media")
def media_list():
    kind = (request.args.get("kind") or "").strip()
    try:
        limit = max(1, min(200, int(request.args.get("limit") or 50)))
        offset = max(0, int(request.args.get("offset") or 0))
    except ValueError:
        return _err("Некорректные limit/offset.")

    s = SessionLocal()
    try:
        q = s.query(MediaAsset).filter(MediaAsset.deleted_at.is_(None))
        if kind in ("image", "video"):
            q = q.filter(MediaAsset.kind == kind)
        q = q.order_by(MediaAsset.created_at.desc()).limit(limit).offset(offset)
        return jsonify([a.to_dict() for a in q.all()])
    finally:
        s.close()


@bp.get("/media/<int:asset_id>")
def media_get(asset_id: int):
    s = SessionLocal()
    try:
        a = s.get(MediaAsset, asset_id)
        if not a or a.deleted_at is not None:
            return _err("Файл не найден.", 404)
        result = a.to_dict()
        # Прикрепляем сам промпт, если есть связь — фронту удобно показать «по какому промпту»
        if a.source_prompt_id:
            p = s.get(MediaPrompt, a.source_prompt_id)
            if p is not None:
                result["source_prompt"] = p.to_dict()
        return jsonify(result)
    finally:
        s.close()


@bp.patch("/media/<int:asset_id>")
def media_update(asset_id: int):
    """Обновляет оценку и связь с промптом. Принимает rating (-2..+2), feedback_notes, source_prompt_id."""
    data = request.get_json(silent=True) or {}
    s = SessionLocal()
    try:
        a = s.get(MediaAsset, asset_id)
        if not a or a.deleted_at is not None:
            return _err("Файл не найден.", 404)

        if "rating" in data:
            raw = data["rating"]
            if raw is None or raw == "":
                a.rating = None
            else:
                try:
                    r = int(raw)
                except (TypeError, ValueError):
                    return _err("rating должен быть числом -2..+2.")
                if not -2 <= r <= 2:
                    return _err("rating должен быть в диапазоне -2..+2.")
                a.rating = r

        if "feedback_notes" in data:
            notes = (data.get("feedback_notes") or "").strip()
            a.feedback_notes = notes or None

        if "source_prompt_id" in data:
            raw = data["source_prompt_id"]
            if raw in (None, "", 0):
                a.source_prompt_id = None
            else:
                try:
                    pid = int(raw)
                except (TypeError, ValueError):
                    return _err("source_prompt_id должен быть числом.")
                p = s.get(MediaPrompt, pid)
                if p is None or p.media_type != a.kind:
                    return _err("Промпт не найден или его media_type не совпадает с файлом.", 404)
                a.source_prompt_id = pid

        s.commit()
        s.refresh(a)
        return jsonify(a.to_dict())
    finally:
        s.close()


@bp.get("/media/<int:asset_id>/download")
def media_download(asset_id: int):
    """Отдаёт файл с правильным Content-Disposition и оригинальным именем."""
    s = SessionLocal()
    try:
        a = s.get(MediaAsset, asset_id)
        if not a or a.deleted_at is not None:
            return _err("Файл не найден.", 404)
        # file_path вида 'images/xxx.jpg' или 'videos/xxx.mp4'
        subdir, _, filename = a.file_path.partition("/")
        if subdir == "images":
            directory = config.IMAGES_DIR
        elif subdir == "videos":
            directory = config.VIDEOS_DIR
        else:
            return _err("Некорректный путь файла.", 500)
        download_name = a.original_name or filename
        return send_from_directory(
            directory, filename, as_attachment=True, download_name=download_name
        )
    finally:
        s.close()


@bp.delete("/media/<int:asset_id>")
def media_delete(asset_id: int):
    s = SessionLocal()
    try:
        a = s.get(MediaAsset, asset_id)
        if not a:
            return _err("Файл не найден.", 404)
        a.deleted_at = datetime.utcnow()
        s.commit()
        return jsonify({"deleted": True})
    finally:
        s.close()


# ============================================================
# Media: Kling prompts (v0.3.2 — один промпт под Kling)
# ============================================================

_ALLOWED_ASPECTS_IMAGE = {"1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "21:9"}
_ALLOWED_ASPECTS_VIDEO = {"1:1", "16:9", "9:16"}
_ALLOWED_DURATIONS = {5, 10}
_ALLOWED_STYLES = {"pixar_3d_brand", "photo_realistic", "flat_illustration", "watercolor", "cinematic"}
_ALLOWED_CAMERA = {"static", "pan_left", "pan_right", "dolly_in", "dolly_out",
                   "tilt_up", "tracking", "rotate_360"}
_ALLOWED_VIDEO_MODES = {"silent", "audio_en"}
_ALLOWED_PROMPT_TARGETS = {"kling", "gpt_image_2"}


@bp.post("/media/generate-kling-prompt")
def media_generate_kling_prompt():
    """Один промпт под Kling или gpt-image-2. Возвращает {prompt, negative_prompt,
    kling_hint, prompt_id}. Также сохраняет MediaPrompt в БД и возвращает его id для
    последующей привязки к файлу-результату.

    Параметр `target` (опционально):
    - 'kling' (по умолчанию) — Kling-структура (image / video / video+audio_en)
    - 'gpt_image_2' — natural-language промпт под OpenAI gpt-image-2 (только image)
    """
    data = request.get_json(silent=True) or {}
    idea = (data.get("idea_ru") or "").strip()
    media_type = (data.get("media_type") or "image").strip()
    style = (data.get("style") or "pixar_3d_brand").strip()
    aspect_ratio = (data.get("aspect_ratio") or "1:1").strip()
    user_negative_ru = (data.get("user_negative_ru") or "").strip()
    target = (data.get("target") or "kling").strip()
    rubric_key = (data.get("rubric_key") or "").strip() or None
    emotion = (data.get("emotion") or "").strip() or None
    use_reference = bool(data.get("use_reference", True))

    if not idea:
        return _err("Опиши идею.")
    if media_type not in ("image", "video"):
        return _err("media_type должен быть 'image' или 'video'.")
    if style not in _ALLOWED_STYLES:
        return _err(f"Неподдерживаемый стиль: {style}.")
    if target not in _ALLOWED_PROMPT_TARGETS:
        return _err(f"target должен быть одним из {_ALLOWED_PROMPT_TARGETS}.")
    if target == "gpt_image_2" and media_type != "image":
        return _err("target='gpt_image_2' поддерживается только для image.")

    duration = None
    camera_movement = None
    video_mode = "silent"
    dialog_en = ""
    voice_tone = ""

    if media_type == "video":
        if aspect_ratio not in _ALLOWED_ASPECTS_VIDEO:
            return _err(f"Для видео aspect_ratio допустимо: {', '.join(sorted(_ALLOWED_ASPECTS_VIDEO))}.")
        try:
            duration = int(data.get("duration") or 5)
        except (TypeError, ValueError):
            return _err("duration должен быть числом.")
        if duration not in _ALLOWED_DURATIONS:
            return _err("Длительность видео: 5 или 10 секунд.")
        camera_movement = (data.get("camera_movement") or "static").strip()
        if camera_movement not in _ALLOWED_CAMERA:
            return _err(f"Неподдерживаемое движение камеры: {camera_movement}.")
        video_mode = (data.get("video_mode") or "silent").strip()
        if video_mode not in _ALLOWED_VIDEO_MODES:
            return _err(f"Режим видео: silent или audio_en.")
        if video_mode == "audio_en":
            dialog_en = (data.get("dialog_en") or "").strip()
            voice_tone = (data.get("voice_tone") or "warm friendly").strip()
            if not dialog_en:
                return _err("Для режима «с речью» нужна английская реплика.")
    else:
        if aspect_ratio not in _ALLOWED_ASPECTS_IMAGE:
            return _err(f"Для image aspect_ratio допустимо: {', '.join(sorted(_ALLOWED_ASPECTS_IMAGE))}.")

    try:
        result = generate_kling_prompt(
            idea_ru=idea,
            media_type=media_type,
            style=style,
            aspect_ratio=aspect_ratio,
            duration=duration,
            camera_movement=camera_movement,
            video_mode=video_mode,
            dialog_en=dialog_en,
            voice_tone=voice_tone,
            user_negative_ru=user_negative_ru,
            target=target,
            rubric_key=rubric_key,
            emotion=emotion,
            use_reference=use_reference,
        )
    except LLMError as e:
        return _err(str(e), 502)

    # Сохраняем промпт в БД
    s = SessionLocal()
    try:
        p = MediaPrompt(
            idea_ru=idea,
            prompt_en=result["prompt"],
            negative_prompt_en=result["negative_prompt"] or None,
            media_type=media_type,
            style=style,
            aspect_ratio=aspect_ratio,
            duration=duration,
            camera_movement=camera_movement,
            video_mode=video_mode if media_type == "video" else None,
            dialog_en=dialog_en or None,
            voice_tone=voice_tone or None,
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        prompt_id = p.id
    finally:
        s.close()

    return jsonify({
        "prompt_id": prompt_id,
        "prompt": result["prompt"],
        "negative_prompt": result["negative_prompt"],
        "kling_hint": result["kling_hint"],
        "reference_emotion": result.get("reference_emotion"),
        "meta": result["meta"],
    })


@bp.get("/media/prompts")
def media_prompt_list():
    s = SessionLocal()
    try:
        items = s.query(MediaPrompt).order_by(MediaPrompt.created_at.desc()).limit(200).all()
        return jsonify([p.to_dict() for p in items])
    finally:
        s.close()


@bp.delete("/media/prompts/<int:prompt_id>")
def media_prompt_delete(prompt_id: int):
    s = SessionLocal()
    try:
        p = s.get(MediaPrompt, prompt_id)
        if not p:
            return _err("Промпт не найден.", 404)
        s.delete(p)
        s.commit()
        return jsonify({"deleted": True})
    finally:
        s.close()


# ============================================================
# Media: direct image generation via gpt-image-2 (ProxyAPI)
# ============================================================

_ALLOWED_GPT_IMAGE_QUALITY_UI = {"low", "medium", "high"}  # auto скрываем от UI


@bp.post("/media/generate-image")
def media_generate_image():
    """Прямая генерация картинки через ProxyAPI → gpt-image-2.

    Body:
      - prompt_id: int — id существующего MediaPrompt (предпочтительно, даёт связь)
      - prompt: str   — сырой английский промпт (fallback, если нет prompt_id)
      - size_preset: 'square' | 'vertical' | 'horizontal' | 'auto'
      - quality: 'low' | 'medium' | 'high'
    """
    data = request.get_json(silent=True) or {}
    raw_prompt_id = data.get("prompt_id")
    raw_prompt = (data.get("prompt") or "").strip()
    size_preset = (data.get("size_preset") or "square").strip()
    quality = (data.get("quality") or "high").strip()
    rubric_key = (data.get("rubric_key") or "").strip() or None
    emotion = (data.get("emotion") or "").strip() or None
    use_reference = bool(data.get("use_reference", True))

    if size_preset not in config.GPT_IMAGE_SIZE_PRESETS:
        return _err(f"size_preset должен быть одним из {set(config.GPT_IMAGE_SIZE_PRESETS)}.")
    if quality not in _ALLOWED_GPT_IMAGE_QUALITY_UI:
        return _err("quality должен быть 'low' | 'medium' | 'high'.")

    # Резолвим промпт: prompt_id приоритетнее
    prompt_text = ""
    source_prompt_id: int | None = None
    if raw_prompt_id not in (None, ""):
        try:
            source_prompt_id = int(raw_prompt_id)
        except (TypeError, ValueError):
            return _err("prompt_id должен быть числом.")
        s = SessionLocal()
        try:
            p = s.get(MediaPrompt, source_prompt_id)
            if p is None:
                return _err("Промпт не найден.", 404)
            if p.media_type != "image":
                return _err("Промпт не для изображения.")
            prompt_text = p.prompt_en
        finally:
            s.close()
    elif raw_prompt:
        prompt_text = raw_prompt
    else:
        return _err("Нужен prompt_id или prompt.")

    size = config.GPT_IMAGE_SIZE_PRESETS[size_preset]

    # Подбираем референс Лоры (если включён). Если файла нет — тихо откатываемся
    # на обычный /generations без референса.
    reference_path = None
    reference_emotion = None
    if use_reference:
        ref = get_reference_path(rubric_key=rubric_key, emotion=emotion)
        if ref is not None:
            reference_path = ref
            reference_emotion = resolve_emotion(rubric_key=rubric_key, emotion=emotion)

    try:
        provider = OpenAIImageProvider()
        if reference_path is not None:
            result = provider.generate_with_reference(
                prompt=prompt_text,
                reference_paths=[reference_path],
                size=size,
                quality=quality,
                output_format="png",
            )
        else:
            result = provider.generate(
                prompt=prompt_text,
                size=size,
                quality=quality,
                output_format="png",
            )
    except ImageError as e:
        return _err(str(e), 502)

    # Сохраняем MediaAsset со связью на промпт (если есть)
    name_suffix = f"-{reference_emotion}" if reference_emotion else ""
    s = SessionLocal()
    try:
        asset = MediaAsset(
            kind="image",
            file_path=result["file_path"],
            original_name=f"gpt-image-2-{quality}{name_suffix}.png",
            mime_type=result["mime_type"],
            size_bytes=result["size_bytes"],
            width=result["width"],
            height=result["height"],
            source="external_ai",
            prompt_used=prompt_text[:2000],
            source_prompt_id=source_prompt_id,
        )
        s.add(asset)
        s.commit()
        s.refresh(asset)
        payload = asset.to_dict()
        payload["reference_emotion"] = reference_emotion
        return jsonify(payload), 201
    finally:
        s.close()


@bp.get("/media/lora-emotions")
def media_lora_emotions():
    """Список доступных эмоций Лоры для UI-дропдауна."""
    return jsonify(list_available_emotions())


# ============================================================
# VK publishing
# ============================================================

@bp.get("/vk/status")
def vk_status():
    """Сообщает фронту, настроен ли VK и какой тип токена используется."""
    vk = VKClient()
    expires_at = vk.token_expires_at.isoformat() if vk.token_expires_at else None
    return jsonify({
        "configured": vk.is_configured(),
        "group_id": vk.group_id,
        "token_source": vk.token_source,           # 'oauth_user' | 'legacy_community' | None
        "token_expires_at": expires_at,
        # С v0.3.0 публикуем только текст; медиа-флаги намеренно убраны.
    })


@bp.post("/posts/<int:post_id>/publish-now")
def publish_post_now(post_id: int):
    s = SessionLocal()
    try:
        p = s.get(Post, post_id)
        if not p or p.deleted_at is not None:
            return _err("Пост не найден.", 404)
        if not (p.text_content or "").strip():
            return _err("Текст поста пуст.")
        if len(p.text_content) > config.VK_TEXT_LIMIT:
            return _err(f"Текст длиннее {config.VK_TEXT_LIMIT} символов — VK не примет.")
    finally:
        s.close()

    try:
        result = publish_now(post_id)
    except (VKAPIError, PublishError) as e:
        return _err(str(e), 502)
    except Exception as e:
        log.exception("publish_now error")
        return _err(f"Не удалось опубликовать: {e}", 502)

    return jsonify({"success": True, **result})


@bp.post("/posts/<int:post_id>/schedule")
def schedule_post_endpoint(post_id: int):
    data = request.get_json(silent=True) or {}
    when = _parse_iso_utc(data.get("scheduled_at") or "")
    if not when:
        return _err("Некорректный формат scheduled_at (ожидается ISO 8601, UTC).")

    now = datetime.utcnow()
    if when <= now + timedelta(minutes=4):
        return _err("Время публикации должно быть минимум через 5 минут.")

    s = SessionLocal()
    try:
        p = s.get(Post, post_id)
        if not p or p.deleted_at is not None:
            return _err("Пост не найден.", 404)
        if not (p.text_content or "").strip():
            return _err("Текст поста пуст.")
        if len(p.text_content) > config.VK_TEXT_LIMIT:
            return _err(f"Текст длиннее {config.VK_TEXT_LIMIT} символов — VK не примет.")

        p.status = "scheduled"
        p.scheduled_at = when
        p.last_publish_error = None
        s.commit()
        s.refresh(p)
    finally:
        s.close()

    try:
        schedule_post(post_id, when)
    except Exception as e:
        log.exception("scheduler error")
        return _err(f"Не удалось зарегистрировать задачу: {e}", 500)

    return jsonify({"success": True, "scheduled_at": when.isoformat() + "Z", "post_id": post_id})


@bp.delete("/posts/<int:post_id>/schedule")
def schedule_post_cancel(post_id: int):
    s = SessionLocal()
    try:
        p = s.get(Post, post_id)
        if not p:
            return _err("Пост не найден.", 404)
        if p.status == "scheduled":
            p.status = "draft"
            p.scheduled_at = None
            s.commit()
    finally:
        s.close()
    cancel_scheduled_post(post_id)
    return jsonify({"success": True})


@bp.get("/posts/<int:post_id>/publication-history")
def publication_history(post_id: int):
    s = SessionLocal()
    try:
        p = s.get(Post, post_id)
        if not p or p.deleted_at is not None:
            return _err("Пост не найден.", 404)
        history = []
        if p.published_at and p.vk_post_url:
            history.append({
                "published_at": p.published_at.isoformat() + "Z",
                "vk_post_id": p.vk_post_id,
                "vk_post_url": p.vk_post_url,
            })
        return jsonify({
            "post_id": p.id,
            "status": p.status,
            "scheduled_at": p.scheduled_at.isoformat() + "Z" if p.scheduled_at else None,
            "last_publish_error": p.last_publish_error,
            "history": history,
        })
    finally:
        s.close()
