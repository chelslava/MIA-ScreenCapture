<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-06-05 -->

# recorder/

## Purpose
Физический слой захвата экрана и аудио. Использует Windows Graphics Capture API через библиотеку `windows-capture` для видео и `sounddevice`/`soundfile` для аудио. Кодирование видео через OpenCV и FFmpeg. Этот модуль работает только на Windows 10/11.

## Key Files

| Файл | Описание |
|------|----------|
| `video_recorder.py` | `VideoRecorder` — захват экрана (полный экран, окно, прямоугольник), управление состоянием, кодирование кадров |
| `audio_recorder.py` | `AudioRecorder` — захват аудио с микрофона/системного звука через sounddevice |
| `encoder.py` | `VideoEncoder` — кодирование видео через FFmpeg pipeline (современный подход) |
| `ffmpeg_pipeline.py` | `FFmpegPipeline` — полный pipeline кодирования через FFmpeg subprocess |
| `ffmpeg_writer.py` | `FFmpegWriter` — упрощённая обёртка над FFmpeg subprocess (legacy, используется в тестах) |
| `utils.py` | Утилиты: `get_available_monitors()`, `get_available_windows()`, `validate_rect_coords()`, `get_platform()` |

## Subdirectories

Нет поддиректорий.

## For AI Agents

### Working In This Directory
- Модуль Windows-only: не удалять и не обходить проверки платформы.
- `VideoRecorder` управляет `RecordingState` (IDLE/RECORDING/PAUSED/STOPPING) — state machine.
- Захват экрана происходит в отдельном потоке; синхронизация через threading.Event.
- `CaptureArea` определяет тип захвата: `"full"`, `"window"`, `"rect"`.
- При изменении кодирования — затрагивает и `encoder.py`, и `ffmpeg_writer.py`.
- FFmpeg должен быть в PATH — `ffmpeg_writer.py` запускает его через `subprocess`.

### Testing Requirements
- `tests/unit/test_video_recorder.py` — базовые тесты рекордера
- `tests/unit/test_video_recorder_extended.py` — edge cases
- `tests/unit/test_video_recorder_threading.py` — thread safety
- `tests/unit/test_audio_recorder.py`, `test_audio_recorder_extended.py`, `test_audio_recorder_threading.py`
- `tests/unit/test_encoder.py`, `test_encoder_extended.py`
- `tests/unit/test_ffmpeg_writer.py`
- `tests/unit/test_recorder_utils.py`
- Запуск: `uv run pytest tests/unit/test_video_recorder*.py tests/unit/test_audio_recorder*.py`

### Common Patterns
```python
# Захват области
area = CaptureArea(type="rect", x=0, y=0, width=1920, height=1080)

# Доступные мониторы
monitors = get_available_monitors()

# Доступные окна
windows = get_available_windows()
```

## Dependencies

### Internal
- `logger_config.py` — логирование
- `exceptions.py` — `RecordingError`

### External
- `windows-capture` — Windows Graphics Capture API
- `opencv-python` (`cv2`) — кодирование видео
- `numpy` — обработка кадров
- `sounddevice` — захват аудио
- `soundfile` — запись аудио в файл
- `ffmpeg` (системная зависимость, в PATH)

<!-- MANUAL: -->
