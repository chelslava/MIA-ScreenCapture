"""Юнит-тесты маппинга исключений в контракт API."""

from __future__ import annotations

import pytest

from api.error_mapping import map_exception_to_api_error
from exceptions import (
    APIAuthenticationError,
    APIAuthorizationError,
    APIError,
    APINotFoundError,
    APIRateLimitError,
    APIValidationError,
    CaptureAreaInvalidError,
    ConfigurationError,
    ConfigValidationError,
    RecordingNotActiveError,
    RecordingStateError,
    WindowNotFoundError,
)


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (APIAuthenticationError("bad key"), 401, "unauthorized"),
        (APIAuthorizationError("no access"), 403, "forbidden"),
        (APINotFoundError("missing"), 404, "not_found"),
        (APIRateLimitError("limit"), 429, "rate_limited"),
        (APIValidationError("bad payload"), 400, "validation_error"),
        (APIError("payload", status_code=409), 409, "conflict"),
        (RecordingStateError("already running"), 409, "conflict"),
        (RecordingNotActiveError("not active"), 409, "conflict"),
        (CaptureAreaInvalidError("invalid area"), 400, "validation_error"),
        (WindowNotFoundError("window missing"), 404, "not_found"),
        (ConfigValidationError("invalid config"), 400, "validation_error"),
        (ConfigurationError("broken config"), 400, "configuration_error"),
        (ValueError("bad value"), 400, "validation_error"),
        (TimeoutError(), 504, "timeout"),
    ],
)
def test_map_exception_to_api_error_known_types(
    error: Exception,
    status_code: int,
    code: str,
) -> None:
    """Проверяет маппинг известных типов исключений."""
    mapped = map_exception_to_api_error(error)
    assert mapped.status_code == status_code
    assert mapped.code == code
    assert isinstance(mapped.message, str)
    assert mapped.message


def test_map_exception_to_api_error_fallback() -> None:
    """Проверяет безопасный fallback для неизвестной ошибки."""
    mapped = map_exception_to_api_error(RuntimeError("boom"))
    assert mapped.status_code == 500
    assert mapped.code == "internal_error"
    assert mapped.message == "Внутренняя ошибка сервера"
    assert mapped.details is None
