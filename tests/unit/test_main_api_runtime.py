"""
Unit тесты runtime-управления API из main.py.
"""

import os
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
        server_threads: int = 4,
        api_key: str | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.server_threads = server_threads
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

    def get_runtime_api_key(self) -> str | None:
        return self.get_api_key()

    def set_api_key(self, api_key: str | None) -> None:
        self.api_key = api_key.strip() if api_key and api_key.strip() else None


class MaskedApiServer(FakeApiServer):
    """Фейковый сервер, возвращающий маскированный ключ для UI."""

    def get_api_key(self) -> str | None:
        if self.api_key is None:
            return None
        return "****"

    def get_runtime_api_key(self) -> str | None:
        return self.api_key


def _build_app(
    monkeypatch: pytest.MonkeyPatch,
    *,
    enabled: bool = True,
    host: str = "127.0.0.1",
    port: int = 5000,
    api_key: str | None = None,
    server_threads: int = 4,
    cli_api: dict[str, object] | None = None,
    scheduler_max_concurrent_tasks: int = 1,
) -> tuple[main.VideoRecorderApp, SimpleNamespace]:
    """Создаёт приложение с моками для runtime-тестов API."""
    fake_api = SimpleNamespace(
        enabled=enabled,
        host=host,
        port=port,
        server_threads=server_threads,
        api_key=api_key,
    )
    fake_config = SimpleNamespace(
        settings=SimpleNamespace(
            api=fake_api,
            scheduler=SimpleNamespace(
                max_concurrent_tasks=scheduler_max_concurrent_tasks
            ),
        ),
        config_path="config/config.json",
        save=MagicMock(),
    )

    monkeypatch.setattr(main, "get_config", lambda: fake_config)
    monkeypatch.setattr(main, "RecordingService", FakeRecordingService)
    monkeypatch.setattr(main, "GUIRecordingBackend", lambda: object())
    monkeypatch.setattr(main, "WebSocketManager", FakeWebSocketManager)
    stored_key: dict[str, str | None] = {"value": None}

    def _get_stored_key() -> str | None:
        env_key = os.environ.get("MIA_API_KEY")
        if env_key is not None and env_key.strip():
            return env_key.strip()
        return stored_key["value"]

    def _set_stored_key(value: str | None) -> None:
        normalized = value.strip() if value and value.strip() else None
        stored_key["value"] = normalized
        if normalized is not None:
            monkeypatch.setenv("MIA_API_KEY", normalized)
            return
        monkeypatch.delenv("MIA_API_KEY", raising=False)

    monkeypatch.setattr(main, "get_stored_api_key", _get_stored_key)
    monkeypatch.setattr(main, "set_stored_api_key", _set_stored_key)
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
        app, fake_config = _build_app(monkeypatch, api_key="config-token")

        monkeypatch.delenv("MIA_API_KEY", raising=False)

        assert app._get_effective_api_key() == "config-token"
        assert fake_config.settings.api.api_key is None
        assert fake_config.save.call_count == 1

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
        assert app._api_server.server_threads == 4
        register_routes_mock.assert_called_once_with(
            app._api_server.app, app._api_server
        )

    def test_start_api_server_registers_expected_callbacks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """При старте API должны регистрироваться все runtime callbacks."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        monkeypatch.setenv("MIA_API_KEY", "env-token")
        monkeypatch.setattr("api.server.APIServer", FakeApiServer)
        monkeypatch.setattr("api.routes.register_routes", lambda *args: None)

        result = app._start_api_server(force=True)

        assert result["success"] is True
        assert isinstance(app._api_server, FakeApiServer)
        assert set(app._api_server.callbacks.keys()) == {
            "status",
            "start",
            "stop",
            "pause",
            "recordings",
            "get_schedule",
            "create_schedule",
            "delete_schedule",
            "update_schedule",
            "toggle_schedule",
            "devices",
            "windows",
            "get_config",
            "update_config",
        }

    def test_start_api_server_stores_generated_key_in_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Сгенерированный сервером токен должен попасть в env."""
        app, fake_config = _build_app(monkeypatch, api_key=None)
        monkeypatch.delenv("MIA_API_KEY", raising=False)
        monkeypatch.setattr("api.server.APIServer", FakeApiServer)
        monkeypatch.setattr("api.routes.register_routes", lambda *args: None)

        result = app._start_api_server(force=True)

        assert result["success"] is True
        assert fake_config.settings.api.api_key is None
        assert fake_config.save.call_count == 1
        assert app._get_effective_api_key() == "generated-api-key"
        assert os.environ["MIA_API_KEY"] == "generated-api-key"

    def test_start_api_server_uses_runtime_key_for_env_sync(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """При синхронизации должен использоваться немаскированный ключ."""
        app, _ = _build_app(monkeypatch, api_key="test1234")
        monkeypatch.delenv("MIA_API_KEY", raising=False)
        monkeypatch.setattr("api.server.APIServer", MaskedApiServer)
        monkeypatch.setattr("api.routes.register_routes", lambda *args: None)

        result = app._start_api_server(force=True)

        assert result["success"] is True
        assert os.environ["MIA_API_KEY"] == "test1234"

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
        """Изменение токена в GUI должно обновлять хранилище и env."""
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
        assert fake_config.settings.api.api_key is None
        assert os.environ["MIA_API_KEY"] == "new-token"
        assert server.api_key == "new-token"
        assert server.callbacks == {}

    def test_apply_api_settings_updates_server_threads(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Изменение server_threads обновляет конфиг и требует рестарт."""
        app, fake_config = _build_app(monkeypatch, server_threads=4)
        server = FakeApiServer(server_threads=4)
        server._running = True
        app._api_server = server

        result = app._apply_api_settings({"server_threads": 6})

        assert result["success"] is True
        assert result["restart_required"] is True
        assert "server_threads" in result["updated_fields"]
        assert fake_config.settings.api.server_threads == 6

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
        assert "MIA_API_KEY" not in os.environ
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

    def test_get_api_controls_returns_expected_actions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GUI должен получать полный набор API-контролов."""
        app, _ = _build_app(monkeypatch, api_key="config-token")

        start_mock = MagicMock(return_value={"success": True})
        stop_mock = MagicMock(return_value={"success": True})
        restart_mock = MagicMock(return_value={"success": True})
        apply_settings_mock = MagicMock(return_value={"success": True})
        get_status_mock = MagicMock(return_value={"success": True})
        open_logs_mock = MagicMock()

        app._start_api_server = start_mock
        app._stop_api_server = stop_mock
        app._restart_api_server = restart_mock
        app._apply_api_settings = apply_settings_mock
        app._get_api_status = get_status_mock
        app._open_api_logs_folder = open_logs_mock

        controls = app.get_api_controls()

        assert set(controls.keys()) == {
            "get_status",
            "apply_settings",
            "start",
            "stop",
            "restart",
            "open_logs",
        }

        controls["get_status"]()
        controls["apply_settings"]({"port": 5011})
        controls["start"]()
        controls["stop"]()
        controls["restart"]()
        controls["open_logs"]()

        get_status_mock.assert_called_once_with()
        apply_settings_mock.assert_called_once_with({"port": 5011})
        start_mock.assert_called_once_with(force=True)
        stop_mock.assert_called_once_with()
        restart_mock.assert_called_once_with()
        open_logs_mock.assert_called_once_with()

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

    def test_start_scheduler_uses_configured_max_concurrency(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Планировщик должен получать лимит параллельных задач из конфига."""
        app, _ = _build_app(monkeypatch, scheduler_max_concurrent_tasks=4)
        captured_kwargs: dict[str, object] = {}

        class FakeTaskScheduler:
            """Заглушка TaskScheduler для проверки параметров старта."""

            def __init__(self, **kwargs: object) -> None:
                captured_kwargs.update(kwargs)

            def set_task_callback(self, _callback: object) -> None:
                return None

            def start(self) -> None:
                return None

            def get_all_tasks(self) -> list[object]:
                return []

        monkeypatch.setattr(
            "scheduler.task_scheduler.TaskScheduler", FakeTaskScheduler
        )

        app._start_scheduler()

        assert captured_kwargs["max_concurrent_tasks"] == 4
        assert str(captured_kwargs["persist_path"]).endswith("tasks.json")
