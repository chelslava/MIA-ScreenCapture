"""
Модуль глобальных горячих клавиш
================================

Обработка глобальных горячих клавиш на Windows через pynput.
"""

from collections.abc import Callable
from enum import Enum
from typing import Any

from logger_config import get_module_logger

logger = get_module_logger(__name__)

try:
    from pynput import keyboard

    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    logger.warning("pynput не установлен, горячие клавиши недоступны")


class HotkeyAction(Enum):
    """Действия горячих клавиш."""

    START_RECORDING = "start_recording"
    STOP_RECORDING = "stop_recording"
    PAUSE_RECORDING = "pause_recording"
    TOGGLE_RECORDING = "toggle_recording"


class GlobalHotkeys:
    """
    Менеджер глобальных горячих клавиш.

    Позволяет регистрировать горячие клавиши, работающие
    даже когда приложение не в фокусе.
    """

    DEFAULT_HOTKEYS = {
        HotkeyAction.START_RECORDING: "<ctrl>+<alt>+r",
        HotkeyAction.STOP_RECORDING: "<ctrl>+<alt>+s",
        HotkeyAction.PAUSE_RECORDING: "<ctrl>+<alt>+p",
        HotkeyAction.TOGGLE_RECORDING: "<ctrl>+<alt>+t",
    }

    def __init__(self) -> None:
        """Инициализация менеджера горячих клавиш."""
        self._hotkeys: dict[HotkeyAction, str] = {}
        self._callbacks: dict[HotkeyAction, Callable] = {}
        self._listener: Any | None = None
        self._running = False

        if PYNPUT_AVAILABLE:
            self._hotkeys = self.DEFAULT_HOTKEYS.copy()

    @property
    def is_available(self) -> bool:
        """Проверка доступности горячих клавиш."""
        return PYNPUT_AVAILABLE

    def register(
        self,
        action: HotkeyAction,
        callback: Callable,
        hotkey: str | None = None,
    ) -> bool:
        """
        Регистрация горячей клавиши.

        Args:
            action: Действие
            callback: Функция обратного вызова
            hotkey: Комбинация клавиш (опционально)

        Returns:
            True если успешно зарегистрировано
        """
        if not PYNPUT_AVAILABLE:
            return False

        self._callbacks[action] = callback
        if hotkey:
            self._hotkeys[action] = hotkey

        logger.info(
            f"Зарегистрирована горячая клавиша: {action.value} -> {hotkey}"
        )
        return True

    def unregister(self, action: HotkeyAction) -> None:
        """
        Отмена регистрации горячей клавиши.

        Args:
            action: Действие для отмены
        """
        if action in self._callbacks:
            del self._callbacks[action]
            logger.info(f"Отменена регистрация: {action.value}")

    def start(self) -> bool:
        """
        Запуск слушателя горячих клавиш.

        Returns:
            True если успешно запущен
        """
        if not PYNPUT_AVAILABLE:
            return False

        if self._running:
            return True

        try:
            hotkey_map = {}
            for action, hotkey_str in self._hotkeys.items():
                if action in self._callbacks:
                    hotkey_map[hotkey_str] = self._callbacks[action]

            if hotkey_map:

                def on_activate(hotkey: str) -> None:
                    if hotkey in hotkey_map:
                        try:
                            hotkey_map[hotkey]()
                        except Exception as e:
                            logger.error(f"Ошибка в callback: {e}")

                listener = keyboard.GlobalHotKeys(
                    {k: lambda k=k: on_activate(k) for k in hotkey_map}
                )
                listener.start()
                self._listener = listener
                self._running = True
                logger.info("Горячие клавиши активированы")
                return True
            else:
                logger.warning("Нет зарегистрированных горячих клавиш")
                return True

        except Exception as e:
            logger.error(f"Ошибка запуска горячих клавиш: {e}")
            return False

    def stop(self) -> None:
        """Остановка слушателя горячих клавиш."""
        if self._listener:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        self._running = False
        logger.info("Горячие клавиши деактивированы")

    def get_hotkey(self, action: HotkeyAction) -> str | None:
        """
        Получение комбинации клавиш для действия.

        Args:
            action: Действие

        Returns:
            Комбинация клавиш или None
        """
        return self._hotkeys.get(action)

    def set_hotkey(self, action: HotkeyAction, hotkey: str) -> None:
        """
        Установка новой комбинации клавиш.

        Args:
            action: Действие
            hotkey: Новая комбинация клавиш
        """
        self._hotkeys[action] = hotkey
        logger.info(f"Изменена горячая клавиша {action.value}: {hotkey}")
