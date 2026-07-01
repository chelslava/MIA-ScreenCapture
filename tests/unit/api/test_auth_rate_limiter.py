import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from api.auth_rate_limiter import (
    AuthRateLimitConfig,
    AuthRateLimiter,
    get_auth_rate_limiter,
    init_auth_rate_limiter,
)


class TestAuthRateLimitConfig:
    def test_default_values(self):
        config = AuthRateLimitConfig()
        assert config.max_attempts == 5
        assert config.base_delay == 60
        assert config.enabled is True

    def test_custom_values(self):
        config = AuthRateLimitConfig(
            max_attempts=10,
            base_delay=120,
            enabled=False,
        )
        assert config.max_attempts == 10
        assert config.base_delay == 120
        assert config.enabled is False


class TestAuthRateLimiter:
    def test_init_default_config(self):
        limiter = AuthRateLimiter()
        assert limiter.config.max_attempts == 5
        assert limiter.config.base_delay == 60
        assert limiter.config.enabled is True

    def test_init_custom_config(self):
        config = AuthRateLimitConfig(
            max_attempts=3,
            base_delay=30,
        )
        limiter = AuthRateLimiter(config=config)
        assert limiter.config.max_attempts == 3
        assert limiter.config.base_delay == 30

    def test_record_failed_attempt_increments_counter(self):
        limiter = AuthRateLimiter(max_attempts=3)
        current_time = time.monotonic()

        with patch("time.monotonic", return_value=current_time):
            is_blocked, delay = limiter.record_failed_attempt("192.168.1.1")

        assert is_blocked is False
        assert delay == 0
        assert limiter._attempts["192.168.1.1"] == 1

    def test_record_multiple_failed_attempts(self):
        limiter = AuthRateLimiter(max_attempts=3)

        current_time = time.monotonic()

        with patch("time.monotonic", return_value=current_time):
            for i in range(3):
                limiter.record_failed_attempt("192.168.1.1")

        assert limiter._attempts["192.168.1.1"] == 3

    def test_is_blocked_after_max_attempts(self):
        limiter = AuthRateLimiter(max_attempts=3)

        current_time = time.monotonic()

        with patch("time.monotonic", return_value=current_time):
            for _ in range(3):
                limiter.record_failed_attempt("192.168.1.1")

        is_blocked = limiter.is_blocked("192.168.1.1")
        assert is_blocked is True

    def test_exponential_backoff_calculation(self):
        limiter = AuthRateLimiter(max_attempts=3, base_delay=60)

        current_time = time.monotonic()

        with patch("time.monotonic", return_value=current_time):
            for _ in range(3):
                limiter.record_failed_attempt("192.168.1.1")

        blocked_until = limiter._blocked_until["192.168.1.1"]
        expected_delay = 60
        assert blocked_until == pytest.approx(
            current_time + expected_delay, abs=1
        )

    def test_record_success_resets_counter(self):
        limiter = AuthRateLimiter(max_attempts=3)

        current_time = time.monotonic()

        with patch("time.monotonic", return_value=current_time):
            for _ in range(3):
                limiter.record_failed_attempt("192.168.1.1")

        limiter.record_success("192.168.1.1")

        assert "192.168.1.1" not in limiter._attempts
        is_blocked = limiter.is_blocked("192.168.1.1")
        assert is_blocked is False

    def test_check_and_increment_allowed(self):
        limiter = AuthRateLimiter(max_attempts=3)

        allowed, blocking_reason = limiter.check_and_increment("192.168.1.1")

        assert allowed is True
        assert blocking_reason is None

    def test_check_and_increment_blocked(self):
        limiter = AuthRateLimiter(max_attempts=3)

        current_time = time.monotonic()

        with patch("time.monotonic", return_value=current_time):
            for _ in range(5):
                limiter.record_failed_attempt("192.168.1.1")

        allowed, blocking_reason = limiter.check_and_increment("192.168.1.1")

        assert allowed is False
        assert blocking_reason is not None
        assert "слишком много" in blocking_reason.lower()

    def test_thread_safety(self):
        limiter = AuthRateLimiter(max_attempts=100)

        def record_attempts(ip, count):
            for _ in range(count):
                limiter.record_failed_attempt(ip)

        threads = []
        for i in range(10):
            ip = f"192.168.1.{i}"
            t = threading.Thread(target=record_attempts, args=(ip, 10))
            threads.append(t)

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        for i in range(10):
            ip = f"192.168.1.{i}"
            assert limiter._attempts[ip] == 10

    def test_reset_client(self):
        limiter = AuthRateLimiter(max_attempts=3)

        current_time = time.monotonic()

        with patch("time.monotonic", return_value=current_time):
            for _ in range(5):
                limiter.record_failed_attempt("192.168.1.1")

        limiter.reset_client("192.168.1.1")

        assert "192.168.1.1" not in limiter._attempts
        assert "192.168.1.1" not in limiter._blocked_until

    def test_clear_all(self):
        limiter = AuthRateLimiter(max_attempts=3)

        current_time = time.monotonic()

        for i in range(3):
            ip = f"192.168.1.{i}"
            with patch("time.monotonic", return_value=current_time):
                for _ in range(5):
                    limiter.record_failed_attempt(ip)

        limiter.clear_all()

        assert len(limiter._attempts) == 0
        assert len(limiter._blocked_until) == 0

    def test_get_client_stats(self):
        limiter = AuthRateLimiter(max_attempts=3)

        current_time = time.monotonic()

        with patch("time.monotonic", return_value=current_time):
            limiter.record_failed_attempt("192.168.1.1")
            limiter.record_failed_attempt("192.168.1.1")
            limiter.record_failed_attempt("192.168.1.1")

        stats = limiter.get_client_stats("192.168.1.1")

        assert stats["ip"] == "192.168.1.1"
        assert stats["failed_attempts"] == 3
        assert stats["is_blocked"] is True
        assert stats["remaining_delay"] > 0
        assert stats["max_attempts"] == 3
        assert stats["base_delay"] == 60

    def test_get_global_stats(self):
        limiter = AuthRateLimiter(max_attempts=3)

        current_time = time.monotonic()

        for i in range(3):
            ip = f"192.168.1.{i}"
            with patch("time.monotonic", return_value=current_time):
                for _ in range(5):
                    limiter.record_failed_attempt(ip)

        stats = limiter.get_global_stats()

        assert stats["total_tracked_ips"] == 3
        assert stats["blocked_ips_count"] == 3
        assert len(stats["blocked_ips"]) == 3
        assert stats["config"]["max_attempts"] == 3
        assert stats["config"]["base_delay"] == 60
        assert stats["config"]["enabled"] is True

    def test_auth_rate_limiter_disabled(self):
        config = AuthRateLimitConfig(enabled=False)
        limiter = AuthRateLimiter(config=config)

        current_time = time.monotonic()

        with patch("time.monotonic", return_value=current_time):
            for _ in range(10):
                limiter.record_failed_attempt("192.168.1.1")

        is_blocked = limiter.is_blocked("192.168.1.1")
        assert is_blocked is False

    def test_blocked_client_reset_after_timeout(self):
        limiter = AuthRateLimiter(max_attempts=3, base_delay=1)

        current_time = time.monotonic()

        with patch("time.monotonic", return_value=current_time):
            for _ in range(3):
                limiter.record_failed_attempt("192.168.1.1")

        is_blocked = limiter.is_blocked("192.168.1.1")
        assert is_blocked is True

        new_time = current_time + 2
        with patch("time.monotonic", return_value=new_time):
            is_blocked = limiter.is_blocked("192.168.1.1")

        assert is_blocked is False
        assert "192.168.1.1" not in limiter._attempts

    def test_publish_lockout_event(self):
        event_bus = MagicMock()
        limiter = AuthRateLimiter(max_attempts=3, event_bus=event_bus)

        current_time = time.monotonic()

        with patch("time.monotonic", return_value=current_time):
            for _ in range(5):
                limiter.record_failed_attempt("192.168.1.1")

        assert event_bus.publish.called
        event = event_bus.publish.call_args[0][0]
        assert event.event_type.value == "error"
        assert event.payload["type"] == "auth_lockout"
        assert event.payload["client_ip"] == "192.168.1.1"
        assert event.payload["duration"] > 0


class TestInitAuthRateLimiter:
    def test_init_with_app(self):
        from flask import Flask

        app = Flask(__name__)
        config = AuthRateLimitConfig(max_attempts=10)
        init_auth_rate_limiter(app, config=config)

        assert app._auth_rate_limiter is not None
        assert app._auth_rate_limiter.config.max_attempts == 10

    def test_init_without_config(self):
        from flask import Flask

        app = Flask(__name__)
        init_auth_rate_limiter(app)

        assert app._auth_rate_limiter is not None
        assert app._auth_rate_limiter.config.max_attempts == 5


class TestGetAuthRateLimiter:
    def test_get_auth_rate_limiter_singleton(self):
        import api.auth_rate_limiter as arl_module

        arl_module._auth_limiter = None

        limiter1 = get_auth_rate_limiter()
        limiter2 = get_auth_rate_limiter()

        assert limiter1 is limiter2
