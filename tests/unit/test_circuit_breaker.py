"""Unit-тесты для CircuitBreaker."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from api.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
)


def _make_cb(**kwargs) -> CircuitBreaker:
    defaults = {
        "name": "test",
        "failure_threshold": 3,
        "recovery_timeout": 30.0,
        "half_open_max_calls": 1,
    }
    defaults.update(kwargs)
    return CircuitBreaker(**defaults)


class TestCircuitBreakerInitialState:
    def test_initial_state_closed(self) -> None:
        cb = _make_cb()
        assert cb.state == CircuitState.CLOSED.value

    def test_initial_counts_zero(self) -> None:
        cb = _make_cb()
        assert cb.failure_count == 0
        assert cb.success_count == 0

    def test_get_metrics_returns_dict(self) -> None:
        cb = _make_cb(name="my_cb")
        metrics = cb.get_metrics()
        assert metrics["name"] == "my_cb"
        assert metrics["state"] == "closed"
        assert metrics["failure_count"] == 0
        assert metrics["success_count"] == 0


class TestCircuitBreakerClosed:
    def test_successful_call_increments_success(self) -> None:
        cb = _make_cb()
        fn = MagicMock(return_value="ok")
        result = cb.call(fn, 1, key="val")
        fn.assert_called_once_with(1, key="val")
        assert result == "ok"
        assert cb.success_count == 1
        assert cb.failure_count == 0

    def test_failed_call_increments_failure(self) -> None:
        cb = _make_cb()
        fn = MagicMock(side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError):
            cb.call(fn)
        assert cb.failure_count == 1
        assert cb.state == CircuitState.CLOSED.value

    def test_stays_closed_below_threshold(self) -> None:
        cb = _make_cb(failure_threshold=3)
        fn = MagicMock(side_effect=RuntimeError("boom"))
        for _ in range(2):
            with pytest.raises(RuntimeError):
                cb.call(fn)
        assert cb.state == CircuitState.CLOSED.value


class TestCircuitBreakerTransitionToOpen:
    def test_transitions_to_open_at_threshold(self) -> None:
        cb = _make_cb(failure_threshold=3)
        fn = MagicMock(side_effect=RuntimeError("boom"))
        for _ in range(3):
            with pytest.raises(RuntimeError):
                cb.call(fn)
        assert cb.state == CircuitState.OPEN.value

    def test_open_rejects_calls_without_calling_fn(self) -> None:
        cb = _make_cb(failure_threshold=1)
        fn = MagicMock(side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError):
            cb.call(fn)
        assert cb.state == CircuitState.OPEN.value

        probe = MagicMock(return_value="ok")
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            cb.call(probe)
        probe.assert_not_called()
        assert exc_info.value.name == "test"
        assert exc_info.value.retry_after > 0

    def test_circuit_breaker_open_error_attributes(self) -> None:
        err = CircuitBreakerOpenError("svc", 12.5)
        assert err.name == "svc"
        assert err.retry_after == 12.5
        assert "svc" in str(err)


def _force_half_open(cb: CircuitBreaker) -> None:
    """Форсирует CB в состояние HALF_OPEN без ожидания таймаута."""
    with cb._lock:
        cb._state = CircuitState.HALF_OPEN
        cb._half_open_calls = 0


def _force_open(cb: CircuitBreaker) -> None:
    """Форсирует CB в состояние OPEN."""
    with cb._lock:
        cb._state = CircuitState.OPEN
        cb._opened_at = time.monotonic()
        cb._half_open_calls = 0


class TestCircuitBreakerHalfOpen:
    def test_transitions_to_half_open_after_timeout(self) -> None:
        cb = _make_cb(failure_threshold=1, recovery_timeout=0.05)
        fn = MagicMock(side_effect=RuntimeError("boom"))
        with pytest.raises(RuntimeError):
            cb.call(fn)
        assert cb.state == CircuitState.OPEN.value
        time.sleep(0.06)
        probe = MagicMock(return_value="ok")
        cb.call(probe)
        assert cb.state == CircuitState.CLOSED.value

    def test_half_open_success_closes_circuit(self) -> None:
        cb = _make_cb(failure_threshold=1)
        _force_open(cb)
        _force_half_open(cb)
        probe = MagicMock(return_value="data")
        result = cb.call(probe)
        assert result == "data"
        assert cb.state == CircuitState.CLOSED.value

    def test_half_open_failure_reopens_circuit(self) -> None:
        cb = _make_cb(failure_threshold=1)
        _force_open(cb)
        _force_half_open(cb)
        probe = MagicMock(side_effect=RuntimeError("still broken"))
        with pytest.raises(RuntimeError):
            cb.call(probe)
        assert cb.state == CircuitState.OPEN.value

    def test_half_open_max_calls_exceeded_raises_open_error(self) -> None:
        cb = _make_cb(failure_threshold=1, half_open_max_calls=1)
        _force_open(cb)
        _force_half_open(cb)
        with cb._lock:
            cb._half_open_calls = cb.half_open_max_calls
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(MagicMock(return_value="ok"))


class TestCircuitBreakerMetrics:
    def test_metrics_reflect_state(self) -> None:
        cb = _make_cb(name="metrics_cb", failure_threshold=2)
        fn_ok = MagicMock(return_value=42)
        fn_fail = MagicMock(side_effect=ValueError("err"))

        cb.call(fn_ok)
        with pytest.raises(ValueError):
            cb.call(fn_fail)

        m = cb.get_metrics()
        assert m["name"] == "metrics_cb"
        assert m["success_count"] == 1
        assert m["failure_count"] == 1
        assert m["state"] == "closed"

    def test_metrics_state_open(self) -> None:
        cb = _make_cb(failure_threshold=1)
        fn_fail = MagicMock(side_effect=ValueError("err"))
        with pytest.raises(ValueError):
            cb.call(fn_fail)
        m = cb.get_metrics()
        assert m["state"] == "open"
