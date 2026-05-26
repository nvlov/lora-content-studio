"""SQLAlchemy engine, sessionmaker и инициализация БД (включая миграции v0.2)."""
import logging
import shutil
from pathlib import Path

from sqlalchemy import create_engine, text

from sqlalchemy.orm import sessionmaker, scoped_session

import config
from core.storage.models import Base, Rubric, Post
from core.generators.prompts import STARTER_RUBRICS, NEW_RUBRICS_V0_2

log = logging.getLogger(__name__)

# echo=False — SQL не спамит в консоль; SQLite + check_same_thread=False для Flask
engine = create_engine(
    config.DB_URL,
    echo=False,
    future=True,
    connect_args={"check_same_thread": False},
)

SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True))


# ============================================================
# Миграции v0.2 (идемпотентно — безопасно вызывать многократно)
# ============================================================

# Колонки, которые надо добавить в Post по сравнению с v0.1.
# (имя, SQL-определение). NOT NULL только если есть DEFAULT.
_POST_COLUMNS_V0_2 = [
    ("video_path", "VARCHAR(500)"),
    ("media_kind", "VARCHAR(16) NOT NULL DEFAULT 'none'"),
    ("scheduled_at", "DATETIME"),
    ("published_at", "DATETIME"),
    ("vk_post_id", "VARCHAR(64)"),
    ("vk_post_url", "VARCHAR(500)"),
    ("last_publish_error", "TEXT"),
    ("deleted_at", "DATETIME"),
    ("parent_post_id", "INTEGER"),
]


def _existing_columns(conn, table: str) -> set[str]:
    """Возвращает множество имён колонок таблицы (через PRAGMA)."""
    rows = conn.execute(text(f"PRAGMA table_info({table})")).all()
    return {r[1] for r in rows}


def migrate_to_v0_2() -> None:
    """ALTER TABLE для добавления новых колонок Post. Идемпотентно."""
    with engine.begin() as conn:
        # Проверяем, что таблица posts существует (если нет — это первый запуск,
        # create_all уже создаст её со всеми колонками).
        present = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='posts'")
        ).first()
        if not present:
            return

        existing = _existing_columns(conn, "posts")
        added = []
        for col_name, col_def in _POST_COLUMNS_V0_2:
            if col_name not in existing:
                conn.execute(text(f"ALTER TABLE posts ADD COLUMN {col_name} {col_def}"))
                added.append(col_name)

        # Для существующих записей v0.1: проставим media_kind на основе image_path
        if "media_kind" in added:
            conn.execute(text(
                "UPDATE posts SET media_kind = CASE "
                "WHEN image_path IS NOT NULL AND image_path != '' THEN 'image' "
                "ELSE 'none' END WHERE media_kind IS NULL OR media_kind = 'none'"
            ))

        # Для existing — поправим тип topic (varchar→text) — SQLite не строгий, но безопасно
        if added:
            log.info("v0.2 миграция БД: добавлены колонки %s", added)


# Колонки v0.3.2 — связь медиа↔промпт + оценка, Kling-специфичные поля промпта.
_MEDIA_ASSET_COLUMNS_V0_3_2 = [
    ("source_prompt_id", "INTEGER"),
    ("rating", "INTEGER"),
    ("feedback_notes", "TEXT"),
]
_MEDIA_PROMPT_COLUMNS_V0_3_2 = [
    ("negative_prompt_en", "TEXT"),
    ("duration", "INTEGER"),
    ("camera_movement", "VARCHAR(32)"),
    ("video_mode", "VARCHAR(16)"),
    ("dialog_en", "TEXT"),
    ("voice_tone", "VARCHAR(64)"),
]


def migrate_to_v0_3_2() -> None:
    """ALTER TABLE для v0.3.2: новые поля в media_assets и media_prompts. Идемпотентно."""
    with engine.begin() as conn:
        # media_assets — добавляем только если таблица существует (create_all создаст её
        # со всеми колонками при первом запуске).
        ma_present = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='media_assets'")
        ).first()
        if ma_present:
            existing = _existing_columns(conn, "media_assets")
            added_ma = []
            for col_name, col_def in _MEDIA_ASSET_COLUMNS_V0_3_2:
                if col_name not in existing:
                    conn.execute(text(f"ALTER TABLE media_assets ADD COLUMN {col_name} {col_def}"))
                    added_ma.append(col_name)
            if added_ma:
                log.info("v0.3.2 миграция media_assets: добавлены колонки %s", added_ma)

        mp_present = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='media_prompts'")
        ).first()
        if mp_present:
            existing = _existing_columns(conn, "media_prompts")
            added_mp = []
            for col_name, col_def in _MEDIA_PROMPT_COLUMNS_V0_3_2:
                if col_name not in existing:
                    conn.execute(text(f"ALTER TABLE media_prompts ADD COLUMN {col_name} {col_def}"))
                    added_mp.append(col_name)
            if added_mp:
                log.info("v0.3.2 миграция media_prompts: добавлены колонки %s", added_mp)


_POST_COLUMNS_V0_4 = [
    ("target_platforms", "TEXT NOT NULL DEFAULT '[\"vk\"]'"),
]


def migrate_to_v0_4() -> None:
    """ALTER TABLE для v0.4: Post.target_platforms. Идемпотентно."""
    with engine.begin() as conn:
        present = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='posts'")
        ).first()
        if not present:
            return
        existing = _existing_columns(conn, "posts")
        added = []
        for col_name, col_def in _POST_COLUMNS_V0_4:
            if col_name not in existing:
                conn.execute(text(f"ALTER TABLE posts ADD COLUMN {col_name} {col_def}"))
                added.append(col_name)
        if added:
            log.info("v0.4 миграция БД: добавлены колонки %s", added)


def migrate_rating_scale_to_signed() -> None:
    """Переводит rating с шкалы 1..5 на -2..+2 сдвигом на -3. Идемпотентно:
    запускается только если в данных есть значения > 2 (признак старой шкалы)."""
    with engine.begin() as conn:
        ma_present = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='media_assets'")
        ).first()
        if not ma_present:
            return
        existing = _existing_columns(conn, "media_assets")
        if "rating" not in existing:
            return
        max_rating = conn.execute(
            text("SELECT MAX(rating) FROM media_assets WHERE rating IS NOT NULL")
        ).scalar()
        if max_rating is None or max_rating <= 2:
            return
        result = conn.execute(
            text("UPDATE media_assets SET rating = rating - 3 WHERE rating IS NOT NULL")
        )
        log.info("Миграция шкалы оценок 1..5 → -2..+2: обновлено %s строк", result.rowcount)


def migrate_uploads_v0_2() -> None:
    """Переносит файлы из static/uploads/*.{jpg,png,webp} в static/uploads/images/.
    Обновляет Post.image_path. Идемпотентно — если файл уже в images/, ничего не делает."""
    src_dir: Path = config.UPLOADS_DIR
    dst_dir: Path = config.IMAGES_DIR
    dst_dir.mkdir(parents=True, exist_ok=True)

    moved = []
    for ext in ("jpg", "jpeg", "png", "webp"):
        for p in src_dir.glob(f"*.{ext}"):
            # Не трогаем поддиректории (images/, videos/)
            if p.is_dir():
                continue
            target = dst_dir / p.name
            if target.exists():
                # Уже на месте — просто удалим дубликат в корне uploads
                try:
                    p.unlink()
                except OSError:
                    pass
                continue
            try:
                shutil.move(str(p), str(target))
                moved.append(p.name)
            except OSError as e:
                log.warning("Не удалось перенести %s: %s", p.name, e)

    if moved:
        log.info("v0.2 миграция файлов: перенесено %s изображений в images/", len(moved))

    # Обновим image_path в БД: если image_path не содержит '/', добавим 'images/' впереди
    s = SessionLocal()
    try:
        posts = s.query(Post).filter(Post.image_path.isnot(None)).all()
        updated = 0
        for p in posts:
            ip = (p.image_path or "").strip()
            if not ip or "/" in ip or "\\" in ip:
                continue
            p.image_path = f"images/{ip}"
            updated += 1
        if updated:
            s.commit()
            log.info("v0.2 миграция БД: обновлено %s путей image_path", updated)
    finally:
        s.close()


def seed_new_rubrics_v0_2() -> None:
    """Добавляет 4 новые рубрики v0.2, если их ещё нет. Не перезаписывает существующие."""
    s = SessionLocal()
    try:
        existing = {r.key for r in s.query(Rubric).all()}
        added = 0
        for r in NEW_RUBRICS_V0_2:
            if r["key"] not in existing:
                s.add(Rubric(**r))
                added += 1
        if added:
            s.commit()
            log.info("v0.2 засеяно новых рубрик: %s", added)
    finally:
        s.close()


# ============================================================
# Инициализация БД
# ============================================================

def init_db() -> None:
    """Создаёт таблицы, мигрирует схему, засеивает рубрики и переносит файлы."""
    # 1) ALTER старых таблиц — ДО create_all, чтобы create_all не пытался переопределять
    migrate_to_v0_2()
    migrate_to_v0_3_2()
    migrate_to_v0_4()
    migrate_rating_scale_to_signed()

    # 2) Создание новых таблиц (media_assets, media_prompts) и недостающих
    Base.metadata.create_all(bind=engine)

    # 3) Стартовый засев v0.1
    s = SessionLocal()
    try:
        existing = {r.key for r in s.query(Rubric).all()}
        added = 0
        for r in STARTER_RUBRICS:
            if r["key"] not in existing:
                s.add(Rubric(**r))
                added += 1
        if added:
            s.commit()
            log.info("Засеяно стартовых рубрик: %s", added)
    finally:
        s.close()

    # 4) Засев новых рубрик v0.2
    seed_new_rubrics_v0_2()

    # 5) Перенос файлов из uploads/ в uploads/images/
    migrate_uploads_v0_2()
