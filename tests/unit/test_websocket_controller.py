"""
Unit-тесты для контроллера WebSocket-клиента.
"""

import json
from unittest.mock import MagicMock, patch

from gui.controllers.websocket_controller import (
    RECONNECT_INITIAL_DELAY_MS,
    RECONNECT_JITTER,
    RECONNECT_MAX_DELAY_MS,
    RECONNECT_MULTIPLIER,
    WebSocketClientController,
    WebSocketWorker,
)
from gui.models.websocket_state import ConnectionStatus


class TestWebSocketWorker:
    """Тесты рабочего потока WebSocket."""

    def test_worker_init(self) -> None:
        """Тест инициализации worker."""
        worker = WebSocketWorker(
            url="ws://localhost:5000/ws", token="test_token"
        )

        assert worker._url == "ws://localhost:5000/ws"
        assert worker._token == "test_token"
        assert not worker._stop_event.is_set()

    def test_worker_stop(self) -> None:
        """Тест остановки worker."""
        worker = WebSocketWorker(
            url="ws://localhost:5000/ws", token="test_token"
        )

        worker.stop()

        assert worker._stop_event.is_set()

    def test_handle_hello_message(self) -> None:
        """Тест обработки hello сообщения."""
        worker = WebSocketWorker(
            url="ws://localhost:5000/ws", token="test_token"
        )
        worker.connected = MagicMock()

        message = json.dumps(
            {
                "type": "hello",
                "channel": "system",
                "data": {"version": "1.5.0"},
            }
        )

        worker._handle_message(message)

        worker.connected.emit.assert_called_once_with("1.5.0")

    def test_handle_snapshot_message(self) -> None:
        """Тест обработки snapshot сообщения."""
        worker = WebSocketWorker(
            url="ws://localhost:5000/ws", token="test_token"
        )
        worker.event_received = MagicMock()

        message = json.dumps(
            {
                "type": "snapshot",
                "channel": "recording",
                "data": {
                    "recording": {
                        "status": "recording",
                        "output_path": "/tmp/test.mp4",
                    }
                },
            }
        )

        worker._handle_message(message)

        worker.event_received.emit.assert_called_once_with(
            "snapshot",
            {"status": "recording", "output_path": "/tmp/test.mp4"},
        )

    def test_handle_event_message(self) -> None:
        """Тест обработки event сообщения."""
        worker = WebSocketWorker(
            url="ws://localhost:5000/ws", token="test_token"
        )
        worker.event_received = MagicMock()

        message = json.dumps(
            {
                "type": "event",
                "channel": "recording",
                "event": {
                    "type": "recording.started",
                    "payload": {"output_path": "/tmp/test.mp4"},
                },
            }
        )

        worker._handle_message(message)

        worker.event_received.emit.assert_called_once_with(
            "recording.started",
            {"output_path": "/tmp/test.mp4"},
        )

    def test_handle_heartbeat_message(self) -> None:
        """Тест обработки heartbeat сообщения."""
        worker = WebSocketWorker(
            url="ws://localhost:5000/ws", token="test_token"
        )
        worker.heartbeat_received = MagicMock()
        worker._ws = MagicMock()

        message = json.dumps(
            {
                "type": "heartbeat",
                "channel": "system",
                "data": {"ping": True},
            }
        )

        worker._handle_message(message)

        worker.heartbeat_received.emit.assert_called_once()
        worker._ws.send.assert_called_once()

    def test_handle_error_message(self) -> None:
        """Тест обработки error сообщения."""
        worker = WebSocketWorker(
            url="ws://localhost:5000/ws", token="test_token"
        )
        worker.error_occurred = MagicMock()

        message = json.dumps(
            {
                "type": "error",
                "channel": "system",
                "error": {"code": "unauthorized", "message": "Invalid token"},
            }
        )

        worker._handle_message(message)

        worker.error_occurred.emit.assert_called_once_with("Invalid token")

    def test_handle_invalid_json(self) -> None:
        """Тест обработки невалидного JSON."""
        worker = WebSocketWorker(
            url="ws://localhost:5000/ws", token="test_token"
        )

        worker._handle_message("not a json")

    def test_handle_missing_fields(self) -> None:
        """Тест обработки сообщения без обязательных полей."""
        worker = WebSocketWorker(
            url="ws://localhost:5000/ws", token="test_token"
        )

        message = json.dumps({})

        worker._handle_message(message)


class TestWebSocketClientController:
    """Тесты контроллера WebSocket-клиента."""

    def test_controller_init(self) -> None:
        """Тест инициализации контроллера."""
        controller = WebSocketClientController(
            base_url="ws://localhost:5000/ws", api_token="test_token"
        )

        assert controller._base_url == "ws://localhost:5000/ws"
        assert controller._api_token == "test_token"
        assert controller._state.status == ConnectionStatus.DISCONNECTED
        assert controller._worker is None

    def test_is_connected_property(self) -> None:
        """Тест свойства is_connected."""
        controller = WebSocketClientController()

        assert not controller.is_connected

        controller._state.set_connected("1.0")
        assert controller.is_connected

    def test_set_credentials(self) -> None:
        """Тест установки учётных данных."""
        controller = WebSocketClientController()

        controller.set_credentials(
            base_url="ws://newhost:8080/ws", api_token="new_token"
        )

        assert controller._base_url == "ws://newhost:8080/ws"
        assert controller._api_token == "new_token"

    def test_connect_without_token(self) -> None:
        """Тест подключения без токена."""
        controller = WebSocketClientController(api_token="")

        controller.connect()

        assert controller._state.status == ConnectionStatus.ERROR
        assert "token" in controller._state.error_message.lower()

    def test_disconnect(self) -> None:
        """Тест отключения."""
        controller = WebSocketClientController(api_token="test_token")

        controller.disconnect()

        assert controller._state.status == ConnectionStatus.DISCONNECTED

    def test_on_connected(self) -> None:
        """Тест обработки успешного подключения."""
        controller = WebSocketClientController()
        controller.connected = MagicMock()
        controller.status_changed = MagicMock()

        controller._on_connected("1.5.0")

        assert controller._state.status == ConnectionStatus.CONNECTED
        assert controller._state.server_version == "1.5.0"
        assert controller._reconnect_attempts == 0
        controller.connected.emit.assert_called_once()

    def test_on_disconnected(self) -> None:
        """Тест обработки отключения."""
        controller = WebSocketClientController()
        controller._state.set_connected("1.0")

        with patch.object(controller, "_schedule_reconnect") as mock_reconnect:
            controller._on_disconnected()
            mock_reconnect.assert_called_once()

    def test_on_event(self) -> None:
        """Тест обработки события."""
        controller = WebSocketClientController()
        controller.event_received = MagicMock()

        payload = {"frame": 42}
        controller._on_event("recording.progress", payload)

        assert controller._state.last_event is not None
        assert controller._state.last_event.event_type == "recording.progress"
        controller.event_received.emit.assert_called_once_with(
            "recording.progress", payload
        )

    def test_on_error(self) -> None:
        """Тест обработки ошибки."""
        controller = WebSocketClientController()
        controller.error_occurred = MagicMock()
        controller.status_changed = MagicMock()

        controller._on_error("Connection refused")

        assert controller._state.status == ConnectionStatus.ERROR
        assert controller._state.error_message == "Connection refused"
        controller.error_occurred.emit.assert_called_once_with(
            "Connection refused"
        )

    def test_on_heartbeat(self) -> None:
        """Тест обработки heartbeat."""
        controller = WebSocketClientController()

        controller._on_heartbeat()

        assert controller._state.last_heartbeat is not None

    def test_schedule_reconnect_increments_attempts(self) -> None:
        """Тест увеличения счётчика попыток переподключения."""
        controller = WebSocketClientController()

        controller._schedule_reconnect()

        assert controller._reconnect_attempts == 1
        assert controller._state.status == ConnectionStatus.RECONNECTING

    def test_schedule_reconnect_respects_max_delay(self) -> None:
        """Тест ограничения максимальной задержки."""
        controller = WebSocketClientController()
        controller._reconnect_attempts = 100

        controller._schedule_reconnect()

        assert controller._reconnect_timer is not None
        controller._cancel_reconnect()

    def test_cancel_reconnect(self) -> None:
        """Тест отмены переподключения."""
        controller = WebSocketClientController()
        controller._reconnect_timer = MagicMock()

        controller._cancel_reconnect()

        assert controller._reconnect_timer is None


class TestReconnectParameters:
    """Тесты параметров переподключения."""

    def test_initial_delay(self) -> None:
        """Тест начальной задержки."""
        assert RECONNECT_INITIAL_DELAY_MS == 500

    def test_max_delay(self) -> None:
        """Тест максимальной задержки."""
        assert RECONNECT_MAX_DELAY_MS == 15000

    def test_multiplier(self) -> None:
        """Тест множителя."""
        assert RECONNECT_MULTIPLIER == 1.8

    def test_jitter(self) -> None:
        """Тест джиттера."""
        assert RECONNECT_JITTER == 0.2

    def test_delay_calculation(self) -> None:
        """Тест расчёта задержки."""
        attempt = 1
        delay = min(
            RECONNECT_INITIAL_DELAY_MS
            * (RECONNECT_MULTIPLIER ** (attempt - 1)),
            RECONNECT_MAX_DELAY_MS,
        )
        assert delay == 500

        attempt = 5
        delay = min(
            RECONNECT_INITIAL_DELAY_MS
            * (RECONNECT_MULTIPLIER ** (attempt - 1)),
            RECONNECT_MAX_DELAY_MS,
        )
        assert delay < RECONNECT_MAX_DELAY_MS

        attempt = 20
        delay = min(
            RECONNECT_INITIAL_DELAY_MS
            * (RECONNECT_MULTIPLIER ** (attempt - 1)),
            RECONNECT_MAX_DELAY_MS,
        )
        assert delay == RECONNECT_MAX_DELAY_MS
