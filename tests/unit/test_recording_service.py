"""
Unit тесты для RecordingService.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from core.event_bus import InMemoryEventBus, RecordingEventType
from core.recording_types import AudioMode
from core.recording_service import RecordingService


class TestRecordingService:
    """Тесты сервиса записи без GUI."""

    def test_get_status_initial(self) -> None:
        service = RecordingService()
        status = service.get_status()

        assert status["is_recording"] is False
        assert status["is_paused"] is False
        assert status["current_file"] is None

    def test_start_recording_success(self) -> None:
        service = RecordingService()
        with patch.object(
            service._controller, "start_recording", return_value=(True, None)
        ) as start_mock:
            result = service.start_recording({"area": "full", "audio": "none"})

        assert result["success"] is True
        assert "output_path" in result
        start_mock.assert_called_once()

    def test_start_recording_fails_when_already_recording(self) -> None:
        service = RecordingService()
        service._state.start_recording(Path("demo.mp4"))

        result = service.start_recording({"area": "full"})
        assert result == {"success": False, "error": "Запись уже идёт"}

    def test_stop_recording_success(self) -> None:
        service = RecordingService()
        service._state.start_recording(Path("demo.mp4"))

        with (
            patch.object(
                service._controller,
                "stop_recording",
                return_value=Path("demo.mp4"),
            ),
            patch("core.recording_service.get_config") as get_config_mock,
            patch.object(Path, "exists", return_value=False),
        ):
            get_config_mock.return_value = MagicMock()
            result = service.stop_recording()

        assert result["success"] is True
        assert result["filepath"] == "demo.mp4"

    def test_toggle_pause(self) -> None:
        service = RecordingService()
        service._state.start_recording(Path("demo.mp4"))

        def pause_side_effect() -> bool:
            service._state.pause_recording()
            return True

        with patch.object(
            service._controller, "pause_recording", side_effect=pause_side_effect
        ):
            paused = service.toggle_pause()
        assert paused == {"success": True, "is_paused": True}

        def resume_side_effect() -> bool:
            service._state.resume_recording()
            return True

        with patch.object(
            service._controller,
            "resume_recording",
            side_effect=resume_side_effect,
        ):
            resumed = service.toggle_pause()
        assert resumed == {"success": True, "is_paused": False}

    def test_normalize_internal_keys(self) -> None:
        service = RecordingService()
        normalized = service._normalize_params(
            {"area_type": "rect", "rect_coords": [1, 2, 3, 4], "audio_type": "mic"}
        )

        assert normalized["area"] == "rect"
        assert normalized["rect"] == [1, 2, 3, 4]
        assert normalized["audio"] == "mic"

    def test_build_audio_settings(self) -> None:
        service = RecordingService()
        audio = service._build_audio_settings({"audio": "both"})
        assert audio.mode == AudioMode.BOTH

    def test_publishes_started_event(self) -> None:
        bus = InMemoryEventBus()
        events = []
        bus.subscribe(RecordingEventType.STARTED, lambda e: events.append(e))
        service = RecordingService(event_bus=bus)

        with patch.object(
            service._controller, "start_recording", return_value=(True, None)
        ):
            result = service.start_recording({"area": "full", "audio": "none"})

        assert result["success"] is True
        assert len(events) == 1
        assert events[0].event_type == RecordingEventType.STARTED

    def test_publishes_error_event(self) -> None:
        bus = InMemoryEventBus()
        events = []
        bus.subscribe(RecordingEventType.ERROR, lambda e: events.append(e))
        service = RecordingService(event_bus=bus)
        service._state.start_recording(Path("demo.mp4"))

        result = service.start_recording({"area": "full"})

        assert result["success"] is False
        assert len(events) == 1
        assert events[0].payload["error"] == "Запись уже идёт"
