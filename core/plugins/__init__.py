"""Пакет плагин-системы MIA-ScreenCapture."""

from __future__ import annotations

from core.plugins.manager import PluginManager
from core.plugins.protocol import (
    MIAPlugin,
    PluginMetadata,
    PluginStatus,
)
from core.plugins.step import PluginPostProcessingStep

__all__ = [
    "MIAPlugin",
    "PluginManager",
    "PluginMetadata",
    "PluginPostProcessingStep",
    "PluginStatus",
]
