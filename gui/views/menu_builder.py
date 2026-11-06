"""
Меню/тулбар главного окна: desktop actions и горячие клавиши (#164)
====================================================================

Миксин ``MainWindowMenuActionsMixin`` вынесен из ``gui/main_window.py``:
регистрация desktop-действий, tooltips/accessibility-метаданные,
tab order и оконные Qt-шорткаты. ``MainWindow`` наследует миксин,
поэтому все методы остаются доступны как раньше.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from gui.constants import SidebarPage
from gui.controllers.desktop_actions_controller import (
    DesktopActionsController,
)
from gui.desktop_actions import (
    DesktopAction,
    DesktopActionId,
    DesktopActionRegistry,
    get_desktop_action_spec,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from PyQt6.QtWidgets import (
        QLabel,
        QListWidget,
        QMainWindow,
        QPushButton,
        QWidget,
    )

    from gui.models.recording_state import RecordingState
    from gui.views.library_view import LibraryView


if TYPE_CHECKING:
    _QWindowBase = QMainWindow
else:
    # В рантайме миксин — обычный класс (без metaclass-конфликтов
    # с PyQt); QMainWindow приходит от MainWindow напрямую.
    _QWindowBase = object


class MainWindowMenuActionsMixin(_QWindowBase):
    """Регистрация desktop-действий, шорткатов и доступности окна."""

    if TYPE_CHECKING:
        # Общие атрибуты окна
        _desktop_actions: DesktopActionRegistry
        _desktop_actions_controller: DesktopActionsController
        _registered_shortcuts: dict[str, str]
        _tab_navigation_order: list[QWidget]
        _state: RecordingState

        # Виджеты, создаваемые MainWindowUIBuilderMixin._setup_ui
        start_btn: QPushButton
        pause_btn: QPushButton
        stop_btn: QPushButton
        _sidebar: QListWidget
        status_label: QLabel
        _ws_status_label: QLabel
        time_label: QLabel
        library_view: LibraryView

        # Callback-методы MainWindow (регистрируются в desktop actions)
        _show_page: Callable[[SidebarPage], None]
        _start_recording: Callable[[], None]
        _toggle_pause: Callable[[], None]
        _stop_recording: Callable[[], None]
        _open_latest_recording: Callable[[], None]
        _open_recording_folder: Callable[[], None]
        _open_application_logs: Callable[[], None]
        _toggle_draw_overlay: Callable[[], None]

    def _setup_desktop_actions(self) -> None:
        """Создать action registry, shortcuts и accessibility metadata."""
        callbacks = {
            DesktopActionId.START_RECORDING: self._start_recording,
            DesktopActionId.TOGGLE_PAUSE: self._toggle_pause,
            DesktopActionId.STOP_RECORDING: self._stop_recording,
            DesktopActionId.OPEN_LATEST_RECORDING: self._open_latest_recording,
            DesktopActionId.OPEN_RECORDING_FOLDER: self._open_recording_folder,
            DesktopActionId.SHOW_RECORDING_TAB: lambda: self._show_page(
                SidebarPage.RECORD
            ),
            DesktopActionId.SHOW_SCHEDULER_TAB: lambda: self._show_page(
                SidebarPage.SCHEDULER
            ),
            DesktopActionId.SHOW_DIAGNOSTICS_TAB: lambda: self._show_page(
                SidebarPage.DIAGNOSTICS
            ),
            DesktopActionId.SHOW_API_TAB: lambda: self._show_page(
                SidebarPage.API
            ),
            DesktopActionId.OPEN_APP_LOGS: self._open_application_logs,
            DesktopActionId.TOGGLE_DRAW_OVERLAY: (self._toggle_draw_overlay),
        }
        enabled_conditions = {
            DesktopActionId.START_RECORDING: lambda: (
                not self._state.is_recording()
            ),
            DesktopActionId.TOGGLE_PAUSE: lambda: (
                self._state.is_recording() or self._state.is_paused()
            ),
            DesktopActionId.STOP_RECORDING: lambda: (
                self._state.is_recording() or self._state.is_paused()
            ),
        }
        if hasattr(self, "_desktop_actions_controller"):
            self._desktop_actions_controller.registry = self._desktop_actions
            self._desktop_actions_controller.register_default_actions(
                callbacks=callbacks,
                enabled_conditions=enabled_conditions,
            )
        else:
            for action_id, spec in [
                (
                    DesktopActionId.START_RECORDING,
                    get_desktop_action_spec(DesktopActionId.START_RECORDING),
                ),
                (
                    DesktopActionId.TOGGLE_PAUSE,
                    get_desktop_action_spec(DesktopActionId.TOGGLE_PAUSE),
                ),
                (
                    DesktopActionId.STOP_RECORDING,
                    get_desktop_action_spec(DesktopActionId.STOP_RECORDING),
                ),
                (
                    DesktopActionId.OPEN_LATEST_RECORDING,
                    get_desktop_action_spec(
                        DesktopActionId.OPEN_LATEST_RECORDING
                    ),
                ),
                (
                    DesktopActionId.OPEN_RECORDING_FOLDER,
                    get_desktop_action_spec(
                        DesktopActionId.OPEN_RECORDING_FOLDER
                    ),
                ),
                (
                    DesktopActionId.SHOW_RECORDING_TAB,
                    get_desktop_action_spec(
                        DesktopActionId.SHOW_RECORDING_TAB
                    ),
                ),
                (
                    DesktopActionId.SHOW_SCHEDULER_TAB,
                    get_desktop_action_spec(
                        DesktopActionId.SHOW_SCHEDULER_TAB
                    ),
                ),
                (
                    DesktopActionId.SHOW_DIAGNOSTICS_TAB,
                    get_desktop_action_spec(
                        DesktopActionId.SHOW_DIAGNOSTICS_TAB
                    ),
                ),
                (
                    DesktopActionId.SHOW_API_TAB,
                    get_desktop_action_spec(DesktopActionId.SHOW_API_TAB),
                ),
                (
                    DesktopActionId.OPEN_APP_LOGS,
                    get_desktop_action_spec(DesktopActionId.OPEN_APP_LOGS),
                ),
                (
                    DesktopActionId.TOGGLE_DRAW_OVERLAY,
                    get_desktop_action_spec(
                        DesktopActionId.TOGGLE_DRAW_OVERLAY
                    ),
                ),
            ]:
                self._desktop_actions.register(
                    DesktopAction(
                        action_id=action_id,
                        title=spec.title,
                        description=spec.description,
                        callback=callbacks[action_id],
                        shortcut=spec.shortcut,
                        enabled_when=enabled_conditions.get(action_id),
                    )
                )

        self._apply_action_metadata(
            self.start_btn,
            DesktopActionId.START_RECORDING,
        )
        self._apply_action_metadata(
            self.pause_btn,
            DesktopActionId.TOGGLE_PAUSE,
        )
        self._apply_action_metadata(
            self.stop_btn,
            DesktopActionId.STOP_RECORDING,
        )

        if hasattr(self, "_sidebar"):
            self._apply_accessible_metadata(
                self._sidebar,
                "Боковая панель навигации",
                "Позволяет переключаться между записью, планировщиком, "
                "диагностикой и API.",
            )
        self._apply_accessible_metadata(
            self.status_label,
            "Статус записи",
            "Показывает текущее состояние записи и readiness-подсказки.",
        )
        self._apply_accessible_metadata(
            self._ws_status_label,
            "Статус WebSocket",
            "Показывает состояние соединения с API сервером.",
        )
        self._apply_accessible_metadata(
            self.time_label,
            "Таймер записи",
            "Показывает длительность текущей записи.",
        )
        self._apply_accessible_metadata(
            self.library_view,
            "Библиотека записей",
            "Поиск, теги, сортировка и управление записанными файлами.",
        )

        self._configure_tab_order()
        self._register_qt_shortcuts()

    def _apply_action_metadata(
        self,
        widget: QWidget,
        action_id: DesktopActionId,
    ) -> None:
        """Применить tooltip/accessibility metadata для desktop-действия."""
        action = self._desktop_actions.get(action_id)
        tooltip = action.description
        if action.shortcut:
            tooltip = f"{tooltip} Горячая клавиша: {action.shortcut}."
            self._registered_shortcuts[action_id.value] = action.shortcut
        self._apply_accessible_metadata(
            widget,
            action.title,
            action.description,
        )
        widget_any = cast(Any, widget)
        widget_any._tooltip = tooltip
        set_tooltip = getattr(widget, "setToolTip", None)
        if callable(set_tooltip):
            set_tooltip(tooltip)

        set_shortcut = getattr(widget, "setShortcut", None)
        if callable(set_shortcut) and action.shortcut:
            set_shortcut(action.shortcut)
        if action.shortcut:
            widget_any._shortcut = action.shortcut

    def _apply_accessible_metadata(
        self,
        widget: QWidget,
        accessible_name: str,
        accessible_description: str,
    ) -> None:
        """Назначить accessible metadata с fallback для unit-test моков."""
        DesktopActionsController.apply_accessible_metadata(
            widget, accessible_name, accessible_description
        )

    def _configure_tab_order(self) -> None:
        """Настроить логичный tab order для сценариев без мыши."""
        tab_order: list[QWidget] = [
            self.start_btn,
            self.pause_btn,
            self.stop_btn,
        ]
        self._tab_navigation_order = tab_order
        if hasattr(self, "_desktop_actions_controller"):
            self._desktop_actions_controller.configure_tab_order(
                self, tab_order
            )
        else:
            set_tab_order = getattr(self, "setTabOrder", None)
            if callable(set_tab_order):
                for current_widget, next_widget in zip(
                    tab_order,
                    tab_order[1:],
                    strict=False,
                ):
                    set_tab_order(current_widget, next_widget)

    def _register_qt_shortcuts(self) -> None:
        """Зарегистрировать оконные shortcuts для key actions."""
        alt_shortcuts: list[tuple[str, Any]] = [
            ("Alt+R", self.start_btn),
            ("Alt+S", self.stop_btn),
            ("Alt+P", self.pause_btn),
        ]
        if hasattr(self, "_desktop_actions_controller"):
            self._desktop_actions_controller.register_qt_shortcuts(
                self, alt_shortcuts
            )
