"""SQLAlchemy ORM-модели."""
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
    topic = Column(String(500), nullable=True)
    text_content = Column(Text, nullable=False, default="")
    image_path = Column(String(500), nullable=True)         # относительно static/uploads/
    image_prompt = Column(Text, nullable=True)
    image_source = Column(String(32), nullable=False, default="none")  # kling | manual_upload | none
    status = Column(String(32), nullable=False, default="draft")       # draft | scheduled | published
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rubric_key": self.rubric_key,
            "topic": self.topic,
            "text_content": self.text_content,
            "image_path": self.image_path,
            "image_prompt": self.image_prompt,
            "image_source": self.image_source,
            "status": self.status,
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
    """Лог-запись о вызове внешнего AI-сервиса (Claude / Kling)."""
    __tablename__ = "generation_logs"

    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    provider = Column(String(32), nullable=False)          # claude | kling
    request_type = Column(String(32), nullable=False)      # text | image
    tokens_in = Column(Integer, nullable=True)
    tokens_out = Column(Integer, nullable=True)
    cost_estimate_rub = Column(Float, nullable=True)
    success = Column(Boolean, nullable=False, default=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
