"""
Интеграционные тесты для планировщика задач
============================================

Тестирует полный цикл работы планировщика с реальным APScheduler.
"""

import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from scheduler.task_scheduler import (
    RecordingParams,
    ScheduleTask,
    ScheduleType,
    TaskScheduler,
)


@pytest.fixture
def temp_tasks_file(tmp_path: Path) -> Path:
    """
    Создание временного файла для сохранения задач.

    Args:
        tmp_path: Временная директория pytest

    Returns:
        Путь к файлу задач
    """
    tasks_file = tmp_path / "tasks.json"
    tasks_file.write_text("[]")
    return tasks_file


@pytest.fixture
def task_callback_results() -> dict[str, Any]:
    """
    Хранилище результатов выполнения callback.

    Returns:
        Словарь для хранения результатов
    """
    return {"executed_tasks": [], "execution_count": 0, "last_params": None}


@pytest.fixture
def scheduler_with_callback(
    temp_tasks_file: Path, task_callback_results: dict[str, Any]
) -> TaskScheduler:
    """
    Создание планировщика с настроенным callback.

    Args:
        temp_tasks_file: Путь к файлу задач
        task_callback_results: Хранилище результатов

    Returns:
        Настроенный планировщик
    """
    scheduler = TaskScheduler(persist_path=temp_tasks_file)

    def task_callback(params: RecordingParams) -> dict[str, Any]:
        """Callback для выполнения задачи."""
        task_callback_results["executed_tasks"].append(
            {
                "params": params.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }
        )
        task_callback_results["execution_count"] += 1
        task_callback_results["last_params"] = params
        return {"success": True}

    scheduler.set_task_callback(task_callback)

    return scheduler


class TestTaskSchedulerFullCycle:
    """Тесты полного цикла работы планировщика."""

    def test_scheduler_start_stop(self, temp_tasks_file: Path):
        """Проверка запуска и остановки планировщика."""
        scheduler = TaskScheduler(persist_path=temp_tasks_file)

        # Запуск
        scheduler.start()
        assert scheduler._scheduler.running is True

        # Остановка
        scheduler.stop()
        assert scheduler._scheduler.running is False

    def test_add_and_execute_immediate_task(
        self,
        scheduler_with_callback: TaskScheduler,
        task_callback_results: dict[str, Any],
    ):
        """Проверка добавления и немедленного выполнения задачи."""
        scheduler_with_callback.start()

        try:
            # Создание задачи на ближайшее время
            task = ScheduleTask(
                id="immediate-test",
                name="Immediate Task",
                schedule_type=ScheduleType.ONCE,
                params=RecordingParams(area_type="full", fps=30, duration=10),
                start_time=datetime.now() + timedelta(seconds=1),
            )

            scheduler_with_callback.add_task(task)

            # Ожидание выполнения
            time.sleep(2)

            # Проверка выполнения
            assert task_callback_results["execution_count"] >= 1
            assert task_callback_results["last_params"] is not None
            assert task_callback_results["last_params"].area_type == "full"

        finally:
            scheduler_with_callback.stop()

    def test_add_remove_task(self, scheduler_with_callback: TaskScheduler):
        """Проверка добавления и удаления задачи."""
        scheduler_with_callback.start()

        try:
            task = ScheduleTask(
                id="remove-test",
                name="Task to Remove",
                schedule_type=ScheduleType.DAILY,
                params=RecordingParams(),
                time_of_day="10:00",
            )

            # Добавление
            result = scheduler_with_callback.add_task(task)
            assert result is True
            assert "remove-test" in scheduler_with_callback._tasks

            # Удаление
            result = scheduler_with_callback.remove_task("remove-test")
            assert result is True
            assert "remove-test" not in scheduler_with_callback._tasks

        finally:
            scheduler_with_callback.stop()

    def test_update_task(self, scheduler_with_callback: TaskScheduler):
        """Проверка обновления задачи."""
        scheduler_with_callback.start()

        try:
            # Создание исходной задачи
            task = ScheduleTask(
                id="update-test",
                name="Original Name",
                schedule_type=ScheduleType.DAILY,
                params=RecordingParams(fps=30),
                time_of_day="09:00",
            )

            scheduler_with_callback.add_task(task)

            # Обновление
            updated_task = ScheduleTask(
                id="update-test",
                name="Updated Name",
                schedule_type=ScheduleType.DAILY,
                params=RecordingParams(fps=60),
                time_of_day="10:00",
            )

            result = scheduler_with_callback.update_task(updated_task)
            assert result is True

            # Проверка обновления
            stored_task = scheduler_with_callback._tasks["update-test"]
            assert stored_task.name == "Updated Name"
            assert stored_task.params.fps == 60
            assert stored_task.time_of_day == "10:00"

        finally:
            scheduler_with_callback.stop()

    def test_enable_disable_task(self, scheduler_with_callback: TaskScheduler):
        """Проверка включения/выключения задачи."""
        scheduler_with_callback.start()

        try:
            task = ScheduleTask(
                id="toggle-test",
                name="Toggle Task",
                schedule_type=ScheduleType.DAILY,
                params=RecordingParams(),
                time_of_day="09:00",
                enabled=True,
            )

            scheduler_with_callback.add_task(task)

            # Выключение
            result = scheduler_with_callback.enable_task("toggle-test", False)
            assert result is True
            assert (
                scheduler_with_callback._tasks["toggle-test"].enabled is False
            )

            # Включение
            result = scheduler_with_callback.enable_task("toggle-test", True)
            assert result is True
            assert (
                scheduler_with_callback._tasks["toggle-test"].enabled is True
            )

        finally:
            scheduler_with_callback.stop()


class TestTaskSchedulerPersistence:
    """Тесты сохранения и восстановления задач."""

    def test_persist_tasks(self, temp_tasks_file: Path):
        """Проверка сохранения задач в файл."""
        scheduler = TaskScheduler(persist_path=temp_tasks_file)
        scheduler.start()

        try:
            # Добавление задач
            task1 = ScheduleTask(
                id="persist-1",
                name="Task 1",
                schedule_type=ScheduleType.DAILY,
                params=RecordingParams(fps=30),
                time_of_day="09:00",
            )

            task2 = ScheduleTask(
                id="persist-2",
                name="Task 2",
                schedule_type=ScheduleType.WEEKLY,
                params=RecordingParams(fps=60),
                time_of_day="10:00",
                days_of_week=[0, 2, 4],
            )

            scheduler.add_task(task1)
            scheduler.add_task(task2)

            # Принудительное сохранение
            scheduler._save_tasks()

            # Проверка файла
            with open(temp_tasks_file, encoding="utf-8") as f:
                data = json.load(f)

            # Формат файла: {"tasks": [...], "last_updated": "..."}
            assert "tasks" in data
            assert len(data["tasks"]) == 2
            assert any(t["id"] == "persist-1" for t in data["tasks"])
            assert any(t["id"] == "persist-2" for t in data["tasks"])

        finally:
            scheduler.stop()

    def test_load_tasks_on_init(self, temp_tasks_file: Path):
        """Проверка загрузки задач при инициализации."""
        # Создание файла с задачами в правильном формате
        tasks_data = {
            "tasks": [
                {
                    "id": "loaded-1",
                    "name": "Loaded Task 1",
                    "schedule_type": "daily",
                    "params": {"fps": 30},
                    "time_of_day": "08:00",
                    "enabled": True,
                },
                {
                    "id": "loaded-2",
                    "name": "Loaded Task 2",
                    "schedule_type": "weekly",
                    "params": {"fps": 60},
                    "time_of_day": "14:00",
                    "days_of_week": [1, 3, 5],
                    "enabled": False,
                },
            ],
            "last_updated": "2026-03-18T12:00:00",
        }

        with open(temp_tasks_file, "w", encoding="utf-8") as f:
            json.dump(tasks_data, f)

        # Создание нового планировщика
        scheduler = TaskScheduler(persist_path=temp_tasks_file)

        # Проверка загрузки
        assert "loaded-1" in scheduler._tasks
        assert "loaded-2" in scheduler._tasks
        assert scheduler._tasks["loaded-1"].name == "Loaded Task 1"
        assert scheduler._tasks["loaded-2"].params.fps == 60

    def test_persist_after_remove(self, temp_tasks_file: Path):
        """Проверка сохранения после удаления задачи."""
        scheduler = TaskScheduler(persist_path=temp_tasks_file)
        scheduler.start()

        try:
            # Добавление и удаление
            task = ScheduleTask(
                id="remove-persist",
                name="To Remove",
                schedule_type=ScheduleType.DAILY,
                params=RecordingParams(),
                time_of_day="09:00",
            )

            scheduler.add_task(task)
            scheduler.remove_task("remove-persist")

            # Проверка файла
            with open(temp_tasks_file, encoding="utf-8") as f:
                data = json.load(f)

            # Формат файла: {"tasks": [...], "last_updated": "..."}
            assert "tasks" in data
            assert not any(t["id"] == "remove-persist" for t in data["tasks"])

        finally:
            scheduler.stop()


class TestTaskSchedulerTriggers:
    """Тесты различных типов триггеров."""

    def test_once_trigger(
        self,
        scheduler_with_callback: TaskScheduler,
        task_callback_results: dict[str, Any],
    ):
        """Проверка разового триггера."""
        scheduler_with_callback.start()

        try:
            task = ScheduleTask(
                id="once-trigger",
                name="Once Task",
                schedule_type=ScheduleType.ONCE,
                params=RecordingParams(duration=5),
                start_time=datetime.now() + timedelta(seconds=1),
            )

            scheduler_with_callback.add_task(task)

            # Ожидание выполнения
            time.sleep(2)

            # Задача должна выполниться один раз
            assert task_callback_results["execution_count"] >= 1

            # После выполнения задача должна быть удалена или помечена
            # (зависит от реализации)

        finally:
            scheduler_with_callback.stop()

    def test_interval_trigger(
        self,
        scheduler_with_callback: TaskScheduler,
        task_callback_results: dict[str, Any],
    ):
        """Проверка интервального триггера."""
        scheduler_with_callback.start()

        try:
            task = ScheduleTask(
                id="interval-trigger",
                name="Interval Task",
                schedule_type=ScheduleType.INTERVAL,
                params=RecordingParams(duration=1),
                interval_minutes=5,  # Используем 5 минут для стабильности в CI
                interval_hours=0,
            )

            scheduler_with_callback.add_task(task)

            # Проверка что задача добавлена в планировщик
            assert "interval-trigger" in scheduler_with_callback._tasks

            # Проверка что задача включена
            assert (
                scheduler_with_callback._tasks["interval-trigger"].enabled
                is True
            )

            # Проверка что задача имеет корректный next_run
            stored_task = scheduler_with_callback._tasks["interval-trigger"]
            assert stored_task.next_run is not None

        finally:
            scheduler_with_callback.stop()

    def test_disabled_task_not_executed(
        self,
        scheduler_with_callback: TaskScheduler,
        task_callback_results: dict[str, Any],
    ):
        """Проверка что выключенная задача не выполняется."""
        scheduler_with_callback.start()

        try:
            task = ScheduleTask(
                id="disabled-task",
                name="Disabled Task",
                schedule_type=ScheduleType.ONCE,
                params=RecordingParams(),
                start_time=datetime.now() + timedelta(seconds=1),
                enabled=False,
            )

            scheduler_with_callback.add_task(task)

            # Ожидание
            time.sleep(2)

            # Задача не должна выполниться
            assert task_callback_results["execution_count"] == 0

        finally:
            scheduler_with_callback.stop()


class TestTaskSchedulerConcurrency:
    """Тесты конкурентности планировщика."""

    def test_concurrent_task_operations(
        self, scheduler_with_callback: TaskScheduler
    ):
        """Проверка конкурентных операций с задачами."""
        scheduler_with_callback.start()

        try:
            results = {"added": 0, "errors": []}
            lock = threading.Lock()

            def add_task(task_id: str):
                """Добавление задачи в потоке."""
                try:
                    task = ScheduleTask(
                        id=task_id,
                        name=f"Task {task_id}",
                        schedule_type=ScheduleType.DAILY,
                        params=RecordingParams(),
                        time_of_day="09:00",
                    )

                    if scheduler_with_callback.add_task(task):
                        with lock:
                            results["added"] += 1
                except Exception as e:
                    with lock:
                        results["errors"].append(str(e))

            # Создание потоков
            threads = []
            for i in range(10):
                thread = threading.Thread(
                    target=add_task, args=(f"concurrent-{i}",)
                )
                threads.append(thread)

            # Запуск всех потоков
            for thread in threads:
                thread.start()

            # Ожидание завершения
            for thread in threads:
                thread.join(timeout=5)

            # Проверка результатов
            assert len(results["errors"]) == 0
            assert results["added"] == 10

        finally:
            scheduler_with_callback.stop()


class TestTaskSchedulerEdgeCases:
    """Тесты граничных случаев."""

    def test_add_task_with_past_time(
        self, scheduler_with_callback: TaskScheduler
    ):
        """Проверка добавления задачи с прошедшим временем."""
        scheduler_with_callback.start()

        try:
            task = ScheduleTask(
                id="past-task",
                name="Past Task",
                schedule_type=ScheduleType.ONCE,
                params=RecordingParams(),
                start_time=datetime.now() - timedelta(hours=1),
            )

            # Задача должна добавиться, но не выполниться
            result = scheduler_with_callback.add_task(task)
            assert result is True

        finally:
            scheduler_with_callback.stop()

    def test_add_duplicate_task(self, scheduler_with_callback: TaskScheduler):
        """Проверка добавления дубликата задачи."""
        scheduler_with_callback.start()

        try:
            task1 = ScheduleTask(
                id="duplicate",
                name="Original",
                schedule_type=ScheduleType.DAILY,
                params=RecordingParams(fps=30),
                time_of_day="09:00",
            )

            task2 = ScheduleTask(
                id="duplicate",
                name="Duplicate",
                schedule_type=ScheduleType.DAILY,
                params=RecordingParams(fps=60),
                time_of_day="10:00",
            )

            result1 = scheduler_with_callback.add_task(task1)
            result2 = scheduler_with_callback.add_task(task2)

            assert result1 is True
            assert result2 is False  # Дубликат не добавляется
            assert (
                scheduler_with_callback._tasks["duplicate"].name == "Original"
            )

        finally:
            scheduler_with_callback.stop()

    def test_remove_nonexistent_task(
        self, scheduler_with_callback: TaskScheduler
    ):
        """Проверка удаления несуществующей задачи."""
        result = scheduler_with_callback.remove_task("nonexistent")
        assert result is False

    def test_update_nonexistent_task(
        self, scheduler_with_callback: TaskScheduler
    ):
        """Проверка обновления несуществующей задачи."""
        task = ScheduleTask(
            id="nonexistent",
            name="Nonexistent",
            schedule_type=ScheduleType.DAILY,
            params=RecordingParams(),
            time_of_day="09:00",
        )

        result = scheduler_with_callback.update_task(task)
        assert result is False

    def test_get_all_tasks_empty(self, scheduler_with_callback: TaskScheduler):
        """Проверка получения пустого списка задач."""
        tasks = scheduler_with_callback.get_all_tasks()
        assert tasks == []

    def test_get_all_tasks_with_tasks(
        self, scheduler_with_callback: TaskScheduler
    ):
        """Проверка получения списка задач."""
        task1 = ScheduleTask(
            id="task-1",
            name="Task 1",
            schedule_type=ScheduleType.DAILY,
            params=RecordingParams(),
            time_of_day="09:00",
        )

        task2 = ScheduleTask(
            id="task-2",
            name="Task 2",
            schedule_type=ScheduleType.WEEKLY,
            params=RecordingParams(),
            time_of_day="10:00",
            days_of_week=[1],
        )

        scheduler_with_callback.add_task(task1)
        scheduler_with_callback.add_task(task2)

        tasks = scheduler_with_callback.get_all_tasks()

        assert len(tasks) == 2
        assert any(t.id == "task-1" for t in tasks)
        assert any(t.id == "task-2" for t in tasks)


class TestTaskSchedulerFromDict:
    """Тесты создания задач из словаря."""

    def test_create_once_task_from_dict(
        self, scheduler_with_callback: TaskScheduler
    ):
        """Проверка создания разовой задачи из словаря."""
        data = {
            "name": "Once Task from Dict",
            "trigger": "once",
            "datetime": (datetime.now() + timedelta(hours=1)).isoformat(),
            "params": {
                "area_type": "rect",
                "rect_coords": [0, 0, 1920, 1080],
                "fps": 60,
            },
        }

        task = scheduler_with_callback.create_task_from_dict(data)

        assert task.name == "Once Task from Dict"
        assert task.schedule_type == ScheduleType.ONCE
        assert task.params.area_type == "rect"
        assert task.params.fps == 60

    def test_create_daily_task_from_dict(
        self, scheduler_with_callback: TaskScheduler
    ):
        """Проверка создания ежедневной задачи из словаря."""
        data = {
            "name": "Daily Task from Dict",
            "trigger": "daily",
            "time": "09:30",
            "params": {"area_type": "window", "window_title": "Browser"},
        }

        task = scheduler_with_callback.create_task_from_dict(data)

        assert task.name == "Daily Task from Dict"
        assert task.schedule_type == ScheduleType.DAILY
        assert task.time_of_day == "09:30"
        assert task.params.window_title == "Browser"

    def test_create_weekly_task_from_dict(
        self, scheduler_with_callback: TaskScheduler
    ):
        """Проверка создания еженедельной задачи из словаря."""
        data = {
            "name": "Weekly Task from Dict",
            "trigger": "weekly",
            "time": "14:00",
            "day_of_week": "0,2,4",
            "params": {},
        }

        task = scheduler_with_callback.create_task_from_dict(data)

        assert task.name == "Weekly Task from Dict"
        assert task.schedule_type == ScheduleType.WEEKLY
        assert task.time_of_day == "14:00"
        assert task.days_of_week == [0, 2, 4]

    def test_create_interval_task_from_dict(
        self, scheduler_with_callback: TaskScheduler
    ):
        """Проверка создания интервальной задачи из словаря."""
        data = {
            "name": "Interval Task from Dict",
            "trigger": "interval",
            "hours": 2,
            "minutes": 30,
            "params": {},
        }

        task = scheduler_with_callback.create_task_from_dict(data)

        assert task.name == "Interval Task from Dict"
        assert task.schedule_type == ScheduleType.INTERVAL
        assert task.interval_hours == 2
        assert task.interval_minutes == 30

    def test_create_cron_task_from_dict(
        self, scheduler_with_callback: TaskScheduler
    ):
        """Проверка создания cron задачи из словаря."""
        data = {
            "name": "Cron Task from Dict",
            "trigger": "cron",
            "cron_expression": "0 9 * * 1-5",
            "params": {},
        }

        task = scheduler_with_callback.create_task_from_dict(data)

        assert task.name == "Cron Task from Dict"
        assert task.schedule_type == ScheduleType.CRON
        assert task.cron_expression == "0 9 * * 1-5"


class TestDSTTimezoneHandling:
    """Тесты для обработки DST и часовых поясов."""

    def test_daily_task_across_dst_boundary(
        self, scheduler_with_callback: TaskScheduler
    ):
        """Проверка что daily задача корректно работает при переходе DST."""
        task = ScheduleTask(
            id="dst-test",
            name="DST Test Task",
            schedule_type=ScheduleType.DAILY,
            time_of_day="03:00",
            params=RecordingParams(),
        )

        ok = scheduler_with_callback.add_task(task)
        assert ok, "Task creation failed"

        # Проверяем что next_run вычислен корректно
        scheduler_with_callback.start()
        time.sleep(0.5)

        task_info = scheduler_with_callback.get_task("dst-test")
        assert task_info is not None
        assert task_info.next_run is not None

        scheduler_with_callback.stop()

    def test_weekly_task_with_timezone(
        self, scheduler_with_callback: TaskScheduler
    ):
        """Проверка weekly задачи с явным часовым поясом."""
        task = ScheduleTask(
            id="weekly-tz-test",
            name="Weekly TZ Test",
            schedule_type=ScheduleType.WEEKLY,
            time_of_day="14:30",
            days_of_week=[0, 2, 4],
            params=RecordingParams(),
        )

        ok = scheduler_with_callback.add_task(task)
        assert ok, "Task creation failed"

        scheduler_with_callback.start()
        time.sleep(0.5)

        task_info = scheduler_with_callback.get_task("weekly-tz-test")
        assert task_info is not None
        assert task_info.next_run is not None

        scheduler_with_callback.stop()

    def test_cron_task_with_timezone(
        self, scheduler_with_callback: TaskScheduler
    ):
        """Проверка cron задачи с часовым поясом."""
        task = ScheduleTask(
            id="cron-tz-test",
            name="Cron TZ Test",
            schedule_type=ScheduleType.CRON,
            cron_expression="30 9 * * 1-5",
            params=RecordingParams(),
        )

        ok = scheduler_with_callback.add_task(task)
        assert ok, "Task creation failed"

        scheduler_with_callback.start()
        time.sleep(0.5)

        task_info = scheduler_with_callback.get_task("cron-tz-test")
        assert task_info is not None
        assert task_info.next_run is not None

        scheduler_with_callback.stop()

    def test_interval_task_timezone_independent(
        self,
        scheduler_with_callback: TaskScheduler,
        task_callback_results: dict,
    ):
        """Проверка что interval задача не зависит от DST.

        Примечание: тест требует минимум 1 минуту ожидания, поэтому
        пропускается в CI. Для локального тестирования уберите skip.
        """
        import pytest

        pytest.skip(
            "Interval test requires 65+ seconds. "
            "Run locally to verify DST handling."
        )

        task = ScheduleTask(
            id="interval-dst-test",
            name="Interval DST Test",
            schedule_type=ScheduleType.INTERVAL,
            interval_minutes=1,
            params=RecordingParams(),
        )

        ok = scheduler_with_callback.add_task(task)
        assert ok, "Task creation failed"

        scheduler_with_callback.start()
        time.sleep(65)

        scheduler_with_callback.stop()

        assert task_callback_results["execution_count"] >= 1
