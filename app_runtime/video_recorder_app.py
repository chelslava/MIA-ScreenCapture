"""Класс приложения VideoRecorderApp (#176).

Ядро runtime: протоколы координаторов, инициализация, режимы
gui/headless, API-обёртки, graceful shutdown. Группы операций
вынесены в миксины того же пакета; для обратной совместимости
класс ре-экспортируется из main.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from api.server import APIServer
    from gui.main_window import MainWindow
    from gui.tray_icon import TrayIcon
    from scheduler.task_scheduler import TaskScheduler
from app_runtime.app_api_callbacks_mixin import ApiCallbacksMixin
from app_runtime.app_cli_proxy_mixin import CliProxyMixin
from app_runtime.app_facade_ops_mixin import FacadeOpsMixin
from app_runtime.app_hotkeys_mixin import HotkeysMixin
from app_runtime.app_platform_ops_mixin import PlatformOpsMixin
from app_runtime.app_scheduler_mixin import SchedulerOpsMixin
from app_runtime.app_settings_ops_mixin import SettingsOpsMixin
from config import get_config
from core.geometry import ensure_process_dpi_awareness
from core.lifecycle import GracefulShutdown, get_shutdown_manager
from exceptions import (
    ConfigValidationError,
    RecordingError,
    SchedulerError,
)
from logger_config import get_module_logger
from recorder.utils import (
    check_ffmpeg,
)

logger = get_module_logger(__name__)

# Режимы, требующие полного рантайма и single-instance guard (#176/#184)
_SINGLE_INSTANCE_MODES = ("gui", "headless")


class VideoRecorderApp(
    # ApiCallbacksMixin первым: его реализациям кросс-миксиновых
    # методов нужно перекрывать заглушки AppSharedState в MRO (#176)
    ApiCallbacksMixin,
    CliProxyMixin,
    FacadeOpsMixin,
    HotkeysMixin,
    SchedulerOpsMixin,
    SettingsOpsMixin,
    PlatformOpsMixin,
):
    """
    Главный класс приложения.

    Управляет всеми компонентами:
    - GUI (опционально)
    - API сервер
    - Планировщик задач
    - Менеджер записи
    """

    def __init__(self, config: dict[str, Any]):
        """
        Инициализация приложения.

        Args:
            config: Разобранная конфигурация из CLI
        """
        # Per-monitor DPI-awareness до любых Win32/Qt обращений к
        # геометрии: иначе headless-режим (API/CLI/Service) получает
        # виртуализованные координаты мониторов, не совпадающие с
        # физическими кадрами WGC (#200).
        ensure_process_dpi_awareness()

        self._config = config
        self._mode = config.get("mode", "gui")

        # Компоненты
        self._app: Any | None = None  # QApplication
        self._main_window: MainWindow | None = None
        self._tray_icon: TrayIcon | None = None
        self._api_server: APIServer | None = None
        self._scheduler: TaskScheduler | None = None

        # Состояние
        self._running = False

        # Graceful shutdown менеджер
        self._shutdown_manager: GracefulShutdown | None = None
        if self._mode in _SINGLE_INSTANCE_MODES:
            # Полный рантайм: GUI и headless используют все сервисы.
            # CLI-прокси-режимы (--start/--stop/--status/...) создают
            # сервисы лениво — им нужен только REST-прокси (#184).
            self._init_runtime_services()
        else:
            # Сентинелы: ленивая инициализация при первом обращении
            # (см. _init_runtime_services / _ensure_runtime_services).
            for attr in (
                "_recording_service",
                "_websocket_manager",
                "_webhook_notifier",
                "_multi_recording_service",
                "_plugin_manager",
                "_library_manager",
                "_cloud_sync_manager",
                "_post_processing_manager",
                "_updater",
                "_command_queue",
                "_gui_executor",
                "_gui_thread_id",
                "_gui_runtime_coordinator",
                "_recording_runtime_coordinator",
                "_application_service",
                "_api_runtime_manager",
                "_api_runtime_coordinator",
            ):
                setattr(self, attr, None)

    def _init_runtime_services(self) -> None:
        """Инициализация полного набора runtime-сервисов (#184).

        Тяжёлые импорты (Flask через api.*, PyQt6 через gui.*) выполняются
        только для режимов gui/headless — CLI-прокси их не платит.
        """
        from api.websocket import WebSocketManager
        from app_runtime.api_coordinator import ApiRuntimeCoordinator
        from app_runtime.gui_coordinator import GuiRuntimeCoordinator
        from app_runtime.recording_coordinator import (
            RecordingRuntimeCoordinator,
        )
        from core.api_runtime_manager import ApiRuntimeManager
        from core.application_service import ApplicationService
        from core.cloud.manager import CloudSyncManager
        from core.command_queue import CommandQueue
        from core.library.manager import LibraryManager
        from core.multi_recording_service import MultiRecordingService
        from core.plugins.manager import PluginManager
        from core.post_processing.manager import PostProcessingManager
        from core.recording_service import RecordingService
        from core.updater.updater import AppUpdater
        from core.webhook import WebhookNotifier
        from gui.backends import GUIRecordingBackend

        self._recording_service = RecordingService(
            backend=GUIRecordingBackend()
        )
        self._websocket_manager = WebSocketManager()
        self._websocket_manager.attach_event_bus(
            self._recording_service.event_bus
        )
        self._webhook_notifier = WebhookNotifier()
        self._webhook_notifier.attach_event_bus(
            self._recording_service.event_bus
        )
        # Мультиисточниковая запись (#51) — делит event_bus с
        # _recording_service: события доходят до тех же подписчиков.
        self._multi_recording_service = MultiRecordingService(
            event_bus=self._recording_service.event_bus
        )
        self._plugin_manager = PluginManager(
            event_bus=self._recording_service.event_bus,
        )
        self._plugin_manager.discover_and_load()
        self._library_manager = LibraryManager(
            event_bus=self._recording_service.event_bus,
        )
        self._cloud_sync_manager = CloudSyncManager(
            event_bus=self._recording_service.event_bus,
        )
        self._post_processing_manager = PostProcessingManager(
            event_bus=self._recording_service.event_bus,
            plugin_manager=self._plugin_manager,
        )
        self._updater = AppUpdater(
            event_bus=self._recording_service.event_bus,
        )
        self._command_queue = CommandQueue(maxsize=50)
        self._gui_executor = None
        self._gui_thread_id = None
        self._gui_runtime_coordinator = GuiRuntimeCoordinator(self)
        self._recording_runtime_coordinator = RecordingRuntimeCoordinator(self)
        self._application_service = ApplicationService(self)
        self._api_runtime_manager = ApiRuntimeManager(
            self,
            self._application_service,
        )
        self._api_runtime_coordinator = ApiRuntimeCoordinator(
            self._api_runtime_manager
        )

    def _ensure_runtime_services(self) -> None:
        """Ленивая инициализация сервисов для fallback-путей CLI (#184)."""
        if self._recording_service is None:
            self._init_runtime_services()

    def run(self) -> int:
        """
        Запуск приложения.

        Returns:
            Код выхода
        """
        try:
            # Инициализация graceful shutdown
            self._setup_graceful_shutdown()

            # Проверка FFmpeg
            ffmpeg_status = check_ffmpeg()
            if not ffmpeg_status.available:
                logger.warning(
                    "FFmpeg не найден. Кодирование видео может работать некорректно. "
                    "Пожалуйста, установите FFmpeg с https://ffmpeg.org/download.html"
                )

            # Запуск в зависимости от режима
            if self._mode == "gui":
                return self._run_gui()
            elif self._mode == "headless":
                return self._run_headless()
            elif self._mode == "start":
                return self._run_start()
            elif self._mode == "stop":
                return self._run_stop()
            elif self._mode == "status":
                return self._run_status()
            elif self._mode == "schedule_list":
                return self._run_schedule_list()
            elif self._mode == "schedule_create":
                return self._run_schedule_create()
            elif self._mode == "schedule_update":
                return self._run_schedule_update()
            elif self._mode == "schedule_delete":
                return self._run_schedule_delete()
            elif self._mode == "schedule_toggle":
                return self._run_schedule_toggle()
            elif self._mode == "schedule_preview":
                return self._run_schedule_preview()
            elif self._mode == "list_presets":
                return self._run_list_presets()
            elif self._mode == "plugins_list":
                return self._run_plugins_list()
            elif self._mode == "plugins_info":
                return self._run_plugins_info()
            elif self._mode == "plugins_enable":
                return self._run_plugins_enable()
            elif self._mode == "plugins_disable":
                return self._run_plugins_disable()
            elif self._mode == "service":
                return self._run_service()
            else:
                logger.error(f"Неизвестный режим: {self._mode}")
            return 1

        except KeyboardInterrupt:
            logger.info("Прервано пользователем")
            return 0
        except (
            RecordingError,
            SchedulerError,
            ConfigValidationError,
            OSError,
            RuntimeError,
            ValueError,
        ) as e:
            logger.error(f"Ошибка приложения: {e}")
            return 1
        except Exception as e:
            # Последний барьер: непредвиденные исключения от сторонних компонентов
            logger.exception(f"Непредвиденная ошибка приложения: {e}")
            return 1
        finally:
            self._cleanup()

    def _run_gui(self) -> int:
        """Запуск с GUI."""
        return self._gui_runtime_coordinator.run()

    def _run_headless(self) -> int:
        """Запуск в режиме без интерфейса (только API)."""
        logger.info("Запуск в режиме без интерфейса")

        # Запуск API сервера
        self._start_api_server()

        # Запуск планировщика
        self._start_scheduler()

        self._running = True

        # Поддержание работы до прерывания
        try:
            import time

            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            self._running = False

        return 0

    def _start_api_server(self, force: bool = False) -> dict[str, Any]:
        """Запускает API сервер через менеджер runtime."""
        return self._api_runtime_coordinator.start_api_server(force=force)

    def _get_api_runtime_settings(self) -> dict[str, Any]:
        """Возвращает runtime-настройки API через менеджер."""
        return self._api_runtime_coordinator.get_api_runtime_settings()

    def _get_api_status(self) -> dict[str, Any]:
        """Возвращает статус API через менеджер runtime."""
        return self._api_runtime_coordinator.get_api_status()

    def _apply_api_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        """Применяет настройки API через менеджер runtime."""
        return self._api_runtime_coordinator.apply_api_settings(data)

    def _stop_api_server(self) -> dict[str, Any]:
        """Останавливает API сервер через менеджер runtime."""
        return self._api_runtime_coordinator.stop_api_server()

    def _restart_api_server(self) -> dict[str, Any]:
        """
        Перезапуск API сервера.

        Returns:
            Словарь с результатом операции.
        """
        return self._api_runtime_coordinator.restart_api_server()

    def _open_api_logs_folder(self) -> None:
        """Открывает папку с логами API через менеджер runtime."""
        self._api_runtime_coordinator.open_api_logs_folder()

    def _setup_api_callbacks(self) -> None:
        """Настраивает обратные вызовы API через менеджер runtime."""
        self._api_runtime_coordinator.setup_api_callbacks()

    def _handle_close_requested(self, event: Any) -> None:
        """Обработка запроса закрытия окна через сигнал.

        Параметр ``event`` может быть как самим QCloseEvent, так и
        словарём ``{"event": QCloseEvent, "force_minimize_to_tray": bool}``
        (см. MainWindow.closeEvent — явный выбор «свернуть» при активной
        записи, #94/#90).
        """
        config = get_config()

        # Приводим сигнал к единому виду.
        force_minimize_to_tray = False
        if isinstance(event, dict):
            force_minimize_to_tray = bool(
                event.get("force_minimize_to_tray", False)
            )
            event = event.get("event")

        if event is None:
            return

        # Решаем, сворачивать ли в трей:
        # 1) Явный запрос пользователя из диалога главного окна
        #    (force_minimize_to_tray=True).
        # 2) Глобальная настройка ``minimize_to_tray``.
        should_minimize = bool(config.settings.minimize_to_tray)
        if force_minimize_to_tray:
            should_minimize = True

        if should_minimize and self._tray_icon:
            event.ignore()
            if self._main_window:
                self._main_window.hide()
            self._tray_icon.show_notification(
                "MIA-ScreenCapture", "Свернуто в трей"
            )
        else:
            # minimize_to_tray=False И нет явного «свернуть» — полный выход.
            self._quit_app()

    def _setup_graceful_shutdown(self) -> None:
        """
        Настройка graceful shutdown.

        Регистрирует обработчики для корректного завершения работы.
        """
        self._shutdown_manager = get_shutdown_manager()
        self._shutdown_manager.timeout = 30.0  # 30 секунд на завершение

        # Регистрация обработчиков в обратном порядке (LIFO)
        # Последний зарегистрированный выполнится первым

        # 0. Отключение подписчиков от EventBus — регистрируем ПЕРВЫМ,
        #    чтобы при LIFO-выполнении отключение прошло ПОСЛЕДНИМ,
        #    после остановки API сервера и записи (#100). Предотвращает
        #    доставку событий освобождённым объектам после завершения работы.
        self._shutdown_manager.register_handler(self._detach_event_subscribers)

        # 1. Очистка трея
        self._shutdown_manager.register_handler(self._cleanup_tray)

        # 2. Остановка API сервера
        self._shutdown_manager.register_handler(self._cleanup_api_server)

        # 3. Остановка планировщика
        self._shutdown_manager.register_handler(self._cleanup_scheduler)

        # 4. Остановка активной записи (критически важно!)
        self._shutdown_manager.register_handler(self._stop_active_recording)

        # 5. Сохранение конфигурации
        self._shutdown_manager.register_handler(self._save_config)

        # Установка обработчиков сигналов
        self._shutdown_manager.setup_signal_handlers()

        logger.info(
            f"Graceful shutdown настроен "
            f"({self._shutdown_manager.get_handlers_count()} обработчиков)"
        )

    def _stop_active_recording(self) -> None:
        """Остановка активной записи при завершении."""
        if self._main_window:
            try:
                status = self._main_window.get_status()
                if status.get("is_recording"):
                    logger.info("Остановка активной записи...")
                    gui_stop_result = self._main_window.stop_recording()
                    if gui_stop_result.get("success"):
                        logger.info(
                            f"Запись сохранена: {gui_stop_result.get('filepath', 'неизвестно')}"
                        )
                    else:
                        logger.error(
                            f"Ошибка при остановке записи: "
                            f"{gui_stop_result.get('error', 'неизвестная ошибка')}"
                        )
            except (RecordingError, OSError, RuntimeError) as e:
                logger.error(f"Ошибка при остановке записи: {e}")
        else:
            try:
                headless_stop_result: dict[str, Any] | None = (
                    self._recording_service.stop_active_recording_if_any()
                )
                if (
                    headless_stop_result is not None
                    and headless_stop_result.get("success")
                ):
                    logger.info(
                        f"Запись сохранена: {headless_stop_result.get('filepath', 'неизвестно')}"
                    )
            except (RecordingError, OSError, RuntimeError) as e:
                logger.error(f"Ошибка при остановке headless записи: {e}")

    def _save_config(self) -> None:
        """Сохранение конфигурации при завершении."""
        try:
            config = get_config()
            # Сначала flush debounce timer
            config.flush_debounced_saves()
            config.save()
            logger.info("Конфигурация сохранена")
        except (OSError, ValueError) as e:
            logger.error(f"Ошибка при сохранении конфигурации: {e}")

    def _cleanup_scheduler(self) -> None:
        """Остановка планировщика."""
        if self._scheduler:
            try:
                logger.info("Остановка планировщика...")
                self._scheduler.stop()
                logger.info("Планировщик остановлен")
            except (SchedulerError, OSError, RuntimeError) as e:
                logger.error(f"Ошибка при остановке планировщика: {e}")

    def _cleanup_api_server(self) -> None:
        """Остановка API сервера."""
        if self._api_server:
            try:
                logger.info("Остановка API сервера...")
                self._api_server.stop()
                logger.info("API сервер остановлен")
            except (OSError, RuntimeError) as e:
                logger.error(f"Ошибка при остановке API сервера: {e}")

    def _cleanup_tray(self) -> None:
        """Очистка трея."""
        if self._tray_icon:
            try:
                logger.info("Очистка трея...")
                self._tray_icon.cleanup()
                logger.info("Трей очищен")
            except (OSError, RuntimeError) as e:
                logger.error(f"Ошибка при очистке трея: {e}")

    def _quit_app(self) -> None:
        """Выход из приложения."""
        self._running = False

        # Graceful shutdown будет вызван в _cleanup() в finally блоке
        if self._main_window:
            self._main_window.close()

        if self._app:
            self._app.quit()

    def _detach_event_subscribers(self) -> None:
        """Отключает WebSocket и webhook подписчиков от EventBus (#100).

        Идемпотентно: повторные вызовы безопасны, отсутствующие
        подписчики (частичная инициализация) не приводят к ошибке.
        """
        if hasattr(self, "_webhook_notifier"):
            try:
                self._webhook_notifier.detach_event_bus()
            except AttributeError:
                pass
        if hasattr(self, "_websocket_manager"):
            try:
                self._websocket_manager.detach_event_bus()
            except AttributeError:
                pass

    def _cleanup(self) -> None:
        """
        Очистка ресурсов.

        Вызывается в finally блоке метода run().
        Если graceful shutdown ещё не был запущен, запускает его.
        """
        if self._shutdown_manager:
            # Graceful shutdown через менеджер
            if not self._shutdown_manager.is_shutting_down:
                self._shutdown_manager.shutdown()
        else:
            # Fallback: базовая очистка если shutdown manager не инициализирован
            logger.info("Очистка (fallback)...")
            # Отключение от EventBus — единый идемпотентный путь (#100)
            self._detach_event_subscribers()
            # Остановка активной записи (критически важно!)
            self._stop_active_recording()
            # Сохранение конфигурации
            self._save_config()
            # Остановка горячих клавиш
            if hasattr(self, "_hotkeys"):
                self._hotkeys.stop()
            # Остановка компонентов в обратном порядке
            self._cleanup_scheduler()
            self._cleanup_api_server()
            self._cleanup_tray()
            logger.info("Очистка завершена")
