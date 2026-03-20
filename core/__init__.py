"""
Модуль core
===========

Содержит базовые компоненты архитектуры приложения.
"""

from core.container import (
    Container,
    IAPIServer,
    IConfigManager,
    IRecordingController,
    IRecordingManager,
    IRecordingState,
    ISettingsController,
    ITaskScheduler,
    get_container,
    reset_container,
)

__all__ = [
    "Container",
    "IConfigManager",
    "IRecordingController",
    "IRecordingManager",
    "IRecordingState",
    "ISettingsController",
    "ITaskScheduler",
    "IAPIServer",
    "get_container",
    "reset_container",
]
