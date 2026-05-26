"""SQLAlchemy ORM-модели."""
import json
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Post(Base):
    """Пост для VK — черновик / запланированный / опубликованный."""
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True)
    rubric_key = Column(String(64), nullable=False, index=True)
    topic = Column(Text, nullable=True)  # для free_topic — большое описание задачи
    text_content = Column(Text, nullable=False, default="")
    image_path = Column(String(500), nullable=True)         # относительно static/uploads/
    image_prompt = Column(Text, nullable=True)
    image_source = Column(String(32), nullable=False, default="none")  # kling | manual_upload | external_ai | none

    # v0.2: видео
    video_path = Column(String(500), nullable=True)         # относительно static/uploads/
    media_kind = Column(String(16), nullable=False, default="none")  # none | image | video

    # draft | scheduled | published | publish_failed
    status = Column(String(32), nullable=False, default="draft")

    # v0.2: расписание / публикация
    scheduled_at = Column(DateTime, nullable=True)          # UTC
    published_at = Column(DateTime, nullable=True)          # UTC
    vk_post_id = Column(String(64), nullable=True)
    vk_post_url = Column(String(500), nullable=True)
    last_publish_error = Column(Text, nullable=True)

    # v0.2: soft-delete и связь с предком
    deleted_at = Column(DateTime, nullable=True)
    parent_post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)

    # v0.4: список целевых платформ для публикации (JSON-array строк).
    # Дефолт '["vk"]' сохраняет старое поведение для постов без явного выбора.
    target_platforms = Column(Text, nullable=False, default='["vk"]')

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_target_platforms(self) -> list[str]:
        """Парсит JSON-список платформ. Падает мягко на дефолт ['vk']."""
        try:
            parsed = json.loads(self.target_platforms or '["vk"]')
            if isinstance(parsed, list) and parsed:
                return [str(p) for p in parsed]
        except (json.JSONDecodeError, TypeError):
            pass
        return ["vk"]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rubric_key": self.rubric_key,
            "topic": self.topic,
            "text_content": self.text_content,
            "image_path": self.image_path,
            "image_prompt": self.image_prompt,
            "image_source": self.image_source,
            "video_path": self.video_path,
            "media_kind": self.media_kind,
            "status": self.status,
            "scheduled_at": self.scheduled_at.isoformat() + "Z" if self.scheduled_at else None,
            "published_at": self.published_at.isoformat() + "Z" if self.published_at else None,
            "vk_post_id": self.vk_post_id,
            "vk_post_url": self.vk_post_url,
            "last_publish_error": self.last_publish_error,
            "target_platforms": self.get_target_platforms(),
            "parent_post_id": self.parent_post_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Rubric(Base):
    """Рубрика — задаёт системный промпт для LLM и шаблон промпта картинки."""
    __tablename__ = "rubrics"

    key = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    emoji = Column(String(16), nullable=False, default="")
    system_prompt = Column(Text, nullable=False)
    image_prompt_template = Column(Text, nullable=False, default="")

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "emoji": self.emoji,
            "system_prompt": self.system_prompt,
            "image_prompt_template": self.image_prompt_template,
        }


class GenerationLog(Base):
    """Лог-запись о вызове внешнего AI-сервиса (Claude / Kling / VK)."""
    __tablename__ = "generation_logs"

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    provider = Column(String(32), nullable=False)          # claude | kling | vk | manual_upload
    request_type = Column(String(32), nullable=False)      # text | image | video | wall_post | upload_photo | upload_video
    tokens_in = Column(Integer, nullable=True)
    tokens_out = Column(Integer, nullable=True)
    cost_estimate_rub = Column(Float, nullable=True)
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class MediaAsset(Base):
    """Файл в медиа-библиотеке: изображение или видео."""
    __tablename__ = "media_assets"

    id = Column(Integer, primary_key=True)
    kind = Column(String(16), nullable=False)              # image | video
    file_path = Column(String(500), nullable=False)        # относительно static/uploads/
    original_name = Column(String(500), nullable=False, default="")
    mime_type = Column(String(64), nullable=False, default="")
    size_bytes = Column(Integer, nullable=False, default=0)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    source = Column(String(32), nullable=False, default="manual_upload")  # manual_upload | kling | external_ai
    prompt_used = Column(Text, nullable=True)
    # v0.3.2: связь с промптом + оценка
    source_prompt_id = Column(Integer, ForeignKey("media_prompts.id"), nullable=True)
    rating = Column(Integer, nullable=True)                # -2..+2, NULL = не оценено
    feedback_notes = Column(Text, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "file_path": self.file_path,
            "original_name": self.original_name,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "width": self.width,
            "height": self.height,
            "duration_seconds": self.duration_seconds,
            "source": self.source,
            "prompt_used": self.prompt_used,
            "source_prompt_id": self.source_prompt_id,
            "rating": self.rating,
            "feedback_notes": self.feedback_notes,
            "url": f"/static/uploads/{self.file_path}",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class PostPublication(Base):
    """v0.4: запись об одной публикации поста в одной платформе.

    Один Post может иметь несколько PostPublication (по одной на платформу).
    Legacy-поля Post.vk_post_id/vk_post_url дублируют запись для VK ради
    backward-compat с существующим UI — со временем можно мигрировать
    UI на эту таблицу и убрать legacy.
    """
    __tablename__ = "post_publications"

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    platform = Column(String(32), nullable=False)             # vk | telegram | youtube | tiktok
    post_id_at_platform = Column(String(64), nullable=True)   # id поста в платформе (если успех)
    post_url = Column(String(500), nullable=True)             # прямая ссылка (если успех)
    success = Column(Boolean, nullable=False, default=False)
    error_message = Column(Text, nullable=True)               # если упал — что сказал API
    published_at = Column(DateTime, nullable=True)            # UTC, заполняется при успехе
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "post_id": self.post_id,
            "platform": self.platform,
            "post_id_at_platform": self.post_id_at_platform,
            "post_url": self.post_url,
            "success": self.success,
            "error_message": self.error_message,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MediaPrompt(Base):
    """Сохранённый промпт для генерации картинок/видео через Kling (внешний workflow)."""
    __tablename__ = "media_prompts"

    id = Column(Integer, primary_key=True)
    idea_ru = Column(Text, nullable=False)
    prompt_en = Column(Text, nullable=False)
    media_type = Column(String(16), nullable=False)        # image | video
    style = Column(String(64), nullable=False, default="pixar_3d_brand")
    aspect_ratio = Column(String(16), nullable=False, default="1:1")
    # v0.3.2 — Kling-специфичные поля
    negative_prompt_en = Column(Text, nullable=True)
    duration = Column(Integer, nullable=True)              # 5 или 10, только для video
    camera_movement = Column(String(32), nullable=True)
    video_mode = Column(String(16), nullable=True)         # silent | audio_en, только для video
    dialog_en = Column(Text, nullable=True)                # для audio_en
    voice_tone = Column(String(64), nullable=True)         # для audio_en
    # legacy v0.2 — оставлен для backward-compat
    best_for = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "idea_ru": self.idea_ru,
            "prompt_en": self.prompt_en,
            "negative_prompt_en": self.negative_prompt_en,
            "media_type": self.media_type,
            "style": self.style,
            "aspect_ratio": self.aspect_ratio,
            "duration": self.duration,
            "camera_movement": self.camera_movement,
            "video_mode": self.video_mode,
            "dialog_en": self.dialog_en,
            "voice_tone": self.voice_tone,
            "best_for": self.best_for,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
