"""Получение VK ID OAuth 2.1 токенов (manual-paste flow).

Запускается ОДИН раз на машине с браузером. После этого долгоживущее
приложение (app.py) само рефрешит access_token через refresh_token.

Архитектура — manual paste, потому что VK ID не принимает http://localhost
в качестве redirect_uri (требует HTTPS). Используем blank-страницу VK
(https://oauth.vk.com/blank.html) и просим пользователя скопировать URL
из адресной строки браузера после редиректа.

Запуск:
    python scripts/get_vk_token.py

Что делает:
1. Читает .env (VK_OAUTH_APP_ID, VK_OAUTH_REDIRECT_URI, VK_OAUTH_DEVICE_ID).
2. Генерирует device_id (UUID-hex), если его ещё нет — сразу пишет в .env.
3. Открывает браузер на /authorize с PKCE.
4. Просит пользователя авторизоваться и вставить полный URL из адресной строки.
5. Парсит code+state+device_id, обменивает на пару (access, refresh).
6. Записывает 4 ключа в .env (access, refresh, expires_at, device_id).
"""
from __future__ import annotations

import argparse
import sys
import uuid
import webbrowser
from pathlib import Path

# Добавляем корень проекта в sys.path, чтобы работали "import config" и т.п.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from core.vk_oauth import (  # noqa: E402
    VKOAuthError,
    build_authorize_url,
    exchange_code_for_tokens,
    generate_pkce_pair,
    generate_state,
    parse_callback_url,
)


ENV_PATH = ROOT / ".env"


def update_env_file(env_path: Path, updates: dict[str, str]) -> None:
    """Аккуратно обновляет/добавляет KEY=VALUE строки в .env, не трогая остальные.

    Сохраняет порядок и комментарии. Если ключ есть — заменяет правую часть.
    Если нет — добавляет в конец файла.
    """
    if not env_path.exists():
        env_path.write_text("", encoding="utf-8")

    lines = env_path.read_text(encoding="utf-8").splitlines()
    remaining = dict(updates)
    out: list[str] = []

    for line in lines:
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(line)

    for key, value in remaining.items():
        out.append(f"{key}={value}")

    # Сохраняем перевод строки в конце.
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _ensure_device_id() -> str:
    """Возвращает существующий VK_OAUTH_DEVICE_ID или генерирует новый и пишет в .env."""
    existing = (config.VK_OAUTH_DEVICE_ID or "").strip()
    if existing:
        print(f"  device_id (из .env): {existing}")
        return existing
    new_id = uuid.uuid4().hex
    update_env_file(ENV_PATH, {"VK_OAUTH_DEVICE_ID": new_id})
    print(f"  device_id (сгенерирован): {new_id}")
    print(f"  → записан в {ENV_PATH}")
    return new_id


def _print_scope_warning(scope: str) -> None:
    needed = {"wall", "photos", "video", "groups"}
    got = set((scope or "").split())
    missing = needed - got
    if not missing:
        return
    print()
    print("⚠ ВНИМАНИЕ: в выданных правах НЕ хватает:", " ".join(sorted(missing)))
    print("  В Self Service VK-приложения (id.vk.com → твоё приложение → Настройки)")
    print("  нужно явно разрешить эти scope. См. README → «Шаг A».")


def main() -> int:
    parser = argparse.ArgumentParser(description="Получить VK ID OAuth токены (manual-paste flow).")
    parser.add_argument(
        "--scope",
        default=config.VK_OAUTH_DEFAULT_SCOPE,
        help=f"Запрашиваемые scope (по умолчанию: {config.VK_OAUTH_DEFAULT_SCOPE!r}).",
    )
    args = parser.parse_args()

    app_id = config.VK_OAUTH_APP_ID
    redirect_uri = config.VK_OAUTH_REDIRECT_URI

    print("=" * 70)
    print("VK ID OAuth 2.1 — получение токенов (manual-paste flow)")
    print("=" * 70)
    print()

    if not app_id:
        print("ОШИБКА: VK_OAUTH_APP_ID не задан в .env.")
        print("Заполни VK_OAUTH_APP_ID (App ID Standalone-приложения с id.vk.com)")
        print("и запусти снова.")
        return 1

    if not redirect_uri:
        print("ОШИБКА: VK_OAUTH_REDIRECT_URI не задан в .env.")
        return 1

    print(f"App ID:      {app_id}")
    print(f"Redirect:    {redirect_uri}")
    print(f"Scope:       {args.scope}")
    print()

    device_id = _ensure_device_id()
    code_verifier, code_challenge = generate_pkce_pair()
    state = generate_state()

    auth_url = build_authorize_url(
        app_id=app_id,
        redirect_uri=redirect_uri,
        scope=args.scope,
        code_challenge=code_challenge,
        state=state,
    )

    print()
    print("Сейчас откроется браузер на странице авторизации VK ID.")
    print("Если не открылся автоматически — скопируй URL ниже и открой вручную:")
    print()
    print(auth_url)
    print()

    try:
        webbrowser.open(auth_url)
    except Exception as e:
        print(f"  (не удалось открыть браузер автоматически: {e})")

    print("=" * 70)
    print("Что делать в браузере:")
    print(f"  1. Авторизуйся ПОД ЛИЧНЫМ аккаунтом админа группы.")
    print(f"  2. Подтверди запрашиваемые разрешения.")
    print(f"  3. VK редиректит на {redirect_uri} (страница будет почти пустая).")
    print(f"  4. Скопируй ПОЛНЫЙ URL из адресной строки браузера")
    print(f"     (он содержит ?code=...&state=...&device_id=...).")
    print(f"  5. Вставь его сюда ниже и нажми Enter.")
    print("=" * 70)
    print()

    try:
        callback_url = input("URL из адресной строки: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        print("Отменено пользователем.")
        return 1

    if not callback_url:
        print("Пустой ввод — отменено.")
        return 1

    try:
        parsed = parse_callback_url(callback_url, expected_state=state)
    except VKOAuthError as e:
        print(f"\nОШИБКА разбора callback URL: {e}")
        return 1

    callback_device_id = parsed["device_id"]
    if callback_device_id != device_id:
        # VK прислал свой device_id — он авторитетен, перезаписываем .env.
        print()
        print(f"  VK прислал свой device_id: {callback_device_id}")
        print(f"  → перезаписываю VK_OAUTH_DEVICE_ID в .env")
        device_id = callback_device_id

    print()
    print("Обмениваю code на токены...")
    try:
        tokens = exchange_code_for_tokens(
            code=parsed["code"],
            code_verifier=code_verifier,
            app_id=app_id,
            redirect_uri=redirect_uri,
            device_id=device_id,
            state=state,
        )
    except VKOAuthError as e:
        print(f"\nОШИБКА обмена code на токены: {e}")
        return 1

    print("Готово. Получены токены.")
    print(f"  user_id:    {tokens.get('user_id')}")
    print(f"  scope:      {tokens.get('scope')}")
    print(f"  expires_at: {tokens['expires_at'].isoformat()}")
    print(f"  refresh:    {'есть' if tokens.get('refresh_token') else 'НЕТ — добавь scope offline'}")

    update_env_file(ENV_PATH, {
        "VK_OAUTH_DEVICE_ID": device_id,
        "VK_USER_ACCESS_TOKEN": tokens["access_token"],
        "VK_USER_REFRESH_TOKEN": tokens.get("refresh_token", ""),
        "VK_USER_TOKEN_EXPIRES_AT": tokens["expires_at"].isoformat(),
    })
    print()
    print(f"Записано в {ENV_PATH}:")
    print("  VK_OAUTH_DEVICE_ID, VK_USER_ACCESS_TOKEN,")
    print("  VK_USER_REFRESH_TOKEN, VK_USER_TOKEN_EXPIRES_AT")

    _print_scope_warning(tokens.get("scope", ""))

    print()
    print("Дальше:")
    print("  1. Перезапусти приложение (python app.py).")
    print("  2. Открой http://127.0.0.1:5000 — попробуй опубликовать пост с медиа.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
