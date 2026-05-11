"""APScheduler — фоновая публикация постов в ВК по расписанию.

При старте приложения:
- восстанавливает все задачи со status='scheduled' и scheduled_at > now
- немедленно публикует пропущенные (scheduled_at <= now)
"""
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

import config
from core.db import SessionLocal, engine
from core.models import Post
from core.vk_client import VKClient, VKAPIError
from core.logging_utils import log_ai_call

log = logging.getLogger(__name__)


_scheduler: Optional[BackgroundScheduler] = None


def get_scheduler() -> BackgroundScheduler:
    """Singleton-getter планировщика."""
    global _scheduler
    if _scheduler is None:
        # Используем тот же SQLite-файл, отдельная таблица apscheduler_jobs
        jobstore = SQLAlchemyJobStore(engine=engine, tablename="apscheduler_jobs")
        _scheduler = BackgroundScheduler(
            jobstores={"default": jobstore},
            timezone="UTC",
        )
    return _scheduler


def _job_id(post_id: int) -> str:
    return f"publish_post_{post_id}"


def schedule_post(post_id: int, run_at_utc: datetime) -> None:
    """Регистрирует задачу публикации поста. Если задача уже есть — заменяет."""
    sched = get_scheduler()
    job_id = _job_id(post_id)
    try:
        sched.remove_job(job_id)
    except Exception:
        pass
    sched.add_job(
        publish_scheduled_post,
        trigger="date",
        run_date=run_at_utc,
        args=[post_id],
        id=job_id,
        replace_existing=True,
        misfire_grace_time=3600,  # допускаем выполнение в течение часа после misfire
    )
    log.info("Запланирована публикация post_id=%s на %s UTC", post_id, run_at_utc.isoformat())


def cancel_scheduled_post(post_id: int) -> None:
    sched = get_scheduler()
    try:
        sched.remove_job(_job_id(post_id))
        log.info("Расписание для post_id=%s отменено", post_id)
    except Exception as e:
        log.info("Задача для post_id=%s не найдена: %s", post_id, e)


def publish_scheduled_post(post_id: int) -> None:
    """Исполнитель — вызывается APScheduler в назначенное время."""
    log.info("Триггер публикации post_id=%s", post_id)
    s = SessionLocal()
    try:
        p = s.get(Post, post_id)
        if not p:
            log.warning("post_id=%s не найден — задачу пропускаем", post_id)
            return
        if p.deleted_at is not None:
            log.warning("post_id=%s удалён — публикация отменена", post_id)
            return
        if p.status != "scheduled":
            log.warning("post_id=%s статус=%s, ожидался 'scheduled' — пропускаем", post_id, p.status)
            return

        try:
            _do_publish(s, p)
            s.commit()
        except Exception as e:
            log.exception("Ошибка публикации post_id=%s: %s", post_id, e)
            p.status = "publish_failed"
            p.last_publish_error = str(e)[:1000]
            s.commit()
    finally:
        s.close()


def _do_publish(session, post: Post) -> None:
    """Внутренняя логика публикации — общая для 'now' и 'scheduled'.

    С v0.3.0 публикуется только текст. Поля post.media_kind/image_path/video_path
    остались в модели для backward-compat (старые черновики не ломаются) и для
    будущей ручной выгрузки файлов, но в wall.post не передаются.
    """
    vk = VKClient()
    if not vk.is_configured():
        raise VKAPIError("VK не настроен (нет токена/group_id в .env).")

    result = vk.post_to_wall(message=post.text_content)
    post.status = "published"
    post.published_at = datetime.utcnow()
    post.vk_post_id = result["vk_post_id"]
    post.vk_post_url = result["vk_post_url"]
    post.last_publish_error = None


def publish_now(post_id: int) -> dict:
    """Синхронная публикация — вызывается из эндпоинта publish-now."""
    s = SessionLocal()
    try:
        p = s.get(Post, post_id)
        if not p or p.deleted_at is not None:
            raise VKAPIError("Пост не найден.")
        if not (p.text_content or "").strip():
            raise VKAPIError("Текст поста пуст.")
        if len(p.text_content) > config.VK_TEXT_LIMIT:
            raise VKAPIError(f"Текст длиннее {config.VK_TEXT_LIMIT} символов — VK не примет.")
        try:
            _do_publish(s, p)
            s.commit()
            s.refresh(p)
        except Exception as e:
            p.status = "publish_failed"
            p.last_publish_error = str(e)[:1000]
            s.commit()
            raise
        return {"vk_post_url": p.vk_post_url, "vk_post_id": p.vk_post_id}
    finally:
        s.close()


def init_scheduler() -> None:
    """Запускает планировщик и восстанавливает задачи при старте Flask."""
    sched = get_scheduler()
    if not sched.running:
        sched.start(paused=False)
        log.info("APScheduler запущен")

    # Догоняем пропущенные публикации и восстанавливаем будущие
    s = SessionLocal()
    try:
        scheduled = s.query(Post).filter(
            Post.status == "scheduled",
            Post.deleted_at.is_(None),
            Post.scheduled_at.isnot(None),
        ).all()
        now = datetime.utcnow()
        for p in scheduled:
            if p.scheduled_at and p.scheduled_at <= now:
                # Пропущенная — публикуем немедленно (через джобу +5 сек, чтобы Flask успел подняться)
                from datetime import timedelta
                schedule_post(p.id, now + timedelta(seconds=5))
                log.info("Догоняем пропущенную публикацию post_id=%s", p.id)
            else:
                schedule_post(p.id, p.scheduled_at)
    finally:
        s.close()


def shutdown_scheduler() -> None:
    sched = get_scheduler()
    if sched.running:
        sched.shutdown(wait=False)
