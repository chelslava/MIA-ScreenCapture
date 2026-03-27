"""
Тесты для модуля планировщика задач
===================================

Проверяет функциональность TaskScheduler, ScheduleTask и RecordingParams.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from scheduler.task_scheduler import (
    RecordingParams,
    ScheduleTask,
    ScheduleType,
    TaskScheduler,
)


class TestRecordingParams:
    """Тесты для RecordingParams dataclass."""

    def test_default_values(self):
        """Проверка значений по умолчанию."""
        params = RecordingParams()

        assert params.area_type == "full"
        assert params.window_title is None
        assert params.rect_coords is None
        assert params.audio_type == "none"
        assert params.output_path is None
        assert params.fps == 30
        assert params.codec == "libx264"
        assert params.bitrate == "2M"
        assert params.duration is None

    def test_custom_values(self):
        """Проверка пользовательских значений."""
        params = RecordingParams(
            area_type="rect",
            rect_coords=[100, 100, 800, 600],
            audio_type="mic",
            fps=60,
            codec="h264",
            bitrate="5M",
            duration=300,
        )

        assert params.area_type == "rect"
        assert params.rect_coords == [100, 100, 800, 600]
        assert params.audio_type == "mic"
        assert params.fps == 60
        assert params.codec == "h264"
        assert params.bitrate == "5M"
        assert params.duration == 300

    def test_to_dict(self):
        """Проверка преобразования в словарь."""
        params = RecordingParams(
            area_type="window", window_title="Test Window", fps=60
        )

        data = params.to_dict()

        assert isinstance(data, dict)
        assert data["area_type"] == "window"
        assert data["window_title"] == "Test Window"
        assert data["fps"] == 60

    def test_from_dict(self):
        """Проверка создания из словаря."""
        data = {
            "area_type": "rect",
            "rect_coords": [0, 0, 1920, 1080],
            "fps": 60,
            "extra_field": "ignored",
        }

        params = RecordingParams.from_dict(data)

        assert params.area_type == "rect"
        assert params.rect_coords == [0, 0, 1920, 1080]
        assert params.fps == 60
        # Лишние поля должны игнорироваться
        assert not hasattr(params, "extra_field")

    def test_from_dict_empty(self):
        """Проверка создания из пустого словаря."""
        params = RecordingParams.from_dict({})

        assert params.area_type == "full"
        assert params.fps == 30


class TestScheduleType:
    """Тесты для ScheduleType enum."""

    def test_values(self):
        """Проверка значений enum."""
        assert ScheduleType.ONCE.value == "once"
        assert ScheduleType.DAILY.value == "daily"
        assert ScheduleType.WEEKLY.value == "weekly"
        assert ScheduleType.INTERVAL.value == "interval"
        assert ScheduleType.CRON.value == "cron"

    def test_from_string(self):
        """Проверка создания из строки."""
        assert ScheduleType("once") == ScheduleType.ONCE
        assert ScheduleType("daily") == ScheduleType.DAILY
        assert ScheduleType("cron") == ScheduleType.CRON


class TestScheduleTask:
    """Тесты для ScheduleTask dataclass."""

    def test_default_values(self):
        """Проверка значений по умолчанию."""
        task = ScheduleTask(
            id="test-001",
            name="Test Task",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(),
        )

        assert task.id == "test-001"
        assert task.name == "Test Task"
        assert task.schedule_type == ScheduleType.ONCE
        assert task.enabled is True
        assert task.start_time is None
        assert task.time_of_day is None
        assert task.days_of_week is None
        assert task.interval_minutes is None
        assert task.interval_hours is None
        assert task.last_run is None
        assert task.next_run is None
        assert task.run_count == 0

    def test_to_dict(self):
        """Проверка преобразования в словарь."""
        start_time = datetime(2026, 3, 18, 12, 0, 0)
        task = ScheduleTask(
            id="test-001",
            name="Test Task",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(fps=60),
            start_time=start_time,
            run_count=5,
        )

        data = task.to_dict()

        assert data["id"] == "test-001"
        assert data["name"] == "Test Task"
        assert data["schedule_type"] == "once"
        assert data["params"]["fps"] == 60
        assert data["enabled"] is True
        assert data["start_time"] == start_time.isoformat()
        assert data["run_count"] == 5

    def test_to_dict_with_optional_fields(self):
        """Проверка преобразования с опциональными полями."""
        last_run = datetime(2026, 3, 17, 10, 0, 0)
        next_run = datetime(2026, 3, 18, 10, 0, 0)

        task = ScheduleTask(
            id="test-001",
            name="Test Task",
            schedule_type=ScheduleType.DAILY,
            params=RecordingParams(),
            time_of_day="10:00",
            last_run=last_run,
            next_run=next_run,
        )

        data = task.to_dict()

        assert data["time_of_day"] == "10:00"
        assert data["last_run"] == last_run.isoformat()
        assert data["next_run"] == next_run.isoformat()

    def test_from_dict(self):
        """Проверка создания из словаря."""
        data = {
            "id": "test-002",
            "name": "Restored Task",
            "schedule_type": "weekly",
            "params": {"area_type": "window", "fps": 30},
            "enabled": False,
            "time_of_day": "14:30",
            "days_of_week": [0, 2, 4],
            "run_count": 10,
        }

        task = ScheduleTask.from_dict(data)

        assert task.id == "test-002"
        assert task.name == "Restored Task"
        assert task.schedule_type == ScheduleType.WEEKLY
        assert task.params.area_type == "window"
        assert task.enabled is False
        assert task.time_of_day == "14:30"
        assert task.days_of_week == [0, 2, 4]
        assert task.run_count == 10

    def test_from_dict_with_datetime_fields(self):
        """Проверка создания из словаря с полями datetime."""
        start_time = "2026-03-18T12:00:00"
        last_run = "2026-03-17T10:00:00"

        data = {
            "id": "test-003",
            "name": "Task with dates",
            "schedule_type": "once",
            "params": {},
            "start_time": start_time,
            "last_run": last_run,
        }

        task = ScheduleTask.from_dict(data)

        assert task.start_time == datetime.fromisoformat(start_time)
        assert task.last_run == datetime.fromisoformat(last_run)


class TestTaskScheduler:
    """Тесты для TaskScheduler."""

    def test_init_default(self):
        """Проверка инициализации без пути сохранения."""
        scheduler = TaskScheduler()

        assert scheduler.persist_path is None
        assert scheduler._tasks == {}

    def test_init_with_persist_path(self, tasks_file: Path):
        """Проверка инициализации с путём сохранения."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        assert scheduler.persist_path == tasks_file

    def test_start_scheduler(self, tasks_file: Path):
        """Проверка запуска планировщика."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        scheduler.start()

        assert scheduler._scheduler.running is True

        # Остановка для очистки
        scheduler.stop()

    def test_stop_scheduler(self, tasks_file: Path):
        """Проверка остановки планировщика."""
        scheduler = TaskScheduler(persist_path=tasks_file)
        scheduler.start()

        scheduler.stop()

        assert scheduler._scheduler.running is False

    def test_set_task_callback(self, tasks_file: Path):
        """Проверка установки обратного вызова."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        callback_called = []

        def test_callback(params):
            callback_called.append(params)

        scheduler.set_task_callback(test_callback)

        assert scheduler._on_task_execute == test_callback

    def test_create_task_from_dict_once(self, tasks_file: Path):
        """Проверка создания разовой задачи из словаря."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        data = {
            "name": "One-time recording",
            "trigger": "once",
            "datetime": "2026-03-18T15:00:00",
            "params": {"area_type": "full", "fps": 30},
        }

        task = scheduler.create_task_from_dict(data)

        assert task.name == "One-time recording"
        assert task.schedule_type == ScheduleType.ONCE
        assert task.start_time == datetime.fromisoformat("2026-03-18T15:00:00")
        assert task.params.area_type == "full"

    def test_create_task_from_dict_daily(self, tasks_file: Path):
        """Проверка создания ежедневной задачи из словаря."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        data = {
            "name": "Daily recording",
            "trigger": "daily",
            "time": "09:00",
            "params": {"area_type": "window", "window_title": "Browser"},
        }

        task = scheduler.create_task_from_dict(data)

        assert task.name == "Daily recording"
        assert task.schedule_type == ScheduleType.DAILY
        assert task.time_of_day == "09:00"

    def test_create_task_from_dict_weekly(self, tasks_file: Path):
        """Проверка создания еженедельной задачи из словаря."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        data = {
            "name": "Weekly recording",
            "trigger": "weekly",
            "time": "10:00",
            "day_of_week": "0,2,4",
            "params": {},
        }

        task = scheduler.create_task_from_dict(data)

        assert task.name == "Weekly recording"
        assert task.schedule_type == ScheduleType.WEEKLY
        assert task.time_of_day == "10:00"
        assert task.days_of_week == [0, 2, 4]

    def test_create_task_from_dict_interval(self, tasks_file: Path):
        """Проверка создания интервальной задачи из словаря."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        data = {
            "name": "Interval recording",
            "trigger": "interval",
            "hours": 2,
            "minutes": 30,
            "params": {},
        }

        task = scheduler.create_task_from_dict(data)

        assert task.name == "Interval recording"
        assert task.schedule_type == ScheduleType.INTERVAL
        assert task.interval_hours == 2
        assert task.interval_minutes == 30

    def test_create_task_from_dict_gui_format(self, tasks_file: Path):
        """Проверка создания задачи из GUI-формата payload."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        data = {
            "name": "GUI Task",
            "schedule_type": ScheduleType.WEEKLY,
            "time_of_day": "11:15",
            "days_of_week": [1, 3, 5],
            "area_type": "window",
            "window_title": "Browser",
            "audio_type": "system",
            "fps": 60,
            "duration": 120,
        }

        task = scheduler.create_task_from_dict(data)

        assert task.name == "GUI Task"
        assert task.schedule_type == ScheduleType.WEEKLY
        assert task.time_of_day == "11:15"
        assert task.days_of_week == [1, 3, 5]
        assert task.params.area_type == "window"
        assert task.params.window_title == "Browser"
        assert task.params.audio_type == "system"
        assert task.params.fps == 60
        assert task.params.duration == 120

    def test_create_task_from_dict_start_time_datetime_instance(
        self, tasks_file: Path
    ):
        """Проверка разовой задачи с datetime-объектом из GUI."""
        scheduler = TaskScheduler(persist_path=tasks_file)
        start_time = datetime(2026, 4, 1, 9, 30)
        data = {
            "name": "GUI Once",
            "schedule_type": ScheduleType.ONCE,
            "start_time": start_time,
            "area_type": "full",
        }

        task = scheduler.create_task_from_dict(data)

        assert task.schedule_type == ScheduleType.ONCE
        assert task.start_time == start_time
        assert task.params.area_type == "full"

    def test_add_task(self, tasks_file: Path):
        """Проверка добавления задачи."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        task = ScheduleTask(
            id="test-add",
            name="Test Add",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(),
        )

        result = scheduler.add_task(task)

        assert result is True
        assert "test-add" in scheduler._tasks
        assert scheduler._tasks["test-add"] == task

    def test_add_duplicate_task(self, tasks_file: Path):
        """Проверка добавления дубликата задачи."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        task1 = ScheduleTask(
            id="duplicate",
            name="Task 1",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(),
        )

        task2 = ScheduleTask(
            id="duplicate",
            name="Task 2",
            schedule_type=ScheduleType.DAILY,
            params=RecordingParams(),
        )

        scheduler.add_task(task1)
        result = scheduler.add_task(task2)

        # Дубликат не должен добавляться, оригинал сохраняется
        assert result is False
        assert scheduler._tasks["duplicate"].name == "Task 1"

    def test_remove_task(self, tasks_file: Path):
        """Проверка удаления задачи."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        task = ScheduleTask(
            id="to-remove",
            name="To Remove",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(),
        )

        scheduler.add_task(task)
        result = scheduler.remove_task("to-remove")

        assert result is True
        assert "to-remove" not in scheduler._tasks

    def test_remove_nonexistent_task(self, tasks_file: Path):
        """Проверка удаления несуществующей задачи."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        result = scheduler.remove_task("nonexistent")

        assert result is False

    def test_update_task(self, tasks_file: Path):
        """Проверка обновления задачи."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        task = ScheduleTask(
            id="to-update",
            name="Original Name",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(fps=30),
        )

        scheduler.add_task(task)

        # Обновление
        updated_task = ScheduleTask(
            id="to-update",
            name="Updated Name",
            schedule_type=ScheduleType.DAILY,
            params=RecordingParams(fps=60),
        )

        result = scheduler.update_task(updated_task)

        assert result is True
        assert scheduler._tasks["to-update"].name == "Updated Name"
        assert scheduler._tasks["to-update"].params.fps == 60

    def test_enable_task(self, tasks_file: Path):
        """Проверка включения/выключения задачи."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        task = ScheduleTask(
            id="toggle-test",
            name="Toggle Test",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(),
            enabled=True,
        )

        scheduler.add_task(task)

        # Выключение
        result = scheduler.enable_task("toggle-test", False)

        assert result is True
        assert scheduler._tasks["toggle-test"].enabled is False

        # Включение
        result = scheduler.enable_task("toggle-test", True)

        assert result is True
        assert scheduler._tasks["toggle-test"].enabled is True

    def test_get_all_tasks(self, tasks_file: Path):
        """Проверка получения всех задач."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        task1 = ScheduleTask(
            id="task-1",
            name="Task 1",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(),
        )

        task2 = ScheduleTask(
            id="task-2",
            name="Task 2",
            schedule_type=ScheduleType.DAILY,
            params=RecordingParams(),
        )

        scheduler.add_task(task1)
        scheduler.add_task(task2)

        tasks = scheduler.get_all_tasks()

        assert len(tasks) == 2
        assert any(t.id == "task-1" for t in tasks)
        assert any(t.id == "task-2" for t in tasks)

    def test_get_task_by_id(self, tasks_file: Path):
        """Проверка получения задачи по ID."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        task = ScheduleTask(
            id="specific-task",
            name="Specific Task",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(),
        )

        scheduler.add_task(task)

        found_task = scheduler.get_task("specific-task")

        assert found_task is not None
        assert found_task.id == "specific-task"

    def test_get_nonexistent_task(self, tasks_file: Path):
        """Проверка получения несуществующей задачи."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        found_task = scheduler.get_task("nonexistent")

        assert found_task is None

    def test_persist_tasks(self, tasks_file: Path):
        """Проверка сохранения задач в файл."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        task = ScheduleTask(
            id="persist-test",
            name="Persist Test",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(fps=60),
        )

        scheduler.add_task(task)
        scheduler._save_tasks()

        # Проверка файла
        with open(tasks_file, encoding="utf-8") as f:
            data = json.load(f)

        # Данные сохраняются в формате {'tasks': [...], 'last_updated': ...}
        assert "tasks" in data
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["id"] == "persist-test"
        assert data["tasks"][0]["params"]["fps"] == 60

    def test_save_tasks_uses_atomic_replace(
        self, tasks_file: Path, monkeypatch
    ):
        """Проверка атомарной записи задач через os.replace."""
        scheduler = TaskScheduler(persist_path=tasks_file)
        replace_calls: list[tuple[Path, Path]] = []

        def fake_replace(src, dst):
            replace_calls.append((Path(src), Path(dst)))
            Path(dst).write_text(
                Path(src).read_text(encoding="utf-8"), encoding="utf-8"
            )

        monkeypatch.setattr(
            "scheduler.task_scheduler.os.replace", fake_replace
        )

        task = ScheduleTask(
            id="atomic-save",
            name="Atomic Save",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(),
        )
        scheduler.add_task(task)

        assert replace_calls
        src, dst = replace_calls[0]
        assert src.parent == dst.parent
        assert src != dst
        assert dst == tasks_file

    def test_save_tasks_keeps_existing_file_on_replace_error(
        self, tasks_file: Path, monkeypatch
    ):
        """Проверка сохранения старого файла при ошибке атомарной записи."""
        tasks_file.write_text(
            json.dumps({"tasks": [{"id": "original"}]}), encoding="utf-8"
        )
        scheduler = TaskScheduler(persist_path=tasks_file)

        def failing_replace(src, dst):
            raise OSError("replace failed")

        monkeypatch.setattr(
            "scheduler.task_scheduler.os.replace", failing_replace
        )

        task = ScheduleTask(
            id="failed-save",
            name="Failed Save",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(),
        )
        scheduler.add_task(task)

        data = json.loads(tasks_file.read_text(encoding="utf-8"))
        assert data == {"tasks": [{"id": "original"}]}

    def test_load_tasks_on_init(self, tasks_file: Path):
        """Проверка загрузки задач при инициализации."""
        # Создание файла с задачами в правильном формате
        tasks_data = {
            "tasks": [
                {
                    "id": "loaded-task",
                    "name": "Loaded Task",
                    "schedule_type": "daily",
                    "params": {"fps": 30},
                    "enabled": True,
                    "time_of_day": "08:00",
                }
            ]
        }

        with open(tasks_file, "w", encoding="utf-8") as f:
            json.dump(tasks_data, f)

        # Инициализация планировщика
        scheduler = TaskScheduler(persist_path=tasks_file)

        assert "loaded-task" in scheduler._tasks
        assert scheduler._tasks["loaded-task"].name == "Loaded Task"


class TestTaskSchedulerIntegration:
    """Интеграционные тесты для планировщика."""

    def test_full_task_lifecycle(self, tasks_file: Path):
        """Проверка полного жизненного цикла задачи."""
        scheduler = TaskScheduler(persist_path=tasks_file)
        scheduler.start()

        try:
            # Создание задачи
            data = {
                "name": "Lifecycle Test",
                "trigger": "once",
                "datetime": (datetime.now() + timedelta(hours=1)).isoformat(),
                "params": {"area_type": "full"},
            }

            task = scheduler.create_task_from_dict(data)

            # Добавление
            assert scheduler.add_task(task) is True

            # Получение
            found = scheduler.get_task(task.id)
            assert found is not None

            # Обновление
            task.name = "Updated Lifecycle Test"
            assert scheduler.update_task(task) is True

            # Выключение
            assert scheduler.enable_task(task.id, False) is True
            assert scheduler.get_task(task.id).enabled is False

            # Удаление
            assert scheduler.remove_task(task.id) is True
            assert scheduler.get_task(task.id) is None

        finally:
            scheduler.stop()

    def test_multiple_tasks_management(self, tasks_file: Path):
        """Проверка управления несколькими задачами."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        # Добавление нескольких задач
        for i in range(5):
            task = ScheduleTask(
                id=f"multi-task-{i}",
                name=f"Multi Task {i}",
                schedule_type=ScheduleType.DAILY,
                params=RecordingParams(),
                time_of_day=f"{10 + i}:00",
            )
            scheduler.add_task(task)

        # Проверка количества
        all_tasks = scheduler.get_all_tasks()
        assert len(all_tasks) == 5

        # Удаление половины
        for i in range(0, 5, 2):
            scheduler.remove_task(f"multi-task-{i}")

        remaining = scheduler.get_all_tasks()
        assert len(remaining) == 2


class TestCronSchedule:
    """Тесты для cron-расписания."""

    def test_cron_expression_in_task(self):
        """Проверка cron-выражения в задаче."""
        task = ScheduleTask(
            id="cron-task",
            name="Cron Task",
            schedule_type=ScheduleType.CRON,
            params=RecordingParams(),
            cron_expression="0 9 * * 1-5",
        )

        assert task.cron_expression == "0 9 * * 1-5"
        assert task.schedule_type == ScheduleType.CRON

    def test_cron_task_to_dict(self):
        """Проверка преобразования cron-задачи в словарь."""
        task = ScheduleTask(
            id="cron-task",
            name="Cron Task",
            schedule_type=ScheduleType.CRON,
            params=RecordingParams(fps=60),
            cron_expression="30 14 * * *",
        )

        data = task.to_dict()

        assert data["schedule_type"] == "cron"
        assert data["cron_expression"] == "30 14 * * *"

    def test_cron_task_from_dict(self):
        """Проверка создания cron-задачи из словаря."""
        data = {
            "id": "cron-restored",
            "name": "Restored Cron Task",
            "schedule_type": "cron",
            "params": {"fps": 30},
            "enabled": True,
            "cron_expression": "0 18 * * 5",
        }

        task = ScheduleTask.from_dict(data)

        assert task.schedule_type == ScheduleType.CRON
        assert task.cron_expression == "0 18 * * 5"

    def test_create_cron_task_from_dict(self, tasks_file: Path):
        """Проверка создания cron-задачи из данных API."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        data = {
            "name": "Weekly report recording",
            "trigger": "cron",
            "cron_expression": "0 9 * * 1",
            "params": {"area_type": "full"},
        }

        task = scheduler.create_task_from_dict(data)

        assert task.name == "Weekly report recording"
        assert task.schedule_type == ScheduleType.CRON
        assert task.cron_expression == "0 9 * * 1"

    def test_cron_trigger_creation(self, tasks_file: Path):
        """Проверка создания триггера для cron-задачи."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        task = ScheduleTask(
            id="cron-trigger-test",
            name="Cron Trigger Test",
            schedule_type=ScheduleType.CRON,
            params=RecordingParams(),
            cron_expression="0 12 * * *",
        )

        trigger = scheduler._create_trigger(task)

        assert trigger is not None
        # Проверяем, что триггер является CronTrigger
        from apscheduler.triggers.cron import CronTrigger

        assert isinstance(trigger, CronTrigger)

    def test_cron_task_without_expression(self, tasks_file: Path):
        """Проверка cron-задачи без выражения."""
        scheduler = TaskScheduler(persist_path=tasks_file)

        task = ScheduleTask(
            id="cron-no-expr",
            name="Cron No Expression",
            schedule_type=ScheduleType.CRON,
            params=RecordingParams(),
        )

        trigger = scheduler._create_trigger(task)

        # Без выражения триггер не должен создаваться
        assert trigger is None

    def test_cron_task_persistence(self, tasks_file: Path):
        """Проверка сохранения и загрузки cron-задачи."""
        scheduler1 = TaskScheduler(persist_path=tasks_file)

        task = ScheduleTask(
            id="persist-cron",
            name="Persist Cron Task",
            schedule_type=ScheduleType.CRON,
            params=RecordingParams(fps=60),
            cron_expression="15 10 * * 1-5",
        )

        scheduler1.add_task(task)
        scheduler1._save_tasks()

        # Создаём новый планировщик для загрузки
        scheduler2 = TaskScheduler(persist_path=tasks_file)

        loaded_task = scheduler2.get_task("persist-cron")
        assert loaded_task is not None
        assert loaded_task.cron_expression == "15 10 * * 1-5"
        assert loaded_task.schedule_type == ScheduleType.CRON
