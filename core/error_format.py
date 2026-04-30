"""Унифицированный формат ошибок и ответов API/сервисов.

Предоставляет строго типизированный контракт для формата ошибок:
    {"success": False, "error": {"code": str, "message": str, "details": str | None}}

Обратная совместимость: существующий формат {"success": False, "error": "string"}
остаётся валидным на уровне API, но новый код должен использовать этот модуль.
"""

from __future__ import annotations

from typing import Any

from exceptions import (
    APIAuthenticationError,
    APIAuthorizationError,
    APINotFoundError,
    APIRateLimitError,
    APIValidationError,
    MIAError,
    RecordingError,
    RecordingNotActiveError,
    RecordingStateError,
    SchedulerError,
    TaskNotFoundError,
    TaskValidationError,
)
from logger_config import get_module_logger

logger = get_module_logger(__name__)


# ---------------------------------------------------------------------------
# Коды ошибок
# ---------------------------------------------------------------------------


class ErrorCode:
    """Строковые коды ошибок для машинной обработки на стороне клиента."""

    # Запись
    RECORDING_ALREADY_ACTIVE = "recording_already_active"
    RECORDING_NOT_ACTIVE = "recording_not_active"
    RECORDING_FAILED = "recording_failed"
    RECORDING_STOP_FAILED = "recording_stop_failed"
    RECORDING_PAUSE_FAILED = "recording_pause_failed"
    RECORDING_RESUME_FAILED = "recording_resume_failed"

    # Планировщик
    TASK_NOT_FOUND = "task_not_found"
    TASK_VALIDATION_FAILED = "task_validation_failed"
    SCHEDULER_ERROR = "scheduler_error"

    # API
    AUTHENTICATION_REQUIRED = "authentication_required"
    AUTHORIZATION_DENIED = "authorization_denied"
    VALIDATION_ERROR = "validation_error"
    RESOURCE_NOT_FOUND = "resource_not_found"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"

    # Общие
    INTERNAL_ERROR = "internal_error"
    INVALID_REQUEST = "invalid_request"
    OPERATION_CANCELLED = "operation_cancelled"


# ---------------------------------------------------------------------------
# Формирование ответов
# ---------------------------------------------------------------------------


def error_response(
    code: str,
    message: str,
    details: str | None = None,
) -> dict[str, Any]:
    """Сформировать унифицированный ответ об ошибке.

    Args:
        code: Машиночитаемый код ошибки (см. ErrorCode).
        message: Человекочитаемое описание на русском языке.
        details: Дополнительные детали для диагностики (опционально).

    Returns:
        Dict формата {"success": False, "error": {"code": ..., "message": ..., "details": ...}}.
    """
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
    }


def success_response(data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Сформировать унифицированный ответ об успехе.

    Args:
        data: Дополнительные поля ответа, слитые в результирующий dict.

    Returns:
        Dict формата {"success": True, **data}.
    """
    result: dict[str, Any] = {"success": True}
    if data:
        result.update(data)
    return result


# ---------------------------------------------------------------------------
# ErrorHandler
# ---------------------------------------------------------------------------


class ErrorHandler:
    """Централизованная конвертация исключений в унифицированные ответы.

    Применяется в service layer и API-обработчиках для единого
    маппинга MIAError-иерархии на коды и сообщения.
    """

    def handle(self, exc: Exception) -> dict[str, Any]:
        """Преобразовать исключение в унифицированный ответ об ошибке.

        Args:
            exc: Любое исключение.

        Returns:
            Dict c полями success=False и вложенным error-объектом.
        """
        code, message, details = self._classify(exc)
        logger.debug("Ошибка [%s]: %s", code, message)
        return error_response(code, message, details)

    @staticmethod
    def _classify(exc: Exception) -> tuple[str, str, str | None]:
        """Определить код, сообщение и детали по типу исключения."""
        if isinstance(exc, RecordingStateError):
            return (
                ErrorCode.RECORDING_ALREADY_ACTIVE,
                str(exc),
                getattr(exc, "details", None),
            )
        if isinstance(exc, RecordingNotActiveError):
            return (
                ErrorCode.RECORDING_NOT_ACTIVE,
                str(exc),
                getattr(exc, "details", None),
            )
        if isinstance(exc, RecordingError):
            return (
                ErrorCode.RECORDING_FAILED,
                str(exc),
                getattr(exc, "details", None),
            )
        if isinstance(exc, TaskNotFoundError):
            return (
                ErrorCode.TASK_NOT_FOUND,
                str(exc),
                getattr(exc, "details", None),
            )
        if isinstance(exc, TaskValidationError):
            return (
                ErrorCode.TASK_VALIDATION_FAILED,
                str(exc),
                getattr(exc, "details", None),
            )
        if isinstance(exc, SchedulerError):
            return (
                ErrorCode.SCHEDULER_ERROR,
                str(exc),
                getattr(exc, "details", None),
            )
        if isinstance(exc, APIAuthenticationError):
            return (
                ErrorCode.AUTHENTICATION_REQUIRED,
                str(exc),
                getattr(exc, "details", None),
            )
        if isinstance(exc, APIAuthorizationError):
            return (
                ErrorCode.AUTHORIZATION_DENIED,
                str(exc),
                getattr(exc, "details", None),
            )
        if isinstance(exc, APIValidationError):
            return (
                ErrorCode.VALIDATION_ERROR,
                str(exc),
                getattr(exc, "details", None),
            )
        if isinstance(exc, APINotFoundError):
            return (
                ErrorCode.RESOURCE_NOT_FOUND,
                str(exc),
                getattr(exc, "details", None),
            )
        if isinstance(exc, APIRateLimitError):
            return (
                ErrorCode.RATE_LIMIT_EXCEEDED,
                str(exc),
                getattr(exc, "details", None),
            )
        if isinstance(exc, MIAError):
            return (
                ErrorCode.INTERNAL_ERROR,
                str(exc),
                getattr(exc, "details", None),
            )
        if isinstance(exc, ValueError):
            return ErrorCode.INVALID_REQUEST, str(exc), None
        if isinstance(exc, OSError):
            return ErrorCode.INTERNAL_ERROR, str(exc), None

        return ErrorCode.INTERNAL_ERROR, str(exc), None
