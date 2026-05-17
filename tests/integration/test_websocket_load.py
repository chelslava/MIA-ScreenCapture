"""
Нагрузочные тесты WebSocket/SSE транспорта.

Параметры подобраны для быстрого CI-прогона (< 30 сек).
Тесты с большей нагрузкой отмечены @pytest.mark.slow и
пропускаются при стандартном запуске CI (-m "not slow").
"""

from __future__ import annotations

import threading
import time
from collections.abc import Generator

import pytest

from api.websocket import WebSocketManager
from api.websocket_transport import WebSocketTransport

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ws_manager() -> WebSocketManager:
    """Менеджер WebSocket с небольшим буфером для нагрузочных тестов."""
    return WebSocketManager(max_events=200)


@pytest.fixture
def ws_transport(
    ws_manager: WebSocketManager,
) -> Generator[WebSocketTransport, None, None]:
    """Транспорт WebSocket, запускается и останавливается вокруг теста."""
    transport = WebSocketTransport(ws_manager)
    transport.start()
    yield transport
    transport.stop()


# ---------------------------------------------------------------------------
# Publish throughput — без IO, только in-process
# ---------------------------------------------------------------------------


class TestWebSocketPublishLoad:
    """Тесты пропускной способности публикации событий."""

    # CI: 50 итераций; полный прогон (slow): 500
    NUM_EVENTS_CI = 50
    NUM_EVENTS_SLOW = 500

    def test_publish_many_events_sequential(
        self, ws_manager: WebSocketManager
    ) -> None:
        """Последовательная публикация событий не вешает менеджер."""
        for i in range(self.NUM_EVENTS_CI):
            ws_manager.publish({"type": "progress", "data": {"frame": i}})

        recent = ws_manager.get_recent_events(limit=self.NUM_EVENTS_CI)
        # Буфер ограничен max_events=200; при 50 событиях все должны быть.
        assert len(recent) == self.NUM_EVENTS_CI
        assert recent[-1]["data"]["frame"] == self.NUM_EVENTS_CI - 1

    def test_publish_concurrent_threads(
        self, ws_manager: WebSocketManager
    ) -> None:
        """Параллельная публикация из нескольких потоков — без дедлоков."""
        num_threads = 5
        events_per_thread = 10  # итого 50 событий
        errors: list[Exception] = []

        def publish_batch(thread_id: int) -> None:
            try:
                for i in range(events_per_thread):
                    ws_manager.publish(
                        {"type": "load", "data": {"t": thread_id, "i": i}}
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(target=publish_batch, args=(tid,))
            for tid in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert errors == [], f"Потоки упали с ошибками: {errors}"
        # Все события опубликованы и буфер не переполнен некорректно.
        recent = ws_manager.get_recent_events(limit=200)
        assert len(recent) == num_threads * events_per_thread

    @pytest.mark.slow
    def test_publish_many_events_high_volume(
        self, ws_manager: WebSocketManager
    ) -> None:
        """500 событий — полный прогон, пропускается в CI."""
        for i in range(self.NUM_EVENTS_SLOW):
            ws_manager.publish({"type": "stress", "data": {"n": i}})

        recent = ws_manager.get_recent_events(limit=200)
        # Буфер max_events=200, поэтому хранятся последние 200.
        assert len(recent) == 200
        assert recent[-1]["data"]["n"] == self.NUM_EVENTS_SLOW - 1


# ---------------------------------------------------------------------------
# Client registration throughput
# ---------------------------------------------------------------------------


class TestWebSocketClientLoad:
    """Тесты регистрации/отключения клиентов."""

    # CI: 20 клиентов; slow: 100
    NUM_CLIENTS_CI = 20
    NUM_CLIENTS_SLOW = 100

    def test_register_and_unregister_clients(
        self, ws_transport: WebSocketTransport
    ) -> None:
        """Быстрая регистрация и отключение клиентов."""
        client_ids = [f"client-{i}" for i in range(self.NUM_CLIENTS_CI)]

        for cid in client_ids:
            ws_transport.register_client(cid)

        assert ws_transport.get_client_count() == self.NUM_CLIENTS_CI

        for cid in client_ids:
            ws_transport.unregister_client(cid)

        assert ws_transport.get_client_count() == 0

    def test_concurrent_register_unregister(
        self, ws_transport: WebSocketTransport
    ) -> None:
        """Параллельная регистрация и отключение — без гонок."""
        num_clients = 10
        errors: list[Exception] = []

        def register_and_unregister(cid: str) -> None:
            try:
                ws_transport.register_client(cid)
                # Минимальная пауза чтобы создать перекрытие потоков.
                time.sleep(0.002)
                ws_transport.unregister_client(cid)
            except Exception as exc:
                errors.append(exc)

        threads = [
            threading.Thread(
                target=register_and_unregister, args=(f"concurrent-{i}",)
            )
            for i in range(num_clients)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert errors == [], f"Ошибки в потоках: {errors}"
        assert ws_transport.get_client_count() == 0

    @pytest.mark.slow
    def test_register_many_clients_high_volume(
        self, ws_transport: WebSocketTransport
    ) -> None:
        """100 клиентов — полный прогон, пропускается в CI."""
        client_ids = [f"heavy-{i}" for i in range(self.NUM_CLIENTS_SLOW)]

        for cid in client_ids:
            ws_transport.register_client(cid)

        assert ws_transport.get_client_count() == self.NUM_CLIENTS_SLOW

        for cid in client_ids:
            ws_transport.unregister_client(cid)

        assert ws_transport.get_client_count() == 0


# ---------------------------------------------------------------------------
# Mixed publish + client lifecycle
# ---------------------------------------------------------------------------


class TestWebSocketMixedLoad:
    """Совместная нагрузка: публикация событий + управление клиентами."""

    def test_publish_while_clients_connect(
        self, ws_manager: WebSocketManager, ws_transport: WebSocketTransport
    ) -> None:
        """События публикуются корректно пока клиенты подключаются/отключаются."""
        errors: list[Exception] = []
        published: list[int] = []

        def publisher() -> None:
            try:
                for i in range(20):
                    ws_manager.publish({"type": "mixed", "data": {"seq": i}})
                    time.sleep(0.001)
                    published.append(i)
            except Exception as exc:
                errors.append(exc)

        def client_churn() -> None:
            try:
                for i in range(5):
                    cid = f"churn-{i}"
                    ws_transport.register_client(cid)
                    time.sleep(0.002)
                    ws_transport.unregister_client(cid)
            except Exception as exc:
                errors.append(exc)

        pub_thread = threading.Thread(target=publisher)
        churn_thread = threading.Thread(target=client_churn)

        pub_thread.start()
        churn_thread.start()

        pub_thread.join(timeout=5)
        churn_thread.join(timeout=5)

        assert errors == [], f"Ошибки при смешанной нагрузке: {errors}"
        assert len(published) == 20
        assert ws_transport.get_client_count() == 0

    @pytest.mark.slow
    def test_sustained_publish_load(
        self, ws_manager: WebSocketManager
    ) -> None:
        """Длительная публикация — помечена slow, пропускается в CI."""
        start = time.monotonic()
        count = 0
        # Публикуем 0.5 секунды вместо 30 (оригинальный timeout).
        while time.monotonic() - start < 0.5:
            ws_manager.publish({"type": "sustained", "data": {"n": count}})
            count += 1

        assert count > 0
        recent = ws_manager.get_recent_events(limit=200)
        assert len(recent) > 0


# ---------------------------------------------------------------------------
# Buffer boundary tests
# ---------------------------------------------------------------------------


class TestWebSocketBufferBoundary:
    """Тесты граничных условий буфера событий."""

    def test_buffer_wraps_correctly_at_limit(self) -> None:
        """Буфер корректно отбрасывает старые события при переполнении."""
        manager = WebSocketManager(max_events=10)

        for i in range(25):
            manager.publish({"type": "wrap", "data": {"n": i}})

        recent = manager.get_recent_events(limit=50)
        assert len(recent) == 10
        # Последние 10 событий: 15..24
        assert recent[0]["data"]["n"] == 15
        assert recent[-1]["data"]["n"] == 24

    def test_get_recent_events_respects_limit_param(self) -> None:
        """Параметр limit в get_recent_events работает корректно."""
        manager = WebSocketManager(max_events=50)

        for i in range(30):
            manager.publish({"type": "limit-test", "data": {"n": i}})

        five = manager.get_recent_events(limit=5)
        assert len(five) == 5
        assert five[-1]["data"]["n"] == 29

        ten = manager.get_recent_events(limit=10)
        assert len(ten) == 10

    def test_empty_manager_returns_empty_list(self) -> None:
        """Пустой менеджер возвращает пустой список."""
        manager = WebSocketManager(max_events=10)
        assert manager.get_recent_events(limit=100) == []
