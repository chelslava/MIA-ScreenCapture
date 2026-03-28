# API

## Swagger

- UI: `http://127.0.0.1:<port>/api/docs`
- OpenAPI JSON: `http://127.0.0.1:<port>/api/swagger.json`

## Аутентификация

Все защищенные эндпоинты требуют заголовок:

`X-API-Key: <token>`

Без токена доступны только служебные endpoints вроде `GET /health`.

## Версионирование

Актуальный контракт:

- `/api/v1/*`

Legacy-совместимость:

- часть эндпоинтов доступна и через `/api/*` (`status/start/stop/pause`).

Рекомендуется использовать только `/api/v1/*`.

## Список основных эндпоинтов v1

- `GET /health`
- `GET /api/v1/status`
- `POST /api/v1/start`
- `POST /api/v1/stop`
- `POST /api/v1/pause`
- `GET /api/v1/recordings`
- `GET /api/v1/devices`
- `GET /api/v1/windows`
- `GET /api/v1/config`
- `PUT /api/v1/config`
- `GET /api/v1/schedule`
- `POST /api/v1/schedule`
- `PUT /api/v1/schedule/{task_id}`
- `DELETE /api/v1/schedule/{task_id}`
- `POST /api/v1/schedule/{task_id}/toggle`
- `GET /api/v1/events/recent?limit=50`
- `GET /api/v1/events/stats`
- `GET /api/v1/observability/metrics`
- `GET /api/v1/observability/baseline`

## Примеры валидных запросов

### 1) Проверка здоровья

```bash
curl http://127.0.0.1:5010/health
```

### 2) Статус записи

```bash
curl -H "X-API-Key: test1234" \
  http://127.0.0.1:5010/api/v1/status
```

### 3) Старт записи

```json
{
  "area": "full",
  "audio": "mic",
  "fps": 30,
  "codec": "libx264",
  "bitrate": "5M",
  "output_path": "D:/Recordings/session_001.mp4",
  "duration": 60
}
```

Важные ограничения:

- `fps`: от `1` до `120`.
- `duration`: либо не передавать, либо `>= 1`.
- Для `area = "window"` обязателен `window_title`.
- Для `area = "rect"` обязателен `rect: [x1, y1, x2, y2]`, где `x2 > x1`, `y2 > y1`.

### 4) Стоп записи

```bash
curl -X POST -H "X-API-Key: test1234" \
  http://127.0.0.1:5010/api/v1/stop
```

### 5) Создание cron-задачи (валидный пример)

```json
{
  "name": "Ежедневная запись",
  "trigger": "cron",
  "cron_expression": "0 10 * * 1-5",
  "params": {
    "area": "full",
    "audio": "none",
    "fps": 30,
    "codec": "libx264",
    "bitrate": "2M"
  }
}
```

Для `trigger = "cron"` не передавайте пустые `datetime`/`time`.

### 6) Создание разовой задачи (once)

```json
{
  "name": "Разовая запись",
  "trigger": "once",
  "datetime": "2026-03-29T10:30:00+03:00",
  "params": {
    "area": "full",
    "audio": "mic",
    "fps": 30
  }
}
```

## Формат ошибок

Ошибка возвращается в едином формате:

```json
{
  "success": false,
  "error": {
    "code": "validation_error",
    "message": "Ошибка валидации данных",
    "details": []
  },
  "trace_id": "..."
}
```

`trace_id` также дублируется в заголовке `X-Request-ID`.
