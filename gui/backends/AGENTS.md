<!-- Parent: ../gui/AGENTS.md -->
<!-- Generated: 2026-05-07 -->

# gui/backends/

## Purpose
Адаптер между GUI recording stack и `core.RecordingBackend` Protocol. Позволяет сервисному слою работать с GUI-рекордером без прямой зависимости от контроллеров.

## Key Files

| Файл | Описание |
|------|----------|
| `recording_backend.py` | `GUIRecordingBackend` — адаптер `RecordingController` → `RecordingBackend` Protocol. Маппит `CaptureRequest`/`AudioRequest`/`VideoRequest` → `CaptureSettings`/`AudioSettings`/`VideoSettings`. |

## For AI Agents

### Working In This Directory
- `GUIRecordingBackend` — адаптер, НЕ реализация. Физический захват остаётся в `recorder/`.
- Новые методы добавляй через делегирование к `self._controller` — не дублируй логику.
- `_map_*` функции — чистые преобразователи; не мутируй состояние здесь.
- `state` и `controller` свойства — для тестов и интеграции, не для прямого использования в prod.

### Testing Requirements
- Тесты в `tests/unit/test_recording_backend.py` (если есть).
- Мокай `RecordingController`, тестируй маппинг параметров.

### Common Patterns
```python
# Адаптер к RecordingBackend Protocol
backend = GUIRecordingBackend(controller=my_controller)
success, error = backend.start(output_path, capture, audio, video)

# Чтение статуса
snapshot = backend.get_status()
```
