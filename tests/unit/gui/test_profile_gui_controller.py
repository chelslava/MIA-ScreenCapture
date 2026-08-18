"""
Unit-тесты для ProfileGUIController
==================================
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QComboBox, QStatusBar

from core.recording_types import AudioMode, CaptureMode
from gui.controllers.profile_gui_controller import ProfileGUIController
from gui.models.recording_state import RecordingState
from gui.views.audio_view import AudioView
from gui.views.capture_view import CaptureView
from gui.views.video_view import VideoView


class TestProfileGUIController:
    """Тесты контроллера интерфейса профилей."""

    def test_init_profiles(self) -> None:
        ctrl = ProfileGUIController()
        combo = QComboBox()

        mock_profile = MagicMock()
        mock_profile.id = "p1"
        mock_profile.name = "Test Profile"
        mock_profile.icon = "🎬"
        mock_profile.is_default = True

        with patch(
            "gui.controllers.profile_gui_controller.get_profile_storage"
        ) as mock_storage:
            mock_storage.return_value.list_profiles.return_value = [
                mock_profile
            ]
            ctrl.init_profiles(combo)

        assert combo.count() == 1
        assert "Test Profile" in combo.itemText(0)
        assert combo.itemData(0) == "p1"

    def test_on_profile_combo_changed(self) -> None:
        ctrl = ProfileGUIController()
        combo = QComboBox()
        combo.addItem("Profile 1", "p1")

        mock_profile = MagicMock()
        mock_profile.id = "p1"
        apply_cb = MagicMock()

        with patch(
            "gui.controllers.profile_gui_controller.get_profile_storage"
        ) as mock_storage:
            mock_storage.return_value.get_profile.return_value = mock_profile
            ctrl.on_profile_combo_changed(0, combo, apply_cb)

        apply_cb.assert_called_once_with(mock_profile)

    def test_apply_profile_settings(self) -> None:
        ctrl = ProfileGUIController()

        mock_profile = MagicMock()
        mock_profile.id = "p1"
        mock_profile.name = "My Profile"
        mock_profile.video.fps = 60
        mock_profile.video.codec = "h264"
        mock_profile.video.bitrate = "5M"
        mock_profile.video.format = "mp4"
        mock_profile.video.preset = "fast"
        mock_profile.audio.record_mic = True
        mock_profile.audio.record_system = False
        mock_profile.capture.area_type = "full"
        mock_profile.capture.window_title = ""
        mock_profile.capture.rect_coords = None

        video_view = MagicMock(spec=VideoView)
        audio_view = MagicMock(spec=AudioView)
        capture_view = MagicMock(spec=CaptureView)
        state = RecordingState()
        combo = QComboBox()
        combo.addItem("My Profile", "p1")
        status_bar = QStatusBar()

        ctrl.apply_profile_settings(
            mock_profile,
            video_view=video_view,
            audio_view=audio_view,
            capture_view=capture_view,
            state=state,
            combo=combo,
            status_bar=status_bar,
        )

        video_view.set_fps.assert_called_once_with(60)
        assert state.audio.audio_type == AudioMode.MIC
        capture_view.set_capture_type.assert_called_once_with(CaptureMode.FULL)
