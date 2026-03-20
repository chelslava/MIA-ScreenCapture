"""
Модуль управления жизненным циклом приложения
==============================================

Предоставляет механизм корректного завершения работы (graceful shutdown)
с обработкой сигналов и последовательным выполнением обработчиков.

Example:
    shutdown = GracefulShutdown()
    
    # Регистрация обработчиков
    shutdown.register_handler(stop_recording)
    shutdown.register_handler(save_config)
    shutdown.register_handler(stop_api_server)
    
    # Установка обработчиков сигналов
    shutdown.setup_signal_handlers()
"""

import signal
import sys
import threading
from typing import Any, Callable, Optional

from logger_config import get_module_logger

logger = get_module_logger(__name__)


class GracefulShutdown:
    """
    Менеджер корректного завершения работы.

    Обеспечивает:
    - Обработку сигналов SIGINT (Ctrl+C) и SIGTERM
    - Последовательное выполнение обработчиков в обратном порядке
    - Защиту от повторного срабатывания
    - Таймаут для принудительного завершения
    - Потокобезопасность

    Attributes:
        timeout: Максимальное время на завершение (секунды)
        is_shutting_down: Флаг активного процесса завершения

    Example:
        shutdown = GracefulShutdown(timeout=30)

        @shutdown.handler
        def cleanup_database():
            db.close()

        shutdown.setup_signal_handlers()
    """

    def __init__(self, timeout: float = 30.0) -> None:
        """
        Инициализация менеджера завершения.

        Args:
            timeout: Максимальное время на graceful shutdown в секундах.
                     После истечения времени происходит принудительный выход.
        """
        self._handlers: list[Callable[[], None]] = []
        self._is_shutting_down = False
        self._lock = threading.Lock()
        self._timeout = timeout
        # signal.signal возвращает Union[Callable, int, None]
        self._original_handlers: dict[int, Any] = {}

    @property
    def is_shutting_down(self) -> bool:
        """Возвращает True, если идёт процесс завершения."""
        return self._is_shutting_down

    @property
    def timeout(self) -> float:
        """Возвращает таймаут завершения в секундах."""
        return self._timeout

    @timeout.setter
    def timeout(self, value: float) -> None:
        """Устанавливает таймаут завершения."""
        if value <= 0:
            raise ValueError("Таймаут должен быть положительным числом")
        self._timeout = value

    def register_handler(self, handler: Callable[[], None]) -> None:
        """
        Регистрирует обработчик завершения.

        Обработчики выполняются в обратном порядке регистрации
        (LIFO — Last In, First Out).

        Args:
            handler: Функция без аргументов, выполняемая при завершении

        Example:
            def stop_recording():
                recorder.stop()

            shutdown.register_handler(stop_recording)
        """
        with self._lock:
            self._handlers.append(handler)
            logger.debug(
                f"Зарегистрирован обработчик завершения: "
                f"{handler.__name__ if hasattr(handler, '__name__') else handler}"
            )

    def handler(self, func: Callable[[], None]) -> Callable[[], None]:
        """
        Декоратор для регистрации обработчика завершения.

        Args:
            func: Функция для регистрации

        Returns:
            Та же функция (для возможности использования как декоратора)

        Example:
            @shutdown.handler
            def cleanup():
                save_state()
                close_connections()
        """
        self.register_handler(func)
        return func

    def unregister_handler(self, handler: Callable[[], None]) -> bool:
        """
        Удаляет обработчик из списка.

        Args:
            handler: Функция для удаления

        Returns:
            True если обработчик был найден и удалён
        """
        with self._lock:
            try:
                self._handlers.remove(handler)
                return True
            except ValueError:
                return False

    def clear_handlers(self) -> None:
        """Удаляет все зарегистрированные обработчики."""
        with self._lock:
            self._handlers.clear()
            logger.debug("Все обработчики завершения удалены")

    def setup_signal_handlers(self) -> None:
        """
        Устанавливает обработчики сигналов SIGINT и SIGTERM.

        Сохраняет оригинальные обработчики для возможности восстановления.

        Note:
            В Windows SIGTERM может не поддерживаться полностью,
            но SIGINT (Ctrl+C) работает корректно.
        """
        # Установка обработчика SIGINT (Ctrl+C)
        self._original_handlers[signal.SIGINT] = signal.signal(
            signal.SIGINT, self._handle_signal
        )

        # Установка обработчика SIGTERM (kill, systemd stop)
        self._original_handlers[signal.SIGTERM] = signal.signal(
            signal.SIGTERM, self._handle_signal
        )

        logger.info("Обработчики сигналов установлены (SIGINT, SIGTERM)")

    def restore_signal_handlers(self) -> None:
        """Восстанавливает оригинальные обработчики сигналов."""
        for sig, handler in self._original_handlers.items():
            if handler is not None:
                signal.signal(sig, handler)
        self._original_handlers.clear()
        logger.debug("Оригинальные обработчики сигналов восстановлены")

    def _handle_signal(self, signum: int, frame: Optional[Any]) -> None:
        """
        Обрабатывает сигнал завершения.

        При первом вызове запускает graceful shutdown.
        При повторном вызове — принудительное завершение.

        Args:
            signum: Номер сигнала
            frame: Текущий стек вызовов (не используется)
        """
        signal_name = self._get_signal_name(signum)

        with self._lock:
            if self._is_shutting_down:
                logger.warning(
                    f"Получен повторный сигнал {signal_name}. "
                    "Принудительное завершение..."
                )
                sys.exit(1)

            self._is_shutting_down = True
            logger.info(
                f"Получен сигнал {signal_name}. "
                f"Запуск graceful shutdown (таймаут: {self._timeout}с)..."
            )

        # Запуск shutdown в отдельном потоке с таймаутом
        shutdown_thread = threading.Thread(target=self.shutdown, daemon=True)
        shutdown_thread.start()
        shutdown_thread.join(timeout=self._timeout)

        if shutdown_thread.is_alive():
            logger.error(
                f"Graceful shutdown не завершился за {self._timeout}с. "
                "Принудительный выход."
            )
            sys.exit(1)

        sys.exit(0)

    def _get_signal_name(self, signum: int) -> str:
        """Возвращает имя сигнала по его номеру."""
        signal_names: dict[int, str] = {
            signal.SIGINT: "SIGINT",
            signal.SIGTERM: "SIGTERM",
        }
        return signal_names.get(signum, f"SIGNAL_{signum}")

    def shutdown(self) -> bool:
        """
        Выполняет все зарегистрированные обработчики завершения.

        Обработчики выполняются в обратном порядке регистрации (LIFO).
        Ошибки в обработчиках логируются, но не прерывают процесс.

        Note:
            Обработчики не должны модифицировать список handlers
            (регистрировать/удалять обработчики) во время выполнения shutdown.

        Returns:
            True если все обработчики выполнились без ошибок
        """
        if not self._handlers:
            logger.info("Нет зарегистрированных обработчиков для выполнения")
            return True

        logger.info(f"Выполнение {len(self._handlers)} обработчиков завершения...")

        success = True
        # Копируем список внутри lock для потокобезопасности.
        # Итерация происходит вне lock, но это безопасно т.к. мы работаем
        # с копией списка. Обработчики не должны модифицировать handlers.
        with self._lock:
            handlers = list(reversed(self._handlers))

        for i, handler in enumerate(handlers, 1):
            handler_name = (
                handler.__name__ if hasattr(handler, "__name__") else str(handler)
            )
            try:
                logger.debug(f"Выполнение обработчика {i}/{len(handlers)}: {handler_name}")
                handler()
                logger.debug(f"Обработчик {handler_name} выполнен успешно")
            except Exception as e:
                logger.error(f"Ошибка в обработчике {handler_name}: {e}")
                success = False

        if success:
            logger.info("Graceful shutdown завершён успешно")
        else:
            logger.warning("Graceful shutdown завершён с ошибками")

        return success

    def request_shutdown(self) -> bool:
        """
        Программный запрос на завершение работы.

        Может вызываться из любого места приложения для инициирования
        graceful shutdown (например, при критической ошибке).

        Returns:
            True если это первый запрос на завершение
        """
        with self._lock:
            if self._is_shutting_down:
                return False
            self._is_shutting_down = True

        logger.info("Запрошен graceful shutdown")
        return self.shutdown()

    def get_handlers_count(self) -> int:
        """Возвращает количество зарегистрированных обработчиков."""
        return len(self._handlers)


# Глобальный экземпляр для удобства
_shutdown_manager: Optional[GracefulShutdown] = None


def get_shutdown_manager() -> GracefulShutdown:
    """
    Возвращает глобальный менеджер завершения работы.

    Создаёт менеджер при первом вызове с настройками по умолчанию.

    Returns:
        Глобальный экземпляр GracefulShutdown
    """
    global _shutdown_manager
    if _shutdown_manager is None:
        _shutdown_manager = GracefulShutdown()
    return _shutdown_manager


def reset_shutdown_manager() -> None:
    """Сбрасывает глобальный менеджер завершения работы."""
    global _shutdown_manager
    if _shutdown_manager is not None:
        _shutdown_manager.clear_handlers()
        try:
            _shutdown_manager.restore_signal_handlers()
        except Exception as e:
            logger.debug(f"Ошибка при восстановлении обработчиков: {e}")
    _shutdown_manager = None


def register_shutdown_handler(handler: Callable[[], None]) -> None:
    """
    Регистрирует обработчик в глобальном менеджере.

    Удобная функция для быстрой регистрации без получения менеджера.

    Args:
        handler: Функция без аргументов
    """
    get_shutdown_manager().register_handler(handler)


def request_shutdown() -> bool:
    """
    Запрашивает graceful shutdown через глобальный менеджер.

    Returns:
        True если это первый запрос на завершение
    """
    return get_shutdown_manager().request_shutdown()
