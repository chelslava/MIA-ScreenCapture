"""Тесты сборки APScheduler-триггеров для scheduler-задач."""

from datetime import datetime

import pytest
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from scheduler.task_scheduler import (
    RecordingParams,
    ScheduleTask,
    ScheduleType,
)
from scheduler.trigger_builder import (
    create_trigger,
    normalize_crontab_expression,
)


def _parse_time_of_day(value: str) -> tuple[int, int]:
    """Локальный парсер HH:MM для тестов trigger builder."""
    hour_text, minute_text = value.split(":")
    return int(hour_text), int(minute_text)


class TestTriggerBuilder:
    """Проверки сборки trigger-ов для ключевых типов расписания."""

    # ------------------------------------------------------------------
    # once
    # ------------------------------------------------------------------

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

    def test_once_trigger_run_date_matches_start_time(self) -> None:
        """DateTrigger должен хранить именно переданный start_time (без tzinfo)."""
        run_date = datetime(2027, 1, 15, 8, 0, 0)
        task = ScheduleTask(
            id="once-3",
            name="Once date check",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(),
            start_time=run_date,
        )

        trigger = create_trigger(task, _parse_time_of_day)

        assert isinstance(trigger, DateTrigger)
        # APScheduler может добавить локальную timezone к наивному datetime;
        # сравниваем только компоненты даты и времени.
        assert trigger.run_date.replace(tzinfo=None) == run_date

    # ------------------------------------------------------------------
    # daily
    # ------------------------------------------------------------------

    def test_create_daily_trigger_returns_cron_trigger(self) -> None:
        """daily расписание должно возвращать CronTrigger."""
        task = ScheduleTask(
            id="daily-1",
            name="Daily",
            schedule_type=ScheduleType.DAILY,
            params=RecordingParams(),
            time_of_day="08:30",
        )

        trigger = create_trigger(task, _parse_time_of_day)

        assert isinstance(trigger, CronTrigger)

    def test_daily_trigger_encodes_correct_hour_and_minute(self) -> None:
        """CronTrigger для daily должен содержать правильный час и минуту."""
        task = ScheduleTask(
            id="daily-2",
            name="Daily time check",
            schedule_type=ScheduleType.DAILY,
            params=RecordingParams(),
            time_of_day="23:45",
        )

        trigger = create_trigger(task, _parse_time_of_day)

        assert isinstance(trigger, CronTrigger)
        fields = {f.name: str(f) for f in trigger.fields}
        assert fields["hour"] == "23"
        assert fields["minute"] == "45"

    def test_create_daily_trigger_returns_none_when_time_of_day_missing(
        self,
    ) -> None:
        """Без time_of_day daily расписание возвращает None."""
        task = ScheduleTask(
            id="daily-3",
            name="Daily no time",
            schedule_type=ScheduleType.DAILY,
            params=RecordingParams(),
        )

        trigger = create_trigger(task, _parse_time_of_day)

        assert trigger is None

    # ------------------------------------------------------------------
    # weekly
    # ------------------------------------------------------------------

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

    def test_weekly_trigger_returns_none_when_days_of_week_missing(
        self,
    ) -> None:
        """Без days_of_week weekly расписание возвращает None."""
        task = ScheduleTask(
            id="weekly-2",
            name="Weekly no days",
            schedule_type=ScheduleType.WEEKLY,
            params=RecordingParams(),
            time_of_day="10:00",
        )

        trigger = create_trigger(task, _parse_time_of_day)

        assert trigger is None

    def test_weekly_trigger_returns_none_when_time_of_day_missing(
        self,
    ) -> None:
        """Без time_of_day weekly расписание возвращает None."""
        task = ScheduleTask(
            id="weekly-3",
            name="Weekly no time",
            schedule_type=ScheduleType.WEEKLY,
            params=RecordingParams(),
            days_of_week=[0, 2, 4],
        )

        trigger = create_trigger(task, _parse_time_of_day)

        assert trigger is None

    # ------------------------------------------------------------------
    # interval
    # ------------------------------------------------------------------

    def test_create_interval_trigger_with_hours(self) -> None:
        """interval расписание с interval_hours возвращает IntervalTrigger."""
        task = ScheduleTask(
            id="interval-1",
            name="Interval hours",
            schedule_type=ScheduleType.INTERVAL,
            params=RecordingParams(),
            interval_hours=2,
        )

        trigger = create_trigger(task, _parse_time_of_day)

        assert isinstance(trigger, IntervalTrigger)

    def test_create_interval_trigger_with_minutes(self) -> None:
        """interval расписание с interval_minutes возвращает IntervalTrigger."""
        task = ScheduleTask(
            id="interval-2",
            name="Interval minutes",
            schedule_type=ScheduleType.INTERVAL,
            params=RecordingParams(),
            interval_minutes=30,
        )

        trigger = create_trigger(task, _parse_time_of_day)

        assert isinstance(trigger, IntervalTrigger)

    def test_create_interval_trigger_with_hours_and_minutes(self) -> None:
        """interval расписание с обоими полями возвращает IntervalTrigger."""
        task = ScheduleTask(
            id="interval-3",
            name="Interval both",
            schedule_type=ScheduleType.INTERVAL,
            params=RecordingParams(),
            interval_hours=1,
            interval_minutes=30,
        )

        trigger = create_trigger(task, _parse_time_of_day)

        assert isinstance(trigger, IntervalTrigger)

    def test_interval_trigger_with_none_fields_uses_zero(self) -> None:
        """interval без явных полей создаёт IntervalTrigger с нулевым интервалом."""
        task = ScheduleTask(
            id="interval-4",
            name="Interval zero",
            schedule_type=ScheduleType.INTERVAL,
            params=RecordingParams(),
        )

        # create_trigger всегда возвращает IntervalTrigger для interval,
        # даже если hours=0 и minutes=0 (валидация — на уровне TaskScheduler).
        trigger = create_trigger(task, _parse_time_of_day)

        assert isinstance(trigger, IntervalTrigger)

    # ------------------------------------------------------------------
    # cron
    # ------------------------------------------------------------------

    def test_create_cron_trigger_from_valid_expression(self) -> None:
        """Валидное cron-выражение возвращает CronTrigger."""
        task = ScheduleTask(
            id="cron-1",
            name="Cron",
            schedule_type=ScheduleType.CRON,
            params=RecordingParams(),
            cron_expression="30 8 * * 1",
        )

        trigger = create_trigger(task, _parse_time_of_day)

        assert isinstance(trigger, CronTrigger)

    def test_create_cron_trigger_returns_none_when_expression_missing(
        self,
    ) -> None:
        """cron расписание без cron_expression возвращает None."""
        task = ScheduleTask(
            id="cron-2",
            name="Cron no expr",
            schedule_type=ScheduleType.CRON,
            params=RecordingParams(),
        )

        trigger = create_trigger(task, _parse_time_of_day)

        assert trigger is None

    def test_create_cron_trigger_raises_for_invalid_expression(self) -> None:
        """Некорректное cron-выражение вызывает ValueError от APScheduler."""
        task = ScheduleTask(
            id="cron-3",
            name="Cron invalid",
            schedule_type=ScheduleType.CRON,
            params=RecordingParams(),
            cron_expression="not a valid cron",
        )

        with pytest.raises(ValueError):
            create_trigger(task, _parse_time_of_day)

    # ------------------------------------------------------------------
    # normalize_crontab_expression
    # ------------------------------------------------------------------

    def test_normalize_crontab_numeric_sunday_zero_maps_to_sun(self) -> None:
        """numeric '0' в поле day-of-week должен стать 'sun'."""
        result = normalize_crontab_expression("0 8 * * 0")

        assert result == "0 8 * * sun"

    def test_normalize_crontab_numeric_monday_one_maps_to_mon(self) -> None:
        """numeric '1' в поле day-of-week должен стать 'mon'."""
        result = normalize_crontab_expression("0 9 * * 1")

        assert result == "0 9 * * mon"

    def test_normalize_crontab_numeric_sunday_seven_maps_to_sun(self) -> None:
        """numeric '7' в поле day-of-week (альтернативное воскресенье) должен стать 'sun'."""
        result = normalize_crontab_expression("0 8 * * 7")

        assert result == "0 8 * * sun"

    def test_normalize_crontab_wildcard_unchanged(self) -> None:
        """Wildcard '*' в day-of-week должен остаться без изменений."""
        result = normalize_crontab_expression("0 8 * * *")

        assert result == "0 8 * * *"

    def test_normalize_crontab_comma_separated_days(self) -> None:
        """Несколько числовых дней через запятую нормализуются все."""
        result = normalize_crontab_expression("0 10 * * 1,3,5")

        assert result == "0 10 * * mon,wed,fri"

    def test_normalize_crontab_expression_with_wrong_field_count_unchanged(
        self,
    ) -> None:
        """Выражение с числом полей != 5 возвращается без изменений."""
        expr = "0 8 * *"

        result = normalize_crontab_expression(expr)

        assert result == expr

    def test_normalize_crontab_named_day_passes_through(self) -> None:
        """Уже именованный день ('mon') должен остаться без изменений."""
        result = normalize_crontab_expression("0 12 * * mon")

        assert result == "0 12 * * mon"

    def test_normalize_crontab_step_expression_in_day_of_week(self) -> None:
        """Step-выражение '0/2' нормализует базу: 0 → sun, шаг остаётся."""
        result = normalize_crontab_expression("0 8 * * 0/2")

        assert result == "0 8 * * sun/2"

    def test_normalize_crontab_range_expression_in_day_of_week(self) -> None:
        """Range-выражение '1-5' нормализует оба конца: 1→mon, 5→fri."""
        result = normalize_crontab_expression("0 8 * * 1-5")

        assert result == "0 8 * * mon-fri"
