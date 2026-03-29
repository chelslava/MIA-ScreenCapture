"""
Модуль планировщика задач
=========================

Управляет запланированными задачами записи с использованием APScheduler.
Поддерживает разовые, ежедневные, еженедельные и интервальные расписания.
"""

import contextlib
import re
import threading
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

import tzlocal
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from logger_config import get_module_logger
from scheduler.task_storage import TaskStorage

logger = get_module_logger(__name__)
_TIME_OF_DAY_PATTERN = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


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
    window_title: str | None = None
    rect_coords: list[int] | None = None  # [x1, y1, x2, y2]
    audio_type: str = "none"  # "mic", "system", "none", "both"
    output_path: str | None = None
    fps: int = 30
    codec: str = "libx264"
    bitrate: str = "2M"
    duration: int | None = None  # Длительность в секундах

    def to_dict(self) -> dict[str, Any]:
        """Преобразование в словарь."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RecordingParams":
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
    start_time: datetime | None = None  # Для разовых задач
    time_of_day: str | None = None  # Для daily/weekly: "HH:MM"
    days_of_week: list[int] | None = (
        None  # Для weekly: 0=Понедельник, 6=Воскресенье
    )
    interval_minutes: int | None = None  # Для интервальных задач
    interval_hours: int | None = None
    cron_expression: str | None = None  # Для cron: стандартное cron-выражение

    # Отслеживание выполнения
    last_run: datetime | None = None
    next_run: datetime | None = None
    run_count: int = 0

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> "ScheduleTask":
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

    def __init__(
        self,
        persist_path: Path | None = None,
        max_concurrent_tasks: int = 3,
    ):
        """
        Инициализация планировщика задач.

        Args:
            persist_path: Путь для сохранения задач (опционально)
            max_concurrent_tasks: Лимит параллельных задач APScheduler.
        """
        self.persist_path = persist_path
        self._storage = (
            TaskStorage(persist_path) if persist_path is not None else None
        )
        self._tasks: dict[str, ScheduleTask] = {}
        self._lock = threading.Lock()
        self._max_concurrent_tasks = max(1, int(max_concurrent_tasks))

        # Обратный вызов для выполнения задачи
        self._on_task_execute: Callable | None = None

        # Инициализация APScheduler
        self._scheduler = BackgroundScheduler(
            jobstores={"default": MemoryJobStore()},
            executors={
                "default": ThreadPoolExecutor(
                    max_workers=self._max_concurrent_tasks
                )
            },
            timezone=tzlocal.get_localzone(),
        )

        # Загрузка сохранённых задач
        if self._storage is not None:
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
            # Ждём корректного завершения scheduler-потоков, чтобы не оставлять
            # открытые дескрипторы во временных директориях (важно для Windows/CI).
            self._scheduler.shutdown(wait=True)
            logger.info("Планировщик задач остановлен")

    def __del__(self) -> None:
        """Защитная остановка scheduler при сборке мусора."""
        with contextlib.suppress(Exception):
            self.stop()

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

            is_valid, validation_error = self._validate_task_schedule(task)
            if not is_valid:
                logger.warning(
                    "Задача %s отклонена: %s", task.id, validation_error
                )
                return False

            self._tasks[task.id] = task

            if task.enabled and self._scheduler.running:
                if not self._schedule_job(task):
                    del self._tasks[task.id]
                    logger.warning(
                        "Добавление задачи %s отменено: не удалось "
                        "запланировать задачу",
                        task.id,
                    )
                    return False

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

            is_valid, validation_error = self._validate_task_schedule(task)
            if not is_valid:
                logger.warning(
                    "Обновление задачи %s отклонено: %s",
                    task.id,
                    validation_error,
                )
                return False

            # Удаление старой задачи
            previous_task = self._tasks[task.id]
            self._unschedule_job(task.id)

            # Обновление задачи
            self._tasks[task.id] = task

            # Перепланирование если включена
            if task.enabled and self._scheduler.running:
                if not self._schedule_job(task):
                    self._tasks[task.id] = previous_task
                    if previous_task.enabled and self._scheduler.running:
                        self._schedule_job(previous_task)
                    logger.warning(
                        "Обновление задачи %s отменено: не удалось "
                        "запланировать обновлённую задачу",
                        task.id,
                    )
                    return False

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
                if not self._schedule_job(task):
                    task.enabled = False
                    logger.warning(
                        "Не удалось включить задачу %s: ошибка планирования",
                        task_id,
                    )
                    return False
            else:
                self._unschedule_job(task_id)

        self._save_tasks()
        return True

    def get_task(self, task_id: str) -> ScheduleTask | None:
        """
        Получение задачи по ID.

        Args:
            task_id: ID задачи

        Returns:
            Задача или None если не найдена
        """
        with self._lock:
            return self._tasks.get(task_id)

    def get_all_tasks(self) -> list[ScheduleTask]:
        """
        Получение всех запланированных задач.

        Returns:
            Список всех задач
        """
        with self._lock:
            return list(self._tasks.values())

    def get_task_count(self) -> int:
        """Получение общего количества задач."""
        with self._lock:
            return len(self._tasks)

    def get_upcoming_runs(self, count: int = 5) -> list[dict[str, Any]]:
        """
        Возвращает предстоящие запуски задач.

        Args:
            count: Максимальное количество запусков для возврата

        Returns:
            Список словарей с информацией о запусках:
            [{
                'task_id': str,
                'name': str,
                'next_run': str (ISO format),
                'type': str,
                'enabled': bool
            }, ...]
        """
        upcoming: list[dict[str, Any]] = []

        with self._lock:
            for task in self._tasks.values():
                if not task.enabled:
                    continue

                # Получение next_run из задачи или из job
                next_run = task.next_run
                if next_run is None and self._scheduler.running:
                    try:
                        job = self._scheduler.get_job(task.id)
                        if job and job.next_run_time:
                            next_run = job.next_run_time
                    except Exception as e:
                        logger.warning(
                            "Не удалось получить next_run для задачи %s: %s",
                            task.id,
                            e,
                        )

                if next_run:
                    upcoming.append(
                        {
                            "task_id": task.id,
                            "name": task.name,
                            "next_run": next_run.isoformat()
                            if hasattr(next_run, "isoformat")
                            else str(next_run),
                            "type": task.schedule_type.value,
                            "enabled": task.enabled,
                        }
                    )

        # Сортировка по времени (ближайшие сначала)
        upcoming.sort(key=lambda x: x["next_run"])

        return upcoming[:count]

    def _schedule_job(self, task: ScheduleTask) -> bool:
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
                    task.next_run = getattr(job, "next_run_time", None)

                logger.debug(
                    "Задача запланирована: %s, следующий запуск: %s",
                    task.id,
                    task.next_run,
                )
                return True

        except Exception as e:
            logger.error(f"Ошибка планирования задачи {task.id}: {e}")
            return False

        return False

    def _unschedule_job(self, task_id: str) -> None:
        """
        Удаление задачи из APScheduler.

        Args:
            task_id: ID задачи для удаления из расписания
        """
        with contextlib.suppress(Exception):
            self._scheduler.remove_job(task_id)

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
                hour, minute = self._parse_time_of_day(task.time_of_day)
                return CronTrigger(hour=hour, minute=minute)

        elif task.schedule_type == ScheduleType.WEEKLY:
            if task.time_of_day and task.days_of_week:
                hour, minute = self._parse_time_of_day(task.time_of_day)
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

        elif task.schedule_type == ScheduleType.CRON and task.cron_expression:
            return CronTrigger.from_crontab(task.cron_expression)

        return None

    def _validate_task_schedule(
        self, task: ScheduleTask
    ) -> tuple[bool, str | None]:
        """Проверяет только критичные невыполнимые сценарии расписания."""
        if task.schedule_type == ScheduleType.WEEKLY:
            if task.time_of_day is None:
                return (
                    False,
                    "Для weekly задачи требуется time_of_day в формате HH:MM",
                )
            if not self._is_valid_time_of_day(task.time_of_day):
                return (
                    False,
                    f"Некорректный формат time_of_day: {task.time_of_day}",
                )
            if not task.days_of_week:
                return (
                    False,
                    "Для weekly задачи нужен минимум один день недели",
                )
            invalid_days = [d for d in task.days_of_week if d < 0 or d > 6]
            if invalid_days:
                return (
                    False,
                    f"Недопустимые дни недели: {invalid_days}",
                )

        if task.schedule_type == ScheduleType.DAILY:
            if task.time_of_day is None:
                return (
                    False,
                    "Для daily задачи требуется time_of_day в формате HH:MM",
                )
            if not self._is_valid_time_of_day(task.time_of_day):
                return (
                    False,
                    f"Некорректный формат time_of_day: {task.time_of_day}",
                )

        if task.schedule_type == ScheduleType.INTERVAL:
            hours = task.interval_hours or 0
            minutes = task.interval_minutes or 0
            if hours <= 0 and minutes <= 0:
                return (
                    False,
                    "Для interval задачи нужен интервал больше 0",
                )
        return True, None

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
        if self._storage is None:
            return

        try:
            for task_data in self._storage.load_tasks_payload():
                try:
                    task = ScheduleTask.from_dict(task_data)
                    self._tasks[task.id] = task
                except Exception as e:
                    logger.error(f"Ошибка загрузки задачи: {e}")

            logger.info(
                "Загружено %s задач из %s",
                len(self._tasks),
                self._storage.persist_path,
            )

        except Exception as e:
            logger.error(f"Ошибка загрузки задач: {e}")

    def _save_tasks(self) -> None:
        """Сохранение задач в файл."""
        if self._storage is None:
            return

        try:
            with self._lock:
                tasks_snapshot = [
                    task.to_dict() for task in self._tasks.values()
                ]
            self._storage.save_tasks_payload(tasks_snapshot)
        except Exception as e:
            logger.error(f"Ошибка сохранения задач: {e}")

    def create_task_from_dict(self, data: dict[str, Any]) -> ScheduleTask:
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

        # Разбор типа расписания (поддержка API- и GUI-форматов)
        trigger_type = self._extract_trigger_type(data)
        schedule_type = ScheduleType(trigger_type)

        # Разбор параметров записи (поддержка вложенного и плоского формата)
        params_data = self._extract_params_data(data)
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
            start_value = data.get("datetime", data.get("start_time"))
            if start_value:
                if isinstance(start_value, datetime):
                    task.start_time = start_value
                else:
                    task.start_time = datetime.fromisoformat(str(start_value))

        elif schedule_type in (ScheduleType.DAILY, ScheduleType.WEEKLY):
            task.time_of_day = data.get(
                "time", data.get("time_of_day", "12:00")
            )
            if task.time_of_day is None or not self._is_valid_time_of_day(
                task.time_of_day
            ):
                raise ValueError(
                    "time_of_day должен быть в формате HH:MM "
                    "в диапазоне 00:00..23:59"
                )
            if schedule_type == ScheduleType.WEEKLY:
                days_value = data.get(
                    "day_of_week", data.get("days_of_week", "0,1,2,3,4")
                )
                if isinstance(days_value, list):
                    task.days_of_week = [int(d) for d in days_value]
                else:
                    task.days_of_week = [
                        int(d.strip()) for d in str(days_value).split(",")
                    ]

        elif schedule_type == ScheduleType.INTERVAL:
            task.interval_hours = int(
                data.get("hours", data.get("interval_hours", 0))
            )
            task.interval_minutes = int(
                data.get("minutes", data.get("interval_minutes", 0))
            )

        elif schedule_type == ScheduleType.CRON:
            task.cron_expression = data.get("cron_expression")

        return task

    def _is_valid_time_of_day(self, value: str) -> bool:
        """Проверяет формат времени HH:MM в 24-часовом диапазоне."""
        return _TIME_OF_DAY_PATTERN.fullmatch(value) is not None

    def _parse_time_of_day(self, value: str) -> tuple[int, int]:
        """Преобразует строку HH:MM в часы и минуты с валидацией."""
        match = _TIME_OF_DAY_PATTERN.fullmatch(value)
        if not match:
            raise ValueError(
                "time_of_day должен быть в формате HH:MM "
                "в диапазоне 00:00..23:59"
            )
        return int(match.group(1)), int(match.group(2))

    def _extract_trigger_type(self, data: dict[str, Any]) -> str:
        """Извлекает тип расписания из API/GUІ payload."""
        trigger_value = data.get("trigger", data.get("schedule_type", "once"))
        if isinstance(trigger_value, ScheduleType):
            return trigger_value.value
        return str(trigger_value)

    def _extract_params_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Извлекает параметры записи из вложенного или плоского payload."""
        params_data = data.get("params")
        if isinstance(params_data, dict):
            return dict(params_data)

        result: dict[str, Any] = {}
        for key in (
            "area_type",
            "window_title",
            "rect_coords",
            "audio_type",
            "output_path",
            "fps",
            "codec",
            "bitrate",
            "duration",
        ):
            if key in data and data[key] is not None:
                result[key] = data[key]
        return result
