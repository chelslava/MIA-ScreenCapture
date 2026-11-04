"""Core types for recording parameters.

Does not depend on the GUI layer and is used in use-case services.
Single source of truth for types across the application.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, StrEnum


class CaptureMode(Enum):
    """
    Screen capture mode.

    Used across all application layers.
    Values are compatible with API and CLI.
    """

    FULL = "full"
    WINDOW = "window"
    RECT = "rect"


class AudioMode(Enum):
    """
    Audio recording mode.

    Used across all application layers.
    Values are compatible with API and CLI.
    """

    NONE = "none"
    MIC = "mic"
    SYSTEM = "system"
    BOTH = "both"


# Aliases for backward compatibility
CaptureType = CaptureMode
AudioType = AudioMode


class PiPPosition(StrEnum):
    """Угол основного видео для PiP-оверлея веб-камеры (#165)."""

    BOTTOM_RIGHT = "bottom-right"
    BOTTOM_LEFT = "bottom-left"
    TOP_RIGHT = "top-right"
    TOP_LEFT = "top-left"


@dataclass(frozen=True)
class PiPSettings:
    """Настройки PiP-оверлея веб-камеры (#165).

    Атрибуты:
        enabled: Наложение включено.
        device_name: Имя устройства DirectShow; пустая строка —
            первое найденное устройство.
        position: Угол основного видео.
        size_percent: Ширина окна камеры в процентах от ширины
            основного видео.
        margin_px: Отступ окна камеры от краёв, px.
    """

    enabled: bool = False
    device_name: str = ""
    position: PiPPosition = PiPPosition.BOTTOM_RIGHT
    size_percent: int = 20
    margin_px: int = 24


@dataclass(frozen=True)
class CaptureRequest:
    """Screen capture parameters at core level."""

    mode: CaptureMode
    window_title: str
    rect_coords: tuple[int, int, int, int]


@dataclass(frozen=True)
class AudioRequest:
    """Audio parameters at core level."""

    mode: AudioMode
    mic_device_index: int | None = None


@dataclass(frozen=True)
class VideoRequest:
    """Video parameters at core level."""

    fps: int
    codec: str
    bitrate: str
    format: str
    pip: PiPSettings | None = None
