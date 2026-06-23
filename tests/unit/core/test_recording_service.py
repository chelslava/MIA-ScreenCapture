"""
Unit тесты для RecordingService.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from core.event_bus import InMemoryEventBus, RecordingEventType
from core.recording_backend import RecordingStatusSnapshot
from core.recording_service import RecordingService
from core.recording_types import AudioMode
from exceptions import RecordingError


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
        self.switch_capture_source_result = (True, None)
        self.switch_capture_source_calls: list[object] = []

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

    def switch_capture_source(self, capture):
        self.switch_capture_source_calls.append(capture)
        return self.switch_capture_source_result


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
        assert result == {
            "success": False,
            "error": "Recording already in progress",
        }

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
            get_config_mock.return_value.settings.video.verify_on_complete = (
                False
            )
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

    def test_switch_capture_source_success(self) -> None:
        """#48: успешное переключение делегирует в backend с CaptureRequest."""
        backend = FakeBackend()
        backend.status = RecordingStatusSnapshot(
            is_recording=True,
            is_paused=False,
            elapsed_time=0.0,
            current_file=Path("demo.mp4"),
        )
        service = RecordingService(backend=backend)

        result = service.switch_capture_source(
            {"area": "window", "window_title": "Notepad"}
        )

        assert result == {"success": True}
        assert len(backend.switch_capture_source_calls) == 1
        capture_request = backend.switch_capture_source_calls[0]
        assert capture_request.window_title == "Notepad"

    def test_switch_capture_source_fails_when_not_recording(self) -> None:
        """#48: переключение недоступно, если запись не активна."""
        service = RecordingService(backend=FakeBackend())

        result = service.switch_capture_source({"area": "full"})

        assert result["success"] is False
        assert "not active" in result["error"]

    def test_switch_capture_source_propagates_backend_failure(self) -> None:
        """#48: ошибка backend пробрасывается в результат."""
        backend = FakeBackend()
        backend.status = RecordingStatusSnapshot(
            is_recording=True,
            is_paused=False,
            elapsed_time=0.0,
            current_file=Path("demo.mp4"),
        )
        backend.switch_capture_source_result = (
            False,
            "Таймаут переключения источника захвата",
        )
        service = RecordingService(backend=backend)

        result = service.switch_capture_source({"area": "full"})

        assert result == {
            "success": False,
            "error": "Таймаут переключения источника захвата",
        }

    def test_switch_capture_source_rejects_invalid_rect(self) -> None:
        """#48: невалидный rect не доходит до backend."""
        backend = FakeBackend()
        backend.status = RecordingStatusSnapshot(
            is_recording=True,
            is_paused=False,
            elapsed_time=0.0,
            current_file=Path("demo.mp4"),
        )
        service = RecordingService(backend=backend)

        result = service.switch_capture_source(
            {"area": "rect", "rect": [1, 2, 3]}
        )

        assert result["success"] is False
        assert backend.switch_capture_source_calls == []

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
        assert events[0].payload["error"] == "Recording already in progress"

    def test_build_output_path_accepts_directory(self) -> None:
        """При передаче директории должен генерироваться файл внутри неё."""
        service = RecordingService(backend=FakeBackend())
        cfg = MagicMock()
        cfg.settings.video.format = "mp4"
        cfg.get_output_path.return_value = Path("recording_default.mp4")
        directory = Path("D:/Recordings")

        with patch("core.recording_service.get_config", return_value=cfg):
            path = service._build_output_path(
                {"output_path": "D:/Recordings/"}
            )

        assert path.parent == directory
        assert path.suffix == ".mp4"

    def test_build_output_path_adds_extension_for_filename_without_suffix(
        self,
    ) -> None:
        """Если extension не передан, он должен быть добавлен из конфига."""
        service = RecordingService(backend=FakeBackend())
        cfg = MagicMock()
        cfg.settings.video.format = "mkv"
        cfg.get_output_path.return_value = Path("recording_default.mkv")

        with patch("core.recording_service.get_config", return_value=cfg):
            path = service._build_output_path(
                {"output_path": "D:/Recordings/session_01"}
            )

        assert str(path).endswith("session_01.mkv")


class TestRectCoordsValidation:
    """Тесты валидации координат области захвата."""

    def test_valid_rect_coords(self) -> None:
        """Корректные координаты проходят валидацию."""
        service = RecordingService(backend=FakeBackend())
        result = service._validate_rect_coords([100, 200, 500, 600])
        assert result == (100, 200, 500, 600)

    def test_valid_rect_coords_tuple(self) -> None:
        """Кортеж координат проходит валидацию."""
        service = RecordingService(backend=FakeBackend())
        result = service._validate_rect_coords((0, 0, 1920, 1080))
        assert result == (0, 0, 1920, 1080)

    def test_invalid_rect_coords_wrong_count(self) -> None:
        """Ошибка при количестве координат != 4."""
        service = RecordingService(backend=FakeBackend())
        try:
            service._validate_rect_coords([100, 200, 500])
            assert False, "Должен быть выброшен ValueError"
        except ValueError as e:
            assert "4 coordinates" in str(e)

    def test_invalid_rect_coords_x2_le_x1(self) -> None:
        """Ошибка при x2 <= x1."""
        service = RecordingService(backend=FakeBackend())
        try:
            service._validate_rect_coords([500, 100, 100, 600])
            assert False, "Должен быть выброшен ValueError"
        except ValueError as e:
            assert "x2 must be greater than x1" in str(e)

    def test_invalid_rect_coords_y2_le_y1(self) -> None:
        """Ошибка при y2 <= y1."""
        service = RecordingService(backend=FakeBackend())
        try:
            service._validate_rect_coords([100, 600, 500, 100])
            assert False, "Должен быть выброшен ValueError"
        except ValueError as e:
            assert "y2 must be greater than y1" in str(e)

    def test_invalid_rect_coords_negative(self) -> None:
        """Ошибка при отрицательных координатах."""
        service = RecordingService(backend=FakeBackend())
        try:
            service._validate_rect_coords([-100, 0, 500, 600])
            assert False, "Должен быть выброшен ValueError"
        except ValueError as e:
            assert "negative" in str(e)

    def test_build_capture_settings_rect_without_coords(self) -> None:
        """Ошибка при area=rect без координат."""
        service = RecordingService(backend=FakeBackend())
        try:
            service._build_capture_settings({"area": "rect"})
            assert False, "Должен быть выброшен ValueError"
        except ValueError as e:
            assert "rect_coords" in str(e)

    def test_build_capture_settings_rect_with_valid_coords(self) -> None:
        """Корректные координаты при area=rect."""
        service = RecordingService(backend=FakeBackend())
        result = service._build_capture_settings(
            {"area": "rect", "rect": [0, 0, 800, 600]}
        )
        assert result.rect_coords == (0, 0, 800, 600)

    def test_build_capture_settings_full_without_coords(self) -> None:
        """Fallback координаты при area=full без rect."""
        service = RecordingService(backend=FakeBackend())
        result = service._build_capture_settings({"area": "full"})
        assert result.rect_coords == (0, 0, 1920, 1080)


class TestRecordingServiceExtraEdgeCases:
    """Дополнительные тесты для покрытия непокрытых веток."""

    def test_event_bus_property_returns_bus(self) -> None:
        bus = InMemoryEventBus()
        service = RecordingService(event_bus=bus, backend=FakeBackend())
        assert service.event_bus is bus

    def test_start_recording_fails_when_backend_returns_failure(self) -> None:
        backend = FakeBackend()
        backend.start_result = (False, "Нет доступа к экрану")
        service = RecordingService(backend=backend)
        result = service.start_recording({"area": "full", "audio": "none"})
        assert result["success"] is False
        assert "Нет доступа к экрану" in result["error"]

    def test_start_recording_catches_recording_error(self) -> None:
        class ErrorBackend(FakeBackend):
            def start(self, **kwargs):
                raise RecordingError("тест ошибки")

        service = RecordingService(backend=ErrorBackend())
        result = service.start_recording({"area": "full", "audio": "none"})
        assert result["success"] is False
        assert "тест ошибки" in result["error"]

    def test_start_recording_catches_oserror(self) -> None:
        class ErrorBackend(FakeBackend):
            def start(self, **kwargs):
                raise OSError("disk full")

        service = RecordingService(backend=ErrorBackend())
        result = service.start_recording({"area": "full", "audio": "none"})
        assert result["success"] is False
        assert "disk full" in result["error"]

    def test_stop_recording_returns_failure_when_stop_returns_none(
        self,
    ) -> None:
        backend = FakeBackend()
        backend.status = RecordingStatusSnapshot(
            is_recording=True,
            is_paused=False,
            elapsed_time=0.0,
            current_file=Path("demo.mp4"),
        )
        backend.stop_result = None
        service = RecordingService(backend=backend)
        result = service.stop_recording()
        assert result["success"] is False

    def test_stop_recording_ignores_oserror_on_recent_recordings_update(
        self,
    ) -> None:
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
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "stat", side_effect=OSError("disk error")),
        ):
            get_config_mock.return_value.settings.video.verify_on_complete = (
                False
            )
            result = service.stop_recording()
        assert result["success"] is True

    def test_stop_recording_skips_verification_when_disabled(self) -> None:
        """verify_on_complete=False -> verify_video_integrity не вызывается."""
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
            patch(
                "core.recording_service.verify_video_integrity"
            ) as mock_verify,
        ):
            get_config_mock.return_value.settings.video.verify_on_complete = (
                False
            )
            result = service.stop_recording()

        assert "integrity" not in result
        mock_verify.assert_not_called()

    def test_stop_recording_includes_valid_integrity_result(self) -> None:
        """Валидный результат проверки попадает в result['integrity']."""
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
            patch(
                "core.recording_service.verify_video_integrity"
            ) as mock_verify,
        ):
            get_config_mock.return_value.settings.video.verify_on_complete = (
                True
            )
            mock_verify.return_value = MagicMock(valid=True, error=None)
            result = service.stop_recording()

        assert result["integrity"] == {"valid": True, "repaired": False}

    def test_stop_recording_reports_invalid_without_auto_repair(
        self,
    ) -> None:
        """Невалидный файл без auto_repair_corrupted -> репорт без попытки repair."""
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
            patch(
                "core.recording_service.verify_video_integrity"
            ) as mock_verify,
            patch(
                "core.recording_service.attempt_repair_video"
            ) as mock_repair,
        ):
            get_config_mock.return_value.settings.video.verify_on_complete = (
                True
            )
            get_config_mock.return_value.settings.video.auto_repair_corrupted = False
            mock_verify.return_value = MagicMock(
                valid=False, error="moov atom not found"
            )
            result = service.stop_recording()

        assert result["integrity"] == {
            "valid": False,
            "repaired": False,
            "error": "moov atom not found",
        }
        mock_repair.assert_not_called()

    def test_stop_recording_attempts_repair_when_enabled_and_succeeds(
        self,
    ) -> None:
        """auto_repair_corrupted=True и успешный ремукс -> valid/repaired=True."""
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
            patch(
                "core.recording_service.verify_video_integrity"
            ) as mock_verify,
            patch(
                "core.recording_service.attempt_repair_video"
            ) as mock_repair,
        ):
            get_config_mock.return_value.settings.video.verify_on_complete = (
                True
            )
            get_config_mock.return_value.settings.video.auto_repair_corrupted = True
            mock_verify.return_value = MagicMock(
                valid=False, error="moov atom not found"
            )
            mock_repair.return_value = MagicMock(repaired=True, error=None)
            result = service.stop_recording()

        assert result["integrity"] == {"valid": True, "repaired": True}
        mock_repair.assert_called_once()

    def test_stop_recording_reports_repair_failure(self) -> None:
        """Неудачный repair -> репорт остаётся невалидным."""
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
            patch(
                "core.recording_service.verify_video_integrity"
            ) as mock_verify,
            patch(
                "core.recording_service.attempt_repair_video"
            ) as mock_repair,
        ):
            get_config_mock.return_value.settings.video.verify_on_complete = (
                True
            )
            get_config_mock.return_value.settings.video.auto_repair_corrupted = True
            mock_verify.return_value = MagicMock(
                valid=False, error="moov atom not found"
            )
            mock_repair.return_value = MagicMock(
                repaired=False, error="ffmpeg decode error"
            )
            result = service.stop_recording()

        assert result["integrity"] == {
            "valid": False,
            "repaired": False,
            "error": "ffmpeg decode error",
        }

    def test_stop_recording_verification_failure_does_not_block_stop(
        self,
    ) -> None:
        """Неожиданное исключение в верификации не должно ломать stop()."""
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
            patch(
                "core.recording_service.verify_video_integrity",
                side_effect=RuntimeError("unexpected"),
            ),
        ):
            get_config_mock.return_value.settings.video.verify_on_complete = (
                True
            )
            result = service.stop_recording()

        assert result["success"] is True
        assert "integrity" not in result

    def test_toggle_pause_returns_error_when_not_recording(self) -> None:
        service = RecordingService(backend=FakeBackend())
        result = service.toggle_pause()
        assert result["success"] is False
        assert "Recording is not active" in result["error"]

    def test_toggle_pause_returns_error_when_resume_fails(self) -> None:
        backend = FakeBackend()
        backend.status = RecordingStatusSnapshot(
            is_recording=False,
            is_paused=True,
            elapsed_time=0.0,
            current_file=Path("demo.mp4"),
        )
        backend.resume_result = False
        service = RecordingService(backend=backend)
        result = service.toggle_pause()
        assert result["success"] is False
        assert "Failed to resume" in result["error"]

    def test_toggle_pause_returns_error_when_pause_fails(self) -> None:
        backend = FakeBackend()
        backend.status = RecordingStatusSnapshot(
            is_recording=True,
            is_paused=False,
            elapsed_time=0.0,
            current_file=Path("demo.mp4"),
        )
        backend.pause_result = False
        service = RecordingService(backend=backend)
        result = service.toggle_pause()
        assert result["success"] is False
        assert "Failed to pause" in result["error"]

    def test_get_recordings_returns_list(self) -> None:
        service = RecordingService(backend=FakeBackend())
        with patch("core.recording_service.get_config") as mock_cfg:
            mock_cfg.return_value.settings.recent_recordings = [
                {"path": "demo.mp4"}
            ]
            recordings = service.get_recordings()
        assert recordings == [{"path": "demo.mp4"}]

    def test_stop_active_recording_if_any_returns_none_when_idle(
        self,
    ) -> None:
        service = RecordingService(backend=FakeBackend())
        result = service.stop_active_recording_if_any()
        assert result is None

    def test_stop_active_recording_if_any_stops_when_recording(
        self,
    ) -> None:
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
            result = service.stop_active_recording_if_any()
        assert result is not None
        assert result["success"] is True
