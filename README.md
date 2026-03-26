# MIA-ScreenCapture v1.3.0

Профессиональная программа для записи видео с экрана с графическим интерфейсом, REST API, планировщиком задач и поддержкой командной строки.

## Возможности

- **Графический интерфейс (GUI)** на базе PyQt6
  - Выбор области захвата: весь экран, окно, прямоугольная область
  - Настройки звука: микрофон, системный звук, без звука
  - Параметры видео: FPS, кодек, битрейт
  - Список последних записей
  - Иконка в системном трее

- **REST API** для удаленного управления
  - Запуск/остановка/пауза записи
  - Получение статуса
  - Управление планировщиком
  - Получение recent event-ленты для real-time интеграций

- **Планировщик задач** на базе APScheduler
  - Одноразовые задачи
  - Ежедневные задачи
  - Еженедельные задачи
  - Интервальные задачи

- **Командная строка**
  - Запуск записи с параметрами
  - Остановка записи
  - Получение статуса

## Требования

- Python 3.9+
- FFmpeg (должен быть в PATH)
- [UV](https://docs.astral.sh/uv/) — быстрый менеджер пакетов (рекомендуется)

## Установка

### Способ 1: Через UV (рекомендуется)

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd MIA-ScreenCapture
```

2. Установите UV (если не установлен):
```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Linux/macOS
curl -LsSf https://astral.sh/uv/install.sh | sh
```

3. Создайте виртуальное окружение и установите зависимости:
```bash
# Создать venv и установить все зависимости
uv sync

# Или только production зависимости
uv sync --no-dev
```

4. Активируйте виртуальное окружение:

Windows:
```bash
.venv\Scripts\activate
```

Linux/macOS:
```bash
source .venv/bin/activate
```

### Способ 2: Через pip (классический)

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd MIA-ScreenCapture
```

2. Создайте виртуальное окружение:
```bash
python -m venv .venv
```

3. Активируйте виртуальное окружение:

Windows:
```bash
.venv\Scripts\activate
```

Linux/macOS:
```bash
source .venv/bin/activate
```

4. Установите зависимости:
```bash
# Production зависимости
pip install -r requirements.txt

# Или все зависимости включая dev
pip install -r requirements-dev.txt
```

### Проверка FFmpeg

Убедитесь, что FFmpeg установлен:
```bash
ffmpeg -version
```

Если FFmpeg не установлен:
- Официальный сайт: https://ffmpeg.org/download.html
- GitHub репозиторий: https://github.com/FFmpeg/FFmpeg

После установки добавьте FFmpeg в PATH.

## Разработка

### Установка dev-зависимостей

```bash
# Через UV
uv sync

# Через pip
pip install -r requirements-dev.txt
```

### Запуск тестов

```bash
# Через UV (рекомендуется)
uv run pytest

# С покрытием кода
uv run pytest --cov=. --cov-report=html

# Только unit-тесты
uv run pytest tests/unit/

# Или через активированный venv
pytest
```

### Линтинг и форматирование

```bash
# Через UV (рекомендуется)
uv run ruff check .
uv run ruff format .
uv run mypy .

# Или через активированный venv
ruff check .
ruff format .
mypy .
```

## Использование

### Графический интерфейс

Запуск с GUI (по умолчанию):
```bash
# Через UV (рекомендуется)
uv run python main.py

# Или через активированный venv
python main.py
```

### Командная строка

Запуск записи с параметрами по умолчанию:
```bash
uv run python main.py --start
```

Запуск записи с указанием области:
```bash
uv run python main.py --start --area rect --rect 100 100 800 600
```

Запись с микрофоном:
```bash
uv run python main.py --start --audio mic --duration 60
```

Остановка записи:
```bash
uv run python main.py --stop
```

Получение статуса:
```bash
uv run python main.py --status
```

Список запланированных задач:
```bash
uv run python main.py --schedule-list
```

Создание запланированной задачи:
```bash
# Ежедневная запись в 09:30
uv run python main.py --schedule-create --trigger daily --time "09:30" --audio mic --duration 1800

# Еженедельная запись по будням в 14:00
uv run python main.py --schedule-create --trigger weekly --time "14:00" --days "0,2,4" --audio both

# Использование preset шаблона
uv run python main.py --schedule-create --preset workday-morning

# Показать список presets
uv run python main.py --list-presets
```

Управление задачами:
```bash
# Обновить задачу
uv run python main.py --schedule-update TASK_ID --time "10:00"

# Удалить задачу
uv run python main.py --schedule-delete TASK_ID

# Включить/выключить задачу
uv run python main.py --schedule-toggle TASK_ID --enabled false

# Показать предстоящие запуски
uv run python main.py --schedule-preview
```

### Headless режим (только API)

```bash
uv run python main.py --headless
```

### Параметры командной строки

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `--gui` | Запуск с GUI | Да |
| `--headless` | Запуск без GUI (только API) | - |
| `--start` | Начать запись | - |
| `--stop` | Остановить запись | - |
| `--status` | Показать статус | - |
| `--area` | Область захвата: full, window, rect | full |
| `--rect X1 Y1 X2 Y2` | Координаты прямоугольника | - |
| `--window TITLE` | Заголовок окна | - |
| `--audio` | Источник звука: mic, system, none, both | none |
| `--output PATH` | Путь к выходному файлу | Авто |
| `--fps FPS` | Кадров в секунду | 30 |
| `--codec CODEC` | Видеокодек | libx264 |
| `--bitrate RATE` | Битрейт | 2M |
| `--duration SECONDS` | Длительность записи | Без ограничений |
| `--api-host HOST` | Хост API сервера | 127.0.0.1 |
| `--api-port PORT` | Порт API сервера | 5000 |
| `--no-api` | Отключить API | - |

## REST API

API сервер запускается по адресу `http://127.0.0.1:5000`

### Health

#### GET /health
Проверка доступности сервиса (без API key).

**Ответ:**
```json
{
  "status": "ok",
  "timestamp": "2026-03-23T18:12:34.567890+00:00",
  "version": "1.3.0",
  "uptime_seconds": 123.456,
  "websocket": {
    "transport_ready": false
  }
}
```

### Эндпоинты

#### GET /api/status
Получить текущий статус записи.

**Ответ:**
```json
{
  "success": true,
  "data": {
    "is_recording": true,
    "is_paused": false,
    "elapsed_time": 45.2,
    "current_file": "/path/to/recording.mp4"
  }
}
```

#### GET /api/events/recent?limit=50
Получить последние события записи (transport-ready слой для WebSocket/SSE).
`limit` должен быть числом в диапазоне `1..500`.

#### GET /api/events/stats
Получить статистику event-менеджера (буфер, количество событий, готовность транспорта).

#### GET /api/observability/metrics
Получить эксплуатационные метрики API (RPS, latency, статусы ответов, ресурсы процесса).

#### GET /api/observability/baseline
Получить baseline SLO и текущие значения (`p95 latency`, `error rate`, `requests_per_second`, `rss_mb`).

### Формат ошибок

Для ошибок используется единый контракт:

```json
{
  "success": false,
  "error": {
    "code": "validation_error",
    "message": "Ошибка валидации данных",
    "details": [
      {
        "field": "fps",
        "message": "Input should be less than or equal to 120",
        "type": "less_than_equal"
      }
    ]
  },
  "trace_id": "a1b2c3d4e5f6478a9b0c1234567890ab"
}
```

`trace_id` дублируется в заголовке `X-Request-ID`.
Примечание: успешные ответы остаются в формате `{ "success": true, "data": ... }`.

#### POST /api/start
Начать запись.

**Тело запроса:**
```json
{
  "area": "full",
  "audio": "mic",
  "output_path": "/path/to/output.mp4",
  "fps": 30,
  "codec": "libx264",
  "bitrate": "2M",
  "duration": 60
}
```

**Ответ:**
```json
{
  "success": true,
  "data": {
    "output_path": "/path/to/output.mp4"
  }
}
```

#### POST /api/stop
Остановить текущую запись.

#### POST /api/pause
Поставить на паузу или возобновить.

#### GET /api/recordings
Получить список последних записей.

#### GET /api/schedule
Получить список запланированных задач.

#### POST /api/schedule
Создать новую задачу.

**Тело запроса:**
```json
{
  "trigger": "cron",
  "day_of_week": "0,2,4",
  "time": "10:00",
  "params": {
    "area": "full",
    "audio": "mic",
    "duration": 3600
  }
}
```

#### DELETE /api/schedule/<task_id>
Удалить задачу.

#### GET /api/devices
Получить список аудиоустройств.

#### GET /api/windows
Получить список окон для захвата.

### Примеры curl

Начать запись:
```bash
curl -X POST http://localhost:5000/api/start \
  -H "Content-Type: application/json" \
  -d '{"area":"full", "audio":"mic", "fps":30}'
```

Остановить запись:
```bash
curl -X POST http://localhost:5000/api/stop
```

Получить статус:
```bash
curl http://localhost:5000/api/status
```

Создать задачу планировщика:
```bash
curl -X POST http://localhost:5000/api/schedule \
  -H "Content-Type: application/json" \
  -d '{
    "trigger": "cron",
    "day_of_week": "mon,wed,fri",
    "time": "15:00",
    "params": {
      "area": "window",
      "window_title": "Zoom",
      "audio": "system",
      "duration": 3600
    }
  }'
```

## Архитектура

```
MIA-ScreenCapture/
├── main.py                 # Точка входа
├── config.py               # Управление настройками
├── logger_config.py        # Конфигурация логирования
├── pyproject.toml          # Конфигурация проекта (UV/pip)
├── requirements.txt        # Production зависимости
├── requirements-dev.txt    # Dev зависимости
├── recorder/
│   ├── __init__.py
│   ├── video_recorder.py   # Захват видео
│   ├── audio_recorder.py   # Захват аудио
│   ├── encoder.py          # Кодирование через FFmpeg
│   └── utils.py            # Вспомогательные функции
├── gui/
│   ├── __init__.py
│   ├── main_window.py      # Главное окно
│   ├── tray_icon.py        # Иконка в трее
│   └── scheduler_tab.py    # Вкладка планировщика
├── api/
│   ├── __init__.py
│   ├── server.py           # Flask сервер
│   ├── routes.py           # API эндпоинты
│   └── schemas.py          # Pydantic схемы валидации
├── scheduler/
│   ├── __init__.py
│   └── task_scheduler.py   # Планировщик задач
├── cli/
│   ├── __init__.py
│   └── parser.py           # Парсер аргументов
└── tests/                  # Тесты
    ├── unit/
    └── integration/
```

### Компоненты

1. **VideoRecorder** - захват экрана с помощью MSS и запись через OpenCV
2. **AudioRecorder** - захват звука через sounddevice/pyaudio
3. **Encoder** - объединение видео и аудио через FFmpeg
4. **MainWindow** - главное окно приложения на PyQt6
5. **TrayIcon** - иконка в системном трее
6. **APIServer** - REST API сервер на Flask
7. **TaskScheduler** - планировщик задач на APScheduler

## Логирование

Логи сохраняются в папку `logs/recorder.log` с ротацией по размеру (5 MB, 5 файлов).

## Конфигурация

Настройки сохраняются в `config/config.json`:

```json
{
  "video": {
    "fps": 30,
    "codec": "libx264",
    "bitrate": "2M",
    "format": "mp4"
  },
  "audio": {
    "record_mic": true,
    "sample_rate": 44100,
    "channels": 2
  },
  "api": {
    "enabled": true,
    "host": "127.0.0.1",
    "port": 5000
  }
}
```

## Известные ограничения

1. **Системный звук**:
   - Windows: Требует наличия устройства "Stereo Mix" или loopback
   - Linux: Требует PulseAudio monitor
   - macOS: Требует виртуальное аудиоустройство (BlackHole, Soundflower)

2. **Захват окон**:
   - Требует дополнительные библиотеки для некоторых платформ

3. **Кодирование**:
   - OpenCV поддерживает ограниченный набор кодеков
   - Для полного функционала требуется FFmpeg

## Решение проблем

### FFmpeg не найден
Убедитесь, что FFmpeg установлен и добавлен в PATH:
```bash
ffmpeg -version
```

### Нет звука при записи
1. Проверьте, что микрофон включен в настройках системы
2. Выберите правильное устройство ввода в GUI
3. Для системного звука убедитесь, что настроено соответствующее устройство

### Ошибка при кодировании
1. Проверьте наличие свободного места на диске
2. Убедитесь, что FFmpeg корректно установлен
3. Проверьте логи в `logs/recorder.log`

## Лицензия

MIT License

## Автор

Chelischev Vyacheslav [@ChelSlava](https://github.com/chelslava)
