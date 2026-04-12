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
        save=MagicMock(return_value=True),
    )

    monkeypatch.setattr(main, "get_config", lambda: fake_config)
    monkeypatch.setattr("config.get_config", lambda: fake_config)
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

    monkeypatch.setattr("api.auth.get_stored_api_key", _get_stored_key)
    monkeypatch.setattr("api.auth.set_stored_api_key", _set_stored_key)
    FakeApiServer.instances.clear()

    app = main.VideoRecorderApp({"mode": "gui", "api": cli_api or {}})
    return app, fake_config


class TestMainApiRuntime:
    """Тесты runtime-управления API сервера из main.py."""

    def test_gui_runtime_components_use_public_api_refresh(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """GUI runtime coordinator не должен трогать private refresh окна."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        app._main_window = SimpleNamespace(
            bind_application_facade=MagicMock(),
            refresh_api_status_view=MagicMock(),
        )
        app._setup_hotkeys = MagicMock()
        app.start_api_server = MagicMock()
        app._start_scheduler = MagicMock()

        coordinator = main.GuiRuntimeCoordinator(app)
        coordinator._bind_runtime_components()

        app._main_window.bind_application_facade.assert_called_once_with(app)
        app._main_window.refresh_api_status_view.assert_called_once_with()

    def test_run_gui_delegates_to_gui_runtime_coordinator(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`_run_gui` делегирует запуск координатору GUI-рантайма."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        run_mock = MagicMock(return_value=123)
        app._gui_runtime_coordinator = SimpleNamespace(run=run_mock)

        result = app._run_gui()

        assert result == 123
        run_mock.assert_called_once_with()

    def test_runtime_accessors_expose_current_runtime_objects(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Runtime accessors должны отдавать текущие app-level объекты."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        api_server = object()

        app.set_api_server_instance(api_server)

        assert app.get_runtime_config() == {"mode": "gui", "api": {}}
        assert app.get_runtime_mode() == "gui"
        assert app.get_api_server_instance() is api_server
        assert app.get_websocket_manager_instance() is app._websocket_manager

    def test_public_facade_wrappers_delegate_to_private_methods(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Публичные facade wrappers должны делегировать private методам."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        app._get_status = MagicMock(return_value={"status": "ok"})
        app._get_recordings = MagicMock(return_value=[{"path": "demo.mp4"}])
        app._get_schedule = MagicMock(return_value=[{"id": "task-1"}])
        app._create_schedule = MagicMock(return_value={"success": True})
        app._delete_schedule = MagicMock(return_value={"success": True})
        app._update_schedule = MagicMock(return_value={"success": True})
        app._toggle_schedule = MagicMock(return_value={"success": True})
        app._get_devices = MagicMock(return_value={"input": [], "output": []})
        app._get_windows = MagicMock(return_value=[{"title": "Window"}])
        app._get_config = MagicMock(return_value={"video": {"fps": 30}})
        app._update_config = MagicMock(return_value={"success": True})
        app._start_api_server = MagicMock(return_value={"success": True})
        app._get_api_status = MagicMock(return_value={"running": False})
        app._apply_api_settings = MagicMock(return_value={"success": True})
        app._stop_api_server = MagicMock(return_value={"success": True})
        app._restart_api_server = MagicMock(return_value={"success": True})

        assert app.get_status() == {"status": "ok"}
        assert app.get_recordings() == [{"path": "demo.mp4"}]
        assert app.get_schedule() == [{"id": "task-1"}]
        assert app.create_schedule({"name": "task"}) == {"success": True}
        assert app.delete_schedule("task-1") == {"success": True}
        assert app.update_schedule({"id": "task-1"}) == {"success": True}
        assert app.toggle_schedule("task-1", True) == {"success": True}
        assert app.get_devices() == {"input": [], "output": []}
        assert app.get_windows() == [{"title": "Window"}]
        assert app.get_config_snapshot() == {"video": {"fps": 30}}
        assert app.update_config({"video": {"fps": 60}}) == {
            "success": True
        }
        assert app.start_api_server(force=True) == {"success": True}
        assert app.get_api_status() == {"running": False}
        assert app.apply_api_settings({"port": 5001}) == {"success": True}
        assert app.stop_api_server() == {"success": True}
        assert app.restart_api_server() == {"success": True}

        app._create_schedule.assert_called_once_with({"name": "task"})
        app._delete_schedule.assert_called_once_with("task-1")
        app._toggle_schedule.assert_called_once_with("task-1", True)

    def test_private_runtime_wrappers_delegate_to_coordinators_and_cli(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Private runtime wrappers должны делегировать coordinators/CLI."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        app._gui_runtime_coordinator = SimpleNamespace(run=MagicMock(return_value=7))
        app._api_runtime_coordinator = SimpleNamespace(
            get_effective_api_key=MagicMock(return_value="secret"),
            start_api_server=MagicMock(return_value={"success": True}),
            get_api_runtime_settings=MagicMock(return_value={"port": 5000}),
            get_api_status=MagicMock(return_value={"running": True}),
            apply_api_settings=MagicMock(return_value={"success": True}),
            stop_api_server=MagicMock(return_value={"success": True}),
            restart_api_server=MagicMock(return_value={"success": True}),
        )
        app._recording_runtime_coordinator = SimpleNamespace(
            get_status=MagicMock(return_value={"is_recording": False}),
            start_recording=MagicMock(return_value={"success": True}),
            stop_recording=MagicMock(return_value={"success": True}),
            toggle_pause=MagicMock(return_value={"success": True}),
            get_recordings=MagicMock(return_value=[]),
        )

        monkeypatch.setattr(
            "cli.scheduler.create_schedule",
            lambda _config: 1,
        )
        monkeypatch.setattr(
            "cli.scheduler.update_schedule",
            lambda _config: 2,
        )
        monkeypatch.setattr(
            "cli.scheduler.delete_schedule",
            lambda _config: 3,
        )
        monkeypatch.setattr(
            "cli.scheduler.toggle_schedule",
            lambda _config: 4,
        )
        monkeypatch.setattr(
            "cli.scheduler.preview_upcoming_runs",
            lambda _config: 5,
        )

        assert app._get_effective_api_key() == "secret"
        assert app._run_gui() == 7
        assert app._start_api_server(force=True) == {"success": True}
        assert app._get_api_runtime_settings() == {"port": 5000}
        assert app._get_api_status() == {"running": True}
        assert app._apply_api_settings({"port": 5001}) == {"success": True}
        assert app._stop_api_server() == {"success": True}
        assert app._restart_api_server() == {"success": True}
        assert app._get_status() == {"is_recording": False}
        assert app._start_recording({"area": "full"}) == {"success": True}
        assert app._stop_recording() == {"success": True}
        assert app._toggle_pause() == {"success": True}
        assert app._get_recordings() == []
        assert app._run_schedule_create() == 1
        assert app._run_schedule_update() == 2
        assert app._run_schedule_delete() == 3
        assert app._run_schedule_toggle() == 4
        assert app._run_schedule_preview() == 5

    def test_start_api_server_delegates_to_api_runtime_coordinator(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`_start_api_server` должен делегироваться API coordinator."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        start_mock = MagicMock(return_value={"success": True})
        app._api_runtime_coordinator = SimpleNamespace(
            start_api_server=start_mock
        )

        result = app._start_api_server(force=True)

        start_mock.assert_called_once_with(force=True)
        assert result == {"success": True}

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
        """При отсутствии env токен читается из конфигурации без миграции."""
        app, fake_config = _build_app(monkeypatch, api_key="config-token")

        monkeypatch.delenv("MIA_API_KEY", raising=False)

        assert app._get_effective_api_key() == "config-token"
        assert fake_config.settings.api.api_key == "config-token"
        assert fake_config.save.call_count == 0

    def test_start_api_server_migrates_legacy_config_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Legacy API key из конфига мигрируется в env при старте API."""
        app, fake_config = _build_app(monkeypatch, api_key="config-token")
        monkeypatch.delenv("MIA_API_KEY", raising=False)
        monkeypatch.setattr("api.server.APIServer", FakeApiServer)
        monkeypatch.setattr("api.routes.register_routes", lambda *args: None)

        result = app._start_api_server(force=True)

        assert result["success"] is True
        assert fake_config.settings.api.api_key is None
        assert fake_config.save.call_count == 1
        assert os.environ["MIA_API_KEY"] == "config-token"

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

    def test_start_api_server_registers_public_facade_callbacks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Runtime API должен регистрировать публичный фасад приложения."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        monkeypatch.setenv("MIA_API_KEY", "env-token")
        monkeypatch.setattr("api.server.APIServer", FakeApiServer)
        monkeypatch.setattr("api.routes.register_routes", lambda *args: None)

        result = app._start_api_server(force=True)

        assert result["success"] is True
        assert isinstance(app._api_server, FakeApiServer)
        expected_methods = {
            "status": app.get_status,
            "start": app.start_recording,
            "stop": app.stop_recording,
            "pause": app.toggle_pause,
            "recordings": app.get_recordings,
            "get_schedule": app.get_schedule,
            "create_schedule": app.create_schedule,
            "delete_schedule": app.delete_schedule,
            "update_schedule": app.update_schedule,
            "toggle_schedule": app.toggle_schedule,
            "devices": app.get_devices,
            "windows": app.get_windows,
            "get_config": app.get_config_snapshot,
            "update_config": app.update_config,
        }

        for action, expected in expected_methods.items():
            callback = app._api_server.callbacks[action]
            assert callback.__self__ is expected.__self__
            assert callback.__func__ is expected.__func__

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

    def test_api_status_contains_lifecycle_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Статус API должен содержать текущее lifecycle-состояние."""
        app, _ = _build_app(monkeypatch, api_key="config-token")

        status = app._get_api_status()
        assert status["lifecycle_state"] == "created"

    def test_start_api_server_returns_busy_during_transition(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Старт отклоняется, если lifecycle уже в переходном состоянии."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        app._api_runtime_manager._set_lifecycle_state("stopping")

        result = app._start_api_server(force=True)

        assert result["success"] is False
        assert result["error"] == "API lifecycle busy"
        assert result["running"] is False

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

    def test_apply_api_settings_validation_error_is_atomic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """При невалидных значениях настройки не должны применяться частично."""
        app, fake_config = _build_app(monkeypatch, api_key="old-token")
        before_port = fake_config.settings.api.port
        before_threads = fake_config.settings.api.server_threads

        result = app._apply_api_settings(
            {"port": 70000, "server_threads": "not-number"}
        )

        assert result["success"] is False
        assert fake_config.settings.api.port == before_port
        assert fake_config.settings.api.server_threads == before_threads
        assert fake_config.save.call_count == 0

    def test_apply_api_settings_rollback_on_persist_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """При ошибке save значения API и токен должны быть откатаны."""
        app, fake_config = _build_app(monkeypatch, api_key="old-token")
        fake_config.save.return_value = False
        server = FakeApiServer(api_key="old-token")
        app._api_server = server
        monkeypatch.setenv("MIA_API_KEY", "old-token")
        before_port = fake_config.settings.api.port

        result = app._apply_api_settings({"port": 5055, "token": "new-token"})

        assert result["success"] is False
        assert fake_config.settings.api.port == before_port
        assert os.environ["MIA_API_KEY"] == "old-token"
        assert server.api_key == "old-token"

    def test_update_config_validation_error_is_atomic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Невалидные секционные данные не должны применяться частично."""
        app, fake_config = _build_app(monkeypatch, api_key="old-token")
        before_port = fake_config.settings.api.port

        result = app._update_config({"api": {"port": 70000}})

        assert result["success"] is False
        assert fake_config.settings.api.port == before_port
        assert fake_config.save.call_count == 0

    def test_update_config_rolls_back_on_save_failure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """При ошибке сохранения значения секций откатываются."""
        app, fake_config = _build_app(monkeypatch, api_key="old-token")
        fake_config.save.return_value = False
        before_port = fake_config.settings.api.port

        result = app._update_config({"api": {"port": 5055}})

        assert result["success"] is False
        assert result["error"] == "Не удалось сохранить конфигурацию"
        assert fake_config.settings.api.port == before_port

    def test_stop_api_server_clears_server_reference(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Остановка API должна очищать runtime-ссылку у приложения."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        server = FakeApiServer(api_key="config-token")
        server._running = True
        app._api_server = server
        result = app._stop_api_server()

        assert result == {"success": True, "running": False}
        assert server.stop_calls == 1
        assert app._api_server is None

    def test_restart_api_server_delegates_to_runtime_manager(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Перезапуск должен делегироваться runtime-менеджеру."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        restart_mock = MagicMock(
            return_value={"success": True, "status": {"running": True}}
        )
        app._api_runtime_manager.restart_api_server = restart_mock

        result = app._restart_api_server()

        restart_mock.assert_called_once_with()
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

    def test_stop_recording_delegates_to_recording_coordinator(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Остановка записи должна делегироваться recording coordinator."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        stop_mock = MagicMock(return_value={"success": True})
        app._recording_runtime_coordinator = SimpleNamespace(
            stop_recording=stop_mock
        )

        result = app._stop_recording()

        stop_mock.assert_called_once_with()
        assert result == {"success": True}

    def test_request_methods_delegate_to_gui_public_interactive_api(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Tray/hotkeys должны идти через публичные interactive-методы."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        stop_result = {"success": True, "is_recording": True}
        pause_result = {"success": True, "is_paused": True}
        start_result = {"success": True, "output_path": "D:/capture.mp4"}
        app._main_window = SimpleNamespace(
            request_stop_recording=MagicMock(return_value=stop_result),
            request_toggle_pause=MagicMock(return_value=pause_result),
        )
        app.start_recording = MagicMock(return_value=start_result)
        run_on_gui_thread_mock = MagicMock(
            side_effect=[stop_result, pause_result]
        )
        app._run_on_gui_thread = run_on_gui_thread_mock

        assert app.request_start_recording() == start_result
        assert app.request_stop_recording() == stop_result
        assert app.request_toggle_pause_recording() == pause_result

        app.start_recording.assert_called_once_with()
        assert run_on_gui_thread_mock.call_count == 2
        stop_call = run_on_gui_thread_mock.call_args_list[0]
        pause_call = run_on_gui_thread_mock.call_args_list[1]
        assert stop_call.args[0] is app._main_window.request_stop_recording
        assert stop_call.kwargs["timeout"] == 10.0
        assert pause_call.args[0] is app._main_window.request_toggle_pause
        assert pause_call.kwargs["timeout"] == 10.0

    def test_hotkeys_route_through_request_methods(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Hotkeys не должны дергать private-методы окна напрямую."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        app.request_start_recording = MagicMock()
        app.request_stop_recording = MagicMock()
        app.request_toggle_pause_recording = MagicMock()
        app._main_window = SimpleNamespace(
            get_status=MagicMock(
                side_effect=[
                    {"is_recording": False},
                    {"is_recording": True},
                ]
            )
        )

        app._toggle_recording_hotkey()
        app._toggle_recording_hotkey()
        app._pause_recording_hotkey()

        app.request_start_recording.assert_called_once_with()
        app.request_stop_recording.assert_called_once_with()
        app.request_toggle_pause_recording.assert_called_once_with()

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
