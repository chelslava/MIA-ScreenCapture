"""
Контроллер WebSocket-клиента для GUI.

Управляет подключением к серверу WebSocket, переподключением
и доставкой событий в UI через Qt-сигналы.
"""

from __future__ import annotations

import json
import random
import threading
import time
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QObject, QThread, pyqtSignal

from gui.models.websocket_state import ConnectionStatus, WebSocketState
from logger_config import get_module_logger

if TYPE_CHECKING:
    pass

logger = get_module_logger(__name__)

RECONNECT_INITIAL_DELAY_MS = 500
RECONNECT_MAX_DELAY_MS = 15000
RECONNECT_MULTIPLIER = 1.8
RECONNECT_JITTER = 0.2


class WebSocketWorker(QThread):
    """Рабочий поток для WebSocket-соединения."""

    connected = pyqtSignal(str)
    disconnected = pyqtSignal()
    event_received = pyqtSignal(str, dict)
    error_occurred = pyqtSignal(str)
    heartbeat_received = pyqtSignal()

    def __init__(
        self,
        url: str,
        token: str,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._url = url
        self._token = token
        self._stop_event = threading.Event()
        self._ws: Any = None

    def run(self) -> None:
        """Основной цикл WebSocket-клиента."""
        try:
            import websockets.sync.client as ws_client
        except ImportError:
            self.error_occurred.emit("Библиотека websockets не установлена")
            return

        headers = {"X-API-Key": self._token}
        ws_url = f"{self._url}?token={self._token}"

        while not self._stop_event.is_set():
            try:
                self._ws = ws_client.connect(
                    ws_url,
                    additional_headers=headers,
                    close_timeout=5.0,
                )

                self.connected.emit("1.0")

                try:
                    for message in self._ws:
                        if self._stop_event.is_set():
                            break

                        self._handle_message(message)

                except Exception as e:
                    if not self._stop_event.is_set():
                        logger.warning("WebSocket соединение разорвано: %s", e)
                finally:
                    if self._ws:
                        try:
                            self._ws.close()
                        except Exception:
                            pass
                        self._ws = None
                    self.disconnected.emit()

            except Exception as e:
                if not self._stop_event.is_set():
                    logger.error("Ошибка подключения WebSocket: %s", e)
                    self.error_occurred.emit(str(e))

            if not self._stop_event.is_set():
                time.sleep(1)

    def _handle_message(self, raw_message: str) -> None:
        """Обработка входящего сообщения."""
        try:
            message = json.loads(raw_message)
            msg_type = message.get("type", "")
            data = message.get("data", {})
            event = message.get("event", {})

            if msg_type == "hello":
                version = data.get("version", "unknown")
                self.connected.emit(version)

            elif msg_type == "snapshot":
                if "recording" in data:
                    self.event_received.emit("snapshot", data["recording"])

            elif msg_type == "event":
                event_type = event.get("type", "unknown")
                payload = event.get("payload", {})
                self.event_received.emit(event_type, payload)

            elif msg_type == "heartbeat":
                self.heartbeat_received.emit()
                try:
                    if self._ws:
                        self._ws.send(
                            json.dumps(
                                {
                                    "type": "heartbeat",
                                    "channel": "system",
                                    "data": {"pong": True},
                                }
                            )
                        )
                except Exception as e:
                    logger.warning("Ошибка отправки heartbeat: %s", e)

            elif msg_type == "error":
                error_data = message.get("error", {})
                error_msg = error_data.get("message", "Unknown error")
                self.error_occurred.emit(error_msg)

        except json.JSONDecodeError as e:
            logger.warning("Некорректный JSON в сообщении: %s", e)
        except Exception as e:
            logger.error("Ошибка обработки сообщения WebSocket: %s", e)

    def stop(self) -> None:
        """Остановка рабочего потока."""
        self._stop_event.set()
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass


class WebSocketClientController(QObject):
    """
    Контроллер WebSocket-клиента.

    Управляет подключением, переподключением с экспоненциальным backoff
    и доставкой событий через сигналы Qt.
    """

    connected = pyqtSignal()
    disconnected = pyqtSignal()
    event_received = pyqtSignal(str, dict)
    error_occurred = pyqtSignal(str)
    status_changed = pyqtSignal(str)

    def __init__(
        self,
        base_url: str = "ws://localhost:5000/ws",
        api_token: str = "",
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._base_url = base_url
        self._api_token = api_token
        self._state = WebSocketState()
        self._worker: WebSocketWorker | None = None
        self._reconnect_timer: threading.Timer | None = None
        self._reconnect_attempts = 0

    @property
    def state(self) -> WebSocketState:
        """Получить модель состояния."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Проверка активности соединения."""
        return self._state.status == ConnectionStatus.CONNECTED

    def set_credentials(self, base_url: str, api_token: str) -> None:
        """Установка учётных данных для подключения."""
        self._base_url = base_url
        self._api_token = api_token

    def connect(self) -> None:
        """Подключение к WebSocket-серверу."""
        if self._worker and self._worker.isRunning():
            logger.warning("WebSocket уже подключён или подключается")
            return

        if not self._api_token:
            self._state.set_error("API token не указан")
            self.error_occurred.emit("API token не указан")
            return

        self._state.set_connecting()
        self.status_changed.emit(ConnectionStatus.CONNECTING.value)

        self._worker = WebSocketWorker(
            self._base_url, self._api_token, parent=self
        )
        self._worker.connected.connect(self._on_connected)
        self._worker.disconnected.connect(self._on_disconnected)
        self._worker.event_received.connect(self._on_event)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.heartbeat_received.connect(self._on_heartbeat)
        self._worker.start()

    def disconnect(self) -> None:
        """Отключение от WebSocket-сервера."""
        self._cancel_reconnect()

        if self._worker:
            self._worker.stop()
            if not self._worker.wait(3000):
                self._worker.terminate()
            self._worker = None

        self._state.set_disconnected()
        self.status_changed.emit(ConnectionStatus.DISCONNECTED.value)
        self.disconnected.emit()

    def _on_connected(self, version: str) -> None:
        """Обработка успешного подключения."""
        self._reconnect_attempts = 0
        self._state.set_connected(version)
        self.status_changed.emit(ConnectionStatus.CONNECTED.value)
        self.connected.emit()
        logger.info("WebSocket подключён, версия сервера: %s", version)

    def _on_disconnected(self) -> None:
        """Обработка отключения."""
        if self._state.status == ConnectionStatus.CONNECTED:
            logger.info("WebSocket отключён, попытка переподключения")
            self._schedule_reconnect()

    def _on_event(self, event_type: str, payload: dict) -> None:
        """Обработка полученного события."""
        self._state.set_last_event(event_type, payload)
        self.event_received.emit(event_type, payload)

    def _on_error(self, message: str) -> None:
        """Обработка ошибки."""
        self._state.set_error(message)
        self.status_changed.emit(ConnectionStatus.ERROR.value)
        self.error_occurred.emit(message)
        logger.error("WebSocket ошибка: %s", message)

    def _on_heartbeat(self) -> None:
        """Обработка heartbeat."""
        self._state.update_heartbeat()

    def _schedule_reconnect(self) -> None:
        """Планирование переподключения с экспоненциальным backoff."""
        self._cancel_reconnect()

        self._reconnect_attempts += 1
        self._state.set_reconnecting(self._reconnect_attempts)
        self.status_changed.emit(ConnectionStatus.RECONNECTING.value)

        delay_ms = min(
            RECONNECT_INITIAL_DELAY_MS
            * (RECONNECT_MULTIPLIER ** (self._reconnect_attempts - 1)),
            RECONNECT_MAX_DELAY_MS,
        )
        jitter = delay_ms * RECONNECT_JITTER * random.random()
        delay_ms = delay_ms + jitter
        delay_sec = delay_ms / 1000.0

        logger.info(
            "Переподключение через %.2f сек (попытка %d)",
            delay_sec,
            self._reconnect_attempts,
        )

        self._reconnect_timer = threading.Timer(delay_sec, self._do_reconnect)
        self._reconnect_timer.daemon = True
        self._reconnect_timer.start()

    def _do_reconnect(self) -> None:
        """Выполнение переподключения."""
        if self._worker:
            self._worker.stop()
            if not self._worker.wait(1000):
                self._worker.terminate()
            self._worker = None

        self.connect()

    def _cancel_reconnect(self) -> None:
        """Отмена запланированного переподключения."""
        if self._reconnect_timer:
            self._reconnect_timer.cancel()
            self._reconnect_timer = None
