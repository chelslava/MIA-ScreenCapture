"""Тесты frame-skip логики FFmpeg writer (#87)."""

import time
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np

from recorder.ffmpeg_writer import FFmpegVideoWriter


class TestFrameSkip:
    """Логика пропуска кадров при перегрузке (#87)."""

    def _make_writer(
        self, tmp_path: Path, enable_frame_skip: bool = True
    ) -> FFmpegVideoWriter:
        writer = FFmpegVideoWriter(
            output_path=tmp_path / "out.mp4",
            width=640,
            height=360,
            fps=30,
            health_check_interval_s=0.05,
            enable_frame_skip=enable_frame_skip,
        )
        # Mock-им процесс — write_frame пишет в память
        fake_process = MagicMock()
        fake_process.poll = MagicMock(return_value=None)
        fake_process.stdin = MagicMock()
        fake_process.stderr = None
        writer._process = fake_process
        writer._start_time = time.time() - 1.0  # uptime 1 сек
        return writer

    def _make_frame(self) -> np.ndarray:
        return np.zeros((360, 640, 3), dtype=np.uint8)

    def test_skip_disabled_by_default(self, tmp_path: Path) -> None:
        """frame-skip выключен по умолчанию (обратная совместимость)."""
        writer = FFmpegVideoWriter(
            output_path=tmp_path / "out.mp4",
            width=640,
            height=360,
            fps=30,
        )
        assert writer._enable_frame_skip is False

    def test_no_skip_when_frame_on_time(self, tmp_path: Path) -> None:
        """Кадры вовремя — не скипаются."""
        writer = self._make_writer(tmp_path)
        frame = self._make_frame()

        for _ in range(10):
            assert writer.write(frame) is True

        assert writer.skipped_frames == 0
        assert writer.frame_count == 10

    def test_skip_after_consecutive_late_frames(self, tmp_path: Path) -> None:
        """Скипаем каждый 6-й кадр после 5 подряд медленных."""
        writer = self._make_writer(tmp_path)
        writer._max_consecutive_late_frames = 5
        frame = self._make_frame()

        # Переполнение: пишем с задержкой > 2× интервала (при fps=30
        # интервал ≈ 0.033с, threshold 0.066с)
        original_write = writer._process.stdin.write  # type: ignore[union-attr]

        def slow_write(data: bytes) -> None:
            time.sleep(0.070)  # > threshold
            original_write(data)

        writer._process.stdin.write = slow_write  # type: ignore[method-assign,union-attr]

        # Прогоняем 11 кадров — первые 5 медленные
        for _ in range(11):
            writer.write(frame)

        assert writer.skipped_frames >= 1, (
            f"Ожидали ≥1 скипнутый кадр, skipped={writer.skipped_frames}"
        )

    def test_skip_counter_resets_on_time_write(self, tmp_path: Path) -> None:
        """При восстановлении нормального timing счётчик обнуляется."""
        writer = self._make_writer(tmp_path)
        writer._max_consecutive_late_frames = 5
        frame = self._make_frame()

        original_write = writer._process.stdin.write  # type: ignore[union-attr]
        call_counter = [0]

        def slow_then_fast(data: bytes) -> None:
            call_counter[0] += 1
            if call_counter[0] <= 5:
                time.sleep(0.070)
            original_write(data)

        writer._process.stdin.write = slow_then_fast  # type: ignore[method-assign,union-attr]

        for _ in range(10):
            writer.write(frame)

        # После обратно-нормальных write счётчик late-frames сбрасывается
        assert writer._consecutive_late_frames == 0
