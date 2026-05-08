"""JSON API: рубрики, генерация текста/картинки, CRUD постов, настройки рубрик."""
import logging
from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy import or_

import config
from core.db import SessionLocal
from core.models import Post, Rubric
from core.llm_client import ClaudeClient, LLMError
from core.image_clients import KlingImageProvider, ManualUploadHandler, ImageError

log = logging.getLogger(__name__)
bp = Blueprint("api", __name__, url_prefix="/api")


# ---------- helpers ----------

def _err(message: str, status: int = 400):
    return jsonify({"error": message}), status


# ---------- rubrics (read-only list) ----------

@bp.get("/rubrics")
def list_rubrics():
    s = SessionLocal()
    try:
        items = s.query(Rubric).order_by(Rubric.name).all()
        return jsonify([{"key": r.key, "name": r.name, "emoji": r.emoji} for r in items])
    finally:
        s.close()


# ---------- text generation ----------

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


# ---------- image generation (Kling) ----------

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


# ---------- manual upload ----------

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


# ---------- posts CRUD ----------

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
        q = s.query(Post)
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
        if not p:
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
        if not p:
            return _err("Пост не найден.", 404)
        for field in (
            "rubric_key", "topic", "text_content",
            "image_path", "image_prompt", "image_source", "status",
        ):
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
    s = SessionLocal()
    try:
        p = s.get(Post, post_id)
        if not p:
            return _err("Пост не найден.", 404)
        s.delete(p)
        s.commit()
        return jsonify({"deleted": True})
    finally:
        s.close()


# ---------- settings: rubrics edit ----------

@bp.get("/settings/rubrics")
def list_rubrics_full():
    s = SessionLocal()
    try:
        items = s.query(Rubric).order_by(Rubric.name).all()
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
