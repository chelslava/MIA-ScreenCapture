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

import os
import sys
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

# Добавление родительской директории в путь для импорта
sys.path.insert(0, str(Path(__file__).parent))

# Загрузка .env файла ДО любых импортов, использующих переменные окружения
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # .env не обязателен, переменные могут быть заданы в окружении
    pass

if TYPE_CHECKING:
    from api.server import APIServer
    from gui.main_window import MainWindow
    from gui.tray_icon import TrayIcon
    from scheduler.task_scheduler import TaskScheduler

from api.auth import API_KEY_ENV_VAR, API_KEY_HEADER
from api.websocket import WebSocketManager
from cli.parser import (
    parse_args,
    print_schedule_list,
    print_status,
    validate_recording_params,
)
from config import get_config, init_config
from core.lifecycle import GracefulShutdown, get_shutdown_manager
from core.recording_service import RecordingService
from gui.backends import GUIRecordingBackend
from logger_config import get_module_logger, setup_logger
from recorder.utils import (
    check_ffmpeg,
    get_audio_devices,
    get_available_windows,
)

logger = get_module_logger(__name__)


class _MainThreadExecutor:
    """Выполнение callables в главном потоке Qt из фоновых потоков."""

    def __init__(self) -> None:
        from PyQt6.QtCore import QObject, Qt, pyqtSignal

        class _ExecutorObject(QObject):
            execute = pyqtSignal(object)

        self._obj = _ExecutorObject()
        self._obj.execute.connect(  # type: ignore[attr-defined]
            self._run_callable,
            Qt.ConnectionType.QueuedConnection,
        )

    @staticmethod
    def _run_callable(fn: Any) -> None:
        fn()

    def run_sync(self, fn: Any, timeout: float = 10.0) -> Any:
        done = threading.Event()
        result: Dict[str, Any] = {}

        def wrapped() -> None:
            try:
                result["value"] = fn()
            except Exception as e:
                result["error"] = e
            finally:
                done.set()

        self._obj.execute.emit(wrapped)  # type: ignore[attr-defined]
        if not done.wait(timeout):
            raise TimeoutError("Таймаут выполнения в GUI потоке")
        if "error" in result:
            raise result["error"]
        return result.get("value")


class VideoRecorderApp:
    """
    Главный класс приложения.

    Управляет всеми компонентами:
    - GUI (опционально)
    - API сервер
    - Планировщик задач
    - Менеджер записи
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Инициализация приложения.

        Args:
            config: Разобранная конфигурация из CLI
        """
        self._config = config
        self._mode = config.get("mode", "gui")

        # Компоненты
        self._app: Optional[Any] = None  # QApplication
        self._main_window: Optional[MainWindow] = None
        self._tray_icon: Optional[TrayIcon] = None
        self._api_server: Optional[APIServer] = None
        self._scheduler: Optional[TaskScheduler] = None

        # Состояние
        self._running = False

        # Graceful shutdown менеджер
        self._shutdown_manager: Optional[GracefulShutdown] = None
        # Headless-friendly сервис записи (используется как fallback без GUI)
        self._recording_service = RecordingService(
            backend=GUIRecordingBackend()
        )
        self._websocket_manager = WebSocketManager()
        self._websocket_manager.attach_event_bus(self._recording_service.event_bus)
        self._gui_executor: Optional[_MainThreadExecutor] = None
        self._gui_thread_id: Optional[int] = None

    def _get_api_headers(self) -> dict:
        """
        Получение заголовков для API запросов с аутентификацией.

        Returns:
            Словарь с заголовками, включая API ключ если он установлен.
        """
        api_key = os.environ.get(API_KEY_ENV_VAR)
        if api_key:
            return {API_KEY_HEADER: api_key}
        return {}

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
            ffmpeg_available, _ = check_ffmpeg()
            if not ffmpeg_available:
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
        except Exception as e:
            logger.error(f"Ошибка приложения: {e}")
            return 1
        finally:
            self._cleanup()

    def _run_gui(self) -> int:
        """Запуск с GUI."""
        from PyQt6.QtWidgets import QApplication

        # Создание Qt приложения
        self._app = QApplication(sys.argv)
        assert self._app is not None
        self._gui_thread_id = threading.get_ident()
        self._gui_executor = _MainThreadExecutor()
        self._app.setApplicationName("MIA-ScreenCapture")
        self._app.setApplicationVersion("1.3.0")

        # Примечание: В PyQt6 High DPI поддержка включена по умолчанию
        # Атрибуты AA_EnableHighDpiScaling и AA_UseHighDpiPixmaps удалены в Qt 6

        # Создание главного окна
        from gui.main_window import MainWindow

        self._main_window = MainWindow()
        assert self._main_window is not None

        # Создание иконки в трее
        from gui.tray_icon import TrayIcon

        self._tray_icon = TrayIcon(self._main_window)
        assert self._tray_icon is not None
        self._tray_icon.show()

        # Подключение сигналов трея
        self._tray_icon.start_requested.connect(
            self._main_window._start_recording
        )
        self._tray_icon.stop_requested.connect(
            self._main_window._stop_recording
        )
        self._tray_icon.pause_requested.connect(
            self._main_window._toggle_pause
        )
        self._tray_icon.show_window_requested.connect(self._show_window)
        self._tray_icon.exit_requested.connect(self._quit_app)

        # Подключение сигналов окна к трею
        self._main_window.recording_started.connect(
            lambda p: self._tray_icon.on_recording_started(p)  # type: ignore[union-attr]
        )
        self._main_window.recording_stopped.connect(
            lambda p: self._tray_icon.on_recording_stopped(p)  # type: ignore[union-attr]
        )
        self._main_window.recording_paused.connect(
            self._tray_icon.on_recording_paused
        )
        self._main_window.recording_resumed.connect(
            self._tray_icon.on_recording_resumed
        )
        self._main_window.error_occurred.connect(self._tray_icon.on_error)

        # Обработка закрытия окна через сигнал
        self._main_window.close_requested.connect(self._handle_close_requested)

        # Запуск API сервера
        self._start_api_server()

        # Запуск планировщика
        self._start_scheduler()

        # Показ окна
        self._main_window.show()

        self._running = True

        # Запуск цикла событий
        return self._app.exec()

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

        return create_schedule(self._config)

    def _run_schedule_update(self) -> int:
        """Обновление запланированной задачи через CLI."""
        from cli.scheduler import update_schedule

        return update_schedule(self._config)

    def _run_schedule_delete(self) -> int:
        """Удаление запланированной задачи через CLI."""
        from cli.scheduler import delete_schedule

        return delete_schedule(self._config)

    def _run_schedule_toggle(self) -> int:
        """Включение/выключение запланированной задачи через CLI."""
        from cli.scheduler import toggle_schedule

        return toggle_schedule(self._config)

    def _run_schedule_preview(self) -> int:
        """Просмотр предстоящих запусков через CLI."""
        from cli.scheduler import preview_upcoming_runs

        return preview_upcoming_runs(self._config)

    def _run_list_presets(self) -> int:
        """Показ списка preset шаблонов."""
        from cli.templates import print_presets_help

        print_presets_help()
        return 0

    def _start_api_server(self) -> None:
        """Запуск API сервера."""
        api_config = self._config.get("api", {})

        if not api_config.get("enabled", True):
            return

        from api.routes import register_routes
        from api.server import APIServer

        self._api_server = APIServer(
            host=api_config.get("host", "127.0.0.1"),
            port=api_config.get("port", 5000),
        )
        assert self._api_server is not None
        self._api_server.set_websocket_manager(self._websocket_manager)

        # Регистрация маршрутов
        register_routes(self._api_server.app, self._api_server)

        # Настройка обратных вызовов
        self._setup_api_callbacks()

        # Запуск сервера
        self._api_server.start()
        logger.info(f"API сервер запущен на {self._api_server.get_url()}")

    def _setup_api_callbacks(self) -> None:
        """Настройка обратных вызовов API."""
        if not self._api_server:
            return

        # Обратный вызов статуса
        self._api_server.set_callback("status", self._get_status)

        # Обратные вызовы записи
        self._api_server.set_callback("start", self._start_recording)
        self._api_server.set_callback("stop", self._stop_recording)
        self._api_server.set_callback("pause", self._toggle_pause)
        self._api_server.set_callback("recordings", self._get_recordings)

        # Обратные вызовы планировщика
        self._api_server.set_callback("get_schedule", self._get_schedule)
        self._api_server.set_callback("create_schedule", self._create_schedule)
        self._api_server.set_callback("delete_schedule", self._delete_schedule)
        self._api_server.set_callback("update_schedule", self._update_schedule)
        self._api_server.set_callback("toggle_schedule", self._toggle_schedule)

        # Обратные вызовы устройств
        self._api_server.set_callback("devices", self._get_devices)
        self._api_server.set_callback("windows", self._get_windows)

        # Обратные вызовы конфигурации
        self._api_server.set_callback("get_config", self._get_config)
        self._api_server.set_callback("update_config", self._update_config)

    def _start_scheduler(self) -> None:
        """Запуск планировщика задач."""
        from scheduler.task_scheduler import TaskScheduler

        # Получение пути сохранения
        config = get_config()
        persist_path = Path(config.config_path).parent / "tasks.json"

        self._scheduler = TaskScheduler(persist_path=persist_path)
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
        else:
            param_dict = params

        logger.info(f"Выполнение запланированной задачи: {param_dict}")

        # Запуск записи
        if self._main_window:
            self._run_on_gui_thread(
                lambda: self._main_window.start_recording_with_params(
                    param_dict
                ),
                timeout=20.0,
            )
        else:
            self._start_recording(param_dict)

    # Реализации обратных вызовов API

    def _run_on_gui_thread(self, fn: Any, timeout: float = 10.0) -> Any:
        """Безопасный синхронный вызов функции в GUI-потоке."""
        if not self._main_window:
            return fn()
        if self._gui_thread_id == threading.get_ident():
            return fn()
        if self._gui_executor is None:
            raise RuntimeError("GUI executor не инициализирован")
        return self._gui_executor.run_sync(fn, timeout=timeout)

    def _get_status(self) -> Dict[str, Any]:
        """Получение статуса записи."""
        if self._main_window:
            return self._run_on_gui_thread(
                lambda: self._main_window.get_status()
            )
        return self._recording_service.get_status()

    def _start_recording(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Запуск записи."""
        if self._main_window:
            return self._run_on_gui_thread(
                lambda: self._main_window.start_recording_with_params(params),
                timeout=20.0,
            )
        return self._recording_service.start_recording(params)

    def _stop_recording(self) -> Dict[str, Any]:
        """Остановка записи."""
        if self._main_window:
            return self._run_on_gui_thread(
                lambda: self._main_window.stop_recording()
            )
        return self._recording_service.stop_recording()

    def _toggle_pause(self) -> Dict[str, Any]:
        """Переключение состояния паузы."""
        if self._main_window:
            return self._run_on_gui_thread(
                lambda: self._main_window.toggle_pause()
            )
        return self._recording_service.toggle_pause()

    def _get_recordings(self) -> list:
        """Получение недавних записей."""
        if self._main_window:
            return self._run_on_gui_thread(
                lambda: self._main_window.get_recordings()
            )
        return self._recording_service.get_recordings()

    def _get_schedule(self) -> list:
        """Получение запланированных задач."""
        if self._scheduler:
            return [task.to_dict() for task in self._scheduler.get_all_tasks()]
        return []

    def _create_schedule(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Создание запланированной задачи."""
        if not self._scheduler:
            return {"success": False, "error": "Планировщик недоступен"}

        try:
            task = self._scheduler.create_task_from_dict(data)
            success = self._scheduler.add_task(task)

            if success and self._main_window:
                self._run_on_gui_thread(
                    lambda: self._main_window.scheduler_tab.set_tasks(  # type: ignore[union-attr]
                        self._scheduler.get_all_tasks()
                    )
                )

            return {
                "success": success,
                "task_id": task.id if success else None,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _delete_schedule(self, task_id: str) -> Dict[str, Any]:
        """Удаление запланированной задачи."""
        if not self._scheduler:
            return {"success": False, "error": "Планировщик недоступен"}

        success = self._scheduler.remove_task(task_id)

        if success and self._main_window:
            self._run_on_gui_thread(
                lambda: self._main_window.scheduler_tab.set_tasks(  # type: ignore[union-attr]
                    self._scheduler.get_all_tasks()
                )
            )

        return {"success": success}

    def _update_schedule(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Обновление запланированной задачи."""
        if not self._scheduler:
            return {"success": False, "error": "Планировщик недоступен"}

        try:
            task = self._scheduler.create_task_from_dict(data)
            task.id = data.get("id", task.id)
            success = self._scheduler.update_task(task)

            if success and self._main_window:
                self._run_on_gui_thread(
                    lambda: self._main_window.scheduler_tab.set_tasks(  # type: ignore[union-attr]
                        self._scheduler.get_all_tasks()
                    )
                )

            return {"success": success}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _toggle_schedule(self, task_id: str, enabled: bool) -> Dict[str, Any]:
        """Переключение запланированной задачи."""
        if not self._scheduler:
            return {"success": False, "error": "Планировщик недоступен"}

        success = self._scheduler.enable_task(task_id, enabled)

        if success and self._main_window:
            self._run_on_gui_thread(
                lambda: self._main_window.scheduler_tab.set_tasks(  # type: ignore[union-attr]
                    self._scheduler.get_all_tasks()
                )
            )

        return {"success": success, "enabled": enabled}

    def _get_devices(self) -> Dict[str, list]:
        """Получение аудиоустройств."""
        return get_audio_devices()

    def _get_windows(self) -> list:
        """Получение доступных окон."""
        return get_available_windows()

    def _get_config(self) -> Dict[str, Any]:
        """Получение текущей конфигурации."""
        config = get_config()
        from dataclasses import asdict

        return asdict(config.settings)

    def _update_config(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Обновление конфигурации."""
        config = get_config()
        # Здесь было бы обновление
        config.save()
        return {"success": True}

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
                    result = self._main_window.stop_recording()
                    if result.get("success"):
                        logger.info(
                            f"Запись сохранена: {result.get('filepath', 'неизвестно')}"
                        )
                    else:
                        logger.error(
                            f"Ошибка при остановке записи: "
                            f"{result.get('error', 'неизвестная ошибка')}"
                        )
            except Exception as e:
                logger.error(f"Ошибка при остановке записи: {e}")
        else:
            try:
                result = self._recording_service.stop_active_recording_if_any()
                if result and result.get("success"):
                    logger.info(
                        f"Запись сохранена: {result.get('filepath', 'неизвестно')}"
                    )
            except Exception as e:
                logger.error(f"Ошибка при остановке headless записи: {e}")

    def _save_config(self) -> None:
        """Сохранение конфигурации при завершении."""
        try:
            config = get_config()
            config.save()
            logger.info("Конфигурация сохранена")
        except Exception as e:
            logger.error(f"Ошибка при сохранении конфигурации: {e}")

    def _cleanup_scheduler(self) -> None:
        """Остановка планировщика."""
        if self._scheduler:
            try:
                logger.info("Остановка планировщика...")
                self._scheduler.stop()
                logger.info("Планировщик остановлен")
            except Exception as e:
                logger.error(f"Ошибка при остановке планировщика: {e}")

    def _cleanup_api_server(self) -> None:
        """Остановка API сервера."""
        if self._api_server:
            try:
                logger.info("Остановка API сервера...")
                self._api_server.stop()
                logger.info("API сервер остановлен")
            except Exception as e:
                logger.error(f"Ошибка при остановке API сервера: {e}")

    def _cleanup_tray(self) -> None:
        """Очистка трея."""
        if self._tray_icon:
            try:
                logger.info("Очистка трея...")
                self._tray_icon.cleanup()
                logger.info("Трей очищен")
            except Exception as e:
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

    # Создание и запуск приложения
    app = VideoRecorderApp(config)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
