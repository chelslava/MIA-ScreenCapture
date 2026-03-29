"""
Модуль конфигурации логирования
===============================

Настраивает логирование для всего приложения с поддержкой
ротации файлов по дням и вывода в консоль.
"""

import atexit
import logging
import os
import sys
from collections.abc import MutableMapping
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast


def get_log_dir() -> Path:
    """Получение директории для логов."""
    import os

    if getattr(sys, "frozen", False):
        base_path = Path(os.environ.get("APPDATA", ".")) / "MIA-ScreenCapture"
    else:
        base_path = Path(__file__).parent

    log_dir = base_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


LOG_DIR = get_log_dir()
API_LOG_DIR = LOG_DIR / "api"
API_LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_root_logger: logging.Logger | None = None
_file_handler: logging.Handler | None = None
_api_file_handler: logging.Handler | None = None


def _now() -> datetime:
    """Возвращает текущее локальное время для логирования."""
    return datetime.now()


class _DailyLogFileHandler(logging.FileHandler):
    """
    Обработчик логов с именем файла по текущей дате.

    Формат имени: `<prefix>_YYYY-MM-DD.log`.
    При смене даты обработчик автоматически открывает новый файл
    без суффиксов, что упрощает чтение live-логов.
    """

    def __init__(
        self,
        log_dir: Path,
        prefix: str,
        backup_days: int,
        encoding: str = "utf-8",
    ) -> None:
        self._log_dir = log_dir
        self._prefix = prefix
        self._backup_days = backup_days
        self._current_date = self._get_date_str()
        path = self._build_path(self._current_date)
        super().__init__(path, mode="a", encoding=encoding, delay=False)
        self._cleanup_old_files()

    def _get_date_str(self) -> str:
        """Текущая дата в формате `YYYY-MM-DD`."""
        return _now().strftime("%Y-%m-%d")

    def _build_path(self, date_str: str) -> Path:
        """Построение пути к файлу лога для указанной даты."""
        return self._log_dir / f"{self._prefix}_{date_str}.log"

    def _maybe_rollover(self) -> None:
        """Переключение файла при смене календарной даты."""
        next_date = self._get_date_str()
        if next_date == self._current_date:
            return

        self.acquire()
        try:
            if self.stream:
                self.stream.close()
                self.stream = cast(Any, None)

            self._current_date = next_date
            self.baseFilename = os.fspath(self._build_path(next_date))
            self.stream = self._open()
            self._cleanup_old_files()
        finally:
            self.release()

    def _cleanup_old_files(self) -> None:
        """Удаление старых файлов логов старше `backup_days`."""
        if self._backup_days <= 0:
            return

        cutoff_date = (_now() - timedelta(days=self._backup_days)).date()
        pattern = f"{self._prefix}_*.log"
        for file_path in self._log_dir.glob(pattern):
            suffix = file_path.stem.removeprefix(f"{self._prefix}_")
            try:
                file_date = datetime.strptime(suffix, "%Y-%m-%d").date()
            except ValueError:
                continue
            if file_date < cutoff_date:
                try:
                    file_path.unlink()
                except OSError:
                    continue

    def emit(self, record: logging.LogRecord) -> None:
        """Записывает запись и выполняет rollover по дате при необходимости."""
        self._maybe_rollover()
        super().emit(record)


class _ApiModuleFilter(logging.Filter):
    """Фильтр логов только для модулей API."""

    def filter(self, record: logging.LogRecord) -> bool:
        normalized_path = record.pathname.replace("\\", "/").lower()
        return "/api/" in normalized_path


def setup_logger(
    name: str = "video_recorder",
    level: int = logging.DEBUG,
    log_to_file: bool = True,
    log_to_console: bool = True,
    backup_days: int = 30,
) -> logging.Logger:
    """
    Настройка логгера с обработчиками файла и консоли.

    Args:
        name: Имя логгера
        level: Уровень логирования (по умолчанию: DEBUG)
        log_to_file: Включить логирование в файл
        log_to_console: Включить логирование в консоль
        backup_days: Количество дней для хранения логов

    Returns:
        Настроенный экземпляр логгера
    """
    global _api_file_handler, _root_logger, _file_handler

    logger = logging.getLogger(name)
    logger.setLevel(level)

    logger.handlers.clear()

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    if log_to_file:
        try:
            _file_handler = _DailyLogFileHandler(
                log_dir=LOG_DIR,
                prefix="mia",
                backup_days=backup_days,
                encoding="utf-8",
            )
            _file_handler.setLevel(logging.DEBUG)
            _file_handler.setFormatter(formatter)
            logger.addHandler(_file_handler)

            _api_file_handler = _DailyLogFileHandler(
                log_dir=API_LOG_DIR,
                prefix="api",
                backup_days=backup_days,
                encoding="utf-8",
            )
            _api_file_handler.setLevel(logging.DEBUG)
            _api_file_handler.setFormatter(formatter)
            _api_file_handler.addFilter(_ApiModuleFilter())
            logger.addHandler(_api_file_handler)
        except Exception as e:
            print(
                f"Предупреждение: Не удалось создать файл логов: {e}",
                file=sys.stderr,
            )

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    _root_logger = logger

    atexit.register(_cleanup_handlers)

    return logger


def _cleanup_handlers() -> None:
    """Очистка обработчиков при выходе."""
    global _api_file_handler, _root_logger, _file_handler
    if _file_handler:
        _file_handler.close()
    if _api_file_handler:
        _api_file_handler.close()
    if _root_logger:
        for handler in _root_logger.handlers[:]:
            handler.close()


def get_logger(name: str) -> logging.Logger:
    """
    Получение существующего логгера или создание нового.

    Args:
        name: Имя логгера

    Returns:
        Экземпляр логгера
    """
    return logging.getLogger(name)


root_logger = setup_logger("video_recorder")


class LoggerAdapter(logging.LoggerAdapter):
    """
    Пользовательский адаптер логгера для добавления контекстной информации.
    """

    def process(
        self, msg: str, kwargs: MutableMapping[str, Any]
    ) -> tuple[str, MutableMapping[str, Any]]:
        """
        Обработка вызова логирования для добавления контекста.

        Args:
            msg: Сообщение лога
            kwargs: Дополнительные именованные аргументы

        Returns:
            Кортеж (сообщение, kwargs)
        """
        extra = kwargs.get("extra", {})
        extra.update(self.extra or {})
        kwargs["extra"] = extra
        return msg, kwargs


def create_module_logger(module_name: str) -> logging.Logger:
    """
    Создание логгера для конкретного модуля.

    Args:
        module_name: Имя модуля

    Returns:
        Логгер для модуля
    """
    return logging.getLogger(f"video_recorder.{module_name}")


def get_module_logger(module_name: str) -> logging.Logger:
    """
    Получение логгера для модуля.

    Args:
        module_name: Имя модуля (обычно __name__)

    Returns:
        Экземпляр логгера для модуля
    """
    return create_module_logger(module_name.split(".")[-1])


def open_logs_folder() -> None:
    """Открытие папки с логами в проводнике."""
    import os
    import subprocess

    log_dir = get_log_dir()

    if log_dir.exists():
        if sys.platform == "win32":
            os.startfile(str(log_dir))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(log_dir)])
        else:
            subprocess.run(["xdg-open", str(log_dir)])


def get_api_log_dir() -> Path:
    """Получение директории для логов API."""
    API_LOG_DIR.mkdir(parents=True, exist_ok=True)
    return API_LOG_DIR


def open_api_logs_folder() -> None:
    """Открытие папки с логами API в проводнике."""
    import subprocess

    api_log_dir = get_api_log_dir()

    if api_log_dir.exists():
        if sys.platform == "win32":
            os.startfile(str(api_log_dir))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(api_log_dir)])
        else:
            subprocess.run(["xdg-open", str(api_log_dir)])
