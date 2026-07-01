"""
Модуль ограничения частоты запросов для аутентификации
=====================================================

Предотвращает перебор API-ключей с экспоненциальной задержкой.
"""

import threading
import time
from dataclasses import dataclass
from logging import Logger
from typing import Any

from core.event_bus import EventBus, RecordingEvent, RecordingEventType
from logger_config import get_module_logger

logger: Logger = get_module_logger(__name__)


@dataclass
class AuthRateLimitConfig:
    """Конфигурация ограничения аутентификации."""

    max_attempts: int = 5
    base_delay: int = 60
    enabled: bool = True


class AuthRateLimiter:
    """Ограничитель частоты запросов для неудачных аутентификаций."""

    def __init__(
        self,
        config: AuthRateLimitConfig | None = None,
        event_bus: EventBus | None = None,
        max_attempts: int | None = None,
        base_delay: int | None = None,
    ):
        """
        Инициализация ограничителя.

        Args:
            config: Конфигурация ограничений (если None, создаётся с параметрами)
            event_bus: Event bus для публикации событий блокировок
            max_attempts: Максимальное число неудачных попыток
            base_delay: Базовая задержка при блокировке (сек)
        """
        if config is None:
            if max_attempts is not None or base_delay is not None:
                config = AuthRateLimitConfig(
                    max_attempts=max_attempts or 5,
                    base_delay=base_delay or 60,
                )
            else:
                config = AuthRateLimitConfig()
        self.config = config
        self._event_bus = event_bus

        self._attempts: dict[str, int] = {}
        self._blocked_until: dict[str, float] = {}
        self._lock = threading.Lock()

    def record_failed_attempt(self, client_ip: str) -> tuple[bool, int]:
        """
        Записывает неудачную попытку аутентификации.

        Args:
            client_ip: IP-адрес клиента

        Returns:
            Кортеж (blocked, remaining_delay)
        """
        if not self.config.enabled:
            return False, 0

        with self._lock:
            current_time = time.monotonic()

            if client_ip in self._blocked_until:
                if current_time < self._blocked_until[client_ip]:
                    remaining = int(
                        self._blocked_until[client_ip] - current_time
                    )
                    return True, remaining

                self._blocked_until.pop(client_ip, None)
                self._attempts.pop(client_ip, None)

            self._attempts[client_ip] = self._attempts.get(client_ip, 0) + 1
            attempts = self._attempts[client_ip]

            logger.warning(
                f"Неудачная попытка аутентификации: IP={client_ip}, "
                f"попытка {attempts}/{self.config.max_attempts}"
            )

            if attempts >= self.config.max_attempts:
                exponent = max(0, attempts - self.config.max_attempts)
                delay = self.config.base_delay * (2**exponent)

                self._blocked_until[client_ip] = current_time + delay

                logger.warning(
                    f"IP заблокирован после {attempts} неудачных попыток: "
                    f"{client_ip}, задержка {delay} сек"
                )

                self._publish_lockout_event(client_ip, delay)

                return True, delay

            return False, 0

    def _publish_lockout_event(self, client_ip: str, delay: int) -> None:
        """
        Публикует событие блокировки через event bus.

        Args:
            client_ip: IP-адрес клиента
            delay: Время блокировки в секундах
        """
        if not self._event_bus:
            return

        event = RecordingEvent(
            event_type=RecordingEventType.ERROR,
            payload={
                "type": "auth_lockout",
                "client_ip": client_ip,
                "duration": delay,
            },
        )
        self._event_bus.publish(event)

    def is_blocked(self, client_ip: str) -> bool:
        """
        Проверяет, заблокирован ли клиент.

        Args:
            client_ip: IP-адрес клиента

        Returns:
            True если заблокирован
        """
        if not self.config.enabled:
            return False

        with self._lock:
            current_time = time.monotonic()

            if client_ip in self._blocked_until:
                if current_time < self._blocked_until[client_ip]:
                    return True
                self._blocked_until.pop(client_ip, None)
                self._attempts.pop(client_ip, None)

            return False

    def record_success(self, client_ip: str) -> None:
        """
        Сбрасывает счётчик неудач после успешной аутентификации.

        Args:
            client_ip: IP-адрес клиента
        """
        with self._lock:
            self._attempts.pop(client_ip, None)
            self._blocked_until.pop(client_ip, None)

    def check_and_increment(self, client_ip: str) -> tuple[bool, str | None]:
        """
        Проверяет блокировку и инкрементирует счётчик.

        Args:
            client_ip: IP-адрес клиента

        Returns:
            Кортеж (allowed, blocking_reason)
        """
        if self.is_blocked(client_ip):
            with self._lock:
                current_time = time.monotonic()
                if client_ip in self._blocked_until:
                    remaining = int(
                        self._blocked_until[client_ip] - current_time
                    )
                    return False, (
                        f"Слишком много неудачных попыток. "
                        f"Повторите через {remaining} сек"
                    )

            return False, "Слишком много неудачных попыток аутентификации"

        return True, None

    def reset_client(self, client_ip: str) -> None:
        """
        Сбрасывает ограничения для клиента.

        Args:
            client_ip: IP-адрес клиента
        """
        with self._lock:
            self._attempts.pop(client_ip, None)
            self._blocked_until.pop(client_ip, None)
            logger.info(f"Auth rate limit reset for {client_ip}")

    def clear_all(self) -> None:
        """Очищает все данные о клиентах."""
        with self._lock:
            self._attempts.clear()
            self._blocked_until.clear()
            logger.info("All auth rate limit data cleared")

    def get_client_stats(self, client_ip: str) -> dict[str, Any]:
        """
        Получает статистику клиента.

        Args:
            client_ip: IP-адрес клиента

        Returns:
            Словарь со статистикой
        """
        with self._lock:
            current_time = time.monotonic()
            attempts = self._attempts.get(client_ip, 0)
            is_blocked = False
            remaining = 0

            if client_ip in self._blocked_until:
                if current_time < self._blocked_until[client_ip]:
                    is_blocked = True
                    remaining = int(
                        self._blocked_until[client_ip] - current_time
                    )

            return {
                "ip": client_ip,
                "failed_attempts": attempts,
                "is_blocked": is_blocked,
                "remaining_delay": remaining,
                "max_attempts": self.config.max_attempts,
                "base_delay": self.config.base_delay,
            }

    def get_global_stats(self) -> dict[str, Any]:
        """
        Получает глобальную статистику.

        Returns:
            Словарь со статистикой
        """
        with self._lock:
            current_time = time.monotonic()

            blocked_ips = [
                ip
                for ip, until in self._blocked_until.items()
                if current_time < until
            ]

            return {
                "total_tracked_ips": len(self._attempts),
                "blocked_ips_count": len(blocked_ips),
                "blocked_ips": blocked_ips[:10],
                "config": {
                    "max_attempts": self.config.max_attempts,
                    "base_delay": self.config.base_delay,
                    "enabled": self.config.enabled,
                },
            }


# Глобальный экземпляр ограничителя
_auth_limiter: AuthRateLimiter | None = None


def get_auth_rate_limiter() -> AuthRateLimiter:
    """Получение глобального экземпляра ограничителя."""
    global _auth_limiter
    if _auth_limiter is None:
        _auth_limiter = AuthRateLimiter()
    return _auth_limiter


def init_auth_rate_limiter(
    app: Any,
    config: AuthRateLimitConfig | None = None,
    event_bus: EventBus | None = None,
) -> None:
    """
    Инициализация ограничителя для Flask приложения.

    Args:
        app: Flask приложение
        config: Конфигурация ограничений
        event_bus: Event bus для публикации событий
    """
    global _auth_limiter

    actual_config = config or AuthRateLimitConfig()
    _auth_limiter = AuthRateLimiter(actual_config, event_bus)

    app.config["AUTH_RATE_LIMITER"] = _auth_limiter
    app.config["AUTH_RATE_LIMIT_CONFIG"] = actual_config

    app._auth_rate_limiter = _auth_limiter

    logger.info(
        f"Auth rate limiter initialized: "
        f"{actual_config.max_attempts} attempts, "
        f"base delay {actual_config.base_delay} sec"
    )
