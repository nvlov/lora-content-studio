# core/analytics/ — аналитика публикаций

Пустой пакет под перспективу. Запланирован после стабилизации автопостинга.

## Зачем

Понимать какие посты «зашли», какие нет — иначе генерация остаётся слепой. С шкалой оценок −2..+2 (v0.3.3) у нас есть subjective rating от Dr. Nik. Аналитика добавляет объективные метрики из соцсети.

## Что собирать

### VK (доступно через token, который уже есть)

- `wall.getById` — count: likes/reposts/comments/views
- `stats.get` (требует доп. права) — охваты по дням
- `wall.getComments` — текст комментариев (sentiment анализом потом)

Лимиты: 3 запроса/сек на токен, batch по 100 постов через `wall.getById` с list owner_id+post_id.

### Telegram (после подключения)

- `getChatMember` для статистики канала
- В Bot API статистика канала ограничена; для серьёзной аналитики нужен бот-админ + `getChat` + ручной парсинг

### YouTube / TikTok (после OAuth)

- YouTube Analytics API
- TikTok Display API

## Структура (планируется)

```
core/analytics/
  vk.py            # сборщик метрик из VK API
  telegram.py      # из Telegram Bot API
  aggregator.py    # сведение в data/exports/
  scheduler_hook.py  # запуск раз в день/час через APScheduler
```

## Связь с другими модулями

- Источник `post_id`/`post_url`: таблица `posts` в `core/storage/models.py` (поля `vk_post_id`, в будущем `telegram_post_id` и т.д.)
- Результат: новая таблица `post_metrics` (post_id, platform, snapshot_at, likes, reposts, comments, views) или JSON-файлы в `data/exports/metrics-YYYY-MM-DD.json`
