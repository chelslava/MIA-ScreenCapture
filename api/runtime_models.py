"""Типизированные внутренние модели runtime-слоя API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

OperationStatus = Literal["running", "succeeded", "failed"]
IdempotencyStatus = Literal["running", "completed"]


@dataclass(slots=True)
class APIOperation:
    """Внутреннее представление фоновой операции API."""

    operation_id: str
    operation_type: str
    status: OperationStatus
    created_at: str
    updated_at: str
    completed_at: str | None = None
    result: Any | None = None
    error: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    client_ip: str | None = None

    @classmethod
    def create_running(
        cls,
        operation_id: str,
        operation_type: str,
        *,
        request_id: str | None = None,
        trace_id: str | None = None,
        client_ip: str | None = None,
    ) -> APIOperation:
        """Создать операцию в состоянии running."""
        now_iso = datetime.now(UTC).isoformat()
        return cls(
            operation_id=operation_id,
            operation_type=operation_type,
            status="running",
            created_at=now_iso,
            updated_at=now_iso,
            request_id=request_id,
            trace_id=trace_id,
            client_ip=client_ip,
        )

    @classmethod
    def create_failed(
        cls,
        operation_id: str,
        operation_type: str,
        error_message: str,
    ) -> APIOperation:
        """Создать операцию, сразу завершённую ошибкой."""
        now_iso = datetime.now(UTC).isoformat()
        return cls(
            operation_id=operation_id,
            operation_type=operation_type,
            status="failed",
            created_at=now_iso,
            updated_at=now_iso,
            completed_at=now_iso,
            error=error_message,
        )

    def complete(
        self,
        status: OperationStatus,
        *,
        result: Any | None = None,
        error: str | None = None,
    ) -> None:
        """Перевести операцию в terminal state."""
        now_iso = datetime.now(UTC).isoformat()
        self.status = status
        self.updated_at = now_iso
        self.completed_at = now_iso
        self.result = result
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        """Сериализовать в совместимый dict snapshot."""
        return {
            "id": self.operation_id,
            "type": self.operation_type,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "error": self.error,
            "request_id": self.request_id,
            "trace_id": self.trace_id,
            "client_ip": self.client_ip,
        }


@dataclass(slots=True)
class IdempotencyResponse:
    """Кэшируемый ответ для идемпотентного запроса."""

    status_code: int
    body_bytes: bytes
    mimetype: str

    def to_dict(self) -> dict[str, Any]:
        """Сериализация в совместимый dict."""
        return {
            "status_code": self.status_code,
            "body_bytes": self.body_bytes,
            "mimetype": self.mimetype,
        }


@dataclass(slots=True)
class IdempotencyEntry:
    """Внутренняя запись хранилища идемпотентности."""

    fingerprint: str
    status: IdempotencyStatus
    created_at_monotonic: float
    updated_at_monotonic: float
    response: IdempotencyResponse | None = None
