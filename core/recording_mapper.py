"""
Маппинг core-типов записи в GUI/controller-типы.

Изолирует зависимость use-case слоя от GUI-моделей.
"""

from __future__ import annotations

from core.recording_types import (
    AudioMode,
    AudioRequest,
    CaptureMode,
    CaptureRequest,
    VideoRequest,
)
from gui.models.recording_state import (
    AudioSettings as GUIAudioSettings,
    AudioType as GUIAudioType,
    CaptureSettings as GUICaptureSettings,
    CaptureType as GUICaptureType,
    VideoSettings as GUIVideoSettings,
)


def map_capture_to_gui(capture: CaptureRequest) -> GUICaptureSettings:
    """Преобразует core-параметры захвата в типы GUI контроллера."""
    capture_type_map = {
        CaptureMode.FULL: GUICaptureType.FULL_SCREEN,
        CaptureMode.WINDOW: GUICaptureType.WINDOW,
        CaptureMode.RECT: GUICaptureType.RECTANGLE,
    }
    return GUICaptureSettings(
        capture_type=capture_type_map[capture.mode],
        window_title=capture.window_title,
        rect_coords=capture.rect_coords,
    )


def map_audio_to_gui(audio: AudioRequest) -> GUIAudioSettings:
    """Преобразует core-параметры аудио в типы GUI контроллера."""
    audio_type_map = {
        AudioMode.NONE: GUIAudioType.NONE,
        AudioMode.MIC: GUIAudioType.MICROPHONE,
        AudioMode.SYSTEM: GUIAudioType.SYSTEM,
        AudioMode.BOTH: GUIAudioType.BOTH,
    }
    return GUIAudioSettings(
        audio_type=audio_type_map[audio.mode],
        mic_device_index=audio.mic_device_index,
    )


def map_video_to_gui(video: VideoRequest) -> GUIVideoSettings:
    """Преобразует core-параметры видео в типы GUI контроллера."""
    return GUIVideoSettings(
        fps=video.fps,
        codec=video.codec,
        bitrate=video.bitrate,
        format=video.format,
    )

