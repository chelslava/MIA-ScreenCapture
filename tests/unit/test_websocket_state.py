"""
Unit-тесты для модели состояния WebSocket-клиента.
"""

from datetime import datetime

import pytest

from gui.models.websocket_state import (
    ConnectionStatus,
    ReceivedEvent,
    WebSocketState,
)


class TestConnectionStatus:
    """Тесты перечисления ConnectionStatus."""

    def test_status_values(self) -> None:
        """Тест значений статуса."""
        assert ConnectionStatus.DISCONNECTED.value == "disconnected"
        assert ConnectionStatus.CONNECTING.value == "connecting"
        assert ConnectionStatus.CONNECTED.value == "connected"
        assert ConnectionStatus.RECONNECTING.value == "reconnecting"
        assert ConnectionStatus.ERROR.value == "error"


class TestReceivedEvent:
    """Тесты класса ReceivedEvent."""

    def test_create_event(self) -> None:
        """Тест создания события."""
        timestamp = datetime.now()
        event = ReceivedEvent(
            event_type="recording.started",
            timestamp=timestamp,
            payload={"output_path": "/tmp/test.mp4"},
        )

        assert event.event_type == "recording.started"
        assert event.timestamp == timestamp
        assert event.payload["output_path"] == "/tmp/test.mp4"

    def test_default_payload(self) -> None:
        """Тест значения payload по умолчанию."""
        event = ReceivedEvent(event_type="test", timestamp=datetime.now())
        assert event.payload == {}


class TestWebSocketState:
    """Тесты класса WebSocketState."""

    def test_default_values(self) -> None:
        """Тест значений по умолчанию."""
        state = WebSocketState()

        assert state.status == ConnectionStatus.DISCONNECTED
        assert state.last_event is None
        assert state.error_message == ""
        assert state.reconnect_attempts == 0
        assert state.server_version == ""
        assert state.connected_at is None
        assert state.last_heartbeat is None

    def test_set_connecting(self) -> None:
        """Тест установки состояния подключения."""
        state = WebSocketState()
        state.set_error("previous error")

        state.set_connecting()

        assert state.status == ConnectionStatus.CONNECTING
        assert state.error_message == ""

    def test_set_connected(self) -> None:
        """Тест установки состояния подключено."""
        state = WebSocketState()
        state.reconnect_attempts = 5

        state.set_connected("1.5.0")

        assert state.status == ConnectionStatus.CONNECTED
        assert state.server_version == "1.5.0"
        assert state.connected_at is not None
        assert state.last_heartbeat is not None
        assert state.reconnect_attempts == 0
        assert state.error_message == ""

    def test_set_connected_default_version(self) -> None:
        """Тест установки состояния без версии."""
        state = WebSocketState()

        state.set_connected()

        assert state.status == ConnectionStatus.CONNECTED
        assert state.server_version == ""

    def test_set_disconnected(self) -> None:
        """Тест установки состояния отключено."""
        state = WebSocketState()
        state.set_connected("1.0")
        state.error_message = "some error"

        state.set_disconnected()

        assert state.status == ConnectionStatus.DISCONNECTED
        assert state.connected_at is None
        assert state.last_heartbeat is None
        assert state.error_message == ""

    def test_set_reconnecting(self) -> None:
        """Тест установки состояния переподключения."""
        state = WebSocketState()

        state.set_reconnecting(3)

        assert state.status == ConnectionStatus.RECONNECTING
        assert state.reconnect_attempts == 3

    def test_set_error(self) -> None:
        """Тест установки состояния ошибки."""
        state = WebSocketState()

        state.set_error("Connection refused")

        assert state.status == ConnectionStatus.ERROR
        assert state.error_message == "Connection refused"

    def test_update_heartbeat(self) -> None:
        """Тест обновления heartbeat."""
        state = WebSocketState()

        state.update_heartbeat()

        assert state.last_heartbeat is not None
        elapsed = (datetime.now() - state.last_heartbeat).total_seconds()
        assert elapsed < 1.0

    def test_set_last_event(self) -> None:
        """Тест установки последнего события."""
        state = WebSocketState()
        payload = {"frame": 42, "fps": 30}

        state.set_last_event("recording.progress", payload)

        assert state.last_event is not None
        assert state.last_event.event_type == "recording.progress"
        assert state.last_event.payload == payload
        assert state.last_event.timestamp is not None

    def test_get_status_info(self) -> None:
        """Тест получения информации о статусе."""
        state = WebSocketState()
        state.set_connected("2.0")
        state.set_last_event("test", {"key": "value"})

        info = state.get_status_info()

        assert info["status"] == "connected"
        assert info["server_version"] == "2.0"
        assert info["error_message"] == ""
        assert info["reconnect_attempts"] == 0
        assert info["connected_at"] is not None
        assert info["last_heartbeat"] is not None

    def test_thread_safety(self) -> None:
        """Тест потокобезопасности."""
        import threading

        state = WebSocketState()

        def set_connecting() -> None:
            for _ in range(100):
                state.set_connecting()

        def set_connected() -> None:
            for _ in range(100):
                state.set_connected("1.0")

        def set_error() -> None:
            for _ in range(100):
                state.set_error("error")

        threads = [
            threading.Thread(target=set_connecting),
            threading.Thread(target=set_connected),
            threading.Thread(target=set_error),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert state.status in (
            ConnectionStatus.CONNECTING,
            ConnectionStatus.CONNECTED,
            ConnectionStatus.ERROR,
        )
