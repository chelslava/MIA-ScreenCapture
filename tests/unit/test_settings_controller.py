"""
Тесты контроллера настроек
=========================

Тестирует управление загрузкой и сохранением настроек.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from config import ConfigManager
from gui.controllers.settings_controller import SettingsController
from gui.models.recording_state import (
    AudioType,
    CaptureType,
    RecordingState,
)


class TestSettingsControllerInit:
    """Тесты инициализации контроллера."""

    def test_init_with_defaults(self) -> None:
        """Тест инициализации с параметрами по умолчанию."""
        controller = SettingsController()
        assert isinstance(controller.state, RecordingState)

    def test_init_with_custom_state(self) -> None:
        """Тест инициализации с кастомным состоянием."""
        state = RecordingState()
        controller = SettingsController(state=state)
        assert controller.state is state

    def test_init_with_custom_config(self) -> None:
        """Тест инициализации с кастомным конфигом."""
        config = MagicMock(spec=ConfigManager)
        controller = SettingsController(config=config)
        assert controller._config is config

    def test_init_with_all_params(self) -> None:
        """Тест инициализации со всеми параметрами."""
        state = RecordingState()
        config = MagicMock(spec=ConfigManager)
        controller = SettingsController(state=state, config=config)
        assert controller.state is state
        assert controller._config is config


class TestLoadSettings:
    """Тесты загрузки настроек."""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Создаёт мок ConfigManager."""
        config = MagicMock(spec=ConfigManager)
        config.settings.video.fps = 30
        config.settings.video.codec = "libx264"
        config.settings.video.bitrate = "5M"
        config.settings.video.format = "mp4"
        config.settings.output.default_path = "/default/path"
        config.settings.recent_recordings = []
        return config

    def test_load_video_settings(self, mock_config: MagicMock) -> None:
        """Тест загрузки настроек видео."""
        state = RecordingState()
        controller = SettingsController(state=state, config=mock_config)
        controller.load_settings()
        assert state.video.fps == 30
        assert state.video.codec == "libx264"
        assert state.video.bitrate == "5M"
        assert state.video.format == "mp4"

    def test_load_output_path(self, mock_config: MagicMock) -> None:
        """Тест загрузки пути вывода."""
        state = RecordingState()
        controller = SettingsController(state=state, config=mock_config)
        controller.load_settings()
        assert state.output.default_path == "/default/path"

    def test_load_recent_recordings_empty(
        self, mock_config: MagicMock
    ) -> None:
        """Тест загрузки пустого списка недавних записей."""
        state = RecordingState()
        controller = SettingsController(state=state, config=mock_config)
        controller.load_settings()
        assert len(state.recent_recordings) == 0

    def test_load_recent_recordings_with_existing_file(
        self, mock_config: MagicMock, tmp_path: Path
    ) -> None:
        """Тест загрузки недавних записей с существующим файлом."""
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"test")
        mock_config.settings.recent_recordings = [
            {"path": str(video_file), "size": 100, "date": "2024-01-01"}
        ]
        state = RecordingState()
        controller = SettingsController(state=state, config=mock_config)
        controller.load_settings()
        assert len(state.recent_recordings) == 1
        assert state.recent_recordings[0].path == video_file


class TestSaveSettings:
    """Тесты сохранения настроек."""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Создаёт мок ConfigManager."""
        config = MagicMock(spec=ConfigManager)
        config.settings.video.fps = 30
        config.settings.video.codec = "libx264"
        config.settings.video.bitrate = "5M"
        config.settings.video.format = "mp4"
        config.settings.output.default_path = ""
        config.settings.recent_recordings = []
        return config

    def test_save_video_settings(self, mock_config: MagicMock) -> None:
        """Тест сохранения настроек видео."""
        state = RecordingState()
        state.video.fps = 60
        state.video.codec = "libx265"
        state.video.bitrate = "10M"
        state.video.format = "mkv"
        controller = SettingsController(state=state, config=mock_config)
        controller.save_settings()
        assert mock_config.settings.video.fps == 60
        assert mock_config.settings.video.codec == "libx265"
        assert mock_config.settings.video.bitrate == "10M"
        assert mock_config.settings.video.format == "mkv"

    def test_save_output_path(self, mock_config: MagicMock) -> None:
        """Тест сохранения пути вывода."""
        state = RecordingState()
        state.output.default_path = "/new/path"
        controller = SettingsController(state=state, config=mock_config)
        controller.save_settings()
        assert mock_config.settings.output.default_path == "/new/path"

    def test_save_calls_config_save(self, mock_config: MagicMock) -> None:
        """Тест вызова save() у конфигурации."""
        state = RecordingState()
        controller = SettingsController(state=state, config=mock_config)
        controller.save_settings()
        mock_config.save.assert_called_once()


class TestUpdateVideoSettings:
    """Тесты обновления настроек видео."""

    @pytest.fixture
    def controller(self) -> SettingsController:
        """Создаёт контроллер для тестов."""
        return SettingsController()

    def test_update_fps(self, controller: SettingsController) -> None:
        """Тест обновления FPS."""
        controller.update_video_settings(fps=60)
        assert controller.state.video.fps == 60

    def test_update_codec(self, controller: SettingsController) -> None:
        """Тест обновления кодека."""
        controller.update_video_settings(codec="libx265")
        assert controller.state.video.codec == "libx265"

    def test_update_bitrate(self, controller: SettingsController) -> None:
        """Тест обновления битрейта."""
        controller.update_video_settings(bitrate="10M")
        assert controller.state.video.bitrate == "10M"

    def test_update_format(self, controller: SettingsController) -> None:
        """Тест обновления формата."""
        controller.update_video_settings(format="mkv")
        assert controller.state.video.format == "mkv"

    def test_update_all_params(self, controller: SettingsController) -> None:
        """Тест обновления всех параметров."""
        controller.update_video_settings(
            fps=60, codec="libx265", bitrate="10M", format="mkv"
        )
        assert controller.state.video.fps == 60
        assert controller.state.video.codec == "libx265"
        assert controller.state.video.bitrate == "10M"
        assert controller.state.video.format == "mkv"

    def test_update_none_params(self, controller: SettingsController) -> None:
        """Тест обновления с None параметрами."""
        original_fps = controller.state.video.fps
        controller.update_video_settings(fps=None)
        assert controller.state.video.fps == original_fps


class TestUpdateCaptureSettings:
    """Тесты обновления настроек захвата."""

    @pytest.fixture
    def controller(self) -> SettingsController:
        """Создаёт контроллер для тестов."""
        return SettingsController()

    def test_update_capture_type(self, controller: SettingsController) -> None:
        """Тест обновления типа захвата."""
        controller.update_capture_settings(capture_type=CaptureType.WINDOW)
        assert controller.state.capture.capture_type == CaptureType.WINDOW

    def test_update_window_title(self, controller: SettingsController) -> None:
        """Тест обновления заголовка окна."""
        controller.update_capture_settings(window_title="Test Window")
        assert controller.state.capture.window_title == "Test Window"

    def test_update_rect_coords(self, controller: SettingsController) -> None:
        """Тест обновления координат."""
        coords = (100, 100, 500, 500)
        controller.update_capture_settings(rect_coords=coords)
        assert controller.state.capture.rect_coords == coords


class TestUpdateAudioSettings:
    """Тесты обновления настроек аудио."""

    @pytest.fixture
    def controller(self) -> SettingsController:
        """Создаёт контроллер для тестов."""
        return SettingsController()

    def test_update_audio_type(self, controller: SettingsController) -> None:
        """Тест обновления типа аудио."""
        controller.update_audio_settings(audio_type=AudioType.MIC)
        assert controller.state.audio.audio_type == AudioType.MIC

    def test_update_mic_device_index(
        self, controller: SettingsController
    ) -> None:
        """Тест обновления индекса устройства."""
        controller.update_audio_settings(mic_device_index=2)
        assert controller.state.audio.mic_device_index == 2

    def test_update_mic_device_name(
        self, controller: SettingsController
    ) -> None:
        """Тест обновления имени устройства."""
        controller.update_audio_settings(mic_device_name="Test Mic")
        assert controller.state.audio.mic_device_name == "Test Mic"


class TestUpdateOutputSettings:
    """Тесты обновления настроек вывода."""

    @pytest.fixture
    def controller(self) -> SettingsController:
        """Создаёт контроллер для тестов."""
        return SettingsController()

    def test_update_output_path(self, controller: SettingsController) -> None:
        """Тест обновления пути вывода."""
        controller.update_output_settings(output_path="/test/output.mp4")
        assert controller.state.output.output_path == "/test/output.mp4"

    def test_update_default_path(self, controller: SettingsController) -> None:
        """Тест обновления пути по умолчанию."""
        controller.update_output_settings(default_path="/test/default")
        assert controller.state.output.default_path == "/test/default"


class TestRecentRecordings:
    """Тесты недавних записей."""

    @pytest.fixture
    def controller(self) -> SettingsController:
        """Создаёт контроллер для тестов."""
        config = MagicMock(spec=ConfigManager)
        return SettingsController(config=config)

    def test_add_recent_recording(
        self, controller: SettingsController, tmp_path: Path
    ) -> None:
        """Тест добавления недавней записи."""
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"test")
        controller.add_recent_recording(video_file, 100)
        assert len(controller.state.recent_recordings) == 1
        controller._config.add_recent_recording.assert_called_once_with(
            str(video_file), 100
        )

    def test_clear_recent_recordings(
        self, controller: SettingsController, tmp_path: Path
    ) -> None:
        """Тест очистки недавних записей."""
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"test")
        controller.add_recent_recording(video_file, 100)
        assert len(controller.state.recent_recordings) == 1
        controller.clear_recent_recordings()
        assert len(controller.state.recent_recordings) == 0
        controller._config.clear_recent_recordings.assert_called_once()


class TestGetOutputPath:
    """Тесты получения пути вывода."""

    @pytest.fixture
    def controller(self) -> SettingsController:
        """Создаёт контроллер для тестов."""
        return SettingsController()

    def test_with_output_path(self, controller: SettingsController) -> None:
        """Тест с заданным путём вывода."""
        controller.update_output_settings(output_path="/custom/output.mp4")
        result = controller.get_output_path()
        assert result == Path("/custom/output.mp4")

    def test_with_default_path(self, controller: SettingsController) -> None:
        """Тест с путём по умолчанию."""
        controller.update_output_settings(default_path="/default")
        result = controller.get_output_path()
        assert "default" in str(result).lower() or result.suffix == ".mp4"

    def test_without_paths(self, controller: SettingsController) -> None:
        """Тест без заданных путей."""
        controller.state.output.output_path = ""
        controller.state.output.default_path = ""
        result = controller.get_output_path()
        assert result.name.endswith(".mp4")
