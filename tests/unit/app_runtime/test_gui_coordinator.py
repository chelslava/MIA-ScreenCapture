"""Unit-тесты GuiRuntimeCoordinator (инициализация темы/материала)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app_runtime.gui_coordinator import GuiRuntimeCoordinator


class TestApplyThemeAndBackdrop:
    """Инициализация темы и материала Windows 11 (#157)."""

    @staticmethod
    def _make_coordinator() -> GuiRuntimeCoordinator:
        coordinator = GuiRuntimeCoordinator.__new__(GuiRuntimeCoordinator)
        coordinator._app = SimpleNamespace(_app=MagicMock())
        return coordinator

    def test_enabled_and_supported_sets_active(self, monkeypatch) -> None:
        coordinator = self._make_coordinator()
        config_mock = MagicMock()
        config_mock.settings.win11_backdrop = True
        config_mock.settings.theme = "dark"
        monkeypatch.setattr("config.get_config", lambda: config_mock)
        monkeypatch.setattr(
            "gui.styles.backdrop.backdrop_supported", lambda: True
        )

        with (
            patch("gui.styles.theme.set_backdrop_active") as set_active_mock,
            patch("gui.styles.theme.apply_theme") as apply_mock,
        ):
            coordinator._apply_theme_and_backdrop()

        set_active_mock.assert_called_once_with(True)
        apply_mock.assert_called_once_with(coordinator._app._app, "dark")

    def test_unsupported_os_disables_backdrop(self, monkeypatch) -> None:
        """Win10: настройка включена, но материал не активен."""
        coordinator = self._make_coordinator()
        config_mock = MagicMock()
        config_mock.settings.win11_backdrop = True
        config_mock.settings.theme = "light"
        monkeypatch.setattr("config.get_config", lambda: config_mock)
        monkeypatch.setattr(
            "gui.styles.backdrop.backdrop_supported", lambda: False
        )

        with (
            patch("gui.styles.theme.set_backdrop_active") as set_active_mock,
            patch("gui.styles.theme.apply_theme"),
        ):
            coordinator._apply_theme_and_backdrop()

        set_active_mock.assert_called_once_with(False)

    def test_disabled_setting_disables_backdrop(self, monkeypatch) -> None:
        coordinator = self._make_coordinator()
        config_mock = MagicMock()
        config_mock.settings.win11_backdrop = False
        config_mock.settings.theme = "blue"
        monkeypatch.setattr("config.get_config", lambda: config_mock)
        monkeypatch.setattr(
            "gui.styles.backdrop.backdrop_supported", lambda: True
        )

        with (
            patch("gui.styles.theme.set_backdrop_active") as set_active_mock,
            patch("gui.styles.theme.apply_theme"),
        ):
            coordinator._apply_theme_and_backdrop()

        set_active_mock.assert_called_once_with(False)
