"""Сборка APScheduler-триггеров для scheduler задач."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger


class TriggerTaskProtocol(Protocol):
    """Минимальный контракт задачи для сборки триггера."""

    schedule_type: Any
    start_time: datetime | None
    time_of_day: str | None
    days_of_week: list[int] | None
    interval_hours: int | None
    interval_minutes: int | None
    cron_expression: str | None


def _schedule_type_value(task: TriggerTaskProtocol) -> str:
    schedule_type = task.schedule_type
    value = getattr(schedule_type, "value", schedule_type)
    return str(value).lower()


def create_trigger(
    task: TriggerTaskProtocol,
    parse_time_of_day: Callable[[str], tuple[int, int]],
) -> Any | None:
    """Создаёт APScheduler-триггер для указанной scheduler-задачи."""
    schedule_type = _schedule_type_value(task)

    if schedule_type == "once":
        if task.start_time:
            return DateTrigger(run_date=task.start_time)

    elif schedule_type == "daily":
        if task.time_of_day:
            hour, minute = parse_time_of_day(task.time_of_day)
            return CronTrigger(hour=hour, minute=minute)

    elif schedule_type == "weekly":
        if task.time_of_day and task.days_of_week:
            hour, minute = parse_time_of_day(task.time_of_day)
            return CronTrigger(
                hour=hour,
                minute=minute,
                day_of_week=",".join(str(d) for d in task.days_of_week),
            )

    elif schedule_type == "interval":
        return IntervalTrigger(
            weeks=0,
            days=0,
            hours=task.interval_hours or 0,
            minutes=task.interval_minutes or 0,
        )

    elif schedule_type == "cron" and task.cron_expression:
        return CronTrigger.from_crontab(task.cron_expression)

    return None
