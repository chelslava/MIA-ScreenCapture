"""
Unit-тесты для ReadinessController
=================================
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from core.readiness import ReadinessSnapshot
from core.recording_types import AudioMode, CaptureMode
from gui.controllers.readiness_controller import ReadinessController
from gui.models.recording_state import AudioSettings, CaptureSettings
from recorder.utils import FFmpegStatus


class TestReadinessController:
    """Тесты контроллера проверки готовности."""

    def test_check_dependencies(self) -> None:
        readiness_service = MagicMock()
        ctrl = ReadinessController(readiness_service=readiness_service)

        mock_status = FFmpegStatus(
            available=True, version="6.0", path="ffmpeg.exe"
        )
        callback = MagicMock()

        with patch(
            "gui.controllers.readiness_controller.check_ffmpeg",
            return_value=mock_status,
        ):
            ctrl.check_dependencies(callback)

        callback.assert_called_once_with(mock_status, None)

    def test_request_readiness_refresh(self, tmp_path: Path) -> None:
        readiness_service = MagicMock()
        mock_snapshot = ReadinessSnapshot(issues=())
        readiness_service.evaluate.return_value = mock_snapshot

        ctrl = ReadinessController(readiness_service=readiness_service)

        capture = CaptureSettings(capture_type=CaptureMode.FULL)
        audio = AudioSettings(audio_type=AudioMode.NONE)
        output_path = tmp_path / "out.mp4"

        callback = MagicMock()
        req_id = ctrl.request_readiness_refresh(
            capture=capture,
            audio=audio,
            output_path=output_path,
            on_completed=callback,
        )

        assert req_id == 1
        assert ctrl.is_request_current(1)
        callback.assert_called_once_with(
            1, mock_snapshot, None, capture, audio
        )

    def test_store_and_resolve_cached_snapshot(self, tmp_path: Path) -> None:
        readiness_service = MagicMock()
        ctrl = ReadinessController(readiness_service=readiness_service)

        capture = CaptureSettings(capture_type=CaptureMode.FULL)
        audio = AudioSettings(audio_type=AudioMode.NONE)
        output_path = tmp_path / "out.mp4"

        mock_snapshot = ReadinessSnapshot(issues=())

        ctrl.store_readiness_result(mock_snapshot, capture, audio, output_path)

        # Совпадающие параметры возвращают кэш
        cached = ctrl.resolve_cached_snapshot(capture, audio, output_path)
        assert cached is mock_snapshot

        # Другие параметры возвращают None
        other_path = tmp_path / "other.mp4"
        assert ctrl.resolve_cached_snapshot(capture, audio, other_path) is None

    def test_handle_readiness_action(self) -> None:
        readiness_service = MagicMock()
        ctrl = ReadinessController(readiness_service=readiness_service)

        mock_handler = MagicMock()
        handlers = {"choose_output_path": mock_handler}

        ctrl.handle_readiness_action("Папка вывода", handlers)
        mock_handler.assert_called_once()
