"""
Тесты модуля ограничения частоты запросов
=========================================
"""

from unittest.mock import patch

import pytest
from flask import Flask

from api.rate_limiter import (
    ClientState,
    InMemoryRateLimiter,
    RateLimitConfig,
    get_rate_limiter,
    init_rate_limiter,
    rate_limit,
)


class TestRateLimitConfig:
    """Тесты конфигурации rate limiter."""

    def test_default_values(self):
        """Тест значений по умолчанию."""
        config = RateLimitConfig()
        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 1000
        assert config.burst_limit == 10
        assert config.block_duration == 10
        assert config.enabled is True
        assert config.whitelist == []

    def test_custom_values(self):
        """Тест пользовательских значений."""
        config = RateLimitConfig(
            requests_per_minute=100,
            requests_per_hour=500,
            burst_limit=5,
            block_duration=30,
            enabled=False,
            whitelist=["127.0.0.1"],
        )
        assert config.requests_per_minute == 100
        assert config.requests_per_hour == 500
        assert config.burst_limit == 5
        assert config.block_duration == 30
        assert config.enabled is False
        assert "127.0.0.1" in config.whitelist


class TestClientState:
    """Тесты состояния клиента."""

    def test_default_values(self):
        """Тест значений по умолчанию."""
        state = ClientState()
        assert state.minute_count == 0
        assert state.hour_count == 0
        assert state.burst_count == 0
        assert state.last_minute_reset == 0.0
        assert state.last_hour_reset == 0.0
        assert state.last_burst_reset == 0.0
        assert state.blocked_until == 0.0


class TestInMemoryRateLimiter:
    """Тесты ограничителя частоты запросов."""

    @pytest.fixture
    def app(self):
        """Создание тестового Flask приложения."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        return app

    def test_init_default_config(self):
        """Тест инициализации с конфигурацией по умолчанию."""
        limiter = InMemoryRateLimiter()
        assert limiter.config.requests_per_minute == 60
        assert limiter.config.enabled is True

    def test_init_custom_config(self):
        """Тест инициализации с пользовательской конфигурацией."""
        config = RateLimitConfig(requests_per_minute=100)
        limiter = InMemoryRateLimiter(config)
        assert limiter.config.requests_per_minute == 100

    def test_disabled_limiter_allows_all(self, app):
        """Тест отключённого ограничителя."""
        config = RateLimitConfig(enabled=False)
        limiter = InMemoryRateLimiter(config)

        with app.test_request_context():
            # Все запросы должны быть разрешены
            for _ in range(100):
                allowed, info = limiter.check_rate_limit()
                assert allowed is True
                assert info is None

    def test_whitelist_bypasses_limit(self, app):
        """Тест обхода ограничений для белого списка."""
        config = RateLimitConfig(
            requests_per_minute=5, whitelist=["192.168.1.1"]
        )
        limiter = InMemoryRateLimiter(config)

        with app.test_request_context():
            # Эмулируем IP из белого списка
            with patch.object(
                limiter, "_get_client_ip", return_value="192.168.1.1"
            ):
                # Запросы из белого списка не ограничиваются
                for _ in range(100):
                    allowed, info = limiter.check_rate_limit()
                    assert allowed is True
                    assert info is None

    def test_burst_limit_enforcement(self, app):
        """Тест ограничения всплесков."""
        config = RateLimitConfig(burst_limit=3, requests_per_minute=1000)
        limiter = InMemoryRateLimiter(config)

        with app.test_request_context(), patch.object(
            limiter, "_get_client_ip", return_value="10.0.0.1"
        ):
            # Первые 3 запроса должны быть разрешены
            for _ in range(3):
                allowed, info = limiter.check_rate_limit()
                assert allowed is True

            # 4-й запрос должен быть отклонён
            allowed, info = limiter.check_rate_limit()
            assert allowed is False
            assert info is not None
            assert info["limit_type"] == "burst"
            assert info["limit"] == 3

    def test_minute_limit_enforcement(self, app):
        """Тест минутного ограничения."""
        config = RateLimitConfig(
            requests_per_minute=5, burst_limit=100
        )
        limiter = InMemoryRateLimiter(config)

        with app.test_request_context(), patch.object(
            limiter, "_get_client_ip", return_value="10.0.0.2"
        ):
            # Первые 5 запросов должны быть разрешены
            for _ in range(5):
                allowed, info = limiter.check_rate_limit()
                assert allowed is True

            # 6-й запрос должен быть отклонён
            allowed, info = limiter.check_rate_limit()
            assert allowed is False
            assert info is not None
            assert info["limit_type"] == "minute"
            assert info["limit"] == 5

    def test_hour_limit_enforcement(self, app):
        """Тест часового ограничения."""
        config = RateLimitConfig(
            requests_per_minute=1000,
            requests_per_hour=3,
            burst_limit=100,
        )
        limiter = InMemoryRateLimiter(config)

        with app.test_request_context(), patch.object(
            limiter, "_get_client_ip", return_value="10.0.0.3"
        ):
            # Первые 3 запроса должны быть разрешены
            for _ in range(3):
                allowed, info = limiter.check_rate_limit()
                assert allowed is True

            # 4-й запрос должен быть отклонён
            allowed, info = limiter.check_rate_limit()
            assert allowed is False
            assert info is not None
            assert info["limit_type"] == "hour"
            assert info["limit"] == 3

    def test_get_client_stats(self, app):
        """Тест получения статистики клиента."""
        limiter = InMemoryRateLimiter()

        with app.test_request_context(), patch.object(
            limiter, "_get_client_ip", return_value="10.0.0.4"
        ):
            # Выполнение нескольких запросов
            for _ in range(5):
                limiter.check_rate_limit()

            stats = limiter.get_client_stats()
            assert stats["ip"] == "10.0.0.4"
            assert stats["minute_count"] == 5
            assert stats["hour_count"] == 5
            assert stats["is_blocked"] is False

    def test_reset_client(self, app):
        """Тест сброса ограничений клиента."""
        config = RateLimitConfig(requests_per_minute=2)
        limiter = InMemoryRateLimiter(config)

        with app.test_request_context(), patch.object(
            limiter, "_get_client_ip", return_value="10.0.0.5"
        ):
            # Выполнение запросов до лимита
            limiter.check_rate_limit()
            limiter.check_rate_limit()
            allowed, _ = limiter.check_rate_limit()
            assert allowed is False

            # Сброс ограничений
            limiter.reset_client("10.0.0.5")

            # Теперь запросы должны быть разрешены
            allowed, _ = limiter.check_rate_limit()
            assert allowed is True

    def test_clear_all(self, app):
        """Тест очистки всех данных."""
        config = RateLimitConfig(requests_per_minute=2)
        limiter = InMemoryRateLimiter(config)

        with app.test_request_context():
            # Добавление данных для нескольких клиентов
            for i in range(3):
                with patch.object(
                    limiter, "_get_client_ip", return_value=f"10.0.0.{i}"
                ):
                    limiter.check_rate_limit()
                    limiter.check_rate_limit()

            # Очистка всех данных
            limiter.clear_all()

            # Проверка, что данные очищены
            with patch.object(
                limiter, "_get_client_ip", return_value="10.0.0.0"
            ):
                allowed, _ = limiter.check_rate_limit()
                assert allowed is True

    def test_x_forwarded_for_header(self, app):
        """Тест обработки заголовка X-Forwarded-For."""
        limiter = InMemoryRateLimiter()

        with app.test_request_context(
            headers={"X-Forwarded-For": "203.0.113.1, 70.41.3.18"}
        ):
            ip = limiter._get_client_ip()
            assert ip == "203.0.113.1"

    def test_x_real_ip_header(self, app):
        """Тест обработки заголовка X-Real-IP."""
        limiter = InMemoryRateLimiter()

        with app.test_request_context(headers={"X-Real-IP": "198.51.100.1"}):
            ip = limiter._get_client_ip()
            assert ip == "198.51.100.1"

    def test_blocked_client(self, app):
        """Тест блокировки клиента."""
        config = RateLimitConfig(burst_limit=2)
        limiter = InMemoryRateLimiter(config)

        with app.test_request_context(), patch.object(
            limiter, "_get_client_ip", return_value="10.0.0.6"
        ):
            # Превышение burst лимита
            limiter.check_rate_limit()
            limiter.check_rate_limit()
            allowed, info = limiter.check_rate_limit()
            assert allowed is False
            assert info["limit_type"] == "burst"

            # Последующие запросы также должны быть заблокированы
            allowed, info = limiter.check_rate_limit()
            assert allowed is False
            assert info["limit_type"] == "blocked"


class TestRateLimitDecorator:
    """Тесты декоратора rate_limit."""

    @pytest.fixture
    def app(self):
        """Создание тестового Flask приложения."""
        app = Flask(__name__)
        app.config["TESTING"] = True
        return app

    def test_allows_request(self, app):
        """Тест разрешения запроса."""
        limiter = InMemoryRateLimiter()

        @rate_limit
        def test_endpoint():
            return {"success": True}

        with app.test_request_context(), patch(
            "api.rate_limiter.get_rate_limiter", return_value=limiter
        ), patch.object(
            limiter, "_get_client_ip", return_value="10.0.0.7"
        ):
            result = test_endpoint()
            assert result == {"success": True}

    def test_blocks_request(self, app):
        """Тест блокировки запроса."""
        config = RateLimitConfig(requests_per_minute=1)
        limiter = InMemoryRateLimiter(config)

        @rate_limit
        def test_endpoint():
            return {"success": True}

        with app.test_request_context(), patch(
            "api.rate_limiter.get_rate_limiter", return_value=limiter
        ), patch.object(
            limiter, "_get_client_ip", return_value="10.0.0.8"
        ):
            # Первый запрос разрешён
            result = test_endpoint()
            assert result == {"success": True}

            # Второй запрос заблокирован
            result = test_endpoint()
            assert result.status_code == 429


class TestInitRateLimiter:
    """Тесты инициализации rate limiter."""

    def test_init_with_app(self):
        """Тест инициализации с Flask приложением."""
        app = Flask(__name__)
        config = RateLimitConfig(requests_per_minute=100)
        init_rate_limiter(app, config)

        assert "RATE_LIMITER" in app.config
        assert "RATE_LIMIT_CONFIG" in app.config
        assert app.config["RATE_LIMIT_CONFIG"].requests_per_minute == 100

    def test_init_without_config(self):
        """Тест инициализации без конфигурации."""
        app = Flask(__name__)
        init_rate_limiter(app)

        assert "RATE_LIMITER" in app.config
        assert "RATE_LIMIT_CONFIG" in app.config


class TestGetRateLimiter:
    """Тесты получения глобального ограничителя."""

    def test_get_rate_limiter_singleton(self):
        """Тест получения singleton ограничителя."""
        import api.rate_limiter as rl_module

        # Сброс глобального экземпляра
        rl_module._rate_limiter = None

        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()

        assert limiter1 is limiter2
