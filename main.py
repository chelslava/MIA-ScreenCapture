#!/usr/bin/env python3
"""
MIA-ScreenCapture - Главная точка входа
======================================

Профессиональный видеозаписывающий рекордер экрана с GUI, REST API,
планировщиком и поддержкой интерфейса командной строки.

Использование:
    python main.py                          # Запуск с GUI
    python main.py --headless               # Запуск без GUI (только API)
    python main.py --start                  # Начать запись немедленно
    python main.py --start --area rect --rect 100 100 800 600
    python main.py --stop                   # Остановить текущую запись
    python main.py --status                 # Показать статус записи
"""

import sys
from pathlib import Path

# Добавление родительской директории в путь для импорта
sys.path.insert(0, str(Path(__file__).parent))

# Загрузка .env файла ДО любых импортов, использующих переменные окружения
from dotenv import load_dotenv

from app_runtime.gui_coordinator import GuiRuntimeCoordinator
from cli.parser import (
    parse_args,
)
from config import init_config
from core.i18n import set_locale
from core.lifecycle import GracefulShutdown, get_shutdown_manager
from logger_config import get_module_logger, setup_logger
from single_instance import SingleInstanceGuard, bring_existing_window_to_front

logger = get_module_logger(__name__)

_SINGLE_INSTANCE_MODES = ("gui", "headless")

# Ре-экспорты для обратной совместимости: тесты ссылаются на
# main.GracefulShutdown и main.GuiRuntimeCoordinator (#176)
__all__ = [
    "GracefulShutdown",
    "GuiRuntimeCoordinator",
    "SingleInstanceGuard",
    "VideoRecorderApp",
    "get_shutdown_manager",
    "main",
]


def _load_environment() -> None:
    """Загружает переменные окружения из `.env` при наличии файла."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def _handle_already_running(mode: str) -> int:
    """
    Обрабатывает запуск при уже работающем экземпляре приложения.

    Args:
        mode: Режим запуска текущего (второго) процесса.

    Returns:
        Код выхода 0 — это штатный сценарий, а не ошибка пользователя.
    """
    logger.info("Другой экземпляр MIA-ScreenCapture уже запущен. Завершение.")
    print("MIA-ScreenCapture уже запущен.")

    if mode == "gui":
        bring_existing_window_to_front()

    return 0


# VideoRecorderApp переехал в app_runtime (#176); ре-экспорт для
# обратной совместимости: cli/windows_service.py и тесты ссылаются
# на main.VideoRecorderApp.
from app_runtime.video_recorder_app import VideoRecorderApp


def main() -> int:
    """
    Главная точка входа.

    Returns:
        Код выхода
    """
    # Явная bootstrap-загрузка переменных окружения.
    _load_environment()

    # Разбор аргументов командной строки
    config = parse_args()

    # Настройка логирования
    log_level = 20  # INFO
    if config.get("verbose", 0) >= 2:
        log_level = 10  # DEBUG
    elif config.get("quiet", False):
        log_level = 30  # WARNING

    setup_logger(level=log_level)

    # Инициализация конфигурации
    config_path_arg = config.get("config_path")
    config_path = Path(config_path_arg) if config_path_arg else None
    cfg_manager = init_config(config_path)

    # Инициализация языка интерфейса
    cfg_lang = None
    if (
        cfg_manager
        and hasattr(cfg_manager, "settings")
        and hasattr(cfg_manager.settings, "language")
    ):
        cfg_lang = cfg_manager.settings.language

    active_lang = config.get("language") or cfg_lang or "auto"
    set_locale(active_lang)

    mode = config.get("mode", "gui")
    if mode not in _SINGLE_INSTANCE_MODES:
        # CLI-команды (--start/--stop/--status/--schedule-*) проксируются
        # в работающий экземпляр через REST API — мьютекс им не нужен.
        app = VideoRecorderApp(config)
        return app.run()

    guard = SingleInstanceGuard()
    if not guard.acquire():
        return _handle_already_running(mode)

    try:
        app = VideoRecorderApp(config)
        return app.run()
    finally:
        guard.release()


if __name__ == "__main__":
    sys.exit(main())
