"""Placeholder для YouTube-публикатора.

Требует:
- Google Cloud project + OAuth 2.0 client credentials
- YouTube Data API v3 enabled
- App review для production scope (если канал не личный) — это процедура от Google
- Видеофайл подходящего формата (mp4, до 256 ГБ или 12 ч)
- Загрузка через `videos.insert` (resumable upload)

Документация: https://developers.google.com/youtube/v3/docs/videos/insert
Лимиты: 10 000 quota units / день по умолчанию, video upload = 1600 units.

Это не реализуется в рамках v0.4.0. Подключение — отдельная сессия с
Discovery (см. `CLAUDE.md` раздел 4) после реальной потребности у Dr. Nik.
"""
from pathlib import Path

from core.publishers.base import BasePublisher, PublishResult, PublishError


class YouTubePublisher(BasePublisher):
    PLATFORM = "youtube"
    IMPLEMENTED = False  # placeholder, OAuth flow ещё не написан

    def is_configured(self) -> bool:
        return False

    def publish_text(self, message: str) -> PublishResult:
        raise PublishError("YouTube не поддерживает text-only публикации. Требуется видео.")

    def publish_with_video(self, message: str, video_path: Path) -> PublishResult:
        raise NotImplementedError(
            "YouTube-публикация ещё не реализована. См. core/publishers/youtube.py docstring "
            "для плана подключения (Google Cloud, OAuth, app review)."
        )
