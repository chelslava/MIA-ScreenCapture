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
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any


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
_file_handler: TimedRotatingFileHandler | None = None
_api_file_handler: TimedRotatingFileHandler | None = None


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
            today = datetime.now().strftime("%Y-%m-%d")
            log_file = LOG_DIR / f"mia_{today}.log"

            _file_handler = TimedRotatingFileHandler(
                log_file,
                when="midnight",
                interval=1,
                backupCount=backup_days,
                encoding="utf-8",
            )
            _file_handler.suffix = "%Y-%m-%d"
            _file_handler.setLevel(logging.DEBUG)
            _file_handler.setFormatter(formatter)
            logger.addHandler(_file_handler)

            api_log_file = API_LOG_DIR / f"api_{today}.log"
            _api_file_handler = TimedRotatingFileHandler(
                api_log_file,
                when="midnight",
                interval=1,
                backupCount=backup_days,
                encoding="utf-8",
            )
            _api_file_handler.suffix = "%Y-%m-%d"
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
