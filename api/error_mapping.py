"""Маппинг исключений домена в контракт ошибок API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from exceptions import (
    APIAuthenticationError,
    APIAuthorizationError,
    APIError,
    APINotFoundError,
    APIRateLimitError,
    APIValidationError,
    CaptureAreaError,
    ConfigurationError,
    ConfigValidationError,
    RecordingNotActiveError,
    RecordingStateError,
    WindowNotFoundError,
)


@dataclass(frozen=True, slots=True)
class ErrorMappingResult:
    """Результат нормализации исключения в API-ответ."""

    status_code: int
    code: str
    message: str
    details: Any | None = None


_API_CODE_BY_EXCEPTION: dict[type[Exception], str] = {
    APIAuthenticationError: "unauthorized",
    APIAuthorizationError: "forbidden",
    APIValidationError: "validation_error",
    APINotFoundError: "not_found",
    APIRateLimitError: "rate_limited",
}

_API_CODE_BY_STATUS: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    413: "payload_too_large",
    429: "rate_limited",
    504: "timeout",
    500: "internal_error",
}


def _safe_message(
    error: Exception,
    fallback: str,
) -> str:
    """Возвращает сообщение исключения либо fallback."""
    message = str(error).strip()
    return message or fallback


def map_exception_to_api_error(error: Exception) -> ErrorMappingResult:
    """Преобразует исключение в стандартизированный API-контракт."""
    if isinstance(error, APIError):
        code = _API_CODE_BY_EXCEPTION.get(
            type(error),
            _API_CODE_BY_STATUS.get(error.status_code, "api_error"),
        )
        return ErrorMappingResult(
            status_code=error.status_code,
            code=code,
            message=_safe_message(error, "Ошибка API"),
            details=error.details,
        )

    if isinstance(error, RecordingNotActiveError):
        return ErrorMappingResult(
            status_code=409,
            code="conflict",
            message=_safe_message(error, "Запись не активна"),
        )

    if isinstance(error, RecordingStateError):
        return ErrorMappingResult(
            status_code=409,
            code="conflict",
            message=_safe_message(error, "Некорректное состояние записи"),
        )

    if isinstance(error, WindowNotFoundError):
        return ErrorMappingResult(
            status_code=404,
            code="not_found",
            message=_safe_message(error, "Окно не найдено"),
        )

    if isinstance(error, CaptureAreaError):
        return ErrorMappingResult(
            status_code=400,
            code="validation_error",
            message=_safe_message(error, "Некорректная область захвата"),
        )

    if isinstance(error, ConfigValidationError):
        return ErrorMappingResult(
            status_code=400,
            code="validation_error",
            message=_safe_message(error, "Ошибка валидации конфигурации"),
        )

    if isinstance(error, ConfigurationError):
        return ErrorMappingResult(
            status_code=400,
            code="configuration_error",
            message=_safe_message(error, "Ошибка конфигурации"),
        )

    if isinstance(error, ValueError):
        return ErrorMappingResult(
            status_code=400,
            code="validation_error",
            message=_safe_message(error, "Ошибка валидации данных"),
        )

    if isinstance(error, TimeoutError):
        return ErrorMappingResult(
            status_code=504,
            code="timeout",
            message=_safe_message(error, "Операция превысила таймаут"),
        )

    return ErrorMappingResult(
        status_code=500,
        code="internal_error",
        message="Внутренняя ошибка сервера",
        details=None,
    )
