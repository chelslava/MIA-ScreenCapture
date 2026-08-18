"""
Unit-тесты для RecordingsController
==================================
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import (
    QLineEdit,
    QListWidget,
    QStatusBar,
)

from gui.controllers.recordings_controller import RecordingsController
from gui.controllers.settings_controller import SettingsController
from gui.models.recording_state import RecentRecording, RecordingState


class TestRecordingsController:
    """Тесты контроллера недавних записей."""

    def test_filter_matching(self) -> None:
        assert RecordingsController.recording_matches_filter(
            "my_video.mp4", "2026-08-18", "video"
        )
        assert RecordingsController.recording_matches_filter(
            "my_video.mp4", "2026-08-18", "2026"
        )
        assert not RecordingsController.recording_matches_filter(
            "my_video.mp4", "2026-08-18", "xyz"
        )
        assert RecordingsController.recording_matches_filter(
            "my_video.mp4", "2026-08-18", ""
        )

    def test_refresh_recent_recordings(self, tmp_path: Path) -> None:
        rec_file = tmp_path / "rec1.mp4"
        rec_file.write_text("dummy")

        state = RecordingState()
        state.recent_recordings = [
            RecentRecording(path=rec_file, size=5, date="2026-08-18 10:00")
        ]
        settings_ctrl = MagicMock(spec=SettingsController)
        list_widget = QListWidget()
        filter_input = QLineEdit()

        ctrl = RecordingsController(
            state=state,
            settings_controller=settings_ctrl,
            recordings_list=list_widget,
            filter_input=filter_input,
        )

        with patch(
            "gui.controllers.recordings_controller.generate_thumbnail",
            return_value=None,
        ):
            ctrl.refresh_recent_recordings()

        assert list_widget.count() == 1
        item = list_widget.item(0)
        assert item is not None
        assert "rec1.mp4" in item.text()

    def test_clear_filter(self) -> None:
        state = RecordingState()
        settings_ctrl = MagicMock(spec=SettingsController)
        list_widget = QListWidget()
        filter_input = QLineEdit()
        filter_input.setText("filter text")

        ctrl = RecordingsController(
            state=state,
            settings_controller=settings_ctrl,
            recordings_list=list_widget,
            filter_input=filter_input,
        )
        ctrl.clear_recordings_filter()
        assert filter_input.text() == ""

    def test_clear_recent_recordings(self) -> None:
        state = RecordingState()
        settings_ctrl = MagicMock(spec=SettingsController)
        list_widget = QListWidget()
        filter_input = QLineEdit()
        status_bar = QStatusBar()

        ctrl = RecordingsController(
            state=state,
            settings_controller=settings_ctrl,
            recordings_list=list_widget,
            filter_input=filter_input,
            status_bar=status_bar,
        )
        ctrl.clear_recent_recordings()
        settings_ctrl.clear_recent_recordings.assert_called_once()

    def test_open_file_and_folder(self) -> None:
        state = RecordingState()
        settings_ctrl = MagicMock(spec=SettingsController)
        list_widget = QListWidget()
        filter_input = QLineEdit()

        ctrl = RecordingsController(
            state=state,
            settings_controller=settings_ctrl,
            recordings_list=list_widget,
            filter_input=filter_input,
        )

        with (
            patch("platform.system", return_value="Windows"),
            patch("os.startfile") as mock_startfile,
        ):
            ctrl.open_file("C:/test/file.mp4")
            mock_startfile.assert_called_once_with("C:/test/file.mp4")

        with (
            patch("platform.system", return_value="Windows"),
            patch("subprocess.run") as mock_run,
        ):
            ctrl.open_folder("C:/test")
            mock_run.assert_called_once_with(["explorer", "C:/test"])

    def test_open_application_logs(self) -> None:
        state = RecordingState()
        settings_ctrl = MagicMock(spec=SettingsController)
        list_widget = QListWidget()
        filter_input = QLineEdit()
        status_bar = QStatusBar()

        ctrl = RecordingsController(
            state=state,
            settings_controller=settings_ctrl,
            recordings_list=list_widget,
            filter_input=filter_input,
            status_bar=status_bar,
        )

        with patch(
            "gui.controllers.recordings_controller.open_logs_folder"
        ) as mock_logs:
            ctrl.open_application_logs()
            mock_logs.assert_called_once()
