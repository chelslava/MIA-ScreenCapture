"""
GUI-backed реализация backend-порта записи.

Инкапсулирует существующий recording stack за core-интерфейсом,
чтобы сервисный слой не зависел от GUI-контроллеров напрямую.
"""

from __future__ import annotations

from pathlib import Path

from core.recording_backend import RecordingBackend, RecordingStatusSnapshot
from core.recording_state import (
    AudioSettings,
    CaptureSettings,
    RecordingState,
    VideoSettings,
)
from core.recording_types import (
    AudioMode,
    AudioRequest,
    CaptureMode,
    CaptureRequest,
    VideoRequest,
)
from gui.controllers.recording_controller import RecordingController


def _map_capture(capture: CaptureRequest) -> CaptureSettings:
    return CaptureSettings(
        capture_type=capture.mode,
        window_title=capture.window_title,
        rect_coords=capture.rect_coords,
    )


def _map_audio(audio: AudioRequest) -> AudioSettings:
    return AudioSettings(
        audio_type=audio.mode,
        mic_device_index=audio.mic_device_index,
    )


def _map_video(video: VideoRequest) -> VideoSettings:
    return VideoSettings(
        fps=video.fps,
        codec=video.codec,
        bitrate=video.bitrate,
        format=video.format,
    )


class GUIRecordingBackend(RecordingBackend):
    """Адаптер существующего GUI recording stack к core-порту."""

    def __init__(
        self,
        controller: RecordingController | None = None,
        state: RecordingState | None = None,
    ) -> None:
        self._state = state or RecordingState()
        self._controller = controller or RecordingController(self._state)

    @property
    def state(self) -> RecordingState:
        """Возвращает внутреннюю модель состояния для тестов и интеграции."""
        return self._state

    @property
    def controller(self) -> RecordingController:
        """Возвращает внутренний контроллер для тестов и интеграции."""
        return self._controller

    def get_status(self) -> RecordingStatusSnapshot:
        return RecordingStatusSnapshot(
            is_recording=self._state.is_recording(),
            is_paused=self._state.is_paused(),
            elapsed_time=self._controller.elapsed_time,
            current_file=self._state.current_output,
        )

    def start(
        self,
        output_path: Path,
        capture: CaptureRequest,
        audio: AudioRequest,
        video: VideoRequest,
        duration: int | None = None,
    ) -> tuple[bool, str | None]:
        return self._controller.start_recording(
            output_path=output_path,
            capture=_map_capture(capture),
            audio=_map_audio(audio),
            video=_map_video(video),
            duration=duration,
        )

    def stop(self) -> Path | None:
        return self._controller.stop_recording()

    def pause(self) -> bool:
        return self._controller.pause_recording()

    def resume(self) -> bool:
        return self._controller.resume_recording()
