"""SQLAlchemy engine, sessionmaker и инициализация БД."""
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

import config
from core.models import Base, Rubric
from core.prompts import STARTER_RUBRICS

log = logging.getLogger(__name__)

# echo=False — SQL не спамит в консоль; SQLite + check_same_thread=False для Flask
engine = create_engine(
    config.DB_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
)

SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True))


def init_db() -> None:
    """Создаёт таблицы и засеивает стартовые рубрики при первом запуске."""
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        existing = {r.key for r in session.query(Rubric).all()}
        added = 0
        for r in STARTER_RUBRICS:
            if r["key"] not in existing:
                session.add(Rubric(**r))
                added += 1
        if added:
            session.commit()
            log.info("Засеяно стартовых рубрик: %s", added)
    finally:
        session.close()
