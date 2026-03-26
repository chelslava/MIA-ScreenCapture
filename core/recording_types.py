"""
Core-типы для параметров записи.

Не зависят от GUI-слоя и используются в use-case сервисах.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CaptureMode(Enum):
    """Режим захвата экрана."""

    FULL = "full"
    WINDOW = "window"
    RECT = "rect"


class AudioMode(Enum):
    """Режим записи аудио."""

    NONE = "none"
    MIC = "mic"
    SYSTEM = "system"
    BOTH = "both"


@dataclass(frozen=True)
class CaptureRequest:
    """Параметры захвата экрана на уровне core."""

    mode: CaptureMode
    window_title: str
    rect_coords: tuple[int, int, int, int]


@dataclass(frozen=True)
class AudioRequest:
    """Параметры аудио на уровне core."""

    mode: AudioMode
    mic_device_index: int | None = None


@dataclass(frozen=True)
class VideoRequest:
    """Параметры видео на уровне core."""

    fps: int
    codec: str
    bitrate: str
    format: str
