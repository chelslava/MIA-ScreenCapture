"""
Модуль планировщика задач
=========================

Управляет запланированными задачами записи с использованием APScheduler.
Поддерживает разовые, ежедневные, еженедельные и интервальные расписания.
"""

import json
import os
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
import tempfile
from typing import Any, Callable, Dict, List, Optional

import tzlocal
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from logger_config import get_module_logger

logger = get_module_logger(__name__)


def _atomic_write_json(path: Path, data: Any) -> bool:
    """Атомарно записывает JSON в файл через временный файл."""
    temp_path: Optional[Path] = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp_file:
            temp_path = Path(tmp_file.name)
            json.dump(data, tmp_file, indent=2, ensure_ascii=False)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())

        os.replace(temp_path, path)
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения задач: {e}")
        return False
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


class ScheduleType(Enum):
    """Перечисление типов расписания."""

    ONCE = "once"  # Разовая задача
    DAILY = "daily"  # Каждый день в определённое время
    WEEKLY = "weekly"  # Определённые дни недели
    INTERVAL = "interval"  # Каждые N минут/часов
    CRON = "cron"  # Cron-выражение


@dataclass
class RecordingParams:
    """Параметры записи для запланированных задач."""

    area_type: str = "full"  # "full", "window", "rect"
    window_title: Optional[str] = None
    rect_coords: Optional[List[int]] = None  # [x1, y1, x2, y2]
    audio_type: str = "none"  # "mic", "system", "none", "both"
    output_path: Optional[str] = None
    fps: int = 30
    codec: str = "libx264"
    bitrate: str = "2M"
    duration: Optional[int] = None  # Длительность в секундах

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecordingParams":
        """Создание из словаря."""
        return cls(
            **{k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        )


@dataclass
class ScheduleTask:
    """Определение запланированной задачи."""

    id: str
    name: str
    schedule_type: ScheduleType
    params: RecordingParams
    enabled: bool = True

    # Поля специфичные для расписания
    start_time: Optional[datetime] = None  # Для разовых задач
    time_of_day: Optional[str] = None  # Для daily/weekly: "HH:MM"
    days_of_week: Optional[List[int]] = (
        None  # Для weekly: 0=Понедельник, 6=Воскресенье
    )
    interval_minutes: Optional[int] = None  # Для интервальных задач
    interval_hours: Optional[int] = None
    cron_expression: Optional[str] = (
        None  # Для cron: стандартное cron-выражение
    )

    # Отслеживание выполнения
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для сериализации."""
        data = {
            "id": self.id,
            "name": self.name,
            "schedule_type": self.schedule_type.value,
            "params": self.params.to_dict(),
            "enabled": self.enabled,
            "time_of_day": self.time_of_day,
            "days_of_week": self.days_of_week,
            "interval_minutes": self.interval_minutes,
            "interval_hours": self.interval_hours,
            "cron_expression": self.cron_expression,
            "run_count": self.run_count,
        }

        if self.start_time:
            data["start_time"] = self.start_time.isoformat()
        if self.last_run:
            data["last_run"] = self.last_run.isoformat()
        if self.next_run:
            data["next_run"] = self.next_run.isoformat()

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScheduleTask":
        """Создание из словаря."""
        params = RecordingParams.from_dict(data.get("params", {}))

        start_time = None
        if data.get("start_time"):
            start_time = datetime.fromisoformat(data["start_time"])

        last_run = None
        if data.get("last_run"):
            last_run = datetime.fromisoformat(data["last_run"])

        next_run = None
        if data.get("next_run"):
            next_run = datetime.fromisoformat(data["next_run"])

        return cls(
            id=data["id"],
            name=data["name"],
            schedule_type=ScheduleType(data["schedule_type"]),
            params=params,
            enabled=data.get("enabled", True),
            start_time=start_time,
            time_of_day=data.get("time_of_day"),
            days_of_week=data.get("days_of_week"),
            interval_minutes=data.get("interval_minutes"),
            interval_hours=data.get("interval_hours"),
            cron_expression=data.get("cron_expression"),
            last_run=last_run,
            next_run=next_run,
            run_count=data.get("run_count", 0),
        )


class TaskScheduler:
    """
    Планировщик задач для управления запланированными записями.

    Использует APScheduler для надёжного выполнения задач с поддержкой
    различных типов расписания и сохранения задач.
    """

    def __init__(self, persist_path: Optional[Path] = None):
        """
        Инициализация планировщика задач.

        Args:
            persist_path: Путь для сохранения задач (опционально)
        """
        self.persist_path = persist_path
        self._tasks: Dict[str, ScheduleTask] = {}
        self._lock = threading.Lock()

        # Обратный вызов для выполнения задачи
        self._on_task_execute: Optional[Callable] = None

        # Инициализация APScheduler
        self._scheduler = BackgroundScheduler(
            jobstores={"default": MemoryJobStore()},
            executors={"default": ThreadPoolExecutor(max_workers=3)},
            timezone=tzlocal.get_localzone(),
        )

        # Загрузка сохранённых задач
        if self.persist_path:
            self._load_tasks()

    def start(self) -> None:
        """Запуск планировщика."""
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("Планировщик задач запущен")

            # Планирование всех включённых задач
            with self._lock:
                for task in self._tasks.values():
                    if task.enabled:
                        self._schedule_job(task)

    def stop(self) -> None:
        """Остановка планировщика."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Планировщик задач остановлен")

    def set_task_callback(self, callback: Callable) -> None:
        """
        Установка функции обратного вызова для выполнения задачи.

        Args:
            callback: Функция для вызова при выполнении задачи (получает RecordingParams)
        """
        self._on_task_execute = callback

    def add_task(self, task: ScheduleTask) -> bool:
        """
        Добавление новой запланированной задачи.

        Args:
            task: Задача для добавления

        Returns:
            True если задача успешно добавлена
        """
        with self._lock:
            if task.id in self._tasks:
                logger.warning(f"Задача {task.id} уже существует")
                return False

            self._tasks[task.id] = task

            if task.enabled and self._scheduler.running:
                self._schedule_job(task)

        self._save_tasks()
        logger.info(f"Задача добавлена: {task.id} ({task.name})")
        return True

    def update_task(self, task: ScheduleTask) -> bool:
        """
        Обновление существующей задачи.

        Args:
            task: Обновлённые данные задачи

        Returns:
            True если задача успешно обновлена
        """
        with self._lock:
            if task.id not in self._tasks:
                logger.warning(f"Задача {task.id} не найдена")
                return False

            # Удаление старой задачи
            self._unschedule_job(task.id)

            # Обновление задачи
            self._tasks[task.id] = task

            # Перепланирование если включена
            if task.enabled and self._scheduler.running:
                self._schedule_job(task)

        self._save_tasks()
        logger.info(f"Задача обновлена: {task.id}")
        return True

    def remove_task(self, task_id: str) -> bool:
        """
        Удаление запланированной задачи.

        Args:
            task_id: ID задачи для удаления

        Returns:
            True если задача успешно удалена
        """
        with self._lock:
            if task_id not in self._tasks:
                return False

            self._unschedule_job(task_id)
            del self._tasks[task_id]

        self._save_tasks()
        logger.info(f"Задача удалена: {task_id}")
        return True

    def enable_task(self, task_id: str, enabled: bool = True) -> bool:
        """
        Включение или отключение задачи.

        Args:
            task_id: ID задачи
            enabled: Состояние включения

        Returns:
            True если успешно
        """
        with self._lock:
            if task_id not in self._tasks:
                return False

            task = self._tasks[task_id]
            task.enabled = enabled

            if enabled:
                self._schedule_job(task)
            else:
                self._unschedule_job(task_id)

        self._save_tasks()
        return True

    def get_task(self, task_id: str) -> Optional[ScheduleTask]:
        """
        Получение задачи по ID.

        Args:
            task_id: ID задачи

        Returns:
            Задача или None если не найдена
        """
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[ScheduleTask]:
        """
        Получение всех запланированных задач.

        Returns:
            Список всех задач
        """
        return list(self._tasks.values())

    def get_task_count(self) -> int:
        """Получение общего количества задач."""
        return len(self._tasks)

    def _schedule_job(self, task: ScheduleTask) -> None:
        """
        Планирование задачи в APScheduler.

        Args:
            task: Задача для планирования
        """
        try:
            trigger = self._create_trigger(task)
            if trigger:
                self._scheduler.add_job(
                    self._execute_task,
                    trigger=trigger,
                    id=task.id,
                    args=[task.id],
                    replace_existing=True,
                )

                # Обновление next_run
                job = self._scheduler.get_job(task.id)
                if job:
                    task.next_run = job.next_run_time

                logger.debug(
                    f"Задача запланирована: {task.id}, следующий запуск: {task.next_run}"
                )

        except Exception as e:
            logger.error(f"Ошибка планирования задачи {task.id}: {e}")

    def _unschedule_job(self, task_id: str) -> None:
        """
        Удаление задачи из APScheduler.

        Args:
            task_id: ID задачи для удаления из расписания
        """
        try:
            self._scheduler.remove_job(task_id)
        except Exception:
            pass  # Задача может не существовать

    def _create_trigger(self, task: ScheduleTask):
        """
        Создание триггера APScheduler для задачи.

        Args:
            task: Задача для создания триггера

        Returns:
            Триггер APScheduler
        """
        if task.schedule_type == ScheduleType.ONCE:
            if task.start_time:
                return DateTrigger(run_date=task.start_time)

        elif task.schedule_type == ScheduleType.DAILY:
            if task.time_of_day:
                hour, minute = map(int, task.time_of_day.split(":"))
                return CronTrigger(hour=hour, minute=minute)

        elif task.schedule_type == ScheduleType.WEEKLY:
            if task.time_of_day and task.days_of_week:
                hour, minute = map(int, task.time_of_day.split(":"))
                return CronTrigger(
                    hour=hour,
                    minute=minute,
                    day_of_week=",".join(str(d) for d in task.days_of_week),
                )

        elif task.schedule_type == ScheduleType.INTERVAL:
            return IntervalTrigger(
                weeks=0,
                days=0,
                hours=task.interval_hours or 0,
                minutes=task.interval_minutes or 0,
            )

        elif task.schedule_type == ScheduleType.CRON:
            if task.cron_expression:
                return CronTrigger.from_crontab(task.cron_expression)

        return None

    def _execute_task(self, task_id: str) -> None:
        """
        Выполнение запланированной задачи.

        Args:
            task_id: ID задачи для выполнения
        """
        # Получение задачи с блокировкой для thread-safety
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                logger.warning(f"Задача {task_id} не найдена для выполнения")
                return

            logger.info(
                f"Выполнение запланированной задачи: {task_id} ({task.name})"
            )

            # Обновление отслеживания выполнения
            task.last_run = datetime.now()
            task.run_count += 1

            # Обновление next_run для повторяющихся задач
            job = self._scheduler.get_job(task_id)
            if job:
                task.next_run = job.next_run_time

        self._save_tasks()

        # Выполнение обратного вызова вне блокировки
        if self._on_task_execute:
            try:
                self._on_task_execute(task.params)
            except Exception as e:
                logger.error(f"Ошибка выполнения обратного вызова задачи: {e}")

    def _load_tasks(self) -> None:
        """Загрузка задач из файла сохранения."""
        if not self.persist_path or not self.persist_path.exists():
            return

        try:
            with open(self.persist_path, encoding="utf-8") as f:
                data = json.load(f)

            for task_data in data.get("tasks", []):
                try:
                    task = ScheduleTask.from_dict(task_data)
                    self._tasks[task.id] = task
                except Exception as e:
                    logger.error(f"Ошибка загрузки задачи: {e}")

            logger.info(
                f"Загружено {len(self._tasks)} задач из {self.persist_path}"
            )

        except Exception as e:
            logger.error(f"Ошибка загрузки задач: {e}")

    def _save_tasks(self) -> None:
        """Сохранение задач в файл."""
        if not self.persist_path:
            return

        try:
            data = {
                "tasks": [task.to_dict() for task in self._tasks.values()],
                "last_updated": datetime.now().isoformat(),
            }
            _atomic_write_json(self.persist_path, data)
        except Exception as e:
            logger.error(f"Ошибка сохранения задач: {e}")

    def create_task_from_dict(self, data: Dict[str, Any]) -> ScheduleTask:
        """
        Создание задачи из данных API запроса.

        Args:
            data: Словарь конфигурации задачи

        Returns:
            Созданная ScheduleTask
        """
        import uuid

        task_id = data.get("id", str(uuid.uuid4())[:8])
        name = data.get("name", f"Задача {task_id}")

        # Разбор типа расписания
        trigger_type = data.get("trigger", "once")
        schedule_type = ScheduleType(trigger_type)

        # Разбор параметров записи
        params_data = data.get("params", {})
        params = RecordingParams.from_dict(params_data)

        # Создание задачи
        task = ScheduleTask(
            id=task_id,
            name=name,
            schedule_type=schedule_type,
            params=params,
            enabled=data.get("enabled", True),
        )

        # Установка полей специфичных для расписания
        if schedule_type == ScheduleType.ONCE:
            if data.get("datetime"):
                task.start_time = datetime.fromisoformat(data["datetime"])

        elif schedule_type in (ScheduleType.DAILY, ScheduleType.WEEKLY):
            task.time_of_day = data.get("time", "12:00")
            if schedule_type == ScheduleType.WEEKLY:
                days = data.get("day_of_week", "0,1,2,3,4")
                task.days_of_week = [int(d.strip()) for d in days.split(",")]

        elif schedule_type == ScheduleType.INTERVAL:
            task.interval_hours = data.get("hours", 0)
            task.interval_minutes = data.get("minutes", 0)

        elif schedule_type == ScheduleType.CRON:
            task.cron_expression = data.get("cron_expression")

        return task
