<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-06-05 -->

# core/

## Purpose
Доменное ядро приложения. Содержит бизнес-логику записи, управление жизненным циклом приложения, event bus для слабосвязанного взаимодействия компонентов, DI-контейнер и протоколы (интерфейсы) для всех внешних зависимостей. Этот слой не зависит от GUI или API — только от доменной логики.

## Key Files

| Файл | Описание |
|------|----------|
| `application_facade.py` | `ApplicationFacade` Protocol — единый публичный контракт команд/запросов для GUI/API/CLI |
| `application_service.py` | Реализация `ApplicationFacade` — оркестрирует все компоненты |
| `container.py` | DI-контейнер: создаёт и хранит все сервисы приложения |
| `lifecycle.py` | `AppLifecycle` — управление состояниями запуска/остановки приложения |
| `readiness.py` | `ReadinessChecker` — проверки готовности компонентов (FFmpeg, аудио, диск) |
| `event_bus.py` | `EventBus` Protocol + `RecordingEvent`, `RecordingEventType` — шина доменных событий |
| `recording_service.py` | `RecordingService` — управление жизненным циклом записи |
| `recording_state.py` | Thread-safe хранилище состояния текущей записи |
| `recording_types.py` | Доменные типы: `RecordingParams`, `RecordingResult` и другие |
| `recording_backend.py` | `RecordingBackend` Protocol — абстракция над физическим рекордером |
| `api_lifecycle_manager.py` | Управление жизненным циклом API сервера |
| `api_runtime_manager.py` | Runtime-операции API: запуск/остановка/перезапуск/настройки |
| `error_format.py` | Форматирование ошибок FFmpeg и доменных исключений для диагностики |
| `geometry.py` | Геометрические утилиты: прямоугольники, координаты, нормализация областей |

## Subdirectories

Нет поддиректорий.

## For AI Agents

### Working In This Directory
- `core/` — единственный слой без зависимостей от GUI/API. Никогда не импортируй `gui.*` или `api.*` здесь.
- Новые сервисы регистрируй в `container.py` и добавляй методы в `ApplicationFacade` Protocol.
- `ApplicationFacade` — это Protocol (структурная типизация), реализация в `application_service.py`.
- Event bus использует подписки: `bus.subscribe(RecordingEventType.STARTED, handler)`.
- `RecordingBackend` — Protocol для абстракции; GUI реализует его в `gui/backends/recording_backend.py`.
- Состояние записи thread-safe через `recording_state.py` — не хранить состояние в сервисах.

### Testing Requirements
- `tests/unit/test_event_bus.py` — тесты шины событий
- `tests/unit/test_recording_service.py` — тесты сервиса записи
- `tests/unit/test_lifecycle.py` — тесты lifecycle
- `tests/unit/test_container.py` — тесты DI-контейнера
- `tests/unit/test_application_service.py` — тесты фасада
- `tests/unit/test_readiness.py` — тесты готовности

### Common Patterns
```python
# Подписка на события
event_bus.subscribe(RecordingEventType.STARTED, self._on_recording_started)

# Публикация события
event_bus.publish(RecordingEvent(
    event_type=RecordingEventType.STARTED,
    payload={"file": path}
))

# Обращение к фасаду
result = facade.start_recording({"area": "full", "fps": 30})
```

## Dependencies

### Internal
- `config.py` — конфигурация приложения
- `exceptions.py` — иерархия исключений
- `logger_config.py` — логирование
- `recorder/` — физический рекордер через `RecordingBackend` Protocol
- `scheduler/` — планировщик через DI-контейнер

### External
- Только стандартная библиотека Python + `dataclasses`, `threading`

<!-- MANUAL: -->
