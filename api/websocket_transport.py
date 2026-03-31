"""
WebSocket транспорт для real-time событий записи.

Реализует протокол согласно plans/websocket-transport-v1.5.0.md:
- Аутентификация через X-API-Key или token query parameter
- Heartbeat (ping/pong)
- Каналы: system, recording, api, metrics
- Единый envelope формат сообщений
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from logger_config import get_module_logger

logger = get_module_logger(__name__)

WEBSOCKET_PROTOCOL_VERSION = "1.0"
SCHEMA_VERSION = 1
HEARTBEAT_INTERVAL_SECONDS = 15.0
HEARTBEAT_TIMEOUT_SECONDS = 45.0


class MessageType(Enum):
    """Типы сообщений WebSocket протокола."""

    HELLO = "hello"
    SNAPSHOT = "snapshot"
    EVENT = "event"
    STATUS = "status"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    ACK = "ack"


class Channel(Enum):
    """Каналы доставки сообщений."""

    SYSTEM = "system"
    RECORDING = "recording"
    API = "api"
    METRICS = "metrics"


class ErrorCode(Enum):
    """Коды ошибок."""

    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    VALIDATION_ERROR = "validation_error"
    TRANSPORT_UNAVAILABLE = "transport_unavailable"
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"


@dataclass
class WebSocketMessage:
    """Структура сообщения WebSocket."""

    type: MessageType
    channel: Channel
    data: dict[str, Any] = field(default_factory=dict)
    event: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Преобразование в словарь для JSON сериализации."""
        result: dict[str, Any] = {
            "type": self.type.value,
            "channel": self.channel.value,
            "meta": {
                "message_id": str(uuid.uuid4()),
                "server_time": datetime.now(UTC).isoformat(),
                "schema_version": SCHEMA_VERSION,
                **self.meta,
            },
        }
        if self.data:
            result["data"] = self.data
        if self.event:
            result["event"] = self.event
        if self.error:
            result["error"] = self.error
        return result

    def to_json(self) -> str:
        """Сериализация в JSON строку."""
        return json.dumps(self.to_dict(), ensure_ascii=False)


def create_hello_message() -> WebSocketMessage:
    """Создание приветственного сообщения."""
    return WebSocketMessage(
        type=MessageType.HELLO,
        channel=Channel.SYSTEM,
        data={
            "server": "MIA-ScreenCapture",
            "transport": "websocket",
            "protocol_version": WEBSOCKET_PROTOCOL_VERSION,
        },
    )


def create_snapshot_message(
    events: list[dict[str, Any]], status: dict[str, Any]
) -> WebSocketMessage:
    """Создание сообщения snapshot при подключении."""
    return WebSocketMessage(
        type=MessageType.SNAPSHOT,
        channel=Channel.SYSTEM,
        data={
            "recent_events": events,
            "status": status,
        },
    )


def create_event_message(event: dict[str, Any]) -> WebSocketMessage:
    """Создание сообщения о доменном событии."""
    return WebSocketMessage(
        type=MessageType.EVENT,
        channel=Channel.RECORDING,
        event={
            "type": event.get("type", "unknown"),
            "timestamp": event.get("timestamp", datetime.now(UTC).isoformat()),
            "data": event.get("data", {}),
        },
    )


def create_heartbeat_message(ping: bool = True) -> WebSocketMessage:
    """Создание heartbeat сообщения."""
    return WebSocketMessage(
        type=MessageType.HEARTBEAT,
        channel=Channel.SYSTEM,
        data={"ping": ping} if ping else {"pong": True},
    )


def create_error_message(
    code: ErrorCode,
    message: str,
    details: list[dict[str, str]] | None = None,
    retryable: bool = False,
) -> WebSocketMessage:
    """Создание сообщения об ошибке."""
    return WebSocketMessage(
        type=MessageType.ERROR,
        channel=Channel.API,
        error={
            "code": code.value,
            "message": message,
            "details": details or [],
        },
        meta={"retryable": retryable},
    )


class WebSocketClient:
    """Состояние подключённого клиента."""

    def __init__(self, client_id: str) -> None:
        self.client_id = client_id
        self.connected_at = time.time()
        self.last_pong = time.time()
        self.last_ping: float | None = None
        self.channels: set[Channel] = {Channel.RECORDING}
        self._lock = threading.Lock()

    def update_pong(self) -> None:
        """Обновление времени последнего pong."""
        with self._lock:
            self.last_pong = time.time()

    def update_ping(self) -> None:
        """Обновление времени последнего ping."""
        with self._lock:
            self.last_ping = time.time()

    def is_alive(self) -> bool:
        """Проверка живости соединения."""
        with self._lock:
            if self.last_ping is None:
                return True
            return (time.time() - self.last_pong) < HEARTBEAT_TIMEOUT_SECONDS

    @property
    def uptime_seconds(self) -> float:
        """Время работы соединения."""
        return time.time() - self.connected_at


class WebSocketTransport:
    """
    Менеджер WebSocket соединений.

    Управляет подключениями, аутентификацией, heartbeat и рассылкой событий.
    """

    def __init__(
        self,
        websocket_manager: Any,
        auth_check: Callable[[str], bool] | None = None,
    ) -> None:
        self._ws_manager = websocket_manager
        self._auth_check = auth_check
        self._clients: dict[str, WebSocketClient] = {}
        self._lock = threading.Lock()
        self._running = False
        self._heartbeat_thread: threading.Thread | None = None

    def start(self) -> None:
        """Запуск heartbeat мониторинга."""
        self._running = True
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True
        )
        self._heartbeat_thread.start()
        logger.info("WebSocket transport запущен")

    def stop(self) -> None:
        """Остановка транспорта."""
        self._running = False
        with self._lock:
            self._clients.clear()
        logger.info("WebSocket transport остановлен")

    def _heartbeat_loop(self) -> None:
        """Цикл отправки heartbeat и проверки живости."""
        while self._running:
            time.sleep(HEARTBEAT_INTERVAL_SECONDS)
            self._check_clients_alive()

    def _check_clients_alive(self) -> None:
        """Проверка живости всех клиентов."""
        dead_clients: list[str] = []
        with self._lock:
            for client_id, client in self._clients.items():
                if not client.is_alive():
                    dead_clients.append(client_id)
            for client_id in dead_clients:
                del self._clients[client_id]
                logger.debug(f"Клиент {client_id} отключён по таймауту")

    def authenticate(self, token: str | None) -> bool:
        """Проверка токена аутентификации."""
        if not token:
            return False
        if self._auth_check:
            return self._auth_check(token)
        return True

    def register_client(self, client_id: str) -> WebSocketClient:
        """Регистрация нового клиента."""
        client = WebSocketClient(client_id)
        with self._lock:
            self._clients[client_id] = client
        logger.info(f"WebSocket клиент подключён: {client_id}")
        return client

    def unregister_client(self, client_id: str) -> None:
        """Отключение клиента."""
        with self._lock:
            self._clients.pop(client_id, None)
        logger.info(f"WebSocket клиент отключён: {client_id}")

    def get_client_count(self) -> int:
        """Количество подключённых клиентов."""
        with self._lock:
            return len(self._clients)

    def broadcast_event(self, event: dict[str, Any]) -> None:
        """Рассылка события всем подключённым клиентам."""
        logger.debug(f"Broadcast event: {event.get('type', 'unknown')}")

    def get_initial_messages(self) -> list[str]:
        """Получение начальных сообщений для нового клиента."""
        messages: list[str] = []
        messages.append(create_hello_message().to_json())

        events = self._ws_manager.get_recent_events(limit=50)
        status = self._ws_manager.get_stats()
        messages.append(create_snapshot_message(events, status).to_json())

        return messages


def create_websocket_handler(transport: WebSocketTransport) -> Callable:
    """
    Создание WebSocket обработчика для Flask-Sock.

    Args:
        transport: Экземпляр WebSocketTransport

    Returns:
        Функция-обработчик для @sock.route
    """

    def websocket_handler(ws: Any) -> None:
        client_id = str(uuid.uuid4())[:8]

        token = ws.environ.get("HTTP_X_API_KEY")
        if not token:
            args = ws.environ.get("QUERY_STRING", "")
            if "token=" in args:
                for part in args.split("&"):
                    if part.startswith("token="):
                        token = part.split("=", 1)[1]
                        break

        if not transport.authenticate(token):
            error_msg = create_error_message(
                ErrorCode.UNAUTHORIZED,
                "Недействительный API токен",
                [{"field": "token", "message": "Token is missing or invalid"}],
            )
            ws.send(error_msg.to_json())
            ws.close()
            return

        client = transport.register_client(client_id)

        try:
            for msg in transport.get_initial_messages():
                ws.send(msg)

            while True:
                try:
                    data = ws.receive(timeout=HEARTBEAT_INTERVAL_SECONDS)
                    if data is None:
                        break

                    message = json.loads(data)
                    _handle_client_message(ws, transport, client, message)

                except TimeoutError:
                    ws.send(create_heartbeat_message(ping=True).to_json())
                    client.update_ping()

                except json.JSONDecodeError as e:
                    error_msg = create_error_message(
                        ErrorCode.VALIDATION_ERROR,
                        "Некорректный JSON",
                        [{"field": "body", "message": str(e)}],
                    )
                    ws.send(error_msg.to_json())

        except Exception as e:
            logger.error(f"WebSocket error for client {client_id}: {e}")

        finally:
            transport.unregister_client(client_id)

    return websocket_handler


def _handle_client_message(
    ws: Any,
    transport: WebSocketTransport,
    client: WebSocketClient,
    message: dict[str, Any],
) -> None:
    """Обработка сообщения от клиента."""
    msg_type = message.get("type", "")

    if msg_type == "heartbeat" or msg_type == "pong":
        client.update_pong()
        return

    if msg_type == "ping":
        ws.send(create_heartbeat_message(ping=False).to_json())
        return

    logger.debug(f"Received message from {client.client_id}: {msg_type}")
