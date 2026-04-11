"""Тесты менеджера runtime-управления API сервера."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from core.api_runtime_manager import ApiRuntimeManager


class MockApiServer:
    """Mock API сервера для тестов."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5000,
        server_threads: int = 4,
        api_key: str | None = None,
    ):
        self._host = host
        self._port = port
        self._server_threads = server_threads
        self._api_key = api_key
        self._running = False
        self._callbacks: dict[str, Any] = {}
        self._websocket_manager = None

    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "host": self._host,
            "port": self._port,
            "url": f"http://{self._host}:{self._port}",
            "api_key_set": bool(self._api_key),
        }

    def get_url(self) -> str:
        return f"http://{self._host}:{self._port}"

    def get_runtime_api_key(self) -> str | None:
        return self._api_key

    def set_websocket_manager(self, manager: Any) -> None:
        self._websocket_manager = manager

    def set_callback(self, action: str, callback: Any) -> None:
        self._callbacks[action] = callback

    def start(self) -> bool:
        self._running = True
        return True

    def stop(self) -> None:
        self._running = False

    def set_api_key(self, api_key: str | None) -> None:
        self._api_key = api_key


class MockApp:
    """Mock приложения для тестов."""

    def __init__(self, mode: str = "gui"):
        self._config: dict[str, Any] = {"api": {}}
        self._mode = mode
        self._api_server: Any = None
        self._main_window: Any = None
        self._websocket_manager = MagicMock()

    def _get_status(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"status": "ok"}

    def _start_recording(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"success": True}

    def _stop_recording(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"success": True}

    def _toggle_pause(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"success": True}

    def _get_recordings(self, *args: Any, **kwargs: Any) -> list[Any]:
        return []

    def _get_schedule(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {}

    def _create_schedule(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"success": True}

    def _delete_schedule(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"success": True}

    def _update_schedule(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"success": True}

    def _toggle_schedule(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"success": True}

    def _get_devices(self, *args: Any, **kwargs: Any) -> list[Any]:
        return []

    def _get_windows(self, *args: Any, **kwargs: Any) -> list[Any]:
        return []

    def _get_config(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {}

    def _update_config(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"success": True}

    def get_status(self) -> dict[str, Any]:
        return self._get_status()

    def start_recording(
        self, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        return self._start_recording(params)

    def stop_recording(self) -> dict[str, Any]:
        return self._stop_recording()

    def toggle_pause(self) -> dict[str, Any]:
        return self._toggle_pause()

    def get_recordings(self) -> list[Any]:
        return self._get_recordings()

    def get_schedule(self) -> dict[str, Any]:
        return self._get_schedule()

    def create_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._create_schedule(data)

    def delete_schedule(self, task_id: str) -> dict[str, Any]:
        return self._delete_schedule(task_id)

    def update_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._update_schedule(data)

    def toggle_schedule(
        self,
        task_id: str,
        enabled: bool,
    ) -> dict[str, Any]:
        return self._toggle_schedule(task_id, enabled)

    def get_devices(self) -> list[Any]:
        return self._get_devices()

    def get_windows(self) -> list[Any]:
        return self._get_windows()

    def get_config_snapshot(self) -> dict[str, Any]:
        return self._get_config()

    def update_config(self, data: dict[str, Any]) -> dict[str, Any]:
        return self._update_config(data)

    def request_start_recording(self) -> dict[str, Any]:
        return self.start_recording()

    def get_runtime_config(self) -> dict[str, Any]:
        return self._config

    def get_runtime_mode(self) -> str:
        return self._mode

    def get_api_server_instance(self) -> Any | None:
        return self._api_server

    def set_api_server_instance(self, server: Any | None) -> None:
        self._api_server = server

    def get_websocket_manager_instance(self) -> Any:
        return self._websocket_manager

    def request_stop_recording(self) -> dict[str, Any]:
        return self.stop_recording()

    def request_toggle_pause_recording(self) -> dict[str, Any]:
        return self.toggle_pause()

    def get_api_status(self) -> dict[str, Any]:
        return {"running": False}

    def apply_api_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        return {"success": True, "data": data}

    def start_api_server(self, force: bool = False) -> dict[str, Any]:
        return {"success": True, "force": force}

    def stop_api_server(self) -> dict[str, Any]:
        return {"success": True}

    def restart_api_server(self) -> dict[str, Any]:
        return {"success": True}

    def open_api_logs_folder(self) -> None:
        return None


@pytest.fixture
def mock_app() -> MockApp:
    """Создаёт mock приложения."""
    return MockApp()


@pytest.fixture
def manager(mock_app: MockApp) -> ApiRuntimeManager:
    """Создаёт менеджер API runtime."""
    return ApiRuntimeManager(mock_app)


class TestApiRuntimeManagerInit:
    """Проверки инициализации менеджера."""

    def test_init_creates_manager(self, mock_app: MockApp) -> None:
        """Менеджер создаётся с mock приложения."""
        manager = ApiRuntimeManager(mock_app)
        assert manager._app is mock_app
        assert manager._lifecycle is not None

    def test_initial_lifecycle_state_created(
        self, manager: ApiRuntimeManager
    ) -> None:
        """Начальное lifecycle-состояние — created."""
        assert manager._get_lifecycle_state() == "created"


class TestNormalizeApiKey:
    """Проверки нормализации API ключа."""

    def test_normalize_none_returns_none(
        self, manager: ApiRuntimeManager
    ) -> None:
        """None остаётся None."""
        assert manager._normalize_api_key(None) is None

    def test_normalize_empty_string_returns_none(
        self, manager: ApiRuntimeManager
    ) -> None:
        """Пустая строка становится None."""
        assert manager._normalize_api_key("") is None
        assert manager._normalize_api_key("   ") is None

    def test_normalize_string_returns_stripped(
        self, manager: ApiRuntimeManager
    ) -> None:
        """Строка очищается от пробелов."""
        assert manager._normalize_api_key("  test-key  ") == "test-key"

    def test_normalize_int_returns_string(
        self, manager: ApiRuntimeManager
    ) -> None:
        """Число преобразуется в строку."""
        assert manager._normalize_api_key(12345) == "12345"


class TestGetEffectiveApiKey:
    """Проверки получения актуального API ключа."""

    def test_stored_api_key_has_priority(
        self, manager: ApiRuntimeManager
    ) -> None:
        """Stored API ключ имеет приоритет над config."""
        with patch(
            "core.api_runtime_manager.api_auth.get_stored_api_key",
            return_value="stored-key",
        ):
            with patch(
                "core.api_runtime_manager.config_module.get_config"
            ) as mock:
                mock_config = MagicMock()
                mock_config.settings.api.api_key = "config-key"
                mock.return_value = mock_config

                result = manager.get_effective_api_key()
                assert result == "stored-key"

    def test_config_api_key_used_when_no_stored(
        self, manager: ApiRuntimeManager
    ) -> None:
        """Config API ключ используется при отсутствии stored."""
        with patch(
            "core.api_runtime_manager.api_auth.get_stored_api_key",
            return_value=None,
        ):
            with patch(
                "core.api_runtime_manager.config_module.get_config"
            ) as mock:
                mock_config = MagicMock()
                mock_config.settings.api.api_key = "config-key"
                mock.return_value = mock_config

                result = manager.get_effective_api_key()
                assert result == "config-key"

    def test_returns_none_when_no_keys(
        self, manager: ApiRuntimeManager
    ) -> None:
        """Возвращает None при отсутствии ключей."""
        with patch(
            "core.api_runtime_manager.api_auth.get_stored_api_key",
            return_value=None,
        ):
            with patch(
                "core.api_runtime_manager.config_module.get_config"
            ) as mock:
                mock_config = MagicMock()
                mock_config.settings.api.api_key = None
                mock.return_value = mock_config

                result = manager.get_effective_api_key()
                assert result is None


class TestMigrateLegacyApiKey:
    """Проверки миграции legacy API ключа."""

    def test_no_migration_when_stored_exists(
        self, manager: ApiRuntimeManager
    ) -> None:
        """Миграция не выполняется при наличии stored ключа."""
        with patch(
            "core.api_runtime_manager.api_auth.get_stored_api_key",
            return_value="stored-key",
        ):
            result = manager.migrate_legacy_api_key_if_needed()
            assert result == "stored-key"

    def test_migrates_config_key_to_env(
        self, manager: ApiRuntimeManager
    ) -> None:
        """Config ключ мигрирует в env при отсутствии stored."""
        with patch(
            "core.api_runtime_manager.api_auth.get_stored_api_key",
            return_value=None,
        ):
            with patch(
                "core.api_runtime_manager.api_auth.set_stored_api_key"
            ) as mock_set:
                with patch(
                    "core.api_runtime_manager.config_module.get_config"
                ) as mock_config:
                    mock_cfg = MagicMock()
                    mock_cfg.settings.api.api_key = "legacy-key"
                    mock_config.return_value = mock_cfg

                    result = manager.migrate_legacy_api_key_if_needed()
                    assert result == "legacy-key"
                    mock_set.assert_called_once_with("legacy-key")

    def test_returns_none_when_no_keys_to_migrate(
        self, manager: ApiRuntimeManager
    ) -> None:
        """Возвращает None при отсутствии ключей для миграции."""
        with patch(
            "core.api_runtime_manager.api_auth.get_stored_api_key",
            return_value=None,
        ):
            with patch(
                "core.api_runtime_manager.config_module.get_config"
            ) as mock_config:
                mock_cfg = MagicMock()
                mock_cfg.settings.api.api_key = None
                mock_config.return_value = mock_cfg

                result = manager.migrate_legacy_api_key_if_needed()
                assert result is None


class TestSyncApiKeyEnv:
    """Проверки синхронизации API ключа."""

    def test_sync_calls_set_stored_api_key(
        self, manager: ApiRuntimeManager
    ) -> None:
        """sync_api_key_env вызывает set_stored_api_key."""
        with patch(
            "core.api_runtime_manager.api_auth.set_stored_api_key"
        ) as mock_set:
            manager.sync_api_key_env("new-key")
            mock_set.assert_called_once_with("new-key")

    def test_sync_with_none_calls_set_with_none(
        self, manager: ApiRuntimeManager
    ) -> None:
        """sync_api_key_env с None вызывает set_stored_api_key(None)."""
        with patch(
            "core.api_runtime_manager.api_auth.set_stored_api_key"
        ) as mock_set:
            manager.sync_api_key_env(None)
            mock_set.assert_called_once_with(None)


class TestStartApiServer:
    """Проверки запуска API сервера."""

    def test_start_rejected_when_lifecycle_busy(
        self, manager: ApiRuntimeManager
    ) -> None:
        """Запуск отклоняется при lifecycle busy."""
        manager._set_lifecycle_state("starting")

        result = manager.start_api_server()
        assert result["success"] is False
        assert result["error"] == "API lifecycle busy"

    def test_start_returns_running_when_already_running(
        self, manager: ApiRuntimeManager, mock_app: MockApp
    ) -> None:
        """Возвращает success при уже запущенном сервере."""
        mock_server = MockApiServer()
        mock_server._running = True
        mock_app._api_server = mock_server

        with patch(
            "core.api_runtime_manager.api_auth.get_stored_api_key",
            return_value=None,
        ):
            with patch(
                "core.api_runtime_manager.config_module.get_config"
            ) as mock_config:
                mock_cfg = MagicMock()
                mock_cfg.settings.api.api_key = None
                mock_cfg.settings.api.enabled = True
                mock_cfg.settings.api.host = "127.0.0.1"
                mock_cfg.settings.api.port = 5000
                mock_cfg.settings.api.server_threads = 4
                mock_config.return_value = mock_cfg

                result = manager.start_api_server()
                assert result["success"] is True
                assert "status" in result

    def test_start_disabled_by_config(
        self, manager: ApiRuntimeManager
    ) -> None:
        """Не запускает при disabled в конфигурации."""
        with patch(
            "core.api_runtime_manager.api_auth.get_stored_api_key",
            return_value=None,
        ):
            with patch(
                "core.api_runtime_manager.config_module.get_config"
            ) as mock_config:
                mock_cfg = MagicMock()
                mock_cfg.settings.api.api_key = None
                mock_cfg.settings.api.enabled = False
                mock_config.return_value = mock_cfg

                result = manager.start_api_server()
                assert result["success"] is False
                assert result["running"] is False


class TestGetApiRuntimeSettings:
    """Проверки получения runtime-настроек."""

    def test_gui_mode_uses_config(self, manager: ApiRuntimeManager) -> None:
        """GUI режим использует config."""
        with patch(
            "core.api_runtime_manager.config_module.get_config"
        ) as mock:
            mock_cfg = MagicMock()
            mock_cfg.settings.api.enabled = True
            mock_cfg.settings.api.host = "0.0.0.0"
            mock_cfg.settings.api.port = 8080
            mock_cfg.settings.api.server_threads = 8
            mock.return_value = mock_cfg

            with patch.object(
                manager, "get_effective_api_key", return_value="test-key"
            ):
                result = manager.get_api_runtime_settings()
                assert result["enabled"] is True
                assert result["host"] == "0.0.0.0"
                assert result["port"] == 8080
                assert result["server_threads"] == 8
                assert result["api_key"] == "test-key"

    def test_cli_mode_merges_cli_config(
        self, manager: ApiRuntimeManager, mock_app: MockApp
    ) -> None:
        """CLI режим объединяет CLI и config настройки."""
        mock_app._mode = "cli"
        mock_app._config = {"api": {"enabled": False, "port": 9000}}

        with patch(
            "core.api_runtime_manager.config_module.get_config"
        ) as mock:
            mock_cfg = MagicMock()
            mock_cfg.settings.api.enabled = True
            mock_cfg.settings.api.host = "127.0.0.1"
            mock_cfg.settings.api.port = 5000
            mock_cfg.settings.api.server_threads = 4
            mock.return_value = mock_cfg

            with patch.object(
                manager, "get_effective_api_key", return_value=None
            ):
                result = manager.get_api_runtime_settings()
                assert result["enabled"] is False
                assert result["port"] == 9000
                assert result["host"] == "127.0.0.1"


class TestGetApiStatus:
    """Проверки получения статуса API."""

    def test_status_without_server(self, manager: ApiRuntimeManager) -> None:
        """Статус без запущенного сервера."""
        with patch(
            "core.api_runtime_manager.config_module.get_config"
        ) as mock:
            mock_cfg = MagicMock()
            mock_cfg.settings.api.enabled = True
            mock_cfg.settings.api.host = "127.0.0.1"
            mock_cfg.settings.api.port = 5000
            mock_cfg.settings.api.server_threads = 4
            mock.return_value = mock_cfg

            with patch.object(
                manager, "get_effective_api_key", return_value=None
            ):
                with patch(
                    "core.api_runtime_manager.get_api_log_dir",
                    return_value=Path("/tmp/logs"),
                ):
                    result = manager.get_api_status()
                    assert result["running"] is False
                    assert result["configured"]["enabled"] is True
                    assert result["lifecycle_state"] == "created"

    def test_status_with_running_server(
        self, manager: ApiRuntimeManager, mock_app: MockApp
    ) -> None:
        """Статус с запущенным сервером."""
        mock_server = MockApiServer(api_key="test-key")
        mock_server._running = True
        mock_app._api_server = mock_server

        with patch(
            "core.api_runtime_manager.config_module.get_config"
        ) as mock:
            mock_cfg = MagicMock()
            mock_cfg.settings.api.enabled = True
            mock_cfg.settings.api.host = "127.0.0.1"
            mock_cfg.settings.api.port = 5000
            mock_cfg.settings.api.server_threads = 4
            mock.return_value = mock_cfg

            with patch.object(
                manager, "get_effective_api_key", return_value="test-key"
            ):
                with patch(
                    "core.api_runtime_manager.get_api_log_dir",
                    return_value=Path("/tmp/logs"),
                ):
                    result = manager.get_api_status()
                    assert result["running"] is True
                    assert result["api_key_set"] is True


class TestApplyApiSettings:
    """Проверки применения настроек API."""

    def test_apply_invalid_host(self, manager: ApiRuntimeManager) -> None:
        """Невалидный host возвращает ошибку."""
        with patch(
            "core.api_runtime_manager.config_module.get_config"
        ) as mock:
            mock_cfg = MagicMock()
            mock_cfg.settings.api.enabled = True
            mock_cfg.settings.api.host = "127.0.0.1"
            mock_cfg.settings.api.port = 5000
            mock_cfg.settings.api.server_threads = 4
            mock_cfg.settings.api.api_key = None
            mock.return_value = mock_cfg

            with patch.object(manager, "get_api_status", return_value={}):
                with patch.object(
                    manager, "get_effective_api_key", return_value=None
                ):
                    with patch(
                        "core.api_runtime_manager.config_module.APISettingsSchema"
                    ) as mock_schema:
                        mock_schema.model_validate.side_effect = ValueError(
                            "Invalid host"
                        )
                        result = manager.apply_api_settings({"host": 12345})
                        assert result["success"] is False
                        assert "error" in result

    def test_apply_invalid_port(self, manager: ApiRuntimeManager) -> None:
        """Невалидный port возвращает ошибку."""
        with patch(
            "core.api_runtime_manager.config_module.get_config"
        ) as mock:
            mock_cfg = MagicMock()
            mock_cfg.settings.api.enabled = True
            mock_cfg.settings.api.host = "127.0.0.1"
            mock_cfg.settings.api.port = 5000
            mock_cfg.settings.api.server_threads = 4
            mock_cfg.settings.api.api_key = None
            mock.return_value = mock_cfg

            with patch.object(manager, "get_api_status", return_value={}):
                result = manager.apply_api_settings({"port": "invalid"})
                assert result["success"] is False

    def test_apply_save_failure(self, manager: ApiRuntimeManager) -> None:
        """Ошибка сохранения возвращает ошибку."""
        with patch(
            "core.api_runtime_manager.config_module.get_config"
        ) as mock:
            mock_cfg = MagicMock()
            mock_cfg.settings.api.enabled = True
            mock_cfg.settings.api.host = "127.0.0.1"
            mock_cfg.settings.api.port = 5000
            mock_cfg.settings.api.server_threads = 4
            mock_cfg.settings.api.api_key = None
            mock_cfg.save.return_value = False
            mock.return_value = mock_cfg

            with patch.object(manager, "get_api_status", return_value={}):
                with patch.object(
                    manager, "get_effective_api_key", return_value=None
                ):
                    result = manager.apply_api_settings({"enabled": False})
                    assert result["success"] is False
                    assert "сохранить" in result["error"]


class TestStopApiServer:
    """Проверки остановки API сервера."""

    def test_stop_rejected_when_lifecycle_starting(
        self, manager: ApiRuntimeManager
    ) -> None:
        """Остановка отклоняется при lifecycle в starting."""
        manager._set_lifecycle_state("starting")

        result = manager.stop_api_server()
        assert result["success"] is False
        assert result["error"] == "API lifecycle busy"

    def test_stop_when_no_server(self, manager: ApiRuntimeManager) -> None:
        """Остановка при отсутствии сервера."""
        result = manager.stop_api_server()
        assert result["success"] is True
        assert result["running"] is False

    def test_stop_running_server(
        self, manager: ApiRuntimeManager, mock_app: MockApp
    ) -> None:
        """Остановка запущенного сервера."""
        mock_server = MockApiServer()
        mock_server._running = True
        mock_app._api_server = mock_server

        result = manager.stop_api_server()
        assert result["success"] is True
        assert result["running"] is False
        assert mock_app._api_server is None


class TestRestartApiServer:
    """Проверки перезапуска API сервера."""

    def test_restart_calls_stop_and_start(
        self, manager: ApiRuntimeManager
    ) -> None:
        """Перезапуск вызывает stop и start."""
        with patch.object(manager, "stop_api_server") as mock_stop:
            with patch.object(
                manager, "start_api_server", return_value={"success": True}
            ) as mock_start:
                manager.restart_api_server()
                mock_stop.assert_called_once()
                mock_start.assert_called_once_with(force=True)


class TestSetupApiCallbacks:
    """Проверки регистрации callbacks API."""

    def test_setup_skips_when_no_server(
        self, manager: ApiRuntimeManager, mock_app: MockApp
    ) -> None:
        """Пропускает при отсутствии сервера."""
        mock_app._api_server = None
        manager.setup_api_callbacks()

    def test_setup_registers_all_callbacks(
        self, manager: ApiRuntimeManager, mock_app: MockApp
    ) -> None:
        """Регистрирует все callbacks."""
        mock_server = MockApiServer()
        mock_app._api_server = mock_server

        manager.setup_api_callbacks()

        expected_actions = [
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
        ]
        for action in expected_actions:
            assert action in mock_server._callbacks

    def test_setup_uses_public_facade_callbacks(
        self, manager: ApiRuntimeManager, mock_app: MockApp
    ) -> None:
        """Runtime callbacks должны ссылаться на публичный фасад."""
        mock_server = MockApiServer()
        mock_app._api_server = mock_server

        manager.setup_api_callbacks()

        expected_methods = {
            "status": mock_app.get_status,
            "start": mock_app.start_recording,
            "stop": mock_app.stop_recording,
            "pause": mock_app.toggle_pause,
            "recordings": mock_app.get_recordings,
            "get_schedule": mock_app.get_schedule,
            "create_schedule": mock_app.create_schedule,
            "delete_schedule": mock_app.delete_schedule,
            "update_schedule": mock_app.update_schedule,
            "toggle_schedule": mock_app.toggle_schedule,
            "devices": mock_app.get_devices,
            "windows": mock_app.get_windows,
            "get_config": mock_app.get_config_snapshot,
            "update_config": mock_app.update_config,
        }

        for action, expected in expected_methods.items():
            callback = mock_server._callbacks[action]
            assert callback.__self__ is expected.__self__
            assert callback.__func__ is expected.__func__
