# Сессия 4 — VK OAuth: завершение через community-token workaround

**Дата:** 2026-05-11
**Длительность:** ~3 часа (Claude Code, объединение `vk-oauth-002` / `004` диагностики + реализация workaround)
**Версия после сессии:** **v0.3.0** (без `-rc`, медиа-публикация подтверждена в реальности)
**Статус:** ✅ GREEN-via-workaround — фото-публикация работает; видео признано non-feasible (платформенное ограничение VK)

---

## Цель сессии

Закрыть v0.3 — добиться рабочей медиа-публикации в VK-сообщество. Phase 1-2 (`vk-oauth-001`) дали полную OAuth 2.1 инфраструктуру, но `vk-oauth-002` / `004` диагностика показала, что VK с 2025 года не выдаёт scope `wall`/`photos`/`video` третьим лицам через VK ID OAuth ни при какой верификации (политика «extended API access no longer issued» — официальный ответ поддержки VK, подтверждено независимыми источниками).

## Что выяснили в диагностике (vk-oauth-002 → 003 → 004)

1. **Старое приложение `54586535`** (мини-приложение, физлицо) — даёт scope только `vkid.personal_info`. Тупик.
2. **Новое Web-приложение `54587420`** в профиле физлица — тот же scope `vkid.personal_info`. Тупик.
3. **Новое Web-приложение `54587881`** в **подтверждённом профиле самозанятого** (бизнес-верификация пройдена) — на странице авторизации VK ID показывает только «Общая информация», расширенные scope не запрашиваются. Тупик.
4. **Документация id.vk.ru** прямо говорит: расширенные scope «доступны в исключительных случаях», только через `devsupport@corp.vk.com`.
5. **Ответ поддержки VK** (зафиксирован на vc.ru): «Из-за изменения политики дистрибуции API-методов расширенные API-доступы больше не выдаются».

Вывод: **VK ID OAuth 2.1 как путь к media-scope мёртв для новых приложений**. Это не баг и не недонастройка — это политика платформы.

## Что нашли как workaround

Существующий **community-token** сообщества (создан через `vk.com/lora_ai_english?act=tokens` с правами «управление, фотографии, файлы, истории, стена») умеет вызывать `photos.getMessagesUploadServer(group_id=...)` — формально это метод для прикрепления фото к личным сообщениям сообщества, но **результирующий photo-attachment корректно прикрепляется к `wall.post`** (известный обход для community-токенов).

**Smoke-test:** реальное фото опубликовано в `vk.com/wall-237689862_4` (удалено вручную после теста).

| Метод | Community-token | OAuth user-token |
|---|---|---|
| `wall.post` (текст) | ✅ работает с v0.2 | ✅ (если бы был с wall scope) |
| `photos.getWallUploadServer` | ❌ code 27 | ✅ (если бы был с photos scope) |
| **`photos.getMessagesUploadServer`** | ✅ **работает** | ✅ |
| `photos.saveMessagesPhoto` | ✅ работает | ✅ |
| `video.save` | ❌ code 27 (lim. VK API) | ✅ (если бы был с video scope) |

## Что реализовано в коде

1. **`core/vk_client.py` `upload_photo()`** — переписан на `photos.getMessagesUploadServer` + `photos.saveMessagesPhoto`. Работает с community-токеном.
2. **`core/vk_client.py` `upload_video()`** — early-return с понятной ошибкой при `token_source == "legacy_community"` (до похода в VK), чтобы UI сразу показал «загрузи видео руками».
3. **`media_publish_supported()`** теперь True и для `legacy_community` (фото работают), **`video_publish_supported()`** — новый флаг, True только для `oauth_user`.
4. **`/api/vk/status`** отдаёт оба флага (`media_publish_supported`, `video_publish_supported`) — фронт может различать «фото можно, видео нельзя».
5. **OAuth-инфраструктура Phase 2 оставлена в коде как «спящая заготовка»** — если VK когда-нибудь снова откроет media scopes, переключение тривиальное (заполнил `VK_USER_ACCESS_TOKEN/REFRESH/DEVICE_ID` → код пойдёт через старый `photos.getWallUploadServer`).

## Тесты

- 20/20 юнит-тестов в `tests/test_vk_oauth.py` зелёные.
- Один live smoke-test в группу `lora_ai_english`: upload + post + delete вручную.

## Что в backlog (НЕ блокеры)

1. **Видео-публикация в группу** — недоступна для community-токенов на уровне VK API (code 27 на `video.save` — задокументированный лимит платформы). Решение: ручная загрузка в VK Studio после публикации текстового поста.
2. **Markdown-фикс v0.2.3** — звёздочки в LLM-выводе по-прежнему не чистятся. Отложен.
3. **VK ID OAuth** — если VK сменит политику и снова начнёт выдавать media scopes, наш Phase 2 код «оживёт» сам. Никаких отдельных задач не нужно.

## Артефакты

- `core/vk_client.py` — `upload_photo` через messages-upload-server, `upload_video` с early-return
- `routes/api.py` — `/api/vk/status` отдаёт `video_publish_supported`
- `tests/test_vk_oauth.py` — обновлён ассерт по `media_publish_supported`
- эта сессия: `docs/sessions/2026-05-11-vk-oauth-complete.md`
- ветка `feat/v0.3-vk-oauth` смержена в `main` через `--no-ff`
- тег `v0.3.0` (без `-rc`)
- **НЕ запушено на remote** — по правилам проекта

## Расходы AI за сессию

~25 web-search и web-fetch вызовов (доку id.vk.ru, ответы поддержки VK через сторонние источники), ~10 запусков диагностических Python-скриптов с реальными API VK (read-only пробы), 1 реальная VK-публикация (smoke-test, удалена). Расходов на Claude/Kling — 0.
