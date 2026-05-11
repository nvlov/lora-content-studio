# CLAUDE_CODE_VK_OAUTH_001 — VK ID OAuth 2.1 helper + автообновление токена

> **Тип:** инфраструктурное задание, разблокирующее медиа-публикацию.
> **Целевая версия после:** v0.3.0 (это уже не патч — добавляется новая инфраструктура и точка интеграции).
> **Приоритет:** блокирующий — без user-токена с правами публикации медиа в группу проект остаётся в состоянии «текст работает, картинки и видео нет».

---

## 1. Контекст и предыстория

После v0.2.2 (markdown-фикс v0.2.3 ещё не сделан — он ОТЛОЖЕН до этого OAuth-фикса):
- Текстовая публикация в VK работает (user-token Dr. Nik подтвердил руками)
- Медиа-публикация падает с VK code 27 на community-token (документированное ограничение `wall_upload`/`video.save` для community-токенов)
- Наша инструкция получить user-token через старый Implicit Flow (`oauth.vk.com/authorize?response_type=token`) **не работает** — VK с 2025 перевёл систему на VK ID OAuth 2.1, Implicit Flow удалён
- Сторонние обходы (vkhost.github.io через чужой client_id) отвергнуты — выбран путь честной интеграции с VK ID OAuth 2.1

Цель этого задания — построить **инфраструктуру user-токена** которая (а) работает сегодня на локальной машине Dr. Nik, (б) совместима с будущим деплоем на VPS без изменения кода — только конфигурации.

## 2. Цели задания

1. **Один раз** провести user-OAuth через VK ID и получить пару `access_token + refresh_token`
2. **Автоматически обновлять** `access_token` (живёт 24 часа) с помощью `refresh_token` — без участия пользователя
3. **Архитектура — серверо-готовая:** скрипт получения токена работает на машине с браузером (один раз), а долгоживущее приложение использует только `refresh_token` для server-to-server обновления
4. **Backward-compat:** не сломать публикацию текстов, которая сейчас работает на community-token; deprecation-предупреждение в логах если используется старый токен

## 3. Phase 1 — Discovery (ОБЯЗАТЕЛЬНЫЙ первый шаг)

**До написания любого кода** — провести web search и зафиксировать ответы в новый файл `docs/vk-oauth-research.md`. Если хоть один пункт даёт «нет/не уверен» — **остановиться**, написать пользователю в чате, не идти в реализацию.

### 3.1. Что выяснить

1. **Точный домен и эндпоинты VK ID OAuth 2.1:**
   - `id.vk.com` или `id.vk.ru` или оба (актуальный)?
   - Endpoint authorize: `/authorize` или другой
   - Endpoint token exchange: `/oauth2/auth` или другой
   - Endpoint userinfo (опц.): какой
   - Свежий пример рабочего HTTP-флоу из документации или production-пакета (Laravel Socialite VKID, vk-api Python, etc.)

2. **Какие scope выдают права на `wall.post` + `photos.getWallUploadServer` + `video.save`** через VK ID OAuth 2.1?
   - Старые scope `wall,photos,video,offline` всё ещё валидны?
   - Или VK ID использует новые названия (например, `vkid.personal_info`, `vkid.email` и т.п.)?
   - **Главное: можно ли user-токеном из VK ID опубликовать пост с медиа в группу-сообщество от имени группы (через `wall.post(owner_id=-group_id, from_group=1)`)?**

3. **Параметры PKCE:**
   - Algorithm: S256 или plain
   - Code verifier length: точные ограничения VK
   - Состав символов

4. **Refresh token:**
   - Сколько живёт `refresh_token` (бесконечно? 90 дней? до явного отзыва?)
   - Refresh token rotation (выдаёт ли VK новый refresh при каждом обновлении access)
   - Как корректно делать `grant_type=refresh_token` запрос

5. **Redirect URI требования:**
   - HTTP допустим для localhost, или HTTPS обязателен везде?
   - Сколько redirect URI можно зарегистрировать на одно приложение?
   - Параметр `device_id` (упоминается в новой документации) — что это и нужен ли он

### 3.2. Decision gate

После discovery — записать в `docs/vk-oauth-research.md` краткий вердикт:

- ✅ **GREEN:** все 5 пунктов отвечены, сценарий wall.post с медиа через VK ID токен подтверждён рабочим примером — продолжаем Phase 2
- ⚠ **YELLOW:** есть неясности по 1-2 пунктам, но базовый пайплайн понятен — продолжаем Phase 2 с пометками о рисках в коде
- ❌ **RED:** VK ID не поддерживает scope для community-постинга, или другая фундаментальная блокировка — **СТОП**. Написать пользователю в чат: «discovery показал X, рекомендую обсудить альтернативы». **НЕ продолжать самостоятельно.**

---

## 4. Phase 2 — Implementation (только если discovery GREEN/YELLOW)

### 4.1. Расширение `.env.example` и `config.py`

Новые переменные:

```
# === VK ID OAuth 2.1 (новая система авторизации, для медиа-публикации) ===
# App ID из dev.vk.com (создан вручную)
VK_OAUTH_APP_ID=54586535

# Защищённый ключ (client secret) из настроек приложения, вкладка "Ключи доступа"
VK_OAUTH_CLIENT_SECRET=

# Redirect URI — должен быть точно зарегистрирован в настройках приложения VK
# Для локальной разработки:
VK_OAUTH_REDIRECT_URI=http://localhost:8123/callback
# Для серверного деплоя (раскомментировать и настроить когда будет домен и SSL):
# VK_OAUTH_REDIRECT_URI=https://lora.example.com/oauth/vk/callback

# Токены — заполняются автоматически скриптом scripts/get_vk_token.py
# НЕ трогать руками после первой авторизации
VK_USER_ACCESS_TOKEN=
VK_USER_REFRESH_TOKEN=
VK_USER_TOKEN_EXPIRES_AT=

# Локальный сервер для приёма OAuth callback (только для локальной авторизации)
VK_OAUTH_LOCAL_PORT=8123

# === Старые переменные (deprecated, оставлены для backward compatibility) ===
# Если VK_USER_ACCESS_TOKEN пустой — приложение упадёт обратно на этот старый community/user token
# Используется как fallback при первом запуске v0.3 до получения нового токена
VK_COMMUNITY_TOKEN=
VK_GROUP_ID=237689862
VK_API_VERSION=5.131
```

**В `config.py`** добавить логику:
- Загрузка всех новых переменных
- Helper-функция `get_active_vk_token() -> tuple[str, str]` возвращает `(token, source)` где source ∈ `'oauth_user'` | `'legacy_community'`
- Если `VK_USER_ACCESS_TOKEN` есть и не истёк (`now() < VK_USER_TOKEN_EXPIRES_AT - 5min`) — отдаёт его
- Иначе если есть `VK_USER_REFRESH_TOKEN` — рефрешит и отдаёт
- Иначе если есть `VK_COMMUNITY_TOKEN` — отдаёт его с warning в лог («deprecation: get OAuth token via scripts/get_vk_token.py»)
- Иначе — `None, None`

### 4.2. Модуль `core/vk_oauth.py` (новый)

Содержит всю OAuth-логику отдельно от `vk_client.py` чтобы не загромождать его.

**Функции:**

```python
def generate_pkce_pair() -> tuple[str, str]:
    """Возвращает (code_verifier, code_challenge). S256."""
    # Random 32 bytes -> base64url -> 43 chars без padding = code_verifier
    # SHA-256(code_verifier) -> base64url без padding = code_challenge

def build_authorize_url(app_id: str, redirect_uri: str, scope: str,
                         code_challenge: str, state: str, device_id: str = None) -> str:
    """Собирает URL для VK ID authorize endpoint."""
    # Если discovery показал что нужен device_id — генерировать UUID4

def exchange_code_for_tokens(code: str, code_verifier: str, app_id: str,
                              client_secret: str, redirect_uri: str,
                              device_id: str = None) -> dict:
    """
    POST на token-endpoint VK ID, обмен code на (access_token, refresh_token, expires_in).
    Возвращает {'access_token': ..., 'refresh_token': ..., 'expires_at': datetime, ...}
    """

def refresh_access_token(refresh_token: str, app_id: str, client_secret: str,
                          device_id: str = None) -> dict:
    """
    POST с grant_type=refresh_token. Возвращает новый access_token (+ возможно новый refresh_token
    если VK rotates). Использует тот же формат ответа что и exchange_code_for_tokens.
    """

class VKOAuthError(Exception):
    """Понятные русские сообщения по типичным ошибкам VK ID."""
```

Каждая функция логирует в `logs/ai_calls.jsonl` с `provider: "vk_oauth"` и без значения токена в логе (чтобы не утекало в файл).

### 4.3. Скрипт `scripts/get_vk_token.py`

Запускается **на машине Dr. Nik с браузером** один раз (или при истечении refresh_token).

**Поток выполнения:**

1. Загрузить `.env` через python-dotenv
2. Проверить что `VK_OAUTH_APP_ID` и `VK_OAUTH_CLIENT_SECRET` заполнены — если нет, показать инструкцию (см. README раздел) и завершиться с кодом 1
3. Сгенерировать `code_verifier`, `code_challenge`, `state` (random 32 bytes hex), `device_id` (UUID4 если нужен)
4. Вычислить `redirect_uri` из `VK_OAUTH_REDIRECT_URI`
5. Поднять `http.server.HTTPServer` на порту `VK_OAUTH_LOCAL_PORT` с обработчиком `/callback`
6. Открыть браузер через `webbrowser.open(authorize_url)`
7. Вывести в консоль: «Открыл браузер. Авторизуйся в VK и подтверди разрешения. Жду callback на http://localhost:8123/callback…»
8. После получения callback на `/callback`:
   - Проверить что `state` совпадает (защита от CSRF) — если нет, ошибка
   - Извлечь `code` из query params
   - Если ошибка от VK — вывести понятно, завершиться
   - Иначе вызвать `exchange_code_for_tokens(...)`
9. Полученные `access_token`, `refresh_token`, `expires_at` записать в `.env` через **аккуратное обновление** (не перезаписывать весь файл — заменить/добавить только эти 3 строки):

```python
def update_env_file(env_path: Path, updates: dict[str, str]):
    """Аккуратно обновляет/добавляет строки в .env, не трогая остальные."""
    # Читать построчно, для каждого ключа из updates искать строку KEY=...,
    # заменять; если не нашли — добавить в конец.
```

10. Показать пользователю в браузере страницу-подтверждение «Готово! Можешь закрыть это окно. Возвращайся в терминал.»
11. Корректно завершить HTTP-сервер и скрипт (success exit 0)

**Edge cases:**
- Порт 8123 занят → попробовать 8124, 8125; если все заняты — ошибка
- Пользователь закрыл браузер не подтвердив → таймаут 5 минут, потом завершение с понятной ошибкой
- VK вернул `error=access_denied` → понятное сообщение «Ты отказался разрешить доступ»

### 4.4. Обновление `core/vk_client.py`

Добавить в начало каждого метода (`upload_photo`, `upload_video`, `post_to_wall`) вызов `_ensure_fresh_token()`:

```python
class VKClient:
    def __init__(self, ...):
        self._token = None
        self._token_source = None  # 'oauth_user' | 'legacy_community'
        self._token_expires_at = None
        self._refresh_token = None
        self._client_secret = None
        self._app_id = None
        self._lock = threading.Lock()  # защита от параллельного refresh

    def _ensure_fresh_token(self):
        """
        Проверяет свежесть токена. Если до истечения < 5 минут — рефрешит.
        Если refresh_token нет (legacy mode) — пропускает (старый токен живёт пока живёт).
        """
        with self._lock:
            if self._token_source != 'oauth_user':
                return  # legacy токен не обновляем
            if not self._token_expires_at:
                return
            if datetime.utcnow() < self._token_expires_at - timedelta(minutes=5):
                return  # ещё свеж
            # рефрешим
            from core.vk_oauth import refresh_access_token
            tokens = refresh_access_token(self._refresh_token, self._app_id,
                                           self._client_secret)
            self._token = tokens['access_token']
            self._token_expires_at = tokens['expires_at']
            if 'refresh_token' in tokens:  # rotation
                self._refresh_token = tokens['refresh_token']
            # Сохраняем в .env через ту же update_env_file
            from scripts.get_vk_token import update_env_file
            update_env_file(Path('.env'), {
                'VK_USER_ACCESS_TOKEN': self._token,
                'VK_USER_REFRESH_TOKEN': self._refresh_token,
                'VK_USER_TOKEN_EXPIRES_AT': self._token_expires_at.isoformat(),
            })
            logger.info("VK access token refreshed automatically")
```

Если refresh падает с ошибкой «invalid refresh_token» (например, истёк) — выбросить `VKAuthExpiredError` с сообщением «Refresh token истёк. Запусти `python scripts/get_vk_token.py` для повторной авторизации.»

### 4.5. Обновление настроек VK-приложения (для пользователя)

В **README** добавить раздел «**Шаг A. Настроить VK-приложение перед первой авторизацией**»:

> 1. Зайди на [dev.vk.com](https://dev.vk.com) → твоё приложение «Lora Content Studio»
> 2. Перейди в раздел «Настройки → Размещение» (или похожий — название может отличаться)
> 3. В поле «Доверенные redirect URI» добавь две строки:
>    ```
>    http://localhost:8123/callback
>    https://lora.example.com/oauth/vk/callback   ← оставь как заготовку для будущего сервера
>    ```
> 4. В разделе «Настройки → Ключи доступа» скопируй **Защищённый ключ** (client_secret) и положи в `.env` как `VK_OAUTH_CLIENT_SECRET=…`
> 5. Сохрани изменения в настройках VK-приложения

**ВАЖНО:** если в discovery выяснилось что URL/раздел в новом интерфейсе VK ID отличаются — Claude Code исправляет инструкцию в README на актуальную версию.

---

## 5. Phase 3 — Backward compatibility и миграция

### 5.1. Логика fallback в `vk_client.__init__`

```python
# Сначала пробуем VK_USER_ACCESS_TOKEN (новый OAuth путь)
if VK_USER_ACCESS_TOKEN and VK_USER_REFRESH_TOKEN:
    self._token = VK_USER_ACCESS_TOKEN
    self._refresh_token = VK_USER_REFRESH_TOKEN
    self._token_expires_at = parse_iso(VK_USER_TOKEN_EXPIRES_AT)
    self._client_secret = VK_OAUTH_CLIENT_SECRET
    self._app_id = VK_OAUTH_APP_ID
    self._token_source = 'oauth_user'
    logger.info("VK client initialized with OAuth user token")
elif VK_COMMUNITY_TOKEN:
    self._token = VK_COMMUNITY_TOKEN
    self._token_source = 'legacy_community'
    logger.warning(
        "VK client using legacy community token. "
        "Media upload may fail with code 27. "
        "Run scripts/get_vk_token.py to upgrade to OAuth user token."
    )
else:
    self._token = None
    self._token_source = None
    logger.warning("VK client has no token configured")
```

### 5.2. Эндпоинт `/api/vk/status` — расширить ответ

```json
{
  "configured": true,
  "token_source": "oauth_user",  // или "legacy_community" или null
  "token_expires_at": "2026-05-11T12:34:56Z",  // null для legacy
  "media_publish_supported": true  // false для legacy_community
}
```

В UI — если `media_publish_supported: false`, кнопки публикации **с медиа** становятся серыми с тултипом «Загрузка медиа требует OAuth-токен. Запусти `scripts/get_vk_token.py`». Кнопка публикации **только текста** остаётся активной.

### 5.3. Обновление `app.py`

При старте Flask: попробовать вызвать `_ensure_fresh_token()` через `vk_client.refresh_if_needed()`. Если refresh упал — залогировать предупреждение, но не падать. Приложение должно стартовать всегда.

---

## 6. Phase 4 — Серверо-совместимость (документация для v0.4)

В новый файл `docs/server-deployment-vk.md` (даже если v0.4 не сейчас, документация про OAuth должна быть готова):

```markdown
# VK OAuth на сервере (v0.4+)

## Принцип

Авторизацию проводим **на локальной машине** (один раз) → получаем `refresh_token` → переносим в `.env` сервера. Сервер сам рефрешит access_token через `refresh_token` без браузера.

## Шаги

1. На локальной машине (там где есть браузер):
   - В `.env` указать `VK_OAUTH_REDIRECT_URI=https://домен.сервера/oauth/vk/callback`
   - В настройках VK-приложения добавить тот же URI в доверенные
   - Запустить `python scripts/get_vk_token.py` — браузер откроется на локалке, но VK редиректнёт на серверный URL
   - Сервер должен иметь endpoint `/oauth/vk/callback` который примет code и сохранит его в `.env` сервера через SSH (или промежуточный механизм)

   **Альтернатива (проще):** временно поменять `VK_OAUTH_REDIRECT_URI` обратно на `localhost:8123/callback`, получить токены локально, скопировать VK_USER_REFRESH_TOKEN на сервер вручную через SSH.

2. На сервере (`.env` после ручного переноса):
   ```
   VK_OAUTH_APP_ID=54586535
   VK_OAUTH_CLIENT_SECRET=…
   VK_OAUTH_REDIRECT_URI=https://домен.сервера/oauth/vk/callback
   VK_USER_REFRESH_TOKEN=…  ← перенести с локали
   VK_USER_ACCESS_TOKEN=     ← оставить пустым, app сам получит свежий через refresh_token
   VK_USER_TOKEN_EXPIRES_AT= ← оставить пустым
   ```

3. При старте app на сервере: `vk_client._ensure_fresh_token()` увидит что access_token пустой/истёк, использует refresh_token, получит свежий — и работает дальше.

## HTTPS

VK ID требует HTTPS на проде. Использовать Let's Encrypt + Caddy / nginx + certbot.

## Если refresh_token истёк

Refresh_token имеет срок жизни (точная цифра — см. `docs/vk-oauth-research.md`). Когда истёк — приложение упадёт с понятной ошибкой `VKAuthExpiredError`. Тогда повторить шаг 1.
```

---

## 7. Phase 5 — Тесты

### 7.1. Юнит-тесты `tests/test_vk_oauth.py`

```python
def test_pkce_pair_format():
    v, c = generate_pkce_pair()
    assert 43 <= len(v) <= 128
    assert all(ch in CHARS_VERIFIER for ch in v)
    # c должен быть base64url(sha256(v)) без padding
    assert c == base64url_no_padding(hashlib.sha256(v.encode()).digest())

def test_authorize_url_contains_required_params():
    url = build_authorize_url(...)
    assert 'client_id=' in url
    assert 'code_challenge=' in url
    assert 'code_challenge_method=S256' in url
    assert 'state=' in url

def test_update_env_file_replaces_existing():
    # Записать в .env строку KEY=old_value
    # Вызвать update_env_file({KEY: 'new_value'})
    # Прочитать .env, убедиться KEY=new_value, остальные строки на месте

def test_update_env_file_adds_missing():
    # update_env_file({NEW_KEY: 'value'})
    # NEW_KEY должен появиться в конце файла
```

### 7.2. Интеграционный тест refresh-flow с моком

Замокать `httpx.post` — вернуть фейковый ответ VK ID с `access_token`, `refresh_token`, `expires_in: 86400`. Проверить что `_ensure_fresh_token()` корректно парсит и обновляет состояние клиента + `.env` файл.

**НЕ запускать** реальный refresh-call в тестах — это расходует токен.

---

## 8. Шаги выполнения по порядку

0. `git checkout -b feat/v0.3-vk-oauth`
1. **Phase 1 Discovery** → `docs/vk-oauth-research.md` → решение GREEN/YELLOW/RED
2. Если RED — стоп, доклад пользователю
3. Если GREEN/YELLOW:
   - Расширить `.env.example` и `config.py` (раздел 4.1)
   - Реализовать `core/vk_oauth.py` (раздел 4.2) + юнит-тесты
   - Реализовать `scripts/get_vk_token.py` (раздел 4.3)
   - Обновить `core/vk_client.py` (раздел 4.4) + интеграционный тест refresh
   - Обновить `routes/api.py` для расширенного `/api/vk/status` (раздел 5.2)
   - Обновить frontend для tooltip серых кнопок при legacy-токене (минимально)
   - Создать `docs/server-deployment-vk.md` (раздел 6)
   - Обновить README с разделом «Шаг A. Настройка приложения VK + получение токена»
   - Прогнать юнит-тесты — все должны проходить
4. **Не публиковать в VK как часть этого задания.** Реальное тестирование — отдельное действие пользователя:
   - Pull request пользователю: «положи client_secret в .env, добавь redirect_uri в настройках VK, запусти `python scripts/get_vk_token.py`, потом протестируй медиа-публикацию»
   - Регрессионный smoke только без участия VK API: `python app.py` стартует, `/api/vk/status` возвращает корректный JSON
5. Отчёт сессии в `docs/sessions/2026-05-XX-vk-oauth.md`:
   - Discovery итоги
   - Что реализовано
   - Что должен сделать пользователь
   - Что отложено на v0.4 (серверный режим)
6. `git tag v0.3.0-rc1` (release candidate, не финал — финал после успешной публикации с медиа)
7. **Не пушить на remote**

## 9. Что НЕ делать

- **Не реализовывать "обходной" путь** через vkhost.github.io или чужие client_id — мы выбрали честный путь
- **Не делать full-on Authorization Code Flow с client_secret в JS** — client_secret НИКОГДА не должен попадать в frontend (он только в .env и в Python)
- **Не менять архитектуру существующих эндпоинтов публикации** — фикс только на уровне клиента, эндпоинты остаются те же
- **Не добавлять refresh_token в логи** — это самый ценный секрет, его утечка даёт долгоживущий доступ к API VK
- **Не апгрейдить зависимости** кроме случая если discovery покажет что нужна новая библиотека (например, `pyjwt` уже есть для JWT — может пригодиться, других не добавлять)
- **Markdown-фикс v0.2.3 не делать в этой сессии** — он отложен; если по дороге нужны изменения промптов под VK ID OAuth — оставить для следующего ТЗ

## 10. Финальный отчёт пользователю

После выполнения:
1. Discovery вердикт (что подтверждено, что нет)
2. Что нужно сделать пользователю — пошагово:
   - В настройках VK-приложения: добавить redirect_uri
   - Скопировать защищённый ключ в .env
   - Запустить `python scripts/get_vk_token.py`
   - Перезапустить `python app.py`
   - Прогнать публикацию с медиа (Kling-картинка → пост в VK)
3. Где найти `docs/server-deployment-vk.md` — для будущего деплоя
4. Где найти `docs/vk-oauth-research.md` — для понимания решений

Конец задания.
