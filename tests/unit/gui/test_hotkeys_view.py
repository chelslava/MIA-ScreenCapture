"""Тесты экрана горячих клавиш."""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

from gui.desktop_actions import (
    DesktopAction,
    DesktopActionId,
    DesktopActionRegistry,
)
from gui.views.hotkeys_view import GLOBAL_HOTKEYS, HotkeysView


def _build_hotkeys_view(
    registry: DesktopActionRegistry,
) -> HotkeysView:
    """Создать HotkeysView без вызова Qt-инициализации."""
    view = HotkeysView.__new__(HotkeysView)
    view._desktop_actions = registry
    return view


class TestGlobalHotkeysConstant:
    """Проверки статичного списка глобальных горячих клавиш."""

    def test_contains_toggle_and_pause(self) -> None:
        """Должны быть ровно те 2 действия, что реально зарегистрированы
        в main.py:_setup_hotkeys (а не все 4 DEFAULT_HOTKEYS)."""
        shortcuts = dict(GLOBAL_HOTKEYS)
        assert shortcuts["Переключить запись (старт/стоп)"] == "Ctrl+Alt+T"
        assert shortcuts["Пауза/продолжить запись"] == "Ctrl+Alt+P"
        assert len(GLOBAL_HOTKEYS) == 2


class TestAppHotkeyRows:
    """Проверки отбора строк in-app горячих клавиш из desktop_actions."""

    def test_includes_only_actions_with_shortcut(self) -> None:
        """Действия без shortcut не должны попадать в таблицу."""
        registry = DesktopActionRegistry()
        registry.register(
            DesktopAction(
                action_id=DesktopActionId.START_RECORDING,
                title="Начать запись",
                description="...",
                callback=lambda: None,
                shortcut="Ctrl+R",
            )
        )
        registry.register(
            DesktopAction(
                action_id=DesktopActionId.STOP_RECORDING,
                title="Без shortcut",
                description="...",
                callback=lambda: None,
                shortcut=None,
            )
        )
        view = _build_hotkeys_view(registry)

        rows = view._app_hotkey_rows()

        assert rows == (("Начать запись", "Ctrl+R"),)

    def test_empty_registry_yields_no_rows(self) -> None:
        """Пустой реестр действий не должен ломать построение строк."""
        view = _build_hotkeys_view(DesktopActionRegistry())

        assert view._app_hotkey_rows() == ()


class TestHotkeysViewConstruction:
    """Проверки реальной сборки диалога в (мокированном) PyQt6."""

    def test_construction_does_not_raise(self, qapp: QApplication) -> None:
        """Диалог должен собираться без ошибок с пустым и непустым реестром."""
        registry = DesktopActionRegistry()
        registry.register(
            DesktopAction(
                action_id=DesktopActionId.START_RECORDING,
                title="Начать запись",
                description="...",
                callback=lambda: None,
                shortcut="Ctrl+R",
            )
        )

        view = HotkeysView(registry)

        assert view.windowTitle() == "Горячие клавиши"
        assert view.isModal() is False
