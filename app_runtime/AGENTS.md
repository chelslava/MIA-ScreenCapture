<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-05-07 -->

# app_runtime/

## Purpose
Слой runtime-координации между компонентами приложения. Координаторы — тонкие обёртки над менеджерами из `core/`, предоставляющие единообразный интерфейс для `ApplicationService`. Разделяет управление API, GUI и записью на независимые координаторы.

## Key Files

| Файл | Описание |
|------|----------|
| `api_coordinator.py` | `ApiRuntimeCoordinator` — управление API сервером (старт/стоп/рестарт/настройки/ключ) |
| `gui_coordinator.py` | `GuiCoordinator` — координация GUI событий и обновлений состояния |
| `recording_coordinator.py` | `RecordingCoordinator` — координация запуска/остановки/паузы записи |
| `thread_executor.py` | `ThreadExecutor` — безопасное выполнение задач в потоках GUI/backend |
| `constants.py` | Общие константы runtime: таймауты, имена потоков |

## Subdirectories

Нет поддиректорий.

## For AI Agents

### Working In This Directory
- Координаторы — это тонкие делегаты; бизнес-логика принадлежит `core/`.
- `ApiRuntimeCoordinator` делегирует в `core/api_runtime_manager.py`.
- `GuiCoordinator` — связующее звено между GUI-сигналами и доменными событиями.
- `RecordingCoordinator` координирует `RecordingService` + `RecordingBackend`.
- `ThreadExecutor` предотвращает блокировку GUI-потока при выполнении тяжёлых операций.

### Testing Requirements
- `tests/unit/test_main_api_runtime.py` — тесты API координатора
- Запуск: `uv run pytest tests/unit/test_main_api_runtime.py`

### Common Patterns
```python
# Координатор как тонкий делегат
class ApiRuntimeCoordinator:
    def __init__(self, manager: ApiRuntimeManager) -> None:
        self._manager = manager

    def start_api_server(self, force: bool = False) -> dict[str, Any]:
        return self._manager.start_api_server(force=force)
```

## Dependencies

### Internal
- `core/api_runtime_manager.py` — управление API
- `core/recording_service.py` — управление записью
- `core/event_bus.py` — доменные события
- `logger_config.py` — логирование

### External
- Только стандартная библиотека (`threading`)

<!-- MANUAL: -->
