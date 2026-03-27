"""
Модуль вспомогательных функций
==============================

Предоставляет вспомогательные функции для захвата экрана, определения окон,
перечисления аудиоустройств и проверки FFmpeg.
"""

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

from logger_config import get_module_logger

logger = get_module_logger(__name__)


def get_platform() -> str:
    """
    Получение идентификатора текущей платформы.

    Returns:
        Строка платформы: 'windows', 'linux', 'darwin' (macOS)
    """
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "linux":
        return "linux"
    elif system == "darwin":
        return "darwin"
    return system


def check_ffmpeg() -> tuple[bool, str | None]:
    """
    Проверка доступности FFmpeg в системном PATH.

    Returns:
        Кортеж (доступен, строка_версии)
    """
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            # Извлечение версии из первой строки
            first_line = result.stdout.split("\n")[0]
            version = (
                first_line.split()[2]
                if len(first_line.split()) > 2
                else "unknown"
            )
            logger.info(f"FFmpeg найден: версия {version}")
            return True, version
    except FileNotFoundError:
        logger.warning("FFmpeg не найден в PATH")
    except subprocess.TimeoutExpired:
        logger.error("Таймаут проверки версии FFmpeg")
    except Exception as e:
        logger.error(f"Ошибка проверки FFmpeg: {e}")

    return False, None


def get_ffmpeg_path() -> str | None:
    """
    Получение пути к исполняемому файлу FFmpeg.

    Returns:
        Путь к FFmpeg или None если не найден
    """
    return shutil.which("ffmpeg")


def get_available_windows() -> list[dict[str, Any]]:
    """
    Получение списка всех видимых окон с их заголовками и позициями.

    Returns:
        Список словарей с информацией об окнах:
        [{'title': str, 'x': int, 'y': int, 'width': int, 'height': int}, ...]
    """
    windows = []
    current_platform = get_platform()

    try:
        if current_platform == "windows":
            windows = _get_windows_windows()
        elif current_platform == "linux":
            windows = _get_linux_windows()
        elif current_platform == "darwin":
            windows = _get_macos_windows()
    except Exception as e:
        logger.error(f"Ошибка получения списка окон: {e}")

    return windows


def _get_windows_windows() -> list[dict[str, Any]]:
    """
    Получение окон на платформе Windows с использованием win32gui.

    Returns:
        Список словарей с информацией об окнах
    """
    windows = []

    try:
        import win32con
        import win32gui

        def enum_windows_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:  # Только окна с заголовками
                    rect = win32gui.GetWindowRect(hwnd)
                    windows.append(
                        {
                            "title": title,
                            "hwnd": hwnd,
                            "x": rect[0],
                            "y": rect[1],
                            "width": rect[2] - rect[0],
                            "height": rect[3] - rect[1],
                        }
                    )
            return True

        win32gui.EnumWindows(enum_windows_callback, None)

    except ImportError:
        logger.warning("win32gui недоступен, пробуем pygetwindow")
        try:
            import pygetwindow as gw

            for win in gw.getAllWindows():
                if win.title:
                    windows.append(
                        {
                            "title": win.title,
                            "x": win.left,
                            "y": win.top,
                            "width": win.width,
                            "height": win.height,
                        }
                    )
        except ImportError:
            logger.error("pygetwindow также недоступен")

    return windows


def _get_linux_windows() -> list[dict[str, Any]]:
    """
    Получение окон на платформе Linux с использованием xlib или wmctrl.

    Returns:
        Список словарей с информацией об окнах
    """
    windows = []

    try:
        # Попытка использования команды wmctrl
        result = subprocess.run(
            ["wmctrl", "-lG"], capture_output=True, text=True, timeout=5
        )

        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                parts = line.split(None, 7)
                if len(parts) >= 8:
                    windows.append(
                        {
                            "title": parts[7],
                            "x": int(parts[2]),
                            "y": int(parts[3]),
                            "width": int(parts[4]),
                            "height": int(parts[5]),
                        }
                    )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.warning("wmctrl недоступен")

    return windows


def _get_macos_windows() -> list[dict[str, Any]]:
    """
    Получение окон на macOS с использованием pygetwindow или AppleScript.

    Returns:
        Список словарей с информацией об окнах
    """
    windows = []

    try:
        import pygetwindow as gw

        for win in gw.getAllWindows():
            if win.title:
                windows.append(
                    {
                        "title": win.title,
                        "x": win.left,
                        "y": win.top,
                        "width": win.width,
                        "height": win.height,
                    }
                )
    except ImportError:
        logger.warning("pygetwindow недоступен на macOS")

    return windows


def get_audio_devices() -> dict[str, list[dict[str, Any]]]:
    """
    Получение доступных устройств ввода и вывода аудио.

    Returns:
        Словарь со списками 'input' и 'output' информации об устройствах
    """
    devices: dict[str, list[dict[str, Any]]] = {"input": [], "output": []}

    try:
        import sounddevice as sd

        for i, device in enumerate(sd.query_devices()):
            device_info = {
                "id": i,
                "name": device["name"],
                "channels": device["max_input_channels"]
                if device["max_input_channels"] > 0
                else device["max_output_channels"],
                "sample_rate": device["default_samplerate"],
            }

            if device["max_input_channels"] > 0:
                devices["input"].append(device_info)
            if device["max_output_channels"] > 0:
                devices["output"].append(device_info)

    except ImportError:
        logger.warning("sounddevice недоступен")

        # Возврат к pyaudio
        try:
            import pyaudio

            p = pyaudio.PyAudio()

            for i in range(p.get_device_count()):
                device = p.get_device_info_by_index(i)
                device_info = {
                    "id": i,
                    "name": device["name"],
                    "channels": device["maxInputChannels"]
                    if device["maxInputChannels"] > 0
                    else device["maxOutputChannels"],
                    "sample_rate": int(device["defaultSampleRate"]),
                }

                if device["maxInputChannels"] > 0:
                    devices["input"].append(device_info)
                if device["maxOutputChannels"] > 0:
                    devices["output"].append(device_info)

            p.terminate()

        except ImportError:
            logger.error("Ни sounddevice, ни pyaudio недоступны")

    return devices


def get_screen_size() -> tuple[int, int]:
    """
    Получение размера основного экрана.

    Returns:
        Кортеж (ширина, высота)
    """
    current_platform = get_platform()
    if current_platform != "windows":
        # Проект ориентирован на Windows-capture.
        return 1920, 1080

    try:
        import ctypes

        user32 = ctypes.windll.user32
        width = int(user32.GetSystemMetrics(0))
        height = int(user32.GetSystemMetrics(1))
        if width > 0 and height > 0:
            return width, height
    except Exception as e:
        logger.error(f"Ошибка получения размера экрана: {e}")
    return 1920, 1080  # Значение по умолчанию


def get_all_monitors() -> list[dict[str, int]]:
    """
    Получение информации о всех подключенных мониторах.

    Returns:
        Список словарей с информацией о мониторах
    """
    current_platform = get_platform()
    if current_platform != "windows":
        width, height = get_screen_size()
        return [{"id": 1, "x": 0, "y": 0, "width": width, "height": height}]

    monitors: list[dict[str, int]] = []
    try:
        import ctypes
        from ctypes import wintypes

        monitor_count = 0

        def _callback(h_monitor, hdc_monitor, lprc_monitor, dw_data):
            nonlocal monitor_count
            rect = lprc_monitor.contents
            monitor_count += 1
            monitors.append(
                {
                    "id": monitor_count,
                    "x": int(rect.left),
                    "y": int(rect.top),
                    "width": int(rect.right - rect.left),
                    "height": int(rect.bottom - rect.top),
                }
            )
            return 1

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        monitor_enum_proc = ctypes.WINFUNCTYPE(
            ctypes.c_int,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(RECT),
            wintypes.LPARAM,
        )
        ctypes.windll.user32.EnumDisplayMonitors(
            0, 0, monitor_enum_proc(_callback), 0
        )
    except Exception as e:
        logger.error(f"Ошибка получения мониторов: {e}")

    if not monitors:
        width, height = get_screen_size()
        monitors.append({"id": 1, "x": 0, "y": 0, "width": width, "height": height})
    return monitors


def get_available_monitors() -> list[dict[str, Any]]:
    """
    Получение списка доступных мониторов для выбора.
    
    Это alias для get_all_monitors() с дополнительными метаданными.

    Returns:
        Список словарей с информацией о мониторах:
        [{
            'index': int,
            'x': int, 'y': int,
            'width': int, 'height': int,
            'name': str,
            'is_primary': bool
        }, ...]
    """
    monitors = get_all_monitors()
    result = []

    # Определение primary монитора (обычно 0,0)
    primary_monitor = None
    for i, mon in enumerate(monitors):
        is_primary = (mon['x'] == 0 and mon['y'] == 0)
        if is_primary:
            primary_monitor = i
        result.append({
            'index': i,
            'x': mon['x'],
            'y': mon['y'],
            'width': mon['width'],
            'height': mon['height'],
            'name': f"Monitor {i + 1}",
            'is_primary': is_primary,
        })

    # Если не нашли primary по координатам, считаем первый primary
    if primary_monitor is None and result:
        result[0]['is_primary'] = True

    return result


def validate_rect_coords(
    x1: int, y1: int, x2: int, y2: int
) -> tuple[int, int, int, int]:
    """
    Проверка и нормализация координат прямоугольника.

    Args:
        x1, y1: Верхний левый угол
        x2, y2: Нижний правый угол

    Returns:
        Нормализованные координаты (left, top, right, bottom)
    """
    left = min(x1, x2)
    top = min(y1, y2)
    right = max(x1, x2)
    bottom = max(y1, y2)

    # Обеспечение минимального размера
    if right - left < 10:
        right = left + 10
    if bottom - top < 10:
        bottom = top + 10

    return left, top, right, bottom


def format_time(seconds: float) -> str:
    """
    Форматирование секунд в строку ЧЧ:ММ:СС.

    Args:
        seconds: Время в секундах

    Returns:
        Отформатированная строка времени
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_filesize(size_bytes: int) -> str:
    """
    Форматирование размера файла в читаемом формате.

    Args:
        size_bytes: Размер в байтах

    Returns:
        Отформатированная строка размера (например, "1.5 MB")
    """
    size: float = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def ensure_directory(path: Path) -> bool:
    """
    Обеспечение существования директории, создание при необходимости.

    Args:
        path: Путь к директории

    Returns:
        True если директория существует или была создана
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Ошибка создания директории {path}: {e}")
        return False


def is_valid_output_path(path: str) -> bool:
    """
    Проверка допустимости пути вывода для записи.

    Args:
        path: Путь к выходному файлу

    Returns:
        True если путь допустим
    """
    try:
        p = Path(path)
        parent = p.parent

        # Проверка существования родительской директории или возможности создания
        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)

        # Проверка возможности записи в расположение
        if p.exists():
            return os.access(path, os.W_OK)
        return os.access(parent, os.W_OK)

    except Exception:
        return False


def get_unique_filename(base_path: Path, filename: str) -> Path:
    """
    Получение уникального имени файла добавлением номера если файл существует.

    Args:
        base_path: Путь к директории
        filename: Желаемое имя файла

    Returns:
        Уникальный путь к файлу
    """
    full_path = base_path / filename

    if not full_path.exists():
        return full_path

    name, ext = os.path.splitext(filename)
    counter = 1

    while full_path.exists():
        new_filename = f"{name}_{counter}{ext}"
        full_path = base_path / new_filename
        counter += 1

    return full_path


class Singleton(type):
    """
    Метакласс Singleton для обеспечения существования только одного экземпляра класса.
    """

    _instances: dict[type, Any] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
