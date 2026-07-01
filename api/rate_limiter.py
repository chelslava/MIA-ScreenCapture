"""
Модуль ограничения частоты запросов (Rate Limiting)
====================================================

Реализует ограничение частоты API запросов для защиты от злоупотреблений.
"""

import re
import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from threading import Lock
from typing import Any

from flask import Flask, current_app, jsonify, request

from logger_config import get_module_logger

logger = get_module_logger(__name__)

# Паттерн для валидации IPv4 адреса
IPV4_PATTERN = re.compile(
    r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
)

# Паттерн для валидации IPv6 адреса (упрощённый)
IPV6_PATTERN = re.compile(
    r"^(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}$|"
    r"^(?:[0-9a-fA-F]{1,4}:){1,7}:$|"
    r"^(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}$|"
    r"^::(?:[0-9a-fA-F]{1,4}:){0,5}[0-9a-fA-F]{1,4}$|"
    r"^(?:[0-9a-fA-F]{1,4}:){1,5}:(?::[0-9a-fA-F]{1,4}){1,2}$|"
    r"^(?:[0-9a-fA-F]{1,4}:){1,4}:(?::[0-9a-fA-F]{1,4}){1,3}$|"
    r"^(?:[0-9a-fA-F]{1,4}:){1,3}:(?::[0-9a-fA-F]{1,4}){1,4}$|"
    r"^(?:[0-9a-fA-F]{1,4}:){1,2}:(?::[0-9a-fA-F]{1,4}){1,5}$|"
    r"^[0-9a-fA-F]{1,4}:(?::[0-9a-fA-F]{1,4}){1,6}$|"
    r"^:(?::[0-9a-fA-F]{1,4}){1,7}$|"
    r"^::(?:[fF]{2}:)?(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\."
    r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\."
    r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\."
    r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
)


def _is_valid_ip(ip_str: str) -> bool:
    """Проверка валидности IP-адреса."""
    if not ip_str:
        return False
    return bool(IPV4_PATTERN.match(ip_str) or IPV6_PATTERN.match(ip_str))


@dataclass
class RateLimitConfig:
    """Конфигурация ограничения частоты запросов."""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10  # Максимум запросов за 1 секунду
    # Длительность блокировки в секундах при превышении burst
    block_duration: int = 10
    enabled: bool = True
    # IP-адреса без ограничений
    whitelist: list[str] = field(default_factory=list)
    # Доверять X-Forwarded-For/X-Real-IP только за доверенным reverse-proxy
    trust_proxy_headers: bool = False


@dataclass
class ClientState:
    """Состояние клиента для отслеживания запросов."""

    minute_count: int = 0
    hour_count: int = 0
    burst_count: int = 0
    last_minute_reset: float = 0.0
    last_hour_reset: float = 0.0
    last_burst_reset: float = 0.0
    blocked_until: float = 0.0
    last_activity: float = 0.0  # Время последней активности


# Время жизни неактивного клиента (2 часа)
CLIENT_TTL_SECONDS = 7200


class InMemoryRateLimiter:
    """
    Потокобезопасный ограничитель частоты запросов в памяти.

    Поддерживает три типа ограничений:
    - Burst: кратковременные всплески (в секунду)
    - Minute: среднесрочные (в минуту)
    - Hour: долгосрочные (в час)
    """

    def __init__(self, config: RateLimitConfig | None = None):
        """
        Инициализация ограничителя.

        Args:
            config: Конфигурация ограничений
        """
        self.config = config or RateLimitConfig()
        self._clients: dict[str, ClientState] = defaultdict(ClientState)
        self._lock = Lock()
        self._last_cleanup = time.monotonic()

    def _get_client_ip(self) -> str:
        """Получение IP-адреса клиента с валидацией."""
        # Без доверенного reverse-proxy заголовки клиента не заслуживают
        # доверия — любой клиент может подставить в них чужой IP и обойти
        # per-IP лимиты (см. issue #74).
        if not self.config.trust_proxy_headers:
            return request.remote_addr or "unknown"

        # Проверка заголовков прокси с валидацией
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Берём первый IP из списка
            ip_candidate = str(forwarded).split(",")[0].strip()
            if _is_valid_ip(ip_candidate):
                return ip_candidate
            logger.warning(
                f"Invalid IP in X-Forwarded-For: {ip_candidate[:50]}"
            )

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            ip_candidate = str(real_ip).strip()
            if _is_valid_ip(ip_candidate):
                return ip_candidate
            logger.warning(f"Invalid IP in X-Real-IP: {ip_candidate[:50]}")

        # Fallback к remote_addr
        return request.remote_addr or "unknown"

    def _is_whitelisted(self, client_ip: str) -> bool:
        """Проверка, находится ли IP в белом списке."""
        return client_ip in self.config.whitelist

    def _reset_counters_if_needed(self, state: ClientState) -> None:
        """Сброс счётчиков при истечении временных окон."""
        current_time = time.monotonic()

        # Сброс burst счётчика (1 секунда)
        if current_time - state.last_burst_reset >= 1.0:
            state.burst_count = 0
            state.last_burst_reset = current_time

        # Сброс минутного счётчика
        if current_time - state.last_minute_reset >= 60.0:
            state.minute_count = 0
            state.last_minute_reset = current_time

        # Сброс часового счётчика
        if current_time - state.last_hour_reset >= 3600.0:
            state.hour_count = 0
            state.last_hour_reset = current_time

    def _cleanup_inactive_clients(self) -> int:
        """
        Удаление неактивных клиентов для предотвращения memory leak.

        Returns:
            Количество удалённых клиентов
        """
        current_time = time.monotonic()
        removed = 0

        # Периодическая очистка (раз в 10 минут)
        if current_time - self._last_cleanup < 600:
            return 0

        self._last_cleanup = current_time

        # Удаление клиентов без активности более CLIENT_TTL_SECONDS
        inactive_ips = [
            ip
            for ip, state in self._clients.items()
            if current_time - state.last_activity > CLIENT_TTL_SECONDS
        ]

        for ip in inactive_ips:
            del self._clients[ip]
            removed += 1

        if removed > 0:
            logger.info(f"Cleaned up {removed} inactive rate limit clients")

        return removed

    def check_rate_limit(self) -> tuple[bool, dict | None]:
        """
        Проверка ограничения частоты для текущего запроса.

        Returns:
            Кортеж (разрешён ли запрос, информация об ограничении)
        """
        if not self.config.enabled:
            return True, None

        client_ip = self._get_client_ip()

        # Белый список не ограничивается
        if self._is_whitelisted(client_ip):
            return True, None

        with self._lock:
            # Периодическая очистка неактивных клиентов
            self._cleanup_inactive_clients()

            state = self._clients[client_ip]
            current_time = time.monotonic()

            # Обновление времени последней активности
            state.last_activity = current_time

            # Проверка блокировки
            if current_time < state.blocked_until:
                remaining = int(state.blocked_until - current_time)
                return False, {
                    "error": "Too Many Requests",
                    "retry_after": remaining,
                    "limit_type": "blocked",
                }

            # Сброс счётчиков
            self._reset_counters_if_needed(state)

            # Проверка burst лимита
            if state.burst_count >= self.config.burst_limit:
                block_duration = self.config.block_duration
                state.blocked_until = current_time + block_duration
                logger.warning(
                    f"Burst rate limit exceeded for {client_ip}: "
                    f"{state.burst_count} requests/second"
                )
                return False, {
                    "error": "Too Many Requests",
                    "retry_after": block_duration,
                    "limit_type": "burst",
                    "limit": self.config.burst_limit,
                    "window": "1 second",
                }

            # Проверка минутного лимита
            if state.minute_count >= self.config.requests_per_minute:
                remaining = 60 - int(current_time - state.last_minute_reset)
                logger.warning(
                    f"Minute rate limit exceeded for {client_ip}: "
                    f"{state.minute_count} requests/minute"
                )
                return False, {
                    "error": "Too Many Requests",
                    "retry_after": remaining,
                    "limit_type": "minute",
                    "limit": self.config.requests_per_minute,
                    "window": "1 minute",
                }

            # Проверка часового лимита
            if state.hour_count >= self.config.requests_per_hour:
                remaining = 3600 - int(current_time - state.last_hour_reset)
                logger.warning(
                    f"Hourly rate limit exceeded for {client_ip}: "
                    f"{state.hour_count} requests/hour"
                )
                return False, {
                    "error": "Too Many Requests",
                    "retry_after": remaining,
                    "limit_type": "hour",
                    "limit": self.config.requests_per_hour,
                    "window": "1 hour",
                }

            # Увеличение счётчиков
            state.burst_count += 1
            state.minute_count += 1
            state.hour_count += 1

            return True, None

    def get_client_stats(self, client_ip: str | None = None) -> dict:
        """
        Получение статистики запросов клиента.

        Args:
            client_ip: IP-адрес клиента (текущий если не указан)

        Returns:
            Словарь со статистикой
        """
        if client_ip is None:
            client_ip = self._get_client_ip()

        with self._lock:
            state = self._clients.get(client_ip)
            if state is None:
                return {
                    "ip": client_ip,
                    "minute_count": 0,
                    "hour_count": 0,
                    "burst_count": 0,
                    "is_blocked": False,
                }

            return {
                "ip": client_ip,
                "minute_count": state.minute_count,
                "hour_count": state.hour_count,
                "burst_count": state.burst_count,
                "is_blocked": time.monotonic() < state.blocked_until,
                "minute_remaining": (
                    self.config.requests_per_minute - state.minute_count
                ),
                "hour_remaining": (
                    self.config.requests_per_hour - state.hour_count
                ),
            }

    def reset_client(self, client_ip: str) -> None:
        """
        Сброс ограничений для конкретного клиента.

        Args:
            client_ip: IP-адрес клиента
        """
        with self._lock:
            if client_ip in self._clients:
                del self._clients[client_ip]
                logger.info(f"Rate limit reset for {client_ip}")

    def clear_all(self) -> None:
        """Очистка всех данных о клиентах."""
        with self._lock:
            self._clients.clear()
            logger.info("All rate limit data cleared")


# Глобальный экземпляр ограничителя
_rate_limiter: InMemoryRateLimiter | None = None


def get_rate_limiter() -> InMemoryRateLimiter:
    """Получение глобального экземпляра ограничителя."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = InMemoryRateLimiter()
    return _rate_limiter


def init_rate_limiter(
    app: Flask, config: RateLimitConfig | None = None
) -> None:
    """
    Инициализация ограничителя для Flask приложения.

    Args:
        app: Flask приложение
        config: Конфигурация ограничений
    """
    global _rate_limiter
    # Создаём конфигурацию по умолчанию если не передана
    actual_config = config or RateLimitConfig()
    _rate_limiter = InMemoryRateLimiter(actual_config)

    # Сохранение в конфигурации приложения
    app.config["RATE_LIMITER"] = _rate_limiter
    app.config["RATE_LIMIT_CONFIG"] = actual_config

    logger.info(
        f"Rate limiter initialized: "
        f"{actual_config.requests_per_minute}/min, "
        f"{actual_config.requests_per_hour}/hour"
    )


def rate_limit(f: Callable) -> Callable:
    """
    Декоратор для применения ограничения частоты запросов.

    Использование:
        @app.route('/api/endpoint')
        @rate_limit
        def endpoint():
            return {'data': 'value'}
    """

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        limiter = get_rate_limiter()
        allowed, info = limiter.check_rate_limit()

        if not allowed:
            # info гарантированно не None при allowed=False
            rate_info = info or {}
            response = jsonify(
                {
                    "success": False,
                    "error": rate_info.get("error", "Too Many Requests"),
                    "rate_limit": {
                        "limit_type": rate_info.get("limit_type"),
                        "limit": rate_info.get("limit"),
                        "window": rate_info.get("window"),
                        "retry_after": rate_info.get("retry_after"),
                    },
                }
            )
            response.status_code = 429
            response.headers["Retry-After"] = str(
                rate_info.get("retry_after", 60)
            )
            response.headers["X-RateLimit-Limit"] = str(
                rate_info.get("limit", 0)
            )
            return response

        # Выполняем функцию и добавляем заголовки с информацией о лимитах
        response = f(*args, **kwargs)
        headers = get_rate_limit_headers()
        if isinstance(response, tuple):
            normalized_response = current_app.make_response(response)
            normalized_response.headers.update(headers)
            return normalized_response
        if hasattr(response, "headers"):
            response.headers.update(headers)
        return response

    return decorated


def get_rate_limit_headers() -> dict[str, str]:
    """Получение заголовков с информацией о лимитах для текущего клиента."""
    limiter = get_rate_limiter()
    stats = limiter.get_client_stats()

    return {
        "X-RateLimit-Limit-Minute": str(limiter.config.requests_per_minute),
        "X-RateLimit-Limit-Hour": str(limiter.config.requests_per_hour),
        "X-RateLimit-Remaining-Minute": str(stats.get("minute_remaining", 0)),
        "X-RateLimit-Remaining-Hour": str(stats.get("hour_remaining", 0)),
    }


def get_rate_limiter_compat() -> InMemoryRateLimiter:
    return get_rate_limiter()
