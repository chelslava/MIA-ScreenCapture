"""
Тесты для GUI Views
===================

Unit тесты для представлений GUI компонентов.
"""

from pathlib import Path
from unittest.mock import patch

from PyQt6.QtWidgets import QApplication

from gui.models.recording_state import (
    AudioType,
    CaptureType,
    OutputSettings,
    VideoSettings,
)
from gui.views.audio_view import AudioView
from gui.views.capture_view import CaptureView
from gui.views.output_view import OutputView
from gui.views.video_view import VideoView

# ============================================================================
# Тесты CaptureView
# ============================================================================


class TestCaptureViewInit:
    """Тесты инициализации CaptureView."""

    def test_init_creates_widget(self, qapp: QApplication) -> None:
        """Проверка создания виджета."""
        view = CaptureView()
        assert view is not None

    def test_default_capture_type_is_full_screen(
        self, qapp: QApplication
    ) -> None:
        """Проверка типа захвата по умолчанию."""
        view = CaptureView()
        assert view.get_capture_type() == CaptureType.FULL_SCREEN

    def test_window_combo_populated(self, qapp: QApplication) -> None:
        """Проверка заполнения списка окон."""
        with patch(
            "gui.views.capture_view.get_available_windows"
        ) as mock_windows:
            mock_windows.return_value = [
                {"title": "Window 1"},
                {"title": "Window 2"},
            ]
            view = CaptureView()
            # Проверяем, что метод был вызван
            assert mock_windows.called


class TestCaptureViewCaptureType:
    """Тесты выбора типа захвата."""

    def test_get_capture_type_full_screen(self, qapp: QApplication) -> None:
        """Проверка получения типа захвата - весь экран."""
        view = CaptureView()
        view._full_screen_radio.setChecked(True)
        assert view.get_capture_type() == CaptureType.FULL_SCREEN

    def test_get_capture_type_window(self, qapp: QApplication) -> None:
        """Проверка получения типа захвата - окно."""
        view = CaptureView()
        view._window_radio.setChecked(True)
        assert view.get_capture_type() == CaptureType.WINDOW

    def test_get_capture_type_rectangle(self, qapp: QApplication) -> None:
        """Проверка получения типа захвата - прямоугольник."""
        view = CaptureView()
        view._rect_radio.setChecked(True)
        assert view.get_capture_type() == CaptureType.RECTANGLE

    def test_set_capture_type_full_screen(self, qapp: QApplication) -> None:
        """Проверка установки типа захвата - весь экран."""
        view = CaptureView()
        view._window_radio.setChecked(True)  # Сначала выбираем другое
        view.set_capture_type(CaptureType.FULL_SCREEN)
        assert view.get_capture_type() == CaptureType.FULL_SCREEN

    def test_set_capture_type_window(self, qapp: QApplication) -> None:
        """Проверка установки типа захвата - окно."""
        view = CaptureView()
        view.set_capture_type(CaptureType.WINDOW)
        assert view.get_capture_type() == CaptureType.WINDOW

    def test_set_capture_type_rectangle(self, qapp: QApplication) -> None:
        """Проверка установки типа захвата - прямоугольник."""
        view = CaptureView()
        view.set_capture_type(CaptureType.RECTANGLE)
        assert view.get_capture_type() == CaptureType.RECTANGLE


class TestCaptureViewWindow:
    """Тесты выбора окна."""

    def test_get_window_title_empty(self, qapp: QApplication) -> None:
        """Проверка получения заголовка окна при пустом списке."""
        with patch(
            "gui.views.capture_view.get_available_windows"
        ) as mock_windows:
            mock_windows.return_value = []
            view = CaptureView()
            assert view.get_window_title() == ""

    def test_get_window_title_with_windows(self, qapp: QApplication) -> None:
        """Проверка получения заголовка окна."""
        with patch(
            "gui.views.capture_view.get_available_windows"
        ) as mock_windows:
            mock_windows.return_value = [
                {"title": "Window 1"},
                {"title": "Window 2"},
            ]
            view = CaptureView()
            # По умолчанию выбран первый элемент
            assert view.get_window_title() == "Window 1"

    def test_set_window_title(self, qapp: QApplication) -> None:
        """Проверка установки заголовка окна."""
        with patch(
            "gui.views.capture_view.get_available_windows"
        ) as mock_windows:
            mock_windows.return_value = [
                {"title": "Window 1"},
                {"title": "Window 2"},
            ]
            view = CaptureView()
            view.set_window_title("Window 2")
            assert view.get_window_title() == "Window 2"

    def test_set_window_title_not_found(self, qapp: QApplication) -> None:
        """Проверка установки несуществующего заголовка окна."""
        with patch(
            "gui.views.capture_view.get_available_windows"
        ) as mock_windows:
            mock_windows.return_value = [
                {"title": "Window 1"},
                {"title": "Window 2"},
            ]
            view = CaptureView()
            view.set_window_title("Nonexistent Window")
            # Должен остаться первый элемент
            assert view.get_window_title() == "Window 1"


class TestCaptureViewRectCoords:
    """Тесты координат прямоугольника."""

    def test_get_rect_coords_valid(self, qapp: QApplication) -> None:
        """Проверка получения валидных координат."""
        view = CaptureView()
        view._rect_edit.setText("100, 200, 300, 400")
        assert view.get_rect_coords() == (100, 200, 300, 400)

    def test_get_rect_coords_with_spaces(self, qapp: QApplication) -> None:
        """Проверка получения координат с пробелами."""
        view = CaptureView()
        view._rect_edit.setText("100,  200,  300,  400")
        assert view.get_rect_coords() == (100, 200, 300, 400)

    def test_get_rect_coords_invalid_text(self, qapp: QApplication) -> None:
        """Проверка получения невалидных координат - текст."""
        view = CaptureView()
        view._rect_edit.setText("invalid")
        assert view.get_rect_coords() is None

    def test_get_rect_coords_invalid_partial(self, qapp: QApplication) -> None:
        """Проверка получения неполных координат."""
        view = CaptureView()
        view._rect_edit.setText("100, 200")
        assert view.get_rect_coords() is None

    def test_get_rect_coords_empty(self, qapp: QApplication) -> None:
        """Проверка получения пустых координат."""
        view = CaptureView()
        view._rect_edit.setText("")
        assert view.get_rect_coords() is None

    def test_set_rect_coords(self, qapp: QApplication) -> None:
        """Проверка установки координат."""
        view = CaptureView()
        view.set_rect_coords((100, 200, 300, 400))
        assert view._rect_edit.text() == "100, 200, 300, 400"


class TestCaptureViewEnabledState:
    """Тесты состояния элементов управления."""

    def test_window_combo_disabled_by_default(
        self, qapp: QApplication
    ) -> None:
        """Проверка отключения комбобокса окон по умолчанию."""
        with patch(
            "gui.views.capture_view.get_available_windows"
        ) as mock_windows:
            mock_windows.return_value = []
            view = CaptureView()
            assert not view._window_combo.isEnabled()

    def test_rect_edit_disabled_by_default(self, qapp: QApplication) -> None:
        """Проверка отключения поля координат по умолчанию."""
        view = CaptureView()
        assert not view._rect_edit.isEnabled()

    def test_window_combo_enabled_when_window_selected(
        self, qapp: QApplication
    ) -> None:
        """Проверка включения комбобокса окон при выборе окна."""
        view = CaptureView()
        view._window_radio.setChecked(True)
        view._update_enabled_state()
        assert view._window_combo.isEnabled()

    def test_rect_edit_enabled_when_rect_selected(
        self, qapp: QApplication
    ) -> None:
        """Проверка включения поля координат при выборе прямоугольника."""
        view = CaptureView()
        view._rect_radio.setChecked(True)
        view._update_enabled_state()
        assert view._rect_edit.isEnabled()


class TestCaptureViewSignals:
    """Тесты сигналов CaptureView."""

    def test_capture_type_changed_signal(self, qapp: QApplication) -> None:
        """Проверка сигнала изменения типа захвата."""
        view = CaptureView()
        signal_received = []

        def on_capture_type_changed(capture_type: CaptureType) -> None:
            signal_received.append(capture_type)

        view.capture_type_changed.connect(on_capture_type_changed)

        # Эмулируем клик по радиокнопке
        view._on_button_clicked(view._window_radio)

        assert len(signal_received) == 1
        assert signal_received[0] == CaptureType.WINDOW


# ============================================================================
# Тесты AudioView
# ============================================================================


class TestAudioViewInit:
    """Тесты инициализации AudioView."""

    def test_init_creates_widget(self, qapp: QApplication) -> None:
        """Проверка создания виджета."""
        view = AudioView()
        assert view is not None

    def test_default_audio_type_is_none(self, qapp: QApplication) -> None:
        """Проверка типа аудио по умолчанию."""
        view = AudioView()
        assert view.get_audio_type() == AudioType.NONE

    def test_mic_combo_populated(self, qapp: QApplication) -> None:
        """Проверка заполнения списка устройств."""
        with patch("gui.views.audio_view.get_audio_devices") as mock_devices:
            mock_devices.return_value = {
                "input": [
                    {"name": "Mic 1", "id": 0},
                    {"name": "Mic 2", "id": 1},
                ]
            }
            view = AudioView()
            assert mock_devices.called


class TestAudioViewAudioType:
    """Тесты выбора типа аудио."""

    def test_get_audio_type_none(self, qapp: QApplication) -> None:
        """Проверка получения типа аудио - без аудио."""
        view = AudioView()
        view._no_audio_radio.setChecked(True)
        assert view.get_audio_type() == AudioType.NONE

    def test_get_audio_type_microphone(self, qapp: QApplication) -> None:
        """Проверка получения типа аудио - микрофон."""
        view = AudioView()
        view._mic_radio.setChecked(True)
        assert view.get_audio_type() == AudioType.MICROPHONE

    def test_get_audio_type_system(self, qapp: QApplication) -> None:
        """Проверка получения типа аудио - системное."""
        view = AudioView()
        view._system_audio_radio.setChecked(True)
        assert view.get_audio_type() == AudioType.SYSTEM

    def test_get_audio_type_both(self, qapp: QApplication) -> None:
        """Проверка получения типа аудио - оба источника."""
        view = AudioView()
        view._both_audio_radio.setChecked(True)
        assert view.get_audio_type() == AudioType.BOTH

    def test_set_audio_type_none(self, qapp: QApplication) -> None:
        """Проверка установки типа аудио - без аудио."""
        view = AudioView()
        view._mic_radio.setChecked(True)
        view.set_audio_type(AudioType.NONE)
        assert view.get_audio_type() == AudioType.NONE

    def test_set_audio_type_microphone(self, qapp: QApplication) -> None:
        """Проверка установки типа аудио - микрофон."""
        view = AudioView()
        view.set_audio_type(AudioType.MICROPHONE)
        assert view.get_audio_type() == AudioType.MICROPHONE

    def test_set_audio_type_system(self, qapp: QApplication) -> None:
        """Проверка установки типа аудио - системное."""
        view = AudioView()
        view.set_audio_type(AudioType.SYSTEM)
        assert view.get_audio_type() == AudioType.SYSTEM

    def test_set_audio_type_both(self, qapp: QApplication) -> None:
        """Проверка установки типа аудио - оба источника."""
        view = AudioView()
        view.set_audio_type(AudioType.BOTH)
        assert view.get_audio_type() == AudioType.BOTH


class TestAudioViewMicDevice:
    """Тесты выбора устройства микрофона."""

    def test_get_mic_device_index_empty(self, qapp: QApplication) -> None:
        """Проверка получения индекса устройства при пустом списке."""
        with patch("gui.views.audio_view.get_audio_devices") as mock_devices:
            mock_devices.return_value = {"input": []}
            view = AudioView()
            assert view.get_mic_device_index() is None

    def test_get_mic_device_index_with_devices(
        self, qapp: QApplication
    ) -> None:
        """Проверка получения индекса устройства."""
        with patch("gui.views.audio_view.get_audio_devices") as mock_devices:
            mock_devices.return_value = {
                "input": [
                    {"name": "Mic 1", "id": 0},
                    {"name": "Mic 2", "id": 1},
                ]
            }
            view = AudioView()
            assert view.get_mic_device_index() == 0

    def test_get_mic_device_name_empty(self, qapp: QApplication) -> None:
        """Проверка получения имени устройства при пустом списке."""
        with patch("gui.views.audio_view.get_audio_devices") as mock_devices:
            mock_devices.return_value = {"input": []}
            view = AudioView()
            assert view.get_mic_device_name() == ""

    def test_get_mic_device_name_with_devices(
        self, qapp: QApplication
    ) -> None:
        """Проверка получения имени устройства."""
        with patch("gui.views.audio_view.get_audio_devices") as mock_devices:
            mock_devices.return_value = {
                "input": [
                    {"name": "Mic 1", "id": 0},
                    {"name": "Mic 2", "id": 1},
                ]
            }
            view = AudioView()
            assert view.get_mic_device_name() == "Mic 1"

    def test_set_mic_device_index(self, qapp: QApplication) -> None:
        """Проверка установки индекса устройства."""
        with patch("gui.views.audio_view.get_audio_devices") as mock_devices:
            mock_devices.return_value = {
                "input": [
                    {"name": "Mic 1", "id": 0},
                    {"name": "Mic 2", "id": 1},
                ]
            }
            view = AudioView()
            view.set_mic_device_index(1)
            assert view.get_mic_device_index() == 1

    def test_set_mic_device_name(self, qapp: QApplication) -> None:
        """Проверка установки имени устройства."""
        with patch("gui.views.audio_view.get_audio_devices") as mock_devices:
            mock_devices.return_value = {
                "input": [
                    {"name": "Mic 1", "id": 0},
                    {"name": "Mic 2", "id": 1},
                ]
            }
            view = AudioView()
            view.set_mic_device_name("Mic 2")
            assert view.get_mic_device_name() == "Mic 2"


class TestAudioViewSignals:
    """Тесты сигналов AudioView."""

    def test_audio_type_changed_signal(self, qapp: QApplication) -> None:
        """Проверка сигнала изменения типа аудио."""
        view = AudioView()
        signal_received = []

        def on_audio_type_changed(audio_type: AudioType) -> None:
            signal_received.append(audio_type)

        view.audio_type_changed.connect(on_audio_type_changed)

        # Эмулируем клик по радиокнопке
        view._on_button_clicked(view._mic_radio)

        assert len(signal_received) == 1
        assert signal_received[0] == AudioType.MICROPHONE


# ============================================================================
# Тесты VideoView
# ============================================================================


class TestVideoViewInit:
    """Тесты инициализации VideoView."""

    def test_init_creates_widget(self, qapp: QApplication) -> None:
        """Проверка создания виджета."""
        view = VideoView()
        assert view is not None

    def test_default_fps(self, qapp: QApplication) -> None:
        """Проверка FPS по умолчанию."""
        view = VideoView()
        assert view.get_fps() == 30

    def test_default_codec(self, qapp: QApplication) -> None:
        """Проверка кодека по умолчанию."""
        view = VideoView()
        assert view.get_codec() == "libx264"

    def test_default_bitrate(self, qapp: QApplication) -> None:
        """Проверка битрейта по умолчанию."""
        view = VideoView()
        assert view.get_bitrate() == "2M"

    def test_default_format(self, qapp: QApplication) -> None:
        """Проверка формата по умолчанию."""
        view = VideoView()
        assert view.get_format() == "mp4"


class TestVideoViewGetters:
    """Тесты геттеров VideoView."""

    def test_get_fps(self, qapp: QApplication) -> None:
        """Проверка получения FPS."""
        view = VideoView()
        view._fps_spin.setValue(60)
        assert view.get_fps() == 60

    def test_get_codec(self, qapp: QApplication) -> None:
        """Проверка получения кодека."""
        view = VideoView()
        view._codec_combo.setCurrentIndex(1)  # mp4v
        assert view.get_codec() == "mp4v"

    def test_get_bitrate(self, qapp: QApplication) -> None:
        """Проверка получения битрейта."""
        view = VideoView()
        view._bitrate_combo.setCurrentIndex(2)  # 4M
        assert view.get_bitrate() == "4M"

    def test_get_format(self, qapp: QApplication) -> None:
        """Проверка получения формата."""
        view = VideoView()
        view._format_combo.setCurrentIndex(1)  # avi
        assert view.get_format() == "avi"

    def test_get_settings(self, qapp: QApplication) -> None:
        """Проверка получения настроек."""
        view = VideoView()
        view._fps_spin.setValue(60)
        view._codec_combo.setCurrentIndex(1)  # mp4v
        view._bitrate_combo.setCurrentIndex(2)  # 4M
        view._format_combo.setCurrentIndex(1)  # avi

        settings = view.get_settings()
        assert settings.fps == 60
        assert settings.codec == "mp4v"
        assert settings.bitrate == "4M"
        assert settings.format == "avi"


class TestVideoViewSetters:
    """Тесты сеттеров VideoView."""

    def test_set_fps(self, qapp: QApplication) -> None:
        """Проверка установки FPS."""
        view = VideoView()
        view.set_fps(60)
        assert view.get_fps() == 60

    def test_set_codec_existing(self, qapp: QApplication) -> None:
        """Проверка установки существующего кодека."""
        view = VideoView()
        view.set_codec("mp4v")
        assert view.get_codec() == "mp4v"

    def test_set_codec_not_found(self, qapp: QApplication) -> None:
        """Проверка установки несуществующего кодека - остаётся прежний."""
        view = VideoView()
        # _codec_combo не является editable, поэтому setEditText не работает
        # Если кодек не найден, остаётся текущий
        view.set_codec("custom_codec")
        # Кодек должен остаться libx264 (по умолчанию)
        assert view.get_codec() == "libx264"

    def test_set_bitrate_existing(self, qapp: QApplication) -> None:
        """Проверка установки существующего битрейта."""
        view = VideoView()
        view.set_bitrate("4M")
        assert view.get_bitrate() == "4M"

    def test_set_bitrate_custom(self, qapp: QApplication) -> None:
        """Проверка установки пользовательского битрейта."""
        view = VideoView()
        view.set_bitrate("5M")
        assert view.get_bitrate() == "5M"

    def test_set_format(self, qapp: QApplication) -> None:
        """Проверка установки формата."""
        view = VideoView()
        view.set_format("avi")
        assert view.get_format() == "avi"

    def test_set_settings(self, qapp: QApplication) -> None:
        """Проверка установки настроек."""
        view = VideoView()
        settings = VideoSettings(
            fps=60,
            codec="mp4v",
            bitrate="4M",
            format="avi",
        )
        view.set_settings(settings)

        assert view.get_fps() == 60
        assert view.get_codec() == "mp4v"
        assert view.get_bitrate() == "4M"
        assert view.get_format() == "avi"


class TestVideoViewSignals:
    """Тесты сигналов VideoView."""

    def test_fps_changed_signal(self, qapp: QApplication) -> None:
        """Проверка сигнала изменения FPS."""
        view = VideoView()
        signal_received = []

        def on_fps_changed(fps: int) -> None:
            signal_received.append(fps)

        view.fps_changed.connect(on_fps_changed)
        view._fps_spin.setValue(60)

        assert 60 in signal_received

    def test_codec_changed_signal(self, qapp: QApplication) -> None:
        """Проверка сигнала изменения кодека."""
        view = VideoView()
        signal_received = []

        def on_codec_changed(codec: str) -> None:
            signal_received.append(codec)

        view.codec_changed.connect(on_codec_changed)
        view._codec_combo.setCurrentIndex(1)

        assert "mp4v" in signal_received


# ============================================================================
# Тесты OutputView
# ============================================================================


class TestOutputViewInit:
    """Тесты инициализации OutputView."""

    def test_init_creates_widget(self, qapp: QApplication) -> None:
        """Проверка создания виджета."""
        view = OutputView()
        assert view is not None

    def test_default_output_path_empty(self, qapp: QApplication) -> None:
        """Проверка пустого пути вывода по умолчанию."""
        view = OutputView()
        assert view.get_output_path() == ""

    def test_default_format(self, qapp: QApplication) -> None:
        """Проверка формата по умолчанию."""
        view = OutputView()
        assert view._default_format == "mp4"


class TestOutputViewGetters:
    """Тесты геттеров OutputView."""

    def test_get_output_path(self, qapp: QApplication) -> None:
        """Проверка получения пути вывода."""
        view = OutputView()
        view._output_edit.setText("/path/to/output.mp4")
        assert view.get_output_path() == "/path/to/output.mp4"

    def test_get_output_path_as_path(self, qapp: QApplication) -> None:
        """Проверка получения пути вывода как Path."""
        view = OutputView()
        view._output_edit.setText("/path/to/output.mp4")
        assert view.get_output_path_as_path() == Path("/path/to/output.mp4")

    def test_get_output_path_as_path_empty(self, qapp: QApplication) -> None:
        """Проверка получения пустого пути вывода как Path."""
        view = OutputView()
        assert view.get_output_path_as_path() == Path()

    def test_get_settings(self, qapp: QApplication) -> None:
        """Проверка получения настроек."""
        view = OutputView()
        view._output_edit.setText("/path/to/output.mp4")
        settings = view.get_settings()
        assert settings.output_path == "/path/to/output.mp4"


class TestOutputViewSetters:
    """Тесты сеттеров OutputView."""

    def test_set_output_path(self, qapp: QApplication) -> None:
        """Проверка установки пути вывода."""
        view = OutputView()
        view.set_output_path("/path/to/output.mp4")
        assert view.get_output_path() == "/path/to/output.mp4"

    def test_set_default_format(self, qapp: QApplication) -> None:
        """Проверка установки формата по умолчанию."""
        view = OutputView()
        view.set_default_format("avi")
        assert view._default_format == "avi"

    def test_set_settings(self, qapp: QApplication) -> None:
        """Проверка установки настроек."""
        view = OutputView()
        settings = OutputSettings(default_path="/path/to/output.mp4")
        view.set_settings(settings)
        assert view.get_output_path() == "/path/to/output.mp4"


class TestOutputViewSignals:
    """Тесты сигналов OutputView."""

    def test_output_path_changed_signal(self, qapp: QApplication) -> None:
        """Проверка сигнала изменения пути вывода."""
        view = OutputView()
        signal_received = []

        def on_output_path_changed(path: str) -> None:
            signal_received.append(path)

        view.output_path_changed.connect(on_output_path_changed)
        view._output_edit.setText("/path/to/output.mp4")

        assert "/path/to/output.mp4" in signal_received


class TestOutputViewBrowse:
    """Тесты выбора файла через диалог."""

    def test_browse_output_cancelled(self, qapp: QApplication) -> None:
        """Проверка отмены выбора файла."""
        view = OutputView()

        with patch(
            "gui.views.output_view.QFileDialog.getSaveFileName"
        ) as mock_dialog:
            mock_dialog.return_value = ("", "")  # Пользователь отменил
            view._browse_output()
            # Путь не должен измениться
            assert view.get_output_path() == ""

    def test_browse_output_selected(self, qapp: QApplication) -> None:
        """Проверка выбора файла."""
        view = OutputView()

        with patch(
            "gui.views.output_view.QFileDialog.getSaveFileName"
        ) as mock_dialog:
            mock_dialog.return_value = (
                "/selected/path/output.mp4",
                "MP4 файлы (*.mp4)",
            )
            view._browse_output()
            assert view.get_output_path() == "/selected/path/output.mp4"
