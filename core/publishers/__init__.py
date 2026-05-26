"""Публикаторы постов в социальные сети.

Каждый публикатор реализует интерфейс BasePublisher (`base.py`) и регистрируется
в реестре PUBLISHERS. Это даёт scheduler возможность публиковать один пост
в несколько каналов одновременно через Post.target_platforms.

Поддерживаемые платформы:
- vk (`vk.py`) — текстовая публикация в сообщество ВК. Работает.
- telegram (`telegram.py`) — Bot API. Заглушка: модуль готов, ключи в .env
  не заданы, до настройки канала отвечает «не настроено».
- youtube (`youtube.py`) — placeholder, требует OAuth и app-review.
- tiktok (`tiktok.py`) — placeholder, требует Content Posting API access.

Вспомогательный модуль `vk_oauth.py` — спящая ветка для возможного
возвращения media-публикации в VK (см. docs/sessions/2026-05-11).
"""
from core.publishers.base import BasePublisher, PublishResult, PublishError

__all__ = ["BasePublisher", "PublishResult", "PublishError", "get_publisher", "available_publishers"]


def get_publisher(platform: str) -> BasePublisher:
    """Фабрика: возвращает экземпляр публикатора по имени платформы.

    Импорты ленивые — не тащим Telegram/YouTube если нужен только VK.
    """
    platform = platform.lower().strip()
    if platform == "vk":
        from core.publishers.vk import VKPublisher
        return VKPublisher()
    if platform == "telegram":
        from core.publishers.telegram import TelegramPublisher
        return TelegramPublisher()
    if platform == "youtube":
        from core.publishers.youtube import YouTubePublisher
        return YouTubePublisher()
    if platform == "tiktok":
        from core.publishers.tiktok import TikTokPublisher
        return TikTokPublisher()
    raise PublishError(f"Неизвестная платформа: {platform!r}. Доступны: vk, telegram, youtube, tiktok.")


def available_publishers() -> list[dict]:
    """Список платформ и их статус (configured / not configured / not implemented).

    Используется CLI-командой `manage.py status` и для UI-индикаторов.
    """
    out = []
    for name in ("vk", "telegram", "youtube", "tiktok"):
        try:
            pub = get_publisher(name)
            out.append({
                "name": name,
                "configured": pub.is_configured(),
                "implemented": pub.IMPLEMENTED,
            })
        except Exception as e:
            out.append({"name": name, "configured": False, "implemented": False, "error": str(e)})
    return out
