"""
Модель состояния WebSocket-клиента в GUI.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import RLock
from typing import Any


class ConnectionStatus(Enum):
    """Статус WebSocket-соединения."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class ReceivedEvent:
    """Полученное через WebSocket событие."""

    event_type: str
    timestamp: datetime
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class WebSocketState:
    """
    Состояние WebSocket-клиента.

    Потокобезопасно — все операции защищены RLock.
    """

    status: ConnectionStatus = ConnectionStatus.DISCONNECTED
    last_event: ReceivedEvent | None = None
    error_message: str = ""
    reconnect_attempts: int = 0
    server_version: str = ""
    connected_at: datetime | None = None
    last_heartbeat: datetime | None = None

    _lock: RLock = field(default_factory=RLock, repr=False, compare=False)

    def set_connecting(self) -> None:
        """Перевести в состояние подключения."""
        with self._lock:
            self.status = ConnectionStatus.CONNECTING
            self.error_message = ""

    def set_connected(self, server_version: str = "") -> None:
        """Перевести в состояние подключено."""
        with self._lock:
            self.status = ConnectionStatus.CONNECTED
            self.server_version = server_version
            self.connected_at = datetime.now()
            self.last_heartbeat = datetime.now()
            self.reconnect_attempts = 0
            self.error_message = ""

    def set_disconnected(self) -> None:
        """Перевести в состояние отключено."""
        with self._lock:
            self.status = ConnectionStatus.DISCONNECTED
            self.connected_at = None
            self.last_heartbeat = None
            self.error_message = ""

    def set_reconnecting(self, attempt: int) -> None:
        """Перевести в состояние переподключения."""
        with self._lock:
            self.status = ConnectionStatus.RECONNECTING
            self.reconnect_attempts = attempt

    def set_error(self, message: str) -> None:
        """Установить состояние ошибки."""
        with self._lock:
            self.status = ConnectionStatus.ERROR
            self.error_message = message

    def update_heartbeat(self) -> None:
        """Обновить время последнего heartbeat."""
        with self._lock:
            self.last_heartbeat = datetime.now()

    def set_last_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Установить последнее полученное событие."""
        with self._lock:
            self.last_event = ReceivedEvent(
                event_type=event_type,
                timestamp=datetime.now(),
                payload=payload,
            )

    def get_status_info(self) -> dict[str, Any]:
        """Получить информацию о текущем статусе."""
        with self._lock:
            return {
                "status": self.status.value,
                "error_message": self.error_message,
                "reconnect_attempts": self.reconnect_attempts,
                "server_version": self.server_version,
                "connected_at": (
                    self.connected_at.isoformat()
                    if self.connected_at
                    else None
                ),
                "last_heartbeat": (
                    self.last_heartbeat.isoformat()
                    if self.last_heartbeat
                    else None
                ),
            }
