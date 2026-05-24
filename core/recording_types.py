"""Core types for recording parameters.

Does not depend on the GUI layer and is used in use-case services.
Single source of truth for types across the application.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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
