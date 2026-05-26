"""CLI для lora-content-studio.

Параллельный интерфейс к Flask UI: позволяет работать с проектом через терминал.
Используется когда генерация ведётся в Claude Code-сессии и нужно быстро
дёрнуть БД / запустить публикатор без открытия localhost:5000.

Примеры:
    python manage.py status
    python manage.py list-posts --status draft --limit 20
    python manage.py show-post 42
    python manage.py generate-post word_of_day
    python manage.py generate-post free_topic --topic "идиома piece of cake — откуда пошла"
    python manage.py publish 42                       # дефолтная платформа: vk
    python manage.py publish 42 --platform telegram
    python manage.py publish 42 --platform all        # все настроенные публикаторы
    python manage.py schedule 42 2026-05-27T10:00:00

Установка не нужна — запуск из корня проекта в venv:
    venv\\Scripts\\python manage.py <команда>
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

# Windows-консоль по умолчанию cp1251 — кириллица в UTF-8 строках выводится мусором.
# Переключаем stdout/stderr на UTF-8 чтобы любые сообщения читались.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

# Корень проекта в sys.path — чтобы работали "import config" и "from core.*".
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from core.storage.db import SessionLocal, init_db  # noqa: E402
from core.storage.models import Post, Rubric  # noqa: E402
from core.publishers import get_publisher, available_publishers, PublishError  # noqa: E402


# ----------------------------------------------------------------------------
# Утилиты вывода
# ----------------------------------------------------------------------------

def _truncate(s: str, n: int) -> str:
    if not s:
        return ""
    s = s.replace("\n", " ").replace("\r", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def _print_table(rows: list[dict], columns: list[tuple[str, int]]) -> None:
    """Простая табличная печать без зависимостей.
    columns: [(key, width), ...]
    """
    header = " ".join(f"{k:<{w}}" for k, w in columns)
    print(header)
    print("-" * len(header))
    for r in rows:
        line = " ".join(f"{_truncate(str(r.get(k, '')), w):<{w}}" for k, w in columns)
        print(line)


# ----------------------------------------------------------------------------
# Команды
# ----------------------------------------------------------------------------

def cmd_status(args) -> int:
    """Сводка состояния системы."""
    init_db()
    pubs = available_publishers()
    s = SessionLocal()
    try:
        count_total = s.query(Post).filter(Post.deleted_at.is_(None)).count()
        count_draft = s.query(Post).filter(Post.deleted_at.is_(None), Post.status == "draft").count()
        count_scheduled = s.query(Post).filter(Post.deleted_at.is_(None), Post.status == "scheduled").count()
        count_published = s.query(Post).filter(Post.deleted_at.is_(None), Post.status == "published").count()
    finally:
        s.close()

    db_size_kb = config.DB_PATH.stat().st_size / 1024 if config.DB_PATH.exists() else 0
    print("=== Lora Content Studio — статус ===")
    print(f"DB:       {config.DB_PATH}  ({db_size_kb:.1f} КБ)")
    print(f"Постов:   total={count_total}  draft={count_draft}  scheduled={count_scheduled}  published={count_published}")
    print()
    print("Публикаторы:")
    for p in pubs:
        flag_impl = "OK" if p["implemented"] else "placeholder"
        flag_conf = "configured" if p["configured"] else "not configured"
        print(f"  {p['name']:<10} {flag_impl:<12} {flag_conf}")
    return 0


def cmd_list_posts(args) -> int:
    """Список постов с фильтром по статусу."""
    init_db()
    s = SessionLocal()
    try:
        q = s.query(Post).filter(Post.deleted_at.is_(None))
        if args.status:
            q = q.filter(Post.status == args.status)
        q = q.order_by(Post.created_at.desc()).limit(args.limit)
        rows = [
            {
                "id": p.id,
                "rubric": p.rubric_key,
                "status": p.status,
                "created": p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "",
                "text": p.text_content,
            }
            for p in q.all()
        ]
    finally:
        s.close()
    if not rows:
        print("Нет постов под фильтр.")
        return 0
    _print_table(rows, [("id", 6), ("rubric", 20), ("status", 14), ("created", 17), ("text", 60)])
    return 0


def cmd_show_post(args) -> int:
    """Подробности одного поста."""
    init_db()
    s = SessionLocal()
    try:
        p = s.get(Post, args.id)
        if not p or p.deleted_at is not None:
            print(f"Пост {args.id} не найден.", file=sys.stderr)
            return 1
        d = p.to_dict()
    finally:
        s.close()
    for k, v in d.items():
        if k == "text_content":
            print(f"--- text_content ---")
            print(v)
            print(f"--- end ---")
        else:
            print(f"{k}: {v}")
    return 0


def cmd_generate_post(args) -> int:
    """Генерирует пост через Claude и сохраняет как draft."""
    from core.generators.llm_client import ClaudeClient, LLMError

    init_db()
    s = SessionLocal()
    try:
        rubric = s.get(Rubric, args.rubric)
        if not rubric:
            print(f"Рубрика {args.rubric!r} не найдена. Доступные:", file=sys.stderr)
            for r in s.query(Rubric).all():
                print(f"  - {r.key}: {r.name}", file=sys.stderr)
            return 1

        topic = args.topic or ""
        user_message = (
            f"Тема: {topic}\n\nСгенерируй пост по этой рубрике."
            if topic
            else "Сгенерируй пост по этой рубрике."
        )

        print(f"Генерирую через Claude (модель {config.LLM_MODEL})...")
        client = ClaudeClient()
        try:
            result = client.generate(
                system_prompt=rubric.system_prompt,
                user_message=user_message,
                max_tokens=config.LLM_MAX_TOKENS,
            )
        except LLMError as e:
            print(f"Ошибка LLM: {e}", file=sys.stderr)
            return 1

        post = Post(
            rubric_key=args.rubric,
            topic=topic or None,
            text_content=result["text"],
            status="draft",
        )
        s.add(post)
        s.commit()
        s.refresh(post)
        post_id = post.id
        text_preview = _truncate(result["text"], 200)
        tokens_in = result.get("tokens_in")
        tokens_out = result.get("tokens_out")
    finally:
        s.close()

    print(f"Создан пост id={post_id} (status=draft).")
    print(f"Токены: in={tokens_in} out={tokens_out}")
    print(f"Превью: {text_preview}")
    print(f"Полностью: python manage.py show-post {post_id}")
    return 0


def cmd_publish(args) -> int:
    """Публикует пост в одной или нескольких платформах."""
    init_db()
    if args.platform == "all":
        platforms = ["vk", "telegram"]
    else:
        platforms = [args.platform]

    s = SessionLocal()
    try:
        p = s.get(Post, args.id)
        if not p or p.deleted_at is not None:
            print(f"Пост {args.id} не найден.", file=sys.stderr)
            return 1
        if not (p.text_content or "").strip():
            print("Текст поста пуст.", file=sys.stderr)
            return 1
        text = p.text_content

        results = []
        had_failure = False
        for platform in platforms:
            try:
                pub = get_publisher(platform)
            except PublishError as e:
                print(f"[{platform}] Пропускаю: {e}", file=sys.stderr)
                had_failure = True
                continue
            if not pub.is_configured():
                print(f"[{platform}] Не сконфигурирован — пропускаю.")
                continue
            try:
                result = pub.publish_text(text)
                results.append(result)
                print(f"[{platform}] OK: {result['post_url']}")
            except PublishError as e:
                print(f"[{platform}] Ошибка: {e}", file=sys.stderr)
                had_failure = True

        # Для VK обновляем поля поста (исторически в БД есть vk_post_id / vk_post_url)
        for r in results:
            if r["platform"] == "vk":
                p.vk_post_id = r["post_id"]
                p.vk_post_url = r["post_url"]
                p.status = "published"
                p.published_at = datetime.utcnow()
                p.last_publish_error = None
        if had_failure and not results:
            p.status = "publish_failed"
            p.last_publish_error = "Все публикаторы упали или не настроены"
        s.commit()
    finally:
        s.close()

    return 1 if had_failure and not results else 0


def cmd_schedule(args) -> int:
    """Планирует публикацию поста на ISO-8601 время (UTC если без TZ)."""
    from core.scheduler import schedule_post as _sched, init_scheduler

    init_db()
    init_scheduler()
    s = SessionLocal()
    try:
        p = s.get(Post, args.id)
        if not p or p.deleted_at is not None:
            print(f"Пост {args.id} не найден.", file=sys.stderr)
            return 1
        try:
            run_at = datetime.fromisoformat(args.when)
        except ValueError as e:
            print(f"Неверный формат времени: {e}. Пример: 2026-05-27T10:00:00", file=sys.stderr)
            return 1
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=timezone.utc)
        run_at_utc = run_at.astimezone(timezone.utc).replace(tzinfo=None)
        p.scheduled_at = run_at_utc
        p.status = "scheduled"
        s.commit()
        _sched(args.id, run_at_utc.replace(tzinfo=timezone.utc))
        print(f"Запланировано: post_id={args.id} на {run_at_utc.isoformat()} UTC")
    finally:
        s.close()
    return 0


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="CLI для lora-content-studio.")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="Сводка состояния")

    lp = sub.add_parser("list-posts", help="Список постов")
    lp.add_argument("--status", choices=["draft", "scheduled", "published", "publish_failed"])
    lp.add_argument("--limit", type=int, default=30)

    sp = sub.add_parser("show-post", help="Детали одного поста")
    sp.add_argument("id", type=int)

    gp = sub.add_parser("generate-post", help="Сгенерировать пост через Claude (draft)")
    gp.add_argument("rubric", help="Ключ рубрики, см. status")
    gp.add_argument("--topic", help="Опциональная тема (для free_topic)")

    pb = sub.add_parser("publish", help="Опубликовать пост")
    pb.add_argument("id", type=int)
    pb.add_argument("--platform", default="vk", choices=["vk", "telegram", "all"])

    sc = sub.add_parser("schedule", help="Запланировать публикацию")
    sc.add_argument("id", type=int)
    sc.add_argument("when", help="ISO-8601, например 2026-05-27T10:00:00")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "status": cmd_status,
        "list-posts": cmd_list_posts,
        "show-post": cmd_show_post,
        "generate-post": cmd_generate_post,
        "publish": cmd_publish,
        "schedule": cmd_schedule,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
