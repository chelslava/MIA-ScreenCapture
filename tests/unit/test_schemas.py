"""
Тесты для схем валидации API
============================

Проверяет Pydantic модели валидации в api/schemas.py.
"""

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from api.schemas import (
    CreateScheduleRequest,
    StartRecordingRequest,
    ToggleScheduleRequest,
    UpdateConfigRequest,
    UpdateScheduleRequest,
)


class TestStartRecordingRequest:
    """Тесты для схемы StartRecordingRequest."""

    def test_default_values(self):
        """Проверка значений по умолчанию."""
        request = StartRecordingRequest()

        assert request.area == "full"
        assert request.audio == "none"
        assert request.fps == 30
        assert request.codec == "libx264"
        assert request.bitrate == "2M"

    def test_valid_full_area(self):
        """Проверка валидного запроса с полным экраном."""
        request = StartRecordingRequest(area="full", fps=60, codec="h264")

        assert request.area == "full"
        assert request.fps == 60

    def test_valid_window_area(self):
        """Проверка валидного запроса с захватом окна."""
        request = StartRecordingRequest(area="window", window_title="Browser")

        assert request.area == "window"
        assert request.window_title == "Browser"

    def test_valid_rect_area(self):
        """Проверка валидного запроса с прямоугольником."""
        request = StartRecordingRequest(area="rect", rect=[100, 100, 800, 600])

        assert request.area == "rect"
        assert request.rect == [100, 100, 800, 600]

    def test_invalid_area_type(self):
        """Проверка невалидного типа области."""
        with pytest.raises(ValidationError) as exc_info:
            StartRecordingRequest(area="invalid")

        assert "area" in str(exc_info.value)

    def test_window_area_without_title(self):
        """Проверка захвата окна без заголовка."""
        with pytest.raises(ValidationError) as exc_info:
            StartRecordingRequest(area="window")

        assert "window_title" in str(exc_info.value)

    def test_rect_area_without_coords(self):
        """Проверка прямоугольника без координат."""
        with pytest.raises(ValidationError) as exc_info:
            StartRecordingRequest(area="rect")

        assert "rect" in str(exc_info.value)

    def test_invalid_rect_coords(self):
        """Проверка невалидных координат прямоугольника."""
        # x2 <= x1
        with pytest.raises(ValidationError):
            StartRecordingRequest(area="rect", rect=[800, 100, 100, 600])

        # Отрицательные координаты
        with pytest.raises(ValidationError):
            StartRecordingRequest(area="rect", rect=[-10, 100, 800, 600])

        # Неправильное количество координат
        with pytest.raises(ValidationError):
            StartRecordingRequest(area="rect", rect=[100, 100, 800])

    def test_invalid_fps(self):
        """Проверка невалидного FPS."""
        # Слишком маленький
        with pytest.raises(ValidationError):
            StartRecordingRequest(fps=0)

        # Слишком большой
        with pytest.raises(ValidationError):
            StartRecordingRequest(fps=200)

    def test_invalid_bitrate_format(self):
        """Проверка невалидного формата битрейта."""
        with pytest.raises(ValidationError):
            StartRecordingRequest(bitrate="invalid")

        with pytest.raises(ValidationError):
            StartRecordingRequest(bitrate="2X")

    def test_valid_bitrate_formats(self):
        """Проверка валидных форматов битрейта."""
        request1 = StartRecordingRequest(bitrate="2M")
        assert request1.bitrate == "2M"

        request2 = StartRecordingRequest(bitrate="5000K")
        assert request2.bitrate == "5000K"

        request3 = StartRecordingRequest(bitrate="2000000")
        assert request3.bitrate == "2000000"

    def test_invalid_audio_type(self):
        """Проверка невалидного типа аудио."""
        with pytest.raises(ValidationError):
            StartRecordingRequest(audio="invalid")

    def test_negative_duration(self):
        """Проверка отрицательной длительности."""
        with pytest.raises(ValidationError):
            StartRecordingRequest(duration=-10)


class TestCreateScheduleRequest:
    """Тесты для схемы CreateScheduleRequest."""

    def test_valid_once_schedule(self):
        """Проверка валидной разовой задачи."""
        future_time = (datetime.now() + timedelta(hours=1)).isoformat()

        request = CreateScheduleRequest(
            name="Test Task", trigger="once", datetime=future_time
        )

        assert request.name == "Test Task"
        assert request.trigger == "once"
        assert request.datetime == future_time

    def test_valid_daily_schedule(self):
        """Проверка валидной ежедневной задачи."""
        request = CreateScheduleRequest(
            name="Daily Task", trigger="daily", time="09:00"
        )

        assert request.trigger == "daily"
        assert request.time == "09:00"

    def test_valid_weekly_schedule(self):
        """Проверка валидной еженедельной задачи."""
        request = CreateScheduleRequest(
            name="Weekly Task",
            trigger="weekly",
            time="10:00",
            day_of_week="0,2,4",
        )

        assert request.trigger == "weekly"
        assert request.day_of_week == "0,2,4"

    def test_valid_interval_schedule(self):
        """Проверка валидной интервальной задачи."""
        request = CreateScheduleRequest(
            name="Interval Task", trigger="interval", hours=2, minutes=30
        )

        assert request.trigger == "interval"
        assert request.hours == 2
        assert request.minutes == 30

    def test_once_without_datetime(self):
        """Проверка разовой задачи без datetime."""
        with pytest.raises(ValidationError) as exc_info:
            CreateScheduleRequest(name="Test", trigger="once")

        assert "datetime" in str(exc_info.value)

    def test_daily_without_time(self):
        """Проверка ежедневной задачи без времени."""
        with pytest.raises(ValidationError) as exc_info:
            CreateScheduleRequest(name="Test", trigger="daily")

        assert "time" in str(exc_info.value)

    def test_weekly_without_day_of_week(self):
        """Проверка еженедельной задачи без дней недели."""
        with pytest.raises(ValidationError) as exc_info:
            CreateScheduleRequest(name="Test", trigger="weekly", time="10:00")

        assert "day_of_week" in str(exc_info.value)

    def test_interval_without_hours_and_minutes(self):
        """Проверка интервальной задачи без интервала."""
        with pytest.raises(ValidationError) as exc_info:
            CreateScheduleRequest(name="Test", trigger="interval")

        assert "hours" in str(exc_info.value) or "minutes" in str(
            exc_info.value
        )

    def test_interval_zero(self):
        """Проверка нулевого интервала."""
        with pytest.raises(ValidationError):
            CreateScheduleRequest(
                name="Test", trigger="interval", hours=0, minutes=0
            )

    def test_invalid_time_format(self):
        """Проверка невалидного формата времени."""
        with pytest.raises(ValidationError):
            CreateScheduleRequest(
                name="Test",
                trigger="daily",
                time="25:00",  # Несуществующий час
            )

        with pytest.raises(ValidationError):
            CreateScheduleRequest(
                name="Test",
                trigger="daily",
                time="99:00",  # Несуществующий час
            )

    def test_invalid_day_of_week(self):
        """Проверка невалидных дней недели."""
        with pytest.raises(ValidationError):
            CreateScheduleRequest(
                name="Test",
                trigger="weekly",
                time="10:00",
                day_of_week="7",  # День 7 не существует
            )

    def test_past_datetime(self):
        """Проверка прошедшего datetime."""
        past_time = (datetime.now() - timedelta(hours=1)).isoformat()

        with pytest.raises(ValidationError):
            CreateScheduleRequest(
                name="Test", trigger="once", datetime=past_time
            )

    def test_empty_name(self):
        """Проверка пустого названия."""
        with pytest.raises(ValidationError):
            CreateScheduleRequest(name="", trigger="daily", time="10:00")

    def test_invalid_trigger(self):
        """Проверка невалидного типа расписания."""
        with pytest.raises(ValidationError):
            CreateScheduleRequest(name="Test", trigger="invalid")

    def test_with_recording_params(self):
        """Проверка с параметрами записи."""
        future_time = (datetime.now() + timedelta(hours=1)).isoformat()

        request = CreateScheduleRequest(
            name="Test",
            trigger="once",
            datetime=future_time,
            params=StartRecordingRequest(
                area="window", window_title="Browser", fps=60
            ),
        )

        assert request.params is not None
        assert request.params.area == "window"
        assert request.params.fps == 60

    def test_valid_cron_schedule(self):
        """Проверка валидной cron-задачи."""
        request = CreateScheduleRequest(
            name="Cron Task", trigger="cron", cron_expression="0 9 * * 1-5"
        )

        assert request.trigger == "cron"
        assert request.cron_expression == "0 9 * * 1-5"

    def test_cron_without_expression(self):
        """Проверка cron-задачи без выражения."""
        with pytest.raises(ValidationError) as exc_info:
            CreateScheduleRequest(name="Test", trigger="cron")

        assert "cron_expression" in str(exc_info.value)

    def test_invalid_cron_expression_format(self):
        """Проверка невалидного формата cron-выражения."""
        # Слишком мало полей
        with pytest.raises(ValidationError):
            CreateScheduleRequest(
                name="Test", trigger="cron", cron_expression="0 9 * *"
            )

        # Слишком много полей
        with pytest.raises(ValidationError):
            CreateScheduleRequest(
                name="Test", trigger="cron", cron_expression="0 9 * * * *"
            )

    def test_cron_expression_with_special_chars(self):
        """Проверка cron-выражения со специальными символами."""
        # С диапазоном
        request1 = CreateScheduleRequest(
            name="Test", trigger="cron", cron_expression="0 9 * * 1-5"
        )
        assert request1.cron_expression == "0 9 * * 1-5"

        # С шагом
        request2 = CreateScheduleRequest(
            name="Test", trigger="cron", cron_expression="*/15 * * * *"
        )
        assert request2.cron_expression == "*/15 * * * *"

        # С звёздочками
        request3 = CreateScheduleRequest(
            name="Test", trigger="cron", cron_expression="0 0 * * *"
        )
        assert request3.cron_expression == "0 0 * * *"


class TestUpdateScheduleRequest:
    """Тесты для схемы UpdateScheduleRequest."""

    def test_valid_update(self):
        """Проверка валидного обновления."""
        request = UpdateScheduleRequest(
            id="task-001", name="Updated Task", enabled=False
        )

        assert request.id == "task-001"
        assert request.name == "Updated Task"
        assert request.enabled is False

    def test_only_id_required(self):
        """Проверка что только ID обязателен."""
        request = UpdateScheduleRequest(id="task-001")

        assert request.id == "task-001"
        assert request.name is None
        assert request.enabled is None

    def test_invalid_time_format(self):
        """Проверка невалидного формата времени."""
        with pytest.raises(ValidationError):
            UpdateScheduleRequest(id="task-001", time="invalid")


class TestToggleScheduleRequest:
    """Тесты для схемы ToggleScheduleRequest."""

    def test_enable(self):
        """Проверка включения."""
        request = ToggleScheduleRequest(enabled=True)

        assert request.enabled is True

    def test_disable(self):
        """Проверка выключения."""
        request = ToggleScheduleRequest(enabled=False)

        assert request.enabled is False


class TestUpdateConfigRequest:
    """Тесты для схемы UpdateConfigRequest."""

    def test_valid_fps_update(self):
        """Проверка обновления FPS."""
        request = UpdateConfigRequest(fps=60)

        assert request.fps == 60

    def test_valid_bitrate_update(self):
        """Проверка обновления битрейта."""
        request = UpdateConfigRequest(bitrate="5M")

        assert request.bitrate == "5M"

    def test_invalid_fps(self):
        """Проверка невалидного FPS."""
        with pytest.raises(ValidationError):
            UpdateConfigRequest(fps=200)

    def test_invalid_bitrate(self):
        """Проверка невалидного битрейта."""
        with pytest.raises(ValidationError):
            UpdateConfigRequest(bitrate="invalid")

    def test_multiple_fields(self):
        """Проверка обновления нескольких полей."""
        request = UpdateConfigRequest(
            fps=60,
            codec="h264",
            bitrate="5M",
            minimize_to_tray=False,
            language="ru",
        )

        assert request.fps == 60
        assert request.codec == "h264"
        assert request.bitrate == "5M"
        assert request.minimize_to_tray is False
        assert request.language == "ru"

    def test_empty_request(self):
        """Проверка пустого запроса."""
        request = UpdateConfigRequest()

        assert request.fps is None
        assert request.codec is None
        assert request.bitrate is None


class TestModelDump:
    """Тесты для метода model_dump."""

    def test_exclude_none(self):
        """Проверка исключения None значений."""
        request = StartRecordingRequest(
            area="window", window_title="Test", fps=60
        )

        data = request.model_dump(exclude_none=True)

        assert "area" in data
        assert "window_title" in data
        assert "fps" in data
        assert "rect" not in data  # None значение
        assert "duration" not in data  # None значение

    def test_include_defaults(self):
        """Проверка включения значений по умолчанию."""
        request = StartRecordingRequest()

        data = request.model_dump()

        assert data["area"] == "full"
        assert data["fps"] == 30
        assert data["codec"] == "libx264"
