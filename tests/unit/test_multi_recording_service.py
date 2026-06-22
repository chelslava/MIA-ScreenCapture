"""Тесты MultiRecordingService (#51)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from core.event_bus import InMemoryEventBus, RecordingEventType
from core.multi_recording_service import MultiRecordingService


class TestStartMultiRecording:
    """Тесты запуска мультиисточниковой записи."""

    def test_start_success_publishes_started_event(self) -> None:
        """Успешный старт публикует STARTED с outputs."""
        bus = InMemoryEventBus()
        events: list = []
        bus.subscribe(RecordingEventType.STARTED, events.append)
        service = MultiRecordingService(event_bus=bus)

        mock_recorder = MagicMock()
        mock_recorder.start.return_value = (
            True,
            {
                "primary": Path("D:/out/video_primary.mp4"),
                "secondary": Path("D:/out/video_secondary.mp4"),
            },
            None,
        )

        with (
            patch("core.multi_recording_service.MultiSourceRecorder") as cls,
            patch(
                "core.multi_recording_service.build_recording_output_path",
                return_value=Path("D:/out/video.mp4"),
            ),
        ):
            cls.return_value = mock_recorder
            result = service.start_multi_recording(
                {
                    "sources": [
                        {
                            "label": "primary",
                            "area": "full",
                            "monitor_index": 0,
                        },
                        {
                            "label": "secondary",
                            "area": "full",
                            "monitor_index": 1,
                        },
                    ]
                }
            )

        assert result["success"] is True
        assert result["outputs"] == {
            "primary": str(Path("D:/out/video_primary.mp4")),
            "secondary": str(Path("D:/out/video_secondary.mp4")),
        }
        assert len(events) == 1

    def test_start_rejects_fewer_than_two_sources(self) -> None:
        """Меньше 2 источников -> ошибка, без создания MultiSourceRecorder."""
        service = MultiRecordingService()

        with patch("core.multi_recording_service.MultiSourceRecorder") as cls:
            result = service.start_multi_recording(
                {"sources": [{"label": "only"}]}
            )

        assert result["success"] is False
        assert "минимум 2" in result["error"]
        cls.assert_not_called()

    def test_start_rejects_missing_label(self) -> None:
        """Источник без label -> ошибка."""
        service = MultiRecordingService()

        with patch("core.multi_recording_service.MultiSourceRecorder") as cls:
            result = service.start_multi_recording(
                {
                    "sources": [
                        {"area": "full"},
                        {"label": "secondary", "area": "full"},
                    ]
                }
            )

        assert result["success"] is False
        cls.assert_not_called()

    def test_start_rejects_invalid_rect(self) -> None:
        """area='rect' без валидных координат -> ошибка."""
        service = MultiRecordingService()

        with patch("core.multi_recording_service.MultiSourceRecorder") as cls:
            result = service.start_multi_recording(
                {
                    "sources": [
                        {"label": "a", "area": "rect"},
                        {"label": "b", "area": "full"},
                    ]
                }
            )

        assert result["success"] is False
        cls.assert_not_called()

    def test_start_rejects_when_already_active(self) -> None:
        """Повторный старт при активной мульти-записи -> отказ."""
        service = MultiRecordingService()
        active_recorder = MagicMock()
        active_recorder.is_active = True
        service._recorder = active_recorder

        with patch("core.multi_recording_service.MultiSourceRecorder") as cls:
            result = service.start_multi_recording(
                {
                    "sources": [
                        {"label": "a", "area": "full"},
                        {"label": "b", "area": "full"},
                    ]
                }
            )

        assert result["success"] is False
        assert "уже активна" in result["error"]
        cls.assert_not_called()

    def test_start_propagates_recorder_failure(self) -> None:
        """Неудача MultiSourceRecorder.start() пробрасывается как ошибка."""
        bus = InMemoryEventBus()
        events: list = []
        bus.subscribe(RecordingEventType.ERROR, events.append)
        service = MultiRecordingService(event_bus=bus)

        mock_recorder = MagicMock()
        mock_recorder.start.return_value = (
            False,
            None,
            "Не удалось запустить запись источника 'b'",
        )

        with (
            patch("core.multi_recording_service.MultiSourceRecorder") as cls,
            patch(
                "core.multi_recording_service.build_recording_output_path",
                return_value=Path("D:/out/video.mp4"),
            ),
        ):
            cls.return_value = mock_recorder
            result = service.start_multi_recording(
                {
                    "sources": [
                        {"label": "a", "area": "full"},
                        {"label": "b", "area": "full"},
                    ]
                }
            )

        assert result["success"] is False
        assert "источника 'b'" in result["error"]
        assert service._recorder is None
        assert len(events) == 1


class TestStopMultiRecording:
    """Тесты остановки мультиисточниковой записи."""

    def test_stop_success_publishes_stopped_and_updates_recents(self) -> None:
        """Успешная остановка публикует STOPPED и обновляет recent_recordings."""
        bus = InMemoryEventBus()
        events: list = []
        bus.subscribe(RecordingEventType.STOPPED, events.append)
        service = MultiRecordingService(event_bus=bus)

        active_recorder = MagicMock()
        active_recorder.is_active = True
        active_recorder.stop.return_value = {
            "primary": {
                "success": True,
                "output_path": "D:/out/video_primary.mp4",
            },
            "secondary": {"success": False, "output_path": None},
        }
        service._recorder = active_recorder

        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.stat") as mock_stat,
            patch(
                "core.multi_recording_service.get_config"
            ) as mock_get_config,
        ):
            mock_stat.return_value.st_size = 12345
            result = service.stop_multi_recording()

        assert result["success"] is True
        assert service._recorder is None
        mock_get_config.return_value.add_recent_recording.assert_called_once_with(
            str(Path("D:/out/video_primary.mp4")), 12345
        )
        assert len(events) == 1

    def test_stop_rejects_when_not_active(self) -> None:
        """Остановка без активной мульти-записи -> отказ."""
        service = MultiRecordingService()

        result = service.stop_multi_recording()

        assert result["success"] is False
        assert "не активна" in result["error"]


class TestGetMultiStatus:
    """Тесты статуса мультиисточниковой записи."""

    def test_status_when_idle(self) -> None:
        service = MultiRecordingService()

        status = service.get_multi_status()

        assert status == {"active": False, "sources": {}}

    def test_status_when_active_delegates_to_recorder(self) -> None:
        service = MultiRecordingService()
        active_recorder = MagicMock()
        active_recorder.get_status.return_value = {
            "active": True,
            "sources": {"primary": {"state": "recording"}},
        }
        service._recorder = active_recorder

        status = service.get_multi_status()

        assert status["active"] is True
        active_recorder.get_status.assert_called_once()
