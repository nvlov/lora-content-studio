# CLAUDE_CODE_VK_OAUTH_001 — уточнения к Phase 2 после Discovery

> **Статус:** дополнение к `CLAUDE_CODE_VK_OAUTH_001.md` после Phase 1 discovery (`docs/vk-oauth-research.md`).
> **Для следующей сессии:** читать вместе с оригинальным ТЗ, эти правки имеют приоритет над оригиналом в местах конфликта.
> **Дата:** 2026-05-10
> **Подтвердил:** Dr. Nik

Discovery вердикт — 🟡 YELLOW (`docs/vk-oauth-research.md`). Продолжаем в Phase 2 со следующими уточнениями.

---

## 1. Подтверждённые эндпоинты (источник: VKCOM/vkid-android-sdk)

| Что | URL | Метод |
|---|---|---|
| Authorize (browser redirect) | `https://id.vk.ru/authorize` | GET |
| Token exchange / refresh | `https://id.vk.ru/oauth2/auth` | POST (form) |
| API VK | `https://api.vk.ru/method/<method>` | GET/POST |

**Не использовать:** `id.vk.com` (это маркетинговая страница, не API), `oauth.vk.com/access_token` (legacy OAuth 2.0, удалён в 2025).

**API version:** `5.131` (подтверждено sample-кодом VKID Android SDK).

---

## 2. Замена в разделе 4.1 ТЗ — `.env.example` и `config.py`

**Заменить блок «VK ID OAuth 2.1» в `.env.example` на:**

```
# === VK ID OAuth 2.1 (для медиа-публикации) ===
# App ID из dev.vk.com (Standalone-приложение, создан вручную)
VK_OAUTH_APP_ID=54586535

# Redirect URI — должен быть точно зарегистрирован в Self Service VK-приложения
# Локальная разработка:
VK_OAUTH_REDIRECT_URI=http://localhost:8123/callback
# Серверный деплой (заготовка):
# VK_OAUTH_REDIRECT_URI=https://lora.example.com/oauth/vk/callback

# Идентификатор устройства/клиента — UUID4, генерируется при ПЕРВОЙ авторизации
# в scripts/get_vk_token.py и затем не меняется. Обязателен в каждом refresh.
# НЕ заполнять руками; скрипт сделает.
VK_OAUTH_DEVICE_ID=

# Токены — заполняются автоматически после OAuth-flow.
# Не трогать руками после первой авторизации.
VK_USER_ACCESS_TOKEN=
VK_USER_REFRESH_TOKEN=
VK_USER_TOKEN_EXPIRES_AT=

# Локальный порт для приёма OAuth callback (только для локальной авторизации)
VK_OAUTH_LOCAL_PORT=8123

# === Старые переменные (deprecated, fallback) ===
# Если VK_USER_ACCESS_TOKEN пустой — приложение упадёт обратно на этот старый
# community/user-token. Используется как fallback при первом запуске v0.3
# до получения нового OAuth-токена.
VK_COMMUNITY_TOKEN=
VK_GROUP_ID=237689862
VK_API_VERSION=5.131
```

**Что убрано:** `VK_OAUTH_CLIENT_SECRET` — для VK ID OAuth 2.1 (Authorization Code Flow + PKCE) `client_secret` НЕ нужен (это public client flow). Подтверждено исходниками VKID Android SDK: метод `getToken()` и `refreshToken()` НЕ передают client_secret.

**Что добавлено:** `VK_OAUTH_DEVICE_ID` — UUID4, генерируется при первой авторизации в `scripts/get_vk_token.py`, сохраняется в `.env`, обязательно используется в каждом refresh-запросе (без него VK может не позволить refresh).

**В `config.py`** — те же helper-функции из ТЗ, но БЕЗ `VK_OAUTH_CLIENT_SECRET`. `get_active_vk_token()` логика без изменений.

---

## 3. Замена в разделе 4.2 ТЗ — `core/vk_oauth.py`

**Сигнатуры функций без `client_secret`:**

```python
def generate_pkce_pair() -> tuple[str, str]:
    """(code_verifier, code_challenge). Алгоритм s256 (нижний регистр).
    code_verifier: 43-128 символов из [A-Z][a-z][0-9]-._~ (RFC 7636).
    code_challenge: base64url-no-padding(sha256(verifier))."""

def build_authorize_url(app_id: str, redirect_uri: str, scope: str,
                         code_challenge: str, state: str) -> str:
    """Собирает URL https://id.vk.ru/authorize?... 
    БЕЗ device_id (он не идёт в URL, только в /oauth2/auth POST)."""

def exchange_code_for_tokens(code: str, code_verifier: str, app_id: str,
                              redirect_uri: str, device_id: str,
                              state: str) -> dict:
    """POST https://id.vk.ru/oauth2/auth с form-body:
    grant_type=authorization_code, code, code_verifier, client_id (=app_id),
    device_id, redirect_uri, state.
    Возвращает {'access_token','refresh_token','expires_at','user_id','scope', ...}."""

def refresh_access_token(refresh_token: str, app_id: str, device_id: str,
                          state: str) -> dict:
    """POST https://id.vk.ru/oauth2/auth с form-body:
    grant_type=refresh_token, refresh_token, client_id (=app_id), device_id, state.
    Возвращает {'access_token','refresh_token','expires_at', ...}."""

class VKOAuthError(Exception):
    """Понятные русские сообщения по ошибкам VK ID."""
```

**Конкретные параметры запросов** см. `docs/vk-oauth-research.md` раздел 2.4.

PKCE параметр `code_challenge_method` — строго `s256` (нижний регистр), не `S256`.

---

## 4. Замена в разделе 4.3 ТЗ — `scripts/get_vk_token.py`

**Изменения:**

1. Шаг 2 ТЗ: убрать проверку `VK_OAUTH_CLIENT_SECRET` — его больше нет.
2. Шаг 3 ТЗ: `device_id` сначала прочитать из `.env`. Если пустой — сгенерировать `uuid.uuid4().hex`, **сразу записать в `.env`** через `update_env_file()`, и использовать. Если уже есть — переиспользовать.
3. Шаг 8 ТЗ: вызов `exchange_code_for_tokens(code, code_verifier, app_id, redirect_uri, device_id, state)` — без `client_secret`.
4. Шаг 9 ТЗ: записать в `.env` четыре ключа:
   - `VK_USER_ACCESS_TOKEN`
   - `VK_USER_REFRESH_TOKEN`
   - `VK_USER_TOKEN_EXPIRES_AT`
   - `VK_OAUTH_DEVICE_ID` (если ещё не записан в шаге 3 — на всякий случай защита от потери)

**Scope, который запрашивает скрипт по умолчанию:**
```python
DEFAULT_SCOPE = "wall photos video groups offline"
```
(Можно вынести в константу `core/vk_oauth.py` и переопределять через CLI-аргумент `--scope`.)

После shows-успешного response — **проверить `scope` в ответе** и распечатать пользователю:
```
Получены права: wall photos video groups offline
```
Если в `scope` нет `wall` или `photos` — вывести предупреждение:
```
⚠ В токене нет 'wall'/'photos'. В Self Service VK-приложения нужно явно
  разрешить эти scope. См. README → Шаг A.
```

---

## 5. Замена в разделе 4.4 ТЗ — `core/vk_client.py`

**В `_ensure_fresh_token()` — без `client_secret`:**

```python
tokens = refresh_access_token(
    self._refresh_token,
    self._app_id,
    self._device_id,
    state=secrets.token_hex(16),
)
```

В `__init__` загружать `VK_OAUTH_DEVICE_ID` в `self._device_id`. Если пусто — это означает что OAuth ни разу не выполнялся; идти по legacy-пути с предупреждением.

Остальная логика (lock, обновление `.env`, `VKAuthExpiredError`) — без изменений.

---

## 6. Замена в разделе 4.5 ТЗ — README раздел «Шаг A»

**Точные имена пунктов меню в новом Self Service (на dev.vk.com / id.vk.com) пока не подтверждены живым источником** — discovery не смогло открыть `id.vk.com` через WebFetch. В Phase 2 при написании README указать общую инструкцию + ссылки, и пометить что точные названия пунктов могут отличаться (Dr. Nik скорректирует руками если что).

Структура раздела:
1. Открыть приложение «Lora Content Studio» в [dev.vk.com](https://dev.vk.com) (App ID = 54586535)
2. Найти раздел с настройкой redirect URI (название может отличаться: «Размещение» / «OAuth» / «Адреса»)
3. Добавить две строки:
   - `http://localhost:8123/callback`
   - `https://lora.example.com/oauth/vk/callback` ← заготовка для сервера
4. Найти раздел с разрешениями / scopes — убедиться что разрешены: **wall, photos, video, groups, offline**. Если нет — включить.
5. **Не нужно** копировать «Защищённый ключ» (client_secret) — для PKCE-flow он не используется.
6. Сохранить настройки приложения VK.

---

## 7. Замена в разделе 5.2 ТЗ — `/api/vk/status` ответ

Без изменений по структуре, только убрать упоминание client_secret из логики.

---

## 8. Без изменений (берём из оригинального ТЗ как есть)

- Phase 3 (раздел 5) — backward compatibility, fallback на legacy token
- Phase 4 (раздел 6) — `docs/server-deployment-vk.md`
- Phase 5 (раздел 7) — юнит-тесты + интеграционный refresh с моком
- Раздел 9 «Что НЕ делать»
- Раздел 10 «Финальный отчёт»

В тестах учесть: `client_secret` нет нигде в сигнатурах и моках.

---

## 9. Чек-лист для следующей сессии перед Phase 2

- [ ] Открыть ветку `feat/v0.3-vk-oauth` (уже создана)
- [ ] Прочитать `docs/vk-oauth-research.md` (фиксирует endpoints, scope, PKCE)
- [ ] Прочитать этот файл (`CLAUDE_CODE_VK_OAUTH_001_PHASE2_UPDATES.md`) — он перекрывает разделы 4.1–4.5 оригинального ТЗ
- [ ] Прочитать `CLAUDE_CODE_VK_OAUTH_001.md` (фазы 3–5, не покрытые updates)
- [ ] Идти по Шагам выполнения раздела 8 оригинального ТЗ, начиная с шага 3 «GREEN/YELLOW → реализация»
