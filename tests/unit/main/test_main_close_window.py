"""Unit тесты обработки закрытия главного окна (#94/#90)."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import main


class _FakeEvent:
    """Минимальный контракт QCloseEvent для тестов обработчика."""

    def __init__(self) -> None:
        self.accepted_calls = 0
        self.ignored_calls = 0

    def accept(self) -> None:
        self.accepted_calls += 1

    def ignore(self) -> None:
        self.ignored_calls += 1


@pytest.fixture
def fake_config() -> SimpleNamespace:
    """Конфиг с настройкой minimize_to_tray по умолчанию."""
    cfg = SimpleNamespace(
        settings=SimpleNamespace(minimize_to_tray=True),
        save=MagicMock(return_value=True),
    )
    return cfg


@pytest.fixture
def app(
    fake_config: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> main.VideoRecorderApp:
    """Экземпляр VideoRecorderApp с подменённым get_config."""
    monkeypatch.setattr(main, "get_config", lambda: fake_config)
    monkeypatch.setattr("config.get_config", lambda: fake_config)
    instance = main.VideoRecorderApp.__new__(main.VideoRecorderApp)
    instance._main_window = MagicMock()
    instance._tray_icon = MagicMock()
    instance._app = MagicMock()
    instance._running = True
    return instance


class TestHandleCloseRequested:
    """Группа: _handle_close_requested решает сворачивание vs выход."""

    def test_default_minimize_to_tray_ignores_event(
        self, app: main.VideoRecorderApp
    ) -> None:
        """При minimize_to_tray=True событие игнорируется и окно скрыто."""
        event = _FakeEvent()
        app._handle_close_requested(event)  # type: ignore[arg-type]

        assert event.ignored_calls == 1
        assert event.accepted_calls == 0
        app._main_window.hide.assert_called_once()
        app._tray_icon.show_notification.assert_called_once()

    def test_minimize_to_tray_disabled_quits_app(
        self,
        app: main.VideoRecorderApp,
        fake_config: SimpleNamespace,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """При minimize_to_tray=False завершает приложение."""
        fake_config.settings.minimize_to_tray = False
        quit_mock = MagicMock()
        monkeypatch.setattr(app, "_quit_app", quit_mock)

        event = _FakeEvent()
        app._handle_close_requested(event)  # type: ignore[arg-type]

        quit_mock.assert_called_once()
        assert event.ignored_calls == 0

    def test_no_tray_icon_falls_back_to_quit(
        self, app: main.VideoRecorderApp, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Если трея нет, завершаем приложение, даже если minimize=True."""
        app._tray_icon = None
        quit_mock = MagicMock()
        monkeypatch.setattr(app, "_quit_app", quit_mock)

        event = _FakeEvent()
        app._handle_close_requested(event)  # type: ignore[arg-type]

        quit_mock.assert_called_once()

    def test_force_minimize_overrides_disabled_setting(
        self,
        app: main.VideoRecorderApp,
        fake_config: SimpleNamespace,
    ) -> None:
        """force_minimize_to_tray перекрывает отключённую настройку."""
        fake_config.settings.minimize_to_tray = False

        event = _FakeEvent()
        payload = {"event": event, "force_minimize_to_tray": True}
        app._handle_close_requested(payload)  # type: ignore[arg-type]

        assert event.ignored_calls == 1
        app._main_window.hide.assert_called_once()

    def test_dict_payload_without_force_respects_config(
        self,
        app: main.VideoRecorderApp,
        fake_config: SimpleNamespace,
    ) -> None:
        """Словарный payload без force уважает настройку minimize_to_tray."""
        fake_config.settings.minimize_to_tray = True

        event = _FakeEvent()
        payload = {"event": event, "force_minimize_to_tray": False}
        app._handle_close_requested(payload)  # type: ignore[arg-type]

        assert event.ignored_calls == 1

    def test_none_event_is_safe_noop(self, app: main.VideoRecorderApp) -> None:
        """Payload без event не приводит к падению."""
        payload = {"event": None}
        # Не должно падать
        app._handle_close_requested(payload)  # type: ignore[arg-type]
