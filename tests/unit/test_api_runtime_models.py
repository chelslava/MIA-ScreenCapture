"""Тесты типизированных внутренних моделей runtime API."""

from api.runtime_models import (
    APIOperation,
    APIOperationPayload,
    ObservabilityBaseline,
    ObservabilityCurrent,
    ObservabilityLatencyStats,
    ObservabilityPathStat,
    ObservabilityResourceStats,
    ObservabilitySnapshot,
    ObservabilityTargets,
)


class TestObservabilityRuntimeModels:
    """Проверки dict-compatible сериализации typed observability models."""

    def test_snapshot_to_dict(self) -> None:
        """Snapshot должен сериализоваться в ожидаемый публичный dict."""
        snapshot = ObservabilitySnapshot(
            uptime_seconds=12.3,
            requests_total=5,
            requests_inflight=1,
            requests_per_second=0.4,
            errors_total=0,
            error_rate_percent=0.0,
            status_codes={"200": 5},
            methods={"GET": 5},
            top_paths=(ObservabilityPathStat(path="/health", count=5),),
            latency_ms=ObservabilityLatencyStats(5, 1.0, 1.0, 2.0, 3.0, 4.0),
            resources=ObservabilityResourceStats(10.5, 3, 0.0),
            generated_at="2026-04-12T00:00:00Z",
        )

        payload = snapshot.to_dict()

        assert payload["requests_total"] == 5
        assert payload["latency_ms"]["p95_ms"] == 2.0
        assert payload["top_paths"][0]["path"] == "/health"

    def test_baseline_to_dict(self) -> None:
        """Baseline должен сериализоваться в прежний контракт."""
        baseline = ObservabilityBaseline(
            sample_size=5,
            slo_targets=ObservabilityTargets(100.0, 1.0),
            current=ObservabilityCurrent(2.0, 0.0, 0.5, 11.0),
            meets_targets={"latency": True, "error_rate": True},
            generated_at="2026-04-12T00:00:00Z",
        )

        payload = baseline.to_dict()

        assert payload["sample_size"] == 5
        assert payload["slo_targets"]["p95_latency_ms"] == 100.0
        assert payload["meets_targets"]["latency"] is True


class TestOperationRuntimeModels:
    """Проверки typed operation payload serialization."""

    def test_operation_payload_to_dict(self) -> None:
        """Operation payload должен сериализоваться в прежний контракт."""
        operation = APIOperation.create_running(
            "op-1",
            "stop",
            request_id="req-1",
            trace_id="trace-1",
        )
        operation.complete("succeeded", result={"success": True})

        payload = APIOperationPayload.from_operation(operation).to_dict()

        assert payload["operation_id"] == "op-1"
        assert payload["type"] == "stop"
        assert payload["status"] == "succeeded"
        assert payload["result"]["success"] is True
