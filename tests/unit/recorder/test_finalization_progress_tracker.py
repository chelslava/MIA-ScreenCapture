"""
Тесты для FinalizationProgressTracker.
"""

import threading
from unittest.mock import MagicMock

from recorder.encoder import FinalizationProgressTracker


class TestFinalizationProgressTrackerBasics:
    def test_initial_state(self) -> None:
        tracker = FinalizationProgressTracker()
        snapshot = tracker.snapshot()
        assert snapshot["percent"] == 0.0
        assert snapshot["active"] is False

    def test_update_clamps_percent(self) -> None:
        tracker = FinalizationProgressTracker()
        tracker.update(percent=-10.0, stage="Тест")
        assert tracker.snapshot()["percent"] == 0.0
        tracker.update(percent=150.0, stage="Тест")
        assert tracker.snapshot()["percent"] == 100.0

    def test_update_sets_stage_and_active(self) -> None:
        tracker = FinalizationProgressTracker()
        tracker.update(percent=25.0, stage="Объединение")
        snapshot = tracker.snapshot()
        assert snapshot["stage"] == "Объединение"
        assert snapshot["active"] is True

    def test_reset_clears_state_but_keeps_configuration(self) -> None:
        tracker = FinalizationProgressTracker()
        tracker.set_total_duration(120.0)
        tracker.set_callback(lambda p, s: None)
        tracker.update(percent=50.0, stage="Test")
        tracker.reset()
        snapshot = tracker.snapshot()
        assert snapshot["percent"] == 0.0
        assert snapshot["active"] is False
        # duration остаётся
        tracker.update_from_ffmpeg_stderr(
            "frame=1 time=00:01:00.00", stage="X"
        )
        assert tracker.snapshot()["percent"] == 50.0

    def test_set_total_duration(self) -> None:
        tracker = FinalizationProgressTracker()
        tracker.set_total_duration(60.0)
        tracker.update_from_ffmpeg_stderr("time=00:00:30.00", stage="X")
        assert tracker.snapshot()["percent"] == 50.0


class TestFFMpegStderrParsing:
    def test_parses_time_format(self) -> None:
        tracker = FinalizationProgressTracker()
        tracker.set_total_duration(100.0)
        tracker.update_from_ffmpeg_stderr(
            "frame=  100 fps=25 q=28.0 size=512KiB time=00:00:50.00",
            stage="Encode",
        )
        assert tracker.snapshot()["percent"] == 50.0

    def test_uses_last_time_match(self) -> None:
        tracker = FinalizationProgressTracker()
        tracker.set_total_duration(100.0)
        tracker.update_from_ffmpeg_stderr(
            "time=00:00:10.00\nsomething\ntime=00:00:75.00\n",
            stage="X",
        )
        assert tracker.snapshot()["percent"] == 75.0

    def test_ignores_invalid_format(self) -> None:
        tracker = FinalizationProgressTracker()
        tracker.set_total_duration(100.0)
        tracker.update_from_ffmpeg_stderr("no time here", stage="X")
        assert tracker.snapshot()["percent"] == 0.0

    def test_handles_duration_zero(self) -> None:
        tracker = FinalizationProgressTracker()
        tracker.set_total_duration(0.0)
        tracker.update_from_ffmpeg_stderr("time=00:00:10.00", stage="X")
        assert tracker.snapshot()["percent"] == 0.0


class TestCallbackBehavior:
    def test_callback_invoked_on_update(self) -> None:
        cb = MagicMock()
        tracker = FinalizationProgressTracker()
        tracker.set_callback(cb)
        tracker.update(percent=42.5, stage="Шаг")
        cb.assert_called_once()
        args = cb.call_args.args
        assert args[0] == 42.5
        assert args[1] == "Шаг"

    def test_callback_called_outside_lock(self) -> None:
        # Колбэк не должен держать lock — используем Event как индикатор
        tracker = FinalizationProgressTracker()
        entered_cb = threading.Event()

        def cb(percent: float, stage: str) -> None:
            tracker.snapshot()  # не должно блокироваться
            entered_cb.set()

        tracker.set_callback(cb)
        tracker.update(percent=10.0, stage="x")
        assert entered_cb.is_set()

    def test_callback_exception_does_not_propagate(self) -> None:
        def failing(percent: float, stage: str) -> None:
            raise RuntimeError("boom")

        tracker = FinalizationProgressTracker()
        tracker.set_callback(failing)
        tracker.update(percent=5.0, stage="x")  # не должно упасть


class TestThreadSafety:
    def test_concurrent_updates(self) -> None:
        tracker = FinalizationProgressTracker()
        errors: list[Exception] = []

        def worker(start: int) -> None:
            try:
                for i in range(100):
                    tracker.update(percent=float((start + i) % 100))
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(i,)) for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        snap_percent = float(tracker.snapshot()["percent"])
        assert 0.0 <= snap_percent <= 100.0
