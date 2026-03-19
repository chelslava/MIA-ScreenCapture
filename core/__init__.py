"""
Модуль core
===========

Содержит базовые компоненты архитектуры приложения.
"""

from core.container import (
    Container,
    IAPIServer,
    IConfigManager,
    IRecordingManager,
    ITaskScheduler,
    get_container,
    reset_container,
)

__all__ = [
    "Container",
    "IConfigManager",
    "IRecordingManager",
    "ITaskScheduler",
    "IAPIServer",
    "get_container",
    "reset_container",
]
