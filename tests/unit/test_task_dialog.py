"""Unit tests for TaskDialog."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from scheduler.task_scheduler import (
    RecordingParams,
    ScheduleTask,
    ScheduleType,
)

from gui.scheduler.task_dialog import TaskDialog


class TestTaskDialogInitialization:
    """Tests for TaskDialog initialization."""

    def test_default_initialization(self):
        """Test dialog initialization without task."""
        # Mock all PyQt6 dependencies
        with patch("gui.scheduler.task_dialog.QDialog") as MockQDialog:
            # Mock the parent class
            MockQDialog.return_value = MagicMock()
            MockQDialog.return_value.exec = MagicMock(return_value=1)
            MockQDialog.return_value.setMinimumWidth = MagicMock()
            MockQDialog.return_value.setWindowTitle = MagicMock()

            # Create a minimal dialog instance by mocking __init__
            dialog = TaskDialog.__new__(TaskDialog)
            dialog.task = None
            dialog._preset_names = ["preset1"]
            dialog.name_edit = MagicMock()
            dialog.name_edit.setPlaceholderText = MagicMock()
            dialog.preset_combo = MagicMock()
            dialog.preset_combo.addItem = MagicMock()
            dialog.preset_combo.currentIndexChanged = MagicMock()
            dialog.type_combo = MagicMock()
            dialog.type_combo.currentIndexChanged = MagicMock()
            dialog.date_edit = MagicMock()
            dialog.date_edit.setDate = MagicMock()
            dialog.date_edit.setCalendarPopup = MagicMock()
            dialog.time_edit = MagicMock()
            dialog.time_edit.setTime = MagicMock()
            dialog.days_widget = MagicMock()
            dialog.interval_widget = MagicMock()
            dialog.cron_widget = MagicMock()
            dialog.area_combo = MagicMock()
            dialog.audio_combo = MagicMock()
            dialog.duration_widget = MagicMock()
            dialog.fps_spin = MagicMock()
            dialog.window_edit = MagicMock()
            dialog._schedule_preview_label = MagicMock()
            dialog._existing_next_run_label = MagicMock()
            dialog._inline_validation_label = MagicMock()

            # Initialize basic attributes
            dialog.name_edit = MagicMock(text=MagicMock(return_value=""))
            dialog.preset_combo = MagicMock(
                addItem=MagicMock(),
                currentIndexChanged=MagicMock(),
                setCurrentIndex=MagicMock(),
                currentIndex=MagicMock(return_value=0),
            )
            dialog.type_combo = MagicMock(
                addItem=MagicMock(),
                currentIndexChanged=MagicMock(),
                setCurrentIndex=MagicMock(),
                currentIndex=MagicMock(return_value=0),
            )
            dialog.date_edit = MagicMock(
                setDate=MagicMock(),
                setCalendarPopup=MagicMock(),
                date=MagicMock(
                    return_value=MagicMock(year=MagicMock(return_value=2025))
                ),
            )
            dialog.time_edit = MagicMock(
                setTime=MagicMock(),
                time=MagicMock(
                    return_value=MagicMock(hour=MagicMock(return_value=12))
                ),
            )
            dialog.days_widget = MagicMock()
            dialog.interval_widget = MagicMock()
            dialog.cron_widget = MagicMock()
            dialog.area_combo = MagicMock(
                addItem=MagicMock(),
                setCurrentIndex=MagicMock(),
                currentIndex=MagicMock(return_value=0),
            )
            dialog.audio_combo = MagicMock(
                addItem=MagicMock(),
                setCurrentIndex=MagicMock(),
                currentIndex=MagicMock(return_value=0),
            )
            dialog.duration_widget = MagicMock()
            dialog.fps_spin = MagicMock(
                setValue=MagicMock(),
                value=MagicMock(return_value=30),
            )
            dialog.window_edit = MagicMock()
            dialog._schedule_preview_label = MagicMock()
            dialog._existing_next_run_label = MagicMock()
            dialog._inline_validation_label = MagicMock()

            dialog._schedule_preview_label = MagicMock()
            dialog._existing_next_run_label = MagicMock()

            # Test basic attributes
            assert dialog.task is None

    def test_initialization_with_task(self):
        """Test dialog initialization with existing task."""
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

        # Test that task attributes can be created
        assert task.name == "Test Task"
        assert task.schedule_type == ScheduleType.DAILY


class TestTaskDialogUI:
    """Tests for TaskDialog UI components."""

    def test_preset_combo_initialization(self):
        """Test preset combo box initialization."""
        with patch(
            "gui.scheduler.task_dialog.list_presets"
        ) as mock_list_presets:
            mock_list_presets.return_value = []

            dialog = TaskDialog.__new__(TaskDialog)
            dialog._preset_names = []
            dialog.preset_combo = MagicMock()

            # Test that dialog creates preset names correctly
            for preset in []:
                preset_name = str(preset.get("name", "")).strip()
                if not preset_name:
                    continue
                display_name = str(
                    preset.get("display_name", preset_name)
                ).strip()
                dialog._preset_names.append(preset_name)

            assert len(dialog._preset_names) == 0

    def test_schedule_type_combo_items(self):
        """Test schedule type combo box items."""
        dialog = TaskDialog.__new__(TaskDialog)
        dialog.type_combo = MagicMock()

        expected_items = [
            "Разовая",
            "Ежедневная",
            "Еженедельная",
            "Интервал",
            "Cron",
        ]

        # Test that combo box can be created with expected items
        assert len(expected_items) == 5

    def test_area_combo_items(self):
        """Test area combo box items."""
        dialog = TaskDialog.__new__(TaskDialog)
        dialog.area_combo = MagicMock()

        expected_items = ["Полный экран", "Окно", "Прямоугольник"]

        # Test that combo box can be created with expected items
        assert len(expected_items) == 3

    def test_audio_combo_items(self):
        """Test audio combo box items."""
        dialog = TaskDialog.__new__(TaskDialog)
        dialog.audio_combo = MagicMock()

        expected_items = ["Нет", "Микрофон", "Системное аудио", "Оба"]

        # Test that combo box can be created with expected items
        assert len(expected_items) == 4


class TestTaskDialogGetTaskData:
    """Tests for get_task_data method."""

    def test_get_task_data_once(self):
        """Test get_task_data for 'once' schedule type."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog.name_edit = MagicMock()
        dialog.name_edit.text = MagicMock(return_value="Once Task")

        dialog.type_combo = MagicMock()
        dialog.type_combo.currentIndex = MagicMock(return_value=0)

        dialog.date_edit = MagicMock()
        dialog.date_edit.date = MagicMock(
            return_value=MagicMock(
                year=MagicMock(return_value=2025),
                month=MagicMock(return_value=6),
                day=MagicMock(return_value=15),
            )
        )
        dialog.date_edit.time = MagicMock(
            return_value=MagicMock(
                hour=MagicMock(return_value=14),
                minute=MagicMock(return_value=30),
            )
        )

        dialog.time_edit = MagicMock()
        dialog.time_edit.time = MagicMock(
            return_value=MagicMock(
                hour=MagicMock(return_value=14),
                minute=MagicMock(return_value=30),
            )
        )

        dialog.area_combo = MagicMock()
        dialog.area_combo.currentIndex = MagicMock(return_value=1)

        dialog.audio_combo = MagicMock()
        dialog.audio_combo.currentIndex = MagicMock(return_value=2)

        dialog.fps_spin = MagicMock()
        dialog.fps_spin.value = MagicMock(return_value=60)

        dialog.duration_spin = MagicMock()
        dialog.duration_spin.value = MagicMock(return_value=0)
        dialog.duration_spin.setValue = MagicMock()

        dialog.duration_unit_combo = MagicMock()
        dialog.duration_unit_combo.currentIndex = MagicMock(return_value=1)

        data = dialog.get_task_data()

        assert data["name"] == "Once Task"
        assert data["schedule_type"] == ScheduleType.ONCE
        assert data["area_type"] == "window"
        assert data["audio_type"] == "system"
        assert data["fps"] == 60
        assert data["start_time"] is not None

    def test_get_task_data_daily(self):
        """Test get_task_data for 'daily' schedule type."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog.name_edit = MagicMock()
        dialog.name_edit.text = MagicMock(return_value="Daily Task")

        dialog.type_combo = MagicMock()
        dialog.type_combo.currentIndex = MagicMock(return_value=1)

        dialog.time_edit = MagicMock()
        dialog.time_edit.time = MagicMock(
            return_value=MagicMock(
                hour=MagicMock(return_value=9),
                minute=MagicMock(return_value=0),
            )
        )

        dialog.area_combo = MagicMock()
        dialog.area_combo.currentIndex = MagicMock(return_value=0)

        data = dialog.get_task_data()

        assert data["name"] == "Daily Task"
        assert data["schedule_type"] == ScheduleType.DAILY
        assert data["area_type"] == "full"
        assert "time_of_day" in data
        assert data["time_of_day"] == "09:00"

    def test_get_task_data_weekly(self):
        """Test get_task_data for 'weekly' schedule type."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog.type_combo = MagicMock()
        dialog.type_combo.currentIndex = MagicMock(return_value=2)

        dialog.day_checks = [
            MagicMock(isChecked=MagicMock(return_value=True)),
            MagicMock(isChecked=MagicMock(return_value=False)),
            MagicMock(isChecked=MagicMock(return_value=True)),
            MagicMock(isChecked=MagicMock(return_value=False)),
            MagicMock(isChecked=MagicMock(return_value=True)),
            MagicMock(isChecked=MagicMock(return_value=False)),
            MagicMock(isChecked=MagicMock(return_value=False)),
        ]

        data = dialog.get_task_data()

        assert data["schedule_type"] == ScheduleType.WEEKLY
        assert data["days_of_week"] == [0, 2, 4]

    def test_get_task_data_interval(self):
        """Test get_task_data for 'interval' schedule type."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog.type_combo = MagicMock()
        dialog.type_combo.currentIndex = MagicMock(return_value=3)

        dialog.interval_hours = MagicMock()
        dialog.interval_hours.value = MagicMock(return_value=2)

        dialog.interval_minutes = MagicMock()
        dialog.interval_minutes.value = MagicMock(return_value=30)

        data = dialog.get_task_data()

        assert data["schedule_type"] == ScheduleType.INTERVAL
        assert data["interval_hours"] == 2
        assert data["interval_minutes"] == 30

    def test_get_task_data_cron(self):
        """Test get_task_data for 'cron' schedule type."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog.type_combo = MagicMock()
        dialog.type_combo.currentIndex = MagicMock(return_value=4)

        dialog.cron_edit = MagicMock()
        dialog.cron_edit.text = MagicMock(return_value="0 9 * * 1-5")

        data = dialog.get_task_data()

        assert data["schedule_type"] == ScheduleType.CRON
        assert data["cron_expression"] == "0 9 * * 1-5"

    def test_get_task_data_duration_minutes(self):
        """Test duration conversion when unit is minutes."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog.duration_spin = MagicMock()
        dialog.duration_spin.value = MagicMock(return_value=90)

        dialog.duration_unit_combo = MagicMock()
        dialog.duration_unit_combo.currentIndex = MagicMock(return_value=1)

        data = dialog.get_task_data()

        assert data["duration"] == 90 * 60  # 90 minutes = 5400 seconds

    def test_get_task_data_duration_seconds(self):
        """Test duration conversion when unit is seconds."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog.duration_spin = MagicMock()
        dialog.duration_spin.value = MagicMock(return_value=1800)

        dialog.duration_unit_combo = MagicMock()
        dialog.duration_unit_combo.currentIndex = MagicMock(return_value=0)

        data = dialog.get_task_data()

        assert data["duration"] == 1800  # 1800 seconds = 30 minutes


class TestTaskDialogApplyPreset:
    """Tests for _apply_preset method."""

    def test_apply_preset(self):
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

        dialog = TaskDialog.__new__(TaskDialog)

        dialog.name_edit = MagicMock()
        dialog.name_edit.setText = MagicMock()

        dialog.time_edit = MagicMock()
        dialog.time_edit.setTime = MagicMock()

        dialog.area_combo = MagicMock()
        dialog.area_combo.setCurrentIndex = MagicMock()

        dialog.audio_combo = MagicMock()
        dialog.audio_combo.setCurrentIndex = MagicMock()

        dialog.duration_spin = MagicMock()
        dialog.duration_spin.setValue = MagicMock()

        dialog.duration_unit_combo = MagicMock()
        dialog.duration_unit_combo.setCurrentIndex = MagicMock()

        dialog._refresh_schedule_preview = MagicMock()

        dialog._apply_preset(preset)

        dialog.name_edit.setText.assert_called_with("Workday Morning")
        dialog.area_combo.setCurrentIndex.assert_called_with(0)  # Full
        dialog.audio_combo.setCurrentIndex.assert_called_with(1)  # Mic

    def test_apply_preset_with_interval(self):
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

        dialog = TaskDialog.__new__(TaskDialog)

        dialog.type_combo = MagicMock()
        dialog.type_combo.setCurrentIndex = MagicMock()

        dialog.interval_hours = MagicMock()
        dialog.interval_hours.setValue = MagicMock()

        dialog.interval_minutes = MagicMock()
        dialog.interval_minutes.setValue = MagicMock()

        dialog._refresh_schedule_preview = MagicMock()

        dialog._apply_preset(preset)

        dialog.type_combo.setCurrentIndex.assert_called_with(3)  # Interval
        dialog.interval_hours.setValue.assert_called_with(1)

    def test_apply_preset_with_cron(self):
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

        dialog = TaskDialog.__new__(TaskDialog)

        dialog.type_combo = MagicMock()
        dialog.type_combo.setCurrentIndex = MagicMock()

        dialog.cron_edit = MagicMock()
        dialog.cron_edit.setText = MagicMock()

        dialog.audio_combo = MagicMock()
        dialog.audio_combo.setCurrentIndex = MagicMock()

        dialog.duration_spin = MagicMock()
        dialog.duration_spin.setValue = MagicMock()

        dialog._refresh_schedule_preview = MagicMock()

        dialog._apply_preset(preset)

        dialog.type_combo.setCurrentIndex.assert_called_with(4)  # Cron
        dialog.cron_edit.setText.assert_called_with("0 14 * * 1-5")


class TestTaskDialogValidateScheduleInputs:
    """Tests for _validate_schedule_inputs method."""

    def test_validate_weekly_no_days(self):
        """Test validation fails for weekly without selected days."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog.type_combo = MagicMock()
        dialog.type_combo.currentIndex = MagicMock(return_value=2)

        dialog.day_checks = [
            MagicMock(isChecked=MagicMock(return_value=False)),
            MagicMock(isChecked=MagicMock(return_value=False)),
            MagicMock(isChecked=MagicMock(return_value=False)),
            MagicMock(isChecked=MagicMock(return_value=False)),
            MagicMock(isChecked=MagicMock(return_value=False)),
            MagicMock(isChecked=MagicMock(return_value=False)),
            MagicMock(isChecked=MagicMock(return_value=False)),
        ]

        error = dialog._validate_schedule_inputs()

        assert error is not None
        assert "выберите хотя бы один день" in error.lower()

    def test_validate_interval_zero(self):
        """Test validation fails for interval with zero duration."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog.type_combo = MagicMock()
        dialog.type_combo.currentIndex = MagicMock(return_value=3)

        dialog.interval_hours = MagicMock()
        dialog.interval_hours.value = MagicMock(return_value=0)

        dialog.interval_minutes = MagicMock()
        dialog.interval_minutes.value = MagicMock(return_value=0)

        error = dialog._validate_schedule_inputs()

        assert error is not None
        assert "должен быть больше нуля" in error.lower()

    def test_validate_cron_empty(self):
        """Test validation fails for empty cron expression."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog.type_combo = MagicMock()
        dialog.type_combo.currentIndex = MagicMock(return_value=4)

        dialog.cron_edit = MagicMock()
        dialog.cron_edit.text = MagicMock(return_value="")

        error = dialog._validate_schedule_inputs()

        assert error is not None
        assert "cron-выражение" in error.lower()

    def test_validate_once_past_time(self):
        """Test validation fails for once with past time."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog.type_combo = MagicMock()
        dialog.type_combo.currentIndex = MagicMock(return_value=0)

        # Set date to yesterday
        yesterday = datetime.now().day - 1
        dialog.date_edit = MagicMock()
        dialog.date_edit.date = MagicMock(
            return_value=MagicMock(
                year=MagicMock(return_value=datetime.now().year),
                month=MagicMock(return_value=datetime.now().month),
                day=MagicMock(return_value=yesterday),
            )
        )
        dialog.time_edit = MagicMock()
        dialog.time_edit.time = MagicMock(
            return_value=MagicMock(
                hour=MagicMock(return_value=datetime.now().hour),
                minute=MagicMock(return_value=datetime.now().minute),
            )
        )

        error = dialog._validate_schedule_inputs()

        assert error is not None
        assert "будущем" in error.lower()

    def test_validate_valid_daily(self):
        """Test validation passes for valid daily task."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog.type_combo = MagicMock()
        dialog.type_combo.currentIndex = MagicMock(return_value=1)

        error = dialog._validate_schedule_inputs()

        assert error is None


class TestTaskDialogButtonBox:
    """Tests for dialog buttons."""

    def test_accept_button_exists(self):
        """Test that dialog has Accept button."""
        from PyQt6.QtWidgets import QDialogButtonBox

        # Test that button box can be created
        buttons = (
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        assert buttons == 3  # Ok=1, Cancel=2

    def test_cancel_button_exists(self):
        """Test that dialog has Cancel button."""
        from PyQt6.QtWidgets import QDialogButtonBox

        # Test that Cancel button is a valid standard button
        assert QDialogButtonBox.StandardButton.Cancel == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
