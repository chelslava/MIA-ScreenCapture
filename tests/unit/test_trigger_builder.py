"""Тесты сборки APScheduler-триггеров для scheduler-задач."""

from datetime import datetime

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from scheduler.task_scheduler import (
    RecordingParams,
    ScheduleTask,
    ScheduleType,
)
from scheduler.trigger_builder import create_trigger


def _parse_time_of_day(value: str) -> tuple[int, int]:
    """Локальный парсер HH:MM для тестов trigger builder."""
    hour_text, minute_text = value.split(":")
    return int(hour_text), int(minute_text)


class TestTriggerBuilder:
    """Проверки сборки trigger-ов для ключевых типов расписания."""

    def test_create_once_trigger(self) -> None:
        task = ScheduleTask(
            id="once-1",
            name="Once",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(),
            start_time=datetime(2026, 4, 1, 10, 30, 0),
        )

        trigger = create_trigger(task, _parse_time_of_day)

        assert isinstance(trigger, DateTrigger)

    def test_create_weekly_trigger(self) -> None:
        task = ScheduleTask(
            id="weekly-1",
            name="Weekly",
            schedule_type=ScheduleType.WEEKLY,
            params=RecordingParams(),
            time_of_day="09:15",
            days_of_week=[1, 3, 5],
        )

        trigger = create_trigger(task, _parse_time_of_day)

        assert isinstance(trigger, CronTrigger)

    def test_create_trigger_returns_none_for_missing_once_datetime(
        self,
    ) -> None:
        task = ScheduleTask(
            id="once-2",
            name="Once invalid",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(),
        )

        trigger = create_trigger(task, _parse_time_of_day)

        assert trigger is None
