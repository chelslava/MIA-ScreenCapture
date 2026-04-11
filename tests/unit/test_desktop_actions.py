"""Тесты реестра desktop-действий GUI."""

from gui.desktop_actions import (
    DesktopAction,
    DesktopActionId,
    DesktopActionRegistry,
    get_desktop_action_spec,
)


class TestDesktopActionRegistry:
    """Проверки регистрации и dispatch desktop-действий."""

    def test_execute_registered_action(self) -> None:
        """Зарегистрированное действие должно выполняться."""
        registry = DesktopActionRegistry()
        called: list[str] = []
        registry.register(
            DesktopAction(
                action_id=DesktopActionId.START_RECORDING,
                title="Старт",
                description="Запускает запись.",
                callback=lambda: called.append("start"),
                shortcut="Ctrl+R",
            )
        )

        result = registry.execute(DesktopActionId.START_RECORDING)

        assert result is True
        assert called == ["start"]

    def test_execute_disabled_action_returns_false(self) -> None:
        """Отключённое действие не должно выполняться."""
        registry = DesktopActionRegistry()
        called: list[str] = []
        registry.register(
            DesktopAction(
                action_id=DesktopActionId.STOP_RECORDING,
                title="Стоп",
                description="Останавливает запись.",
                callback=lambda: called.append("stop"),
                enabled_when=lambda: False,
            )
        )

        result = registry.execute(DesktopActionId.STOP_RECORDING)

        assert result is False
        assert called == []

    def test_default_specs_expose_shortcuts_for_key_actions(self) -> None:
        """Статические action specs должны содержать ожидаемые shortcuts."""
        assert (
            get_desktop_action_spec(
                DesktopActionId.START_RECORDING
            ).shortcut
            == "Ctrl+R"
        )
        assert (
            get_desktop_action_spec(
                DesktopActionId.SHOW_DIAGNOSTICS_TAB
            ).shortcut
            == "Alt+3"
        )
