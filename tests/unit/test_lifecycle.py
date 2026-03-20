"""
Тесты для модуля Graceful Shutdown
===================================

Unit тесты для проверки корректного завершения работы приложения.
"""

import signal
import threading
from unittest.mock import patch

import pytest

from core.lifecycle import (
    GracefulShutdown,
    get_shutdown_manager,
    register_shutdown_handler,
    request_shutdown,
    reset_shutdown_manager,
)


class TestGracefulShutdownInit:
    """Тесты инициализации GracefulShutdown."""

    def test_init_default_timeout(self) -> None:
        """Проверка таймаута по умолчанию."""
        shutdown = GracefulShutdown()
        assert shutdown.timeout == 30.0

    def test_init_custom_timeout(self) -> None:
        """Проверка пользовательского таймаута."""
        shutdown = GracefulShutdown(timeout=60.0)
        assert shutdown.timeout == 60.0

    def test_init_zero_timeout_raises_error(self) -> None:
        """Проверка что нулевой таймаут вызывает ошибку."""
        shutdown = GracefulShutdown()
        with pytest.raises(ValueError, match="положительным"):
            shutdown.timeout = 0

    def test_init_negative_timeout_raises_error(self) -> None:
        """Проверка что отрицательный таймаут вызывает ошибку."""
        shutdown = GracefulShutdown()
        with pytest.raises(ValueError, match="положительным"):
            shutdown.timeout = -10

    def test_is_shutting_down_initial_false(self) -> None:
        """Проверка начального состояния флага."""
        shutdown = GracefulShutdown()
        assert shutdown.is_shutting_down is False


class TestHandlerRegistration:
    """Тесты регистрации обработчиков."""

    def test_register_handler(self) -> None:
        """Проверка регистрации обработчика."""
        shutdown = GracefulShutdown()

        def dummy_handler() -> None:
            pass

        shutdown.register_handler(dummy_handler)
        assert shutdown.get_handlers_count() == 1

    def test_register_multiple_handlers(self) -> None:
        """Проверка регистрации нескольких обработчиков."""
        shutdown = GracefulShutdown()

        shutdown.register_handler(lambda: None)
        shutdown.register_handler(lambda: None)
        shutdown.register_handler(lambda: None)

        assert shutdown.get_handlers_count() == 3

    def test_handler_decorator(self) -> None:
        """Проверка декоратора для регистрации."""
        shutdown = GracefulShutdown()

        @shutdown.handler
        def decorated_handler() -> None:
            pass

        assert shutdown.get_handlers_count() == 1

    def test_unregister_handler(self) -> None:
        """Проверка удаления обработчика."""
        shutdown = GracefulShutdown()

        def handler() -> None:
            pass

        shutdown.register_handler(handler)
        assert shutdown.get_handlers_count() == 1

        result = shutdown.unregister_handler(handler)
        assert result is True
        assert shutdown.get_handlers_count() == 0

    def test_unregister_nonexistent_handler(self) -> None:
        """Проверка удаления несуществующего обработчика."""
        shutdown = GracefulShutdown()

        result = shutdown.unregister_handler(lambda: None)
        assert result is False

    def test_clear_handlers(self) -> None:
        """Проверка очистки всех обработчиков."""
        shutdown = GracefulShutdown()

        shutdown.register_handler(lambda: None)
        shutdown.register_handler(lambda: None)
        shutdown.clear_handlers()

        assert shutdown.get_handlers_count() == 0


class TestShutdown:
    """Тесты выполнения shutdown."""

    def test_shutdown_calls_handlers_in_reverse_order(self) -> None:
        """Проверка вызова обработчиков в обратном порядке."""
        shutdown = GracefulShutdown()
        call_order: list[int] = []

        shutdown.register_handler(lambda: call_order.append(1))
        shutdown.register_handler(lambda: call_order.append(2))
        shutdown.register_handler(lambda: call_order.append(3))

        shutdown.shutdown()

        # LIFO: последний зарегистрированный выполняется первым
        assert call_order == [3, 2, 1]

    def test_shutdown_returns_true_on_success(self) -> None:
        """Проверка возврата True при успешном выполнении."""
        shutdown = GracefulShutdown()
        shutdown.register_handler(lambda: None)

        result = shutdown.shutdown()
        assert result is True

    def test_shutdown_returns_false_on_error(self) -> None:
        """Проверка возврата False при ошибке в обработчике."""
        shutdown = GracefulShutdown()

        def failing_handler() -> None:
            raise RuntimeError("Test error")

        shutdown.register_handler(failing_handler)

        result = shutdown.shutdown()
        assert result is False

    def test_shutdown_continues_on_error(self) -> None:
        """Проверка продолжения выполнения при ошибке."""
        shutdown = GracefulShutdown()
        call_order: list[str] = []

        def error_handler() -> None:
            raise RuntimeError("error")

        shutdown.register_handler(lambda: call_order.append("first"))
        shutdown.register_handler(error_handler)
        shutdown.register_handler(lambda: call_order.append("third"))

        shutdown.shutdown()

        # Все обработчики должны быть вызваны
        assert "first" in call_order
        assert "third" in call_order

    def test_shutdown_empty_handlers(self) -> None:
        """Проверка shutdown без обработчиков."""
        shutdown = GracefulShutdown()
        result = shutdown.shutdown()
        assert result is True


class TestSignalHandlers:
    """Тесты обработки сигналов."""

    def test_setup_signal_handlers(self) -> None:
        """Проверка установки обработчиков сигналов."""
        shutdown = GracefulShutdown()

        with patch("signal.signal") as mock_signal:
            shutdown.setup_signal_handlers()

            # Проверяем что signal.signal был вызван для SIGINT и SIGTERM
            assert mock_signal.call_count == 2

    def test_restore_signal_handlers(self) -> None:
        """Проверка восстановления обработчиков сигналов."""
        shutdown = GracefulShutdown()

        with patch("signal.signal") as mock_signal:
            mock_signal.return_value = signal.SIG_DFL
            shutdown.setup_signal_handlers()
            shutdown.restore_signal_handlers()

            # Проверяем что signal.signal был вызван для восстановления
            assert mock_signal.call_count >= 2


class TestRequestShutdown:
    """Тесты программного запроса shutdown."""

    def test_request_shutdown_returns_true_first_time(self) -> None:
        """Проверка возврата True при первом запросе."""
        shutdown = GracefulShutdown()
        shutdown.register_handler(lambda: None)

        result = shutdown.request_shutdown()
        assert result is True

    def test_request_shutdown_returns_false_second_time(self) -> None:
        """Проверка возврата False при повторном запросе."""
        shutdown = GracefulShutdown()
        shutdown.register_handler(lambda: None)

        shutdown.request_shutdown()
        result = shutdown.request_shutdown()
        assert result is False

    def test_request_shutdown_sets_flag(self) -> None:
        """Проверка установки флага при запросе."""
        shutdown = GracefulShutdown()
        shutdown.register_handler(lambda: None)

        shutdown.request_shutdown()
        assert shutdown.is_shutting_down is True


class TestGlobalFunctions:
    """Тесты глобальных функций."""

    def test_get_shutdown_manager_singleton(self) -> None:
        """Проверка что get_shutdown_manager возвращает singleton."""
        reset_shutdown_manager()

        manager1 = get_shutdown_manager()
        manager2 = get_shutdown_manager()

        assert manager1 is manager2

    def test_reset_shutdown_manager(self) -> None:
        """Проверка сброса менеджера."""
        manager1 = get_shutdown_manager()
        manager1.register_handler(lambda: None)

        reset_shutdown_manager()

        manager2 = get_shutdown_manager()
        assert manager2 is not manager1
        assert manager2.get_handlers_count() == 0

    def test_register_shutdown_handler_global(self) -> None:
        """Проверка глобальной функции регистрации."""
        reset_shutdown_manager()

        register_shutdown_handler(lambda: None)
        manager = get_shutdown_manager()

        assert manager.get_handlers_count() == 1

    def test_request_shutdown_global(self) -> None:
        """Проверка глобальной функции запроса shutdown."""
        reset_shutdown_manager()

        called = []

        register_shutdown_handler(lambda: called.append(True))
        result = request_shutdown()

        assert result is True
        assert called == [True]


class TestThreadSafety:
    """Тесты потокобезопасности."""

    def test_concurrent_handler_registration(self) -> None:
        """Проверка параллельной регистрации обработчиков."""
        shutdown = GracefulShutdown()
        errors: list[Exception] = []

        def register_handler(_: int) -> None:
            try:
                shutdown.register_handler(lambda: None)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=register_handler, args=(i,))
            for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert shutdown.get_handlers_count() == 10

    def test_concurrent_shutdown_requests(self) -> None:
        """Проверка параллельных запросов shutdown."""
        shutdown = GracefulShutdown()
        shutdown.register_handler(lambda: None)

        results: list[bool] = []
        lock = threading.Lock()

        def request() -> None:
            result = shutdown.request_shutdown()
            with lock:
                results.append(result)

        threads = [threading.Thread(target=request) for _ in range(5)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Только один запрос должен вернуть True
        assert sum(results) == 1


class TestTimeout:
    """Тесты таймаута."""

    def test_timeout_property(self) -> None:
        """Проверка свойства timeout."""
        shutdown = GracefulShutdown()
        assert shutdown.timeout == 30.0

        shutdown.timeout = 60.0
        assert shutdown.timeout == 60.0

    def test_custom_timeout_in_init(self) -> None:
        """Проверка пользовательского таймаута в конструкторе."""
        shutdown = GracefulShutdown(timeout=45.0)
        assert shutdown.timeout == 45.0
