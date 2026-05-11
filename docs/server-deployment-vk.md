# VK ID OAuth на сервере (v0.4+)

> **Статус:** заготовка для будущего деплоя. Локальный режим v0.3 уже работает.

## Принцип

Авторизацию проходим **на локальной машине** (там где есть браузер) ровно один
раз → получаем `refresh_token` → переносим его и `device_id` на сервер. Сервер
дальше сам рефрешит `access_token` через `refresh_token` без участия пользователя
и без браузера.

VK ID OAuth 2.1 для PKCE-flow — **public client** (без `client_secret`), поэтому
ни одного секретного ключа сервера на стороне VK нет: refresh_token + device_id
+ app_id — это всё, что нужно для server-to-server обновления.

## Шаги

### 1. Получить токены локально

На локальной машине Dr. Nik (там где есть браузер):

```cmd
python scripts/get_vk_token.py
```

Скрипт работает по **manual-paste flow**: открывает браузер на VK ID, ждёт пока
ты вставишь полный URL из адресной строки после редиректа на
`https://oauth.vk.com/blank.html`, обменивает code на пару токенов и записывает
4 ключа в локальный `.env`:

- `VK_OAUTH_DEVICE_ID` (UUID-hex, генерируется при первой авторизации)
- `VK_USER_ACCESS_TOKEN` (живёт 24 часа)
- `VK_USER_REFRESH_TOKEN` (долгоживущий)
- `VK_USER_TOKEN_EXPIRES_AT` (ISO 8601, UTC)

### 2. Перенести на сервер

В `.env` сервера (например, через `scp` или ручное редактирование через SSH):

```
VK_OAUTH_APP_ID=54587420
VK_OAUTH_REDIRECT_URI=https://oauth.vk.com/blank.html
VK_OAUTH_DEVICE_ID=<тот же что и локально>
VK_USER_REFRESH_TOKEN=<скопировать с локали>
VK_USER_ACCESS_TOKEN=          ← можно оставить пустым
VK_USER_TOKEN_EXPIRES_AT=      ← можно оставить пустым

VK_GROUP_ID=237689862
VK_API_VERSION=5.199
```

При первом запросе к VK API на сервере `_ensure_fresh_token()` увидит, что
access_token пустой/истёк, использует `refresh_token` + `device_id` для
обновления, сохранит свежие значения в `.env` сервера и продолжит работу.

### 3. HTTPS на проде

Для самого приложения (если позже добавим браузерный OAuth-flow на сервере)
нужен HTTPS — VK ID не принимает HTTP redirect_uri кроме особых случаев.
Использовать Let's Encrypt + Caddy или nginx + certbot.

В v0.3 на сервере отдельный браузерный flow **не нужен** — токены приходят с
локали и обновляются server-to-server.

## Если refresh_token истёк / инвалидирован

VK ID может инвалидировать refresh_token (точный TTL VK не публикует —
наблюдаемое поведение: rotation при каждом refresh + инвалидация при отзыве
прав пользователем). Когда это случится:

- Приложение упадёт с понятной ошибкой `VKAuthExpiredError`:
  «Не удалось обновить VK access_token: ... Запусти `python scripts/get_vk_token.py`
  для повторной авторизации.»
- Повторить шаг 1 локально, перенести новый `VK_USER_REFRESH_TOKEN` на сервер
  (device_id остаётся тот же).

## Безопасность

- `VK_USER_REFRESH_TOKEN` — самый ценный секрет (даёт долгоживущий доступ к VK
  от лица пользователя). НЕ коммитить, НЕ логировать, держать в `.env` с правами
  600 на сервере.
- `client_secret` для PKCE-flow НЕ используется — нечего утекать.
- `device_id` — не секрет (UUID), но менять его без необходимости не нужно
  (рискуем сломать refresh).
