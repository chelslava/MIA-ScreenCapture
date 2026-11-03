"""
Модуль глобальных горячих клавиш
================================

Обработка глобальных горячих клавиш на Windows через pynput.
"""

import platform
import threading
from collections.abc import Callable
from enum import Enum
from typing import Any

from logger_config import get_module_logger

logger = get_module_logger(__name__)

# Win32 RegisterHotKey: надёжная альтернатива low-level хукам pynput,
# которые блокируются антивирусами/оверлеями (#159, живая проверка)
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_NOREPEAT = 0x4000


def parse_hotkey_string(hotkey: str) -> tuple[int, int] | None:
    """Разобрать строку хоткея в (модификаторы, VK-код).

    Args:
        hotkey: Строка вида ``<ctrl>+<alt>+d`` (формат pynput).

    Returns:
        Пара (mod, vk) или None, если клавиша не поддерживается.
    """
    modifiers = 0
    vk = 0
    for part in hotkey.split("+"):
        token = part.strip().strip("<>").lower()
        if token == "ctrl":
            modifiers |= MOD_CONTROL
        elif token == "alt":
            modifiers |= MOD_ALT
        elif token == "shift":
            modifiers |= MOD_SHIFT
        elif len(token) == 1 and token.isalnum():
            vk = ord(token.upper())
        else:
            return None
    if vk == 0 or modifiers == 0:
        return None
    return modifiers, vk


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
    TOGGLE_DRAW_OVERLAY = "toggle_draw_overlay"


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
        HotkeyAction.TOGGLE_DRAW_OVERLAY: "<ctrl>+<alt>+d",
    }

    def __init__(self) -> None:
        """Инициализация менеджера горячих клавиш."""
        self._hotkeys: dict[HotkeyAction, str] = {}
        self._callbacks: dict[HotkeyAction, Callable] = {}
        self._listener: Any | None = None
        self._win32_thread: int | None = None
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

        На Windows используется системный RegisterHotKey (без хуков);
        на других платформах — pynput GlobalHotKeys.

        Returns:
            True если успешно запущен
        """
        if self._running:
            return True

        if platform.system() == "Windows":
            return self._start_win32()

        if not PYNPUT_AVAILABLE:
            return False

        try:
            hotkey_map = {}
            for action, hotkey_str in self._hotkeys.items():
                if action in self._callbacks:
                    hotkey_map[hotkey_str] = self._callbacks[action]

            if hotkey_map:

                def on_activate(hotkey: str) -> None:
                    if hotkey in hotkey_map:
                        logger.info("Хоткей сработал: %s", hotkey)
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
        if self._win32_thread is not None:
            try:
                import ctypes

                thread_id = self._win32_thread
                ctypes.windll.user32.PostThreadMessageW(
                    thread_id, WM_QUIT, 0, 0
                )
                self._win32_thread = None
                self._running = False
                logger.info("Горячие клавиши деактивированы")
                return
            except Exception as e:
                logger.warning("Не удалось остановить Win32-хоткеи: %s", e)
        if self._listener:
            try:
                self._listener.stop()
            except Exception as e:
                logger.warning(
                    "Не удалось корректно остановить hotkey listener: %s",
                    e,
                )
            self._listener = None
        self._running = False
        logger.info("Горячие клавиши деактивированы")

    def _start_win32(self) -> bool:
        """Запуск слушателя через RegisterHotKey (Windows)."""
        registered: list[tuple[HotkeyAction, int, int]] = []

        for action, hotkey_str in self._hotkeys.items():
            if action not in self._callbacks:
                continue
            parsed = parse_hotkey_string(hotkey_str)
            if parsed is None:
                logger.warning(
                    "Хоткей %s не поддерживается Win32-слушателем",
                    hotkey_str,
                )
                continue
            registered.append((action, *parsed))

        if not registered:
            logger.warning("Нет зарегистрированных горячих клавиш")
            return True

        callbacks = dict(self._callbacks)
        try:
            import ctypes

            user32 = ctypes.windll.user32

            def listener_loop() -> None:
                import ctypes.wintypes

                msg = ctypes.wintypes.MSG()
                # Регистрация в потоке: хендл окна None == потоковый
                thread_ids: list[int] = []
                for action, mod, vk in registered:
                    hotkey_id = hash(action.value) & 0x7FFFFFFF
                    ok = user32.RegisterHotKey(
                        None, hotkey_id, mod | MOD_NOREPEAT, vk
                    )
                    if ok:
                        thread_ids.append(hotkey_id)
                    else:
                        logger.warning(
                            "Хоткей %s занят другим приложением",
                            action.value,
                        )
                while True:
                    result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                    if result <= 0 or msg.message == WM_QUIT:
                        break
                    if msg.message == WM_HOTKEY:
                        hotkey_id = int(msg.wParam)
                        for action, mod, vk in registered:
                            if hash(action.value) & 0x7FFFFFFF == hotkey_id:
                                logger.info(
                                    "Хоткей сработал: %s", action.value
                                )
                                try:
                                    callbacks[action]()
                                except Exception as e:
                                    logger.error("Ошибка в callback: %s", e)
                for hotkey_id in thread_ids:
                    user32.UnregisterHotKey(None, hotkey_id)

            thread = threading.Thread(
                target=listener_loop, name="win32-hotkeys", daemon=True
            )
            thread.start()
            self._win32_thread = thread.native_id
            self._running = True
            logger.info("Горячие клавиши активированы (RegisterHotKey)")
            return True
        except Exception as e:
            logger.error("Не удалось запустить Win32-хоткеи: %s", e)
            return False

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
