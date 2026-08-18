"""Метрики захвата кадров и производительности в реальном времени."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class FrameMetricsSnapshot:
    """Неизменяемый снимок метрик захвата кадров."""

    actual_fps: float
    target_fps: int
    jitter_ms: float
    frames_dropped: int
    encode_latency_ms: float
    buffer_fill_percent: float
    total_frames: int

    def to_dict(self) -> dict[str, Any]:
        """Преобразует снимок в сериализуемый словарь."""
        return {
            "actual_fps": round(self.actual_fps, 2),
            "target_fps": self.target_fps,
            "jitter_ms": round(self.jitter_ms, 2),
            "frames_dropped": self.frames_dropped,
            "encode_latency_ms": round(self.encode_latency_ms, 2),
            "buffer_fill_percent": round(self.buffer_fill_percent, 2),
            "total_frames": self.total_frames,
        }


class FrameMetrics:
    """Скользящие метрики захвата и кодирования кадров."""

    def __init__(
        self,
        target_fps: int = 30,
        window_size: int = 300,
    ) -> None:
        self.target_fps = max(1, target_fps)
        self._window_size = max(10, window_size)
        self._timestamps: deque[float] = deque(maxlen=self._window_size)
        self._encode_latencies: deque[float] = deque(maxlen=self._window_size)
        self._frames_dropped: int = 0
        self._total_frames: int = 0
        self._buffer_fill_percent: float = 0.0

    def record_frame(
        self,
        encode_latency_ms: float = 0.0,
        buffer_fill_percent: float = 0.0,
    ) -> None:
        """Регистрирует успешный захват и запись кадра."""
        self._timestamps.append(time.monotonic())
        if encode_latency_ms >= 0:
            self._encode_latencies.append(encode_latency_ms)
        self._buffer_fill_percent = max(0.0, min(100.0, buffer_fill_percent))
        self._total_frames += 1

    def record_drop(self, count: int = 1) -> None:
        """Регистрирует пропуск / сброс кадра."""
        self._frames_dropped += max(1, count)

    def set_buffer_fill_percent(self, percent: float) -> None:
        """Устанавливает текущий процент заполнения буфера."""
        self._buffer_fill_percent = max(0.0, min(100.0, percent))

    def reset(self, target_fps: int | None = None) -> None:
        """Сбрасывает накопленные метрики."""
        if target_fps is not None:
            self.target_fps = max(1, target_fps)
        self._timestamps.clear()
        self._encode_latencies.clear()
        self._frames_dropped = 0
        self._total_frames = 0
        self._buffer_fill_percent = 0.0

    @property
    def actual_fps(self) -> float:
        """Фактический FPS за скользящее окно."""
        if len(self._timestamps) < 2:
            return 0.0
        elapsed = self._timestamps[-1] - self._timestamps[0]
        if elapsed <= 0:
            return 0.0
        return (len(self._timestamps) - 1) / elapsed

    @property
    def jitter_ms(self) -> float:
        """Дрожание (jitter) межкадровых интервалов в миллисекундах."""
        if len(self._timestamps) < 3:
            return 0.0
        deltas = [
            (self._timestamps[i + 1] - self._timestamps[i]) * 1000.0
            for i in range(len(self._timestamps) - 1)
        ]
        if not deltas:
            return 0.0
        avg = sum(deltas) / len(deltas)
        return max(abs(d - avg) for d in deltas)

    @property
    def avg_encode_latency_ms(self) -> float:
        """Средняя задержка записи/кодирования в миллисекундах."""
        if not self._encode_latencies:
            return 0.0
        return sum(self._encode_latencies) / len(self._encode_latencies)

    @property
    def frames_dropped(self) -> int:
        """Общее количество пропущенных кадров."""
        return self._frames_dropped

    @property
    def total_frames(self) -> int:
        """Общее количество записанных кадров."""
        return self._total_frames

    @property
    def buffer_fill_percent(self) -> float:
        """Текущее заполнение буфера (0..100%)."""
        return self._buffer_fill_percent

    def get_snapshot(self) -> FrameMetricsSnapshot:
        """Возвращает снимок текущих метрик."""
        return FrameMetricsSnapshot(
            actual_fps=self.actual_fps,
            target_fps=self.target_fps,
            jitter_ms=self.jitter_ms,
            frames_dropped=self.frames_dropped,
            encode_latency_ms=self.avg_encode_latency_ms,
            buffer_fill_percent=self.buffer_fill_percent,
            total_frames=self.total_frames,
        )

    def to_dict(self) -> dict[str, Any]:
        """Возвращает метрики в виде словаря."""
        return self.get_snapshot().to_dict()
