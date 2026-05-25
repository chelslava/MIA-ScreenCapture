"""
Utility functions module.

Provides helpers for screen capture, window enumeration,
audio device listing, and FFmpeg availability checks.
"""

import os
import platform
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from logger_config import get_module_logger

if TYPE_CHECKING:
    pass

logger = get_module_logger(__name__)

_MIN_FFMPEG_VERSION = (4, 0, 0)


@dataclass
class FFmpegStatus:
    """Result of an FFmpeg availability check."""

    available: bool
    version: str | None = None
    path: str | None = None
    error: str | None = None
    recommendation: str | None = None


def get_subprocess_creationflags() -> int:
    """Return flags to suppress a console window on Windows."""
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def get_platform() -> str:
    """
    Return the current platform identifier.

    Returns:
        One of 'windows', 'linux', or 'darwin' (macOS).
    """
    system = platform.system().lower()
    if system == "windows":
        return "windows"
    elif system == "linux":
        return "linux"
    elif system == "darwin":
        return "darwin"
    return system


def check_ffmpeg() -> FFmpegStatus:
    """
    Check FFmpeg availability.

    Returns:
        FFmpegStatus with fields: available, version, path, error, recommendation.
    """
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        msg = "FFmpeg not found in PATH"
        rec = (
            "Install FFmpeg and add it to PATH. "
            "Download: https://ffmpeg.org/download.html"
        )
        logger.warning(msg)
        return FFmpegStatus(available=False, error=msg, recommendation=rec)

    try:
        creationflags = get_subprocess_creationflags()
        run_kwargs: dict[str, Any] = {
            "capture_output": True,
            "text": True,
            "timeout": 10,
        }
        if creationflags:
            run_kwargs["creationflags"] = creationflags

        result = subprocess.run([ffmpeg_path, "-version"], **run_kwargs)

        if result.returncode != 0:
            msg = f"FFmpeg returned code {result.returncode}"
            logger.error(msg)
            return FFmpegStatus(
                available=False,
                path=ffmpeg_path,
                error=msg,
                recommendation="Reinstall FFmpeg.",
            )

        first_line = result.stdout.split("\n")[0]
        parts = first_line.split()
        version = parts[2] if len(parts) > 2 else "unknown"

        recommendation: str | None = None
        version_match = re.match(r"(\d+)\.(\d+)(?:\.(\d+))?", version)
        if version_match:
            major = int(version_match.group(1))
            minor = int(version_match.group(2))
            patch_ver = int(version_match.group(3) or 0)
            detected = (major, minor, patch_ver)
            if detected < _MIN_FFMPEG_VERSION:
                min_str = ".".join(str(v) for v in _MIN_FFMPEG_VERSION)
                recommendation = (
                    f"FFmpeg version {version} is outdated. "
                    f"Version {min_str} or newer is recommended."
                )
                logger.warning(
                    "FFmpeg version %s is outdated, >= %s required",
                    version,
                    min_str,
                )

        logger.info("FFmpeg found: version %s, path %s", version, ffmpeg_path)
        return FFmpegStatus(
            available=True,
            version=version,
            path=ffmpeg_path,
            recommendation=recommendation,
        )

    except FileNotFoundError:
        msg = f"FFmpeg not found at path: {ffmpeg_path}"
        rec = (
            "FFmpeg was found in PATH but failed to run. "
            "Check permissions or reinstall FFmpeg."
        )
        logger.warning(msg)
        return FFmpegStatus(
            available=False,
            path=ffmpeg_path,
            error=msg,
            recommendation=rec,
        )
    except subprocess.TimeoutExpired:
        msg = "Timeout while checking FFmpeg version"
        logger.error(msg)
        return FFmpegStatus(
            available=False,
            path=ffmpeg_path,
            error=msg,
            recommendation="Check whether an FFmpeg process is hanging on the system.",
        )
    except Exception as e:
        msg = f"FFmpeg check error: {e}"
        logger.error(msg)
        return FFmpegStatus(available=False, path=ffmpeg_path, error=msg)


def get_executable_path(executable_name: str) -> str | None:
    """
    Return the absolute path to an executable.

    Args:
        executable_name: Name of the executable to find.

    Returns:
        Absolute path, or None if not found.
    """
    executable_path = shutil.which(executable_name)
    if executable_path is None:
        return None
    return str(Path(executable_path).resolve(strict=False))


def get_ffmpeg_path() -> str | None:
    """Return the absolute path to the FFmpeg executable, or None."""
    return get_executable_path("ffmpeg")


def get_ffprobe_path() -> str | None:
    """Return the absolute path to the FFprobe executable, or None."""
    return get_executable_path("ffprobe")


def get_available_windows() -> list[dict[str, Any]]:
    """
    Return a list of all visible windows with their titles and positions.

    Returns:
        List of dicts: [{'title': str, 'x': int, 'y': int, 'width': int, 'height': int}, ...]
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
        logger.error(f"Failed to enumerate windows: {e}")

    return windows


def _get_windows_windows() -> list[dict[str, Any]]:
    """Return windows on Windows using win32gui."""
    windows = []

    try:
        import win32gui

        def enum_windows_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:  # Only windows with titles
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
        logger.warning("win32gui not available, trying pygetwindow")
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
            logger.error("pygetwindow is also not available")

    return windows


def _get_linux_windows() -> list[dict[str, Any]]:
    """Return windows on Linux using wmctrl."""
    windows = []

    try:
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
        logger.warning("wmctrl not available")

    return windows


def _get_macos_windows() -> list[dict[str, Any]]:
    """Return windows on macOS using pygetwindow."""
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
        logger.warning("pygetwindow not available on macOS")

    return windows


def get_audio_devices() -> dict[str, list[dict[str, Any]]]:
    """
    Return available audio input and output devices.

    Returns:
        Dict with 'input' and 'output' lists of device info dicts.
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
        logger.warning("sounddevice not available")

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
            logger.error("Neither sounddevice nor pyaudio is available")

    return devices


def get_screen_size() -> tuple[int, int]:
    """
    Return the primary screen size.

    Returns:
        Tuple (width, height).
    """
    current_platform = get_platform()
    if current_platform != "windows":
        # Project targets Windows capture.
        return 1920, 1080

    try:
        import ctypes

        # Windows-specific: ctypes.windll.user32 not available in type stubs
        user32: Any = ctypes.windll.user32  # type: ignore[attr-defined, unused-ignore]
        width = int(user32.GetSystemMetrics(0))
        height = int(user32.GetSystemMetrics(1))
        if width > 0 and height > 0:
            return width, height
    except Exception as e:
        logger.error(f"Failed to get screen size: {e}")
    return 1920, 1080  # Default fallback


def get_all_monitors() -> list[dict[str, int]]:
    """
    Return information about all connected monitors.

    Returns:
        List of dicts with monitor info.
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

        # Windows-specific: ctypes.WINFUNCTYPE not available in type stubs
        monitor_enum_proc: Any = ctypes.WINFUNCTYPE(  # type: ignore[attr-defined, unused-ignore]
            ctypes.c_int,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(RECT),
            wintypes.LPARAM,
        )
        # Windows-specific: ctypes.windll.user32 not available in type stubs
        ctypes.windll.user32.EnumDisplayMonitors(  # type: ignore[attr-defined, unused-ignore]
            0, 0, monitor_enum_proc(_callback), 0
        )
    except Exception as e:
        logger.error(f"Failed to enumerate monitors: {e}")

    if not monitors:
        width, height = get_screen_size()
        monitors.append(
            {"id": 1, "x": 0, "y": 0, "width": width, "height": height}
        )
    return monitors


def get_available_monitors() -> list[dict[str, Any]]:
    """
    Return the list of available monitors with metadata.

    This is an alias for get_all_monitors() with additional metadata fields.

    Returns:
        List of dicts: [{'index', 'x', 'y', 'width', 'height', 'name', 'is_primary'}, ...]
    """
    monitors = get_all_monitors()
    result = []

    # Identify the primary monitor (conventionally at 0,0).
    primary_monitor = None
    for i, mon in enumerate(monitors):
        is_primary = mon["x"] == 0 and mon["y"] == 0
        if is_primary:
            primary_monitor = i
        result.append(
            {
                "index": i,
                "x": mon["x"],
                "y": mon["y"],
                "width": mon["width"],
                "height": mon["height"],
                "name": f"Monitor {i + 1}",
                "is_primary": is_primary,
            }
        )

    # If no monitor is at 0,0 treat the first one as primary.
    if primary_monitor is None and result:
        result[0]["is_primary"] = True

    return result


def validate_rect_coords(
    x1: int, y1: int, x2: int, y2: int
) -> tuple[int, int, int, int]:
    """
    Validate and normalize rectangle coordinates.

    .. deprecated::
        Use core.geometry.validate_rect_coords() instead of this function.

    Args:
        x1, y1: Top-left corner.
        x2, y2: Bottom-right corner.

    Returns:
        Normalized coordinates (left, top, right, bottom).
    """
    # Import inside function to avoid circular dependencies
    from core.geometry import validate_rect_coords as geometry_validate

    # Call new function without strict checks (old behavior)
    return geometry_validate(x1, y1, x2, y2, strict=False)  # type: ignore[no-any-return]


def format_time(seconds: float) -> str:
    """
    Format seconds as HH:MM:SS.

    Args:
        seconds: Time in seconds.

    Returns:
        Formatted time string.
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_filesize(size_bytes: int) -> str:
    """
    Format a file size in human-readable form.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Formatted size string (e.g. "1.5 MB").
    """
    size: float = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def ensure_directory(path: Path) -> bool:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path.

    Returns:
        True if the directory exists or was created.
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Failed to create directory {path}: {e}")
        return False


def is_valid_output_path(path: str) -> bool:
    """
    Check whether an output path is writable.

    Args:
        path: Output file path.

    Returns:
        True if the path is valid and writable.
    """
    try:
        p = Path(path)
        parent = p.parent

        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)

        if p.exists():
            return os.access(path, os.W_OK)
        return os.access(parent, os.W_OK)

    except Exception:
        return False


def get_unique_filename(base_path: Path, filename: str) -> Path:
    """
    Return a unique file path by appending a counter if the file already exists.

    Args:
        base_path: Directory path.
        filename: Desired file name.

    Returns:
        Unique file path.
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


def get_available_disk_space(path: Path) -> int:
    """
    Return available disk space in bytes for the given path.

    Args:
        path: File or directory path to check.

    Returns:
        Free bytes on the disk.
    """
    # If the path looks like a file (has an extension), check its parent.
    if path.suffix or path.is_file():
        check_path = path.parent
    else:
        check_path = path
        check_path.mkdir(parents=True, exist_ok=True)

    stat = shutil.disk_usage(str(check_path))
    return stat.free


def check_disk_space(
    output_path: Path,
    min_space_mb: int = 100,
    estimated_size_mb: int | None = None,
) -> tuple[bool, int, str | None]:
    """
    Check whether there is enough disk space for a recording.

    Args:
        output_path: Output file path.
        min_space_mb: Minimum free space in MB (default 100).
        estimated_size_mb: Expected file size in MB (optional).

    Returns:
        Tuple (enough_space, free_bytes, error_message).
    """
    try:
        free_bytes = get_available_disk_space(output_path)
        free_mb = free_bytes / (1024 * 1024)

        required_mb = min_space_mb
        if estimated_size_mb is not None:
            required_mb = max(min_space_mb, estimated_size_mb)

        if free_mb < required_mb:
            error_msg = (
                f"Not enough disk space: {free_mb:.0f} MB free, "
                f"minimum {required_mb:.0f} MB required"
            )
            return False, free_bytes, error_msg

        return True, free_bytes, None

    except FileNotFoundError as e:
        error_msg = f"Path not accessible: {e}"
        return False, 0, error_msg
    except OSError as e:
        error_msg = f"Disk check error: {e}"
        return False, 0, error_msg


class Singleton(type):
    """Metaclass that ensures only one instance of a class exists."""

    _instances: dict[type, Any] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]
