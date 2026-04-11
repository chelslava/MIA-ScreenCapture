"""Тесты readiness-модели перед стартом записи."""

from pathlib import Path

from core.readiness import RecordingReadinessService
from gui.models.recording_state import (
    AudioSettings,
    AudioType,
    CaptureSettings,
    CaptureType,
)


class TestRecordingReadinessService:
    """Проверки классификации blocking/warning/ready состояний."""

    def test_ffmpeg_missing_is_blocking(self) -> None:
        """Отсутствие FFmpeg должно блокировать старт."""
        service = RecordingReadinessService()
        service._ffmpeg_checker = lambda: (False, None)
        service._window_provider = lambda: []
        service._audio_devices_provider = lambda: {"input": []}

        snapshot = service.evaluate(
            capture=CaptureSettings(),
            audio=AudioSettings(),
            output_path=Path("capture.mp4"),
        )

        assert snapshot.is_ready is False
        assert snapshot.blocking_issues[0].code == "ffmpeg_missing"

    def test_missing_window_for_window_capture_is_blocking(self) -> None:
        """Режим захвата окна блокируется, если окно не найдено."""
        service = RecordingReadinessService()
        service._ffmpeg_checker = lambda: (True, "7.0")
        service._window_provider = lambda: [{"title": "Explorer"}]
        service._audio_devices_provider = lambda: {"input": []}

        snapshot = service.evaluate(
            capture=CaptureSettings(
                capture_type=CaptureType.WINDOW,
                window_title="Browser",
            ),
            audio=AudioSettings(),
            output_path=Path("capture.mp4"),
        )

        assert snapshot.is_ready is False
        assert snapshot.blocking_issues[0].code == "window_missing"

    def test_missing_microphone_is_blocking_for_mic_mode(self) -> None:
        """Микрофонный режим без доступных input-устройств блокирует старт."""
        service = RecordingReadinessService()
        service._ffmpeg_checker = lambda: (True, "7.0")
        service._window_provider = lambda: []
        service._audio_devices_provider = lambda: {"input": []}

        snapshot = service.evaluate(
            capture=CaptureSettings(),
            audio=AudioSettings(audio_type=AudioType.MIC),
            output_path=Path("capture.mp4"),
        )

        assert snapshot.is_ready is False
        assert snapshot.blocking_issues[0].code == "microphone_missing"

    def test_default_microphone_is_warning(self) -> None:
        """Отсутствие явного выбора микрофона даёт warning, а не blocking."""
        service = RecordingReadinessService()
        service._ffmpeg_checker = lambda: (True, "7.0")
        service._window_provider = lambda: []
        service._audio_devices_provider = lambda: {
            "input": [{"id": 1, "name": "Mic"}]
        }

        snapshot = service.evaluate(
            capture=CaptureSettings(),
            audio=AudioSettings(audio_type=AudioType.MIC),
            output_path=Path("capture.mp4"),
        )

        assert snapshot.is_ready is True
        assert snapshot.warning_issues[0].code == "microphone_default"
