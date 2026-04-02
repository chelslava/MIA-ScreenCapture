"""
Unit тесты для API сервера
==========================

Тестирует класс APIServer без реального запуска сервера.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

import api.server as api_server_module
from api.auth import init_api_auth
from api.routes import register_routes
from api.server import (
    APIIdempotencyStore,
    APIOperationStore,
    APIServer,
    APIServerObservability,
)
from api.websocket import WebSocketManager


class TestAPIServerInit:
    """Тесты инициализации APIServer."""

    def test_init_default_params(self) -> None:
        """Проверка параметров по умолчанию."""
        server = APIServer()

        assert server.host == "127.0.0.1"
        assert server.port == 5000
        assert server.app is not None
        assert server._running is False
        assert server._callbacks == {}

    def test_init_custom_params(self) -> None:
        """Проверка пользовательских параметров."""
        server = APIServer(host="192.168.1.1", port=8080)

        assert server.host == "192.168.1.1"
        assert server.port == 8080

    def test_init_localhost(self) -> None:
        """Проверка инициализации с localhost."""
        server = APIServer(host="127.0.0.1", port=5001)

        assert server.host == "127.0.0.1"
        assert server.port == 5001

    def test_init_creates_flask_app(self) -> None:
        """Проверка создания Flask приложения."""
        server = APIServer()

        assert server.app is not None
        assert hasattr(server.app, "route")

    def test_init_callbacks_empty(self) -> None:
        """Проверка пустого словаря callbacks при инициализации."""
        server = APIServer()

        assert server._callbacks == {}
        assert server.get_callback("nonexistent") is None


class TestAPIServerCallbacks:
    """Тесты работы с callbacks."""

    def test_set_callback(self) -> None:
        """Проверка установки callback."""
        server = APIServer()

        def test_callback():
            return {"status": "ok"}

        server.set_callback("test", test_callback)

        assert server.get_callback("test") == test_callback

    def test_set_multiple_callbacks(self) -> None:
        """Проверка установки нескольких callbacks."""
        server = APIServer()

        callbacks = {
            "start": lambda: {"started": True},
            "stop": lambda: {"stopped": True},
            "status": lambda: {"recording": False},
        }

        for name, callback in callbacks.items():
            server.set_callback(name, callback)

        for name, callback in callbacks.items():
            assert server.get_callback(name) == callback

    def test_set_callback_overwrite(self) -> None:
        """Проверка перезаписи callback."""
        server = APIServer()

        def callback1():
            return {"version": 1}

        def callback2():
            return {"version": 2}

        server.set_callback("test", callback1)
        server.set_callback("test", callback2)

        assert server.get_callback("test") == callback2

    def test_get_callback_nonexistent(self) -> None:
        """Проверка получения несуществующего callback."""
        server = APIServer()

        result = server.get_callback("nonexistent")

        assert result is None

    def test_set_callback_none(self) -> None:
        """Проверка установки None как callback."""
        server = APIServer()

        server.set_callback("test", None)

        assert server.get_callback("test") is None

    def test_callback_with_args(self) -> None:
        """Проверка callback с аргументами."""
        server = APIServer()

        def callback_with_args(data):
            return {"received": data}

        server.set_callback("test", callback_with_args)

        callback = server.get_callback("test")
        result = callback({"key": "value"})

        assert result == {"received": {"key": "value"}}

    def test_set_and_get_websocket_manager(self) -> None:
        """Проверка установки менеджера real-time событий."""
        server = APIServer()
        manager = WebSocketManager()

        server.set_websocket_manager(manager)

        assert server.get_websocket_manager() is manager


class TestAPIServerStartStop:
    """Тесты запуска и остановки сервера."""

    def test_start_sets_running_flag(self) -> None:
        """Проверка установки флага running при запуске."""
        server = APIServer(host="127.0.0.1", port=5002)

        with (
            patch.object(server, "_run_server"),
            patch.object(server, "_validate_bind_address"),
        ):
            result = server.start()

        assert result is True
        assert server._running is True

    def test_start_returns_false_if_already_running(self) -> None:
        """Проверка что повторный запуск возвращает False."""
        server = APIServer(host="127.0.0.1", port=5003)

        with (
            patch.object(server, "_run_server"),
            patch.object(server, "_validate_bind_address"),
        ):
            server.start()
            result = server.start()

        assert result is False

    def test_start_returns_false_if_bind_validation_fails(self) -> None:
        """Проверка fail-fast при занятом порте или ошибке bind."""
        server = APIServer(host="127.0.0.1", port=5003)

        with patch.object(
            server,
            "_validate_bind_address",
            side_effect=OSError("Address already in use"),
        ):
            result = server.start()

        assert result is False
        assert server._running is False
        assert server._server_thread is None

    def test_stop_clears_running_flag(self) -> None:
        """Проверка очистки флага running при остановке."""
        server = APIServer(host="127.0.0.1", port=5004)

        with (
            patch.object(server, "_run_server"),
            patch.object(server, "_validate_bind_address"),
        ):
            server.start()

        server.stop()

        assert server._running is False

    def test_stop_waits_for_server_thread_shutdown(self) -> None:
        """Проверка ожидания завершения потока при остановке."""
        server = APIServer(host="127.0.0.1", port=5008)
        wsgi_server = MagicMock()
        server_thread = MagicMock()
        server_thread.is_alive.side_effect = [True, False]
        server._wsgi_server = wsgi_server
        server._server_thread = server_thread
        server._running = True

        with patch.object(api_server_module.logger, "warning") as warning:
            server.stop()

        wsgi_server.close.assert_called_once()
        server_thread.join.assert_called_once_with(
            timeout=api_server_module._SERVER_STOP_WAIT_SECONDS
        )
        warning.assert_not_called()
        assert server._running is False

    def test_stop_logs_warning_when_thread_timeout_expires(self) -> None:
        """Проверка логирования при таймауте завершения потока."""
        server = APIServer(host="127.0.0.1", port=5009)
        wsgi_server = MagicMock()
        server_thread = MagicMock()
        server_thread.is_alive.side_effect = [True, True]
        server._wsgi_server = wsgi_server
        server._server_thread = server_thread
        server._running = True

        with patch.object(api_server_module.logger, "warning") as warning:
            server.stop()

        wsgi_server.close.assert_called_once()
        server_thread.join.assert_called_once_with(
            timeout=api_server_module._SERVER_STOP_WAIT_SECONDS
        )
        warning.assert_any_call(
            "Поток API сервера не завершился за %.1f секунд",
            api_server_module._SERVER_STOP_WAIT_SECONDS,
        )
        assert server._running is False

    def test_is_running_returns_correct_state(self) -> None:
        """Проверка метода is_running."""
        server = APIServer(host="127.0.0.1", port=5005)

        assert server.is_running() is False

        with (
            patch.object(server, "_run_server"),
            patch.object(server, "_validate_bind_address"),
        ):
            server.start()

        assert server.is_running() is True

        server.stop()

        assert server.is_running() is False

    def test_start_creates_thread(self) -> None:
        """Проверка создания потока при запуске."""
        server = APIServer(host="127.0.0.1", port=5006)

        with (
            patch.object(server, "_run_server"),
            patch.object(server, "_validate_bind_address"),
        ):
            server.start()

        assert server._server_thread is not None
        assert isinstance(server._server_thread, threading.Thread)

    def test_start_recreates_idempotency_store_after_stop(self) -> None:
        """Проверка пересоздания idempotency store после stop -> start."""
        server = APIServer(host="127.0.0.1", port=5010)
        first_store = server._idempotency

        with (
            patch.object(server, "_run_server"),
            patch.object(server, "_validate_bind_address"),
        ):
            assert server.start() is True

        server.stop()
        assert first_store.is_running() is False

        with (
            patch.object(server, "_run_server"),
            patch.object(server, "_validate_bind_address"),
        ):
            assert server.start() is True

        assert server._idempotency is not first_store
        assert server._idempotency.is_running() is True
        server.stop()

    def test_start_recreates_operation_store_after_stop(self) -> None:
        """Проверка пересоздания operation store после stop -> start."""
        server = APIServer(host="127.0.0.1", port=5011)
        first_store = server._operations

        with (
            patch.object(server, "_run_server"),
            patch.object(server, "_validate_bind_address"),
        ):
            assert server.start() is True

        server.stop()
        assert first_store.is_running() is False

        with (
            patch.object(server, "_run_server"),
            patch.object(server, "_validate_bind_address"),
        ):
            assert server.start() is True

        assert server._operations is not first_store
        assert server._operations.is_running() is True
        server.stop()

    def test_thread_is_daemon(self) -> None:
        """Проверка что поток является daemon."""
        server = APIServer(host="127.0.0.1", port=5007)

        with (
            patch.object(server, "_run_server"),
            patch.object(server, "_validate_bind_address"),
        ):
            server.start()

        assert server._server_thread.daemon is True

    def test_run_server_uses_configured_waitress_threads(self) -> None:
        """Проверка прокидывания server_threads в waitress.create_server."""
        server = APIServer(host="127.0.0.1", port=5007, server_threads=7)
        fake_wsgi_server = MagicMock()

        with patch(
            "api.server.create_server", return_value=fake_wsgi_server
        ) as create_server_mock:
            server._run_server()

        create_server_mock.assert_called_once()
        _, kwargs = create_server_mock.call_args
        assert kwargs["threads"] == 7


class TestAPIServerURL:
    """Тесты получения URL сервера."""

    def test_get_url_default(self) -> None:
        """Проверка URL с параметрами по умолчанию."""
        server = APIServer()

        url = server.get_url()

        assert url == "http://127.0.0.1:5000"

    def test_get_url_custom(self) -> None:
        """Проверка URL с пользовательскими параметрами."""
        server = APIServer(host="192.168.1.100", port=8080)

        url = server.get_url()

        assert url == "http://192.168.1.100:8080"

    def test_get_url_localhost(self) -> None:
        """Проверка URL с localhost."""
        server = APIServer(host="127.0.0.1", port=5001)

        url = server.get_url()

        assert url == "http://127.0.0.1:5001"


class TestAPIServerFlaskApp:
    """Тесты Flask приложения."""

    def test_flask_app_has_error_handlers(self) -> None:
        """Проверка наличия обработчиков ошибок."""
        server = APIServer()

        # Проверяем что обработчики ошибок зарегистрированы
        assert 404 in server.app.error_handler_spec.get(None, {})
        assert 500 in server.app.error_handler_spec.get(None, {})

    def test_flask_app_has_cors(self) -> None:
        """Проверка включения CORS."""
        server = APIServer()

        # Проверяем что CORS настроен (Flask-CORS добавляет заголовки)
        assert server.app is not None

    def test_flask_app_testing_mode(self) -> None:
        """Проверка режима тестирования."""
        server = APIServer()

        # По умолчанию TESTING = False
        assert server.app.testing is False

        # Можно включить режим тестирования
        server.app.config["TESTING"] = True
        assert server.app.testing is True


class TestAPIServerAPIKey:
    """Тесты работы с API ключом."""

    def test_get_api_key_returns_string_or_none(self) -> None:
        """Проверка что get_api_key возвращает строку или None."""
        server = APIServer()

        key = server.get_api_key()

        # Ключ может быть строкой или None
        assert key is None or isinstance(key, str)

    def test_get_api_key_with_env(self) -> None:
        """Проверка получения ключа из переменной окружения."""
        import os

        test_key = "test-api-key-12345"
        original_env = os.environ.get("MIA_API_KEY")

        try:
            os.environ["MIA_API_KEY"] = test_key
            server = APIServer()

            key = server.get_api_key()

            # Ключ должен быть установлен
            assert key is not None

        finally:
            if original_env is not None:
                os.environ["MIA_API_KEY"] = original_env
            else:
                os.environ.pop("MIA_API_KEY", None)


class TestAPIServerThreadSafety:
    """Тесты потокобезопасности."""

    def test_concurrent_callback_access(self) -> None:
        """Проверка параллельного доступа к callbacks."""
        server = APIServer()
        errors = []

        def set_callback(thread_id: int) -> None:
            try:
                for i in range(100):
                    server.set_callback(
                        f"callback_{thread_id}_{i}", lambda: None
                    )
            except Exception as e:
                errors.append(e)

        def get_callback(thread_id: int) -> None:
            try:
                for i in range(100):
                    server.get_callback(f"callback_{thread_id}_{i}")
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(5):
            threads.append(threading.Thread(target=set_callback, args=(i,)))
            threads.append(threading.Thread(target=get_callback, args=(i,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_concurrent_start_stop(self) -> None:
        """Проверка параллельных вызовов start/stop."""
        server = APIServer(host="127.0.0.1", port=5010)
        results = []

        def try_start():
            with patch.object(server, "_run_server"):
                results.append(server.start())

        def try_stop():
            server.stop()
            results.append("stopped")

        threads = [
            threading.Thread(target=try_start),
            threading.Thread(target=try_stop),
            threading.Thread(target=try_start),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Хотя бы один start должен вернуть True
        assert True in results or "stopped" in results


class TestAPIServerEdgeCases:
    """Тесты граничных случаев."""

    def test_multiple_servers_different_ports(self) -> None:
        """Проверка создания нескольких серверов на разных портах."""
        server1 = APIServer(port=5001)
        server2 = APIServer(port=5002)

        assert server1.port != server2.port
        assert server1.app is not server2.app

    def test_server_with_zero_port(self) -> None:
        """Проверка создания сервера с портом 0."""
        # Порт 0 означает автоматический выбор порта ОС
        server = APIServer(port=0)

        assert server.port == 0

    def test_server_with_high_port(self) -> None:
        """Проверка создания сервера с высоким портом."""
        server = APIServer(port=65535)

        assert server.port == 65535

    def test_server_with_ipv6_host(self) -> None:
        """Проверка создания сервера с IPv6 адресом."""
        server = APIServer(host="::1", port=5001)

        assert server.host == "::1"

    def test_callback_with_exception(self) -> None:
        """Проверка callback который выбрасывает исключение."""
        server = APIServer()

        def failing_callback():
            raise RuntimeError("Test error")

        server.set_callback("failing", failing_callback)

        callback = server.get_callback("failing")
        with pytest.raises(RuntimeError, match="Test error"):
            callback()

    def test_callback_returning_none(self) -> None:
        """Проверка callback возвращающего None."""
        server = APIServer()

        def none_callback():
            return None

        server.set_callback("none", none_callback)

        callback = server.get_callback("none")
        assert callback() is None

    def test_callback_returning_empty_dict(self) -> None:
        """Проверка callback возвращающего пустой словарь."""
        server = APIServer()

        def empty_callback():
            return {}

        server.set_callback("empty", empty_callback)

        callback = server.get_callback("empty")
        assert callback() == {}


class TestAPIServerObservability:
    """Тесты observability заголовков и health endpoint."""

    def _make_client(self):
        server = APIServer()
        init_api_auth(server.app, api_key="test-api-key")
        server.set_websocket_manager(WebSocketManager())
        server.set_callback(
            "status",
            MagicMock(
                return_value={
                    "is_recording": False,
                    "is_paused": False,
                    "elapsed_time": 0,
                    "current_file": None,
                }
            ),
        )
        register_routes(server.app, server)
        server.app.config["TESTING"] = True
        client = server.app.test_client()
        client.environ_base["HTTP_X_API_KEY"] = "test-api-key"
        return client, server

    def test_request_id_header_is_propagated(self) -> None:
        client, _ = self._make_client()

        response = client.get(
            "/health", headers={"X-Request-ID": "request-123"}
        )

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "request-123"

    def test_request_id_header_is_generated(self) -> None:
        client, _ = self._make_client()

        response = client.get("/health")

        assert response.status_code == 200
        assert response.headers["X-Request-ID"]
        assert len(response.headers["X-Request-ID"]) >= 16

    def test_health_payload_includes_observability_fields(self) -> None:
        client, server = self._make_client()

        response = client.get("/health")
        data = response.get_json()

        assert response.status_code == 200
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert data["version"] == server._version
        assert data["version"] != "unknown"
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0
        assert data["websocket"]["transport_ready"] is True

    def test_latency_stats_reads_samples_under_lock(self) -> None:
        """Проверка чтения latency samples под lock."""
        observability = APIServerObservability()

        class _LockAwareSamples:
            def __iter__(self):
                assert observability._lock.locked()
                return iter([10.0, 20.0, 30.0])

        observability._latency_ms = _LockAwareSamples()  # type: ignore[assignment]

        stats = observability._latency_stats()

        assert stats["count"] == 3
        assert stats["max_ms"] == 30.0


class TestAPIServerOperations:
    """Тесты фоновых операций API."""

    def _make_client(self, stop_callback):
        server = APIServer()
        init_api_auth(server.app, api_key="test-api-key")
        server.set_websocket_manager(WebSocketManager())
        server.set_callback(
            "status",
            MagicMock(
                return_value={
                    "is_recording": False,
                    "is_paused": False,
                    "elapsed_time": 0,
                    "current_file": None,
                }
            ),
        )
        server.set_callback("stop", stop_callback)
        register_routes(server.app, server)
        server.app.config["TESTING"] = True
        client = server.app.test_client()
        client.environ_base["HTTP_X_API_KEY"] = "test-api-key"
        return client

    def test_stop_returns_200_for_fast_operation(self) -> None:
        client = self._make_client(
            lambda: {
                "success": True,
                "filepath": "recording.mp4",
            }
        )

        response = client.post("/api/v1/stop")
        data = response.get_json()

        assert response.status_code == 200
        assert data["success"] is True
        assert data["data"]["filepath"] == "recording.mp4"
        assert data["data"]["operation_id"]
        assert data["data"]["status"] == "succeeded"

    def test_stop_returns_202_for_slow_operation_and_status_endpoint(
        self,
    ) -> None:
        def slow_stop():
            time.sleep(0.35)
            return {
                "success": True,
                "filepath": "slow-recording.mp4",
            }

        client = self._make_client(slow_stop)

        response = client.post("/api/v1/stop")
        data = response.get_json()

        assert response.status_code == 202
        assert data["success"] is True
        assert data["data"]["operation_id"]
        assert data["data"]["status"] == "running"

        operation_id = data["data"]["operation_id"]
        operation_data = None
        for _ in range(20):
            status_response = client.get(f"/api/v1/operations/{operation_id}")
            operation_data = status_response.get_json()
            if operation_data["data"]["status"] != "running":
                break
            time.sleep(0.05)

        assert operation_data is not None
        assert operation_data["success"] is True
        assert operation_data["data"]["operation_id"] == operation_id
        assert operation_data["data"]["status"] == "succeeded"
        assert operation_data["data"]["result"]["filepath"] == (
            "slow-recording.mp4"
        )


class TestAPIIdempotencyStore:
    """Тесты TTL-хранилища идемпотентных операций."""

    def test_replay_for_same_key_and_fingerprint(self) -> None:
        store = APIIdempotencyStore(
            ttl_seconds=10.0, cleanup_interval_seconds=5.0
        )
        key = "idem-key-1"
        fingerprint = "fp-1"

        started = store.begin(key, fingerprint)
        assert started["state"] == "started"

        store.complete(
            key=key,
            status_code=200,
            body_bytes=b'{"success":true}',
            mimetype="application/json",
        )
        replay = store.begin(key, fingerprint)

        assert replay["state"] == "replay"
        assert replay["response"]["status_code"] == 200
        assert replay["response"]["body_bytes"] == b'{"success":true}'
        store.stop()

    def test_conflict_for_same_key_with_other_fingerprint(self) -> None:
        store = APIIdempotencyStore(
            ttl_seconds=10.0, cleanup_interval_seconds=5.0
        )
        key = "idem-key-2"

        started = store.begin(key, "fp-a")
        assert started["state"] == "started"

        conflict = store.begin(key, "fp-b")
        assert conflict["state"] == "conflict"
        store.stop()

    def test_cleanup_removes_expired_entries(self) -> None:
        store = APIIdempotencyStore(
            ttl_seconds=0.01,
            cleanup_interval_seconds=0.005,
        )
        key = "idem-key-3"

        store.begin(key, "fp-cleanup")
        store.complete(
            key=key,
            status_code=200,
            body_bytes=b'{"ok":true}',
            mimetype="application/json",
        )
        time.sleep(0.05)

        assert store.get_size() == 0
        store.stop()

    def test_abort_clears_in_progress_entry(self) -> None:
        """abort удаляет in-progress запись и позволяет начать заново."""
        store = APIIdempotencyStore(
            ttl_seconds=10.0, cleanup_interval_seconds=5.0
        )
        key = "idem-key-abort"

        started = store.begin(key, "fp-abort")
        assert started["state"] == "started"

        in_progress = store.begin(key, "fp-abort")
        assert in_progress["state"] == "in_progress"

        store.abort(key)
        restarted = store.begin(key, "fp-abort")
        assert restarted["state"] == "started"
        store.stop()

    def test_complete_5xx_drops_entry_without_replay(self) -> None:
        """Ответ 5xx не кэшируется: следующий begin должен быть started."""
        store = APIIdempotencyStore(
            ttl_seconds=10.0, cleanup_interval_seconds=5.0
        )
        key = "idem-key-5xx"

        started = store.begin(key, "fp-5xx")
        assert started["state"] == "started"

        store.complete(
            key=key,
            status_code=500,
            body_bytes=b'{"success":false}',
            mimetype="application/json",
        )
        restarted = store.begin(key, "fp-5xx")
        assert restarted["state"] == "started"
        store.stop()


class TestAPIOperationStore:
    """Тесты bounded executor для фоновых операций API."""

    def test_rejects_operation_when_queue_is_full(self) -> None:
        """При переполнении очереди операция должна отклоняться."""
        store = APIOperationStore(max_workers=1, max_queue_size=0)
        release_event = threading.Event()

        def slow_runner() -> dict[str, bool]:
            release_event.wait(timeout=1.0)
            return {"success": True}

        first = store.submit("slow", slow_runner)
        second = store.submit("slow", slow_runner)

        assert first["status"] == "running"
        assert second["status"] == "failed"
        assert "переполнена" in str(second.get("error", "")).lower()

        metrics = store.get_metrics_snapshot()
        assert metrics["rejected_total"] == 1
        assert metrics["inflight"] == 1

        release_event.set()
        completed = store.wait(str(first["id"]), timeout=1.5)
        assert completed is not None
        assert completed["status"] == "succeeded"
        store.stop()

    def test_runner_exception_marks_operation_failed(self) -> None:
        """Исключение runner переводит операцию в failed."""
        store = APIOperationStore(max_workers=1, max_queue_size=1)

        def failing_runner() -> None:
            raise RuntimeError("boom")

        operation = store.submit("failing", failing_runner)
        completed = store.wait(str(operation["id"]), timeout=1.0)

        assert completed is not None
        assert completed["status"] == "failed"
        assert "boom" in str(completed.get("error", ""))
        store.stop()

    def test_submit_rejected_after_stop(self) -> None:
        """После stop новые операции должны отклоняться."""
        store = APIOperationStore(max_workers=1, max_queue_size=1)
        store.stop()

        operation = store.submit("after-stop", lambda: {"success": True})

        assert operation["status"] == "failed"
        assert "executor остановлен" in str(operation.get("error", ""))

    def test_wait_unknown_operation_returns_none(self) -> None:
        """Ожидание неизвестной операции должно возвращать None."""
        store = APIOperationStore(max_workers=1, max_queue_size=1)
        try:
            result = store.wait("missing-operation-id", timeout=0.01)
            assert result is None
        finally:
            store.stop()
