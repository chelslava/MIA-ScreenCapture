<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-05-07 -->

# scheduler/

## Purpose
Планировщик задач записи на базе APScheduler. Поддерживает разовые, ежедневные, еженедельные, интервальные задачи и cron-выражения. Задачи персистируются в JSON-файле `config/tasks.json`. Выполнение задач вызывает `ApplicationFacade.start_recording()`.

## Key Files

| Файл | Описание |
|------|----------|
| `task_scheduler.py` | `TaskScheduler` — основной класс: добавление/удаление/обновление задач, APScheduler lifecycle |
| `task_storage.py` | `TaskStorage` — персистентное хранилище задач в JSON |
| `execution_engine.py` | `SchedulerExecutionEngine` — выполнение задачи: вызов фасада, обработка ошибок |
| `trigger_builder.py` | `create_trigger()`, `normalize_crontab_expression()` — построение APScheduler triggers |

## Subdirectories

Нет поддиректорий.

## For AI Agents

### Working In This Directory
- `TaskScheduler` использует `BackgroundScheduler` (APScheduler) с `MemoryJobStore`.
- Персистентность — только через `TaskStorage` (JSON), APScheduler jobstore — in-memory.
- `ScheduleType`: ONCE, DAILY, WEEKLY, INTERVAL, CRON.
- При изменении структуры задачи обновляй `RecordingParams` dataclass и `task_storage.py`.
- `trigger_builder.py` нормализует cron-выражения и конвертирует типы в APScheduler triggers.
- Часовой пояс берётся автоматически через `tzlocal`.

### Testing Requirements
- `tests/unit/test_scheduler.py` — основные тесты
- `tests/unit/test_task_storage.py` — тесты хранилища
- `tests/unit/test_trigger_builder.py` — тесты построения триггеров
- `tests/unit/test_execution_engine.py` — тесты движка выполнения
- `tests/integration/test_scheduler_integration.py` — интеграционные тесты
- Запуск: `uv run pytest tests/unit/test_scheduler.py tests/unit/test_task_storage.py`

### Common Patterns
```python
# Добавление задачи
scheduler.add_task({
    "schedule_type": "daily",
    "time": "09:00",
    "recording_params": {"area": "full", "fps": 30}
})

# Типы расписания
ScheduleType.ONCE    # разовая
ScheduleType.DAILY   # ежедневно в время HH:MM
ScheduleType.WEEKLY  # по дням недели
ScheduleType.INTERVAL  # каждые N минут
ScheduleType.CRON    # cron-выражение
```

## Dependencies

### Internal
- `core/application_facade.py` — выполнение задач через `ApplicationFacade`
- `logger_config.py` — логирование
- `exceptions.py` — обработка ошибок

### External
- `apscheduler` — BackgroundScheduler, ThreadPoolExecutor, triggers
- `tzlocal` — определение местного часового пояса

<!-- MANUAL: -->
