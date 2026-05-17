"""Менеджер runtime-управления API сервера."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

import api.auth as api_auth
import config as config_module
from core.api_lifecycle_manager import ApiLifecycleManager, ApiLifecycleState
from core.application_facade import ApplicationFacade
from logger_config import (
    get_api_log_dir,
    get_module_logger,
    open_api_logs_folder,
)

logger = get_module_logger(__name__)


class _ApiServerProtocol(Protocol):
    """Минимальный контракт API сервера для runtime-менеджера."""

    def is_running(self) -> bool:
        """Возвращает True, если сервер запущен."""

    def get_status(self) -> dict[str, Any]:
        """Возвращает снимок состояния сервера."""

    def get_url(self) -> str:
        """Возвращает URL сервера."""

    def get_runtime_api_key(self) -> str | None:
        """Возвращает фактический API ключ, используемый сервером."""

    def set_websocket_manager(self, manager: Any) -> None:
        """Подключает WebSocket-менеджер."""

    def set_callback(self, action: str, callback: Callable[..., Any]) -> None:
        """Регистрирует callback для API действия."""

    def start(self) -> bool:
        """Запускает сервер."""

    def stop(self) -> None:
        """Останавливает сервер."""

    def set_api_key(self, api_key: str | None) -> None:
        """Обновляет runtime API ключ."""


class _ApiRuntimeHostProtocol(Protocol):
    """Минимальный runtime-host контракт для API runtime-менеджера."""

    def get_runtime_config(self) -> dict[str, Any]:
        """Возвращает CLI/runtime конфигурацию приложения."""

    def get_runtime_mode(self) -> str:
        """Возвращает текущий режим запуска приложения."""

    def get_api_server_instance(self) -> Any | None:
        """Возвращает текущий runtime API server instance."""

    def set_api_server_instance(self, server: Any | None) -> None:
        """Устанавливает текущий runtime API server instance."""

    def get_websocket_manager_instance(self) -> Any:
        """Возвращает WebSocket manager приложения."""


class ApiRuntimeManager:
    """Управляет жизненным циклом и настройками API сервера."""

    def __init__(
        self,
        host: _ApiRuntimeHostProtocol,
        application_facade: ApplicationFacade,
    ) -> None:
        """Инициализирует менеджер API runtime.

        Args:
            host: Runtime-host, который хранит lifecycle состояние API.
            application_facade: Публичный command/query facade приложения.
        """
        self._host = host
        self._application_facade = application_facade
        self._lifecycle = ApiLifecycleManager()

    def _get_lifecycle_state(self) -> ApiLifecycleState:
        """Возвращает текущее lifecycle-состояние API runtime."""
        return self._lifecycle.get_state()

    def _set_lifecycle_state(self, state: ApiLifecycleState) -> None:
        """Обновляет lifecycle-состояние API runtime."""
        self._lifecycle.set_state(state)

    @staticmethod
    def _normalize_api_key(value: Any) -> str | None:
        """Нормализует значение API ключа к строке или None."""
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    def get_effective_api_key(self) -> str | None:
        """Возвращает актуальный API ключ без побочных эффектов."""
        stored_api_key = self._normalize_api_key(api_auth.get_stored_api_key())
        if stored_api_key is not None:
            return stored_api_key

        config_api_key = self._normalize_api_key(
            config_module.get_config().settings.api.api_key
        )
        if config_api_key is not None:
            return config_api_key

        return None

    def migrate_legacy_api_key_if_needed(self) -> str | None:
        """Мигрирует API ключ из legacy config в env при необходимости."""
        stored_api_key = self._normalize_api_key(api_auth.get_stored_api_key())
        if stored_api_key is not None:
            return stored_api_key

        config = config_module.get_config()
        config_api_key = self._normalize_api_key(config.settings.api.api_key)
        if config_api_key is None:
            return None

        self.sync_api_key_env(config_api_key)
        config.settings.api.api_key = None
        config.save()
        return config_api_key

    def sync_api_key_env(self, api_key: str | None) -> None:
        """Синхронизирует API ключ с постоянным хранилищем и env."""
        api_auth.set_stored_api_key(api_key)

    def start_api_server(self, force: bool = False) -> dict[str, Any]:
        """Запускает API сервер."""
        if not self._lifecycle.try_begin_start():
            logger.warning(
                "API lifecycle занят переходом состояния: %s",
                self._get_lifecycle_state(),
            )
            return {
                "success": False,
                "running": bool(
                    (server := self._host.get_api_server_instance())
                    is not None
                    and server.is_running()
                ),
                "error": "API lifecycle busy",
            }

        try:
            self.migrate_legacy_api_key_if_needed()
            api_config = self.get_api_runtime_settings()

            if not force and not api_config.get("enabled", True):
                self._set_lifecycle_state("stopped")
                logger.info("API сервер отключен настройками")
                return {"success": False, "running": False}

            from api.routes import register_routes
            from api.server import APIServer

            if (
                server := self._host.get_api_server_instance()
            ) is not None and server.is_running():
                self._set_lifecycle_state("running")
                logger.info("API сервер уже запущен")
                return {"success": True, "status": self.get_api_status()}

            api_server = APIServer(
                host=api_config.get("host", "127.0.0.1"),
                port=api_config.get("port", 5000),
                server_threads=api_config.get("server_threads", 4),
                api_key=api_config.get("api_key"),
            )
            self._host.set_api_server_instance(api_server)
            self.sync_api_key_env(api_config.get("api_key"))

            resolved_api_key = api_server.get_runtime_api_key()
            if resolved_api_key and resolved_api_key != api_config.get(
                "api_key"
            ):
                api_settings = config_module.get_config().settings.api
                api_settings.api_key = None
                config_module.get_config().save()
            self.sync_api_key_env(resolved_api_key)
            api_server.set_websocket_manager(
                self._host.get_websocket_manager_instance()
            )

            # Регистрация маршрутов API.
            register_routes(api_server.app, api_server)

            # Настройка обратных вызовов API.
            self.setup_api_callbacks()

            # Запуск сервера.
            api_server.start()
            self._set_lifecycle_state("running")
            logger.info(f"API сервер запущен на {api_server.get_url()}")
            return {"success": True, "status": self.get_api_status()}
        except Exception:
            self._set_lifecycle_state("stopped")
            raise

    def get_api_runtime_settings(self) -> dict[str, Any]:
        """Возвращает runtime-настройки API для текущего режима запуска."""
        config_api = config_module.get_config().settings.api
        cli_api = self._host.get_runtime_config().get("api", {})

        if self._host.get_runtime_mode() == "gui":
            return {
                "enabled": config_api.enabled,
                "host": config_api.host,
                "port": config_api.port,
                "server_threads": config_api.server_threads,
                "api_key": self.get_effective_api_key(),
            }

        return {
            "enabled": cli_api.get("enabled", config_api.enabled),
            "host": cli_api.get("host", config_api.host),
            "port": cli_api.get("port", config_api.port),
            "server_threads": cli_api.get(
                "server_threads",
                config_api.server_threads,
            ),
            "api_key": self.get_effective_api_key(),
        }

    def get_api_status(self) -> dict[str, Any]:
        """Возвращает статус API для GUI."""
        config_api = config_module.get_config().settings.api
        effective_api_key = self.get_effective_api_key()
        runtime_status = (
            server.get_status()
            if (server := self._host.get_api_server_instance()) is not None
            else {
                "running": False,
                "host": config_api.host,
                "port": config_api.port,
                "url": f"http://{config_api.host}:{config_api.port}",
                "api_key_set": bool(effective_api_key),
            }
        )

        runtime_status["configured"] = {
            "enabled": config_api.enabled,
            "host": config_api.host,
            "port": config_api.port,
            "server_threads": config_api.server_threads,
            "api_key": effective_api_key,
        }
        runtime_status["log_dir"] = str(get_api_log_dir())
        runtime_status["lifecycle_state"] = self._get_lifecycle_state()
        return runtime_status

    def apply_api_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        """Применяет настройки API из GUI."""
        config = config_module.get_config()
        api_settings = config.settings.api
        original_enabled = api_settings.enabled
        original_host = api_settings.host
        original_port = api_settings.port
        original_server_threads = api_settings.server_threads
        original_api_key = api_settings.api_key
        updated_fields: list[str] = []
        restart_required = False
        server_running = bool(
            (server := self._host.get_api_server_instance()) is not None
            and server.is_running()
        )
        proposed = {
            "enabled": api_settings.enabled,
            "host": api_settings.host,
            "port": api_settings.port,
            "server_threads": api_settings.server_threads,
            "api_key": api_settings.api_key,
        }

        try:
            if "host" in data:
                host = str(data["host"])
                if host != api_settings.host:
                    proposed["host"] = host
                    updated_fields.append("host")
                    restart_required = restart_required or server_running

            if "port" in data:
                port = int(data["port"])
                if port != api_settings.port:
                    proposed["port"] = port
                    updated_fields.append("port")
                    restart_required = restart_required or server_running

            if "server_threads" in data:
                server_threads = max(1, int(data["server_threads"]))
                if server_threads != api_settings.server_threads:
                    proposed["server_threads"] = server_threads
                    updated_fields.append("server_threads")
                    restart_required = restart_required or server_running

            if (
                "enabled" in data
                and bool(data["enabled"]) != api_settings.enabled
            ):
                proposed["enabled"] = bool(data["enabled"])
                updated_fields.append("enabled")

            token_value = data.get("token", data.get("api_key"))
            api_key: str | None = None
            if token_value is not None:
                api_key = str(token_value).strip() or None
                current_api_key = self.get_effective_api_key()
                if api_key != current_api_key:
                    updated_fields.append("api_key")
                if proposed["api_key"] is not None:
                    proposed["api_key"] = None

            validated = config_module.APISettingsSchema.model_validate(
                proposed
            )
        except (TypeError, ValueError) as e:
            logger.warning("Невалидные значения API настроек: %s", e)
            return {
                "success": False,
                "error": str(e),
                "status": self.get_api_status(),
            }

        api_settings.enabled = validated.enabled
        api_settings.host = validated.host
        api_settings.port = validated.port
        api_settings.server_threads = validated.server_threads
        api_settings.api_key = validated.api_key

        persisted = config.save()
        if not persisted:
            api_settings.enabled = original_enabled
            api_settings.host = original_host
            api_settings.port = original_port
            api_settings.server_threads = original_server_threads
            api_settings.api_key = original_api_key
            return {
                "success": False,
                "error": "Не удалось сохранить настройки API",
                "status": self.get_api_status(),
            }

        if "api_key" in updated_fields:
            server = self._host.get_api_server_instance()
            if server is not None:
                server.set_api_key(api_key)
            self.sync_api_key_env(api_key)

        return {
            "success": True,
            "updated_fields": updated_fields,
            "restart_required": restart_required,
            "status": self.get_api_status(),
        }

    def stop_api_server(self) -> dict[str, Any]:
        """Останавливает API сервер."""
        if not self._lifecycle.try_begin_stop():
            logger.warning(
                "Остановка API отклонена: lifecycle в состоянии starting"
            )
            return {
                "success": False,
                "running": bool(
                    (server := self._host.get_api_server_instance())
                    is not None
                    and server.is_running()
                ),
                "error": "API lifecycle busy",
            }

        server = self._host.get_api_server_instance()
        if server is None:
            self._set_lifecycle_state("stopped")
            return {"success": True, "running": False}

        server.stop()
        self._host.set_api_server_instance(None)
        self._set_lifecycle_state("stopped")
        return {"success": True, "running": False}

    def restart_api_server(self) -> dict[str, Any]:
        """Перезапускает API сервер."""
        self.stop_api_server()
        return self.start_api_server(force=True)

    def open_api_logs_folder(self) -> None:
        """Открывает папку с логами API."""
        open_api_logs_folder()

    def setup_api_callbacks(self) -> None:
        """Подключает runtime callbacks к API серверу."""
        server = self._host.get_api_server_instance()
        if not server:
            return

        facade = self._application_facade
        server.set_callback("status", facade.get_status)
        server.set_callback("start", facade.start_recording)
        server.set_callback("stop", facade.stop_recording)
        server.set_callback("pause", facade.toggle_pause)
        server.set_callback("recordings", facade.get_recordings)
        server.set_callback("get_schedule", facade.get_schedule)
        server.set_callback("create_schedule", facade.create_schedule)
        server.set_callback("delete_schedule", facade.delete_schedule)
        server.set_callback("update_schedule", facade.update_schedule)
        server.set_callback("toggle_schedule", facade.toggle_schedule)
        server.set_callback("devices", facade.get_devices)
        server.set_callback("windows", facade.get_windows)
        server.set_callback("get_config", facade.get_config_snapshot)
        server.set_callback("update_config", facade.update_config)
