"""Placeholder для TikTok-публикатора.

Требует:
- Developer account на developers.tiktok.com
- App registration + одобрение Content Posting API access (платформа жёстко
  ограничивает доступ; для бизнес-аккаунтов проще)
- OAuth 2.0 flow
- Видеофайл (mp4, до 287 МБ, до 10 минут, ≤30 fps, портретная ориентация
  рекомендована)
- Загрузка через `/v2/post/publish/inbox/video/init/` (init → upload → status)

Документация: https://developers.tiktok.com/doc/content-posting-api-get-started
Особенности: TikTok сильно меняет условия доступа; перед реализацией
обязательно свежий research (см. `CLAUDE.md` раздел 4).

Это не реализуется в рамках v0.4.0.
"""
from pathlib import Path

from core.publishers.base import BasePublisher, PublishResult, PublishError


class TikTokPublisher(BasePublisher):
    PLATFORM = "tiktok"
    IMPLEMENTED = False  # placeholder, требует одобрения Content Posting API

    def is_configured(self) -> bool:
        return False

    def publish_text(self, message: str) -> PublishResult:
        raise PublishError("TikTok не поддерживает text-only публикации. Требуется видео.")

    def publish_with_video(self, message: str, video_path: Path) -> PublishResult:
        raise NotImplementedError(
            "TikTok-публикация ещё не реализована. См. core/publishers/tiktok.py docstring "
            "для плана подключения (Developer account, app review, OAuth)."
        )
