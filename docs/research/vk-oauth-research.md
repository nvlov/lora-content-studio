# VK ID OAuth 2.1 — Discovery research для CLAUDE_CODE_VK_OAUTH_001

**Дата:** 2026-05-10
**Цель:** подтвердить или опровергнуть, что user-токен, полученный через VK ID OAuth 2.1, годится для постинга с медиа в группу-сообщество от имени группы (`wall.post(owner_id=-group_id, from_group=1)` + `photos.getWallUploadServer` + `video.save`).

---

## 1. Источники (ранжировано по достоверности)

| # | Источник | Тип | Чем полезен |
|---|---|---|---|
| 1 | [VKCOM/vkid-android-sdk → AuthOptions.kt](https://github.com/VKCOM/vkid-android-sdk/blob/master/sdk/core/vkid/src/main/java/com/vk/id/internal/auth/AuthOptions.kt) | Источниковый код официального SDK | Точные query-params для `/authorize` |
| 2 | [VKCOM/vkid-android-sdk → InternalVKIDRealApi.kt](https://github.com/VKCOM/vkid-android-sdk/blob/master/sdk/core/network/src/main/kotlin/com/vk/id/network/InternalVKIDRealApi.kt) | Официальный SDK | Точные form-fields для `/oauth2/auth` (exchange + refresh) |
| 3 | [VKCOM/vkid-android-sdk → VkIdNetworkHelper.kt](https://github.com/VKCOM/vkid-android-sdk/blob/master/sample/app/src/main/java/com/vk/id/sample/app/util/VkIdNetworkHelper.kt) | Sample приложения VKCOM | Полный пример HTTP-запроса с парсингом ответа |
| 4 | [VKCOM/vkid-android-sdk → VKIDAuthParams.kt scopes docstring](https://github.com/VKCOM/vkid-android-sdk/blob/master/sdk/core/vkid/src/main/java/com/vk/id/auth/VKIDAuthParams.kt) | Документация SDK | Явная отсылка к [dev.vk.ru/ru/reference/access-rights](https://dev.vk.ru/ru/reference/access-rights) для списка scope strings |
| 5 | [VKCOM/vkid-web-sdk → src/auth/auth.ts](https://github.com/VKCOM/vkid-web-sdk/blob/master/src/auth/auth.ts) | Web SDK подтверждение endpoint-а | Подтверждает `/oauth2/auth` |
| 6 | [VKCOM/vkid-ios-sdk → VKAPI+OAuth2.swift](https://github.com/VKCOM/vkid-ios-sdk/blob/master/VKID/Sources/VKAPI/Namespaces/VKAPI%2BOAuth2.swift) | iOS SDK подтверждение endpoint-а | Подтверждает `/oauth2/auth` |
| 7 | [VKCOM/vk-android-sdk → VKScope.kt](https://github.com/VKCOM/vk-android-sdk/blob/master/core/src/main/java/com/vk/api/sdk/auth/VKScope.kt) | Legacy SDK | Полный enum scope-strings (NOTIFY, FRIENDS, PHOTOS, AUDIO, VIDEO, STORIES, PAGES, STATUS, NOTES, MESSAGES, WALL, ADS, OFFLINE, DOCS, GROUPS, NOTIFICATIONS, STATS, EMAIL, MARKET, PHONE) |
| 8 | [movemoveapp/vkid](https://github.com/movemoveapp/vkid) Laravel Socialite VK ID OAuth 2.1 provider | Сторонний production пакет | Подтверждение что VK ID = OAuth 2.1 + PKCE на `id.vk.ru` |
| 9 | [VKCOM/vk-java-sdk README](https://github.com/VKCOM/vk-java-sdk) | Официальный legacy SDK | Подтверждает классический паттерн `userActor → photos.getWallUploadServer → upload → saveWallPhoto → wall.post(owner_id=-group_id, from_group=1)` |
| 10 | [Alexander Leonov — Automated posting on Vkontakte public pages](https://avleonov.com/2017/07/10/automated-posting-on-vkontakte-public-pages-using-vk-api-and-python/) | Production blog 2017 | Рабочий Python пример `wall.post(from_group=1, owner_id=-149273431)` через user_token |
| 11 | Поисковые сводки (общая картина OAuth 2.1, refresh rotation, PKCE требования) | Косвенные | Потверждают TTL access=24h, обязательное refresh rotation |

Не получилось напрямую открыть ([WebFetch не поддерживает]):
- `https://id.vk.com/about/business/go/docs/...`
- `https://dev.vk.com/ru/reference/access-rights`
— оба домена защищены / не отдают контент через мой WebFetch. Это влияет на пункт 2 (формальное подтверждение списка scope), но косвенные источники (#4 → #7) однозначно говорят, что VK ID использует те же legacy scope strings.

---

## 2. Ответы на 5 пунктов из ТЗ

### 2.1. Эндпоинты VK ID OAuth 2.1

**Источник:** AuthOptions.kt + InternalVKIDRealApi.kt + VkIdNetworkHelper.kt

| Назначение | Метод | URL |
|---|---|---|
| Authorize (browser redirect) | GET | `https://id.vk.ru/authorize` |
| Token exchange / refresh / revoke / logout | POST (form) | `https://id.vk.ru/oauth2/auth` |
| User info | POST (form) | `https://id.vk.ru/oauth2/user_info` |
| Public info по id_token | POST (form) | `https://id.vk.ru/oauth2/public_info` |
| Revoke токена | POST (form) | `https://id.vk.ru/oauth2/revoke` |
| Logout | POST (form) | `https://id.vk.ru/oauth2/logout` |

**Базовый домен:** `id.vk.ru` (единый, без `id.vk.com` варианта в коде SDK; редирект `id.vk.ru` → `id.vk.com/about/id` — это маркетинговая страница, не API)

**API VK для вызова методов:** `https://api.vk.ru/method/<method>?access_token=...&v=5.131` (подтверждено sample-кодом VKID Android SDK; работает и `api.vk.com`).

### 2.2. Authorize-запрос (точные параметры)

Из `AuthOptions.toAuthUriBrowser()`:

```
GET https://id.vk.ru/authorize?
    client_id=<app_id>
   &response_type=code
   &redirect_uri=<url>
   &code_challenge_method=s256          ← НИЖНИЙ РЕГИСТР, не S256
   &code_challenge=<challenge>
   &state=<random>
   &scope=<space-separated-scopes>      ← пробел-сепаратор, не запятая
   &prompt=<optional>
```

Нет `device_id` в authorize-URL. `device_id` появляется ТОЛЬКО в POST на `/oauth2/auth` (см. 2.4).

### 2.3. Scope для постинга с медиа в группу

**Источник:** VKIDAuthParams.kt docstring явно говорит:
> *"You can view the list of available scopes here: https://dev.vk.ru/ru/reference/access-rights"*

То есть VK ID использует **те же legacy scope strings** (это и есть главная находка discovery):

Из VKScope.kt в `vk-android-sdk` (legacy, та же таксономия):
```
NOTIFY, FRIENDS, PHOTOS, AUDIO, VIDEO, STORIES, PAGES, STATUS,
NOTES, MESSAGES, WALL, ADS, OFFLINE, DOCS, GROUPS, NOTIFICATIONS,
STATS, EMAIL, MARKET, PHONE
```

Для нашего сценария (постинг с медиа в группу от имени группы) **нужный набор:**
```
scope = "wall photos video groups offline"
```
(можно добавить `manage` — он часто требуется для управления сообществом, но проверяемо).

`offline` нужен чтобы получить `refresh_token` (наследие от старого VK API, в VK ID 2.1 точно сохранено — судя по тому, что refresh-flow существует).

⚠ **Не подтверждено напрямую (косвенно — да):** что VK ID Self Service на dev.vk.com позволяет приложению запрашивать legacy media-scopes (wall/photos/video). По SDK docstring это так, но конкретное приложение Dr. Nik должно иметь эти scope **разрешёнными в настройках** (Self Service → раздел разрешений). Если запрашивать scope, не разрешённый в Self Service, VK выдаст ошибку или просто проигнорирует.

### 2.4. Token exchange + Refresh

Из `InternalVKIDRealApi.kt`:

**Exchange `code` → `access_token + refresh_token`:**
```
POST https://id.vk.ru/oauth2/auth
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code=<code>
&code_verifier=<verifier>
&client_id=<app_id>
&device_id=<device_id>
&redirect_uri=<redirect>
&state=<UUID>
```

**Ответ:**
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "id_token": "...",
  "user_id": 12345,
  "expires_in": 86400,
  "scope": "wall photos video groups offline"
}
```

**Refresh:**
```
POST https://id.vk.ru/oauth2/auth
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token
&refresh_token=<refresh>
&client_id=<app_id>
&device_id=<device_id>
&state=<UUID>
```

Ответ — той же формы (новый `access_token`, обычно новый `refresh_token` из-за rotation).

**КРИТИЧЕСКОЕ:** `client_secret` НЕ передаётся ни в exchange, ни в refresh. VK ID OAuth 2.1 для Authorization Code Flow + PKCE является **public client flow** — secret не нужен. Это противоречит первоначальной формулировке ТЗ (раздел 4.1, `VK_OAUTH_CLIENT_SECRET=`), но соответствует текущей практике VK.

`client_secret` нужен только для:
- `silent_auth_providers` — не наш кейс (silent auth для нативных мобильных приложений)
- `statEvents.addVKIDAnonymously` — анонимная статистика, не наш кейс

### 2.5. PKCE параметры

- **Алгоритм:** `s256` (lowercase, **не** `S256` как в RFC) — подтверждено `CODE_CHALLENGE_METHOD_VALUE = "s256"`
- **Code verifier:** не указан в SDK явно, но стандарт OAuth 2.1 / RFC 7636 — 43–128 символов, base64url-charset (`[A-Z][a-z][0-9]-._~`), SHA-256(verifier) → base64url-no-padding = challenge
- Проверки длины VK не документированы, идём по RFC

### 2.6. device_id

- Случайный идентификатор устройства/клиента, **обязателен** в form-body POST на `/oauth2/auth` (как в exchange, так и в refresh)
- В Android SDK это `UUID.randomUUID().toString()` (фиксируется один раз для приложения и хранится в SharedPreferences)
- **Для нашего сервера:** генерируем UUID4 один раз при первой авторизации, сохраняем в `.env` как `VK_OAUTH_DEVICE_ID=...`, и используем в каждом refresh-запросе. Если потеряем — VK может не позволить refresh (либо позволит — точно не подтверждено, безопаснее сохранять).

### 2.7. Refresh token

- Точный TTL не документирован публично. Косвенно: «Refresh tokens have intentionally undisclosed expiration» (общий паттерн OAuth 2.0/2.1).
- VK ID OAuth 2.1 заявлен как mandatory rotation: каждый refresh выдаёт **новый refresh_token**, старый инвалидируется. Подтверждено косвенно общим описанием OAuth 2.1.
- Если refresh упал — пользователь должен снова пройти OAuth-flow (новый authorization code flow). Это нормально.

### 2.8. Redirect URI требования

- HTTP допустим только для `http://localhost:*/...` (стандарт OAuth 2.1 для desktop/native apps; VK не публикует точные требования)
- На production HTTPS обязателен (общий стандарт + VK security policy)
- В Self Service на dev.vk.com можно зарегистрировать несколько разрешённых redirect_uri
- Точное совпадение URI обязательно (не префиксное)

---

## 3. Главный вопрос: можно ли user-токеном из VK ID опубликовать пост с медиа в группу от имени группы?

### Прямой эксперимент — невозможен (требует живого VK app + браузера + действия пользователя).

### Косвенные доказательства — ВСЕ положительные:

1. **vkid-android-sdk** официально использует те же legacy scope strings (через docstring → dev.vk.ru/ru/reference/access-rights). Никаких упоминаний "VK ID токен ограничен только email/phone" нет.

2. **VkIdNetworkHelper sample** показывает прямой вызов `api.vk.ru/method/users.get?access_token=...&v=5.131` через VK ID токен. То есть **токен из VK ID работает с обычным VK API** — это и есть наш use case (просто у нас другой method).

3. **Пакет movemoveapp/vkid** для Laravel реализует именно VK ID OAuth 2.1 для production задач — никаких упоминаний что токен непригоден для постинга.

4. **VK Java SDK** документирует pattern `userActor → photos.getWallUploadServer → wall.post(owner_id=-group_id, from_group=1)`. Хотя там OAuth 2.0 endpoints, токен — обычный user access token; в VK ID OAuth 2.1 принципиально тот же тип токена, только flow получения другой.

5. **VKID Android SDK комментарий о "groups" scope:** *"The 'groups' scope will be added automatically to the set of requested scopes"* в OneTap-виджетах — это явное указание, что scope `groups` поддерживается в VK ID OAuth 2.1.

### Возможные причины провала (на которые надо смотреть на этапе тестирования):

- **Self Service VK-приложения** не разрешает media-scopes — Dr. Nik должен в настройках своего приложения на dev.vk.com явно разрешить wall/photos/video/groups в списке "scopes" (если такой раздел есть в новом Self Service)
- VK ID может ограничить scope на уровне UI: пользователю покажут только разрешения которые приложение запросило И которые разрешены
- При попытке `wall.post` от имени группы VK всё равно проверит, что пользователь — админ группы (это known req-нт, у Dr. Nik есть)

---

## 4. Decision gate

# 🟡 YELLOW

**Обоснование:**

- ✅ **Эндпоинты подтверждены** (источниковый код VKCOM SDK)
- ✅ **PKCE параметры подтверждены** (s256, авторизация-флоу)
- ✅ **device_id роль и место подтверждены** (form-body, не URL)
- ✅ **Token exchange + refresh форматы подтверждены** (с примерами кода)
- ✅ **Scope формат подтверждён** (space-separated, legacy strings из dev.vk.ru/reference/access-rights)
- ✅ **client_secret НЕ нужен** (это упрощение vs ТЗ — отличная новость)
- ⚠ **Прямого подтверждения работы media-scope в VK ID нет**, но 5 косвенных позитивных сигналов и ноль противопоказаний
- ⚠ **Зависит от настроек Self Service конкретного приложения Dr. Nik** — это вне scope discovery, но критично для практического запуска

**Что меняется в плане Phase 2 vs ТЗ:**

1. **Убрать `VK_OAUTH_CLIENT_SECRET` из `.env.example` и `config.py`** — VK ID OAuth 2.1 для нашего flow client_secret не использует. Если Dr. Nik по ошибке заполнит — игнорируется (просто не передаём в API).
2. **Добавить `VK_OAUTH_DEVICE_ID` в `.env`** — хранить UUID4, сгенерированный при первой авторизации. Без него refresh может ломаться при VK-рестарте.
3. **Обновить раздел README «Шаг A. Настройки приложения VK»** на актуальный VK Self Service:
   - Добавить redirect URI `http://localhost:8123/callback`
   - В разделе scopes / разрешений: убедиться что разрешены `wall, photos, video, groups, offline` (если такая настройка есть в Self Service — точные имена пунктов сейчас не подтверждены, инструкцию формулирую по факту обнаружения).
4. Все остальные фазы (Phase 3 Backward compat, Phase 4 server-deployment-vk.md, Phase 5 тесты) — без изменений.

## 5. Что осталось проверить только в практике

После реализации Phase 2 — pre-flight для Dr. Nik:
1. Запустить `python scripts/get_vk_token.py` → пройти OAuth → получить токен
2. Распечатать `scope` из ответа: должен содержать `wall photos video groups`. Если содержит только `email phone` — Self Service приложения не разрешает media-scopes, нужно идти в настройки и включить
3. Тестовый ручной вызов `curl https://api.vk.ru/method/wall.post?owner_id=-237689862&from_group=1&message=test&access_token=$TOKEN&v=5.131` — должен пройти (без media сначала, чтобы исключить переменные)
4. Затем тест `photos.getWallUploadServer` + полный пайплайн с медиа
5. Если шаг 2 даёт scope без media — это блокировка на уровне Self Service, **не баг кода**, исправляется в настройках VK-приложения

---

## 6. Решение для пользователя

**Рекомендую: 🟡 YELLOW → продолжать в Phase 2** с тремя оговорками:
1. Убрать client_secret из конфига (упрощение)
2. Добавить device_id в конфиг
3. Чёткая инструкция Dr. Nik после реализации: убедиться что в Self Service VK-приложения media-scope включены, перед тем как запустить `get_vk_token.py`

Если хочешь — могу проверить ещё одно подтверждение перед Phase 2: попробовать через `gh` найти любой публичный пример или integration-тест, где VKID токен реально использовался для wall.post с медиа. Но это удлинит discovery; и YELLOW-сигнала по совокупности уже достаточно для перехода в Phase 2 с пометками о рисках.

Жду твоего «продолжай в Phase 2» (или «копай ещё», если хочешь снять YELLOW до GREEN).
