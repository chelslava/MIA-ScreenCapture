"""
Unit тесты для MainWindow
=========================

Тестирует функциональность главного окна с реальной логикой.

Примечание: PyQt6 мокируется в conftest.py для всех тестов.
"""

from pathlib import Path

import pytest


class TestMainWindowBasics:
    """Базовые тесты MainWindow."""

    def test_main_window_module_exists(self) -> None:
        """Проверка существования модуля."""
        from gui import main_window

        assert main_window is not None

    def test_main_window_class_exists(self) -> None:
        """Проверка существования класса MainWindow."""
        from gui.main_window import MainWindow

        assert MainWindow is not None


class TestMainWindowRecordingState:
    """Тесты модели состояния записи."""

    def test_recording_state_initial_values(self) -> None:
        """Проверка начальных значений состояния."""
        from gui.models.recording_state import RecordingState, RecordingStatus

        state = RecordingState()

        assert state.status == RecordingStatus.IDLE
        assert not state.is_recording()
        assert not state.is_paused()
        assert state.is_idle()

    def test_recording_state_start_recording(self) -> None:
        """Проверка начала записи."""
        from gui.models.recording_state import RecordingState, RecordingStatus

        state = RecordingState()
        state.start_recording(Path("/tmp/test.mp4"))

        assert state.is_recording()
        assert state.status == RecordingStatus.RECORDING
        assert state.current_output == Path("/tmp/test.mp4")

    def test_recording_state_pause_recording(self) -> None:
        """Проверка паузы записи."""
        from gui.models.recording_state import RecordingState, RecordingStatus

        state = RecordingState()
        state.start_recording(Path("/tmp/test.mp4"))
        state.pause_recording()

        assert state.is_paused()
        assert state.status == RecordingStatus.PAUSED

    def test_recording_state_resume_recording(self) -> None:
        """Проверка возобновления записи."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        state.start_recording(Path("/tmp/test.mp4"))
        state.pause_recording()
        state.resume_recording()

        assert state.is_recording()
        assert not state.is_paused()

    def test_recording_state_stop_recording(self) -> None:
        """Проверка остановки записи."""
        from gui.models.recording_state import RecordingState, RecordingStatus

        state = RecordingState()
        state.start_recording(Path("/tmp/test.mp4"))
        state.stop_recording()

        assert state.is_idle()
        assert state.status == RecordingStatus.IDLE

    def test_recording_state_cannot_pause_when_idle(self) -> None:
        """Проверка невозможности паузы без записи."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        state.pause_recording()  # Не должно иметь эффекта

        assert state.is_idle()

    def test_recording_state_cannot_resume_when_not_paused(self) -> None:
        """Проверка невозможности возобновления без паузы."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        state.start_recording(Path("/tmp/test.mp4"))
        state.resume_recording()  # Не должно иметь эффекта

        assert state.is_recording()


class TestMainWindowStateTransitionsParameterized:
    """Параметризованные тесты переходов состояний."""

    @pytest.mark.parametrize(
        "initial_state,action,expected_state",
        [
            ("idle", "start", "recording"),
            ("recording", "stop", "idle"),
            ("recording", "pause", "paused"),
            ("paused", "resume", "recording"),
            ("paused", "stop", "idle"),
        ],
    )
    def test_state_transitions(
        self, initial_state: str, action: str, expected_state: str
    ) -> None:
        """Проверка переходов между состояниями."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()

        # Устанавливаем начальное состояние
        if initial_state == "recording":
            state.start_recording(Path("/tmp/test.mp4"))
        elif initial_state == "paused":
            state.start_recording(Path("/tmp/test.mp4"))
            state.pause_recording()

        # Выполняем действие
        if action == "start":
            state.start_recording(Path("/tmp/test.mp4"))
        elif action == "stop":
            state.stop_recording()
        elif action == "pause":
            state.pause_recording()
        elif action == "resume":
            state.resume_recording()

        # Проверяем ожидаемое состояние
        if expected_state == "idle":
            assert state.is_idle()
        elif expected_state == "recording":
            assert state.is_recording()
            assert not state.is_paused()
        elif expected_state == "paused":
            assert state.is_paused()


class TestMainWindowButtonStates:
    """Тесты состояний кнопок."""

    @pytest.mark.parametrize(
        "is_recording,is_paused,start_enabled,stop_enabled,pause_enabled",
        [
            (False, False, True, False, False),  # idle
            (True, False, False, True, True),  # recording
            (True, True, False, True, True),  # paused
        ],
    )
    def test_button_states_by_recording_state(
        self,
        is_recording: bool,
        is_paused: bool,
        start_enabled: bool,
        stop_enabled: bool,
        pause_enabled: bool,
    ) -> None:
        """Проверка состояний кнопок по состоянию записи."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()

        if is_recording:
            state.start_recording(Path("/tmp/test.mp4"))
            if is_paused:
                state.pause_recording()

        # Логика доступности кнопок
        actual_start_enabled = state.is_idle()
        actual_stop_enabled = state.is_recording() or state.is_paused()
        actual_pause_enabled = state.is_recording() or state.is_paused()

        assert actual_start_enabled == start_enabled
        assert actual_stop_enabled == stop_enabled
        assert actual_pause_enabled == pause_enabled


class TestMainWindowStatusText:
    """Тесты текста статуса."""

    @pytest.mark.parametrize(
        "is_recording,is_paused,expected_text",
        [
            (False, False, "Готов"),
            (True, False, "Запись"),
            (True, True, "Пауза"),
        ],
    )
    def test_status_text_by_state(
        self, is_recording: bool, is_paused: bool, expected_text: str
    ) -> None:
        """Проверка текста статуса по состоянию."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()

        if is_recording:
            state.start_recording(Path("/tmp/test.mp4"))
            if is_paused:
                state.pause_recording()

        # Логика формирования текста статуса
        if state.is_paused():
            status_text = "Пауза"
        elif state.is_recording():
            status_text = "Запись"
        else:
            status_text = "Готов"

        assert status_text == expected_text


class TestMainWindowPauseButtonText:
    """Тесты текста кнопки паузы."""

    @pytest.mark.parametrize(
        "is_paused,expected_text",
        [
            (False, "Пауза"),
            (True, "Продолжить"),
        ],
    )
    def test_pause_button_text(self, is_paused: bool, expected_text: str) -> None:
        """Проверка текста кнопки паузы."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        state.start_recording(Path("/tmp/test.mp4"))

        if is_paused:
            state.pause_recording()

        pause_text = "Продолжить" if state.is_paused() else "Пауза"
        assert pause_text == expected_text


class TestMainWindowRecentRecordings:
    """Тесты списка последних записей."""

    def test_add_recent_recording(self) -> None:
        """Проверка добавления недавней записи."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        state.add_recent_recording(Path("/tmp/test1.mp4"), 1024)

        assert len(state.recent_recordings) == 1
        assert state.recent_recordings[0].path == Path("/tmp/test1.mp4")
        assert state.recent_recordings[0].size == 1024

    def test_recent_recordings_limit(self) -> None:
        """Проверка ограничения списка недавних записей."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()

        # Добавляем 25 записей
        for i in range(25):
            state.add_recent_recording(Path(f"/tmp/test{i}.mp4"), 1024)

        # Должно остаться только 20
        assert len(state.recent_recordings) == 20

    def test_recent_recordings_order(self) -> None:
        """Проверка порядка недавних записей (новые в начале)."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        state.add_recent_recording(Path("/tmp/first.mp4"), 1024)
        state.add_recent_recording(Path("/tmp/second.mp4"), 2048)

        assert state.recent_recordings[0].path == Path("/tmp/second.mp4")
        assert state.recent_recordings[1].path == Path("/tmp/first.mp4")


class TestMainWindowOutputFilename:
    """Тесты генерации имени выходного файла."""

    def test_get_output_filename_format(self) -> None:
        """Проверка формата имени выходного файла."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        filename = state.get_output_filename()

        # Должен содержать timestamp и расширение
        assert filename.startswith("recording_")
        assert filename.endswith(".mp4")

    def test_get_output_filename_with_custom_format(self) -> None:
        """Проверка имени файла с кастомным форматом."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        state.video.format = "avi"
        filename = state.get_output_filename()

        assert filename.endswith(".avi")


class TestMainWindowVideoSettings:
    """Тесты настроек видео."""

    def test_default_video_settings(self) -> None:
        """Проверка настроек видео по умолчанию."""
        from gui.models.recording_state import VideoSettings

        settings = VideoSettings()

        assert settings.fps == 30
        assert settings.codec == "libx264"
        assert settings.bitrate == "2M"
        assert settings.format == "mp4"

    @pytest.mark.parametrize(
        "fps,codec,bitrate,format",
        [
            (60, "libx265", "5M", "mkv"),
            (24, "libvpx-vp9", "1M", "webm"),
            (120, "libx264", "10M", "mp4"),
        ],
    )
    def test_custom_video_settings(
        self, fps: int, codec: str, bitrate: str, format: str
    ) -> None:
        """Проверка кастомных настроек видео."""
        from gui.models.recording_state import VideoSettings

        settings = VideoSettings(
            fps=fps, codec=codec, bitrate=bitrate, format=format
        )

        assert settings.fps == fps
        assert settings.codec == codec
        assert settings.bitrate == bitrate
        assert settings.format == format


class TestMainWindowAudioSettings:
    """Тесты настроек аудио."""

    def test_default_audio_settings(self) -> None:
        """Проверка настроек аудио по умолчанию."""
        from gui.models.recording_state import AudioSettings, AudioType

        settings = AudioSettings()

        assert settings.audio_type == AudioType.NONE
        assert settings.mic_device_index is None

    @pytest.mark.parametrize(
        "audio_type",
        ["NONE", "MICROPHONE", "SYSTEM", "BOTH"],
    )
    def test_audio_type_enum(self, audio_type: str) -> None:
        """Проверка типов источников аудио."""
        from gui.models.recording_state import AudioType

        assert hasattr(AudioType, audio_type)


class TestMainWindowCaptureSettings:
    """Тесты настроек захвата."""

    def test_default_capture_settings(self) -> None:
        """Проверка настроек захвата по умолчанию."""
        from gui.models.recording_state import CaptureSettings, CaptureType

        settings = CaptureSettings()

        assert settings.capture_type == CaptureType.FULL_SCREEN
        assert settings.window_title == ""
        assert settings.rect_coords == (0, 0, 1920, 1080)

    def test_window_capture_settings(self) -> None:
        """Проверка настроек захвата окна."""
        from gui.models.recording_state import CaptureSettings, CaptureType

        settings = CaptureSettings(
            capture_type=CaptureType.WINDOW,
            window_title="Chrome",
        )

        assert settings.capture_type == CaptureType.WINDOW
        assert settings.window_title == "Chrome"

    def test_rectangle_capture_settings(self) -> None:
        """Проверка настроек захвата области."""
        from gui.models.recording_state import CaptureSettings, CaptureType

        settings = CaptureSettings(
            capture_type=CaptureType.RECTANGLE,
            rect_coords=(100, 100, 800, 600),
        )

        assert settings.capture_type == CaptureType.RECTANGLE
        assert settings.rect_coords == (100, 100, 800, 600)


class TestMainWindowElapsedtime:
    """Тесты отслеживания времени."""

    def test_elapsed_time_initial_value(self) -> None:
        """Проверка начального значения времени."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        assert state.elapsed_time == 0.0

    def test_elapsed_time_reset_on_start(self) -> None:
        """Проверка сброса времени при начале записи."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        state.elapsed_time = 100.0
        state.start_recording(Path("/tmp/test.mp4"))

        assert state.elapsed_time == 0.0

    def test_recording_start_time_set(self) -> None:
        """Проверка установки времени начала записи."""
        from datetime import datetime

        from gui.models.recording_state import RecordingState

        state = RecordingState()
        before = datetime.now()
        state.start_recording(Path("/tmp/test.mp4"))
        after = datetime.now()

        assert state.recording_start_time is not None
        assert before <= state.recording_start_time <= after

    def test_recording_start_time_cleared_on_stop(self) -> None:
        """Проверка очистки времени начала при остановке."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        state.start_recording(Path("/tmp/test.mp4"))
        state.stop_recording()

        assert state.recording_start_time is None
