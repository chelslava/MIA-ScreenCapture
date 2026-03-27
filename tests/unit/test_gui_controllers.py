"""
Тесты контроллеров GUI
======================

Тестирует контроллеры для GUI компонентов.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.recording_types import AudioMode, CaptureMode
from gui.controllers.recording_controller import RecordingController
from gui.controllers.settings_controller import SettingsController
from gui.models.recording_state import (
    AudioSettings,
    CaptureSettings,
    RecordingState,
    RecordingStatus,
    VideoSettings,
)


class TestRecordingController:
    """Тесты контроллера записи."""

    @pytest.fixture
    def state(self) -> RecordingState:
        """Создаёт состояние записи для тестов."""
        return RecordingState()

    @pytest.fixture
    def controller(self, state: RecordingState) -> RecordingController:
        """Создаёт контроллер для тестов."""
        return RecordingController(state)

    def test_init_with_state(self, state: RecordingState) -> None:
        """Проверка инициализации с состоянием."""
        controller = RecordingController(state)
        assert controller.state is state

    def test_init_without_state(self) -> None:
        """Проверка инициализации без состояния."""
        controller = RecordingController()
        assert isinstance(controller.state, RecordingState)

    def test_elapsed_time_no_recorder(
        self, controller: RecordingController
    ) -> None:
        """Проверка elapsed_time без рекордера."""
        assert controller.elapsed_time == 0.0

    def test_build_capture_area_full_screen(
        self, controller: RecordingController
    ) -> None:
        """Проверка построения области захвата - весь экран."""
        capture = CaptureSettings(capture_type=CaptureMode.FULL)

        area = controller.build_capture_area(capture)

        assert area is not None

    def test_build_capture_area_window(
        self, controller: RecordingController
    ) -> None:
        """Проверка построения области захвата - окно."""
        capture = CaptureSettings(
            capture_type=CaptureMode.WINDOW,
            window_title="Test Window",
        )

        with patch(
            "gui.controllers.recording_controller.CaptureArea.from_window"
        ) as mock:
            mock.return_value = MagicMock()
            area = controller.build_capture_area(capture)
            mock.assert_called_once_with("Test Window")

    def test_build_capture_area_rectangle(
        self, controller: RecordingController
    ) -> None:
        """Проверка построения области захвата - прямоугольник."""
        capture = CaptureSettings(
            capture_type=CaptureMode.RECT,
            rect_coords=(100, 100, 500, 400),
        )

        with patch(
            "gui.controllers.recording_controller.CaptureArea.from_rect"
        ) as mock:
            mock.return_value = MagicMock()
            area = controller.build_capture_area(capture)
            mock.assert_called_once_with(100, 100, 500, 400)

    @patch("gui.controllers.recording_controller.RecordingEncoder")
    @patch("gui.controllers.recording_controller.VideoRecorder")
    def test_start_recording_success(
        self,
        mock_video_recorder: MagicMock,
        mock_encoder: MagicMock,
        controller: RecordingController,
    ) -> None:
        """Проверка успешного запуска записи."""
        # Настройка моков
        mock_encoder_instance = MagicMock()
        mock_encoder_instance.setup.return_value = (
            Path("/tmp/video.mp4"),
            Path("/tmp/audio.wav"),
        )
        mock_encoder.return_value = mock_encoder_instance

        mock_video_instance = MagicMock()
        mock_video_instance.start.return_value = True
        mock_video_recorder.return_value = mock_video_instance

        # Запуск записи
        output_path = Path("/output/test.mp4")
        capture = CaptureSettings()
        audio = AudioSettings()
        video = VideoSettings()

        success, error_msg = controller.start_recording(
            output_path, capture, audio, video
        )

        assert success is True
        assert error_msg is None
        assert controller.state.status == RecordingStatus.RECORDING

    @patch("gui.controllers.recording_controller.AudioRecorder")
    @patch("gui.controllers.recording_controller.RecordingEncoder")
    @patch("gui.controllers.recording_controller.VideoRecorder")
    def test_start_recording_fails_when_audio_start_fails(
        self,
        mock_video_recorder: MagicMock,
        mock_encoder: MagicMock,
        mock_audio_recorder: MagicMock,
        controller: RecordingController,
    ) -> None:
        """Проверка ошибки запуска, если аудиозапись не стартовала."""
        mock_encoder_instance = MagicMock()
        mock_encoder_instance.setup.return_value = (
            Path("/tmp/video.mp4"),
            Path("/tmp/audio.wav"),
        )
        mock_encoder.return_value = mock_encoder_instance

        mock_video_instance = MagicMock()
        mock_video_instance.start.return_value = True
        mock_video_recorder.return_value = mock_video_instance

        mock_audio_instance = MagicMock()
        mock_audio_instance.start.return_value = False
        mock_audio_recorder.return_value = mock_audio_instance

        output_path = Path("/output/test.mp4")
        capture = CaptureSettings()
        audio = AudioSettings(audio_type=AudioMode.MIC)
        video = VideoSettings()

        success, error_msg = controller.start_recording(
            output_path, capture, audio, video
        )

        assert success is False
        assert error_msg == "Не удалось запустить аудиозапись"

    def test_pause_recording_success(
        self, controller: RecordingController
    ) -> None:
        """Проверка успешной паузы записи."""
        controller.state.status = RecordingStatus.RECORDING

        result = controller.pause_recording()

        assert result is True
        assert controller.state.status == RecordingStatus.PAUSED

    def test_pause_recording_not_recording(
        self, controller: RecordingController
    ) -> None:
        """Проверка паузы когда запись не активна."""
        controller.state.status = RecordingStatus.IDLE

        result = controller.pause_recording()

        assert result is False
        assert controller.state.status == RecordingStatus.IDLE

    def test_pause_recording_already_paused(
        self, controller: RecordingController
    ) -> None:
        """Проверка паузы когда уже на паузе."""
        controller.state.status = RecordingStatus.PAUSED

        result = controller.pause_recording()

        assert result is False

    def test_resume_recording_success(
        self, controller: RecordingController
    ) -> None:
        """Проверка успешного возобновления записи."""
        controller.state.status = RecordingStatus.PAUSED

        result = controller.resume_recording()

        assert result is True
        assert controller.state.status == RecordingStatus.RECORDING

    def test_resume_recording_not_paused(
        self, controller: RecordingController
    ) -> None:
        """Проверка возобновления когда не на паузе."""
        controller.state.status = RecordingStatus.IDLE

        result = controller.resume_recording()

        assert result is False

    def test_stop_recording_not_recording(
        self, controller: RecordingController
    ) -> None:
        """Проверка остановки когда запись не активна."""
        controller.state.status = RecordingStatus.IDLE

        result = controller.stop_recording()

        assert result is None

    def test_cancel_recording(self, controller: RecordingController) -> None:
        """Проверка отмены записи."""
        controller.state.status = RecordingStatus.RECORDING

        controller.cancel_recording()

        assert controller.state.status == RecordingStatus.IDLE


class TestSettingsController:
    """Тесты контроллера настроек."""

    @pytest.fixture
    def state(self) -> RecordingState:
        """Создаёт состояние записи для тестов."""
        return RecordingState()

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Создаёт мок конфигурации."""
        config = MagicMock()
        config.settings = MagicMock()
        config.settings.video = MagicMock()
        config.settings.video.fps = 30
        config.settings.video.codec = "libx264"
        config.settings.video.bitrate = "2M"
        config.settings.video.format = "mp4"
        config.settings.output = MagicMock()
        config.settings.output.default_path = "/default/path"
        config.settings.recent_recordings = []
        return config

    @pytest.fixture
    def controller(
        self, state: RecordingState, mock_config: MagicMock
    ) -> SettingsController:
        """Создаёт контроллер для тестов."""
        return SettingsController(state, mock_config)

    def test_init_with_state_and_config(
        self, state: RecordingState, mock_config: MagicMock
    ) -> None:
        """Проверка инициализации с состоянием и конфигурацией."""
        controller = SettingsController(state, mock_config)
        assert controller.state is state

    def test_init_without_state_and_config(self) -> None:
        """Проверка инициализации без состояния и конфигурации."""
        with patch(
            "gui.controllers.settings_controller.get_config"
        ) as mock_get_config:
            mock_get_config.return_value = MagicMock()
            controller = SettingsController()
            assert isinstance(controller.state, RecordingState)

    def test_load_settings(self, controller: SettingsController) -> None:
        """Проверка загрузки настроек."""
        controller.load_settings()

        assert controller.state.video.fps == 30
        assert controller.state.video.codec == "libx264"
        assert controller.state.video.bitrate == "2M"
        assert controller.state.video.format == "mp4"

    def test_save_settings(
        self, controller: SettingsController, mock_config: MagicMock
    ) -> None:
        """Проверка сохранения настроек."""
        controller.state.video.fps = 60
        controller.state.video.codec = "h264"

        controller.save_settings()

        assert mock_config.settings.video.fps == 60
        assert mock_config.settings.video.codec == "h264"
        mock_config.save.assert_called_once()

    def test_update_video_settings(
        self, controller: SettingsController
    ) -> None:
        """Проверка обновления настроек видео."""
        controller.update_video_settings(
            fps=60,
            codec="h264",
            bitrate="4M",
            format="mkv",
        )

        assert controller.state.video.fps == 60
        assert controller.state.video.codec == "h264"
        assert controller.state.video.bitrate == "4M"
        assert controller.state.video.format == "mkv"

    def test_update_video_settings_partial(
        self, controller: SettingsController
    ) -> None:
        """Проверка частичного обновления настроек видео."""
        original_codec = controller.state.video.codec
        original_bitrate = controller.state.video.bitrate
        original_format = controller.state.video.format

        controller.update_video_settings(fps=60)

        assert controller.state.video.fps == 60
        assert controller.state.video.codec == original_codec
        assert controller.state.video.bitrate == original_bitrate
        assert controller.state.video.format == original_format

    def test_update_capture_settings(
        self, controller: SettingsController
    ) -> None:
        """Проверка обновления настроек захвата."""
        controller.update_capture_settings(
            capture_type=CaptureMode.WINDOW,
            window_title="Test Window",
            rect_coords=(100, 100, 500, 400),
        )

        assert controller.state.capture.capture_type == CaptureMode.WINDOW
        assert controller.state.capture.window_title == "Test Window"
        assert controller.state.capture.rect_coords == (100, 100, 500, 400)

    def test_update_audio_settings(
        self, controller: SettingsController
    ) -> None:
        """Проверка обновления настроек аудио."""
        controller.update_audio_settings(
            audio_type=AudioMode.MIC,
            mic_device_index=1,
            mic_device_name="Test Mic",
        )

        assert controller.state.audio.audio_type == AudioMode.MIC
        assert controller.state.audio.mic_device_index == 1
        assert controller.state.audio.mic_device_name == "Test Mic"

    def test_update_output_settings(
        self, controller: SettingsController
    ) -> None:
        """Проверка обновления настроек вывода."""
        controller.update_output_settings(
            output_path="/path/to/output.mp4",
            default_path="/default/path",
        )

        assert controller.state.output.output_path == "/path/to/output.mp4"
        assert controller.state.output.default_path == "/default/path"

    def test_add_recent_recording(
        self, controller: SettingsController, mock_config: MagicMock
    ) -> None:
        """Проверка добавления недавней записи."""
        path = Path("/path/to/video.mp4")

        controller.add_recent_recording(path, 1024000)

        assert len(controller.state.recent_recordings) == 1
        mock_config.add_recent_recording.assert_called_once_with(
            str(path), 1024000
        )

    def test_get_output_path_with_custom_path(
        self, controller: SettingsController
    ) -> None:
        """Проверка получения пути вывода с пользовательским путём."""
        controller.state.output.output_path = "/custom/path/video.mp4"

        result = controller.get_output_path()

        assert result == Path("/custom/path/video.mp4")

    def test_get_output_path_with_default_path(
        self, controller: SettingsController
    ) -> None:
        """Проверка получения пути вывода с путём по умолчанию."""
        controller.state.output.output_path = ""
        controller.state.output.default_path = "/default/path"
        controller.state.video.format = "mp4"

        result = controller.get_output_path()

        # Проверяем что путь содержит директорию и имя файла
        assert "recording_" in str(result)
        assert str(result).endswith(".mp4")
        assert "default" in str(result) or "path" in str(result)
