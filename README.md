# MIA-ScreenCapture

Профессиональная программа для записи видео с экрана с графическим интерфейсом, REST API, планировщиком задач и поддержкой командной строки.

## Возможности

- **Графический интерфейс (GUI)** на базе PyQt5
  - Выбор области захвата: весь экран, окно, прямоугольная область
  - Настройки звука: микрофон, системный звук, без звука
  - Параметры видео: FPS, кодек, битрейт
  - Список последних записей
  - Иконка в системном трее

- **REST API** для удаленного управления
  - Запуск/остановка/пауза записи
  - Получение статуса
  - Управление планировщиком

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

- Python 3.8+
- FFmpeg (должен быть в PATH)

## Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd Video_Recorder
```

2. Создайте виртуальное окружение:
```bash
python -m venv venv
```

3. Активируйте виртуальное окружение:

Windows:
```bash
venv\Scripts\activate
```

Linux/macOS:
```bash
source venv/bin/activate
```

4. Установите зависимости:
```bash
pip install -r requirements.txt
```

5. Убедитесь, что FFmpeg установлен:
```bash
ffmpeg -version
```

Если FFmpeg не установлен, скачайте его с https://ffmpeg.org/download.html и добавьте в PATH.

## Использование

### Графический интерфейс

Запуск с GUI (по умолчанию):
```bash
python main.py
```

### Командная строка

Запуск записи с параметрами по умолчанию:
```bash
python main.py --start
```

Запуск записи с указанием области:
```bash
python main.py --start --area rect --rect 100 100 800 600
```

Запись с микрофоном:
```bash
python main.py --start --audio mic --duration 60
```

Остановка записи:
```bash
python main.py --stop
```

Получение статуса:
```bash
python main.py --status
```

Список запланированных задач:
```bash
python main.py --schedule-list
```

### Headless режим (только API)

```bash
python main.py --headless
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
Video_Recorder/
├── main.py                 # Точка входа
├── config.py               # Управление настройками
├── logger_config.py        # Конфигурация логирования
├── requirements.txt        # Зависимости
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
│   └── routes.py           # API эндпоинты
├── scheduler/
│   ├── __init__.py
│   └── task_scheduler.py   # Планировщик задач
└── cli/
    ├── __init__.py
    └── parser.py           # Парсер аргументов
```

### Компоненты

1. **VideoRecorder** - захват экрана с помощью MSS и запись через OpenCV
2. **AudioRecorder** - захват звука через sounddevice/pyaudio
3. **Encoder** - объединение видео и аудио через FFmpeg
4. **MainWindow** - главное окно приложения на PyQt5
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

Video Recorder Team
