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


def cmd_show_rubric(args) -> int:
    """Печатает поля рубрики (для использования из Skill lora-post-builder)."""
    init_db()
    s = SessionLocal()
    try:
        r = s.get(Rubric, args.key)
        if not r:
            print(f"Рубрика {args.key!r} не найдена.", file=sys.stderr)
            print("Доступные:", file=sys.stderr)
            for row in s.query(Rubric).all():
                print(f"  - {row.key}: {row.name}", file=sys.stderr)
            return 1
        print(f"=== Рубрика {r.key} ({r.name}) ===")
        print(f"Emoji-якорь: {r.emoji}")
        print()
        print("--- system_prompt ---")
        print(r.system_prompt)
        print()
        print("--- image_prompt_template ---")
        print(r.image_prompt_template)
    finally:
        s.close()
    return 0


def _slug_from_json_topic(topic: str, max_len: int = 30) -> str:
    """Простой slug из топика — для логирования. Не используется в имени поста."""
    s = (topic or "").lower().strip()
    out = []
    for ch in s:
        if ch.isalnum() or ch in "-_":
            out.append(ch)
        elif ch.isspace():
            out.append("-")
    slug = "".join(out)[:max_len].strip("-")
    return slug or "post"


def cmd_import_from_json(args) -> int:
    """Импортирует JSON-черновик от Skill lora-post-builder в БД.

    По умолчанию генерирует картинку через gpt-image-2 /v1/images/edits
    с референсом эмоции Лоры. Флаг --no-image отключает генерацию.
    """
    import json as _json
    from core.generators.lora_references import get_reference_path

    init_db()

    json_path = Path(args.file).resolve()
    if not json_path.exists():
        print(f"Файл не найден: {json_path}", file=sys.stderr)
        return 1
    try:
        with json_path.open("r", encoding="utf-8") as f:
            payload = _json.load(f)
    except _json.JSONDecodeError as e:
        print(f"Невалидный JSON: {e}", file=sys.stderr)
        return 1

    # Минимальная валидация. Полная — через ajv / jsonschema по data/inbox/text/_schema.json.
    required = ("rubric_key", "topic", "emotion", "platforms", "image_prompt")
    missing = [k for k in required if k not in payload]
    if missing:
        print(f"В JSON нет обязательных полей: {missing}", file=sys.stderr)
        return 1
    if "vk" not in payload["platforms"] or "content" not in payload["platforms"]["vk"]:
        print("В JSON отсутствует platforms.vk.content", file=sys.stderr)
        return 1

    rubric_key = payload["rubric_key"]
    topic = payload.get("topic", "") or ""
    emotion = payload["emotion"]
    vk_text = payload["platforms"]["vk"]["content"]
    image_prompt = payload["image_prompt"]

    # target_platforms: vk всегда; telegram если есть секция
    targets = ["vk"]
    if "telegram" in payload["platforms"] and payload["platforms"]["telegram"].get("content"):
        targets.append("telegram")

    s = SessionLocal()
    try:
        rubric = s.get(Rubric, rubric_key)
        if not rubric:
            print(f"Рубрика {rubric_key!r} не найдена в БД. Используй manage.py status или show-rubric.", file=sys.stderr)
            return 1

        post = Post(
            rubric_key=rubric_key,
            topic=topic or None,
            text_content=vk_text,
            status="draft",
            image_prompt=image_prompt,
            image_source="external_ai",
            target_platforms=_json.dumps(targets),
        )
        s.add(post)
        s.commit()
        s.refresh(post)
        post_id = post.id
        print(f"Создан пост id={post_id} (rubric={rubric_key}, status=draft, targets={targets}).")
        print(f"VK preview: {_truncate(vk_text, 200)}")
        if "telegram" in targets:
            tg_text = payload["platforms"]["telegram"]["content"]
            print(f"TG preview: {_truncate(tg_text, 200)}")

        if args.no_image:
            print("Картинка не генерируется (флаг --no-image).")
            return 0

        # Генерация картинки через gpt-image-2 /edits с референсом эмоции
        from core.generators.image_clients import OpenAIImageProvider, ImageError
        from core.storage.models import MediaAsset

        ref_path = get_reference_path(emotion=emotion)
        if ref_path is None:
            print(f"Внимание: референс эмоции {emotion!r} не найден на диске. Генерация будет без референса.")
            references = []
        else:
            references = [ref_path]
            print(f"Использую референс эмоции: {emotion} ({ref_path.name})")

        print(f"Запрашиваю gpt-image-2 (это может занять 1-3 минуты)...")
        provider = OpenAIImageProvider()
        try:
            if references:
                result = provider.generate_with_reference(
                    prompt=image_prompt,
                    reference_paths=references,
                    size="1024x1024",
                    quality=args.quality,
                )
            else:
                result = provider.generate(
                    prompt=image_prompt,
                    size="1024x1024",
                    quality=args.quality,
                )
        except ImageError as e:
            print(f"Ошибка генерации картинки: {e}", file=sys.stderr)
            print(f"Пост создан без картинки (id={post_id}). Можно повторить генерацию позже через UI.", file=sys.stderr)
            return 0  # пост уже создан, не считаем фатальной ошибкой

        # Привязка к посту + запись в media_assets
        post.image_path = result["file_path"]
        media = MediaAsset(
            kind="image",
            file_path=result["file_path"],
            original_name=Path(result["file_path"]).name,
            mime_type=result["mime_type"],
            size_bytes=result["size_bytes"],
            width=result.get("width"),
            height=result.get("height"),
            source="external_ai",
            prompt_used=image_prompt,
        )
        s.add(media)
        s.commit()
        print(f"Картинка готова: static/uploads/{result['file_path']}  ({result['size_bytes']/1024:.0f} КБ)")
    finally:
        s.close()

    print(f"\nГотово. Открой пост в UI: http://127.0.0.1:5000  или CLI: manage.py show-post {post_id}")
    return 0


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

    sr = sub.add_parser("show-rubric", help="Показать system_prompt и image_template рубрики (для Skill)")
    sr.add_argument("key", help="Ключ рубрики: word_of_day, common_mistake, и т. д.")

    ij = sub.add_parser("import-from-json",
                        help="Импортировать JSON-черновик от Skill lora-post-builder в БД")
    ij.add_argument("file", help="Путь к JSON-файлу (data/inbox/text/...)")
    ij.add_argument("--no-image", action="store_true",
                    help="Не генерировать картинку через gpt-image-2 (только текст)")
    ij.add_argument("--quality", default="high", choices=["low", "medium", "high", "auto"],
                    help="Качество gpt-image-2 (default: high). low = быстро для теста, high = production")

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
        "show-rubric": cmd_show_rubric,
        "import-from-json": cmd_import_from_json,
    }
    return handlers[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
