"""Загрузка переменных окружения и общие константы приложения."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Корень проекта
BASE_DIR = Path(__file__).resolve().parent

# Подгружаем .env (если есть) — все ключи берутся отсюда
load_dotenv(BASE_DIR / ".env")

# === API-ключи ===
PROXYAPI_KEY = os.getenv("PROXYAPI_KEY", "").strip()
KLING_ACCESS_KEY = os.getenv("KLING_ACCESS_KEY", "").strip()
KLING_SECRET_KEY = os.getenv("KLING_SECRET_KEY", "").strip()

# === VK API (v0.2) ===
VK_COMMUNITY_TOKEN = os.getenv("VK_COMMUNITY_TOKEN", "").strip()
VK_GROUP_ID = os.getenv("VK_GROUP_ID", "").strip()
VK_API_VERSION = os.getenv("VK_API_VERSION", "5.199").strip()
VK_API_BASE = "https://api.vk.com/method"

# === VK ID OAuth 2.1 (v0.3) ===
VK_OAUTH_APP_ID = os.getenv("VK_OAUTH_APP_ID", "").strip()
VK_OAUTH_REDIRECT_URI = os.getenv(
    "VK_OAUTH_REDIRECT_URI", "https://oauth.vk.com/blank.html"
).strip()
VK_OAUTH_DEVICE_ID = os.getenv("VK_OAUTH_DEVICE_ID", "").strip()
VK_USER_ACCESS_TOKEN = os.getenv("VK_USER_ACCESS_TOKEN", "").strip()
VK_USER_REFRESH_TOKEN = os.getenv("VK_USER_REFRESH_TOKEN", "").strip()
VK_USER_TOKEN_EXPIRES_AT = os.getenv("VK_USER_TOKEN_EXPIRES_AT", "").strip()

# Базовые эндпоинты VK ID OAuth 2.1 (id.vk.com и id.vk.ru — синонимы).
VK_OAUTH_AUTHORIZE_URL = "https://id.vk.com/authorize"
VK_OAUTH_TOKEN_URL = "https://id.vk.com/oauth2/auth"

# Скоупы по умолчанию для медиа-публикации в группу от имени группы.
VK_OAUTH_DEFAULT_SCOPE = "wall photos video groups offline"

# === Flask ===
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-insecure-change-me")
FLASK_ENV = os.getenv("FLASK_ENV", "development")

# === Параметры LLM ===
LLM_MODEL = os.getenv("LLM_MODEL", "claude-opus-4-7")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2000"))

# === Пути ===
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
UPLOADS_DIR = BASE_DIR / "static" / "uploads"
IMAGES_DIR = UPLOADS_DIR / "images"
VIDEOS_DIR = UPLOADS_DIR / "videos"

# Создаём папки если их нет (важно при первом запуске после клонирования)
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "lora.db"
DB_URL = f"sqlite:///{DB_PATH}"

AI_LOG_PATH = LOGS_DIR / "ai_calls.jsonl"
APP_LOG_PATH = LOGS_DIR / "app.log"

# === Эндпоинты внешних сервисов ===
# ProxyAPI: проксирует Anthropic Messages API
PROXYAPI_ANTHROPIC_URL = "https://api.proxyapi.ru/anthropic/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# ProxyAPI: проксирует OpenAI Images API (gpt-image-2)
PROXYAPI_OPENAI_IMAGES_URL = "https://api.proxyapi.ru/openai/v1/images/generations"
OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-2")

# Пресеты size для gpt-image-2 (ключ → строка для API).
# Кратно 16 px, отношение сторон ≤ 3:1, max 3840 px.
GPT_IMAGE_SIZE_PRESETS = {
    "square":     "1024x1024",   # квадрат для VK поста
    "vertical":   "1024x1536",   # сторис / вертикальное превью
    "horizontal": "1536x1024",   # горизонталь / обложка
    "auto":       "auto",        # модель выбирает сама
}
GPT_IMAGE_QUALITY_LEVELS = {"low", "medium", "high", "auto"}

# Kling AI v1 — text2image
KLING_BASE_URL = os.getenv("KLING_BASE_URL", "https://api-singapore.klingai.com").strip()
KLING_T2I_CREATE = "/v1/images/generations"

# === Загрузка файлов ===
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm", "mov"}
ALLOWED_IMAGE_MIME = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_VIDEO_MIME = {"video/mp4", "video/webm", "video/quicktime"}
MAX_UPLOAD_SIZE_MB = 10           # для изображений
MAX_VIDEO_SIZE_MB = 200           # для видео

# === VK ===
VK_TEXT_LIMIT = 4096              # символов в посте VK
