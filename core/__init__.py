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
from core.lifecycle import (
    GracefulShutdown,
    get_shutdown_manager,
    register_shutdown_handler,
    request_shutdown,
    reset_shutdown_manager,
)
from core.recording_state import (
    AudioSettings,
    AudioType,
    CaptureSettings,
    CaptureType,
    OutputSettings,
    RecentRecording,
    RecordingState,
    RecordingStatus,
    VideoSettings,
)

__all__ = [
    # Container
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
    # Lifecycle
    "GracefulShutdown",
    "get_shutdown_manager",
    "register_shutdown_handler",
    "request_shutdown",
    "reset_shutdown_manager",
    # Recording state
    "AudioSettings",
    "AudioType",
    "CaptureSettings",
    "CaptureType",
    "OutputSettings",
    "RecentRecording",
    "RecordingState",
    "RecordingStatus",
    "VideoSettings",
]
