"""Базовый интерфейс публикатора. Все конкретные публикаторы наследуются от BasePublisher.

Контракт:
- `is_configured()` — есть ли валидные ключи и доступ. False = не сконфигурирован.
- `publish_text(message)` — публикует только текст. Возвращает PublishResult.
- `publish_with_image(message, image_path)` — текст + одна картинка (опционально).
- `publish_with_video(message, video_path)` — текст + видео (опционально).

Если платформа не поддерживает медиа — соответствующий метод бросает
NotImplementedError. Это позволяет scheduler корректно реагировать.
"""
from pathlib import Path
from typing import TypedDict, Optional


class PublishError(Exception):
    """Понятная ошибка публикации, безопасная для показа пользователю."""


class PublishResult(TypedDict):
    platform: str          # 'vk' / 'telegram' / ...
    post_id: str           # ID поста в платформе
    post_url: str          # Прямая ссылка на пост


class BasePublisher:
    """Базовый класс публикатора. Подклассы переопределяют publish_*.

    Атрибут IMPLEMENTED — флаг для UI/CLI: можно ли пытаться публиковать.
    Для placeholder'ов (YouTube, TikTok пока не написан реальный OAuth) = False.
    """

    PLATFORM: str = ""
    IMPLEMENTED: bool = True

    def is_configured(self) -> bool:
        """True если ключи доступа заданы в .env. Не делает сетевых вызовов."""
        return False

    def publish_text(self, message: str) -> PublishResult:
        raise NotImplementedError(
            f"{self.__class__.__name__}: publish_text не реализован."
        )

    def publish_with_image(self, message: str, image_path: Path) -> PublishResult:
        raise NotImplementedError(
            f"{self.__class__.__name__}: публикация с изображением не поддерживается."
        )

    def publish_with_video(self, message: str, video_path: Path) -> PublishResult:
        raise NotImplementedError(
            f"{self.__class__.__name__}: публикация с видео не поддерживается."
        )
