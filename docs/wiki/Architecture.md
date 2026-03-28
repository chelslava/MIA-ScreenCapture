# Architecture

## Общая схема

MIA-ScreenCapture состоит из слоев:

- GUI (`PyQt6`) для интерактивного управления.
- API (`Flask` + `waitress`) для внешней автоматизации.
- CLI (`argparse`) для командной работы и скриптов.
- Core/Recorder/Scheduler для доменной логики записи.

## Основные модули

- `main.py`: точка входа и оркестрация всех компонентов.
- `gui/`: окна, вкладки, контролы, трей, горячие клавиши.
- `api/`: аутентификация, маршруты, схемы валидации, swagger.
- `recorder/`: видеозахват, аудиозапись, ffmpeg-пайплайн.
- `scheduler/`: планировщик задач записи.
- `config.py`: dataclass-конфигурация и сохранение JSON.
- `logger_config.py`: настройка логов и API-логов по дням.

## Жизненный цикл записи

1. Пользователь/клиент вызывает старт (`GUI`, `CLI` или `API`).
2. Валидируются параметры записи.
3. Запускается видеозахват и при необходимости аудиозахват.
4. Данные пишутся во временные файлы.
5. При остановке выполняется финализация через FFmpeg.
6. Результат добавляется в список recent recordings.

## Жизненный цикл API

1. При запуске создается `APIServer`.
2. Настраивается API key аутентификация и rate limit.
3. Регистрируются маршруты `/api/v1/*` и legacy `/api/*`.
4. Для GUI доступны контролы: start/stop/restart/apply/get_status.
5. Все запросы логируются с `request_id`, latency и IP.

## Валидация входных данных

- Для API используется `pydantic` (`api/schemas.py`).
- Ошибки приводятся к единому контракту:
  `success=false`, `error.code`, `error.message`, `error.details`, `trace_id`.

## Логи и наблюдаемость

- Основные логи: `logs/mia_YYYY-MM-DD.log`.
- API-логи: `logs/api/api_YYYY-MM-DD.log`.
- Эксплуатационные метрики: `GET /api/v1/observability/metrics`.
- Baseline SLO: `GET /api/v1/observability/baseline`.
