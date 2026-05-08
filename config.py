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

# === Flask ===
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-insecure-change-me")
FLASK_ENV = os.getenv("FLASK_ENV", "development")

# === Параметры LLM ===
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-5-20250929")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2000"))

# === Пути ===
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
UPLOADS_DIR = BASE_DIR / "static" / "uploads"

# Создаём папки если их нет (важно при первом запуске после клонирования)
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "lora.db"
DB_URL = f"sqlite:///{DB_PATH}"

AI_LOG_PATH = LOGS_DIR / "ai_calls.jsonl"
APP_LOG_PATH = LOGS_DIR / "app.log"

# === Эндпоинты внешних сервисов ===
# ProxyAPI: проксирует Anthropic Messages API
PROXYAPI_ANTHROPIC_URL = "https://api.proxyapi.ru/anthropic/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# Kling AI v1 — text2image
KLING_BASE_URL = "https://api.klingai.com"
KLING_T2I_CREATE = "/v1/images/generations"

# === Загрузка файлов ===
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_UPLOAD_SIZE_MB = 10
