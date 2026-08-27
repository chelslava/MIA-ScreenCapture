"""Пакет библиотеки записей MIA-ScreenCapture."""

from __future__ import annotations

from core.library.manager import LibraryManager
from core.library.models import RecordingMetadata
from core.library.scanner import extract_video_metadata, generate_thumbnail

__all__ = [
    "LibraryManager",
    "RecordingMetadata",
    "extract_video_metadata",
    "generate_thumbnail",
]
