"""
Unit-тесты для DesktopActionsController
======================================
"""

from __future__ import annotations

from unittest.mock import MagicMock

from PyQt6.QtWidgets import QPushButton, QWidget

from gui.controllers.desktop_actions_controller import DesktopActionsController
from gui.desktop_actions import DesktopActionId


class TestDesktopActionsController:
    """Тесты контроллера desktop-действий и доступности."""

    def test_register_default_actions(self) -> None:
        ctrl = DesktopActionsController()
        cb = MagicMock()
        callbacks = {
            DesktopActionId.START_RECORDING: cb,
            DesktopActionId.TOGGLE_PAUSE: cb,
            DesktopActionId.STOP_RECORDING: cb,
        }

        ctrl.register_default_actions(callbacks)

        assert ctrl.registry.get(DesktopActionId.START_RECORDING) is not None
        assert ctrl.registry.get(DesktopActionId.TOGGLE_PAUSE) is not None
        assert ctrl.registry.get(DesktopActionId.STOP_RECORDING) is not None

    def test_apply_action_metadata(self) -> None:
        ctrl = DesktopActionsController()
        cb = MagicMock()
        ctrl.register_default_actions({DesktopActionId.START_RECORDING: cb})

        btn = QPushButton()
        ctrl.apply_action_metadata(btn, DesktopActionId.START_RECORDING)

        assert getattr(btn, "_accessible_name", None) is not None
        assert getattr(btn, "_tooltip", None) is not None

    def test_configure_tab_order(self) -> None:
        ctrl = DesktopActionsController()
        parent = QWidget()
        b1 = QPushButton(parent)
        b2 = QPushButton(parent)

        ctrl.configure_tab_order(parent, [b1, b2])
        assert ctrl.tab_navigation_order == [b1, b2]
