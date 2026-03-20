"""
Тесты моделей GUI
=================

Тестирует модели данных для GUI компонентов.
"""

from datetime import datetime
from pathlib import Path

from gui.models.recording_state import (
    AudioSettings,
    AudioType,
    CaptureSettings,
    CaptureType,
    OutputSettings,
    RecentRecording,
    RecordingState,
    RecordingStatus,
    VideoSettings,
)


class TestRecordingStatus:
    """Тесты перечисления RecordingStatus."""

    def test_status_values(self) -> None:
        """Проверка значений статуса."""
        assert RecordingStatus.IDLE.value == "idle"
        assert RecordingStatus.RECORDING.value == "recording"
        assert RecordingStatus.PAUSED.value == "paused"


class TestCaptureType:
    """Тесты перечисления CaptureType."""

    def test_capture_type_values(self) -> None:
        """Проверка значений типа захвата."""
        assert CaptureType.FULL_SCREEN.value == "full_screen"
        assert CaptureType.WINDOW.value == "window"
        assert CaptureType.RECTANGLE.value == "rectangle"


class TestAudioType:
    """Тесты перечисления AudioType."""

    def test_audio_type_values(self) -> None:
        """Проверка значений типа аудио."""
        assert AudioType.NONE.value == "none"
        assert AudioType.MICROPHONE.value == "mic"
        assert AudioType.SYSTEM.value == "system"
        assert AudioType.BOTH.value == "both"


class TestCaptureSettings:
    """Тесты настроек области захвата."""

    def test_default_values(self) -> None:
        """Проверка значений по умолчанию."""
        settings = CaptureSettings()
        assert settings.capture_type == CaptureType.FULL_SCREEN
        assert settings.window_title == ""
        assert settings.rect_coords == (0, 0, 1920, 1080)

    def test_custom_values(self) -> None:
        """Проверка пользовательских значений."""
        settings = CaptureSettings(
            capture_type=CaptureType.WINDOW,
            window_title="Test Window",
            rect_coords=(100, 100, 500, 400),
        )
        assert settings.capture_type == CaptureType.WINDOW
        assert settings.window_title == "Test Window"
        assert settings.rect_coords == (100, 100, 500, 400)


class TestAudioSettings:
    """Тесты настроек аудио."""

    def test_default_values(self) -> None:
        """Проверка значений по умолчанию."""
        settings = AudioSettings()
        assert settings.audio_type == AudioType.NONE
        assert settings.mic_device_index is None
        assert settings.mic_device_name == ""

    def test_custom_values(self) -> None:
        """Проверка пользовательских значений."""
        settings = AudioSettings(
            audio_type=AudioType.MICROPHONE,
            mic_device_index=1,
            mic_device_name="Test Mic",
        )
        assert settings.audio_type == AudioType.MICROPHONE
        assert settings.mic_device_index == 1
        assert settings.mic_device_name == "Test Mic"


class TestVideoSettings:
    """Тесты настроек видео."""

    def test_default_values(self) -> None:
        """Проверка значений по умолчанию."""
        settings = VideoSettings()
        assert settings.fps == 30
        assert settings.codec == "libx264"
        assert settings.bitrate == "2M"
        assert settings.format == "mp4"

    def test_custom_values(self) -> None:
        """Проверка пользовательских значений."""
        settings = VideoSettings(
            fps=60,
            codec="h264",
            bitrate="4M",
            format="mkv",
        )
        assert settings.fps == 60
        assert settings.codec == "h264"
        assert settings.bitrate == "4M"
        assert settings.format == "mkv"


class TestOutputSettings:
    """Тесты настроек вывода."""

    def test_default_values(self) -> None:
        """Проверка значений по умолчанию."""
        settings = OutputSettings()
        assert settings.output_path == ""
        assert settings.default_path == ""

    def test_custom_values(self) -> None:
        """Проверка пользовательских значений."""
        settings = OutputSettings(
            output_path="/path/to/output.mp4",
            default_path="/path/to",
        )
        assert settings.output_path == "/path/to/output.mp4"
        assert settings.default_path == "/path/to"


class TestRecentRecording:
    """Тесты недавней записи."""

    def test_creation(self) -> None:
        """Проверка создания записи."""
        recording = RecentRecording(
            path=Path("/path/to/video.mp4"),
            size=1024000,
            date="2026-03-19 12:00",
        )
        assert recording.path == Path("/path/to/video.mp4")
        assert recording.size == 1024000
        assert recording.date == "2026-03-19 12:00"


class TestRecordingState:
    """Тесты состояния записи."""

    def test_default_values(self) -> None:
        """Проверка значений по умолчанию."""
        state = RecordingState()
        assert state.status == RecordingStatus.IDLE
        assert state.elapsed_time == 0.0
        assert state.current_output is None
        assert isinstance(state.capture, CaptureSettings)
        assert isinstance(state.audio, AudioSettings)
        assert isinstance(state.video, VideoSettings)
        assert isinstance(state.output, OutputSettings)
        assert state.recent_recordings == []

    def test_is_recording(self) -> None:
        """Проверка метода is_recording."""
        state = RecordingState()
        assert not state.is_recording()

        state.status = RecordingStatus.RECORDING
        assert state.is_recording()

    def test_is_paused(self) -> None:
        """Проверка метода is_paused."""
        state = RecordingState()
        assert not state.is_paused()

        state.status = RecordingStatus.PAUSED
        assert state.is_paused()

    def test_is_idle(self) -> None:
        """Проверка метода is_idle."""
        state = RecordingState()
        assert state.is_idle()

        state.status = RecordingStatus.RECORDING
        assert not state.is_idle()

    def test_start_recording(self) -> None:
        """Проверка начала записи."""
        state = RecordingState()
        output_path = Path("/path/to/output.mp4")

        state.start_recording(output_path)

        assert state.status == RecordingStatus.RECORDING
        assert state.current_output == output_path
        assert state.recording_start_time is not None
        assert state.elapsed_time == 0.0

    def test_pause_recording(self) -> None:
        """Проверка паузы записи."""
        state = RecordingState()
        state.status = RecordingStatus.RECORDING

        state.pause_recording()

        assert state.status == RecordingStatus.PAUSED

    def test_pause_recording_when_not_recording(self) -> None:
        """Проверка паузы когда запись не активна."""
        state = RecordingState()
        state.status = RecordingStatus.IDLE

        state.pause_recording()

        assert state.status == RecordingStatus.IDLE

    def test_resume_recording(self) -> None:
        """Проверка возобновления записи."""
        state = RecordingState()
        state.status = RecordingStatus.PAUSED

        state.resume_recording()

        assert state.status == RecordingStatus.RECORDING

    def test_resume_recording_when_not_paused(self) -> None:
        """Проверка возобновления когда не на паузе."""
        state = RecordingState()
        state.status = RecordingStatus.IDLE

        state.resume_recording()

        assert state.status == RecordingStatus.IDLE

    def test_stop_recording(self) -> None:
        """Проверка остановки записи."""
        state = RecordingState()
        state.status = RecordingStatus.RECORDING
        state.recording_start_time = datetime.now()

        state.stop_recording()

        assert state.status == RecordingStatus.IDLE
        assert state.recording_start_time is None

    def test_add_recent_recording(self) -> None:
        """Проверка добавления недавней записи."""
        state = RecordingState()
        path = Path("/path/to/video.mp4")

        state.add_recent_recording(path, 1024000)

        assert len(state.recent_recordings) == 1
        assert state.recent_recordings[0].path == path
        assert state.recent_recordings[0].size == 1024000

    def test_add_recent_recording_limit(self) -> None:
        """Проверка ограничения списка недавних записей."""
        state = RecordingState()

        # Добавляем 25 записей
        for i in range(25):
            state.add_recent_recording(
                Path(f"/path/to/video_{i}.mp4"), 1024000
            )

        # Должно остаться только 20
        assert len(state.recent_recordings) == 20
        # Последняя добавленная должна быть первой
        assert state.recent_recordings[0].path == Path("/path/to/video_24.mp4")

    def test_get_output_filename(self) -> None:
        """Проверка генерации имени выходного файла."""
        state = RecordingState()
        state.video.format = "mp4"

        filename = state.get_output_filename()

        assert filename.startswith("recording_")
        assert filename.endswith(".mp4")

    def test_get_output_filename_different_format(self) -> None:
        """Проверка генерации имени с другим форматом."""
        state = RecordingState()
        state.video.format = "mkv"

        filename = state.get_output_filename()

        assert filename.endswith(".mkv")
