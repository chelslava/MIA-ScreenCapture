"""Глобальные горячие клавиши VideoRecorderApp (#176).

Регистрация RegisterHotKey-хоткеев и их обработка в GUI-потоке."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass
from app_runtime.constants import (
    GUI_START_TIMEOUT_SECONDS,
)
from logger_config import get_module_logger

logger = get_module_logger(__name__)


from app_runtime.app_shared_state import AppSharedState


class HotkeysMixin(AppSharedState):
    """Миксин VideoRecorderApp: см. docstring модуля."""

    def _setup_hotkeys(self) -> None:
        """Настройка глобальных горячих клавиш."""
        from gui.hotkeys import GlobalHotkeys, HotkeyAction

        self._hotkeys = GlobalHotkeys()

        if not self._hotkeys.is_available:
            logger.warning("Горячие клавиши недоступны (pynput не установлен)")
            return

        # Все четыре действия DEFAULT_HOTKEYS реально работают (#162):
        # START/STOP ранее не подключались к callback и были мёртвой
        # конфигурацией
        self._hotkeys.register(
            HotkeyAction.TOGGLE_RECORDING,
            self._toggle_recording_hotkey,
        )
        self._hotkeys.register(
            HotkeyAction.PAUSE_RECORDING,
            self._pause_recording_hotkey,
        )
        self._hotkeys.register(
            HotkeyAction.START_RECORDING,
            self._start_recording_hotkey,
        )
        self._hotkeys.register(
            HotkeyAction.STOP_RECORDING,
            self._stop_recording_hotkey,
        )
        self._hotkeys.register(
            HotkeyAction.TOGGLE_DRAW_OVERLAY,
            self._toggle_draw_overlay_hotkey,
        )
        self._hotkeys.start()
        logger.info("Горячие клавиши активированы")

    def _toggle_draw_overlay_hotkey(self) -> None:
        """Режим рисования поверх экрана по горячей клавише (#159).

        Колбек хоткея выполняется в потоке слушателя: любые операции
        Qt обязаны идти в GUI-поток, иначе виджеты создаются в чужом
        потоке и приложение зависает (живая проверка #159).
        """
        if self._main_window:
            self._run_on_gui_thread(
                self._main_window.toggle_draw_overlay_mode,
                timeout=GUI_START_TIMEOUT_SECONDS,
            )

    def _toggle_recording_hotkey(self) -> None:
        """Переключение записи по горячей клавише."""
        facade = self.get_application_facade()
        if self._main_window:
            if facade.get_status().get("is_recording", False):
                result = facade.request_stop_recording()
                logger.info("Хоткей стопа: %s", result)
                if not result.get("success"):
                    error = str(
                        result.get("error", "Не удалось остановить запись")
                    )
                    self._run_on_gui_thread(
                        lambda: self._main_window._show_non_modal_error(error)
                    )
            else:
                facade.request_start_recording()

    def _pause_recording_hotkey(self) -> None:
        """Пауза записи по горячей клавише."""
        facade = self.get_application_facade()
        if self._main_window:
            facade.request_toggle_pause_recording()

    def _start_recording_hotkey(self) -> None:
        """Старт записи по горячей клавише (no-op, если запись идёт)."""
        facade = self.get_application_facade()
        if not self._main_window:
            return
        if facade.get_status().get("is_recording", False):
            logger.info("Хоткей старта: запись уже идёт")
            return
        result = facade.request_start_recording()
        logger.info("Хоткей старта: %s", result)
        if not result.get("success"):
            error = str(result.get("error", "Не удалось запустить запись"))
            self._run_on_gui_thread(
                lambda: self._main_window._show_non_modal_error(error)
            )

    def _stop_recording_hotkey(self) -> None:
        """Стоп записи по горячей клавише (no-op, если записи нет)."""
        facade = self.get_application_facade()
        if not self._main_window:
            return
        if not facade.get_status().get("is_recording", False):
            logger.info("Хоткей стопа: запись не активна")
            return
        result = facade.request_stop_recording()
        logger.info("Хоткей стопа: %s", result)
        if not result.get("success"):
            error = str(result.get("error", "Не удалось остановить запись"))
            self._run_on_gui_thread(
                lambda: self._main_window._show_non_modal_error(error)
            )
