# Сессия 3 — VK OAuth Phase 1 Discovery

**Дата:** 2026-05-10
**Длительность:** ~30 минут (Claude Code, по `tasks/CLAUDE_CODE_VK_OAUTH_001.md`)
**Версия после сессии:** v0.3.0-rc1 (in progress) — ветка `feat/v0.3-vk-oauth`, не смержена
**Статус:** 🟡 YELLOW — Phase 2 implementation отложен на следующую сессию

---

## Цель сессии
Phase 1 Discovery из `tasks/CLAUDE_CODE_VK_OAUTH_001.md`: web search актуальной документации VK ID OAuth 2.1, ответ на 5 пунктов раздела 3.1 ТЗ, decision gate GREEN/YELLOW/RED. **Никакого кода в Phase 2 не трогать.**

## Что сделано
1. Создана ветка `feat/v0.3-vk-oauth` (от `main`).
2. Серия web-search и `gh search code` запросов: `id.vk.ru` endpoints, PKCE параметры, scope в VK ID, refresh token rotation, device_id роль.
3. Изучены исходники официального VKCOM/vkid-android-sdk: `AuthOptions.kt`, `InternalVKIDRealApi.kt`, `VkIdNetworkHelper.kt`, `VKIDAuthParams.kt`. Из них извлечены точные URL, query/form-параметры и форматы.
4. Изучены косвенные источники: `vkid-web-sdk`, `vkid-ios-sdk`, `vk-android-sdk` (legacy VKScope enum), `movemoveapp/vkid` Laravel пакет, `vk-java-sdk` README.
5. Зафиксировано в `docs/vk-oauth-research.md`: 11 источников, 5 ответов на пункты ТЗ, decision gate с обоснованием.
6. Внесены подтверждённые правки в `tasks/CLAUDE_CODE_VK_OAUTH_001_PHASE2_UPDATES.md` — patch к разделам 4.1–4.5 оригинального ТЗ.

## Вердикт
**🟡 YELLOW — продолжаем в Phase 2 в следующей сессии.**

Все 5 технических пунктов discovery (эндпоинты, PKCE, refresh, device_id, scope формат) подтверждены источниковым кодом VKCOM SDK. Главный вопрос (получится ли user-токеном из VK ID опубликовать пост с медиа в группу от имени группы) подтверждён косвенно — 5 положительных сигналов и 0 противопоказаний; прямого практического подтверждения нет, но это требует живой OAuth-авторизации (вне scope discovery).

## Ключевые открытия (5 строк)
1. **Эндпоинты:** `https://id.vk.ru/authorize` (GET) для browser-redirect, `https://id.vk.ru/oauth2/auth` (POST form) для exchange + refresh + revoke + logout. API VK — `https://api.vk.ru/method/...?v=5.131`.
2. **Scope:** space-separated **legacy strings** (`wall photos video groups offline manage`) — VKID Android SDK явно ссылается на `dev.vk.ru/ru/reference/access-rights`, тот же словарь что у OAuth 2.0.
3. **PKCE:** `code_challenge_method=s256` (нижний регистр, не `S256`); base64url-no-padding(sha256(verifier)).
4. **device_id:** обязателен в каждом form-body POST на `/oauth2/auth` (UUID4, генерируется один раз и сохраняется в `.env` как `VK_OAUTH_DEVICE_ID`).
5. **client_secret НЕ нужен** для Authorization Code Flow + PKCE — это public client flow (упрощение vs первоначальное ТЗ; `getToken()` и `refreshToken()` в исходниках VKCOM SDK его не передают).

## Уточнения от Dr. Nik (ответы на 3 вопроса в конце research)
1. **YELLOW принят**, дополнительный research не нужен.
2. **Упрощения подтверждены:** убрать `VK_OAUTH_CLIENT_SECRET` из `.env.example` и `core/vk_oauth.py`; добавить `VK_OAUTH_DEVICE_ID` (UUID4, persistent в `.env`).
3. **App ID 54586535 — реальный**, использовать в `.env.example` без плейсхолдера.

## Артефакты
- `docs/vk-oauth-research.md` — полный research-файл с 11 источниками, ответами на все 5 пунктов ТЗ, обоснованием YELLOW
- `tasks/CLAUDE_CODE_VK_OAUTH_001_PHASE2_UPDATES.md` — patch к оригинальному ТЗ для следующей сессии
- ветка `feat/v0.3-vk-oauth` — открыта, не смержена в `main`, без тега

## Следующие шаги (Phase 2 — следующая сессия)
1. Открыть ветку `feat/v0.3-vk-oauth`
2. Прочитать `docs/vk-oauth-research.md` + `tasks/CLAUDE_CODE_VK_OAUTH_001_PHASE2_UPDATES.md` + оригинальное `tasks/CLAUDE_CODE_VK_OAUTH_001.md`
3. Идти по Шагам раздела 8 оригинального ТЗ:
   - Расширить `.env.example` и `config.py` (с правками из PHASE2_UPDATES)
   - Реализовать `core/vk_oauth.py` + юнит-тесты
   - Реализовать `scripts/get_vk_token.py` (UUID4 device_id, callback HTTP server)
   - Обновить `core/vk_client.py` для `_ensure_fresh_token()` + интеграционный тест с моком refresh
   - Расширить `/api/vk/status` (`token_source`, `media_publish_supported`)
   - Создать `docs/server-deployment-vk.md`
   - Обновить README с разделом «Шаг A»
4. Тег `v0.3.0-rc1` ставится **только после успешной OAuth-авторизации в реальности** (Dr. Nik пройдёт OAuth-flow и медиа-публикация B/C/D из vk-launch-001 наконец заработает) — не в Phase 2 сразу.

## Расходы AI за сессию
~10 web-search вызовов + ~6 web-fetch + ~5 `gh search code`/`gh api`. Расходов Claude/Kling/VK от лица приложения — 0 (никаких прогонов кода, никаких вызовов внешних API кроме research).
