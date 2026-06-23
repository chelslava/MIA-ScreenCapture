<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-06-23 -->

# tests/unit/

## Purpose
214 unit-тестов с мокированием всех внешних зависимостей. Покрывают все модули: API, core, GUI, recorder, scheduler, cli. Организованы по поддиректориям, зеркалящим структуру исходников. Запускаются быстро, без реального оборудования, PyQt6 или FFmpeg.

## Структура директорий

```
tests/unit/
├── api/              — API-тесты (13 файлов)
├── core/             — Core-тесты (8 файлов)
├── gui/              — GUI-тесты (24 файла)
├── recorder/         — Recorder-тесты (12 файлов)
├── scheduler/        — Scheduler-тесты (6 файлов)
├── cli/              — CLI-тесты (2 файла)
├── config/           — Config/Logger-тесты (4 файла)
├── main/             — Main-тесты (7 файлов)
├── conftest.py       — Общие фикстуры и мок PyQt6
└── AGENTS.md         — Этот файл
```

## Key Files по категориям

| Группа | Директория | Файлы |
|--------|-----------|-------|
| **API** | `api/` | `test_api_server.py`, `test_api_auth.py`, `test_api_error_mapping.py`, `test_api_runtime_models.py`, `test_api_runtime_manager.py`, `test_schemas.py`, `test_swagger.py`, `test_rate_limiter.py`, `test_request_context.py`, `test_request_lifecycle.py`, `test_websocket.py`, `test_websocket_transport.py`, `test_circuit_breaker.py`, `test_webhook.py` |
| **Core** | `core/` | `test_event_bus.py`, `test_recording_service.py`, `test_lifecycle.py`, `test_container.py`, `test_application_service.py`, `test_readiness.py`, `test_api_lifecycle_manager.py`, `test_multi_recording_service.py` |
| **GUI** | `gui/` | `test_main_window.py`, `test_gui_views.py`, `test_gui_controllers.py`, `test_gui_models.py`, `test_tray_icon.py`, `test_hotkeys.py`, `test_notifications.py`, `test_desktop_actions.py`, `test_recording_controller.py`, `test_settings_controller.py`, `test_status_bar_controller.py`, `test_websocket_controller.py`, `test_websocket_state.py`, `test_capture_view.py`, `test_audio_view.py`, `test_video_view.py`, `test_api_settings_view.py`, `test_readiness_center_view.py`, `test_recording_indicator.py`, `test_capture_area_selector.py`, `test_view_accessibility.py`, `test_theme.py`, `test_video_codecs.py`, `test_gui_recording_backend.py` |
| **Recorder** | `recorder/` | `test_video_recorder.py`, `test_video_recorder_extended.py`, `test_video_recorder_threading.py`, `test_audio_recorder.py`, `test_audio_recorder_extended.py`, `test_audio_recorder_threading.py`, `test_encoder.py`, `test_encoder_extended.py`, `test_ffmpeg_writer.py`, `test_ffmpeg_availability.py`, `test_recorder_utils.py`, `test_zero_copy_optimization.py`, `test_multi_source_recorder.py` |
| **Scheduler** | `scheduler/` | `test_scheduler.py`, `test_scheduler_tab.py`, `test_task_storage.py`, `test_trigger_builder.py`, `test_execution_engine.py`, `test_task_dialog.py` |
| **CLI** | `cli/` | `test_cli_parser.py`, `test_cli_scheduler.py` |
| **Config/Logger** | `config/` | `test_config.py`, `test_config_extended.py`, `test_logger_config.py`, `test_exceptions.py` |
| **Main** | `main/` | `test_main_entrypoint.py`, `test_main_api_runtime.py`, `test_utils.py`, `test_single_instance.py` |

## Subdirectories

8 поддиректорий, зеркальных структуре исходников.

## For AI Agents

### Working In This Directory
- Каждый тестовый файл соответствует одному модулю и лежит в соответствующей поддиректории.
- PyQt6 мокируется через `sys.modules` в `conftest.py` — не импортируй реальный PyQt6.
- Для мока внешних сервисов используй `mocker.patch()` (pytest-mock).
- При добавлении нового модуля создавай `test_<новый_модуль>.py` в соответствующей категории (api/, core/, gui/, и т.д.).
- `_extended` файлы покрывают edge cases и дополнительные сценарии.
- `_threading` файлы проверяют thread safety.
- `conftest.py` остаётся в `tests/unit/` и доступен всем поддиректориям.

### Testing Requirements
```bash
# Все unit-тесты
uv run pytest tests/unit/ -v

# Конкретная категория
uv run pytest tests/unit/api/ -v

# Конкретный модуль
uv run pytest tests/unit/api/test_api_server.py -v

# С покрытием
uv run pytest tests/unit/ --cov=. --cov-report=term-missing
```

### Common Patterns
```python
class TestMyModule:
    def test_basic(self, mocker):
        mock_dep = mocker.patch("module.dependency")
        mock_dep.return_value = "value"

        result = MyClass().do_thing()

        assert result == expected
        mock_dep.assert_called_once_with(...)
```

## Dependencies

### Internal
- `conftest.py` в `tests/` — общие фикстуры и мок PyQt6

### External
- `pytest`, `pytest-mock`, `pytest-cov`

<!-- MANUAL: -->
