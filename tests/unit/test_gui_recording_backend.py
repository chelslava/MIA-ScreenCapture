"""Unit тесты GUI-backed адаптера записи."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from core.recording_types import (
    AudioMode,
    AudioRequest,
    CaptureMode,
    CaptureRequest,
    VideoRequest,
)
from gui.backends.recording_backend import GUIRecordingBackend
from gui.models.recording_state import AudioType, CaptureType


def test_get_status_initial() -> None:
    backend = GUIRecordingBackend()

    status = backend.get_status()

    assert status.is_recording is False
    assert status.is_paused is False
    assert status.current_file is None


def test_start_maps_core_types_to_gui_controller_types() -> None:
    controller = MagicMock()
    controller.start_recording.return_value = (True, None)
    backend = GUIRecordingBackend(controller=controller)

    result = backend.start(
        output_path=Path("out.mp4"),
        capture=CaptureRequest(
            mode=CaptureMode.RECT,
            window_title="",
            rect_coords=(1, 2, 3, 4),
        ),
        audio=AudioRequest(mode=AudioMode.BOTH, mic_device_index=7),
        video=VideoRequest(fps=60, codec="libx264", bitrate="5M", format="mp4"),
        duration=30,
    )

    assert result == (True, None)
    kwargs = controller.start_recording.call_args.kwargs
    assert kwargs["capture"].capture_type == CaptureType.RECTANGLE
    assert kwargs["capture"].rect_coords == (1, 2, 3, 4)
    assert kwargs["audio"].audio_type == AudioType.BOTH
    assert kwargs["audio"].mic_device_index == 7
    assert kwargs["video"].fps == 60
    assert kwargs["duration"] == 30


def test_pause_resume_and_stop_delegate_to_controller() -> None:
    controller = MagicMock()
    controller.pause_recording.return_value = True
    controller.resume_recording.return_value = True
    controller.stop_recording.return_value = Path("out.mp4")
    backend = GUIRecordingBackend(controller=controller)

    assert backend.pause() is True
    assert backend.resume() is True
    assert backend.stop() == Path("out.mp4")


@patch("gui.backends.recording_backend.RecordingController")
def test_default_backend_uses_shared_state_with_controller(
    controller_cls: MagicMock,
) -> None:
    controller_instance = MagicMock()
    controller_cls.return_value = controller_instance

    backend = GUIRecordingBackend()

    controller_cls.assert_called_once_with(backend.state)
    assert backend.controller is controller_instance


# ====================
# Дополнительные тесты для T-1.3
# ====================


def test_start_recording_already_recording() -> None:
    """Попытка старта при активной записи должна делегироваться контроллеру."""
    controller = MagicMock()
    controller.start_recording.return_value = (
        False,
        "Запись уже идёт",
    )
    backend = GUIRecordingBackend(controller=controller)

    result = backend.start(
        output_path=Path("out.mp4"),
        capture=CaptureRequest(
            mode=CaptureMode.FULL,
            window_title="",
            rect_coords=(0, 0, 0, 0),
        ),
        audio=AudioRequest(mode=AudioMode.NONE),
        video=VideoRequest(fps=30, codec="libx264", bitrate="2M", format="mp4"),
    )

    assert result == (False, "Запись уже идёт")
    controller.start_recording.assert_called_once()


def test_stop_recording_not_recording() -> None:
    """Остановка без активной записи возвращает None."""
    controller = MagicMock()
    controller.stop_recording.return_value = None
    backend = GUIRecordingBackend(controller=controller)

    result = backend.stop()

    assert result is None
    controller.stop_recording.assert_called_once()


def test_get_status_when_recording() -> None:
    """Статус при активной записи."""
    from core.recording_state import RecordingStatus

    backend = GUIRecordingBackend()
    # Эмулируем активную запись через состояние
    backend._state.status = RecordingStatus.RECORDING
    backend._state.current_output = Path("test_recording.mp4")

    status = backend.get_status()

    assert status.is_recording is True
    assert status.is_paused is False
    assert status.current_file == Path("test_recording.mp4")


def test_get_status_when_paused() -> None:
    """Статус при записи на паузе."""
    from core.recording_state import RecordingStatus

    backend = GUIRecordingBackend()
    backend._state.status = RecordingStatus.PAUSED
    backend._state.current_output = Path("paused_recording.mp4")

    status = backend.get_status()

    assert status.is_recording is False
    assert status.is_paused is True
    assert status.current_file == Path("paused_recording.mp4")


# ====================
# Тесты маппинга типов
# ====================


def test_map_capture_full_mode() -> None:
    """Маппинг CaptureMode.FULL -> CaptureType.FULL_SCREEN."""
    from gui.backends.recording_backend import _map_capture

    capture = CaptureRequest(
        mode=CaptureMode.FULL,
        window_title="",
        rect_coords=(0, 0, 0, 0),
    )
    result = _map_capture(capture)

    assert result.capture_type == CaptureType.FULL_SCREEN
    assert result.window_title == ""


def test_map_capture_window_mode() -> None:
    """Маппинг CaptureMode.WINDOW -> CaptureType.WINDOW."""
    from gui.backends.recording_backend import _map_capture

    capture = CaptureRequest(
        mode=CaptureMode.WINDOW,
        window_title="Test Window",
        rect_coords=(0, 0, 0, 0),
    )
    result = _map_capture(capture)

    assert result.capture_type == CaptureType.WINDOW
    assert result.window_title == "Test Window"


def test_map_capture_rect_mode() -> None:
    """Маппинг CaptureMode.RECT -> CaptureType.RECTANGLE."""
    from gui.backends.recording_backend import _map_capture

    capture = CaptureRequest(
        mode=CaptureMode.RECT,
        window_title="",
        rect_coords=(100, 200, 500, 600),
    )
    result = _map_capture(capture)

    assert result.capture_type == CaptureType.RECTANGLE
    assert result.rect_coords == (100, 200, 500, 600)


def test_map_audio_none_mode() -> None:
    """Маппинг AudioMode.NONE -> AudioType.NONE."""
    from gui.backends.recording_backend import _map_audio

    audio = AudioRequest(mode=AudioMode.NONE)
    result = _map_audio(audio)

    assert result.audio_type == AudioType.NONE


def test_map_audio_mic_mode() -> None:
    """Маппинг AudioMode.MIC -> AudioType.MICROPHONE."""
    from gui.backends.recording_backend import _map_audio

    audio = AudioRequest(mode=AudioMode.MIC, mic_device_index=2)
    result = _map_audio(audio)

    assert result.audio_type == AudioType.MICROPHONE
    assert result.mic_device_index == 2


def test_map_audio_system_mode() -> None:
    """Маппинг AudioMode.SYSTEM -> AudioType.SYSTEM."""
    from gui.backends.recording_backend import _map_audio

    audio = AudioRequest(mode=AudioMode.SYSTEM)
    result = _map_audio(audio)

    assert result.audio_type == AudioType.SYSTEM


def test_map_audio_both_mode() -> None:
    """Маппинг AudioMode.BOTH -> AudioType.BOTH."""
    from gui.backends.recording_backend import _map_audio

    audio = AudioRequest(mode=AudioMode.BOTH, mic_device_index=3)
    result = _map_audio(audio)

    assert result.audio_type == AudioType.BOTH
    assert result.mic_device_index == 3


def test_map_video_preserves_all_params() -> None:
    """Маппинг VideoRequest сохраняет все параметры."""
    from gui.backends.recording_backend import _map_video

    video = VideoRequest(
        fps=60,
        codec="libx265",
        bitrate="10M",
        format="mkv",
    )
    result = _map_video(video)

    assert result.fps == 60
    assert result.codec == "libx265"
    assert result.bitrate == "10M"
    assert result.format == "mkv"


# ====================
# Тесты elapsed_time
# ====================


def test_elapsed_time_from_controller() -> None:
    """elapsed_time берётся из контроллера."""
    controller = MagicMock()
    controller.elapsed_time = 123.45
    backend = GUIRecordingBackend(controller=controller)

    status = backend.get_status()

    assert status.elapsed_time == 123.45


def test_elapsed_time_zero_initially() -> None:
    """elapsed_time равен 0 при инициализации."""
    backend = GUIRecordingBackend()
    status = backend.get_status()

    assert status.elapsed_time == 0.0
