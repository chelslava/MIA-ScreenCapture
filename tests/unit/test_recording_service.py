"""
Unit тесты для RecordingService.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from core.event_bus import InMemoryEventBus, RecordingEventType
from core.recording_backend import RecordingStatusSnapshot
from core.recording_service import RecordingService
from core.recording_types import AudioMode


class FakeBackend:
    def __init__(self) -> None:
        self.status = RecordingStatusSnapshot(
            is_recording=False,
            is_paused=False,
            elapsed_time=0.0,
            current_file=None,
        )
        self.start_result = (True, None)
        self.stop_result = Path("demo.mp4")
        self.pause_result = True
        self.resume_result = True

    def get_status(self) -> RecordingStatusSnapshot:
        return self.status

    def start(self, output_path, capture, audio, video, duration=None):
        if self.start_result[0]:
            self.status = RecordingStatusSnapshot(
                is_recording=True,
                is_paused=False,
                elapsed_time=0.0,
                current_file=output_path,
            )
        return self.start_result

    def stop(self):
        if self.stop_result is not None:
            self.status = RecordingStatusSnapshot(
                is_recording=False,
                is_paused=False,
                elapsed_time=0.0,
                current_file=self.stop_result,
            )
        return self.stop_result

    def pause(self) -> bool:
        if self.pause_result:
            self.status = RecordingStatusSnapshot(
                is_recording=False,
                is_paused=True,
                elapsed_time=self.status.elapsed_time,
                current_file=self.status.current_file,
            )
        return self.pause_result

    def resume(self) -> bool:
        if self.resume_result:
            self.status = RecordingStatusSnapshot(
                is_recording=True,
                is_paused=False,
                elapsed_time=self.status.elapsed_time,
                current_file=self.status.current_file,
            )
        return self.resume_result


class TestRecordingService:
    """Тесты сервиса записи без GUI."""

    def test_get_status_initial(self) -> None:
        service = RecordingService(backend=FakeBackend())
        status = service.get_status()

        assert status["is_recording"] is False
        assert status["is_paused"] is False
        assert status["current_file"] is None

    def test_start_recording_success(self) -> None:
        backend = FakeBackend()
        service = RecordingService(backend=backend)
        result = service.start_recording({"area": "full", "audio": "none"})

        assert result["success"] is True
        assert "output_path" in result
        assert backend.status.is_recording is True

    def test_start_recording_fails_when_already_recording(self) -> None:
        backend = FakeBackend()
        backend.status = RecordingStatusSnapshot(
            is_recording=True,
            is_paused=False,
            elapsed_time=0.0,
            current_file=Path("demo.mp4"),
        )
        service = RecordingService(backend=backend)

        result = service.start_recording({"area": "full"})
        assert result == {"success": False, "error": "Запись уже идёт"}

    def test_stop_recording_success(self) -> None:
        backend = FakeBackend()
        backend.status = RecordingStatusSnapshot(
            is_recording=True,
            is_paused=False,
            elapsed_time=0.0,
            current_file=Path("demo.mp4"),
        )
        service = RecordingService(backend=backend)

        with (
            patch("core.recording_service.get_config") as get_config_mock,
            patch.object(Path, "exists", return_value=False),
        ):
            get_config_mock.return_value = MagicMock()
            result = service.stop_recording()

        assert result["success"] is True
        assert result["filepath"] == "demo.mp4"

    def test_toggle_pause(self) -> None:
        backend = FakeBackend()
        backend.status = RecordingStatusSnapshot(
            is_recording=True,
            is_paused=False,
            elapsed_time=0.0,
            current_file=Path("demo.mp4"),
        )
        service = RecordingService(backend=backend)
        paused = service.toggle_pause()
        assert paused == {"success": True, "is_paused": True}

        resumed = service.toggle_pause()
        assert resumed == {"success": True, "is_paused": False}

    def test_normalize_internal_keys(self) -> None:
        service = RecordingService(backend=FakeBackend())
        normalized = service._normalize_params(
            {
                "area_type": "rect",
                "rect_coords": [1, 2, 3, 4],
                "audio_type": "mic",
            }
        )

        assert normalized["area"] == "rect"
        assert normalized["rect"] == [1, 2, 3, 4]
        assert normalized["audio"] == "mic"

    def test_build_audio_settings(self) -> None:
        service = RecordingService(backend=FakeBackend())
        audio = service._build_audio_settings({"audio": "both"})
        assert audio.mode == AudioMode.BOTH

    def test_publishes_started_event(self) -> None:
        bus = InMemoryEventBus()
        events = []
        bus.subscribe(RecordingEventType.STARTED, lambda e: events.append(e))
        service = RecordingService(event_bus=bus, backend=FakeBackend())
        result = service.start_recording({"area": "full", "audio": "none"})

        assert result["success"] is True
        assert len(events) == 1
        assert events[0].event_type == RecordingEventType.STARTED

    def test_publishes_error_event(self) -> None:
        bus = InMemoryEventBus()
        events = []
        bus.subscribe(RecordingEventType.ERROR, lambda e: events.append(e))
        backend = FakeBackend()
        backend.status = RecordingStatusSnapshot(
            is_recording=True,
            is_paused=False,
            elapsed_time=0.0,
            current_file=Path("demo.mp4"),
        )
        service = RecordingService(event_bus=bus, backend=backend)

        result = service.start_recording({"area": "full"})

        assert result["success"] is False
        assert len(events) == 1
        assert events[0].payload["error"] == "Запись уже идёт"
