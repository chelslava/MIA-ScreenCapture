<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-04-29 -->

# gui/models/

## Purpose
Модели данных GUI-слоя. Служат переходным слоем между доменными типами (`core/recording_state.py`) и GUI — реэкспортируют типы из `core/` и добавляют GUI-специфичные модели (список кодеков, состояние WebSocket).

## Key Files

| Файл | Описание |
|------|----------|
| `recording_state.py` | Реэкспорт доменных типов из `core/recording_state.py`: `RecordingState`, `AudioSettings`, `VideoSettings`, `CaptureSettings`, `OutputSettings`, `CaptureType`, `AudioType`, `RecordingStatus`, `RecentRecording` |
| `video_codecs.py` | `VideoCodec` — перечисление доступных видеокодеков и их параметров |
| `websocket_state.py` | `WebSocketState` — состояние SSE/WebSocket соединения GUI |

## Subdirectories

Нет поддиректорий.

## For AI Agents

### Working In This Directory
- `recording_state.py` — только реэкспорт, не дублировать типы из `core/`.
- Новые GUI-специфичные типы добавляй здесь; доменные типы добавляй в `core/recording_state.py`.
- `VideoCodec` содержит список кодеков, поддерживаемых системой (не всегда совпадает с FFmpeg).
- `WebSocketState` — enum или dataclass для отслеживания статуса SSE подключения в GUI.

### Testing Requirements
- `tests/unit/test_gui_models.py` — тесты GUI-моделей
- `tests/unit/test_video_codecs.py` — тесты кодеков
- `tests/unit/test_websocket_state.py` — тесты состояния WebSocket
- Запуск: `uv run pytest tests/unit/test_gui_models.py tests/unit/test_video_codecs.py`

### Common Patterns
```python
# Импорт доменных типов через gui/models/ (не напрямую из core/)
from gui.models.recording_state import RecordingState, CaptureType

# Кодеки
from gui.models.video_codecs import VideoCodec
codecs = VideoCodec.get_available()
```

## Dependencies

### Internal
- `core/recording_state.py` — реэкспортируемые доменные типы

### External
- Только стандартная библиотека (`enum`, `dataclasses`)

<!-- MANUAL: -->
