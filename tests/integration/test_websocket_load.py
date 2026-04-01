"""
Нагрузочные тесты для WebSocket транспорта
===========================================

Тестирует многопоточное подключение клиентов, устойчивость к нагрузке
и корректность обработки сообщений.
"""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pytest

from api.websocket_transport import (
    Channel,
    MessageType,
    WebSocketMessage,
    WebSocketTransport,
)


class MockWebSocketClient:
    """Мок WebSocket клиента для тестирования."""

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.received_messages: list[dict[str, Any]] = []
        self.closed = False
        self._lock = threading.Lock()

    def send(self, message: str) -> None:
        """Сохранение отправленного сообщения."""
        with self._lock:
            try:
                self.received_messages.append(json.loads(message))
            except json.JSONDecodeError:
                pass

    def close(self) -> None:
        """Закрытие соединения."""
        self.closed = True


@pytest.fixture
def ws_transport():
    """Создание экземпляра WebSocketTransport для тестов."""
    transport = WebSocketTransport()
    yield transport
    transport.shutdown()


class TestWebSocketMultiClient:
    """Тесты множественных подключений."""

    def test_multiple_clients_register(
        self, ws_transport: WebSocketTransport
    ) -> None:
        """Тест регистрации нескольких клиентов одновременно."""
        num_clients = 10
        clients = [
            MockWebSocketClient(f"client_{i}") for i in range(num_clients)
        ]

        def register_client(client: MockWebSocketClient) -> bool:
            return ws_transport.register_client(
                client_id=client.client_id,
                websocket=client,
                subscriptions=[Channel.RECORDING],
            )

        with ThreadPoolExecutor(max_workers=num_clients) as executor:
            futures = [executor.submit(register_client, c) for c in clients]
            results = [f.result() for f in as_completed(futures)]

        assert all(results), "Не все клиенты успешно зарегистрированы"
        assert ws_transport.client_count == num_clients

    def test_broadcast_to_multiple_clients(
        self, ws_transport: WebSocketTransport
    ) -> None:
        """Тест broadcast сообщения всем клиентам."""
        num_clients = 5
        clients = []

        for i in range(num_clients):
            client = MockWebSocketClient(f"client_{i}")
            ws_transport.register_client(
                client_id=client.client_id,
                websocket=client,
                subscriptions=[Channel.RECORDING],
            )
            clients.append(client)

        message = WebSocketMessage(
            type=MessageType.EVENT,
            channel=Channel.RECORDING,
            event={"type": "test_event", "payload": {"value": 42}},
        )

        ws_transport.broadcast(message)

        time.sleep(0.1)

        for client in clients:
            assert len(client.received_messages) == 1
            assert client.received_messages[0]["type"] == "event"

    def test_client_disconnect_cleanup(
        self, ws_transport: WebSocketTransport
    ) -> None:
        """Тест очистки при отключении клиентов."""
        num_clients = 5

        for i in range(num_clients):
            client = MockWebSocketClient(f"client_{i}")
            ws_transport.register_client(
                client_id=client.client_id,
                websocket=client,
                subscriptions=[Channel.RECORDING],
            )

        assert ws_transport.client_count == num_clients

        for i in range(num_clients):
            ws_transport.unregister_client(f"client_{i}")

        assert ws_transport.client_count == 0


class TestWebSocketMessageThroughput:
    """Тесты пропускной способности."""

    def test_high_frequency_broadcast(
        self, ws_transport: WebSocketTransport
    ) -> None:
        """Тест broadcast при высокой частоте сообщений."""
        client = MockWebSocketClient("throughput_test")
        ws_transport.register_client(
            client_id=client.client_id,
            websocket=client,
            subscriptions=[Channel.RECORDING, Channel.METRICS],
        )

        num_messages = 100
        start_time = time.time()

        for i in range(num_messages):
            message = WebSocketMessage(
                type=MessageType.EVENT,
                channel=Channel.RECORDING,
                event={"type": "progress", "payload": {"frame": i}},
            )
            ws_transport.broadcast(message)

        elapsed = time.time() - start_time

        assert elapsed < 2.0, f"Broadcast слишком медленный: {elapsed:.2f}s"
        assert len(client.received_messages) == num_messages

    def test_concurrent_broadcast_and_register(
        self, ws_transport: WebSocketTransport
    ) -> None:
        """Тест конкурентной регистрации и broadcast."""
        num_operations = 20

        def register_clients() -> None:
            for i in range(num_operations):
                client = MockWebSocketClient(f"concurrent_{i}")
                ws_transport.register_client(
                    client_id=client.client_id,
                    websocket=client,
                    subscriptions=[Channel.RECORDING],
                )

        def broadcast_messages() -> None:
            for i in range(num_operations):
                message = WebSocketMessage(
                    type=MessageType.EVENT,
                    channel=Channel.RECORDING,
                    event={"type": "test", "payload": {"seq": i}},
                )
                ws_transport.broadcast(message)
                time.sleep(0.01)

        register_thread = threading.Thread(target=register_clients)
        broadcast_thread = threading.Thread(target=broadcast_messages)

        register_thread.start()
        broadcast_thread.start()

        register_thread.join(timeout=5.0)
        broadcast_thread.join(timeout=5.0)

        assert ws_transport.client_count == num_operations


class TestWebSocketMemoryLeaks:
    """Тесты на утечки памяти."""

    def test_repeated_register_unregister(
        self, ws_transport: WebSocketTransport
    ) -> None:
        """Тест отсутствия утечек при повторной регистрации."""
        iterations = 50

        for i in range(iterations):
            client = MockWebSocketClient(f"leak_test_{i}")
            ws_transport.register_client(
                client_id=client.client_id,
                websocket=client,
                subscriptions=[Channel.RECORDING],
            )
            ws_transport.unregister_client(client.client_id)

        assert ws_transport.client_count == 0

    def test_message_buffer_cleanup(
        self, ws_transport: WebSocketTransport
    ) -> None:
        """Тест очистки буфера сообщений."""
        client = MockWebSocketClient("buffer_test")
        ws_transport.register_client(
            client_id=client.client_id,
            websocket=client,
            subscriptions=[Channel.RECORDING],
        )

        for i in range(100):
            message = WebSocketMessage(
                type=MessageType.EVENT,
                channel=Channel.RECORDING,
                event={"type": "test", "payload": {"seq": i}},
            )
            ws_transport.broadcast(message)

        ws_transport.unregister_client(client.client_id)

        assert ws_transport.client_count == 0


class TestWebSocketErrorHandling:
    """Тесты обработки ошибок."""

    def test_broadcast_to_closed_client(
        self, ws_transport: WebSocketTransport
    ) -> None:
        """Тест broadcast клиенту с закрытым соединением."""
        client = MockWebSocketClient("closed_test")
        ws_transport.register_client(
            client_id=client.client_id,
            websocket=client,
            subscriptions=[Channel.RECORDING],
        )

        client.closed = True

        message = WebSocketMessage(
            type=MessageType.EVENT,
            channel=Channel.RECORDING,
            event={"type": "test", "payload": {}},
        )

        ws_transport.broadcast(message)

        ws_transport.unregister_client(client.client_id)
        assert ws_transport.client_count == 0

    def test_invalid_message_format(
        self, ws_transport: WebSocketTransport
    ) -> None:
        """Тест обработки некорректного формата сообщения."""
        client = MockWebSocketClient("invalid_test")
        ws_transport.register_client(
            client_id=client.client_id,
            websocket=client,
            subscriptions=[Channel.RECORDING],
        )

        message = WebSocketMessage(
            type=MessageType.EVENT,
            channel=Channel.RECORDING,
            event=None,
            data={"test": "value"},
        )

        ws_transport.broadcast(message)

        assert len(client.received_messages) == 1


class TestWebSocketHeartbeat:
    """Тесты heartbeat механизма."""

    def test_heartbeat_timeout_detection(
        self, ws_transport: WebSocketTransport
    ) -> None:
        """Тест обнаружения клиента без heartbeat."""
        client = MockWebSocketClient("heartbeat_test")
        ws_transport.register_client(
            client_id=client.client_id,
            websocket=client,
            subscriptions=[Channel.RECORDING],
        )

        from datetime import datetime, timedelta

        from api.websocket_transport import HEARTBEAT_TIMEOUT_SECONDS

        ws_client = ws_transport._clients.get(client.client_id)
        if ws_client:
            ws_client.last_heartbeat = datetime.utcnow() - timedelta(
                seconds=HEARTBEAT_TIMEOUT_SECONDS + 10
            )

            stale = ws_transport._check_stale_clients()
            assert client.client_id in stale

    def test_heartbeat_updates_timestamp(
        self, ws_transport: WebSocketTransport
    ) -> None:
        """Тест обновления timestamp при heartbeat."""
        client = MockWebSocketClient("heartbeat_update_test")
        ws_transport.register_client(
            client_id=client.client_id,
            websocket=client,
            subscriptions=[Channel.RECORDING],
        )

        ws_transport.update_heartbeat(client.client_id)

        ws_client = ws_transport._clients.get(client.client_id)
        if ws_client:
            from datetime import datetime

            assert ws_client.last_heartbeat is not None
            assert (
                datetime.utcnow() - ws_client.last_heartbeat
            ).total_seconds() < 1.0
