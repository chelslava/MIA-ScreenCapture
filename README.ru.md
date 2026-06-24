<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/logo-dark.png">
  <img src="docs/assets/logo-light.png" alt="MIA-ScreenCapture" width="480">
</picture>

# MIA-ScreenCapture v1.4.9

**Профессиональная программа для записи экрана на Windows — GUI, REST API, WebSocket, планировщик и CLI в одном инструменте.**

[🇬🇧 English](README.md) · [🇷🇺 Русский](README.ru.md)

[![CI](https://github.com/chelslava/MIA-ScreenCapture/actions/workflows/ci.yml/badge.svg)](https://github.com/chelslava/MIA-ScreenCapture/actions/workflows/ci.yml)
[![Version](https://img.shields.io/github/v/tag/chelslava/MIA-ScreenCapture?label=version&sort=semver)](https://github.com/chelslava/MIA-ScreenCapture/tags)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D6)](https://learn.microsoft.com/en-us/windows/win32/winrt/windows-graphics-capture)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

</div>

---

> ⚠️ **Платформа: только Windows 10/11** — проект использует Windows Graphics Capture API.

## Содержание

- [Возможности](#возможности)
- [Требования](#требования)
- [Установка](#установка)
- [Быстрый старт](#быстрый-старт)
- [Справочник CLI](#справочник-cli)
- [REST API](#rest-api)
- [Архитектура](#архитектура)
- [Конфигурация](#конфигурация)
- [Разработка](#разработка)
- [Решение проблем](#решение-проблем)
- [Известные ограничения](#известные-ограничения)
- [Лицензия](#лицензия)

## Возможности

### 🎥 Захват
- Весь экран, конкретное окно или прямоугольная область — через **Windows Graphics Capture API**
- **Одновременная запись с нескольких мониторов** — отдельный независимый файл на каждый монитор
- **Горячее переключение источника захвата** прямо во время записи, без остановки и потери кадров
- Настраиваемая частота кадров (1–120 FPS)

### 🔊 Звук
- Микрофон, системный звук (loopback), оба источника или без звука
- Выбор устройства через `sounddevice`

### 🛡️ Надёжность
- Автоматическое **восстановление после краша**: при падении процесса FFmpeg запись продолжается в новый сегмент (до 3 попыток) вместо потери данных
- Лимиты на размер/длительность сегмента с автоматической ротацией в новый файл
- **Мониторинг свободного места на диске** с плавной автоостановкой до того, как диск заполнится
- **Верификация целостности видео после записи** и автоматическое восстановление через FFmpeg/`ffprobe`
- Политика повторных попыток с экспоненциальной задержкой для FFmpeg writer'а
- **Защита от повторного запуска** — при попытке запустить второй экземпляр на передний план выводится окно уже работающего приложения вместо конфликта за сессию захвата

### 🖥️ GUI (PyQt6)
- Вкладки: Захват, Аудио, Видео, Вывод, API, Планировщик, Диагностика
- Иконка в системном трее, глобальные горячие клавиши, навигация с клавиатуры
- Чек-лист готовности перед стартом записи (FFmpeg, путь вывода, окно, микрофон)
- Централизованный слой темизации и accessibility-метаданные на ключевых элементах
- Плавающий индикатор активной области записи прямо на экране

### 🌐 REST API (Flask + Waitress)
- Версионированные маршруты `/api/v1/*` (legacy `/api/*` сохранены для обратной совместимости)
- Аутентификация по API-ключу (заголовок `X-API-Key` или `Authorization: Bearer`)
- Поддержка `Idempotency-Key` для безопасных повторов POST-запросов
- Sliding-window rate limiting и circuit breaker вокруг операций захвата
- Единый формат ошибок с `trace_id` / `X-Request-ID`
- Интерактивная документация **Swagger UI** на `/api/docs`
- Эндпоинты observability: метрики запросов и SLO baseline

### 📡 WebSocket и вебхуки
- `ws://host:port/ws` — события `recording` / `system` / `api` / `metrics` в реальном времени, с heartbeat и автопереподключением
- **HMAC-подписанные вебхуки** для уведомлений о жизненном цикле записи

### ⏱️ Планировщик (APScheduler)
- Разовые, ежедневные, еженедельные, интервальные и cron-задачи записи
- Presets, совместимые с CLI, предпросмотр следующих запусков, включение/отключение задач

### ⌨️ CLI и headless-режим
- Старт/стоп/статус, полный CRUD планировщика, presets
- `--headless` запускает только API-сервер, без GUI

## Требования

| Требование | Значение |
|---|---|
| ОС | Windows 10/11 (Windows Graphics Capture API) |
| Python | 3.11+ |
| FFmpeg | должен быть доступен через `PATH` |
| Менеджер пакетов | [uv](https://docs.astral.sh/uv/) (рекомендуется) или pip |

## Установка

### Вариант 1 — через uv (рекомендуется)

```bash
git clone https://github.com/chelslava/MIA-ScreenCapture.git
cd MIA-ScreenCapture

# Установка uv, если ещё не установлен
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Создание venv и установка зависимостей
uv sync                # все зависимости, включая dev
uv sync --no-dev        # только production
```

### Вариант 2 — через pip

```bash
git clone https://github.com/chelslava/MIA-ScreenCapture.git
cd MIA-ScreenCapture

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt        # production
pip install -r requirements-dev.txt    # + dev-инструменты
```

### Проверка FFmpeg

```bash
ffmpeg -version
```

Если FFmpeg не установлен — скачайте с [официального сайта](https://ffmpeg.org/download.html) и добавьте в `PATH`.

## Быстрый старт

### GUI (по умолчанию)

```bash
uv run python main.py
```

### CLI

```bash
# Запись с параметрами по умолчанию
uv run python main.py --start

# Запись прямоугольной области
uv run python main.py --start --area rect --rect 100 100 800 600

# Запись с микрофоном, 60 секунд
uv run python main.py --start --audio mic --duration 60

# Остановка / статус
uv run python main.py --stop
uv run python main.py --status
```

### Планировщик

```bash
# Ежедневная запись в 09:30
uv run python main.py --schedule-create --trigger daily --time "09:30" --audio mic --duration 1800

# По будням в 14:00
uv run python main.py --schedule-create --trigger weekly --time "14:00" --days "0,2,4" --audio both

# Применить готовый preset
uv run python main.py --schedule-create --preset workday-morning
uv run python main.py --list-presets

# Управление задачами
uv run python main.py --schedule-list
uv run python main.py --schedule-update TASK_ID --time "10:00"
uv run python main.py --schedule-toggle TASK_ID --enabled false
uv run python main.py --schedule-delete TASK_ID
uv run python main.py --schedule-preview
```

### Headless-режим (только API)

```bash
uv run python main.py --headless
```

## Справочник CLI

| Параметр | Описание | По умолчанию |
|---|---|---|
| `--gui` | Запуск с GUI | да |
| `--headless` | Запуск без GUI (только API) | – |
| `--start` / `--stop` / `--status` | Управление записью | – |
| `--area` | `full`, `window` или `rect` | `full` |
| `--rect X1 Y1 X2 Y2` | Координаты прямоугольника | – |
| `--window TITLE` | Заголовок окна для захвата | – |
| `--monitor INDEX` | Индекс монитора для `full` | основной |
| `--audio` | `mic`, `system`, `both` или `none` | `none` |
| `--output PATH` | Путь к выходному файлу | авто |
| `--fps FPS` | Кадров в секунду | `30` |
| `--codec CODEC` | Видеокодек | `libx264` |
| `--bitrate RATE` | Битрейт | `2M` |
| `--cursor` | Показывать курсор в записи | выкл. |
| `--duration SECONDS` | Длительность записи | без ограничений |
| `--api-host` / `--api-port` | Адрес API-сервера | `127.0.0.1` / `5000` |
| `--no-api` | Отключить API-сервер | – |
| `--version` | Показать установленную версию | – |

Полный список, включая все подкоманды планировщика: `python main.py --help`.

## REST API

По умолчанию API доступен на `http://127.0.0.1:5000`. Все эндпоинты (кроме `/health`) требуют API-ключ через заголовок `X-API-Key` или `Authorization: Bearer`. Версионированные эндпоинты — под `/api/v1/*`; legacy `/api/*` сохранены для обратной совместимости.

Полный справочник со схемами запросов/ответов: [`docs/API.md`](docs/API.md). Интерактивная документация: `GET /api/docs` (Swagger UI) при запущенном сервере.

### Группы эндпоинтов

| Группа | Примеры | Назначение |
|---|---|---|
| Health | `GET /health` | Проверка доступности, без аутентификации |
| Запись | `POST /api/v1/start`, `stop`, `pause`, `GET status` | Основное управление записью |
| Горячее переключение | `POST /api/v1/recording/switch-source` | Смена источника захвата без остановки |
| Мульти-монитор | `POST /api/v1/recording/start-multi`, `stop-multi`, `GET status-multi` | Параллельная запись по мониторам |
| Записи | `GET /api/v1/recordings`, `POST recordings/verify`, `recordings/repair` | История, проверка целостности, восстановление |
| Планировщик | `GET/POST /api/v1/schedule`, `PUT/DELETE .../<id>`, `POST .../<id>/toggle` | CRUD запланированных задач |
| Ресурсы | `GET /api/v1/devices`, `windows`, `resources/monitors`, `resources/disk-space` | Аудиоустройства, окна, мониторы, диск |
| Вебхуки | `GET/POST /api/v1/config/webhook`, `POST .../test` | HMAC-подписанные уведомления о событиях |
| События | `GET /api/v1/events/recent`, `events/stats` | История событий для опроса (polling) |
| Observability | `GET /api/v1/observability/metrics`, `observability/baseline`, `circuit-breakers` | RPS, latency, SLO baseline, статус breaker'ов |
| Конфигурация | `GET/PUT /api/v1/config` | Чтение/обновление runtime-конфигурации |
| WebSocket | `ws://host:port/ws` | Поток событий в реальном времени с heartbeat |

### Формат ошибок

```json
{
  "success": false,
  "error": {
    "code": "validation_error",
    "message": "Ошибка валидации данных",
    "details": [
      {"field": "fps", "message": "Input should be less than or equal to 120", "type": "less_than_equal"}
    ]
  },
  "trace_id": "a1b2c3d4e5f6478a9b0c1234567890ab"
}
```

`trace_id` дублируется в заголовке ответа `X-Request-ID`. Успешные ответы возвращаются в формате `{"success": true, "data": {...}}`.

### Примеры curl

```bash
# Начать запись
curl -X POST http://localhost:5000/api/v1/start \
  -H "X-API-Key: your-api-key" -H "Content-Type: application/json" \
  -d '{"area":"full", "audio":"mic", "fps":30}'

# Статус
curl -H "X-API-Key: your-api-key" http://localhost:5000/api/v1/status

# Создать cron-задачу
curl -X POST http://localhost:5000/api/v1/schedule \
  -H "X-API-Key: your-api-key" -H "Content-Type: application/json" \
  -d '{
    "trigger": "cron",
    "day_of_week": "mon,wed,fri",
    "time": "15:00",
    "params": {"area": "window", "window_title": "Zoom", "audio": "system", "duration": 3600}
  }'
```

## Архитектура

Слоистая архитектура с единым публичным контрактом (`ApplicationFacade`, `Protocol`), общим для GUI, API и CLI, и `EventBus` для pub/sub-уведомлений между ними:

```
CLI / API / GUI
      │  команды
      ▼
ApplicationFacade (Protocol)
      │  оркестрация
      ▼
ApplicationService
      ├── RecordingService  → RecordingBackend → recorder/
      ├── TaskScheduler      → APScheduler
      └── EventBus           → GUI / API / WebSocket / вебхуки
```

```
api/            REST API: маршруты Flask, аутентификация, rate limiting,
                idempotency, circuit breaker, WebSocket-транспорт, Swagger
app_runtime/    Тонкие runtime-координаторы между core/ и GUI/API
cli/            CLI на argparse и подкоманды планировщика
core/           Доменный слой: event bus, DI-контейнер, lifecycle, фасад
gui/            PyQt6 GUI (MVC: views/controllers/models, backends, стили)
recorder/       Физический захват: Windows Graphics Capture, sounddevice,
                кодирование FFmpeg, восстановление после краша, ротация
scheduler/      Планировщик задач на APScheduler и их персистентность
tests/          79+ unit-тестов, 11+ интеграционных тестов
```

## Конфигурация

Настройки сохраняются в `config/config.json`:

```json
{
  "video": { "fps": 30, "codec": "libx264", "bitrate": "2M", "format": "mp4" },
  "audio": { "record_mic": true, "sample_rate": 44100, "channels": 2 },
  "api": { "enabled": true, "host": "127.0.0.1", "port": 5000, "api_key": null }
}
```

API-ключ также можно задать через переменную окружения `MIA_API_KEY` или в Windows Credential Manager (целевое имя `MIA-ScreenCapture/APIKey`).

## Разработка

```bash
uv sync                                    # установка dev-зависимостей

uv run pytest                              # все тесты
uv run pytest tests/unit/                  # только unit-тесты
uv run pytest --cov=. --cov-report=html    # с покрытием

uv run ruff check .                        # линтинг
uv run ruff format .                       # форматирование
uv run mypy .                              # проверка типов
```

Pre-commit хуки (ruff, mypy) настроены в `.pre-commit-config.yaml`:

```bash
uv run pre-commit install
```

## Решение проблем

**FFmpeg не найден** — убедитесь, что `ffmpeg -version` работает и FFmpeg добавлен в `PATH`.

**Нет звука в записи** — проверьте настройки микрофона в системе, выберите правильное устройство ввода в GUI и убедитесь, что для системного звука есть loopback-устройство ("Stereo Mix").

**Ошибки при кодировании** — проверьте свободное место на диске, корректность установки FFmpeg и логи в `logs/recorder.log`.

## Известные ограничения

- Только Windows 10/11 (зависимость от Windows Graphics Capture API)
- Некоторые защищённые DRM-окна не захватываются
- Захват системного звука требует loopback-устройства ("Stereo Mix")
- Нет стриминга RTMP/HLS и интеграции с облачным хранилищем

Полная история изменений — в [`CHANGELOG.md`](CHANGELOG.md), планы развития — в [GitHub Issues](https://github.com/chelslava/MIA-ScreenCapture/issues).

## Лицензия

[MIT](LICENSE)

## Автор

Вячеслав Чельщев — [@chelslava](https://github.com/chelslava)
