"""
Контроллер desktop-действий, горячих клавиш и доступности (Accessibility)
========================================================================

Отвечает за:
- регистрацию системных desktop-действий в едином реестре;
- привязку горячих клавиш (QShortcut) и настройку порядка обхода табуляцией (Tab Order);
- назначение метаданных доступности (AccessibleName, AccessibleDescription, Tooltip).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from PyQt6.QtWidgets import QWidget

from gui.desktop_actions import (
    DesktopAction,
    DesktopActionId,
    DesktopActionRegistry,
    get_desktop_action_spec,
)

if TYPE_CHECKING:
    from collections.abc import Callable


class DesktopActionsController:
    """Контроллер управления desktop-действиями, shortcuts и доступностью."""

    def __init__(
        self,
        registry: DesktopActionRegistry | None = None,
    ) -> None:
        self._registry = registry or DesktopActionRegistry()
        self._registered_shortcuts: dict[str, str] = {}
        self._qt_shortcuts: list[Any] = []
        self._tab_navigation_order: list[QWidget] = []

    @property
    def registry(self) -> DesktopActionRegistry:
        """Реестр зарегистрированных действий."""
        return self._registry

    @registry.setter
    def registry(self, value: DesktopActionRegistry) -> None:
        """Установить новый реестр действий."""
        self._registry = value

    @property
    def registered_shortcuts(self) -> dict[str, str]:
        """Словарь зарегистрированных горячих клавиш."""
        return self._registered_shortcuts

    @property
    def tab_navigation_order(self) -> list[QWidget]:
        """Список элементов в порядке обхода Tab."""
        return self._tab_navigation_order

    def register_default_actions(
        self,
        callbacks: dict[DesktopActionId, Callable[[], None]],
        enabled_conditions: dict[DesktopActionId, Callable[[], bool]]
        | None = None,
    ) -> None:
        """Регистрирует стандартный набор desktop-действий приложения."""
        enabled_conditions = enabled_conditions or {}

        for action_id, callback in callbacks.items():
            spec = get_desktop_action_spec(action_id)
            enabled_when = enabled_conditions.get(action_id)
            self._registry.register(
                DesktopAction(
                    action_id=action_id,
                    title=spec.title,
                    description=spec.description,
                    callback=callback,
                    shortcut=spec.shortcut,
                    enabled_when=enabled_when,
                )
            )

    def apply_action_metadata(
        self,
        widget: QWidget,
        action_id: DesktopActionId,
    ) -> None:
        """Применить tooltip/accessibility metadata для desktop-действия."""
        action = self._registry.get(action_id)
        tooltip = action.description
        if action.shortcut:
            tooltip = f"{tooltip} Горячая клавиша: {action.shortcut}."
            self._registered_shortcuts[action_id.value] = action.shortcut

        self.apply_accessible_metadata(
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

    @staticmethod
    def apply_accessible_metadata(
        widget: QWidget,
        accessible_name: str,
        accessible_description: str,
    ) -> None:
        """Назначить accessible metadata с fallback для unit-test моков."""
        widget_any = cast(Any, widget)
        widget_any._accessible_name = accessible_name
        widget_any._accessible_description = accessible_description
        set_name = getattr(widget, "setAccessibleName", None)
        if callable(set_name):
            set_name(accessible_name)

        set_description = getattr(widget, "setAccessibleDescription", None)
        if callable(set_description):
            set_description(accessible_description)

    def configure_tab_order(
        self,
        parent: QWidget,
        widgets: list[QWidget],
    ) -> None:
        """Настроить логичный tab order для элементов управления."""
        self._tab_navigation_order = widgets
        set_tab_order = getattr(parent, "setTabOrder", None)
        if callable(set_tab_order):
            for current_widget, next_widget in zip(
                widgets,
                widgets[1:],
                strict=False,
            ):
                set_tab_order(current_widget, next_widget)

    def register_qt_shortcuts(
        self,
        parent: QWidget,
        alt_shortcuts: list[tuple[str, Any]] | None = None,
    ) -> None:
        """Зарегистрировать оконные shortcuts для действий и кнопок."""
        self._qt_shortcuts.clear()
        try:
            from PyQt6.QtGui import QKeySequence, QShortcut
        except Exception:
            return

        for action in self._registry.all():
            if not action.shortcut:
                continue
            try:
                shortcut = QShortcut(QKeySequence(action.shortcut), parent)
                shortcut.activated.connect(
                    lambda action_id=action.action_id: self._registry.execute(
                        action_id
                    )
                )
                self._qt_shortcuts.append(shortcut)
            except Exception:
                continue

        if alt_shortcuts:
            for key_seq, target in alt_shortcuts:
                try:
                    shortcut = QShortcut(QKeySequence(key_seq), parent)
                    shortcut.activated.connect(
                        lambda t=target: (
                            t.click() if hasattr(t, "click") else t()
                        )
                    )
                    self._qt_shortcuts.append(shortcut)
                except Exception:
                    continue
