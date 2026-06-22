#!/usr/bin/env python3
"""
MIA-ScreenCapture - Главная точка входа
======================================

Профессиональный видеозаписывающий рекордер экрана с GUI, REST API,
планировщиком и поддержкой интерфейса командной строки.

Использование:
    python main.py                          # Запуск с GUI
    python main.py --headless               # Запуск без GUI (только API)
    python main.py --start                  # Начать запись немедленно
    python main.py --start --area rect --rect 100 100 800 600
    python main.py --stop                   # Остановить текущую запись
    python main.py --status                 # Показать статус записи
"""

import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

# Добавление родительской директории в путь для импорта
sys.path.insert(0, str(Path(__file__).parent))

# Загрузка .env файла ДО любых импортов, использующих переменные окружения
from dotenv import load_dotenv

if TYPE_CHECKING:
    from api.server import APIServer
    from gui.main_window import MainWindow
    from gui.tray_icon import TrayIcon
    from scheduler.task_scheduler import TaskScheduler

from api.auth import (
    API_KEY_ENV_VAR,
    API_KEY_HEADER,
)
from api.websocket import WebSocketManager
from app_runtime.api_coordinator import ApiRuntimeCoordinator
from app_runtime.constants import GUI_DEFAULT_TIMEOUT_SECONDS
from app_runtime.gui_coordinator import GuiRuntimeCoordinator
from app_runtime.recording_coordinator import RecordingRuntimeCoordinator
from app_runtime.thread_executor import MainThreadExecutor
from cli.parser import (
    parse_args,
    print_schedule_list,
    print_status,
    validate_recording_params,
)
from config import get_config, init_config
from core.api_runtime_manager import ApiRuntimeManager
from core.application_facade import ApplicationFacade
from core.application_service import ApplicationService
from core.lifecycle import GracefulShutdown, get_shutdown_manager
from core.recording_service import RecordingService
from core.webhook import (
    WebhookNotifier,
    WebhookSender,
    generate_webhook_secret,
)
from exceptions import (
    ConfigValidationError,
    RecordingError,
    SchedulerError,
    TaskValidationError,
)
from gui.backends import GUIRecordingBackend
from logger_config import get_module_logger, setup_logger
from recorder.utils import (
    check_ffmpeg,
    get_audio_devices,
    get_available_windows,
    get_disk_space_status,
)
from single_instance import SingleInstanceGuard, bring_existing_window_to_front

logger = get_module_logger(__name__)

_SINGLE_INSTANCE_MODES = ("gui", "headless")


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

    def get_recordings(self) -> list[Any]:
        """Возвращает недавние записи."""


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


def _load_environment() -> None:
    """Загружает переменные окружения из `.env` при наличии файла."""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def _handle_already_running(mode: str) -> int:
    """
    Обрабатывает запуск при уже работающем экземпляре приложения.

    Args:
        mode: Режим запуска текущего (второго) процесса.

    Returns:
        Код выхода 0 — это штатный сценарий, а не ошибка пользователя.
    """
    logger.info("Другой экземпляр MIA-ScreenCapture уже запущен. Завершение.")
    print("MIA-ScreenCapture уже запущен.")

    if mode == "gui":
        bring_existing_window_to_front()

    return 0


class VideoRecorderApp:
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
        # Headless-friendly сервис записи (используется как fallback без GUI)
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
        self._gui_executor: MainThreadExecutor | None = None
        self._gui_thread_id: int | None = None
        self._gui_runtime_coordinator: _GuiRuntimeCoordinatorProtocol = (
            GuiRuntimeCoordinator(self)
        )
        self._recording_runtime_coordinator: _RecordingRuntimeCoordinatorProtocol = RecordingRuntimeCoordinator(
            self
        )
        self._application_service: ApplicationFacade = ApplicationService(self)
        self._api_runtime_manager = ApiRuntimeManager(
            self,
            self._application_service,
        )
        self._api_runtime_coordinator: _ApiRuntimeCoordinatorProtocol = (
            ApiRuntimeCoordinator(self._api_runtime_manager)
        )

    def get_application_facade(self) -> ApplicationFacade:
        """Возвращает concrete application facade для внешних consumers."""
        return self._application_service

    def request_start_recording(self) -> dict[str, Any]:
        """Интерактивный запуск записи из tray/hotkeys."""
        return self.start_recording()

    def get_runtime_config(self) -> dict[str, Any]:
        """Возвращает CLI/runtime конфигурацию приложения."""
        return self._config

    def get_runtime_mode(self) -> str:
        """Возвращает текущий режим запуска приложения."""
        return str(self._mode)

    def get_api_server_instance(self) -> "APIServer | None":
        """Возвращает текущий runtime API server instance."""
        return self._api_server

    def set_api_server_instance(self, server: "APIServer | None") -> None:
        """Устанавливает текущий runtime API server instance."""
        self._api_server = server

    def get_websocket_manager_instance(self) -> WebSocketManager:
        """Возвращает WebSocket manager приложения."""
        return self._websocket_manager

    def request_stop_recording(self) -> dict[str, Any]:
        """Интерактивный запрос остановки записи из tray/hotkeys."""
        if self._main_window:
            return cast(
                dict[str, Any],
                self._run_on_gui_thread(
                    self._main_window.request_stop_recording,
                    timeout=GUI_DEFAULT_TIMEOUT_SECONDS,
                ),
            )
        return self.stop_recording()

    def request_toggle_pause_recording(self) -> dict[str, Any]:
        """Интерактивное переключение паузы из tray/hotkeys."""
        if self._main_window:
            return cast(
                dict[str, Any],
                self._run_on_gui_thread(
                    self._main_window.request_toggle_pause,
                    timeout=GUI_DEFAULT_TIMEOUT_SECONDS,
                ),
            )
        return self.toggle_pause()

    def get_status(self) -> dict[str, Any]:
        """Возвращает публичный статус записи."""
        return self._get_status()

    def start_recording(
        self,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Запускает запись через публичный фасад приложения."""
        if params is None:
            return self._recording_runtime_coordinator.start_recording()
        return self._start_recording(params)

    def stop_recording(self) -> dict[str, Any]:
        """Останавливает запись через публичный фасад приложения."""
        return self._stop_recording()

    def toggle_pause(self) -> dict[str, Any]:
        """Переключает паузу через публичный фасад приложения."""
        return self._toggle_pause()

    def get_recordings(self) -> list[Any]:
        """Возвращает список последних записей."""
        return self._get_recordings()

    def get_schedule(self) -> list[Any]:
        """Возвращает список задач планировщика."""
        return self._get_schedule()

    def create_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        """Создаёт задачу планировщика."""
        return self._create_schedule(data)

    def delete_schedule(self, task_id: str) -> dict[str, Any]:
        """Удаляет задачу планировщика."""
        return self._delete_schedule(task_id)

    def update_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        """Обновляет задачу планировщика."""
        return self._update_schedule(data)

    def toggle_schedule(
        self,
        task_id: str,
        enabled: bool,
    ) -> dict[str, Any]:
        """Переключает состояние задачи планировщика."""
        return self._toggle_schedule(task_id, enabled)

    def get_devices(self) -> dict[str, list[Any]]:
        """Возвращает список доступных аудиоустройств."""
        return self._get_devices()

    def get_windows(self) -> list[Any]:
        """Возвращает список доступных окон."""
        return self._get_windows()

    def get_disk_space(self) -> dict[str, Any]:
        """Возвращает статус свободного места на диске для пути записи."""
        return self._get_disk_space()

    def get_webhook_config(self) -> dict[str, Any]:
        """Возвращает настройки webhook (без значения секрета)."""
        return self._get_webhook_config()

    def configure_webhook(
        self, url: str | None, secret: str | None, enabled: bool
    ) -> dict[str, Any]:
        """Настраивает webhook-уведомления."""
        return self._configure_webhook(url, secret, enabled)

    def test_webhook(self) -> dict[str, Any]:
        """Отправляет тестовое webhook-уведомление."""
        return self._test_webhook()

    def get_config_snapshot(self) -> dict[str, Any]:
        """Возвращает snapshot текущей конфигурации."""
        return self._get_config()

    def update_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """Обновляет конфигурацию через публичный фасад."""
        return self._update_config(data)

    def start_api_server(self, force: bool = False) -> dict[str, Any]:
        """Запускает API сервер через публичный фасад."""
        return self._start_api_server(force=force)

    def get_api_status(self) -> dict[str, Any]:
        """Возвращает статус API через публичный фасад."""
        return self._get_api_status()

    def apply_api_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        """Применяет настройки API через публичный фасад."""
        return self._apply_api_settings(data)

    def stop_api_server(self) -> dict[str, Any]:
        """Останавливает API сервер через публичный фасад."""
        return self._stop_api_server()

    def restart_api_server(self) -> dict[str, Any]:
        """Перезапускает API сервер через публичный фасад."""
        return self._restart_api_server()

    def open_api_logs_folder(self) -> None:
        """Открывает каталог логов API через публичный фасад."""
        self._api_runtime_coordinator.open_api_logs_folder()

    def _get_api_headers(self) -> dict:
        """
        Получение заголовков для API запросов с аутентификацией.

        Returns:
            Словарь с заголовками, включая API ключ если он установлен.
        """
        api_key = self._get_effective_api_key()
        if api_key:
            return {API_KEY_HEADER: api_key}
        return {}

    def _sync_api_key_env(self, api_key: str | None) -> None:
        """Синхронизирует API ключ через менеджер runtime."""
        self._api_runtime_coordinator.sync_api_key_env(api_key)

    def _get_effective_api_key(self) -> str | None:
        """Возвращает актуальный API ключ через менеджер runtime."""
        return self._api_runtime_coordinator.get_effective_api_key()

    def _handle_unauthorized_response(self) -> int:
        """
        Обработка ответа 401 Unauthorized.

        Returns:
            Код выхода (1) с выводом сообщения об ошибке.
        """
        print(
            f"Ошибка: Требуется аутентификация. Установите переменную окружения "
            f"{API_KEY_ENV_VAR} с API ключом.",
            file=sys.stderr,
        )
        return 1

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

    def _run_start(self) -> int:
        """Запуск записи через CLI."""
        params = self._config.get("recording", {})

        # Валидация параметров
        is_valid, error = validate_recording_params(params)
        if not is_valid:
            print(f"Ошибка: {error}", file=sys.stderr)
            return 1

        # Попытка подключения к запущенному экземпляру через API
        api_url = f"http://{self._config['api']['host']}:{self._config['api']['port']}"

        try:
            import requests

            # Проверка запущен ли API
            try:
                response = requests.get(f"{api_url}/health", timeout=2)
                if response.status_code == 200:
                    # Отправка команды запуска через API
                    headers = self._get_api_headers()
                    response = requests.post(
                        f"{api_url}/api/start",
                        json={
                            "area": params["area_type"],
                            "rect": params["rect_coords"],
                            "window_title": params["window_title"],
                            "audio": params["audio_type"],
                            "output_path": params["output_path"],
                            "fps": params["fps"],
                            "codec": params["codec"],
                            "bitrate": params["bitrate"],
                            "duration": params["duration"],
                        },
                        headers=headers,
                        timeout=10,
                    )

                    if response.status_code == 401:
                        return self._handle_unauthorized_response()

                    if response.json().get("success"):
                        print("Запись начата")
                        return 0
                    else:
                        print(
                            f"Ошибка: {response.json().get('error', 'Неизвестная ошибка')}",
                            file=sys.stderr,
                        )
                        return 1
            except requests.exceptions.ConnectionError:
                pass  # API не запущен, запуск нового экземпляра
        except ImportError:
            pass  # requests недоступен

        # Запуск нового экземпляра в режиме без интерфейса
        logger.info("Запуск нового экземпляра записи")

        # Запускаем запись в текущем экземпляре без GUI
        result = self._recording_service.start_recording(params)
        if not result.get("success"):
            print(
                f"Ошибка: {result.get('error', 'Не удалось начать запись')}",
                file=sys.stderr,
            )
            return 1

        print("Запись начата")
        return self._run_headless()

    def _run_stop(self) -> int:
        """Остановка записи через CLI."""
        api_url = f"http://{self._config['api']['host']}:{self._config['api']['port']}"

        try:
            import requests

            headers = self._get_api_headers()
            response = requests.post(
                f"{api_url}/api/stop", headers=headers, timeout=10
            )

            if response.status_code == 401:
                return self._handle_unauthorized_response()

            if response.json().get("success"):
                print("Запись остановлена")
                return 0
            else:
                print(
                    f"Ошибка: {response.json().get('error', 'Неизвестная ошибка')}",
                    file=sys.stderr,
                )
                return 1

        except requests.exceptions.ConnectionError:
            print("Ошибка: Запущенный экземпляр не найден", file=sys.stderr)
            return 1
        except ImportError:
            print("Ошибка: библиотека requests недоступна", file=sys.stderr)
            return 1

    def _run_status(self) -> int:
        """Показ статуса записи через CLI."""
        api_url = f"http://{self._config['api']['host']}:{self._config['api']['port']}"

        try:
            import requests

            headers = self._get_api_headers()
            response = requests.get(
                f"{api_url}/api/status", headers=headers, timeout=10
            )

            if response.status_code == 401:
                return self._handle_unauthorized_response()

            if response.json().get("success"):
                status = response.json().get("data", {})
                print_status(status)
                return 0
            else:
                print("Ошибка: Не удалось получить статус", file=sys.stderr)
                return 1

        except requests.exceptions.ConnectionError:
            print("Статус: Не запущен (API сервер не найден)")
            return 0
        except ImportError:
            print("Ошибка: библиотека requests недоступна", file=sys.stderr)
            return 1

    def _run_schedule_list(self) -> int:
        """Список запланированных задач через CLI."""
        api_url = f"http://{self._config['api']['host']}:{self._config['api']['port']}"

        try:
            import requests

            headers = self._get_api_headers()
            response = requests.get(
                f"{api_url}/api/schedule", headers=headers, timeout=10
            )

            if response.status_code == 401:
                return self._handle_unauthorized_response()

            if response.json().get("success"):
                tasks = response.json().get("data", [])
                print_schedule_list(tasks)
                return 0
            else:
                print(
                    "Ошибка: Не удалось получить расписание", file=sys.stderr
                )
                return 1

        except requests.exceptions.ConnectionError:
            print("Ошибка: Запущенный экземпляр не найден", file=sys.stderr)
            return 1
        except ImportError:
            print("Ошибка: библиотека requests недоступна", file=sys.stderr)
            return 1

    def _run_schedule_create(self) -> int:
        """Создание запланированной задачи через CLI."""
        from cli.scheduler import create_schedule

        return int(create_schedule(self._config))

    def _run_schedule_update(self) -> int:
        """Обновление запланированной задачи через CLI."""
        from cli.scheduler import update_schedule

        return int(update_schedule(self._config))

    def _run_schedule_delete(self) -> int:
        """Удаление запланированной задачи через CLI."""
        from cli.scheduler import delete_schedule

        return int(delete_schedule(self._config))

    def _run_schedule_toggle(self) -> int:
        """Включение/выключение запланированной задачи через CLI."""
        from cli.scheduler import toggle_schedule

        return int(toggle_schedule(self._config))

    def _run_schedule_preview(self) -> int:
        """Просмотр предстоящих запусков через CLI."""
        from cli.scheduler import preview_upcoming_runs

        return int(preview_upcoming_runs(self._config))

    def _run_list_presets(self) -> int:
        """Показ списка preset шаблонов."""
        from cli.templates import print_presets_help

        print_presets_help()
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

    def _setup_hotkeys(self) -> None:
        """Настройка глобальных горячих клавиш."""
        from gui.hotkeys import GlobalHotkeys, HotkeyAction

        self._hotkeys = GlobalHotkeys()

        if not self._hotkeys.is_available:
            logger.warning("Горячие клавиши недоступны (pynput не установлен)")
            return

        self._hotkeys.register(
            HotkeyAction.TOGGLE_RECORDING,
            self._toggle_recording_hotkey,
        )
        self._hotkeys.register(
            HotkeyAction.PAUSE_RECORDING,
            self._pause_recording_hotkey,
        )
        self._hotkeys.start()
        logger.info("Горячие клавиши активированы")

    def _toggle_recording_hotkey(self) -> None:
        """Переключение записи по горячей клавише."""
        facade = self.get_application_facade()
        if self._main_window:
            if facade.get_status().get("is_recording", False):
                facade.request_stop_recording()
            else:
                facade.request_start_recording()

    def _pause_recording_hotkey(self) -> None:
        """Пауза записи по горячей клавише."""
        facade = self.get_application_facade()
        if self._main_window:
            facade.request_toggle_pause_recording()

    def _start_scheduler(self) -> None:
        """Запуск планировщика задач."""
        from scheduler.task_scheduler import TaskScheduler

        # Получение пути сохранения
        config = get_config()
        persist_path = Path(config.config_path).parent / "tasks.json"
        max_concurrent_tasks = config.settings.scheduler.max_concurrent_tasks

        self._scheduler = TaskScheduler(
            persist_path=persist_path,
            max_concurrent_tasks=max_concurrent_tasks,
        )
        assert self._scheduler is not None

        # Установка обратного вызова выполнения задачи
        self._scheduler.set_task_callback(self._execute_scheduled_task)

        # Запуск планировщика
        self._scheduler.start()

        # Обновление GUI если доступно
        if self._main_window:
            self._main_window.scheduler_tab.set_tasks(
                self._scheduler.get_all_tasks()
            )

            # Подключение сигналов вкладки планировщика
            self._main_window.scheduler_tab.task_created.connect(
                self._create_schedule
            )
            self._main_window.scheduler_tab.task_updated.connect(
                self._update_schedule
            )
            self._main_window.scheduler_tab.task_deleted.connect(
                self._delete_schedule
            )
            self._main_window.scheduler_tab.task_toggled.connect(
                self._toggle_schedule
            )

    def _execute_scheduled_task(self, params) -> None:
        """Выполнение запланированной задачи записи."""
        from scheduler.task_scheduler import RecordingParams

        if isinstance(params, RecordingParams):
            param_dict = {
                "area_type": params.area_type,
                "window_title": params.window_title,
                "rect_coords": params.rect_coords,
                "audio_type": params.audio_type,
                "output_path": params.output_path,
                "fps": params.fps,
                "codec": params.codec,
                "bitrate": params.bitrate,
                "duration": params.duration,
            }
            task_id = getattr(params, "task_id", "unknown")
        else:
            param_dict = params
            task_id = params.get("id", "unknown")

        logger.info(f"Выполнение запланированной задачи: {param_dict}")

        try:
            self.get_application_facade().start_recording(param_dict)
        except TimeoutError as e:
            logger.error(
                "Таймаут запуска записи из планировщика: task_id=%s, error=%s",
                task_id,
                e,
            )
        except (RecordingError, OSError, ValueError, RuntimeError) as e:
            logger.error(
                "Ошибка запуска записи из планировщика: task_id=%s, error=%s",
                task_id,
                e,
            )

    # Реализации обратных вызовов API

    def _run_on_gui_thread(
        self,
        fn: Any,
        timeout: float | None = GUI_DEFAULT_TIMEOUT_SECONDS,
    ) -> Any:
        """Безопасный синхронный вызов функции в GUI-потоке."""
        if not self._main_window:
            return fn()
        if self._gui_thread_id == threading.get_ident():
            return fn()
        if self._gui_executor is None:
            raise RuntimeError("GUI executor не инициализирован")
        return self._gui_executor.run_sync(fn, timeout=timeout)

    def _get_status(self) -> dict[str, Any]:
        """Получение статуса записи."""
        return self._recording_runtime_coordinator.get_status()

    def _start_recording(self, params: dict[str, Any]) -> dict[str, Any]:
        """Запуск записи."""
        return self._recording_runtime_coordinator.start_recording(params)

    def _stop_recording(self) -> dict[str, Any]:
        """Остановка записи."""
        return self._recording_runtime_coordinator.stop_recording()

    def _toggle_pause(self) -> dict[str, Any]:
        """Переключение состояния паузы."""
        return self._recording_runtime_coordinator.toggle_pause()

    def _get_recordings(self) -> list[Any]:
        """Получение недавних записей."""
        return self._recording_runtime_coordinator.get_recordings()

    def _get_schedule(self) -> list:
        """Получение запланированных задач."""
        if self._scheduler:
            return [task.to_dict() for task in self._scheduler.get_all_tasks()]
        return []

    def _create_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        """Создание запланированной задачи."""
        if not self._scheduler:
            return {"success": False, "error": "Планировщик недоступен"}

        try:
            task = self._scheduler.create_task_from_dict(data)
            success = self._scheduler.add_task(task)

            if success and self._main_window:
                self._run_on_gui_thread(
                    lambda: self._main_window.scheduler_tab.set_tasks(
                        self._scheduler.get_all_tasks()
                    )
                )

            return {
                "success": success,
                "task_id": task.id if success else None,
            }
        except (TaskValidationError, ValueError, RuntimeError) as e:
            return {"success": False, "error": str(e)}

    def _delete_schedule(self, task_id: str) -> dict[str, Any]:
        """Удаление запланированной задачи."""
        if not self._scheduler:
            return {"success": False, "error": "Планировщик недоступен"}

        success = self._scheduler.remove_task(task_id)

        if success and self._main_window:
            self._run_on_gui_thread(
                lambda: self._main_window.scheduler_tab.set_tasks(
                    self._scheduler.get_all_tasks()
                )
            )

        return {"success": success}

    def _update_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        """Обновление запланированной задачи."""
        if not self._scheduler:
            return {"success": False, "error": "Планировщик недоступен"}

        try:
            task = self._scheduler.create_task_from_dict(data)
            task.id = data.get("id", task.id)
            success = self._scheduler.update_task(task)

            if success and self._main_window:
                self._run_on_gui_thread(
                    lambda: self._main_window.scheduler_tab.set_tasks(
                        self._scheduler.get_all_tasks()
                    )
                )

            return {"success": success}
        except (TaskValidationError, ValueError, RuntimeError) as e:
            return {"success": False, "error": str(e)}

    def _toggle_schedule(self, task_id: str, enabled: bool) -> dict[str, Any]:
        """Переключение запланированной задачи."""
        if not self._scheduler:
            return {"success": False, "error": "Планировщик недоступен"}

        success = self._scheduler.enable_task(task_id, enabled)

        if success and self._main_window:
            self._run_on_gui_thread(
                lambda: self._main_window.scheduler_tab.set_tasks(
                    self._scheduler.get_all_tasks()
                )
            )

        return {"success": success, "enabled": enabled}

    def _get_devices(self) -> dict[str, list]:
        """Получение аудиоустройств."""
        return cast(dict[str, list], get_audio_devices())

    def _get_windows(self) -> list:
        """Получение доступных окон."""
        return cast(list, get_available_windows())

    def _get_disk_space(self) -> dict[str, Any]:
        """Получение статуса свободного места на диске для пути записи."""
        output_path = get_config().get_output_path()
        return get_disk_space_status(output_path)

    def _get_webhook_config(self) -> dict[str, Any]:
        """Получение настроек webhook (без значения секрета)."""
        api_settings = get_config().settings.api
        return {
            "url": api_settings.webhook_url,
            "enabled": api_settings.webhook_enabled,
            "has_secret": bool(api_settings.webhook_secret),
        }

    def _configure_webhook(
        self, url: str | None, secret: str | None, enabled: bool
    ) -> dict[str, Any]:
        """
        Настройка webhook-уведомлений.

        Если `secret` не передан явно: при наличии уже сохранённого секрета
        он сохраняется как есть; если секрета нет и `enabled=True` —
        генерируется новый (возвращается в ответе один раз, далее не
        раскрывается через `get_webhook_config`).
        """
        current_secret = get_config().settings.api.webhook_secret
        generated_secret: str | None = None

        if secret:
            resolved_secret = secret
        elif current_secret:
            resolved_secret = current_secret
        elif enabled:
            resolved_secret = generate_webhook_secret()
            generated_secret = resolved_secret
        else:
            resolved_secret = None

        result = self._update_config(
            {
                "api": {
                    "webhook_url": url,
                    "webhook_secret": resolved_secret,
                    "webhook_enabled": enabled,
                }
            }
        )
        if not result.get("success"):
            return result

        response: dict[str, Any] = {
            "success": True,
            "url": url,
            "enabled": enabled,
            "has_secret": bool(resolved_secret),
        }
        if generated_secret is not None:
            response["secret"] = generated_secret
        return response

    def _test_webhook(self) -> dict[str, Any]:
        """Отправка тестового webhook-уведомления текущими настройками."""
        api_settings = get_config().settings.api
        if not api_settings.webhook_url:
            return {"success": False, "error": "Webhook URL не настроен"}

        sender = WebhookSender()
        success, response_time_ms = sender.send(
            url=api_settings.webhook_url,
            event="webhook.test",
            data={"message": "Тестовое уведомление MIA-ScreenCapture"},
            secret=api_settings.webhook_secret,
        )
        return {"success": success, "response_time_ms": response_time_ms}

    def _get_config(self) -> dict[str, Any]:
        """Получение текущей конфигурации."""
        config = get_config()
        from dataclasses import asdict

        return asdict(config.settings)

    def _update_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Обновление конфигурации.

        Поддерживает обновление вложенных секций (video, audio, capture, output, api, scheduler).
        Некоторые изменения требуют перезапуска соответствующих компонентов.
        """
        from config import (
            APISettings,
            APISettingsSchema,
            AudioSettings,
            AudioSettingsSchema,
            CaptureSettings,
            CaptureSettingsSchema,
            OutputSettings,
            OutputSettingsSchema,
            SchedulerSettings,
            SchedulerSettingsSchema,
            VideoSettings,
            VideoSettingsSchema,
        )

        config = get_config()
        restart_required: list[str] = []
        updated_sections: list[str] = []
        staged_sections: dict[str, dict[str, Any]] = {}
        simple_updates: dict[str, Any] = {}
        original_sections: dict[str, dict[str, Any]] = {}
        original_simple: dict[str, Any] = {}

        # Обновление вложенных секций
        section_classes = {
            "video": VideoSettings,
            "audio": AudioSettings,
            "capture": CaptureSettings,
            "output": OutputSettings,
            "api": APISettings,
            "scheduler": SchedulerSettings,
        }
        section_schemas: dict[str, Any] = {
            "video": VideoSettingsSchema,
            "audio": AudioSettingsSchema,
            "capture": CaptureSettingsSchema,
            "output": OutputSettingsSchema,
            "api": APISettingsSchema,
            "scheduler": SchedulerSettingsSchema,
        }

        try:
            for section_name, _section_class in section_classes.items():
                if section_name not in data:
                    continue
                section_data = data[section_name]
                if not isinstance(section_data, dict):
                    continue
                current_section = getattr(config.settings, section_name, None)
                if current_section is None:
                    continue

                current_values = vars(current_section).copy()
                original_sections[section_name] = current_values.copy()
                merged_values = current_values.copy()
                for key, value in section_data.items():
                    if key in merged_values:
                        merged_values[key] = value

                validated = section_schemas[section_name].model_validate(
                    merged_values
                )
                staged_sections[section_name] = validated.model_dump()
                updated_sections.append(section_name)

                # Проверка, нужен ли перезапуск
                if (
                    section_name == "api"
                    and self._api_server
                    and any(
                        k in section_data for k in ["host", "port", "enabled"]
                    )
                ):
                    restart_required.append("api")
        except (ConfigValidationError, ValueError, TypeError) as e:
            return {"success": False, "error": str(e)}

        # Обновление простых полей
        simple_fields = ["minimize_to_tray", "show_notifications", "language"]
        for field_name in simple_fields:
            if field_name in data:
                original_simple[field_name] = getattr(
                    config.settings, field_name
                )
                simple_updates[field_name] = data[field_name]
                updated_sections.append(field_name)

        # Apply
        for section_name, values in staged_sections.items():
            target = getattr(config.settings, section_name, None)
            if target is None:
                continue
            for key, value in values.items():
                if hasattr(target, key):
                    setattr(target, key, value)

        for field_name, value in simple_updates.items():
            setattr(config.settings, field_name, value)

        # Сохранение
        if not config.save():
            for section_name, values in original_sections.items():
                target = getattr(config.settings, section_name, None)
                if target is None:
                    continue
                for key, value in values.items():
                    if hasattr(target, key):
                        setattr(target, key, value)
            for field_name, value in original_simple.items():
                setattr(config.settings, field_name, value)
            return {
                "success": False,
                "error": "Не удалось сохранить конфигурацию",
            }

        # Уведомление о требуемом перезапуске
        if restart_required:
            logger.warning(
                f"Для применения изменений требуется перезапуск: {', '.join(restart_required)}"
            )

        return {
            "success": True,
            "updated_sections": updated_sections,
            "restart_required": restart_required,
        }

    # Вспомогательные методы GUI

    def _show_window(self) -> None:
        """Показ главного окна."""
        if self._main_window:
            self._main_window.show()
            self._main_window.activateWindow()

    def _handle_close_requested(self, event) -> None:
        """Обработка запроса закрытия окна через сигнал."""
        config = get_config()

        if config.settings.minimize_to_tray and self._tray_icon:
            event.ignore()
            if self._main_window:
                self._main_window.hide()
            self._tray_icon.show_notification(
                "MIA-ScreenCapture", "Свернуто в трей"
            )
        else:
            # Если minimize_to_tray=False, завершаем приложение
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


def main() -> int:
    """
    Главная точка входа.

    Returns:
        Код выхода
    """
    # Явная bootstrap-загрузка переменных окружения.
    _load_environment()

    # Разбор аргументов командной строки
    config = parse_args()

    # Настройка логирования
    log_level = 20  # INFO
    if config.get("verbose", 0) >= 2:
        log_level = 10  # DEBUG
    elif config.get("quiet", False):
        log_level = 30  # WARNING

    setup_logger(level=log_level)

    # Инициализация конфигурации
    config_path_arg = config.get("config_path")
    config_path = Path(config_path_arg) if config_path_arg else None
    init_config(config_path)

    mode = config.get("mode", "gui")
    if mode not in _SINGLE_INSTANCE_MODES:
        # CLI-команды (--start/--stop/--status/--schedule-*) проксируются
        # в работающий экземпляр через REST API — мьютекс им не нужен.
        app = VideoRecorderApp(config)
        return app.run()

    guard = SingleInstanceGuard()
    if not guard.acquire():
        return _handle_already_running(mode)

    try:
        app = VideoRecorderApp(config)
        return app.run()
    finally:
        guard.release()


if __name__ == "__main__":
    sys.exit(main())
