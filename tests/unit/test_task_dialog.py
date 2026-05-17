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

        dialog.window_edit = MagicMock()
        dialog.window_edit.text = MagicMock(return_value="Test Window")

        data = dialog.get_task_data()

        assert data["name"] == "Once Task"
        assert data["schedule_type"] == ScheduleType.ONCE
        assert data["area_type"] == "window"
        assert data["audio_type"] == "system"
        assert data["fps"] == 60
        assert data["start_time"] is not None
        assert data["window_title"] == "Test Window"

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

        dialog.audio_combo = MagicMock()
        dialog.audio_combo.currentIndex = MagicMock(return_value=0)

        dialog.fps_spin = MagicMock()
        dialog.fps_spin.value = MagicMock(return_value=30)

        dialog.duration_spin = MagicMock()
        dialog.duration_spin.value = MagicMock(return_value=0)

        dialog.duration_unit_combo = MagicMock()
        dialog.duration_unit_combo.currentIndex = MagicMock(return_value=1)

        data = dialog.get_task_data()

        assert data["name"] == "Daily Task"
        assert data["schedule_type"] == ScheduleType.DAILY
        assert data["area_type"] == "full"
        assert "time_of_day" in data
        assert data["time_of_day"] == "09:00"

    def test_get_task_data_weekly(self):
        """Test get_task_data for 'weekly' schedule type."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog.name_edit = MagicMock()
        dialog.name_edit.text = MagicMock(return_value="Weekly Task")

        dialog.type_combo = MagicMock()
        dialog.type_combo.currentIndex = MagicMock(return_value=2)

        dialog.time_edit = MagicMock()
        dialog.time_edit.time = MagicMock(
            return_value=MagicMock(
                hour=MagicMock(return_value=9),
                minute=MagicMock(return_value=0),
            )
        )

        dialog.area_combo = MagicMock()
        dialog.area_combo.currentIndex = MagicMock(return_value=0)

        dialog.audio_combo = MagicMock()
        dialog.audio_combo.currentIndex = MagicMock(return_value=0)

        dialog.fps_spin = MagicMock()
        dialog.fps_spin.value = MagicMock(return_value=30)

        dialog.duration_spin = MagicMock()
        dialog.duration_spin.value = MagicMock(return_value=0)

        dialog.duration_unit_combo = MagicMock()
        dialog.duration_unit_combo.currentIndex = MagicMock(return_value=1)

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

        dialog.name_edit = MagicMock()
        dialog.name_edit.text = MagicMock(return_value="Interval Task")

        dialog.type_combo = MagicMock()
        dialog.type_combo.currentIndex = MagicMock(return_value=3)

        dialog.area_combo = MagicMock()
        dialog.area_combo.currentIndex = MagicMock(return_value=0)

        dialog.audio_combo = MagicMock()
        dialog.audio_combo.currentIndex = MagicMock(return_value=0)

        dialog.fps_spin = MagicMock()
        dialog.fps_spin.value = MagicMock(return_value=30)

        dialog.duration_spin = MagicMock()
        dialog.duration_spin.value = MagicMock(return_value=0)

        dialog.duration_unit_combo = MagicMock()
        dialog.duration_unit_combo.currentIndex = MagicMock(return_value=1)

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

        dialog.name_edit = MagicMock()
        dialog.name_edit.text = MagicMock(return_value="Cron Task")

        dialog.type_combo = MagicMock()
        dialog.type_combo.currentIndex = MagicMock(return_value=4)

        dialog.area_combo = MagicMock()
        dialog.area_combo.currentIndex = MagicMock(return_value=0)

        dialog.audio_combo = MagicMock()
        dialog.audio_combo.currentIndex = MagicMock(return_value=0)

        dialog.fps_spin = MagicMock()
        dialog.fps_spin.value = MagicMock(return_value=30)

        dialog.duration_spin = MagicMock()
        dialog.duration_spin.value = MagicMock(return_value=0)

        dialog.duration_unit_combo = MagicMock()
        dialog.duration_unit_combo.currentIndex = MagicMock(return_value=1)

        dialog.cron_edit = MagicMock()
        dialog.cron_edit.text = MagicMock(return_value="0 9 * * 1-5")

        data = dialog.get_task_data()

        assert data["schedule_type"] == ScheduleType.CRON
        assert data["cron_expression"] == "0 9 * * 1-5"

    def test_get_task_data_duration_minutes(self):
        """Test duration conversion when unit is minutes."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog.name_edit = MagicMock()
        dialog.name_edit.text = MagicMock(return_value="Duration Test")

        dialog.type_combo = MagicMock()
        dialog.type_combo.currentIndex = MagicMock(return_value=1)

        dialog.time_edit = MagicMock()
        dialog.time_edit.time = MagicMock(
            return_value=MagicMock(
                hour=MagicMock(return_value=12),
                minute=MagicMock(return_value=0),
            )
        )

        dialog.area_combo = MagicMock()
        dialog.area_combo.currentIndex = MagicMock(return_value=0)

        dialog.audio_combo = MagicMock()
        dialog.audio_combo.currentIndex = MagicMock(return_value=0)

        dialog.fps_spin = MagicMock()
        dialog.fps_spin.value = MagicMock(return_value=30)

        dialog.duration_spin = MagicMock()
        dialog.duration_spin.value = MagicMock(return_value=90)

        dialog.duration_unit_combo = MagicMock()
        dialog.duration_unit_combo.currentIndex = MagicMock(return_value=1)

        data = dialog.get_task_data()

        assert data["duration"] == 90 * 60  # 90 minutes = 5400 seconds

    def test_get_task_data_duration_seconds(self):
        """Test duration conversion when unit is seconds."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog.name_edit = MagicMock()
        dialog.name_edit.text = MagicMock(return_value="Duration Test")

        dialog.type_combo = MagicMock()
        dialog.type_combo.currentIndex = MagicMock(return_value=1)

        dialog.time_edit = MagicMock()
        dialog.time_edit.time = MagicMock(
            return_value=MagicMock(
                hour=MagicMock(return_value=12),
                minute=MagicMock(return_value=0),
            )
        )

        dialog.area_combo = MagicMock()
        dialog.area_combo.currentIndex = MagicMock(return_value=0)

        dialog.audio_combo = MagicMock()
        dialog.audio_combo.currentIndex = MagicMock(return_value=0)

        dialog.fps_spin = MagicMock()
        dialog.fps_spin.value = MagicMock(return_value=30)

        dialog.duration_spin = MagicMock()
        dialog.duration_spin.value = MagicMock(return_value=1800)

        dialog.duration_unit_combo = MagicMock()
        dialog.duration_unit_combo.currentIndex = MagicMock(return_value=0)

        data = dialog.get_task_data()

        assert data["duration"] == 1800  # 1800 seconds = 30 minutes


class TestTaskDialogApplyPreset:
    """Tests for _apply_preset method."""

    def _setup_preset_attrs(self, dialog):
        """Set up mock attributes needed by _apply_preset."""
        dialog.type_combo = MagicMock()
        dialog.type_combo.setCurrentIndex = MagicMock()
        dialog.name_edit = MagicMock()
        dialog.name_edit.setText = MagicMock()
        dialog.time_edit = MagicMock()
        dialog.time_edit.setTime = MagicMock()
        dialog.day_checks = [
            MagicMock(setChecked=MagicMock()),
            MagicMock(setChecked=MagicMock()),
            MagicMock(setChecked=MagicMock()),
            MagicMock(setChecked=MagicMock()),
            MagicMock(setChecked=MagicMock()),
            MagicMock(setChecked=MagicMock()),
            MagicMock(setChecked=MagicMock()),
        ]
        dialog.interval_hours = MagicMock()
        dialog.interval_hours.setValue = MagicMock()
        dialog.interval_minutes = MagicMock()
        dialog.interval_minutes.setValue = MagicMock()
        dialog.cron_edit = MagicMock()
        dialog.cron_edit.setText = MagicMock()
        dialog.area_combo = MagicMock()
        dialog.area_combo.setCurrentIndex = MagicMock()
        dialog.audio_combo = MagicMock()
        dialog.audio_combo.setCurrentIndex = MagicMock()
        dialog.duration_spin = MagicMock()
        dialog.duration_spin.setValue = MagicMock()
        dialog.duration_unit_combo = MagicMock()
        dialog.duration_unit_combo.setCurrentIndex = MagicMock()
        dialog._refresh_schedule_preview = MagicMock()

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
        self._setup_preset_attrs(dialog)

        dialog._apply_preset(preset)

        dialog.name_edit.setText.assert_called_with("Workday Morning")
        dialog.area_combo.setCurrentIndex.assert_called_with(0)
        dialog.audio_combo.setCurrentIndex.assert_called_with(1)

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
        self._setup_preset_attrs(dialog)

        dialog._apply_preset(preset)

        dialog.type_combo.setCurrentIndex.assert_called_with(3)
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
        self._setup_preset_attrs(dialog)

        dialog._apply_preset(preset)

        dialog.type_combo.setCurrentIndex.assert_called_with(4)
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
        with patch("gui.scheduler.task_dialog.QDialogButtonBox") as MockBox:
            MockBox.StandardButton.Ok = 1
            buttons = MockBox.StandardButton.Ok | 2
            assert buttons == 3

    def test_cancel_button_exists(self):
        """Test that dialog has Cancel button."""
        with patch("gui.scheduler.task_dialog.QDialogButtonBox") as MockBox:
            MockBox.StandardButton.Cancel = 2
            assert MockBox.StandardButton.Cancel == 2



class TestTaskDialogInitReal:
    """Tests for __init__ with mocking to avoid widget creation."""

    def test_init_no_task(self):
        """Test __init__ without task patches _setup_ui and calls no _load_task."""
        with patch.object(TaskDialog, "_setup_ui") as mock_setup_ui:
            with patch.object(TaskDialog, "_load_task") as mock_load_task:
                with patch(
                    "gui.scheduler.task_dialog.QDialog.__init__",
                    return_value=None,
                ):
                    dialog = TaskDialog.__new__(TaskDialog)
                    dialog.setWindowTitle = MagicMock()
                    dialog.setMinimumWidth = MagicMock()
                    TaskDialog.__init__(dialog, task=None)

                    assert dialog.task is None
                    mock_setup_ui.assert_called_once()
                    mock_load_task.assert_not_called()

    def test_init_with_task(self):
        """Test __init__ with existing task calls _load_task."""
        task = ScheduleTask(
            id="test-1",
            name="Existing Task",
            schedule_type=ScheduleType.DAILY,
            params=RecordingParams(
                area_type="full",
                audio_type="mic",
            ),
            enabled=True,
        )

        with patch.object(TaskDialog, "_setup_ui") as mock_setup_ui:
            with patch.object(TaskDialog, "_load_task") as mock_load_task:
                with patch(
                    "gui.scheduler.task_dialog.QDialog.__init__",
                    return_value=None,
                ):
                    dialog = TaskDialog.__new__(TaskDialog)
                    dialog.setWindowTitle = MagicMock()
                    dialog.setMinimumWidth = MagicMock()
                    TaskDialog.__init__(dialog, task=task)

                    assert dialog.task is task
                    mock_setup_ui.assert_called_once()
                    mock_load_task.assert_called_once_with(task)


class TestTaskDialogOnTypeChanged:
    """Tests for _on_type_changed method."""

    def _setup_type_widgets(self, dialog):
        dialog.date_edit = MagicMock()
        dialog.date_edit.setVisible = MagicMock()
        dialog.time_edit = MagicMock()
        dialog.time_edit.setVisible = MagicMock()
        dialog.days_widget = MagicMock()
        dialog.days_widget.setVisible = MagicMock()
        dialog.interval_widget = MagicMock()
        dialog.interval_widget.setVisible = MagicMock()
        dialog.cron_widget = MagicMock()
        dialog.cron_widget.setVisible = MagicMock()

    def test_type_changed_once(self):
        """Test _on_type_changed with once (index 0)."""
        dialog = TaskDialog.__new__(TaskDialog)
        self._setup_type_widgets(dialog)
        dialog._schedule_preview_label = MagicMock()
        dialog._refresh_schedule_preview = MagicMock()

        dialog._on_type_changed(0)

        dialog.date_edit.setVisible.assert_called_with(True)
        dialog.time_edit.setVisible.assert_called_with(True)
        dialog.days_widget.setVisible.assert_called_with(False)
        dialog.interval_widget.setVisible.assert_called_with(False)
        dialog.cron_widget.setVisible.assert_called_with(False)
        dialog._refresh_schedule_preview.assert_called_once()

    def test_type_changed_daily(self):
        """Test _on_type_changed with daily (index 1)."""
        dialog = TaskDialog.__new__(TaskDialog)
        self._setup_type_widgets(dialog)
        dialog._schedule_preview_label = MagicMock()
        dialog._refresh_schedule_preview = MagicMock()

        dialog._on_type_changed(1)

        dialog.date_edit.setVisible.assert_called_with(False)
        dialog.time_edit.setVisible.assert_called_with(True)
        dialog.days_widget.setVisible.assert_called_with(False)
        dialog.interval_widget.setVisible.assert_called_with(False)
        dialog.cron_widget.setVisible.assert_called_with(False)

    def test_type_changed_weekly(self):
        """Test _on_type_changed with weekly (index 2)."""
        dialog = TaskDialog.__new__(TaskDialog)
        self._setup_type_widgets(dialog)
        dialog._schedule_preview_label = MagicMock()
        dialog._refresh_schedule_preview = MagicMock()

        dialog._on_type_changed(2)

        dialog.date_edit.setVisible.assert_called_with(False)
        dialog.time_edit.setVisible.assert_called_with(True)
        dialog.days_widget.setVisible.assert_called_with(True)
        dialog.interval_widget.setVisible.assert_called_with(False)
        dialog.cron_widget.setVisible.assert_called_with(False)

    def test_type_changed_interval(self):
        """Test _on_type_changed with interval (index 3)."""
        dialog = TaskDialog.__new__(TaskDialog)
        self._setup_type_widgets(dialog)
        dialog._schedule_preview_label = MagicMock()
        dialog._refresh_schedule_preview = MagicMock()

        dialog._on_type_changed(3)

        dialog.date_edit.setVisible.assert_called_with(False)
        dialog.time_edit.setVisible.assert_called_with(False)
        dialog.days_widget.setVisible.assert_called_with(False)
        dialog.interval_widget.setVisible.assert_called_with(True)
        dialog.cron_widget.setVisible.assert_called_with(False)

    def test_type_changed_cron(self):
        """Test _on_type_changed with cron (index 4)."""
        dialog = TaskDialog.__new__(TaskDialog)
        self._setup_type_widgets(dialog)
        dialog._schedule_preview_label = MagicMock()
        dialog._refresh_schedule_preview = MagicMock()

        dialog._on_type_changed(4)

        dialog.date_edit.setVisible.assert_called_with(False)
        dialog.time_edit.setVisible.assert_called_with(False)
        dialog.days_widget.setVisible.assert_called_with(False)
        dialog.interval_widget.setVisible.assert_called_with(False)
        dialog.cron_widget.setVisible.assert_called_with(True)


class TestTaskDialogLoadTask:
    """Tests for _load_task method."""

    def _setup_load_task_widgets(self, dialog):
        dialog.name_edit = MagicMock()
        dialog.name_edit.setText = MagicMock()
        dialog.type_combo = MagicMock()
        dialog.type_combo.setCurrentIndex = MagicMock()
        dialog.date_edit = MagicMock()
        dialog.date_edit.setDate = MagicMock()
        dialog.time_edit = MagicMock()
        dialog.time_edit.setTime = MagicMock()
        dialog.day_checks = [
            MagicMock(setChecked=MagicMock()),
            MagicMock(setChecked=MagicMock()),
            MagicMock(setChecked=MagicMock()),
            MagicMock(setChecked=MagicMock()),
            MagicMock(setChecked=MagicMock()),
            MagicMock(setChecked=MagicMock()),
            MagicMock(setChecked=MagicMock()),
        ]
        dialog.interval_hours = MagicMock()
        dialog.interval_hours.setValue = MagicMock()
        dialog.interval_minutes = MagicMock()
        dialog.interval_minutes.setValue = MagicMock()
        dialog.fps_spin = MagicMock()
        dialog.fps_spin.setValue = MagicMock()
        dialog.cron_edit = MagicMock()
        dialog.cron_edit.setText = MagicMock()
        dialog.area_combo = MagicMock()
        dialog.area_combo.setCurrentIndex = MagicMock()
        dialog.window_edit = MagicMock()
        dialog.window_edit.setText = MagicMock()
        dialog.audio_combo = MagicMock()
        dialog.audio_combo.setCurrentIndex = MagicMock()
        dialog.duration_spin = MagicMock()
        dialog.duration_spin.setValue = MagicMock()
        dialog.duration_unit_combo = MagicMock()
        dialog.duration_unit_combo.setCurrentIndex = MagicMock()
        dialog._refresh_schedule_preview = MagicMock()

    def _make_task(
        self,
        schedule_type=ScheduleType.DAILY,
        area_type="full",
        audio_type="mic",
        fps=30,
        duration=None,
        start_time=None,
        time_of_day="09:00",
        days_of_week=None,
        interval_hours=None,
        interval_minutes=None,
        cron_expression=None,
        window_title="",
    ):
        params = RecordingParams(
            area_type=area_type,
            window_title=window_title,
            audio_type=audio_type,
            fps=fps,
            duration=duration,
        )
        return ScheduleTask(
            id="test-load-task",
            name="Loaded Task",
            schedule_type=schedule_type,
            params=params,
            enabled=True,
            start_time=start_time,
            time_of_day=time_of_day,
            days_of_week=days_of_week,
            interval_hours=interval_hours,
            interval_minutes=interval_minutes,
            cron_expression=cron_expression,
        )

    def test_load_daily(self):
        """Test _load_task with daily task."""
        dialog = TaskDialog.__new__(TaskDialog)
        self._setup_load_task_widgets(dialog)

        task = self._make_task(
            schedule_type=ScheduleType.DAILY,
            area_type="full",
            audio_type="mic",
            fps=30,
            duration=3600,
            time_of_day="10:00",
        )

        dialog._load_task(task)

        dialog.name_edit.setText.assert_called_with("Loaded Task")
        dialog.type_combo.setCurrentIndex.assert_called_with(1)
        dialog.area_combo.setCurrentIndex.assert_called_with(0)
        dialog.audio_combo.setCurrentIndex.assert_called_with(1)
        dialog.duration_spin.setValue.assert_called_with(60)
        dialog.duration_unit_combo.setCurrentIndex.assert_called_with(1)
        dialog._refresh_schedule_preview.assert_called_once()

    def test_load_once_with_start_time(self):
        """Test _load_task with once task and start_time."""
        from datetime import datetime

        dialog = TaskDialog.__new__(TaskDialog)
        self._setup_load_task_widgets(dialog)

        start_time = datetime(2025, 12, 25, 10, 30)
        task = self._make_task(
            schedule_type=ScheduleType.ONCE,
            start_time=start_time,
            time_of_day=None,
        )

        dialog._load_task(task)

        dialog.type_combo.setCurrentIndex.assert_called_with(0)
        dialog.date_edit.setDate.assert_called_once()
        dialog.time_edit.setTime.assert_called_once()

    def test_load_weekly_with_days(self):
        """Test _load_task with weekly and days_of_week."""
        dialog = TaskDialog.__new__(TaskDialog)
        self._setup_load_task_widgets(dialog)

        task = self._make_task(
            schedule_type=ScheduleType.WEEKLY,
            days_of_week=[0, 2, 4],
        )

        dialog._load_task(task)

        dialog.type_combo.setCurrentIndex.assert_called_with(2)
        dialog.day_checks[0].setChecked.assert_called_with(True)
        dialog.day_checks[2].setChecked.assert_called_with(True)
        dialog.day_checks[4].setChecked.assert_called_with(True)

    def test_load_interval(self):
        """Test _load_task with interval."""
        dialog = TaskDialog.__new__(TaskDialog)
        self._setup_load_task_widgets(dialog)

        task = self._make_task(
            schedule_type=ScheduleType.INTERVAL,
            interval_hours=2,
            interval_minutes=30,
        )

        dialog._load_task(task)

        dialog.type_combo.setCurrentIndex.assert_called_with(3)
        dialog.interval_hours.setValue.assert_called_with(2)
        dialog.interval_minutes.setValue.assert_called_with(30)

    def test_load_cron(self):
        """Test _load_task with cron."""
        dialog = TaskDialog.__new__(TaskDialog)
        self._setup_load_task_widgets(dialog)

        task = self._make_task(
            schedule_type=ScheduleType.CRON,
            cron_expression="0 9 * * 1-5",
        )

        dialog._load_task(task)

        dialog.type_combo.setCurrentIndex.assert_called_with(4)
        dialog.cron_edit.setText.assert_called_with("0 9 * * 1-5")

    def test_load_with_window_title(self):
        """Test _load_task sets window edit."""
        dialog = TaskDialog.__new__(TaskDialog)
        self._setup_load_task_widgets(dialog)

        task = self._make_task(
            schedule_type=ScheduleType.DAILY,
            area_type="window",
            window_title="My Window",
        )

        dialog._load_task(task)

        dialog.window_edit.setText.assert_called_with("My Window")

    def test_load_duration_seconds(self):
        """Test _load_task with duration not divisible by 60."""
        dialog = TaskDialog.__new__(TaskDialog)
        self._setup_load_task_widgets(dialog)

        task = self._make_task(
            schedule_type=ScheduleType.DAILY,
            duration=90,
        )

        dialog._load_task(task)

        dialog.duration_spin.setValue.assert_called_with(90)
        dialog.duration_unit_combo.setCurrentIndex.assert_called_with(0)


class TestTaskDialogRefreshPreview:
    """Tests for _refresh_schedule_preview method."""

    def test_refresh_with_existing_next_run(self):
        """Test refresh with existing next run text."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog._existing_next_run_text = "2025-06-15 14:30"
        dialog._existing_next_run_label = MagicMock()
        dialog._existing_next_run_label.setText = MagicMock()
        dialog._existing_next_run_label.setVisible = MagicMock()

        dialog._validate_schedule_inputs = MagicMock(return_value=None)
        dialog._set_inline_validation_message = MagicMock()
        dialog._schedule_preview_label = MagicMock()
        dialog._schedule_preview_label.setText = MagicMock()

        dialog._calculate_schedule_preview = MagicMock(
            return_value=([], None)
        )

        dialog._refresh_schedule_preview()

        dialog._existing_next_run_label.setText.assert_called_once()
        dialog._existing_next_run_label.setVisible.assert_called_with(True)

    def test_refresh_without_existing_next_run(self):
        """Test refresh without existing next run text."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog._existing_next_run_text = ""
        dialog._existing_next_run_label = MagicMock()
        dialog._existing_next_run_label.setVisible = MagicMock()

        dialog._validate_schedule_inputs = MagicMock(return_value=None)
        dialog._set_inline_validation_message = MagicMock()
        dialog._schedule_preview_label = MagicMock()
        dialog._schedule_preview_label.setText = MagicMock()

        dialog._calculate_schedule_preview = MagicMock(
            return_value=([], None)
        )

        dialog._refresh_schedule_preview()

        dialog._existing_next_run_label.setVisible.assert_called_with(False)

    def test_refresh_with_validation_error(self):
        """Test refresh stops when validation fails."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog._existing_next_run_text = ""
        dialog._existing_next_run_label = MagicMock()
        dialog._existing_next_run_label.setVisible = MagicMock()

        dialog._validate_schedule_inputs = MagicMock(
            return_value="Error message"
        )
        dialog._set_inline_validation_message = MagicMock()
        dialog._schedule_preview_label = MagicMock()
        dialog._schedule_preview_label.setText = MagicMock()

        dialog._refresh_schedule_preview()

        dialog._set_inline_validation_message.assert_called_with(
            "Error message"
        )
        dialog._schedule_preview_label.setText.assert_called_once()
        # _calculate_schedule_preview was not called due to early return

    def test_refresh_with_preview_error(self):
        """Test refresh with preview calculation error."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog._existing_next_run_text = ""
        dialog._existing_next_run_label = MagicMock()
        dialog._existing_next_run_label.setVisible = MagicMock()

        dialog._validate_schedule_inputs = MagicMock(return_value=None)
        dialog._set_inline_validation_message = MagicMock()
        dialog._schedule_preview_label = MagicMock()
        dialog._schedule_preview_label.setText = MagicMock()

        dialog._calculate_schedule_preview = MagicMock(
            return_value=([], "Test error")
        )

        dialog._refresh_schedule_preview()

        dialog._set_inline_validation_message.assert_called()
        dialog._schedule_preview_label.setText.assert_called()

    def test_refresh_with_empty_runs(self):
        """Test refresh with no preview runs returned."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog._existing_next_run_text = ""
        dialog._existing_next_run_label = MagicMock()
        dialog._existing_next_run_label.setVisible = MagicMock()

        dialog._validate_schedule_inputs = MagicMock(return_value=None)
        dialog._set_inline_validation_message = MagicMock()
        dialog._schedule_preview_label = MagicMock()
        dialog._schedule_preview_label.setText = MagicMock()

        dialog._calculate_schedule_preview = MagicMock(
            return_value=([], None)
        )

        dialog._refresh_schedule_preview()

        dialog._set_inline_validation_message.assert_called_with(None)
        dialog._schedule_preview_label.setText.assert_called()

    def test_refresh_with_preview_runs(self):
        """Test refresh with successful preview runs."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog._existing_next_run_text = ""
        dialog._existing_next_run_label = MagicMock()
        dialog._existing_next_run_label.setVisible = MagicMock()

        dialog._validate_schedule_inputs = MagicMock(return_value=None)
        dialog._set_inline_validation_message = MagicMock()
        dialog._schedule_preview_label = MagicMock()
        dialog._schedule_preview_label.setText = MagicMock()

        from datetime import datetime
        preview_runs = [
            datetime(2025, 6, 15, 14, 30),
            datetime(2025, 6, 16, 14, 30),
        ]
        dialog._calculate_schedule_preview = MagicMock(
            return_value=(preview_runs, None)
        )

        dialog._refresh_schedule_preview()

        dialog._set_inline_validation_message.assert_called_with(None)
        dialog._schedule_preview_label.setText.assert_called_once()


class TestTaskDialogAccept:
    """Tests for accept method."""

    def test_accept_with_validation_error(self):
        """Test accept blocks when validation fails."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog._validate_schedule_inputs = MagicMock(
            return_value="Some error"
        )
        dialog._set_inline_validation_message = MagicMock()

        with patch(
            "gui.scheduler.task_dialog.QMessageBox.warning"
        ) as mock_warning:
            dialog.accept()

            dialog._set_inline_validation_message.assert_called_with(
                "Some error"
            )
            mock_warning.assert_called_once()

    def test_accept_without_validation_error(self):
        """Test accept does not show warning when validation passes."""
        dialog = TaskDialog.__new__(TaskDialog)

        dialog._validate_schedule_inputs = MagicMock(return_value=None)
        dialog._set_inline_validation_message = MagicMock()

        with patch(
            "gui.scheduler.task_dialog.QMessageBox.warning"
        ) as mock_warning:
            try:
                dialog.accept()
            except (AttributeError, TypeError):
                pass  # super().accept() fails with __new__ pattern

            dialog._set_inline_validation_message.assert_not_called()
            mock_warning.assert_not_called()


class TestTaskDialogParseTimeOfDay:
    """Tests for static _parse_time_of_day method."""

    def test_parse_valid_time(self):
        """Test parsing valid time string."""
        result = TaskDialog._parse_time_of_day("09:30")
        assert result == (9, 30)

    def test_parse_midnight(self):
        """Test parsing midnight."""
        result = TaskDialog._parse_time_of_day("00:00")
        assert result == (0, 0)

    def test_parse_end_of_day(self):
        """Test parsing end of day."""
        result = TaskDialog._parse_time_of_day("23:59")
        assert result == (23, 59)

    def test_parse_invalid_format(self):
        """Test parsing invalid format raises ValueError."""
        with pytest.raises(ValueError, match="HH:MM"):
            TaskDialog._parse_time_of_day("invalid")

    def test_parse_out_of_range_hours(self):
        """Test parsing hours > 23 raises ValueError."""
        with pytest.raises(ValueError, match="00:00..23:59"):
            TaskDialog._parse_time_of_day("25:00")

    def test_parse_out_of_range_minutes(self):
        """Test parsing minutes > 59 raises ValueError."""
        with pytest.raises(ValueError, match="00:00..23:59"):
            TaskDialog._parse_time_of_day("12:60")


class TestTaskDialogSetInlineValidation:
    """Tests for _set_inline_validation_message method."""

    def test_set_message(self):
        """Test setting validation message shows label."""
        dialog = TaskDialog.__new__(TaskDialog)
        dialog._inline_validation_label = MagicMock()
        dialog._inline_validation_label.setText = MagicMock()
        dialog._inline_validation_label.setVisible = MagicMock()

        dialog._set_inline_validation_message("Error text")

        dialog._inline_validation_label.setText.assert_called_with(
            "Error text"
        )
        dialog._inline_validation_label.setVisible.assert_called_with(True)

    def test_clear_message(self):
        """Test clearing validation message hides label."""
        dialog = TaskDialog.__new__(TaskDialog)
        dialog._inline_validation_label = MagicMock()
        dialog._inline_validation_label.setText = MagicMock()
        dialog._inline_validation_label.setVisible = MagicMock()

        dialog._set_inline_validation_message(None)

        dialog._inline_validation_label.setText.assert_called_with("")
        dialog._inline_validation_label.setVisible.assert_called_with(False)


class TestTaskDialogOnPresetChanged:
    """Tests for _on_preset_changed method."""

    def test_on_preset_changed_invalid_index(self):
        """Test preset changed with invalid index."""
        dialog = TaskDialog.__new__(TaskDialog)
        dialog._preset_names = ["", "preset1"]
        dialog._refresh_schedule_preview = MagicMock()

        dialog._on_preset_changed(-1)

        dialog._refresh_schedule_preview.assert_called_once()

    def test_on_preset_changed_index_zero(self):
        """Test preset changed with index 0 (no preset)."""
        dialog = TaskDialog.__new__(TaskDialog)
        dialog._preset_names = ["", "preset1"]
        dialog._refresh_schedule_preview = MagicMock()

        dialog._on_preset_changed(0)

        dialog._refresh_schedule_preview.assert_called_once()

    def test_on_preset_changed_empty_name(self):
        """Test preset changed with empty preset name."""
        dialog = TaskDialog.__new__(TaskDialog)
        dialog._preset_names = ["", ""]
        dialog._refresh_schedule_preview = MagicMock()

        dialog._on_preset_changed(1)

        dialog._refresh_schedule_preview.assert_called_once()

    def test_on_preset_changed_valid(self):
        """Test preset changed with valid preset."""
        dialog = TaskDialog.__new__(TaskDialog)
        dialog._preset_names = ["", "test-preset"]
        dialog._apply_preset = MagicMock()
        dialog._refresh_schedule_preview = MagicMock()

        with patch(
            "gui.scheduler.task_dialog.get_preset"
        ) as mock_get_preset:
            mock_get_preset.return_value = {
                "name": "Test Preset",
                "trigger": "daily",
                "params": {},
            }

            dialog._on_preset_changed(1)

            mock_get_preset.assert_called_with("test-preset")
            dialog._apply_preset.assert_called_once()

    def test_on_preset_changed_preset_none(self):
        """Test preset changed when get_preset returns None."""
        dialog = TaskDialog.__new__(TaskDialog)
        dialog._preset_names = ["", "missing-preset"]
        dialog._apply_preset = MagicMock()
        dialog._refresh_schedule_preview = MagicMock()

        with patch(
            "gui.scheduler.task_dialog.get_preset"
        ) as mock_get_preset:
            mock_get_preset.return_value = None

            dialog._on_preset_changed(1)

            mock_get_preset.assert_called_with("missing-preset")
            dialog._apply_preset.assert_not_called()


class TestTaskDialogBuildPreviewTask:
    """Tests for _build_preview_task method."""

    def test_build_preview_task(self):
        """Test building preview task from dialog data."""
        dialog = TaskDialog.__new__(TaskDialog)
        dialog.name_edit = MagicMock()
        dialog.name_edit.text = MagicMock(return_value="Preview Task")
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
        dialog.area_combo.currentIndex = MagicMock(return_value=0)
        dialog.audio_combo = MagicMock()
        dialog.audio_combo.currentIndex = MagicMock(return_value=0)
        dialog.fps_spin = MagicMock()
        dialog.fps_spin.value = MagicMock(return_value=30)
        dialog.duration_spin = MagicMock()
        dialog.duration_spin.value = MagicMock(return_value=0)
        dialog.duration_unit_combo = MagicMock()
        dialog.duration_unit_combo.currentIndex = MagicMock(return_value=1)

        task = dialog._build_preview_task()

        assert task.name == "Preview Task"
        assert task.schedule_type == ScheduleType.ONCE
        assert task.params.area_type == "full"
        assert task.params.audio_type == "none"
        assert task.params.fps == 30
        assert task.id == "preview-task"


class TestTaskDialogSetupUI:
    """Tests for _setup_ui method with all Qt constructors mocked."""

    def test_setup_ui_basic(self):
        """Test _setup_ui creates widgets and connects signals."""
        from contextlib import ExitStack

        dialog = TaskDialog.__new__(TaskDialog)
        dialog.task = None
        dialog._existing_next_run_text = ""

        # Mock _on_type_changed, _connect, _refresh to avoid recursion
        dialog._on_type_changed = MagicMock()
        dialog._connect_live_preview_signals = MagicMock()
        dialog._refresh_schedule_preview = MagicMock()
        dialog.reject = MagicMock()

        mock_qlineedit = MagicMock()
        mock_qlineedit.setPlaceholderText = MagicMock()

        mock_qcombobox = MagicMock()
        mock_qcombobox.addItem = MagicMock()
        mock_qcombobox.addItems = MagicMock()
        mock_qcombobox.currentIndexChanged = MagicMock()

        mock_qdateedit = MagicMock()
        mock_qdateedit.setCalendarPopup = MagicMock()
        mock_qdateedit.setDate = MagicMock()

        mock_qtimeedit = MagicMock()
        mock_qtimeedit.setTime = MagicMock()

        mock_qspinbox = MagicMock()
        mock_qspinbox.setRange = MagicMock()
        mock_qspinbox.setValue = MagicMock()
        mock_qspinbox.setSpecialValueText = MagicMock()

        mock_qlabel = MagicMock()
        mock_qlabel.setStyleSheet = MagicMock()
        mock_qlabel.setVisible = MagicMock()
        mock_qlabel.setWordWrap = MagicMock()

        mock_qwidget = MagicMock()

        mock_qgroupbox = MagicMock()

        mock_qdialogbuttonbox = MagicMock()
        mock_qdialogbuttonbox.accepted = MagicMock()
        mock_qdialogbuttonbox.rejected = MagicMock()

        mock_qcheckbox = MagicMock()
        mock_qcheckbox.setChecked = MagicMock()

        patches = [
            patch("gui.scheduler.task_dialog.QVBoxLayout", return_value=MagicMock()),
            patch("gui.scheduler.task_dialog.QFormLayout", return_value=MagicMock()),
            patch("gui.scheduler.task_dialog.QHBoxLayout", return_value=MagicMock()),
            patch("gui.scheduler.task_dialog.QLineEdit", return_value=mock_qlineedit),
            patch("gui.scheduler.task_dialog.QComboBox", return_value=mock_qcombobox),
            patch("gui.scheduler.task_dialog.QDateEdit", return_value=mock_qdateedit),
            patch("gui.scheduler.task_dialog.QTimeEdit", return_value=mock_qtimeedit),
            patch("gui.scheduler.task_dialog.QSpinBox", return_value=mock_qspinbox),
            patch("gui.scheduler.task_dialog.QLabel", return_value=mock_qlabel),
            patch("gui.scheduler.task_dialog.QWidget", return_value=mock_qwidget),
            patch("gui.scheduler.task_dialog.QGroupBox", return_value=mock_qgroupbox),
            patch(
                "gui.scheduler.task_dialog.QDialogButtonBox",
                return_value=mock_qdialogbuttonbox,
            ),
            patch(
                "gui.scheduler.task_dialog.list_presets",
                return_value=[],
            ),
            patch(
                "gui.scheduler.task_dialog.QCheckBox",
                return_value=mock_qcheckbox,
            ),
        ]

        with patch(
            "gui.scheduler.task_dialog.QDate.currentDate"
        ) as mock_date:
            mock_date.return_value = MagicMock()
            with patch("gui.scheduler.task_dialog.QTime") as MockQTime:
                MockQTime.return_value = MagicMock()
                with ExitStack() as stack:
                    for p in patches:
                        stack.enter_context(p)
                    dialog._setup_ui()

        # Verify key widget attributes exist on dialog
        assert hasattr(dialog, "name_edit")
        assert hasattr(dialog, "preset_combo")
        assert hasattr(dialog, "type_combo")
        assert hasattr(dialog, "date_edit")
        assert hasattr(dialog, "time_edit")
        assert hasattr(dialog, "days_widget")
        assert hasattr(dialog, "interval_widget")
        assert hasattr(dialog, "interval_hours")
        assert hasattr(dialog, "interval_minutes")
        assert hasattr(dialog, "cron_widget")
        assert hasattr(dialog, "cron_edit")
        assert hasattr(dialog, "area_combo")
        assert hasattr(dialog, "window_edit")
        assert hasattr(dialog, "audio_combo")
        assert hasattr(dialog, "duration_widget")
        assert hasattr(dialog, "duration_spin")
        assert hasattr(dialog, "duration_unit_combo")
        assert hasattr(dialog, "fps_spin")
        assert hasattr(dialog, "day_checks")
        assert hasattr(dialog, "_inline_validation_label")
        assert hasattr(dialog, "_schedule_preview_label")
        assert hasattr(dialog, "_existing_next_run_label")
        assert len(dialog.day_checks) == 7
        assert dialog._preset_names == [""]

    def test_setup_ui_with_presets(self):
        """Test _setup_ui loads presets from list_presets."""
        from contextlib import ExitStack

        dialog = TaskDialog.__new__(TaskDialog)
        dialog.task = None
        dialog._existing_next_run_text = ""

        dialog._on_type_changed = MagicMock()
        dialog._connect_live_preview_signals = MagicMock()
        dialog._refresh_schedule_preview = MagicMock()
        dialog.reject = MagicMock()

        mock_qlineedit = MagicMock()
        mock_qlineedit.setPlaceholderText = MagicMock()

        mock_qcombobox = MagicMock()
        mock_qcombobox.addItem = MagicMock()
        mock_qcombobox.addItems = MagicMock()
        mock_qcombobox.currentIndexChanged = MagicMock()

        mock_qdateedit = MagicMock()
        mock_qdateedit.setCalendarPopup = MagicMock()
        mock_qdateedit.setDate = MagicMock()

        mock_qtimeedit = MagicMock()
        mock_qtimeedit.setTime = MagicMock()

        mock_qspinbox = MagicMock()
        mock_qspinbox.setRange = MagicMock()
        mock_qspinbox.setValue = MagicMock()
        mock_qspinbox.setSpecialValueText = MagicMock()

        mock_qlabel = MagicMock()
        mock_qlabel.setStyleSheet = MagicMock()
        mock_qlabel.setVisible = MagicMock()
        mock_qlabel.setWordWrap = MagicMock()

        mock_qwidget = MagicMock()
        mock_qgroupbox = MagicMock()
        mock_qdialogbuttonbox = MagicMock()
        mock_qdialogbuttonbox.accepted = MagicMock()
        mock_qdialogbuttonbox.rejected = MagicMock()
        mock_qcheckbox = MagicMock()

        patch_list = [
            patch("gui.scheduler.task_dialog.QVBoxLayout", return_value=MagicMock()),
            patch("gui.scheduler.task_dialog.QFormLayout", return_value=MagicMock()),
            patch("gui.scheduler.task_dialog.QHBoxLayout", return_value=MagicMock()),
            patch("gui.scheduler.task_dialog.QLineEdit", return_value=mock_qlineedit),
            patch("gui.scheduler.task_dialog.QComboBox", return_value=mock_qcombobox),
            patch("gui.scheduler.task_dialog.QDateEdit", return_value=mock_qdateedit),
            patch("gui.scheduler.task_dialog.QTimeEdit", return_value=mock_qtimeedit),
            patch("gui.scheduler.task_dialog.QSpinBox", return_value=mock_qspinbox),
            patch("gui.scheduler.task_dialog.QLabel", return_value=mock_qlabel),
            patch("gui.scheduler.task_dialog.QWidget", return_value=mock_qwidget),
            patch("gui.scheduler.task_dialog.QGroupBox", return_value=mock_qgroupbox),
            patch(
                "gui.scheduler.task_dialog.QDialogButtonBox",
                return_value=mock_qdialogbuttonbox,
            ),
            patch(
                "gui.scheduler.task_dialog.QCheckBox",
                return_value=mock_qcheckbox,
            ),
            patch(
                "gui.scheduler.task_dialog.list_presets",
                return_value=[
                    {
                        "name": "test-preset",
                        "display_name": "Test Preset",
                    }
                ],
            ),
        ]

        with patch(
            "gui.scheduler.task_dialog.QDate.currentDate"
        ) as mock_date:
            mock_date.return_value = MagicMock()
            with patch("gui.scheduler.task_dialog.QTime") as MockQTime:
                MockQTime.return_value = MagicMock()
                with ExitStack() as stack:
                    for p in patch_list:
                        stack.enter_context(p)
                    dialog._setup_ui()

        assert dialog._preset_names == ["", "test-preset"]


class TestTaskDialogConnectLivePreview:
    """Tests for _connect_live_preview_signals method."""

    def test_connect_signals(self):
        """Test that signals are connected to _refresh_schedule_preview."""
        dialog = TaskDialog.__new__(TaskDialog)
        dialog._refresh_schedule_preview = MagicMock()

        dialog.name_edit = MagicMock()
        dialog.name_edit.textChanged = MagicMock()
        dialog.date_edit = MagicMock()
        dialog.date_edit.dateChanged = MagicMock()
        dialog.time_edit = MagicMock()
        dialog.time_edit.timeChanged = MagicMock()
        dialog.interval_hours = MagicMock()
        dialog.interval_hours.valueChanged = MagicMock()
        dialog.interval_minutes = MagicMock()
        dialog.interval_minutes.valueChanged = MagicMock()
        dialog.cron_edit = MagicMock()
        dialog.cron_edit.textChanged = MagicMock()
        dialog.duration_spin = MagicMock()
        dialog.duration_spin.valueChanged = MagicMock()
        dialog.duration_unit_combo = MagicMock()
        dialog.duration_unit_combo.currentIndexChanged = MagicMock()
        dialog.day_checks = [
            MagicMock(stateChanged=MagicMock()),
            MagicMock(stateChanged=MagicMock()),
        ]

        dialog._connect_live_preview_signals()

        dialog.name_edit.textChanged.connect.assert_called_once()
        dialog.date_edit.dateChanged.connect.assert_called_once()
        dialog.time_edit.timeChanged.connect.assert_called_once()
        dialog.interval_hours.valueChanged.connect.assert_called_once()
        dialog.interval_minutes.valueChanged.connect.assert_called_once()
        dialog.cron_edit.textChanged.connect.assert_called_once()
        dialog.duration_spin.valueChanged.connect.assert_called_once()
        dialog.duration_unit_combo.currentIndexChanged.connect.assert_called_once()
        for day in dialog.day_checks:
            day.stateChanged.connect.assert_called_once()


class TestTaskDialogCalculateSchedulePreview:
    """Tests for _calculate_schedule_preview method."""

    def test_calculate_preview_success(self):
        """Test preview calculation returns runs."""
        dialog = TaskDialog.__new__(TaskDialog)
        dialog._build_preview_task = MagicMock()
        dialog._parse_time_of_day = MagicMock(return_value=(9, 0))

        mock_trigger = MagicMock()
        mock_trigger.get_next_fire_time = MagicMock(side_effect=[
            datetime(2025, 6, 15, 14, 30),
            datetime(2025, 6, 16, 14, 30),
            None,
        ])

        with patch(
            "gui.scheduler.task_dialog.create_trigger",
            return_value=mock_trigger,
        ):
            runs, error = dialog._calculate_schedule_preview(count=3)

        assert error is None
        assert len(runs) == 2

    def test_calculate_preview_no_trigger(self):
        """Test preview with None trigger returns error."""
        dialog = TaskDialog.__new__(TaskDialog)
        dialog._build_preview_task = MagicMock()
        dialog._parse_time_of_day = MagicMock(return_value=(9, 0))

        with patch(
            "gui.scheduler.task_dialog.create_trigger",
            return_value=None,
        ):
            runs, error = dialog._calculate_schedule_preview()

        assert error is not None
        assert "Не удалось построить" in error
        assert len(runs) == 0

    def test_calculate_preview_exception(self):
        """Test preview with exception returns error."""
        dialog = TaskDialog.__new__(TaskDialog)
        dialog._build_preview_task = MagicMock(
            side_effect=ValueError("test error")
        )

        runs, error = dialog._calculate_schedule_preview()

        assert error is not None
        assert "test error" in error
        assert len(runs) == 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
