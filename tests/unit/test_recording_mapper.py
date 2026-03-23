"""Unit тесты для маппинга core-типов записи в GUI-типы."""

from core.recording_mapper import (
    map_audio_to_gui,
    map_capture_to_gui,
    map_video_to_gui,
)
from core.recording_types import (
    AudioMode,
    AudioRequest,
    CaptureMode,
    CaptureRequest,
    VideoRequest,
)
from gui.models.recording_state import AudioType, CaptureType


def test_map_capture_to_gui_rect() -> None:
    capture = CaptureRequest(
        mode=CaptureMode.RECT,
        window_title="",
        rect_coords=(10, 20, 300, 400),
    )

    mapped = map_capture_to_gui(capture)

    assert mapped.capture_type == CaptureType.RECTANGLE
    assert mapped.rect_coords == (10, 20, 300, 400)


def test_map_audio_to_gui_both() -> None:
    audio = AudioRequest(mode=AudioMode.BOTH, mic_device_index=2)

    mapped = map_audio_to_gui(audio)

    assert mapped.audio_type == AudioType.BOTH
    assert mapped.mic_device_index == 2


def test_map_video_to_gui() -> None:
    video = VideoRequest(fps=60, codec="libx264", bitrate="5M", format="mp4")

    mapped = map_video_to_gui(video)

    assert mapped.fps == 60
    assert mapped.codec == "libx264"
    assert mapped.bitrate == "5M"
    assert mapped.format == "mp4"

