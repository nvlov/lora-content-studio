"""Точка входа Flask: создание приложения, инициализация БД, регистрация роутов."""
import logging
from logging.handlers import RotatingFileHandler

from flask import Flask

import config
from core.db import init_db, SessionLocal
from routes.pages import bp as pages_bp
from routes.api import bp as api_bp


def _setup_logging() -> None:
    """Логи: stdout + logs/app.log."""
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not root.handlers:
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)
        try:
            fh = RotatingFileHandler(
                config.APP_LOG_PATH, maxBytes=2_000_000, backupCount=2, encoding="utf-8"
            )
            fh.setFormatter(fmt)
            root.addHandler(fh)
        except Exception as e:
            root.warning("Не удалось открыть %s: %s", config.APP_LOG_PATH, e)


def create_app() -> Flask:
    _setup_logging()

    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.secret_key = config.FLASK_SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = (config.MAX_UPLOAD_SIZE_MB + 1) * 1024 * 1024

    init_db()

    app.register_blueprint(pages_bp)
    app.register_blueprint(api_bp)

    @app.teardown_appcontext
    def _shutdown_session(exception=None):
        SessionLocal.remove()

    return app


app = create_app()


if __name__ == "__main__":
    # Локальный запуск для Dr. Nik
    app.run(host="127.0.0.1", port=5000, debug=(config.FLASK_ENV == "development"))
