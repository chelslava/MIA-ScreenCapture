# MIA ScreenCapture REST API

REST API для удалённого управления录окомом экрана и приложением MIA ScreenCapture. API предоставляет полный контроль над записью видео, планированием задач и управлением конфигурацией.

## Оглавление

- [Аутентификация](#аутентификация)
- [Базовая информация](#базовая-информация)
- [Формат ошибок](#формат-ошибок)
- [Endpoints](#endpoints)
  - [Health Check](#health-check)
  - [Запись](#запись)
  - [Планировщик](#планировщик)
  - [Конфигурация](#конфигурация)
  - [Ресурсы окружения](#ресурсы-окружения)
  - [Observability](#observability)

---

## Аутентификация

Все API endpoints (кроме `/health`) требуют API Key аутентификацию через заголовок `X-API-Key`.

### Получение API Key

API Key генерируется автоматически при первом запуске приложения. Вы можете:

1. **Найти в переменной окружения** `MIA_API_KEY`
2. **Посмотреть в Windows Credential Manager** (целевое имя: `MIA-ScreenCapture/APIKey`)
3. **Увидеть в логах приложения** при запуске (показывается маскированный вид)

### Использование API Key

Передайте ключ в заголовке всех запросов:

```bash
curl -H "X-API-Key: your-api-key-here" http://localhost:5000/api/v1/status
```

---

## Базовая информация

### URL базы API

```
http://localhost:5000
```

Порт по умолчанию: **5000**. API версия: **v1** (эндпоинты доступны по пути `/api/v1`).

### Версия и статус сервера

Все ответы включают `X-Request-ID` заголовок для tracing запросов.

---

## Формат ошибок

Все ошибки возвращаются в единообразном формате JSON:

```json
{
  "success": false,
  "error": {
    "code": "validation_error",
    "message": "Ошибка валидации данных",
    "details": [
      {
        "field": "fps",
        "message": "ensure this value is less than or equal to 120",
        "type": "value_error.number.not_le"
      }
    ]
  },
  "trace_id": "abc123..."
}
```

### Коды ошибок

| Код | HTTP | Описание |
|-----|------|---------|
| `bad_request` | 400 | Некорректный JSON или синтаксис |
| `validation_error` | 400 | Ошибка валидации данных |
| `unauthorized` | 401 | Отсутствует или неверный API Key |
| `forbidden` | 403 | Доступ запрещён |
| `not_found` | 404 | Ресурс не найден |
| `conflict` | 409 | Конфликт (например, idempotency конфликт) |
| `payload_too_large` | 413 | Размер запроса превышает максимум (1 MB) |
| `rate_limited` | 429 | Превышен лимит запросов |
| `internal_error` | 500 | Внутренняя ошибка сервера |

---

## Endpoints

### Health Check

#### `GET /health`

Проверка здоровья и статуса API сервера. **Не требует аутентификации**.

**Response 200:**
```json
{
  "status": "ok",
  "timestamp": "2024-03-15T10:30:45.123456+00:00",
  "version": "1.0.0",
  "uptime_seconds": 3600.5,
  "websocket": {
    "transport_ready": true,
    "active_connections": 2,
    "total_events": 150
  }
}
```

**Example:**
```bash
curl http://localhost:5000/health
```

---

### Запись

#### `GET /api/v1/status`

Получение текущего статуса записи. Эта операция не требует тело запроса.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "is_recording": true,
    "is_paused": false,
    "elapsed_time": 45.3,
    "current_file": "C:\\Recordings\\2024-03-15_10-30-45.mp4",
    "frame_count": 1359
  }
}
```

**Example:**
```bash
curl -H "X-API-Key: your-api-key" http://localhost:5000/api/v1/status
```

---

#### `POST /api/v1/start`

Начало новой записи.

**Request Body:**
```json
{
  "area": "full",
  "window_title": null,
  "rect": null,
  "audio": "none",
  "output_path": null,
  "fps": 30,
  "codec": "libx264",
  "bitrate": "2M",
  "duration": null,
  "mic_device": null
}
```

**Параметры:**

| Поле | Тип | По умолч. | Описание |
|------|-----|----------|---------|
| `area` | string | "full" | Область захвата: `full`, `window`, `rect` |
| `window_title` | string | null | Заголовок окна (требуется если `area="window"`) |
| `rect` | array | null | Координаты `[x1, y1, x2, y2]` (требуется если `area="rect"`) |
| `audio` | string | "none" | Источник аудио: `mic`, `system`, `none`, `both` |
| `output_path` | string | null | Путь для сохранения файла |
| `fps` | number | 30 | Кадров в секунду (1-120) |
| `codec` | string | "libx264" | Видеокодек |
| `bitrate` | string | "2M" | Битрейт видео (примеры: `2M`, `5000K`, `2000000`) |
| `duration` | number | null | Длительность в секундах (опционально) |
| `mic_device` | number | null | Индекс устройства микрофона |

**Response 200:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "message": "Recording started",
    "file_path": "C:\\Recordings\\2024-03-15_10-30-45.mp4"
  }
}
```

**Response 400 (Validation Error):**
```json
{
  "success": false,
  "error": {
    "code": "validation_error",
    "message": "Ошибка валидации данных",
    "details": [
      {
        "field": "rect",
        "message": "rect должен содержать ровно 4 значения: [x1, y1, x2, y2]",
        "type": "value_error"
      }
    ]
  },
  "trace_id": "xyz789"
}
```

**Examples:**

Запись полного экрана без звука:
```bash
curl -X POST \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "area": "full",
    "audio": "none",
    "fps": 30,
    "codec": "libx264",
    "bitrate": "2M"
  }' \
  http://localhost:5000/api/v1/start
```

Запись определённого окна с микрофоном:
```bash
curl -X POST \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "area": "window",
    "window_title": "Visual Studio Code",
    "audio": "mic",
    "fps": 60,
    "bitrate": "5M"
  }' \
  http://localhost:5000/api/v1/start
```

Запись прямоугольной области:
```bash
curl -X POST \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "area": "rect",
    "rect": [100, 200, 1000, 800],
    "audio": "both",
    "fps": 30,
    "bitrate": "3M"
  }' \
  http://localhost:5000/api/v1/start
```

---

#### `POST /api/v1/stop`

Остановка текущей записи.

**Request Body:** Пусто

**Response 200:**
```json
{
  "success": true,
  "data": {
    "operation_id": "op-123456",
    "status": "completed",
    "file_path": "C:\\Recordings\\2024-03-15_10-30-45.mp4",
    "duration_seconds": 45.3,
    "frame_count": 1359
  }
}
```

**Response 202 (In Progress):**
Если остановка занимает время, вернётся статус операции:
```json
{
  "success": true,
  "data": {
    "operation_id": "op-123456",
    "status": "running"
  }
}
```

Затем можно проверить статус через `GET /api/v1/operations/{operation_id}`.

**Example:**
```bash
curl -X POST \
  -H "X-API-Key: your-api-key" \
  http://localhost:5000/api/v1/stop
```

---

#### `POST /api/v1/pause`

Пауза или возобновление текущей записи.

**Request Body:** Пусто

**Response 200:**
```json
{
  "success": true,
  "data": {
    "is_paused": true,
    "message": "Recording paused"
  }
}
```

**Example:**
```bash
curl -X POST \
  -H "X-API-Key: your-api-key" \
  http://localhost:5000/api/v1/pause
```

---

#### `GET /api/v1/recordings`

Получение списка недавних записей.

**Query Parameters:**

| Параметр | Тип | Описание |
|----------|-----|---------|
| (нет) | - | - |

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "file_path": "C:\\Recordings\\2024-03-15_10-30-45.mp4",
      "duration": 45.3,
      "frame_count": 1359,
      "created_at": "2024-03-15T10:30:45+00:00",
      "size_bytes": 123456789
    }
  ]
}
```

**Example:**
```bash
curl -H "X-API-Key: your-api-key" http://localhost:5000/api/v1/recordings
```

---

#### `GET /api/v1/events/recent`

Получение недавних real-time событий записи.

**Query Parameters:**

| Параметр | Тип | По умолч. | Описание |
|----------|-----|----------|---------|
| `limit` | number | 50 | Максимальное количество событий |

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "timestamp": "2024-03-15T10:30:45.123456+00:00",
      "event_type": "frame_captured",
      "frame_number": 1357,
      "details": {
        "duration_ms": 33.5
      }
    },
    {
      "timestamp": "2024-03-15T10:30:45.090000+00:00",
      "event_type": "recording_started",
      "details": {
        "area": "full",
        "codec": "libx264"
      }
    }
  ]
}
```

**Example:**
```bash
curl -H "X-API-Key: your-api-key" "http://localhost:5000/api/v1/events/recent?limit=20"
```

---

#### `GET /api/v1/events/stats`

Получение статистики event-менеджера.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "transport_ready": true,
    "active_connections": 2,
    "total_events": 5647,
    "event_buffer_size": 50
  }
}
```

**Example:**
```bash
curl -H "X-API-Key: your-api-key" http://localhost:5000/api/v1/events/stats
```

---

### Планировщик

#### `GET /api/v1/schedule`

Получение списка запланированных задач.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "id": "task-123",
      "name": "Daily standup",
      "trigger": "daily",
      "time": "09:00",
      "enabled": true,
      "params": {
        "area": "window",
        "window_title": "Zoom",
        "audio": "both",
        "fps": 30,
        "codec": "libx264",
        "bitrate": "2M"
      },
      "created_at": "2024-03-15T10:30:45+00:00"
    }
  ]
}
```

**Example:**
```bash
curl -H "X-API-Key: your-api-key" http://localhost:5000/api/v1/schedule
```

---

#### `POST /api/v1/schedule`

Создание новой запланированной задачи.

**Request Body:**
```json
{
  "name": "Daily standup",
  "trigger": "daily",
  "time": "09:00",
  "day_of_week": null,
  "datetime": null,
  "hours": null,
  "minutes": null,
  "cron_expression": null,
  "params": {
    "area": "window",
    "window_title": "Zoom",
    "audio": "both",
    "fps": 30,
    "codec": "libx264",
    "bitrate": "2M"
  }
}
```

**Параметры:**

| Поле | Тип | Обязателен | Описание |
|------|-----|-----------|---------|
| `name` | string | Да | Название задачи (1-100 символов) |
| `trigger` | string | Да | Тип расписания: `once`, `daily`, `weekly`, `interval`, `cron` |
| `datetime` | string | Для `once` | ISO формат (например: `2024-03-20T14:30:00`) |
| `time` | string | Для `daily`, `weekly` | Время в формате `HH:MM` |
| `day_of_week` | string | Для `weekly` | Дни недели через запятую (0=Пн, 6=Вс), например `0,2,4` |
| `hours` | number | Для `interval` | Часы (0-168) |
| `minutes` | number | Для `interval` | Минуты (0-59) |
| `cron_expression` | string | Для `cron` | Cron выражение (5 полей: минута час день месяц день_недели) |
| `params` | object | Нет | Параметры записи (см. `/api/v1/recording/start`) |

**Response 201:**
```json
{
  "success": true,
  "data": {
    "id": "task-123",
    "name": "Daily standup",
    "trigger": "daily",
    "time": "09:00",
    "enabled": true,
    "created_at": "2024-03-15T10:30:45+00:00"
  }
}
```

**Examples:**

Создание разовой задачи:
```bash
curl -X POST \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "One-time recording",
    "trigger": "once",
    "datetime": "2024-03-20T14:30:00",
    "params": {
      "area": "full",
      "audio": "none",
      "fps": 30,
      "bitrate": "2M"
    }
  }' \
  http://localhost:5000/api/v1/schedule
```

Создание ежедневной задачи:
```bash
curl -X POST \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Daily standup",
    "trigger": "daily",
    "time": "09:00",
    "params": {
      "area": "window",
      "window_title": "Zoom",
      "audio": "both",
      "fps": 30,
      "bitrate": "2M"
    }
  }' \
  http://localhost:5000/api/v1/schedule
```

Создание еженедельной задачи:
```bash
curl -X POST \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Weekly team meeting",
    "trigger": "weekly",
    "time": "10:00",
    "day_of_week": "0,2,4",
    "params": {
      "area": "full",
      "audio": "both",
      "fps": 24,
      "bitrate": "3M"
    }
  }' \
  http://localhost:5000/api/v1/schedule
```

Создание периодической задачи каждые 2 часа:
```bash
curl -X POST \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Every 2 hours",
    "trigger": "interval",
    "hours": 2,
    "minutes": 0,
    "params": {
      "area": "full",
      "audio": "none",
      "fps": 30,
      "bitrate": "2M"
    }
  }' \
  http://localhost:5000/api/v1/schedule
```

Создание задачи по Cron выражению (в 9:00 по будням):
```bash
curl -X POST \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Weekday mornings",
    "trigger": "cron",
    "cron_expression": "0 9 * * 1-5",
    "params": {
      "area": "full",
      "audio": "mic",
      "fps": 30,
      "bitrate": "2M"
    }
  }' \
  http://localhost:5000/api/v1/schedule
```

---

#### `PUT /api/v1/schedule/<task_id>`

Обновление запланированной задачи.

**Request Body:**
```json
{
  "id": "task-123",
  "name": "Updated name",
  "enabled": true,
  "time": "10:00",
  "day_of_week": "0,2,4",
  "params": {
    "fps": 60,
    "bitrate": "5M"
  }
}
```

**Параметры:** Только те поля, которые нужно обновить.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "task-123",
    "name": "Updated name",
    "time": "10:00",
    "enabled": true,
    "updated_at": "2024-03-15T10:35:45+00:00"
  }
}
```

**Example:**
```bash
curl -X PUT \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "task-123",
    "time": "10:00",
    "params": {
      "fps": 60
    }
  }' \
  http://localhost:5000/api/v1/schedule/task-123
```

---

#### `DELETE /api/v1/schedule/<task_id>`

Удаление запланированной задачи.

**Request Body:** Пусто

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "task-123",
    "message": "Task deleted"
  }
}
```

**Example:**
```bash
curl -X DELETE \
  -H "X-API-Key: your-api-key" \
  http://localhost:5000/api/v1/schedule/task-123
```

---

#### `POST /api/v1/schedule/<task_id>/toggle`

Включение или отключение задачи.

**Request Body:**
```json
{
  "enabled": false
}
```

**Response 200:**
```json
{
  "success": true,
  "data": {
    "id": "task-123",
    "enabled": false
  }
}
```

**Example:**
```bash
curl -X POST \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}' \
  http://localhost:5000/api/v1/schedule/task-123/toggle
```

---

### Конфигурация

#### `GET /api/v1/config`

Получение текущей конфигурации приложения.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "video": {
      "fps": 30,
      "codec": "libx264",
      "bitrate": "2M"
    },
    "audio": {
      "record_mic": true,
      "record_system": false
    },
    "output": {
      "default_path": "C:\\Recordings",
      "filename_template": "{date}_{time}.mp4"
    },
    "app": {
      "minimize_to_tray": true,
      "show_notifications": true,
      "language": "ru"
    }
  }
}
```

**Example:**
```bash
curl -H "X-API-Key: your-api-key" http://localhost:5000/api/v1/config
```

---

#### `PUT /api/v1/config`

Обновление конфигурации приложения.

**Request Body:**
```json
{
  "fps": 60,
  "codec": "h264",
  "bitrate": "5M",
  "record_mic": true,
  "record_system": true,
  "default_path": "D:\\Videos",
  "filename_template": "{date}_{time}_{title}.mp4",
  "minimize_to_tray": false,
  "show_notifications": true,
  "language": "en"
}
```

**Параметры:** Передайте только те, которые нужно изменить.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "video": {
      "fps": 60,
      "codec": "h264",
      "bitrate": "5M"
    },
    "audio": {
      "record_mic": true,
      "record_system": true
    },
    "output": {
      "default_path": "D:\\Videos",
      "filename_template": "{date}_{time}_{title}.mp4"
    },
    "app": {
      "minimize_to_tray": false,
      "show_notifications": true,
      "language": "en"
    }
  }
}
```

**Examples:**

Обновление видео параметров:
```bash
curl -X PUT \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "fps": 60,
    "bitrate": "5M"
  }' \
  http://localhost:5000/api/v1/config
```

Обновление пути вывода:
```bash
curl -X PUT \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "default_path": "D:\\Videos",
    "filename_template": "{date}_{time}.mp4"
  }' \
  http://localhost:5000/api/v1/config
```

---

### Ресурсы окружения

#### `GET /api/v1/devices`

Получение списка доступных аудиоустройств.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "name": "Microphone (Realtek High Definition)",
      "index": 0,
      "channels": 2
    },
    {
      "name": "Stereo Mix (Realtek High Definition)",
      "index": 1,
      "channels": 2
    }
  ]
}
```

**Example:**
```bash
curl -H "X-API-Key: your-api-key" http://localhost:5000/api/v1/devices
```

---

#### `GET /api/v1/windows`

Получение списка доступных окон для захвата.

**Response 200:**
```json
{
  "success": true,
  "data": [
    {
      "title": "Visual Studio Code",
      "x": 0,
      "y": 0,
      "width": 1920,
      "height": 1080
    },
    {
      "title": "Google Chrome",
      "x": 100,
      "y": 100,
      "width": 1000,
      "height": 800
    }
  ]
}
```

**Example:**
```bash
curl -H "X-API-Key: your-api-key" http://localhost:5000/api/v1/windows
```

---

### Observability

#### `GET /api/v1/observability/metrics`

Получение эксплуатационных метрик API.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "http_requests_total": 12345,
    "http_request_duration_seconds": {
      "min": 0.001,
      "max": 5.234,
      "avg": 0.123
    },
    "http_errors_total": 45,
    "idempotency_store_size": 128,
    "background_operations": {
      "total_submitted": 567,
      "currently_running": 2,
      "completed_successfully": 560,
      "failed": 5
    }
  }
}
```

**Example:**
```bash
curl -H "X-API-Key: your-api-key" http://localhost:5000/api/v1/observability/metrics
```

---

#### `GET /api/v1/observability/baseline`

Получение baseline SLO по текущим эксплуатационным метрикам.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "target_availability": 0.99,
    "target_p99_latency_ms": 500,
    "target_error_rate": 0.01,
    "current_availability": 0.9995,
    "current_p99_latency_ms": 234,
    "current_error_rate": 0.0036
  }
}
```

**Example:**
```bash
curl -H "X-API-Key: your-api-key" http://localhost:5000/api/v1/observability/baseline
```

---

### Операции

#### `GET /api/v1/operations/<operation_id>`

Получение статуса фоновой операции.

**Response 200:**
```json
{
  "success": true,
  "data": {
    "operation_id": "op-123456",
    "status": "completed",
    "request_id": "req-789",
    "trace_id": "trace-abc",
    "created_at": "2024-03-15T10:30:45+00:00",
    "completed_at": "2024-03-15T10:31:05+00:00",
    "result": {
      "file_path": "C:\\Recordings\\2024-03-15_10-30-45.mp4",
      "duration": 20.5
    }
  }
}
```

**Example:**
```bash
curl -H "X-API-Key: your-api-key" http://localhost:5000/api/v1/operations/op-123456
```

---

## Идемпотентность

Для write-операций (POST, PUT, DELETE) поддерживается идемпотентность через заголовок `Idempotency-Key`:

```bash
curl -X POST \
  -H "X-API-Key: your-api-key" \
  -H "Idempotency-Key: unique-request-id-12345" \
  -H "Content-Type: application/json" \
  -d '{"area": "full", "audio": "none"}' \
  http://localhost:5000/api/v1/start
```

Если повторить запрос с тем же `Idempotency-Key`, вернётся кэшированный результат первого запроса.

---

## Legacy API (для обратной совместимости)

Поддерживаются следующие legacy endpoints:

- `GET /api/status` — то же самое что `/api/v1/status`
- `POST /api/start` — то же самое что `/api/v1/start`
- `POST /api/stop` — то же самое что `/api/v1/stop`
- `POST /api/pause` — то же самое что `/api/v1/pause`

Рекомендуется использовать новые endpoints `/api/v1/...`.

---

## Rate Limiting

Write-операции (POST, PUT, DELETE) подвергаются rate limiting. При превышении лимита вернётся:

**Response 429:**
```json
{
  "success": false,
  "error": {
    "code": "rate_limited",
    "message": "Слишком много запросов",
    "details": {
      "retry_after_seconds": 60
    }
  }
}
```

---

## WebSocket поддержка

API поддерживает real-time уведомления через WebSocket на адресе `/ws`.

Аутентификация: передайте `?token=YOUR_API_KEY` в URL подключения:

```javascript
const ws = new WebSocket('ws://localhost:5000/ws?token=your-api-key');
ws.onmessage = (event) => {
  const event_data = JSON.parse(event.data);
  console.log('Event:', event_data);
};
```

---

## Примеры интеграции

### Python

```python
import requests

API_KEY = "your-api-key"
BASE_URL = "http://localhost:5000"

headers = {"X-API-Key": API_KEY}

# Запуск записи
response = requests.post(
    f"{BASE_URL}/api/v1/recording/start",
    headers=headers,
    json={
        "area": "full",
        "audio": "none",
        "fps": 30,
        "bitrate": "2M"
    }
)
print(response.json())

# Получение статуса
response = requests.get(f"{BASE_URL}/api/v1/status", headers=headers)
print(response.json())

# Остановка записи
response = requests.post(f"{BASE_URL}/api/v1/recording/stop", headers=headers)
print(response.json())
```

### JavaScript/Node.js

```javascript
const API_KEY = "your-api-key";
const BASE_URL = "http://localhost:5000";

const headers = {
  "X-API-Key": API_KEY,
  "Content-Type": "application/json"
};

// Запуск записи
const startRecording = async () => {
  const response = await fetch(`${BASE_URL}/api/v1/recording/start`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      area: "full",
      audio: "none",
      fps: 30,
      bitrate: "2M"
    })
  });
  return response.json();
};

// Получение статуса
const getStatus = async () => {
  const response = await fetch(`${BASE_URL}/api/v1/status`, { headers });
  return response.json();
};

// Остановка записи
const stopRecording = async () => {
  const response = await fetch(`${BASE_URL}/api/v1/recording/stop`, {
    method: "POST",
    headers
  });
  return response.json();
};

startRecording().then(console.log);
```

---

## Поддержка и отладка

- **Заголовок `X-Request-ID`**: Каждый ответ включает уникальный ID для отладки и логирования.
- **Логи приложения**: Все API запросы логируются. Проверьте логи для подробной информации об ошибках.
- **Swagger документация**: Доступна на `/swagger` для интерактивного тестирования (если включена).

---

Последнее обновление: 2024-03-15
