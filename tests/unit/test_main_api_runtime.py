"""
Unit тесты runtime-управления API из main.py.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import main


class FakeRecordingService:
    """Лёгкая замена RecordingService для unit-тестов."""

    def __init__(self, backend: object) -> None:
        self.backend = backend
        self.event_bus = object()


class FakeWebSocketManager:
    """Заглушка WebSocketManager без реального транспорта."""

    def __init__(self) -> None:
        self.attached_event_bus: object | None = None

    def attach_event_bus(self, event_bus: object) -> None:
        self.attached_event_bus = event_bus


class FakeApiServer:
    """Фейковый APIServer для проверки runtime-сценариев."""

    instances: list["FakeApiServer"] = []

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5000,
        api_key: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.api_key = api_key.strip() if api_key and api_key.strip() else None
        self.app = SimpleNamespace(name="fake-app")
        self.callbacks: dict[str, object] = {}
        self.websocket_manager: object | None = None
        self._running = False
        self.start_calls = 0
        self.stop_calls = 0
        FakeApiServer.instances.append(self)

    def set_websocket_manager(self, manager: object) -> None:
        self.websocket_manager = manager

    def set_callback(self, action: str, callback: object) -> None:
        self.callbacks[action] = callback

    def is_running(self) -> bool:
        return self._running

    def start(self) -> bool:
        self.start_calls += 1
        self._running = True
        return True

    def stop(self) -> None:
        self.stop_calls += 1
        self._running = False

    def get_status(self) -> dict[str, object]:
        return {
            "running": self._running,
            "host": self.host,
            "port": self.port,
            "url": self.get_url(),
            "api_key_set": bool(self.api_key),
        }

    def get_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def get_api_key(self) -> str | None:
        if self.api_key is not None:
            return self.api_key
        return "generated-api-key"

    def set_api_key(self, api_key: str | None) -> None:
        self.api_key = api_key.strip() if api_key and api_key.strip() else None


def _build_app(
    monkeypatch: pytest.MonkeyPatch,
    *,
    enabled: bool = True,
    host: str = "127.0.0.1",
    port: int = 5000,
    api_key: str | None = None,
    cli_api: dict[str, object] | None = None,
) -> tuple[main.VideoRecorderApp, SimpleNamespace]:
    """Создаёт приложение с моками для runtime-тестов API."""
    fake_api = SimpleNamespace(
        enabled=enabled,
        host=host,
        port=port,
        api_key=api_key,
    )
    fake_config = SimpleNamespace(
        settings=SimpleNamespace(api=fake_api),
        save=MagicMock(),
    )

    monkeypatch.setattr(main, "get_config", lambda: fake_config)
    monkeypatch.setattr(main, "RecordingService", FakeRecordingService)
    monkeypatch.setattr(main, "GUIRecordingBackend", lambda: object())
    monkeypatch.setattr(main, "WebSocketManager", FakeWebSocketManager)
    FakeApiServer.instances.clear()

    app = main.VideoRecorderApp({"mode": "gui", "api": cli_api or {}})
    return app, fake_config


class TestMainApiRuntime:
    """Тесты runtime-управления API сервера из main.py."""

    def test_get_effective_api_key_prefers_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Переменная окружения должна иметь приоритет над конфигом."""
        app, _ = _build_app(monkeypatch, api_key="config-token")

        monkeypatch.setenv("MIA_API_KEY", "env-token")

        assert app._get_effective_api_key() == "env-token"

    def test_get_effective_api_key_falls_back_to_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """При отсутствии env токен берётся из конфигурации."""
        app, _ = _build_app(monkeypatch, api_key="config-token")

        monkeypatch.delenv("MIA_API_KEY", raising=False)

        assert app._get_effective_api_key() == "config-token"

    def test_start_api_server_skips_when_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Отключённый API не должен создавать сервер без force."""
        app, _ = _build_app(monkeypatch, enabled=False, api_key="config-token")

        def _fail_if_called(*args: object, **kwargs: object) -> None:
            raise AssertionError("APIServer не должен создаваться")

        monkeypatch.setattr("api.server.APIServer", _fail_if_called)

        result = app._start_api_server()

        assert result == {"success": False, "running": False}
        assert app._api_server is None

    def test_start_api_server_uses_env_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """При старте должен использоваться токен из переменной окружения."""
        app, fake_config = _build_app(monkeypatch, api_key="config-token")
        monkeypatch.setenv("MIA_API_KEY", "env-token")
        monkeypatch.setattr("api.server.APIServer", FakeApiServer)
        register_routes_mock = MagicMock()
        monkeypatch.setattr("api.routes.register_routes", register_routes_mock)

        result = app._start_api_server(force=True)

        assert result["success"] is True
        assert isinstance(app._api_server, FakeApiServer)
        assert app._api_server.api_key == "env-token"
        assert app._api_server.start_calls == 1
        assert app._api_server.websocket_manager is app._websocket_manager
        assert fake_config.settings.api.api_key == "config-token"
        assert fake_config.save.call_count == 0
        assert result["status"]["configured"]["api_key"] == "env-token"
        register_routes_mock.assert_called_once_with(
            app._api_server.app, app._api_server
        )

    def test_start_api_server_stores_generated_key_in_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Сгенерированный сервером токен должен попасть в env и конфиг."""
        app, fake_config = _build_app(monkeypatch, api_key=None)
        monkeypatch.delenv("MIA_API_KEY", raising=False)
        monkeypatch.setattr("api.server.APIServer", FakeApiServer)
        monkeypatch.setattr("api.routes.register_routes", lambda *args: None)

        result = app._start_api_server(force=True)

        assert result["success"] is True
        assert fake_config.settings.api.api_key == "generated-api-key"
        assert fake_config.save.call_count == 1
        assert app._get_effective_api_key() == "generated-api-key"
        assert main.os.environ["MIA_API_KEY"] == "generated-api-key"

    def test_start_api_server_returns_existing_status_when_running(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Запущенный сервер не должен создаваться повторно."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        server = FakeApiServer(api_key="config-token")
        server._running = True
        app._api_server = server

        def _fail_if_called(*args: object, **kwargs: object) -> None:
            raise AssertionError("APIServer не должен создаваться повторно")

        monkeypatch.setattr("api.server.APIServer", _fail_if_called)

        result = app._start_api_server()

        assert result["success"] is True
        assert result["status"]["running"] is True
        assert app._api_server is server

    def test_apply_api_settings_updates_env_and_config(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Изменение токена в GUI должно обновлять конфиг и env."""
        app, fake_config = _build_app(monkeypatch, api_key="old-token")
        server = FakeApiServer(api_key="old-token")
        server._running = True
        app._api_server = server
        app._main_window = SimpleNamespace(_api_server=server)

        monkeypatch.setenv("MIA_API_KEY", "old-token")

        result = app._apply_api_settings({"port": 5051, "token": "new-token"})

        assert result["success"] is True
        assert result["restart_required"] is True
        assert "port" in result["updated_fields"]
        assert "api_key" in result["updated_fields"]
        assert fake_config.settings.api.port == 5051
        assert fake_config.settings.api.api_key == "new-token"
        assert main.os.environ["MIA_API_KEY"] == "new-token"
        assert server.api_key == "new-token"
        assert server.callbacks == {}

    def test_apply_api_settings_clears_env_when_token_removed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Пустой токен должен очищать переменную окружения."""
        app, fake_config = _build_app(monkeypatch, api_key="old-token")
        server = FakeApiServer(api_key="old-token")
        app._api_server = server

        monkeypatch.setenv("MIA_API_KEY", "old-token")

        result = app._apply_api_settings({"token": ""})

        assert result["success"] is True
        assert fake_config.settings.api.api_key is None
        assert "MIA_API_KEY" not in main.os.environ
        assert server.api_key is None

    def test_stop_api_server_clears_server_reference(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Остановка сервера должна освобождать ссылки на экземпляр."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        server = FakeApiServer(api_key="config-token")
        server._running = True
        app._api_server = server
        app._main_window = SimpleNamespace(_api_server=server)

        result = app._stop_api_server()

        assert result == {"success": True, "running": False}
        assert server.stop_calls == 1
        assert app._api_server is None
        assert app._main_window._api_server is None

    def test_restart_api_server_calls_forced_start(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Перезапуск должен использовать force=True при старте."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        stop_mock = MagicMock(return_value={"success": True, "running": False})
        start_mock = MagicMock(
            return_value={"success": True, "status": {"running": True}}
        )
        app._stop_api_server = stop_mock
        app._start_api_server = start_mock

        result = app._restart_api_server()

        stop_mock.assert_called_once()
        start_mock.assert_called_once_with(force=True)
        assert result == {"success": True, "status": {"running": True}}

    def test_stop_recording_uses_extended_gui_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Остановка записи через API должна ждать дольше 10 секунд."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        stop_result = {"success": True, "filepath": "out.mp4"}
        app._main_window = SimpleNamespace(
            stop_recording=MagicMock(return_value=stop_result)
        )
        run_on_gui_thread_mock = MagicMock(return_value=stop_result)
        app._run_on_gui_thread = run_on_gui_thread_mock

        result = app._stop_recording()

        run_on_gui_thread_mock.assert_called_once()
        _, kwargs = run_on_gui_thread_mock.call_args
        assert kwargs["timeout"] == 60.0
        assert result == stop_result
