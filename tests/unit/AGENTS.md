<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-06-23 -->

# tests/unit/

## Purpose
65+ unit-тестов с мокированием всех внешних зависимостей. Покрывают все модули: API, core, GUI, recorder, scheduler, cli. Запускаются быстро, без реального оборудования, PyQt6 или FFmpeg.

## Key Files (группы тестов)

| Группа | Файлы |
|--------|-------|
| **API** | `test_api_server.py`, `test_api_auth.py`, `test_api_error_mapping.py`, `test_api_runtime_models.py`, `test_api_runtime_manager.py`, `test_schemas.py`, `test_swagger.py`, `test_rate_limiter.py`, `test_request_context.py`, `test_request_lifecycle.py`, `test_websocket.py`, `test_websocket_transport.py`, `test_circuit_breaker.py` |
| **Core** | `test_event_bus.py`, `test_recording_service.py`, `test_lifecycle.py`, `test_container.py`, `test_application_service.py`, `test_readiness.py`, `test_api_lifecycle_manager.py` |
| **GUI** | `test_main_window.py`, `test_gui_views.py`, `test_gui_controllers.py`, `test_gui_models.py`, `test_tray_icon.py`, `test_hotkeys.py`, `test_notifications.py`, `test_desktop_actions.py`, `test_recording_controller.py`, `test_settings_controller.py`, `test_status_bar_controller.py`, `test_websocket_controller.py`, `test_websocket_state.py`, `test_capture_view.py`, `test_audio_view.py`, `test_video_view.py`, `test_api_settings_view.py`, `test_readiness_center_view.py`, `test_recording_indicator.py`, `test_capture_area_selector.py`, `test_view_accessibility.py`, `test_theme.py`, `test_video_codecs.py`, `test_gui_recording_backend.py` |
| **Recorder** | `test_video_recorder.py`, `test_video_recorder_extended.py`, `test_video_recorder_threading.py`, `test_audio_recorder.py`, `test_audio_recorder_extended.py`, `test_audio_recorder_threading.py`, `test_encoder.py`, `test_encoder_extended.py`, `test_ffmpeg_writer.py`, `test_ffmpeg_availability.py`, `test_recorder_utils.py`, `test_zero_copy_optimization.py` |
| **Scheduler** | `test_scheduler.py`, `test_scheduler_tab.py`, `test_task_storage.py`, `test_trigger_builder.py`, `test_execution_engine.py`, `test_task_dialog.py` |
| **CLI** | `test_cli_parser.py`, `test_cli_scheduler.py` |
| **Config/Logger** | `test_config.py`, `test_config_extended.py`, `test_logger_config.py`, `test_exceptions.py` |
| **Main** | `test_main_entrypoint.py`, `test_main_api_runtime.py` |

## Subdirectories

Нет поддиректорий.

## For AI Agents

### Working In This Directory
- Каждый тестовый файл соответствует одному модулю: `test_<module>.py` → `<module>.py`.
- PyQt6 мокируется через `sys.modules` в `conftest.py` — не импортируй реальный PyQt6.
- Для мока внешних сервисов используй `mocker.patch()` (pytest-mock).
- При добавлении нового модуля создавай `test_<новый_модуль>.py`.
- `_extended` файлы покрывают edge cases и дополнительные сценарии.
- `_threading` файлы проверяют thread safety.

### Testing Requirements
```bash
# Все unit-тесты
uv run pytest tests/unit/ -v

# Конкретный модуль
uv run pytest tests/unit/test_api_server.py -v

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
