"""Unit tests for TaskDialog."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PyQt6.QtCore import QDate, QTime
from PyQt6.QtWidgets import QDialogButtonBox
from scheduler.task_scheduler import RecordingParams, ScheduleTask, ScheduleType

from gui.scheduler.task_dialog import TaskDialog


@pytest.fixture
def dialog_without_task(qtbot):
    """Create TaskDialog without existing task."""
    dialog = TaskDialog()
    qtbot.add_widget(dialog)
    return dialog


@pytest.fixture
def dialog_with_task(qtbot):
    """Create TaskDialog with existing task."""
    params = RecordingParams(
        area_type="full",
        window_title="",
        audio_type="mic",
        fps=30,
        duration=3600,
    )
    task = ScheduleTask(
        id="test-task-123",
        name="Test Task",
        schedule_type=ScheduleType.DAILY,
        params=params,
        enabled=True,
        start_time=None,
        time_of_day="10:00",
        days_of_week=[1, 3, 5],
        interval_hours=None,
        interval_minutes=None,
        cron_expression=None,
    )
    dialog = TaskDialog(task=task)
    qtbot.add_widget(dialog)
    return dialog


class TestTaskDialogInitialization:
    """Tests for TaskDialog initialization."""

    def test_default_initialization(self, dialog_without_task):
        """Test dialog initialization without task."""
        assert dialog_without_task.windowTitle() == "Новая задача"
        assert dialog_without_task.task is None
        assert len(dialog_without_task._preset_names) > 0

    def test_initialization_with_task(self, dialog_with_task):
        """Test dialog initialization with existing task."""
        assert dialog_with_task.windowTitle() == "Редактирование задачи"
        assert dialog_with_task.task is not None
        assert dialog_with_task.task.name == "Test Task"
        assert dialog_with_task.task.schedule_type == ScheduleType.DAILY


class TestTaskDialogUI:
    """Tests for TaskDialog UI components."""

    def test_preset_combo_initialization(self, dialog_without_task):
        """Test preset combo box initialization."""
        combo = dialog_without_task.preset_combo
        # At minimum, should have "Без preset" option
        assert combo.count() >= 1

    def test_schedule_type_combo_items(self, dialog_without_task):
        """Test schedule type combo box items."""
        combo = dialog_without_task.type_combo
        expected_items = [
            "Разовая",
            "Ежедневная",
            "Еженедельная",
            "Интервал",
            "Cron",
        ]
        assert combo.count() == len(expected_items)
        for i, expected in enumerate(expected_items):
            assert combo.itemText(i) == expected

    def test_area_combo_items(self, dialog_without_task):
        """Test area combo box items."""
        combo = dialog_without_task.area_combo
        expected_items = ["Полный экран", "Окно", "Прямоугольник"]
        assert combo.count() == len(expected_items)
        for i, expected in enumerate(expected_items):
            assert combo.itemText(i) == expected

    def test_audio_combo_items(self, dialog_without_task):
        """Test audio combo box items."""
        combo = dialog_without_task.audio_combo
        expected_items = ["Нет", "Микрофон", "Системное аудио", "Оба"]
        assert combo.count() == len(expected_items)
        for i, expected in enumerate(expected_items):
            assert combo.itemText(i) == expected


class TestTaskDialogTypeChanges:
    """Tests for schedule type change handlers."""

    def test_on_type_changed_once(self, dialog_without_task, qtbot):
        """Test UI state for 'once' schedule type."""
        dialog_without_task.type_combo.setCurrentIndex(0)
        # Date edit should be visible for 'once' type
        assert dialog_without_task.date_edit.isVisible()

    def test_on_type_changed_daily(self, dialog_without_task, qtbot):
        """Test UI state for 'daily' schedule type."""
        dialog_without_task.type_combo.setCurrentIndex(1)
        # Time edit should be visible for 'daily' type
        assert dialog_without_task.time_edit.isVisible()

    def test_on_type_changed_weekly(self, dialog_without_task, qtbot):
        """Test UI state for 'weekly' schedule type."""
        dialog_without_task.type_combo.setCurrentIndex(2)
        # Days widget should be visible for 'weekly' type
        assert dialog_without_task.days_widget.isVisible()

    def test_on_type_changed_interval(self, dialog_without_task, qtbot):
        """Test UI state for 'interval' schedule type."""
        dialog_without_task.type_combo.setCurrentIndex(3)
        # Interval widget should be visible for 'interval' type
        assert dialog_without_task.interval_widget.isVisible()

    def test_on_type_changed_cron(self, dialog_without_task, qtbot):
        """Test UI state for 'cron' schedule type."""
        dialog_without_task.type_combo.setCurrentIndex(4)
        # Cron widget should be visible for 'cron' type
        assert dialog_without_task.cron_widget.isVisible()


class TestTaskDialogGetTaskData:
    """Tests for get_task_data method."""

    def test_get_task_data_once(self, dialog_without_task):
        """Test get_task_data for 'once' schedule type."""
        dialog_without_task.type_combo.setCurrentIndex(0)
        dialog_without_task.name_edit.setText("Once Task")
        dialog_without_task.date_edit.setDate(QDate(2025, 6, 15))
        dialog_without_task.time_edit.setTime(QTime(14, 30))
        dialog_without_task.area_combo.setCurrentIndex(1)
        dialog_without_task.audio_combo.setCurrentIndex(2)
        dialog_without_task.fps_spin.setValue(60)

        data = dialog_without_task.get_task_data()

        assert data["name"] == "Once Task"
        assert data["schedule_type"] == ScheduleType.ONCE
        assert data["area_type"] == "window"
        assert data["audio_type"] == "system"
        assert data["fps"] == 60
        assert data["start_time"] is not None

    def test_get_task_data_daily(self, dialog_without_task):
        """Test get_task_data for 'daily' schedule type."""
        dialog_without_task.type_combo.setCurrentIndex(1)
        dialog_without_task.name_edit.setText("Daily Task")
        dialog_without_task.time_edit.setTime(QTime(9, 0))
        dialog_without_task.area_combo.setCurrentIndex(0)

        data = dialog_without_task.get_task_data()

        assert data["name"] == "Daily Task"
        assert data["schedule_type"] == ScheduleType.DAILY
        assert data["area_type"] == "full"
        assert "time_of_day" in data
        assert data["time_of_day"] == "09:00"

    def test_get_task_data_weekly(self, dialog_without_task):
        """Test get_task_data for 'weekly' schedule type."""
        dialog_without_task.type_combo.setCurrentIndex(2)
        dialog_without_task.name_edit.setText("Weekly Task")
        dialog_without_task.time_edit.setTime(QTime(10, 0))
        # Select Monday, Wednesday, Friday
        dialog_without_task.day_checks[0].setChecked(True)
        dialog_without_task.day_checks[2].setChecked(True)
        dialog_without_task.day_checks[4].setChecked(True)

        data = dialog_without_task.get_task_data()

        assert data["schedule_type"] == ScheduleType.WEEKLY
        assert data["days_of_week"] == [0, 2, 4]

    def test_get_task_data_interval(self, dialog_without_task):
        """Test get_task_data for 'interval' schedule type."""
        dialog_without_task.type_combo.setCurrentIndex(3)
        dialog_without_task.name_edit.setText("Interval Task")
        dialog_without_task.interval_hours.setValue(2)
        dialog_without_task.interval_minutes.setValue(30)

        data = dialog_without_task.get_task_data()

        assert data["schedule_type"] == ScheduleType.INTERVAL
        assert data["interval_hours"] == 2
        assert data["interval_minutes"] == 30

    def test_get_task_data_cron(self, dialog_without_task):
        """Test get_task_data for 'cron' schedule type."""
        dialog_without_task.type_combo.setCurrentIndex(4)
        dialog_without_task.name_edit.setText("Cron Task")
        dialog_without_task.cron_edit.setText("0 9 * * 1-5")

        data = dialog_without_task.get_task_data()

        assert data["schedule_type"] == ScheduleType.CRON
        assert data["cron_expression"] == "0 9 * * 1-5"

    def test_get_task_data_duration_minutes(self, dialog_without_task):
        """Test duration conversion when unit is minutes."""
        dialog_without_task.type_combo.setCurrentIndex(0)
        dialog_without_task.duration_spin.setValue(90)
        dialog_without_task.duration_unit_combo.setCurrentIndex(1)

        data = dialog_without_task.get_task_data()

        assert data["duration"] == 90 * 60  # 90 minutes = 5400 seconds

    def test_get_task_data_duration_seconds(self, dialog_without_task):
        """Test duration conversion when unit is seconds."""
        dialog_without_task.type_combo.setCurrentIndex(0)
        dialog_without_task.duration_spin.setValue(1800)
        dialog_without_task.duration_unit_combo.setCurrentIndex(0)

        data = dialog_without_task.get_task_data()

        assert data["duration"] == 1800  # 1800 seconds = 30 minutes


class TestTaskDialogLoadTask:
    """Tests for _load_task method."""

    def test_load_task(self, dialog_without_task, qtbot):
        """Test loading data into dialog from existing task."""
        params = RecordingParams(
            area_type="window",
            window_title="Test Window",
            audio_type="both",
            fps=25,
            duration=1800,
        )
        task = ScheduleTask(
            id="load-test-123",
            name="Loaded Task",
            schedule_type=ScheduleType.ONCE,
            params=params,
            enabled=True,
            start_time=None,
            time_of_day=None,
            days_of_week=None,
            interval_hours=None,
            interval_minutes=None,
            cron_expression=None,
        )

        dialog_without_task._load_task(task)

        assert dialog_without_task.name_edit.text() == "Loaded Task"
        assert dialog_without_task.area_combo.currentIndex() == 1  # Window
        assert dialog_without_task.window_edit.text() == "Test Window"
        assert dialog_without_task.audio_combo.currentIndex() == 3  # Both
        assert dialog_without_task.fps_spin.value() == 25
        assert dialog_without_task.duration_spin.value() == 30  # 1800s / 60 = 30 min
        assert dialog_without_task.duration_unit_combo.currentIndex() == 1  # Minutes


class TestTaskDialogApplyPreset:
    """Tests for _apply_preset method."""

    def test_apply_preset(self, dialog_without_task):
        """Test applying a preset to the dialog."""
        preset = {
            "name": "Workday Morning",
            "display_name": "Утренняя запись",
            "trigger": "daily",
            "time": "09:30",
            "params": {
                "area": "full",
                "audio": "mic",
                "duration": 3600,
            },
        }

        dialog_without_task._apply_preset(preset)

        assert dialog_without_task.name_edit.text() == "Workday Morning"
        assert dialog_without_task.time_edit.time() == QTime(9, 30)
        assert dialog_without_task.area_combo.currentIndex() == 0  # Full
        assert dialog_without_task.audio_combo.currentIndex() == 1  # Mic
        assert dialog_without_task.duration_spin.value() == 60  # 3600s / 60 = 60 min

    def test_apply_preset_with_interval(self, dialog_without_task):
        """Test applying an interval preset."""
        preset = {
            "name": "Every Hour",
            "trigger": "interval",
            "interval_hours": 1,
            "interval_minutes": 30,
            "params": {
                "area": "window",
                "audio": "none",
                "duration": 0,
            },
        }

        dialog_without_task._apply_preset(preset)

        assert dialog_without_task.type_combo.currentIndex() == 3  # Interval
        assert dialog_without_task.interval_hours.value() == 1
        assert dialog_without_task.interval_minutes.value() == 30

    def test_apply_preset_with_cron(self, dialog_without_task):
        """Test applying a cron preset."""
        preset = {
            "name": "Weekday Afternoon",
            "trigger": "cron",
            "cron_expression": "0 14 * * 1-5",
            "params": {
                "area": "full",
                "audio": "system",
                "duration": 7200,
            },
        }

        dialog_without_task._apply_preset(preset)

        assert dialog_without_task.type_combo.currentIndex() == 4  # Cron
        assert dialog_without_task.cron_edit.text() == "0 14 * * 1-5"
        assert dialog_without_task.audio_combo.currentIndex() == 2  # System
        assert dialog_without_task.duration_spin.value() == 120  # 7200s / 60 = 120 min


class TestTaskDialogValidateScheduleInputs:
    """Tests for _validate_schedule_inputs method."""

    def test_validate_weekly_no_days(self, dialog_without_task):
        """Test validation fails for weekly without selected days."""
        dialog_without_task.type_combo.setCurrentIndex(2)  # Weekly
        # Ensure no days are selected

        error = dialog_without_task._validate_schedule_inputs()

        assert error is not None
        assert "выберите хотя бы один день" in error.lower()

    def test_validate_interval_zero(self, dialog_without_task):
        """Test validation fails for interval with zero duration."""
        dialog_without_task.type_combo.setCurrentIndex(3)  # Interval
        dialog_without_task.interval_hours.setValue(0)
        dialog_without_task.interval_minutes.setValue(0)

        error = dialog_without_task._validate_schedule_inputs()

        assert error is not None
        assert "должен быть больше нуля" in error.lower()

    def test_validate_cron_empty(self, dialog_without_task):
        """Test validation fails for empty cron expression."""
        dialog_without_task.type_combo.setCurrentIndex(4)  # Cron
        dialog_without_task.cron_edit.clear()

        error = dialog_without_task._validate_schedule_inputs()

        assert error is not None
        assert "cron-выражение" in error.lower()

    def test_validate_once_past_time(self, dialog_without_task):
        """Test validation fails for once with past time."""
        dialog_without_task.type_combo.setCurrentIndex(0)  # Once
        # Set date to yesterday
        yesterday = QDate.currentDate().addDays(-1)
        dialog_without_task.date_edit.setDate(yesterday)

        error = dialog_without_task._validate_schedule_inputs()

        assert error is not None
        assert "будущем" in error.lower()

    def test_validate_valid_daily(self, dialog_without_task):
        """Test validation passes for valid daily task."""
        dialog_without_task.type_combo.setCurrentIndex(1)  # Daily
        dialog_without_task.time_edit.setTime(QTime(12, 0))

        error = dialog_without_task._validate_schedule_inputs()

        assert error is None


class TestTaskDialogButtonBox:
    """Tests for dialog buttons."""

    def test_accept button_exists(self, dialog_without_task):
        """Test that dialog has Accept button."""
        button_box = dialog_without_task.findChild(QDialogButtonBox)
        assert button_box is not None
        assert button_box.standardButtons() & QDialogButtonBox.StandardButton.Ok

    def test_cancel_button_exists(self, dialog_without_task):
        """Test that dialog has Cancel button."""
        button_box = dialog_without_task.findChild(QDialogButtonBox)
        assert button_box is not None
        assert button_box.standardButtons() & QDialogButtonBox.StandardButton.Cancel
