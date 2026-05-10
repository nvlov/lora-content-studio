"""JSON API: рубрики, генерация текста/картинки, CRUD постов, медиа-студия, публикация в VK."""
import logging
import mimetypes
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from flask import Blueprint, jsonify, request
from sqlalchemy import or_

import config
from core.db import SessionLocal
from core.models import Post, Rubric, MediaAsset, MediaPrompt
from core.llm_client import ClaudeClient, LLMError
from core.image_clients import KlingImageProvider, ManualUploadHandler, ImageError
from core.prompt_generator import generate_media_prompts
from core.vk_client import VKClient, VKAPIError
from core.scheduler import schedule_post, cancel_scheduled_post, publish_now

log = logging.getLogger(__name__)
bp = Blueprint("api", __name__, url_prefix="/api")


# ============================================================
# helpers
# ============================================================

def _err(message: str, status: int = 400):
    return jsonify({"error": message}), status


def _parse_iso_utc(s: str) -> datetime | None:
    """Парсит ISO 8601 (с/без Z) в naive UTC datetime."""
    if not s:
        return None
    raw = s.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    # Приводим к UTC naive
    if dt.tzinfo is not None:
        dt = dt.astimezone(tz=None).replace(tzinfo=None)
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

    return jsonify({"text": result["text"]})


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
# manual image upload (legacy, для обратной совместимости)
# ============================================================

@bp.post("/upload-image")
def upload_image():
    file = request.files.get("file")
    try:
        filename = ManualUploadHandler().save(file)
    except ImageError as e:
        return _err(str(e), 400)

    return jsonify({
        "image_path": filename,
        "image_url": f"/static/uploads/{filename}",
        "image_source": "manual_upload",
    })


# ============================================================
# posts CRUD
# ============================================================

def _set_media_kind(post: Post) -> None:
    """Авто-проставление media_kind по наличию video_path/image_path."""
    if post.video_path:
        post.media_kind = "video"
    elif post.image_path:
        post.media_kind = "image"
    else:
        post.media_kind = "none"


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
            image_path=(data.get("image_path") or None),
            image_prompt=(data.get("image_prompt") or None),
            image_source=(data.get("image_source") or "none"),
            video_path=(data.get("video_path") or None),
            status="draft",
        )
        _set_media_kind(post)
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
        for field in (
            "rubric_key", "topic", "text_content",
            "image_path", "image_prompt", "image_source",
            "video_path", "status",
        ):
            if field in data:
                setattr(p, field, data[field])
        _set_media_kind(p)
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
            image_path=src.image_path,
            image_prompt=src.image_prompt,
            image_source=src.image_source,
            video_path=src.video_path,
            media_kind=src.media_kind,
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
    """Загрузка файла (image или video) в медиа-библиотеку."""
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

    s = SessionLocal()
    try:
        asset = MediaAsset(
            kind="image" if is_image else "video",
            file_path=rel_path,
            original_name=original_name[:500],
            mime_type=mime,
            size_bytes=size,
            width=width, height=height,
            source="manual_upload",
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
        return jsonify(a.to_dict())
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
# Media: generated prompts
# ============================================================

@bp.post("/media/generate-prompts")
def media_generate_prompts():
    data = request.get_json(silent=True) or {}
    idea = (data.get("idea") or "").strip()
    media_type = (data.get("media_type") or "image").strip()
    style = (data.get("style") or "pixar_3d_brand").strip()
    aspect_ratio = (data.get("aspect_ratio") or "1:1").strip()

    if not idea:
        return _err("Опишите идею для промпта.")
    if media_type not in ("image", "video"):
        return _err("media_type должен быть 'image' или 'video'.")

    try:
        variants = generate_media_prompts(
            idea_ru=idea, media_type=media_type, style=style, aspect_ratio=aspect_ratio
        )
    except LLMError as e:
        return _err(str(e), 502)

    return jsonify({
        "variants": variants,
        "input": {"idea": idea, "media_type": media_type, "style": style, "aspect_ratio": aspect_ratio},
    })


@bp.post("/media/prompts")
def media_prompt_save():
    data = request.get_json(silent=True) or {}
    s = SessionLocal()
    try:
        p = MediaPrompt(
            idea_ru=(data.get("idea_ru") or "").strip(),
            prompt_en=(data.get("prompt_en") or "").strip(),
            media_type=(data.get("media_type") or "image").strip(),
            style=(data.get("style") or "pixar_3d_brand").strip(),
            aspect_ratio=(data.get("aspect_ratio") or "1:1").strip(),
            best_for=(data.get("best_for") or None),
        )
        if not p.prompt_en:
            return _err("Пустой prompt_en — нечего сохранять.")
        s.add(p)
        s.commit()
        s.refresh(p)
        return jsonify(p.to_dict()), 201
    finally:
        s.close()


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
# VK publishing
# ============================================================

@bp.get("/vk/status")
def vk_status():
    """Сообщает фронту, настроен ли VK (есть ли токен)."""
    vk = VKClient()
    return jsonify({"configured": vk.is_configured(), "group_id": vk.group_id})


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
    except VKAPIError as e:
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
