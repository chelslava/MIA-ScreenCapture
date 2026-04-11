"""Потокобезопасный сбор эксплуатационных метрик API."""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import UTC, datetime
from typing import Any

import psutil

from api.runtime_models import (
    ObservabilityBaseline,
    ObservabilityCurrent,
    ObservabilityLatencyStats,
    ObservabilityPathStat,
    ObservabilityResourceStats,
    ObservabilitySnapshot,
    ObservabilityTargets,
)


class APIServerObservability:
    """Потокобезопасный сбор базовых эксплуатационных метрик API."""

    _MAX_PATH_ENTRIES = 100

    def __init__(self, max_latency_samples: int = 2000) -> None:
        self._lock = threading.Lock()
        self._started_at = time.monotonic()
        self._requests_total = 0
        self._requests_inflight = 0
        self._errors_total = 0
        self._status_counts: dict[str, int] = {}
        self._method_counts: dict[str, int] = {}
        self._path_counts: dict[str, int] = {}
        self._latency_ms: deque[float] = deque(maxlen=max_latency_samples)
        self._process = psutil.Process()

    def request_started(self) -> None:
        with self._lock:
            self._requests_inflight += 1

    def request_finished(
        self,
        method: str,
        path: str,
        status_code: int,
        latency_seconds: float,
    ) -> None:
        status_key = str(status_code)
        latency_ms = max(0.0, latency_seconds * 1000.0)
        with self._lock:
            self._requests_total += 1
            self._requests_inflight = max(0, self._requests_inflight - 1)
            if status_code >= 500:
                self._errors_total += 1
            self._status_counts[status_key] = (
                self._status_counts.get(status_key, 0) + 1
            )
            self._method_counts[method] = (
                self._method_counts.get(method, 0) + 1
            )
            if (
                len(self._path_counts) < self._MAX_PATH_ENTRIES
                or path in self._path_counts
            ):
                self._path_counts[path] = self._path_counts.get(path, 0) + 1
            self._latency_ms.append(latency_ms)

    @staticmethod
    def _percentile(sorted_values: list[float], percentile: float) -> float:
        if not sorted_values:
            return 0.0
        if percentile <= 0:
            return sorted_values[0]
        if percentile >= 100:
            return sorted_values[-1]
        index = (len(sorted_values) - 1) * (percentile / 100.0)
        lower = int(index)
        upper = min(lower + 1, len(sorted_values) - 1)
        weight = index - lower
        return (
            sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
        )

    def _latency_stats(self) -> ObservabilityLatencyStats:
        with self._lock:
            samples = sorted(self._latency_ms)
        if not samples:
            return ObservabilityLatencyStats(0, 0.0, 0.0, 0.0, 0.0, 0.0)
        return ObservabilityLatencyStats(
            count=len(samples),
            avg_ms=round(sum(samples) / len(samples), 3),
            p50_ms=round(self._percentile(samples, 50), 3),
            p95_ms=round(self._percentile(samples, 95), 3),
            p99_ms=round(self._percentile(samples, 99), 3),
            max_ms=round(samples[-1], 3),
        )

    def _resource_stats(self) -> ObservabilityResourceStats:
        memory_info = self._process.memory_info()
        return ObservabilityResourceStats(
            rss_mb=round(memory_info.rss / (1024 * 1024), 3),
            threads=self._process.num_threads(),
            cpu_percent=round(self._process.cpu_percent(interval=None), 3),
        )

    def get_metrics_snapshot(self) -> dict[str, Any]:
        with self._lock:
            requests_total = self._requests_total
            requests_inflight = self._requests_inflight
            errors_total = self._errors_total
            status_counts = dict(self._status_counts)
            method_counts = dict(self._method_counts)
            path_counts = dict(self._path_counts)
            uptime = max(0.0, time.monotonic() - self._started_at)

        top_paths = sorted(
            path_counts.items(), key=lambda item: item[1], reverse=True
        )[:10]
        latency = self._latency_stats()
        resources = self._resource_stats()
        requests_per_second = (
            round(requests_total / uptime, 6) if uptime else 0.0
        )
        error_rate_percent = (
            round((errors_total / requests_total) * 100.0, 6)
            if requests_total
            else 0.0
        )

        snapshot = ObservabilitySnapshot(
            uptime_seconds=round(uptime, 3),
            requests_total=requests_total,
            requests_inflight=requests_inflight,
            requests_per_second=requests_per_second,
            errors_total=errors_total,
            error_rate_percent=error_rate_percent,
            status_codes=status_counts,
            methods=method_counts,
            top_paths=tuple(
                ObservabilityPathStat(path=path, count=count)
                for path, count in top_paths
            ),
            latency_ms=latency,
            resources=resources,
            generated_at=datetime.now(UTC).isoformat(),
        )
        return snapshot.to_dict()

    def get_baseline(self) -> dict[str, Any]:
        """Возвращает baseline SLO и текущее observability состояние."""
        metrics = self.get_metrics_snapshot()
        slo_targets = ObservabilityTargets(
            p95_latency_ms=100.0,
            error_rate_percent=1.0,
        )
        current = ObservabilityCurrent(
            p95_latency_ms=metrics["latency_ms"]["p95_ms"],
            error_rate_percent=metrics["error_rate_percent"],
            requests_per_second=metrics["requests_per_second"],
            rss_mb=metrics["resources"]["rss_mb"],
        )
        baseline = ObservabilityBaseline(
            sample_size=metrics["latency_ms"]["count"],
            slo_targets=slo_targets,
            current=current,
            meets_targets={
                "latency": current.p95_latency_ms
                <= slo_targets.p95_latency_ms,
                "error_rate": (
                    current.error_rate_percent
                    <= slo_targets.error_rate_percent
                ),
            },
            generated_at=str(metrics["generated_at"]),
        )
        return baseline.to_dict()
