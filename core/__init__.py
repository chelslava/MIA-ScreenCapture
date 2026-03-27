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
    CaptureSettings,
    OutputSettings,
    RecentRecording,
    RecordingState,
    RecordingStatus,
    VideoSettings,
)
from core.recording_types import (
    AudioMode,
    AudioRequest,
    AudioType,
    CaptureMode,
    CaptureRequest,
    CaptureType,
    VideoRequest,
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
    "CaptureSettings",
    "OutputSettings",
    "RecentRecording",
    "RecordingState",
    "RecordingStatus",
    "VideoSettings",
    # Recording types (с aliases)
    "AudioMode",
    "AudioType",
    "CaptureMode",
    "CaptureType",
    "AudioRequest",
    "CaptureRequest",
    "VideoRequest",
]
