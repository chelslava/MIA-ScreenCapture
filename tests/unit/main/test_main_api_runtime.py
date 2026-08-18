"""
Unit тесты runtime-управления API из main.py.
"""

import os
from pathlib import Path
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
        self.detach_calls = 0

    def attach_event_bus(self, event_bus: object) -> None:
        self.attached_event_bus = event_bus

    def detach_event_bus(self) -> None:
        """Идемпотентное отключение от event bus (как в реальном классе)."""
        if self.attached_event_bus is None:
            return
        self.detach_calls += 1
        self.attached_event_bus = None


class FakeWebhookNotifier:
    """Заглушка WebhookNotifier без реальной подписки на event bus."""

    def __init__(self) -> None:
        self.attached_event_bus: object | None = None
        self.detach_calls = 0

    def attach_event_bus(self, event_bus: object) -> None:
        self.attached_event_bus = event_bus

    def detach_event_bus(self) -> None:
        """Идемпотентное отключение от event bus (как в реальном классе)."""
        if self.attached_event_bus is None:
            return
        self.detach_calls += 1
        self.attached_event_bus = None


class FakeApiServer:
    """Фейковый APIServer для проверки runtime-сценариев."""

    instances: list["FakeApiServer"] = []

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5000,
        server_threads: int = 4,
        api_key: str | None = None,
        trust_proxy_headers: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.server_threads = server_threads
        self.api_key = api_key.strip() if api_key and api_key.strip() else None
        self.trust_proxy_headers = trust_proxy_headers
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
        trust_proxy_headers=False,
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
    monkeypatch.setattr(main, "WebhookNotifier", FakeWebhookNotifier)
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
        facade = app.get_application_facade()
        app._main_window = SimpleNamespace(
            bind_application_facade=MagicMock(),
            refresh_api_status_view=MagicMock(),
        )
        app._setup_hotkeys = MagicMock()
        app.start_api_server = MagicMock()
        app._start_scheduler = MagicMock()

        coordinator = main.GuiRuntimeCoordinator(app)
        coordinator._bind_runtime_components()

        app.start_api_server.assert_called_once_with(force=False)
        app._main_window.bind_application_facade.assert_called_once_with(
            facade
        )
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
        assert app.get_application_facade() is app._application_service

    def test_concrete_application_facade_uses_public_app_contract(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Concrete facade должен делегировать публичному app contract."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        facade = app.get_application_facade()
        app.get_status = MagicMock(return_value={"status": "ok"})
        app.get_recordings = MagicMock(return_value=[{"path": "demo.mp4"}])
        app.get_schedule = MagicMock(return_value=[{"id": "task-1"}])
        app.create_schedule = MagicMock(return_value={"success": True})
        app.delete_schedule = MagicMock(return_value={"success": True})
        app.update_schedule = MagicMock(return_value={"success": True})
        app.toggle_schedule = MagicMock(return_value={"success": True})
        app.get_devices = MagicMock(return_value={"input": [], "output": []})
        app.get_windows = MagicMock(return_value=[{"title": "Window"}])
        app.get_config_snapshot = MagicMock(
            return_value={"video": {"fps": 30}}
        )
        app.update_config = MagicMock(return_value={"success": True})
        app.start_api_server = MagicMock(return_value={"success": True})
        app.get_api_status = MagicMock(return_value={"running": False})
        app.apply_api_settings = MagicMock(return_value={"success": True})
        app.stop_api_server = MagicMock(return_value={"success": True})
        app.restart_api_server = MagicMock(return_value={"success": True})

        assert facade.get_status() == {"status": "ok"}
        assert facade.get_recordings() == [{"path": "demo.mp4"}]
        assert facade.get_schedule() == [{"id": "task-1"}]
        assert facade.create_schedule({"name": "task"}) == {"success": True}
        assert facade.delete_schedule("task-1") == {"success": True}
        assert facade.update_schedule({"id": "task-1"}) == {"success": True}
        assert facade.toggle_schedule("task-1", True) == {"success": True}
        assert facade.get_devices() == {"input": [], "output": []}
        assert facade.get_windows() == [{"title": "Window"}]
        assert facade.get_config_snapshot() == {"video": {"fps": 30}}
        assert facade.update_config({"video": {"fps": 60}}) == {
            "success": True
        }
        assert facade.start_api_server(force=True) == {"success": True}
        assert facade.get_api_status() == {"running": False}
        assert facade.apply_api_settings({"port": 5001}) == {"success": True}
        assert facade.stop_api_server() == {"success": True}
        assert facade.restart_api_server() == {"success": True}

        app.create_schedule.assert_called_once_with({"name": "task"})
        app.delete_schedule.assert_called_once_with("task-1")
        app.toggle_schedule.assert_called_once_with("task-1", True)

    def test_private_runtime_wrappers_delegate_to_coordinators_and_cli(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Private runtime wrappers должны делегировать coordinators/CLI."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        app._gui_runtime_coordinator = SimpleNamespace(
            run=MagicMock(return_value=7)
        )
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
            "monitors",
            "disk_space",
            "get_webhook_config",
            "configure_webhook",
            "test_webhook",
            "verify_recording",
            "repair_recording",
            "switch_capture_source",
            "start_multi_recording",
            "stop_multi_recording",
            "get_multi_recording_status",
            "get_config",
            "update_config",
            "get_profiles",
            "get_profile",
            "create_profile",
            "update_profile",
            "delete_profile",
            "apply_profile",
            "export_profile",
            "import_profile",
        }

    def test_start_api_server_registers_public_facade_callbacks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Runtime API должен регистрировать публичный фасад приложения."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        facade = app.get_application_facade()
        monkeypatch.setenv("MIA_API_KEY", "env-token")
        monkeypatch.setattr("api.server.APIServer", FakeApiServer)
        monkeypatch.setattr("api.routes.register_routes", lambda *args: None)

        result = app._start_api_server(force=True)

        assert result["success"] is True
        assert isinstance(app._api_server, FakeApiServer)
        expected_methods = {
            "status": facade.get_status,
            "start": facade.start_recording,
            "stop": facade.stop_recording,
            "pause": facade.toggle_pause,
            "recordings": facade.get_recordings,
            "get_schedule": facade.get_schedule,
            "create_schedule": facade.create_schedule,
            "delete_schedule": facade.delete_schedule,
            "update_schedule": facade.update_schedule,
            "toggle_schedule": facade.toggle_schedule,
            "devices": facade.get_devices,
            "windows": facade.get_windows,
            "monitors": facade.get_monitors,
            "disk_space": facade.get_disk_space,
            "get_webhook_config": facade.get_webhook_config,
            "configure_webhook": facade.configure_webhook,
            "test_webhook": facade.test_webhook,
            "verify_recording": facade.verify_recording,
            "repair_recording": facade.repair_recording,
            "switch_capture_source": facade.switch_capture_source,
            "start_multi_recording": facade.start_multi_recording,
            "stop_multi_recording": facade.stop_multi_recording,
            "get_multi_recording_status": facade.get_multi_recording_status,
            "get_config": facade.get_config_snapshot,
            "update_config": facade.update_config,
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
        app.get_status = MagicMock(
            side_effect=[
                {"is_recording": False},
                {"is_recording": True},
            ]
        )
        app.request_start_recording = MagicMock()
        app.request_stop_recording = MagicMock()
        app.request_toggle_pause_recording = MagicMock()
        app._main_window = SimpleNamespace()

        app._toggle_recording_hotkey()
        app._toggle_recording_hotkey()
        app._pause_recording_hotkey()

        app.request_start_recording.assert_called_once_with()
        app.request_stop_recording.assert_called_once_with()
        app.request_toggle_pause_recording.assert_called_once_with()

    def test_execute_scheduled_task_uses_application_facade(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Scheduler должен запускать запись через общий facade contract."""
        app, _ = _build_app(monkeypatch, api_key="config-token")
        app.start_recording = MagicMock(return_value={"success": True})

        app._execute_scheduled_task({"id": "task-1", "area": "full"})

        app.start_recording.assert_called_once_with(
            {"id": "task-1", "area": "full"}
        )

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

            def set_task_error_callback(self, _callback: object) -> None:
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


class TestRecordingFilePaths:
    """Тесты разрешения API-путей verify/repair под каталогом вывода."""

    @staticmethod
    def _app() -> main.VideoRecorderApp:
        """Создаёт экземпляр без инициализации несвязанных runtime-сервисов."""
        return object.__new__(main.VideoRecorderApp)

    @staticmethod
    def _configure_output_root(
        monkeypatch: pytest.MonkeyPatch,
        output_root: Path,
    ) -> None:
        """Настраивает generated output path с заданной эффективной базой."""
        fake_config = SimpleNamespace(
            get_output_path=lambda: output_root / "generated.mp4"
        )
        monkeypatch.setattr(main, "get_config", lambda: fake_config)

    def test_verify_uses_canonical_path_under_configured_output_root(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Verify использует configured root вне CWD и каноническую цель."""
        output_root = tmp_path / "external" / "recordings"
        target = output_root / "archive" / "video.mp4"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"video")
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.chdir(cwd)
        self._configure_output_root(monkeypatch, output_root)
        check = SimpleNamespace(
            valid=True,
            duration_s=1.0,
            codec_name="h264",
            width=1920,
            height=1080,
            error=None,
        )
        verify_mock = MagicMock(return_value=check)
        monkeypatch.setattr(main, "verify_video_integrity", verify_mock)

        result = self._app()._verify_recording_file("archive/video.mp4")

        verify_mock.assert_called_once_with(target.resolve())
        assert result["valid"] is True

    def test_repair_uses_canonical_path_under_configured_output_root(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Repair использует ту же configured base независимо от CWD."""
        output_root = tmp_path / "external" / "recordings"
        target = output_root / "archive" / "video.mp4"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"video")
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.chdir(cwd)
        self._configure_output_root(monkeypatch, output_root)
        repair = SimpleNamespace(
            repaired=True,
            original_size_bytes=5,
            repaired_size_bytes=4,
            error=None,
        )
        repair_mock = MagicMock(return_value=repair)
        monkeypatch.setattr(main, "attempt_repair_video", repair_mock)

        result = self._app()._repair_recording_file("archive/video.mp4")

        repair_mock.assert_called_once_with(target.resolve())
        assert result["repaired"] is True

    def test_repair_rejects_parent_escape_before_utility_call(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Побег через parent segment отклоняется до изменения файла."""
        output_root = tmp_path / "recordings"
        output_root.mkdir()
        self._configure_output_root(monkeypatch, output_root)
        repair_mock = MagicMock()
        monkeypatch.setattr(main, "attempt_repair_video", repair_mock)

        with pytest.raises(ValueError, match="каталога вывода"):
            self._app()._repair_recording_file("../outside/video.mp4")

        repair_mock.assert_not_called()

    def test_repair_rejects_existing_link_outside_output_root(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ссылка наружу отклоняется до запуска изменяющей файл операции."""
        output_root = tmp_path / "recordings"
        outside_root = tmp_path / "outside"
        output_root.mkdir()
        outside_root.mkdir()
        link = output_root / "escape"
        try:
            link.symlink_to(outside_root, target_is_directory=True)
        except OSError as error:
            pytest.skip(f"Создание symlink недоступно: {error}")

        self._configure_output_root(monkeypatch, output_root)
        repair_mock = MagicMock()
        monkeypatch.setattr(main, "attempt_repair_video", repair_mock)

        with pytest.raises(ValueError, match="каталога вывода"):
            self._app()._repair_recording_file("escape/video.mp4")

        repair_mock.assert_not_called()

    @pytest.mark.parametrize(
        ("operation_name", "utility_name"),
        [
            ("_verify_recording_file", "verify_video_integrity"),
            ("_repair_recording_file", "attempt_repair_video"),
        ],
    )
    def test_output_root_rejected_before_utility_call(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        operation_name: str,
        utility_name: str,
    ) -> None:
        """Сам output root отклоняется без изменения соседнего файла."""
        output_root = tmp_path / "recordings"
        output_root.mkdir()
        outside_sentinel = tmp_path / "recordings.repair"
        outside_sentinel.write_bytes(b"keep")
        self._configure_output_root(monkeypatch, output_root)
        utility_mock = MagicMock(side_effect=outside_sentinel.unlink)
        monkeypatch.setattr(main, utility_name, utility_mock)

        with pytest.raises(ValueError, match="файлом внутри каталога вывода"):
            getattr(self._app(), operation_name)(".")

        utility_mock.assert_not_called()
        assert outside_sentinel.read_bytes() == b"keep"

    @pytest.mark.parametrize(
        ("operation_name", "utility_name"),
        [
            ("_verify_recording_file", "verify_video_integrity"),
            ("_repair_recording_file", "attempt_repair_video"),
        ],
    )
    def test_existing_directory_rejected_before_utility_call(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        operation_name: str,
        utility_name: str,
    ) -> None:
        """Вложенный существующий каталог не передаётся file utility."""
        output_root = tmp_path / "recordings"
        nested_directory = output_root / "archive"
        nested_directory.mkdir(parents=True)
        self._configure_output_root(monkeypatch, output_root)
        utility_mock = MagicMock()
        monkeypatch.setattr(main, utility_name, utility_mock)

        with pytest.raises(ValueError, match="файлом внутри каталога вывода"):
            getattr(self._app(), operation_name)("archive")

        utility_mock.assert_not_called()

    def test_missing_nested_file_reaches_repair_utility(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Отсутствующий вложенный файл сохраняет штатный repair flow."""
        output_root = tmp_path / "external" / "recordings"
        output_root.mkdir(parents=True)
        cwd = tmp_path / "cwd"
        cwd.mkdir()
        monkeypatch.chdir(cwd)
        self._configure_output_root(monkeypatch, output_root)
        repair = SimpleNamespace(
            repaired=False,
            original_size_bytes=0,
            repaired_size_bytes=0,
            error="Файл не найден",
        )
        repair_mock = MagicMock(return_value=repair)
        monkeypatch.setattr(main, "attempt_repair_video", repair_mock)

        result = self._app()._repair_recording_file("archive/missing.mp4")

        repair_mock.assert_called_once_with(
            (output_root / "archive" / "missing.mp4").resolve()
        )
        assert result["error"] == "Файл не найден"


class TestShutdownDetachEventBus:
    """Тесты отключения подписчиков от EventBus при завершении (#100)."""

    @staticmethod
    def _fresh_shutdown_manager(
        monkeypatch: pytest.MonkeyPatch,
    ) -> main.GracefulShutdown:
        """Изолированный shutdown manager без глобального синглтона."""
        manager = main.GracefulShutdown()
        monkeypatch.setattr(main, "get_shutdown_manager", lambda: manager)
        # Не трогаем реальные обработчики сигналов в unit-тестах
        monkeypatch.setattr(manager, "setup_signal_handlers", lambda: None)
        return manager

    def test_normal_shutdown_detaches_websocket_and_webhook(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Обычный путь shutdown отключает подписчиков от EventBus."""
        app, _ = _build_app(monkeypatch)
        self._fresh_shutdown_manager(monkeypatch)

        app._setup_graceful_shutdown()
        assert app._shutdown_manager is not None
        app._shutdown_manager.shutdown()

        assert app._webhook_notifier.detach_calls == 1
        assert app._websocket_manager.detach_calls == 1
        assert app._webhook_notifier.attached_event_bus is None
        assert app._websocket_manager.attached_event_bus is None

    def test_fallback_cleanup_detaches_websocket_and_webhook(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Fallback-очистка без shutdown manager тоже отключает подписчиков."""
        app, _ = _build_app(monkeypatch)
        app._shutdown_manager = None

        # Fallback-путь выполняет и другие очистки; заглушаем их
        app._cleanup_api_server = MagicMock()
        app._cleanup_scheduler = MagicMock()
        app._cleanup_tray = MagicMock()
        app._stop_active_recording = MagicMock()
        app._save_config = MagicMock()

        app._cleanup()

        assert app._webhook_notifier.detach_calls == 1
        assert app._websocket_manager.detach_calls == 1

    def test_cleanup_after_normal_shutdown_is_idempotent(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Повторная очистка после shutdown не падает и не дублирует detach."""
        app, _ = _build_app(monkeypatch)
        self._fresh_shutdown_manager(monkeypatch)

        app._setup_graceful_shutdown()
        assert app._shutdown_manager is not None
        app._shutdown_manager.shutdown()

        # Повторный вызов _cleanup() — вторая попытка shutdown() вернёт False
        app._cleanup()

        assert app._webhook_notifier.detach_calls == 1
        assert app._websocket_manager.detach_calls == 1

    def test_detach_does_not_fail_when_subscribers_missing(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Отсутствие подписчиков не ломает очистку."""
        app, _ = _build_app(monkeypatch)
        app._shutdown_manager = None
        # Имитация частичной инициализации: подписчики не созданы
        del app._webhook_notifier
        del app._websocket_manager
        app._cleanup_api_server = MagicMock()
        app._cleanup_scheduler = MagicMock()
        app._cleanup_tray = MagicMock()
        app._stop_active_recording = MagicMock()
        app._save_config = MagicMock()

        app._cleanup()  # Не должно бросать исключений
