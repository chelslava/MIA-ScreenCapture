<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-06-05 -->

# gui/controllers/

## Purpose
Контроллеры MVC — связывают представления (`gui/views/`) с доменной логикой (`core/`, `app_runtime/`). Подписываются на сигналы views и вызывают `ApplicationFacade`. Также подписываются на доменные события и обновляют views.

## Key Files

| Файл | Описание |
|------|----------|
| `recording_controller.py` | Управляет запуском/остановкой/паузой записи; строит `RecordingParams` из GUI-настроек |
| `settings_controller.py` | Читает и сохраняет настройки (video, audio, output, API); синхронизирует views ↔ config |
| `status_bar_controller.py` | Управляет строкой статуса главного окна: обновляет текст и иконки по событиям записи |
| `websocket_controller.py` | Управляет WebSocket соединением для SSE; подписывает views на события через event bus |

## Subdirectories

Нет поддиректорий.

## For AI Agents

### Working In This Directory
- Контроллеры получают `ApplicationFacade` через конструктор (dependency injection).
- Подключение сигналов views происходит в `main_window.py`.
- Контроллеры не должны содержать UI-код (создавать виджеты, менять стили).
- `recording_controller.py` собирает параметры из всех views и передаёт в `facade.start_recording()`.
- `settings_controller.py` — единая точка чтения/записи конфигурации для GUI.
- `websocket_controller.py` отвечает за SSE-подключение к API в GUI-режиме.

### Testing Requirements
- `tests/unit/test_gui_controllers.py` — общие тесты контроллеров
- `tests/unit/test_settings_controller.py` — тесты контроллера настроек
- `tests/unit/test_websocket_controller.py` — тесты WebSocket контроллера
- Запуск: `uv run pytest tests/unit/test_gui_controllers.py tests/unit/test_settings_controller.py`

### Common Patterns
```python
class RecordingController:
    def __init__(self, facade: ApplicationFacade) -> None:
        self._facade = facade

    def connect_signals(self, view: CaptureView) -> None:
        view.start_requested.connect(self._on_start_requested)

    def _on_start_requested(self) -> None:
        params = self._build_params()
        result = self._facade.start_recording(params)
        # обновить UI по результату
```

## Dependencies

### Internal
- `core/application_facade.py` — выполнение команд
- `core/event_bus.py` — подписка на доменные события
- `gui/views/` — views, сигналы которых обрабатываются
- `gui/models/` — типы данных
- `config.py` — настройки приложения

### External
- `PyQt6.QtCore` — `pyqtSlot`

<!-- MANUAL: -->
