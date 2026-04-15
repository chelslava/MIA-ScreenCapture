"""
Представления GUI
=================

Модуль содержит компоненты представления (views) для GUI.
"""

from gui.views.api_settings_view import ApiSettingsView
from gui.views.audio_view import AudioView
from gui.views.capture_view import CaptureView
from gui.views.output_view import OutputView
from gui.views.readiness_center_view import ReadinessCenterView
from gui.views.video_view import VideoView

__all__ = [
    "CaptureView",
    "AudioView",
    "VideoView",
    "OutputView",
    "ApiSettingsView",
    "ReadinessCenterView",
]
