"""
Unified contracts для API, CLI и Scheduler.

Предоставляет единые модели данных для использования во всех слоях приложения.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RecordingParams(BaseModel):
    """Unified recording parameters contract.

    Используется в API, CLI, Scheduler для консистентности параметров записи.
    """

    area: Literal["full", "window", "rect"] = "full"
    window_title: str | None = None
    rect: list[int] | None = Field(default=None, min_length=4, max_length=4)
    audio: Literal["none", "mic", "system", "both"] = "none"
    output_path: str | None = None
    fps: int = Field(default=30, ge=1, le=120, description="Frames per second")
    codec: str = "libx264"
    bitrate: str = "2M"
    duration: int | None = Field(
        default=None, ge=1, description="Duration in seconds"
    )
    monitor_index: int = Field(
        default=0, ge=0, description="Monitor index (0 = primary)"
    )
    include_cursor: bool = Field(
        default=False, description="Include cursor in capture"
    )

    model_config = {
        "extra": "ignore",
        "json_schema_extra": {
            "examples": [
                {
                    "area": "full",
                    "audio": "mic",
                    "fps": 30,
                    "duration": 60,
                },
                {
                    "area": "window",
                    "window_title": "Browser",
                    "audio": "system",
                    "fps": 60,
                },
                {
                    "area": "rect",
                    "rect": [0, 0, 1920, 1080],
                    "audio": "both",
                    "fps": 30,
                    "monitor_index": 1,
                },
            ]
        },
    }

    def to_internal_dict(self) -> dict:
        """Преобразование в формат для внутреннего использования.

        Returns:
            Словарь с ключами, ожидаемыми внутренними компонентами.
        """
        return {
            "area_type": self.area,
            "rect_coords": self.rect,
            "window_title": self.window_title,
            "audio_type": self.audio,
            "output_path": self.output_path,
            "fps": self.fps,
            "codec": self.codec,
            "bitrate": self.bitrate,
            "duration": self.duration,
            "monitor_index": self.monitor_index,
            "include_cursor": self.include_cursor,
        }


class ScheduleParams(BaseModel):
    """Unified schedule parameters contract.

    Используется для создания и обновления запланированных задач.
    """

    name: str = Field(..., min_length=1, max_length=100)
    trigger: Literal["once", "daily", "weekly", "interval", "cron"]
    time: str | None = Field(
        default=None,
        pattern=r"^\d{2}:\d{2}$",
        description="Time in HH:MM format for daily/weekly",
    )
    days_of_week: list[int] | None = Field(
        default=None,
        min_length=1,
        max_length=7,
        description="Days of week (0=Monday, 6=Sunday) for weekly",
    )
    interval_hours: int | None = Field(
        default=None,
        ge=0,
        le=168,  # Max 1 week
        description="Interval in hours for interval trigger",
    )
    interval_minutes: int | None = Field(
        default=None,
        ge=1,
        le=1440,  # Max 1 day
        description="Interval in minutes for interval trigger",
    )
    datetime: str | None = Field(
        default=None,
        description="Datetime for once trigger (ISO format: YYYY-MM-DD HH:MM)",
    )
    cron_expression: str | None = Field(
        default=None,
        description="Cron expression for cron trigger",
    )
    params: RecordingParams | None = None
    enabled: bool = True

    model_config = {
        "extra": "ignore",
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Daily standup recording",
                    "trigger": "daily",
                    "time": "09:30",
                    "params": {
                        "area": "full",
                        "audio": "mic",
                        "duration": 1800,
                    },
                },
                {
                    "name": "Weekly meeting",
                    "trigger": "weekly",
                    "time": "14:00",
                    "days_of_week": [0, 2, 4],
                    "params": {
                        "area": "window",
                        "window_title": "Teams",
                    },
                },
                {
                    "name": "Hourly screenshot",
                    "trigger": "interval",
                    "interval_hours": 1,
                    "params": {
                        "area": "full",
                        "duration": 10,
                    },
                },
            ]
        },
    }

    def to_internal_dict(self) -> dict:
        """Преобразование в формат для TaskScheduler.create_task_from_dict().

        Returns:
            Словарь с ключами, ожидаемыми планировщиком.
        """
        result: dict = {
            "name": self.name,
            "trigger": self.trigger,
            "enabled": self.enabled,
        }

        if self.time:
            result["time"] = self.time

        if self.days_of_week is not None:
            result["days_of_week"] = self.days_of_week

        if self.interval_hours is not None:
            result["hours"] = self.interval_hours

        if self.interval_minutes is not None:
            result["minutes"] = self.interval_minutes

        if self.datetime:
            result["datetime"] = self.datetime

        if self.cron_expression:
            result["cron_expression"] = self.cron_expression

        if self.params:
            result["params"] = self.params.to_internal_dict()

        return result


class RecordingStatusResponse(BaseModel):
    """Response model for recording status."""

    is_recording: bool
    is_paused: bool
    elapsed_time: float
    current_file: str | None = None
    frame_count: int | None = None


class ScheduleTaskResponse(BaseModel):
    """Response model for schedule task."""

    id: str
    name: str
    schedule_type: str
    enabled: bool
    next_run: str | None = None
    last_run: str | None = None
    run_count: int = 0


class ApiResponse(BaseModel):
    """Generic API response wrapper."""

    success: bool
    data: dict | list | None = None
    error: str | None = None

    model_config = {
        "extra": "ignore",
    }
