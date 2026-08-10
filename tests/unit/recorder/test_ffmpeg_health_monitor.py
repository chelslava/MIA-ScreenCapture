"""Тесты health-monitor FFmpeg writer (#85)."""

import logging
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

import recorder.ffmpeg_writer as ffmpeg_writer_module
from recorder.ffmpeg_writer import FFmpegVideoWriter


class TestHealthMonitor:
    """Покрытие фонового мониторинга процесса FFmpeg (#85)."""

    def _make_writer(self, tmp_path: Path) -> FFmpegVideoWriter:
        return FFmpegVideoWriter(
            output_path=tmp_path / "out.mp4",
            width=640,
            height=360,
            fps=30,
            health_check_interval_s=0.05,
        )

    def test_start_health_monitor_noop_when_thread_mocked(
        self, tmp_path: Path
    ) -> None:
        """Когда threading.Thread замокан — health-monitor не создаётся."""
        writer = self._make_writer(tmp_path)
        original = ffmpeg_writer_module.threading.Thread

        class _SyncThread:
            """Синхронная обёртка потока (способ mock-окружения тестов)."""

            def __init__(
                self,
                target: Any = None,
                **kwargs: Any,
            ) -> None:
                self._target = target

            def start(self) -> None:
                self._target()  # блокирующий вызов

            def join(self, timeout: float | None = None) -> None:
                return None

            def is_alive(self) -> bool:
                return False

        try:
            ffmpeg_writer_module.threading.Thread = _SyncThread  # type: ignore[assignment, misc]
            writer._start_health_monitor()
            assert writer._health_thread is None, (
                "Health-monitor должен пропускаться при mock-окружении"
            )
        finally:
            ffmpeg_writer_module.threading.Thread = original  # type: ignore[misc]

    def test_health_monitor_detects_process_death(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Health-monitor логирует падение процесса между write()."""
        writer = self._make_writer(tmp_path)
        fake_process = MagicMock()
        tick_calls: list[int] = []

        def poll_after_N() -> int | None:
            tick_calls.append(1)
            return 1 if len(tick_calls) >= 1 else None

        fake_process.poll = poll_after_N
        fake_process.stderr = None
        writer._process = fake_process
        writer._frame_count = 42
        writer._start_time = time.time() - 5.0  # "записали" 5 секунд

        caplog.set_level(logging.ERROR)

        writer._start_health_monitor()
        time.sleep(0.5)
        writer._stop_health_monitor()

        assert any("между кадрами" in r.message for r in caplog.records), (
            f"Ожидали лог про падение FFmpeg, получили: "
            f"{[r.message for r in caplog.records]}"
        )

    def test_health_monitor_stops_cleanly(self, tmp_path: Path) -> None:
        """Поток останавливается через _stop_health_monitor."""
        writer = self._make_writer(tmp_path)
        fake_process = MagicMock()
        fake_process.poll = MagicMock(return_value=None)  # процесс жив
        fake_process.stderr = None
        writer._process = fake_process

        writer._start_health_monitor()
        assert writer._health_thread is not None
        assert writer._health_thread.is_alive()

        writer._stop_health_monitor()
        assert writer._health_thread is None
