"""
Модуль конфигурации логирования
================================

Настраивает логирование для всего приложения с поддержкой
ротации файлов и вывода в консоль.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime
from typing import Optional


# Директория для логов по умолчанию
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Путь к файлу логов
LOG_FILE = LOG_DIR / "recorder.log"

# Формат логов
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(
    name: str = "video_recorder",
    level: int = logging.DEBUG,
    log_to_file: bool = True,
    log_to_console: bool = True,
    max_bytes: int = 5 * 1024 * 1024,  # 5 МБ
    backup_count: int = 5
) -> logging.Logger:
    """
    Настройка логгера с обработчиками файла и консоли.
    
    Args:
        name: Имя логгера
        level: Уровень логирования (по умолчанию: DEBUG)
        log_to_file: Включить логирование в файл
        log_to_console: Включить логирование в консоль
        max_bytes: Максимальный размер файла логов до ротации
        backup_count: Количество резервных файлов для хранения
        
    Returns:
        Настроенный экземпляр логгера
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Очистка существующих обработчиков
    logger.handlers.clear()
    
    # Создание форматтера
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    
    # Файловый обработчик с ротацией
    if log_to_file:
        try:
            file_handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Предупреждение: Не удалось создать файл логов: {e}", file=sys.stderr)
    
    # Консольный обработчик
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Получение существующего логгера или создание нового.
    
    Args:
        name: Имя логгера
        
    Returns:
        Экземпляр логгера
    """
    return logging.getLogger(name)


# Инициализация корневого логгера при импорте модуля
root_logger = setup_logger("video_recorder")


class LoggerAdapter(logging.LoggerAdapter):
    """
    Пользовательский адаптер логгера для добавления контекстной информации.
    """
    
    def process(self, msg: str, kwargs: dict) -> tuple:
        """
        Обработка вызова логирования для добавления контекста.
        
        Args:
            msg: Сообщение лога
            kwargs: Дополнительные именованные аргументы
            
        Returns:
            Кортеж (сообщение, kwargs)
        """
        extra = kwargs.get('extra', {})
        extra.update(self.extra or {})
        kwargs['extra'] = extra
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


# Удобная функция для получения логгеров модулей
def get_module_logger(module_name: str) -> logging.Logger:
    """
    Получение логгера для модуля.
    
    Args:
        module_name: Имя модуля (обычно __name__)
        
    Returns:
        Экземпляр логгера для модуля
    """
    return create_module_logger(module_name.split('.')[-1])
