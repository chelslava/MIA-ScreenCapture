"""
Unit-тесты для WebSocket транспорта.
"""

import json
from unittest.mock import MagicMock
from api.websocket_transport import (
    Channel,
    ErrorCode,
    MessageType,
    WebSocketClient,
    WebSocketTransport,
    create_error_message,
    create_event_message,
    create_hello_message,
    create_heartbeat_message,
    create_snapshot_message,
)


class TestWebSocketMessage:
    """Тесты структуры сообщения."""

    def test_hello_message_structure(self) -> None:
        """Проверка структуры hello сообщения."""
        msg = create_hello_message()
        data = msg.to_dict()

        assert data["type"] == "hello"
        assert data["channel"] == "system"
        assert data["data"]["server"] == "MIA-ScreenCapture"
        assert data["data"]["protocol_version"] == "1.0"
        assert "message_id" in data["meta"]
        assert "server_time" in data["meta"]

    def test_event_message_structure(self) -> None:
        """Проверка структуры event сообщения."""
        event = {
            "type": "started",
            "timestamp": "2026-03-31T12:00:00+00:00",
            "data": {"output_path": "/tmp/video.mp4"},
        }
        msg = create_event_message(event)
        data = msg.to_dict()

        assert data["type"] == "event"
        assert data["channel"] == "recording"
        assert data["event"]["type"] == "started"
        assert data["event"]["data"]["output_path"] == "/tmp/video.mp4"

    def test_error_message_structure(self) -> None:
        """Проверка структуры error сообщения."""
        msg = create_error_message(
            ErrorCode.UNAUTHORIZED,
            "Недействительный токен",
            [{"field": "token", "message": "missing"}],
            retryable=False,
        )
        data = msg.to_dict()

        assert data["type"] == "error"
        assert data["channel"] == "api"
        assert data["error"]["code"] == "unauthorized"
        assert data["error"]["message"] == "Недействительный токен"
        assert data["meta"]["retryable"] is False

    def test_heartbeat_ping_message(self) -> None:
        """Проверка heartbeat ping сообщения."""
        msg = create_heartbeat_message(ping=True)
        data = msg.to_dict()

        assert data["type"] == "heartbeat"
        assert data["data"]["ping"] is True

    def test_heartbeat_pong_message(self) -> None:
        """Проверка heartbeat pong сообщения."""
        msg = create_heartbeat_message(ping=False)
        data = msg.to_dict()

        assert data["type"] == "heartbeat"
        assert data["data"]["pong"] is True

    def test_snapshot_message(self) -> None:
        """Проверка snapshot сообщения."""
        events = [{"type": "started", "data": {}}]
        status = {"is_recording": False}

        msg = create_snapshot_message(events, status)
        data = msg.to_dict()

        assert data["type"] == "snapshot"
        assert data["data"]["recent_events"] == events
        assert data["data"]["status"] == status

    def test_to_json_serialization(self) -> None:
        """Проверка JSON сериализации."""
        msg = create_hello_message()
        json_str = msg.to_json()

        parsed = json.loads(json_str)
        assert parsed["type"] == "hello"


class TestWebSocketClient:
    """Тесты клиента WebSocket."""

    def test_client_initialization(self) -> None:
        """Проверка инициализации клиента."""
        client = WebSocketClient("test-client-1")

        assert client.client_id == "test-client-1"
        assert client.uptime_seconds >= 0
        assert Channel.RECORDING in client.channels

    def test_client_is_alive_initially(self) -> None:
        """Клиент изначально жив."""
        client = WebSocketClient("test-client-1")
        assert client.is_alive() is True

    def test_client_update_pong(self) -> None:
        """Обновление pong времени."""
        client = WebSocketClient("test-client-1")
        client.update_pong()

        assert client.is_alive() is True

    def test_client_uptime(self) -> None:
        """Проверка времени работы."""
        import time

        client = WebSocketClient("test-client-1")
        time.sleep(0.1)

        assert client.uptime_seconds >= 0.1


class TestWebSocketTransport:
    """Тесты транспорта WebSocket."""

    def test_transport_initialization(self) -> None:
        """Проверка инициализации транспорта."""
        mock_manager = MagicMock()
        transport = WebSocketTransport(mock_manager)

        assert transport._ws_manager == mock_manager
        assert transport.get_client_count() == 0

    def test_authenticate_with_valid_token(self) -> None:
        """Аутентификация с валидным токеном."""
        mock_manager = MagicMock()

        def auth_check(token: str) -> bool:
            return token == "valid-token"

        transport = WebSocketTransport(mock_manager, auth_check=auth_check)

        assert transport.authenticate("valid-token") is True
        assert transport.authenticate("invalid-token") is False

    def test_authenticate_without_token(self) -> None:
        """Аутентификация без токена."""
        mock_manager = MagicMock()
        transport = WebSocketTransport(mock_manager)

        assert transport.authenticate(None) is False

    def test_register_client(self) -> None:
        """Регистрация клиента."""
        mock_manager = MagicMock()
        transport = WebSocketTransport(mock_manager)

        client = transport.register_client("client-1")

        assert client.client_id == "client-1"
        assert transport.get_client_count() == 1

    def test_unregister_client(self) -> None:
        """Отключение клиента."""
        mock_manager = MagicMock()
        transport = WebSocketTransport(mock_manager)

        transport.register_client("client-1")
        transport.unregister_client("client-1")

        assert transport.get_client_count() == 0

    def test_get_initial_messages(self) -> None:
        """Получение начальных сообщений."""
        mock_manager = MagicMock()
        mock_manager.get_recent_events.return_value = []
        mock_manager.get_stats.return_value = {"buffered_events": 0}

        transport = WebSocketTransport(mock_manager)
        messages = transport.get_initial_messages()

        assert len(messages) == 2
        hello = json.loads(messages[0])
        assert hello["type"] == "hello"

        snapshot = json.loads(messages[1])
        assert snapshot["type"] == "snapshot"

    def test_start_stop(self) -> None:
        """Запуск и остановка транспорта."""
        mock_manager = MagicMock()
        transport = WebSocketTransport(mock_manager)

        transport.start()
        assert transport._running is True

        transport.stop()
        assert transport._running is False


class TestMessageEnums:
    """Тесты перечислений."""

    def test_message_type_values(self) -> None:
        """Проверка значений MessageType."""
        assert MessageType.HELLO.value == "hello"
        assert MessageType.EVENT.value == "event"
        assert MessageType.ERROR.value == "error"
        assert MessageType.HEARTBEAT.value == "heartbeat"

    def test_channel_values(self) -> None:
        """Проверка значений Channel."""
        assert Channel.SYSTEM.value == "system"
        assert Channel.RECORDING.value == "recording"
        assert Channel.API.value == "api"
        assert Channel.METRICS.value == "metrics"

    def test_error_code_values(self) -> None:
        """Проверка значений ErrorCode."""
        assert ErrorCode.UNAUTHORIZED.value == "unauthorized"
        assert ErrorCode.VALIDATION_ERROR.value == "validation_error"
        assert ErrorCode.INTERNAL_ERROR.value == "internal_error"
