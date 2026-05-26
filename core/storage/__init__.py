"""Слой хранения данных.

Сейчас:
- `db.py` — SQLAlchemy engine, SessionLocal, инициализация схемы, миграции.
- `models.py` — ORM-модели (Post, Rubric, MediaAsset, MediaPrompt).

Целевое состояние (на v0.4-v0.5): PostgreSQL + Alembic-миграции вместо
текущей самописной `init_db`. Структура пакета упростит этот переход.
"""
