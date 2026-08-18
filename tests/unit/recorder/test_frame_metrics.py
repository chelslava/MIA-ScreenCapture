"""Unit-тесты для модуля recorder/frame_metrics.py (#114)."""

from __future__ import annotations

from unittest.mock import patch

from recorder.frame_metrics import FrameMetrics, FrameMetricsSnapshot


class TestFrameMetricsSnapshot:
    """Тесты структуры FrameMetricsSnapshot."""

    def test_to_dict_serialization(self) -> None:
        snapshot = FrameMetricsSnapshot(
            actual_fps=29.8765,
            target_fps=30,
            jitter_ms=2.3456,
            frames_dropped=3,
            encode_latency_ms=4.5678,
            buffer_fill_percent=12.345,
            total_frames=100,
        )
        data = snapshot.to_dict()
        assert data["actual_fps"] == 29.88
        assert data["target_fps"] == 30
        assert data["jitter_ms"] == 2.35
        assert data["frames_dropped"] == 3
        assert data["encode_latency_ms"] == 4.57
        assert data["buffer_fill_percent"] == 12.35
        assert data["total_frames"] == 100


class TestFrameMetrics:
    """Тесты класса FrameMetrics."""

    def test_initial_state(self) -> None:
        metrics = FrameMetrics(target_fps=60, window_size=200)
        assert metrics.target_fps == 60
        assert metrics.actual_fps == 0.0
        assert metrics.jitter_ms == 0.0
        assert metrics.frames_dropped == 0
        assert metrics.avg_encode_latency_ms == 0.0
        assert metrics.total_frames == 0
        assert metrics.buffer_fill_percent == 0.0

    def test_record_frame_calculates_fps(self) -> None:
        metrics = FrameMetrics(target_fps=30, window_size=100)
        timestamps = [10.0, 10.033, 10.066, 10.099]

        with patch("time.monotonic", side_effect=timestamps):
            for _ in range(4):
                metrics.record_frame(encode_latency_ms=2.5)

        assert metrics.total_frames == 4
        assert metrics.avg_encode_latency_ms == 2.5
        # 3 intervals over 0.099 seconds => ~30.3 fps
        assert 30.0 <= metrics.actual_fps <= 31.0

    def test_jitter_calculation(self) -> None:
        metrics = FrameMetrics(target_fps=30)
        # Intervals: 30ms, 40ms, 30ms => avg=33.33ms, max delta = |40 - 33.33| = 6.67ms
        timestamps = [1.0, 1.030, 1.070, 1.100]

        with patch("time.monotonic", side_effect=timestamps):
            for _ in range(4):
                metrics.record_frame(encode_latency_ms=1.0)

        assert metrics.jitter_ms > 0.0
        assert 6.0 <= metrics.jitter_ms <= 7.0

    def test_jitter_with_few_frames_returns_zero(self) -> None:
        metrics = FrameMetrics(target_fps=30)
        with patch("time.monotonic", side_effect=[1.0, 1.033]):
            metrics.record_frame()
            metrics.record_frame()
        # Less than 3 timestamps -> 0.0 jitter
        assert metrics.jitter_ms == 0.0

    def test_record_drop(self) -> None:
        metrics = FrameMetrics()
        metrics.record_drop()
        metrics.record_drop(2)
        assert metrics.frames_dropped == 3

    def test_set_buffer_fill_percent(self) -> None:
        metrics = FrameMetrics()
        metrics.set_buffer_fill_percent(45.5)
        assert metrics.buffer_fill_percent == 45.5

        metrics.set_buffer_fill_percent(150.0)
        assert metrics.buffer_fill_percent == 100.0

        metrics.set_buffer_fill_percent(-10.0)
        assert metrics.buffer_fill_percent == 0.0

    def test_reset_clears_metrics(self) -> None:
        metrics = FrameMetrics(target_fps=30)
        with patch("time.monotonic", side_effect=[1.0, 2.0]):
            metrics.record_frame(encode_latency_ms=5.0)
            metrics.record_frame(encode_latency_ms=6.0)
            metrics.record_drop(5)
            metrics.set_buffer_fill_percent(50.0)

        assert metrics.total_frames == 2
        assert metrics.frames_dropped == 5

        metrics.reset(target_fps=60)
        assert metrics.target_fps == 60
        assert metrics.total_frames == 0
        assert metrics.frames_dropped == 0
        assert metrics.actual_fps == 0.0
        assert metrics.jitter_ms == 0.0
        assert metrics.avg_encode_latency_ms == 0.0
        assert metrics.buffer_fill_percent == 0.0

    def test_to_dict_contains_all_keys(self) -> None:
        metrics = FrameMetrics(target_fps=30)
        with patch("time.monotonic", side_effect=[1.0, 1.033, 1.066]):
            metrics.record_frame(
                encode_latency_ms=3.2, buffer_fill_percent=15.0
            )
            metrics.record_frame(
                encode_latency_ms=3.4, buffer_fill_percent=15.0
            )
            metrics.record_frame(
                encode_latency_ms=3.6, buffer_fill_percent=15.0
            )

        data = metrics.to_dict()
        assert "actual_fps" in data
        assert "target_fps" in data
        assert "jitter_ms" in data
        assert "frames_dropped" in data
        assert "encode_latency_ms" in data
        assert "buffer_fill_percent" in data
        assert "total_frames" in data
        assert data["total_frames"] == 3
