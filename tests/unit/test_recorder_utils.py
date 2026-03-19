"""
Тесты для модуля вспомогательных функций
========================================

Проверяет функциональность recorder/utils.py.
"""

import subprocess
from unittest.mock import MagicMock, patch

from recorder.utils import (
    check_ffmpeg,
    format_filesize,
    format_time,
    get_audio_devices,
    get_available_windows,
    get_ffmpeg_path,
    get_platform,
    get_screen_size,
    validate_rect_coords,
)


class TestGetPlatform:
    """Тесты для функции get_platform."""

    def test_windows_platform(self):
        """Проверка определения Windows."""
        with patch('platform.system', return_value='Windows'):
            assert get_platform() == 'windows'

    def test_linux_platform(self):
        """Проверка определения Linux."""
        with patch('platform.system', return_value='Linux'):
            assert get_platform() == 'linux'

    def test_darwin_platform(self):
        """Проверка определения macOS."""
        with patch('platform.system', return_value='Darwin'):
            assert get_platform() == 'darwin'

    def test_unknown_platform(self):
        """Проверка неизвестной платформы."""
        with patch('platform.system', return_value='UnknownOS'):
            assert get_platform() == 'unknownos'


class TestCheckFFmpeg:
    """Тесты для функции check_ffmpeg."""

    @patch('subprocess.run')
    def test_ffmpeg_available(self, mock_run):
        """Проверка доступности FFmpeg."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="ffmpeg version 5.0\nCopyright (c) 2000-2022"
        )

        available, version = check_ffmpeg()

        assert available is True
        assert version == "5.0"

    @patch('subprocess.run')
    def test_ffmpeg_not_found(self, mock_run):
        """Проверка отсутствия FFmpeg."""
        mock_run.side_effect = FileNotFoundError()

        available, version = check_ffmpeg()

        assert available is False
        assert version is None

    @patch('subprocess.run')
    def test_ffmpeg_timeout(self, mock_run):
        """Проверка таймаута при проверке FFmpeg."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=10)

        available, version = check_ffmpeg()

        assert available is False
        assert version is None

    @patch('subprocess.run')
    def test_ffmpeg_unexpected_error(self, mock_run):
        """Проверка неожиданной ошибки при проверке FFmpeg."""
        mock_run.side_effect = RuntimeError("Unexpected error")

        available, version = check_ffmpeg()

        assert available is False
        assert version is None


class TestGetFFmpegPath:
    """Тесты для функции get_ffmpeg_path."""

    @patch('shutil.which')
    def test_ffmpeg_path_found(self, mock_which):
        """Проверка нахождения пути к FFmpeg."""
        mock_which.return_value = "/usr/bin/ffmpeg"

        path = get_ffmpeg_path()

        assert path == "/usr/bin/ffmpeg"

    @patch('shutil.which')
    def test_ffmpeg_path_not_found(self, mock_which):
        """Проверка отсутствия пути к FFmpeg."""
        mock_which.return_value = None

        path = get_ffmpeg_path()

        assert path is None


class TestGetAvailableWindows:
    """Тесты для функции get_available_windows."""

    @patch('recorder.utils.get_platform')
    @patch('recorder.utils._get_windows_windows')
    def test_windows_platform(self, mock_windows_func, mock_platform):
        """Проверка получения окон на Windows."""
        mock_platform.return_value = 'windows'
        mock_windows_func.return_value = [
            {'title': 'Test Window', 'x': 0, 'y': 0, 'width': 800, 'height': 600}
        ]

        windows = get_available_windows()

        assert len(windows) == 1
        assert windows[0]['title'] == 'Test Window'

    @patch('recorder.utils.get_platform')
    @patch('recorder.utils._get_linux_windows')
    def test_linux_platform(self, mock_linux_func, mock_platform):
        """Проверка получения окон на Linux."""
        mock_platform.return_value = 'linux'
        mock_linux_func.return_value = [
            {'title': 'Linux Window', 'x': 100, 'y': 100, 'width': 1024, 'height': 768}
        ]

        windows = get_available_windows()

        assert len(windows) == 1
        assert windows[0]['title'] == 'Linux Window'

    @patch('recorder.utils.get_platform')
    @patch('recorder.utils._get_macos_windows')
    def test_macos_platform(self, mock_macos_func, mock_platform):
        """Проверка получения окон на macOS."""
        mock_platform.return_value = 'darwin'
        mock_macos_func.return_value = [
            {'title': 'macOS Window', 'x': 50, 'y': 50, 'width': 1280, 'height': 720}
        ]

        windows = get_available_windows()

        assert len(windows) == 1
        assert windows[0]['title'] == 'macOS Window'

    @patch('recorder.utils._get_windows_windows')
    @patch('recorder.utils._get_linux_windows')
    @patch('recorder.utils._get_macos_windows')
    @patch('recorder.utils.get_platform')
    def test_exception_handling(self, mock_platform, mock_macos, mock_linux, mock_windows):
        """Проверка обработки исключений."""
        mock_platform.return_value = 'windows'
        mock_windows.side_effect = RuntimeError("Platform error")

        windows = get_available_windows()

        assert windows == []


class TestGetAudioDevices:
    """Тесты для функции get_audio_devices."""

    def test_audio_devices_structure(self):
        """Проверка структуры возвращаемых устройств."""
        # Мокаем sounddevice внутри функции get_audio_devices
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = [
            {'name': 'Microphone', 'max_input_channels': 2, 'max_output_channels': 0, 'default_samplerate': 44100},
            {'name': 'Speakers', 'max_input_channels': 0, 'max_output_channels': 2, 'default_samplerate': 44100}
        ]

        with patch.dict('sys.modules', {'sounddevice': mock_sd}):
            devices = get_audio_devices()

            assert 'input' in devices
            assert 'output' in devices


class TestGetScreenSize:
    """Тесты для функции get_screen_size."""

    def test_screen_size(self):
        """Проверка получения размера экрана."""
        # Функция использует mss, мокаем её
        mock_mss = MagicMock()
        mock_sct = MagicMock()
        mock_sct.monitors = [
            {},  # Первый элемент пустой (all monitors combined)
            {'width': 1920, 'height': 1080, 'left': 0, 'top': 0}  # Основной монитор
        ]
        mock_mss.mss.return_value.__enter__ = MagicMock(return_value=mock_sct)
        mock_mss.mss.return_value.__exit__ = MagicMock(return_value=False)

        with patch.dict('sys.modules', {'mss': mock_mss}):
            width, height = get_screen_size()

            assert width == 1920
            assert height == 1080


class TestValidateRectCoords:
    """Тесты для функции validate_rect_coords."""

    def test_normal_coords(self):
        """Проверка нормальных координат."""
        left, top, right, bottom = validate_rect_coords(100, 100, 800, 600)

        assert left == 100
        assert top == 100
        assert right == 800
        assert bottom == 600

    def test_swapped_coords(self):
        """Проверка переставленных координат (x2 < x1)."""
        left, top, right, bottom = validate_rect_coords(800, 600, 100, 100)

        # Координаты должны быть упорядочены
        assert left == 100
        assert top == 100
        assert right == 800
        assert bottom == 600

    def test_negative_coords(self):
        """Проверка отрицательных координат."""
        left, top, right, bottom = validate_rect_coords(-10, -10, 800, 600)

        # Текущая реализация не обрезает отрицательные координаты
        # Она только упорядочивает их (min/max)
        assert left == -10
        assert top == -10
        assert right == 800
        assert bottom == 600

    def test_minimum_size(self):
        """Проверка минимального размера области."""
        # Слишком маленькая область
        left, top, right, bottom = validate_rect_coords(100, 100, 101, 101)

        # Должен быть минимальный размер
        assert (right - left) >= 10
        assert (bottom - top) >= 10


class TestFormatTime:
    """Тесты для функции format_time."""

    def test_seconds_only(self):
        """Проверка форматирования только секунд."""
        assert format_time(45) == "00:45"

    def test_minutes_and_seconds(self):
        """Проверка форматирования минут и секунд."""
        assert format_time(125) == "02:05"

    def test_hours(self):
        """Проверка форматирования часов."""
        assert format_time(3661) == "01:01:01"

    def test_zero(self):
        """Проверка нулевого времени."""
        assert format_time(0) == "00:00"

    def test_large_value(self):
        """Проверка большого значения."""
        assert format_time(36000) == "10:00:00"


class TestFormatFilesize:
    """Тесты для функции format_filesize."""

    def test_bytes(self):
        """Проверка форматирования байтов."""
        assert format_filesize(500) == "500.0 B"

    def test_kilobytes(self):
        """Проверка форматирования килобайтов."""
        assert format_filesize(1024) == "1.0 KB"
        assert format_filesize(1536) == "1.5 KB"

    def test_megabytes(self):
        """Проверка форматирования мегабайтов."""
        assert format_filesize(1048576) == "1.0 MB"
        assert format_filesize(1572864) == "1.5 MB"

    def test_gigabytes(self):
        """Проверка форматирования гигабайтов."""
        assert format_filesize(1073741824) == "1.0 GB"

    def test_zero(self):
        """Проверка нулевого размера."""
        assert format_filesize(0) == "0.0 B"


class TestWindowsSpecificFunctions:
    """Тесты для Windows-специфичных функций."""

    @patch('recorder.utils.get_platform')
    def test_get_windows_windows_with_win32gui(self, mock_platform):
        """Проверка получения окон через win32gui."""
        mock_platform.return_value = 'windows'

        with patch.dict('sys.modules', {
            'win32gui': MagicMock(),
            'win32con': MagicMock()
        }):
            import win32gui

            # Настройка mock
            def mock_enum_windows(callback, _):
                callback(1, None)  # Первое окно
                callback(2, None)  # Второе окно

            win32gui.EnumWindows = mock_enum_windows
            win32gui.IsWindowVisible = lambda hwnd: hwnd == 1
            win32gui.GetWindowText = lambda hwnd: f"Window {hwnd}"
            win32gui.GetWindowRect = lambda hwnd: (0, 0, 800, 600)

            from recorder.utils import _get_windows_windows
            windows = _get_windows_windows()

            # Только первое окно видимое
            assert len(windows) == 1
            assert windows[0]['title'] == "Window 1"


class TestLinuxSpecificFunctions:
    """Тесты для Linux-специфичных функций."""

    @patch('subprocess.run')
    def test_get_linux_windows_wmctrl(self, mock_run):
        """Проверка получения окон через wmctrl."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="0x02400003  0 100  100  800  600  hostname Window Title\n"
                   "0x02400004  0 200  200  1024 768  hostname Another Window\n"
        )

        from recorder.utils import _get_linux_windows
        windows = _get_linux_windows()

        assert len(windows) == 2
        assert windows[0]['title'] == "Window Title"
        assert windows[0]['width'] == 800

    @patch('subprocess.run')
    def test_get_linux_windows_wmctrl_not_found(self, mock_run):
        """Проверка отсутствия wmctrl."""
        mock_run.side_effect = FileNotFoundError()

        from recorder.utils import _get_linux_windows
        windows = _get_linux_windows()

        assert windows == []


class TestMacOSSpecificFunctions:
    """Тесты для macOS-специфичных функций."""

    @patch('pygetwindow.getAllWindows')
    def test_get_macos_windows(self, mock_get_windows):
        """Проверка получения окон на macOS."""
        mock_window1 = MagicMock()
        mock_window1.title = "Safari"
        mock_window1.left = 0
        mock_window1.top = 0
        mock_window1.width = 1200
        mock_window1.height = 800

        mock_window2 = MagicMock()
        mock_window2.title = "Finder"
        mock_window2.left = 100
        mock_window2.top = 100
        mock_window2.width = 600
        mock_window2.height = 400

        mock_get_windows.return_value = [mock_window1, mock_window2]

        with patch.dict('sys.modules', {'pygetwindow': MagicMock(getAllWindows=mock_get_windows)}):
            from recorder.utils import _get_macos_windows
            windows = _get_macos_windows()

            assert len(windows) == 2
            assert windows[0]['title'] == "Safari"
