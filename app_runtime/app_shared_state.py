"""Общие протоколы координаторов и состояние VideoRecorderApp (#176).

Базовый класс `AppSharedState` объявляет атрибуты, инициализируемые в
`VideoRecorderApp.__init__`, и сигнатуры методов соседних миксинов —
это даёт mypy полную типизацию миксинов без циклических импортов.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from api.websocket import WebSocketManager
from app_runtime.constants import GUI_DEFAULT_TIMEOUT_SECONDS
from app_runtime.thread_executor import MainThreadExecutor
from core.api_runtime_manager import ApiRuntimeManager
from core.application_facade import ApplicationFacade
from core.cloud.manager import CloudSyncManager
from core.command_queue import CommandQueue
from core.library.manager import LibraryManager
from core.lifecycle import GracefulShutdown
from core.multi_recording_service import MultiRecordingService
from core.plugins.manager import PluginManager
from core.post_processing.manager import PostProcessingManager
from core.recording_service import RecordingService
from core.updater.updater import AppUpdater
from core.webhook import WebhookNotifier

if TYPE_CHECKING:
    from api.server import APIServer
    from gui.main_window import MainWindow
    from gui.tray_icon import TrayIcon
    from scheduler.task_scheduler import TaskScheduler


class _GuiRuntimeCoordinatorProtocol(Protocol):
    """Минимальный контракт GUI runtime coordinator."""

    def run(self) -> int:
        """Запускает GUI runtime."""


class _RecordingRuntimeCoordinatorProtocol(Protocol):
    """Минимальный контракт recording runtime coordinator."""

    def get_status(self) -> dict[str, Any]:
        """Возвращает статус записи."""

    def start_recording(
        self,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Запускает запись."""

    def stop_recording(self) -> dict[str, Any]:
        """Останавливает запись."""

    def toggle_pause(self) -> dict[str, Any]:
        """Переключает паузу записи."""

    def switch_capture_source(self, params: dict[str, Any]) -> dict[str, Any]:
        """Переключает источник захвата активной записи без остановки."""

    def get_recordings(self) -> list[Any]:
        """Возвращает недавние записи."""

    def get_metrics(self) -> dict[str, Any]:
        """Возвращает текущие метрики кадров записи (#114)."""

    def get_finalization_status(self) -> dict[str, Any]:
        """Возвращает статус финализации записи (#151)."""


class _ApiRuntimeCoordinatorProtocol(Protocol):
    """Минимальный контракт API runtime coordinator."""

    def sync_api_key_env(self, api_key: str | None) -> None:
        """Синхронизирует API ключ."""

    def get_effective_api_key(self) -> str | None:
        """Возвращает актуальный API ключ."""

    def start_api_server(self, force: bool = False) -> dict[str, Any]:
        """Запускает API сервер."""

    def get_api_runtime_settings(self) -> dict[str, Any]:
        """Возвращает runtime-настройки API."""

    def get_api_status(self) -> dict[str, Any]:
        """Возвращает статус API."""

    def apply_api_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        """Применяет API-настройки."""

    def stop_api_server(self) -> dict[str, Any]:
        """Останавливает API сервер."""

    def restart_api_server(self) -> dict[str, Any]:
        """Перезапускает API сервер."""

    def open_api_logs_folder(self) -> None:
        """Открывает каталог API-логов."""

    def setup_api_callbacks(self) -> None:
        """Регистрирует callbacks API."""


class AppSharedState:
    """Декларации атрибутов и кросс-миксиновых методов (#176).

    Атрибуты инициализируются в `VideoRecorderApp.__init__`; методы
    реализованы в миксинах (MRO ставит их выше этого базового класса).
    """

    # --- Runtime-состояние (инициализация в __init__) ---
    _config: dict[str, Any]
    _mode: str
    _app: Any | None
    _main_window: MainWindow | None
    _tray_icon: TrayIcon | None
    _api_server: APIServer | None
    _scheduler: TaskScheduler | None
    _running: bool
    _shutdown_manager: GracefulShutdown | None
    _recording_service: RecordingService
    _websocket_manager: WebSocketManager
    _webhook_notifier: WebhookNotifier
    _multi_recording_service: MultiRecordingService
    _plugin_manager: PluginManager
    _library_manager: LibraryManager
    _cloud_sync_manager: CloudSyncManager
    _post_processing_manager: PostProcessingManager
    _updater: AppUpdater
    _command_queue: CommandQueue
    _gui_executor: MainThreadExecutor | None
    _gui_thread_id: int | None
    _gui_runtime_coordinator: _GuiRuntimeCoordinatorProtocol
    _recording_runtime_coordinator: _RecordingRuntimeCoordinatorProtocol
    _application_service: ApplicationFacade
    _api_runtime_manager: ApiRuntimeManager
    _api_runtime_coordinator: _ApiRuntimeCoordinatorProtocol

    # --- Кросс-миксиновые методы (реализация в конкретном миксине) ---

    def _run_on_gui_thread(
        self, fn: Any, timeout: float | None = GUI_DEFAULT_TIMEOUT_SECONDS
    ) -> Any:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _get_status(self) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _get_recording_metrics(self) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _start_recording(self, params: dict[str, Any]) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _stop_recording(self) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _toggle_pause(self) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _switch_capture_source(self, params: dict[str, Any]) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _start_multi_recording(self, params: dict[str, Any]) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _stop_multi_recording(self) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _get_multi_recording_status(self) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _get_recordings(self) -> list[Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _get_schedule(self) -> list:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _create_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _delete_schedule(self, task_id: str) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _delete_schedules(self, task_ids: list) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _toggle_schedules(
        self, task_ids: list, enabled: bool
    ) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _update_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _toggle_schedule(self, task_id: str, enabled: bool) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _get_devices(self) -> dict[str, list]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _get_windows(self) -> list:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _get_monitors(self) -> list:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _get_disk_space(self) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _get_webhook_config(self) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _configure_webhook(
        self, url: str | None, secret: str | None, enabled: bool
    ) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _test_webhook(self) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _verify_recording_file(self, file_path: str) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _repair_recording_file(self, file_path: str) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _get_config(self) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _update_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _start_api_server(self, force: bool = False) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _get_api_status(self) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _apply_api_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _stop_api_server(self) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _restart_api_server(self) -> dict[str, Any]:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _open_api_logs_folder(self) -> None:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def _run_headless(self) -> int:
        """См. реализацию в соответствующем миксине (#176)."""
        raise NotImplementedError

    def get_application_facade(self) -> ApplicationFacade:
        """Фасад приложения для внешних слоёв (ядро VideoRecorderApp)."""
        raise NotImplementedError
