"""
API-вкладка и WebSocket-маршрутизация главного окна (#164)
==========================================================

Миксин ``ApiSectionControllerMixin`` вынесен из ``gui/main_window.py``:
обращения к ``ApplicationFacade`` из вкладки API, запуск/остановка
сервера и пересылка WebSocket-событий в сигналы окна.
``MainWindow`` наследует миксин — методы доступны как раньше.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from gui.controllers.websocket_controller import WebSocketClientController
from gui.styles.theme import Theme
from logger_config import get_module_logger

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QLabel, QMainWindow, QStatusBar

    from core.application_facade import ApplicationFacade
    from gui.views.api_settings_view import ApiSettingsView

logger = get_module_logger(__name__)


if TYPE_CHECKING:
    _QWindowBase = QMainWindow
else:
    # В рантайме миксин — обычный класс (без metaclass-конфликтов
    # с PyQt); QMainWindow приходит от MainWindow напрямую.
    _QWindowBase = object


class ApiSectionControllerMixin(_QWindowBase):
    """Управление API-сервером и WebSocket-клиентом из вкладки API."""

    if TYPE_CHECKING:
        # Общие атрибуты окна
        _application_facade: ApplicationFacade | None
        _api_settings_view: ApiSettingsView
        _ws_controller: WebSocketClientController | None
        _ws_status_label: QLabel
        status_bar: QStatusBar

        # Сигналы MainWindow (после создания класса — bound signal)
        recording_started: Any
        recording_stopped: Any
        recording_paused: Any
        recording_resumed: Any
        error_occurred: Any

        # Методы MainWindow
        _show_non_modal_error: Callable[[str], None]

    def _get_api_control_handler(
        self,
        control_name: str,
    ) -> Callable[..., Any] | None:
        """Возвращает API-обработчик из публичного фасада приложения."""
        application_facade = self._application_facade
        if application_facade is None:
            return None

        handler_map: dict[str, Callable[..., Any]] = {
            "get_status": application_facade.get_api_status,
            "apply_settings": application_facade.apply_api_settings,
            "start": lambda: application_facade.start_api_server(force=True),
            "stop": application_facade.stop_api_server,
            "restart": application_facade.restart_api_server,
            "open_logs": application_facade.open_api_logs_folder,
        }
        return handler_map.get(control_name)

    def _invoke_api_control(
        self,
        control_name: str,
        *args: Any,
    ) -> dict[str, Any] | None:
        """Вызов обработчика API из главного приложения."""
        handler = self._get_api_control_handler(control_name)
        if handler is None:
            return None

        try:
            result = handler(*args)
        except Exception as e:
            logger.error(f"Ошибка вызова API control '{control_name}': {e}")
            self._show_non_modal_error(str(e))
            return None

        if isinstance(result, dict):
            return result
        return {"success": True, "data": result}

    def _refresh_api_status(self) -> None:
        """Обновление статуса API на вкладке."""
        if not hasattr(self, "_api_settings_view"):
            return

        status = self._invoke_api_control("get_status")
        if status is None:
            api_running = False
            if self._application_facade is not None:
                try:
                    api_running = bool(
                        self._application_facade.get_api_status().get(
                            "running", False
                        )
                    )
                except Exception:
                    api_running = False
            message = "Сервер запущен" if api_running else "Сервер остановлен"
            self._api_settings_view.set_status(api_running, message)
            return

        configured = status.get("configured", {})
        port = configured.get("port", status.get("port", 5000))
        token = configured.get("api_key", "")
        if not self._api_settings_view.is_editing_settings():
            self._api_settings_view.set_settings(
                port=int(port),
                token=token or "",
            )

        running = bool(status.get("running", False))
        if running:
            message = f"Запущен: {status.get('url', 'http://127.0.0.1')}"
        else:
            message = "Сервер остановлен"
        self._api_settings_view.set_status(running, message)

    def refresh_api_status_view(self) -> None:
        """Публичное обновление API статуса для runtime-слоя."""
        self._refresh_api_status()

    def _on_api_settings_apply(self, port: int, token: str) -> None:
        """Сохранение настроек API из вкладки."""
        result = self._invoke_api_control(
            "apply_settings", {"port": port, "token": token}
        )
        if result is None:
            self._show_non_modal_error("Управление API недоступно")
            return
        if result.get("success"):
            message = "Настройки API сохранены"
            if result.get("restart_required"):
                message += ". Нужен перезапуск API сервера"
            self.status_bar.showMessage(message, 5000)
            self._refresh_api_status()
            return
        self._show_non_modal_error(
            result.get("error", "Не удалось сохранить настройки API")
        )

    def _on_api_start(self) -> None:
        """Запуск API сервера из вкладки."""
        result = self._invoke_api_control("start")
        if result is None:
            self._show_non_modal_error("Управление API недоступно")
            return
        if result.get("success"):
            self.status_bar.showMessage("API сервер запущен", 5000)
            self._refresh_api_status()
            self._start_websocket_after_api(result)
            return
        self._show_non_modal_error(
            result.get("error", "Не удалось запустить API сервер")
        )

    def _start_websocket_after_api(self, api_result: dict) -> None:
        """Запуск WebSocket клиента после старта API."""
        configured = api_result.get("configured", {})
        url = api_result.get("url", "")
        token = configured.get("api_key", "")

        if url and token:
            if not self._ws_controller:
                self.init_websocket_client(url, token)
            self.connect_websocket()

    def _on_api_stop(self) -> None:
        """Остановка API сервера из вкладки."""
        result = self._invoke_api_control("stop")
        if result is None:
            self._show_non_modal_error("Управление API недоступно")
            return
        if result.get("success"):
            self.disconnect_websocket()
            self.status_bar.showMessage("API сервер остановлен", 5000)
            self._refresh_api_status()
            return
        self._show_non_modal_error(
            result.get("error", "Не удалось остановить API сервер")
        )

    def _on_api_restart(self) -> None:
        """Перезапуск API сервера из вкладки."""
        result = self._invoke_api_control("restart")
        if result is None:
            self._show_non_modal_error("Управление API недоступно")
            return
        if result.get("success"):
            self.disconnect_websocket()
            self.status_bar.showMessage("API сервер перезапущен", 5000)
            self._refresh_api_status()
            self._start_websocket_after_api(result)
            return
        self._show_non_modal_error(
            result.get("error", "Не удалось перезапустить API сервер")
        )

    # === WebSocket клиент ===

    def init_websocket_client(self, base_url: str, api_token: str) -> None:
        """
        Инициализация WebSocket-клиента.

        Args:
            base_url: Базовый URL API (http://host:port)
            api_token: API токен для аутентификации
        """
        ws_url = base_url.replace("http://", "ws://").replace(
            "https://", "wss://"
        )
        ws_url = f"{ws_url}/ws"

        self._ws_controller = WebSocketClientController(
            base_url=ws_url, api_token=api_token, parent=self
        )
        self._ws_controller.status_changed.connect(self._on_ws_status_changed)
        self._ws_controller.event_received.connect(self._on_ws_event_received)
        self._ws_controller.error_occurred.connect(self._on_ws_error)
        logger.info("WebSocket клиент инициализирован: %s", ws_url)

    def connect_websocket(self) -> None:
        """Подключение WebSocket-клиента к серверу."""
        if self._ws_controller:
            self._ws_controller.connect()

    def disconnect_websocket(self) -> None:
        """Отключение WebSocket-клиента."""
        if self._ws_controller:
            self._ws_controller.disconnect()

    def _on_ws_status_changed(self, status: str) -> None:
        """Обработка изменения статуса WebSocket."""
        status_map = {
            "connected": (
                "● Connected",
                Theme.color("success"),
                "Подключено",
            ),
            "connecting": (
                "● Connecting...",
                Theme.color("warning"),
                "Подключение...",
            ),
            "disconnected": (
                "● Disconnected",
                Theme.color("danger"),
                "Отключено",
            ),
            "reconnecting": (
                "◌ Reconnecting...",
                Theme.color("warning"),
                "Переподключение...",
            ),
            "error": ("● Error", Theme.color("danger"), "Ошибка"),
        }
        text, color, tooltip = status_map.get(
            status, ("● Unknown", Theme.color("muted"), "Неизвестно")
        )
        self._ws_status_label.setText(text)
        self._ws_status_label.setStyleSheet(
            f"color: {color}; font-weight: bold;"
        )
        self._ws_status_label.setToolTip(tooltip)

    def _on_ws_event_received(self, event_type: str, payload: dict) -> None:
        """Обработка полученного через WebSocket события."""
        logger.debug("WebSocket событие: %s, payload: %s", event_type, payload)

        if event_type == "recording.started":
            self.recording_started.emit(payload.get("output_path", ""))
        elif event_type == "recording.stopped":
            self.recording_stopped.emit(payload.get("output_path", ""))
        elif event_type == "recording.paused":
            self.recording_paused.emit()
        elif event_type == "recording.resumed":
            self.recording_resumed.emit()
        elif event_type == "recording.error":
            error_msg = payload.get("error", "Неизвестная ошибка")
            self.error_occurred.emit(error_msg)

    def _on_ws_error(self, message: str) -> None:
        """Обработка ошибки WebSocket."""
        logger.warning("WebSocket ошибка: %s", message)
