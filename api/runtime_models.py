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

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> APIOperation:
        """Построить internal model из dict-compatible snapshot."""
        return cls(
            operation_id=str(payload.get("id", "")),
            operation_type=str(payload.get("type", "")),
            status=payload.get("status", "failed"),
            created_at=str(payload.get("created_at", "")),
            updated_at=str(payload.get("updated_at", "")),
            completed_at=payload.get("completed_at"),
            result=payload.get("result"),
            error=payload.get("error"),
            request_id=payload.get("request_id"),
            trace_id=payload.get("trace_id"),
            client_ip=payload.get("client_ip"),
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


@dataclass(frozen=True, slots=True)
class ObservabilityLatencyStats:
    """Сводка latency-метрик API."""

    count: int
    avg_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float

    def to_dict(self) -> dict[str, float | int]:
        """Сериализовать latency-статистику в совместимый dict."""
        return {
            "count": self.count,
            "avg_ms": self.avg_ms,
            "p50_ms": self.p50_ms,
            "p95_ms": self.p95_ms,
            "p99_ms": self.p99_ms,
            "max_ms": self.max_ms,
        }


@dataclass(frozen=True, slots=True)
class ObservabilityResourceStats:
    """Сводка resource-метрик API процесса."""

    rss_mb: float
    threads: int
    cpu_percent: float

    def to_dict(self) -> dict[str, float | int]:
        """Сериализовать resource-статистику в совместимый dict."""
        return {
            "rss_mb": self.rss_mb,
            "threads": self.threads,
            "cpu_percent": self.cpu_percent,
        }


@dataclass(frozen=True, slots=True)
class ObservabilityPathStat:
    """Одна запись top-path статистики."""

    path: str
    count: int

    def to_dict(self) -> dict[str, str | int]:
        """Сериализовать path statistic в совместимый dict."""
        return {
            "path": self.path,
            "count": self.count,
        }


@dataclass(frozen=True, slots=True)
class ObservabilitySnapshot:
    """Типизированный snapshot эксплуатационных метрик API."""

    uptime_seconds: float
    requests_total: int
    requests_inflight: int
    requests_per_second: float
    errors_total: int
    error_rate_percent: float
    status_codes: dict[str, int]
    methods: dict[str, int]
    top_paths: tuple[ObservabilityPathStat, ...]
    latency_ms: ObservabilityLatencyStats
    resources: ObservabilityResourceStats
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        """Сериализовать snapshot в совместимый dict."""
        return {
            "uptime_seconds": self.uptime_seconds,
            "requests_total": self.requests_total,
            "requests_inflight": self.requests_inflight,
            "requests_per_second": self.requests_per_second,
            "errors_total": self.errors_total,
            "error_rate_percent": self.error_rate_percent,
            "status_codes": dict(self.status_codes),
            "methods": dict(self.methods),
            "top_paths": [item.to_dict() for item in self.top_paths],
            "latency_ms": self.latency_ms.to_dict(),
            "resources": self.resources.to_dict(),
            "generated_at": self.generated_at,
        }


@dataclass(frozen=True, slots=True)
class ObservabilityTargets:
    """Целевые SLO observability."""

    p95_latency_ms: float
    error_rate_percent: float

    def to_dict(self) -> dict[str, float]:
        """Сериализовать SLO targets в совместимый dict."""
        return {
            "p95_latency_ms": self.p95_latency_ms,
            "error_rate_percent": self.error_rate_percent,
        }


@dataclass(frozen=True, slots=True)
class ObservabilityCurrent:
    """Текущее observability состояние для baseline-ответа."""

    p95_latency_ms: float
    error_rate_percent: float
    requests_per_second: float
    rss_mb: float

    def to_dict(self) -> dict[str, float]:
        """Сериализовать текущее observability состояние в dict."""
        return {
            "p95_latency_ms": self.p95_latency_ms,
            "error_rate_percent": self.error_rate_percent,
            "requests_per_second": self.requests_per_second,
            "rss_mb": self.rss_mb,
        }


@dataclass(frozen=True, slots=True)
class ObservabilityBaseline:
    """Типизированный baseline observability/SLO."""

    sample_size: int
    slo_targets: ObservabilityTargets
    current: ObservabilityCurrent
    meets_targets: dict[str, bool]
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        """Сериализовать baseline в совместимый dict."""
        return {
            "sample_size": self.sample_size,
            "slo_targets": self.slo_targets.to_dict(),
            "current": self.current.to_dict(),
            "meets_targets": dict(self.meets_targets),
            "generated_at": self.generated_at,
        }


@dataclass(frozen=True, slots=True)
class APIOperationPayload:
    """Публичный payload фоновой операции для route responses."""

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
    def from_operation(cls, operation: APIOperation) -> APIOperationPayload:
        """Построить публичный payload из internal operation model."""
        return cls(
            operation_id=operation.operation_id,
            operation_type=operation.operation_type,
            status=operation.status,
            created_at=operation.created_at,
            updated_at=operation.updated_at,
            completed_at=operation.completed_at,
            result=operation.result,
            error=operation.error,
            request_id=operation.request_id,
            trace_id=operation.trace_id,
            client_ip=operation.client_ip,
        )

    def to_dict(self) -> dict[str, Any]:
        """Сериализовать payload в совместимый dict."""
        payload = {
            "operation_id": self.operation_id,
            "type": self.operation_type,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }
        if self.result is not None:
            payload["result"] = self.result
        if self.error is not None:
            payload["error"] = self.error
        if self.request_id is not None:
            payload["request_id"] = self.request_id
        if self.trace_id is not None:
            payload["trace_id"] = self.trace_id
        if self.client_ip is not None:
            payload["client_ip"] = self.client_ip
        return payload
