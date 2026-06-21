"""Тесты диагностики FFmpeg writer."""

import io
import logging
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import recorder.ffmpeg_writer as ffmpeg_writer_module
from recorder.ffmpeg_writer import FFmpegVideoWriter


class _ImmediateThread:
    """Синхронная замена потока для детерминированных unit-тестов."""

    def __init__(
        self,
        target,
        args: tuple = (),
        kwargs: dict | None = None,
        daemon: bool | None = None,
        name: str | None = None,
    ) -> None:
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}
        self.daemon = daemon
        self.name = name

    def start(self) -> None:
        """Выполнение target сразу в текущем потоке."""
        self._target(*self._args, **self._kwargs)


class _JoinTrackingThread:
    """Псевдопоток для проверки корректного join при close()."""

    instances: list["_JoinTrackingThread"] = []

    def __init__(
        self,
        target,
        args: tuple = (),
        kwargs: dict | None = None,
        daemon: bool | None = None,
        name: str | None = None,
    ) -> None:
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}
        self.daemon = daemon
        self.name = name
        self._alive = False
        self.started = False
        self.joined = False
        self.__class__.instances.append(self)

    def start(self) -> None:
        """Эмулирует запуск фонового потока без выполнения target."""
        self.started = True
        self._alive = True

    def is_alive(self) -> bool:
        """Возвращает состояние «живого» потока."""
        return self._alive

    def join(self, timeout: float | None = None) -> None:
        """Эмулирует успешное завершение потока при join."""
        _ = timeout
        self.joined = True
        self._alive = False


def _make_process(stderr_text: str, returncode: int | None) -> MagicMock:
    process = MagicMock()
    process.stdin = MagicMock()
    process.stderr = io.StringIO(stderr_text)
    process.poll.return_value = None
    process.wait.return_value = None
    process.returncode = returncode
    process.terminate = MagicMock()
    process.kill = MagicMock()
    return process


def _setup_open_mocks(
    monkeypatch,
    stderr_text: str,
    returncode: int | None,
) -> MagicMock:
    monkeypatch.setattr(ffmpeg_writer_module, "_FFMPEG_STDERR_TAIL_LINES", 3)
    monkeypatch.setattr(
        ffmpeg_writer_module.threading,
        "Thread",
        _ImmediateThread,
    )
    monkeypatch.setattr(
        ffmpeg_writer_module,
        "get_ffmpeg_path",
        MagicMock(return_value=r"C:\Tools\ffmpeg\bin\ffmpeg.exe"),
    )

    process = _make_process(stderr_text, returncode)
    monkeypatch.setattr(
        ffmpeg_writer_module.subprocess,
        "Popen",
        MagicMock(return_value=process),
    )
    return process


class TestFFmpegVideoWriterDiagnostics:
    """Проверки безопасного сбора stderr FFmpeg."""

    def test_open_collects_stderr_tail_in_background(
        self,
        monkeypatch,
    ) -> None:
        """Открытие должно включать stderr pipe и собирать хвост строк."""
        process = _setup_open_mocks(
            monkeypatch,
            "line1\nline2\nline3\nline4\n",
            returncode=0,
        )

        writer = FFmpegVideoWriter(
            output_path=Path("test.mp4"),
            width=1920,
            height=1080,
            fps=30,
        )

        assert writer.open() is True

        assert process.stdin is not None
        assert list(writer._stderr_tail) == ["line2", "line3", "line4"]

        popen_args = ffmpeg_writer_module.subprocess.Popen.call_args.args
        popen_kwargs = ffmpeg_writer_module.subprocess.Popen.call_args.kwargs
        assert popen_args[0][0] == r"C:\Tools\ffmpeg\bin\ffmpeg.exe"
        assert popen_kwargs["stderr"] == subprocess.PIPE
        assert popen_kwargs["stdout"] == subprocess.DEVNULL
        assert popen_kwargs["text"] is False
        assert "encoding" not in popen_kwargs
        assert "errors" not in popen_kwargs
        assert popen_kwargs["bufsize"] == 0

    def test_open_fails_without_ffmpeg_path(
        self,
        monkeypatch,
    ) -> None:
        """Открытие должно завершаться ошибкой без пути к FFmpeg."""
        monkeypatch.setattr(
            ffmpeg_writer_module,
            "get_ffmpeg_path",
            MagicMock(return_value=None),
        )
        monkeypatch.setattr(
            ffmpeg_writer_module.subprocess,
            "Popen",
            MagicMock(),
        )

        writer = FFmpegVideoWriter(
            output_path=Path("test.mp4"),
            width=1920,
            height=1080,
            fps=30,
        )

        assert writer.open() is False
        ffmpeg_writer_module.subprocess.Popen.assert_not_called()

    def test_close_logs_stderr_tail_on_error(
        self,
        monkeypatch,
        caplog,
    ) -> None:
        """При ошибочном завершении должен логироваться хвост stderr."""
        _setup_open_mocks(
            monkeypatch,
            "line1\nline2\nline3\nline4\n",
            returncode=1,
        )

        writer = FFmpegVideoWriter(
            output_path=Path("test.mp4"),
            width=1920,
            height=1080,
            fps=30,
        )

        assert writer.open() is True

        with caplog.at_level(logging.ERROR):
            assert writer.close() is False

        assert "FFmpeg stderr tail после ошибочное завершение" in caplog.text
        assert "line1" not in caplog.text
        assert "line2" in caplog.text
        assert "line4" in caplog.text

    def test_close_logs_stderr_tail_on_timeout(
        self,
        monkeypatch,
        caplog,
    ) -> None:
        """При таймауте завершения должен логироваться хвост stderr."""
        process = _setup_open_mocks(
            monkeypatch,
            "alpha\nbeta\ngamma\ndelta\n",
            returncode=None,
        )
        process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="ffmpeg", timeout=180),
            subprocess.TimeoutExpired(cmd="ffmpeg", timeout=15),
        ]

        writer = FFmpegVideoWriter(
            output_path=Path("test.mp4"),
            width=1920,
            height=1080,
            fps=30,
        )

        assert writer.open() is True

        with caplog.at_level(logging.ERROR):
            assert writer.close() is False

        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        assert "FFmpeg stderr tail после таймаут завершения" in caplog.text
        assert "alpha" not in caplog.text
        assert "beta" in caplog.text
        assert "delta" in caplog.text

    def test_write_returns_false_and_marks_corrupted_when_process_died(
        self,
        monkeypatch,
    ) -> None:
        """write() пытается восстановиться, но помечает corrupted, если
        перезапущенный процесс снова оказывается мёртв на каждой попытке."""
        monkeypatch.setattr(
            ffmpeg_writer_module, "_FFMPEG_STDERR_TAIL_LINES", 3
        )
        monkeypatch.setattr(
            ffmpeg_writer_module.threading,
            "Thread",
            _ImmediateThread,
        )
        monkeypatch.setattr(ffmpeg_writer_module.time, "sleep", lambda s: None)

        process = MagicMock()
        process.stdin = MagicMock()
        process.stderr = io.StringIO("")
        process.poll.return_value = None
        process.wait.return_value = None
        process.returncode = 0
        process.terminate = MagicMock()
        process.kill = MagicMock()

        monkeypatch.setattr(
            ffmpeg_writer_module,
            "get_ffmpeg_path",
            MagicMock(return_value=r"C:\Tools\ffmpeg\bin\ffmpeg.exe"),
        )
        popen_mock = MagicMock(return_value=process)
        monkeypatch.setattr(
            ffmpeg_writer_module.subprocess,
            "Popen",
            popen_mock,
        )

        writer = FFmpegVideoWriter(
            output_path=Path("test.mp4"),
            width=640,
            height=480,
            fps=30,
        )
        assert writer.open() is True

        # Симулируем смерть процесса после open() — каждая попытка
        # восстановления снова получает "мёртвый" процесс.
        process.poll.return_value = 1

        import numpy as np

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = writer.write(frame)

        assert result is False
        assert writer.is_corrupted is True
        process.stdin.write.assert_not_called()
        # 1 исходный open() + 3 попытки восстановления (max_recovery_attempts=3)
        assert popen_mock.call_count == 4
        assert writer.recovery_count == 3

    def test_write_recovers_after_single_ffmpeg_crash(
        self,
        monkeypatch,
    ) -> None:
        """write() восстанавливается после одного сбоя, открывая новый сегмент."""
        monkeypatch.setattr(
            ffmpeg_writer_module, "_FFMPEG_STDERR_TAIL_LINES", 3
        )
        monkeypatch.setattr(
            ffmpeg_writer_module.threading,
            "Thread",
            _ImmediateThread,
        )
        monkeypatch.setattr(ffmpeg_writer_module.time, "sleep", lambda s: None)

        dead_process = MagicMock()
        dead_process.stdin = MagicMock()
        dead_process.stderr = io.StringIO("")
        dead_process.poll.return_value = None
        dead_process.wait.return_value = None
        dead_process.returncode = 0
        dead_process.terminate = MagicMock()
        dead_process.kill = MagicMock()

        alive_process = MagicMock()
        alive_process.stdin = MagicMock()
        alive_process.stderr = io.StringIO("")
        alive_process.poll.return_value = None
        alive_process.wait.return_value = None
        alive_process.returncode = 0

        monkeypatch.setattr(
            ffmpeg_writer_module,
            "get_ffmpeg_path",
            MagicMock(return_value=r"C:\Tools\ffmpeg\bin\ffmpeg.exe"),
        )
        monkeypatch.setattr(
            ffmpeg_writer_module.subprocess,
            "Popen",
            MagicMock(side_effect=[dead_process, alive_process]),
        )

        writer = FFmpegVideoWriter(
            output_path=Path("test.mp4"),
            width=640,
            height=480,
            fps=30,
        )
        assert writer.open() is True

        # Симулируем смерть процесса после open()
        dead_process.poll.return_value = 1

        import numpy as np

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = writer.write(frame)

        assert result is True
        assert writer.is_corrupted is False
        assert writer.recovery_count == 1
        assert writer.segment_paths == [
            Path("test.mp4"),
            Path("test_part2.mp4"),
        ]
        alive_process.stdin.write.assert_called_once()
        dead_process.stdin.write.assert_not_called()

    def test_segment_path_naming(self) -> None:
        """_next_segment_path() генерирует имена part2, part3, ..."""
        writer = FFmpegVideoWriter(
            output_path=Path("recording.mp4"),
            width=640,
            height=480,
            fps=30,
        )

        assert writer._next_segment_path() == Path("recording_part2.mp4")

        writer._segment_paths.append(Path("recording.mp4"))
        assert writer._next_segment_path() == Path("recording_part3.mp4")

        writer._segment_paths.append(Path("recording_part2.mp4"))
        assert writer._next_segment_path() == Path("recording_part4.mp4")

    def test_close_logs_segment_summary_when_recovered(
        self,
        monkeypatch,
        caplog,
    ) -> None:
        """close() логирует сводку по сегментам, если было восстановление."""
        monkeypatch.setattr(
            ffmpeg_writer_module.threading,
            "Thread",
            _ImmediateThread,
        )

        process = MagicMock()
        process.stdin = MagicMock()
        process.stderr = io.StringIO("")
        process.poll.return_value = None
        process.wait.return_value = None
        process.returncode = 0

        writer = FFmpegVideoWriter(
            output_path=Path("test.mp4"),
            width=640,
            height=480,
            fps=30,
        )
        writer._process = process
        writer._segment_paths = [Path("test.mp4")]
        writer._current_segment_path = Path("test_part2.mp4")
        writer._recovery_count = 1

        with caplog.at_level(logging.INFO):
            assert writer.close() is True

        assert "восстановлена после 1 сбоев" in caplog.text
        assert "test_part2.mp4" in caplog.text

    def test_multiple_open_close_joins_stderr_reader(
        self,
        monkeypatch,
    ) -> None:
        """Проверка отсутствия утечек stderr-reader при повторных open/close."""
        _JoinTrackingThread.instances.clear()
        monkeypatch.setattr(
            ffmpeg_writer_module.threading,
            "Thread",
            _JoinTrackingThread,
        )
        monkeypatch.setattr(
            ffmpeg_writer_module,
            "get_ffmpeg_path",
            MagicMock(return_value=r"C:\Tools\ffmpeg\bin\ffmpeg.exe"),
        )

        processes: list[MagicMock] = []
        for _ in range(3):
            process = MagicMock()
            process.stdin = MagicMock()
            process.stderr = MagicMock()
            process.poll.return_value = None
            process.wait.return_value = None
            process.returncode = 0
            process.terminate = MagicMock()
            process.kill = MagicMock()
            processes.append(process)

        monkeypatch.setattr(
            ffmpeg_writer_module.subprocess,
            "Popen",
            MagicMock(side_effect=processes),
        )

        writer = FFmpegVideoWriter(
            output_path=Path("test.mp4"),
            width=1920,
            height=1080,
            fps=30,
        )

        for _ in range(3):
            assert writer.open() is True
            assert writer.close() is True

        assert len(_JoinTrackingThread.instances) == 3
        assert all(thread.started for thread in _JoinTrackingThread.instances)
        assert all(thread.joined for thread in _JoinTrackingThread.instances)
        assert writer._stderr_reader is None
        assert writer._stderr_stream is None
        for process in processes:
            process.stderr.close.assert_called_once()


class TestRetryPolicy:
    """Проверки dataclass RetryPolicy."""

    def test_default_values(self) -> None:
        from recorder.ffmpeg_writer import RetryPolicy

        policy = RetryPolicy()
        assert policy.max_attempts == 3
        assert policy.initial_delay_s == 0.5
        assert policy.backoff_factor == 2.0
        assert policy.max_delay_s == 10.0

    def test_custom_values(self) -> None:
        from recorder.ffmpeg_writer import RetryPolicy

        policy = RetryPolicy(
            max_attempts=5,
            initial_delay_s=1.0,
            backoff_factor=3.0,
            max_delay_s=30.0,
        )
        assert policy.max_attempts == 5
        assert policy.initial_delay_s == 1.0
        assert policy.backoff_factor == 3.0
        assert policy.max_delay_s == 30.0


class TestRetryWithBackoff:
    """Проверки функции retry_with_backoff."""

    def test_success_on_first_attempt(self, monkeypatch) -> None:
        from recorder.ffmpeg_writer import RetryPolicy, retry_with_backoff

        sleep_calls: list[float] = []
        monkeypatch.setattr(
            "recorder.ffmpeg_writer.time.sleep",
            lambda s: sleep_calls.append(s),
        )

        call_count = 0

        def fn() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        result = retry_with_backoff(fn, RetryPolicy())
        assert result == "ok"
        assert call_count == 1
        assert sleep_calls == []

    def test_retries_on_ioerror_and_succeeds(self, monkeypatch) -> None:
        from recorder.ffmpeg_writer import RetryPolicy, retry_with_backoff

        sleep_calls: list[float] = []
        monkeypatch.setattr(
            "recorder.ffmpeg_writer.time.sleep",
            lambda s: sleep_calls.append(s),
        )

        call_count = 0

        def fn() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OSError("pipe busy")
            return "ok"

        result = retry_with_backoff(
            fn,
            RetryPolicy(
                max_attempts=3, initial_delay_s=0.1, backoff_factor=2.0
            ),
        )
        assert result == "ok"
        assert call_count == 3
        assert len(sleep_calls) == 2
        assert sleep_calls[0] == pytest.approx(0.1)
        assert sleep_calls[1] == pytest.approx(0.2)

    def test_raises_after_all_attempts_exhausted(self, monkeypatch) -> None:
        from recorder.ffmpeg_writer import RetryPolicy, retry_with_backoff

        monkeypatch.setattr(
            "recorder.ffmpeg_writer.time.sleep", lambda s: None
        )

        call_count = 0

        def fn() -> None:
            nonlocal call_count
            call_count += 1
            raise OSError("disk full")

        with pytest.raises(OSError, match="disk full"):
            retry_with_backoff(fn, RetryPolicy(max_attempts=3))
        assert call_count == 3

    def test_non_retriable_exception_propagates_immediately(
        self, monkeypatch
    ) -> None:
        from recorder.ffmpeg_writer import RetryPolicy, retry_with_backoff

        sleep_calls: list[float] = []
        monkeypatch.setattr(
            "recorder.ffmpeg_writer.time.sleep",
            lambda s: sleep_calls.append(s),
        )

        call_count = 0

        def fn() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("not retriable")

        with pytest.raises(ValueError, match="not retriable"):
            retry_with_backoff(fn, RetryPolicy(max_attempts=3))
        assert call_count == 1
        assert sleep_calls == []

    def test_delay_capped_at_max_delay(self, monkeypatch) -> None:
        from recorder.ffmpeg_writer import RetryPolicy, retry_with_backoff

        sleep_calls: list[float] = []
        monkeypatch.setattr(
            "recorder.ffmpeg_writer.time.sleep",
            lambda s: sleep_calls.append(s),
        )

        call_count = 0

        def fn() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 5:
                raise OSError("err")
            return "ok"

        policy = RetryPolicy(
            max_attempts=5,
            initial_delay_s=1.0,
            backoff_factor=10.0,
            max_delay_s=5.0,
        )
        result = retry_with_backoff(fn, policy)
        assert result == "ok"
        assert len(sleep_calls) == 4
        assert all(s <= 5.0 for s in sleep_calls)
        assert sleep_calls[1] == pytest.approx(5.0)

    def test_logs_warning_on_each_retry(self, monkeypatch, caplog) -> None:
        import logging

        from recorder.ffmpeg_writer import RetryPolicy, retry_with_backoff

        monkeypatch.setattr(
            "recorder.ffmpeg_writer.time.sleep", lambda s: None
        )

        call_count = 0

        def fn() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OSError(f"err {call_count}")
            return "ok"

        with caplog.at_level(logging.WARNING, logger="recorder.ffmpeg_writer"):
            retry_with_backoff(
                fn, RetryPolicy(max_attempts=3, initial_delay_s=0.1)
            )

        warning_msgs = [
            r.message for r in caplog.records if r.levelno == logging.WARNING
        ]
        assert len(warning_msgs) == 2
        assert "1/3" in warning_msgs[0]
        assert "2/3" in warning_msgs[1]

    def test_write_retries_on_ioerror(self, monkeypatch) -> None:
        """write() использует retry_with_backoff при IOError записи в stdin."""
        import numpy as np

        from recorder.ffmpeg_writer import FFmpegVideoWriter, RetryPolicy

        sleep_calls: list[float] = []
        monkeypatch.setattr(
            "recorder.ffmpeg_writer.time.sleep",
            lambda s: sleep_calls.append(s),
        )
        monkeypatch.setattr(
            ffmpeg_writer_module, "_FFMPEG_STDERR_TAIL_LINES", 3
        )
        monkeypatch.setattr(
            ffmpeg_writer_module.threading, "Thread", _ImmediateThread
        )

        write_count = 0

        def failing_write(data: bytes) -> None:
            nonlocal write_count
            write_count += 1
            if write_count == 1:
                raise OSError("write failed once")

        process = MagicMock()
        process.stdin = MagicMock()
        process.stdin.write = failing_write
        process.stderr = io.StringIO("")
        process.poll.return_value = None
        process.wait.return_value = None
        process.returncode = 0

        monkeypatch.setattr(
            ffmpeg_writer_module,
            "get_ffmpeg_path",
            MagicMock(return_value=r"C:\ffmpeg.exe"),
        )
        monkeypatch.setattr(
            ffmpeg_writer_module.subprocess,
            "Popen",
            MagicMock(return_value=process),
        )

        policy = RetryPolicy(
            max_attempts=3, initial_delay_s=0.05, backoff_factor=2.0
        )
        writer = FFmpegVideoWriter(
            output_path=Path("test.mp4"),
            width=640,
            height=480,
            fps=30,
            retry_policy=policy,
        )
        assert writer.open() is True

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = writer.write(frame)

        assert result is True
        assert write_count == 2
        assert len(sleep_calls) == 1
        assert writer.frame_count == 1

    def test_write_marks_corrupted_after_all_retries_fail(
        self, monkeypatch
    ) -> None:
        """write() помечает файл corrupted после исчерпания всех retry."""
        import numpy as np

        from recorder.ffmpeg_writer import FFmpegVideoWriter, RetryPolicy

        monkeypatch.setattr(
            "recorder.ffmpeg_writer.time.sleep", lambda s: None
        )
        monkeypatch.setattr(
            ffmpeg_writer_module, "_FFMPEG_STDERR_TAIL_LINES", 3
        )
        monkeypatch.setattr(
            ffmpeg_writer_module.threading, "Thread", _ImmediateThread
        )

        process = MagicMock()
        process.stdin = MagicMock()
        process.stdin.write.side_effect = OSError("disk full")
        process.stderr = io.StringIO("")
        process.poll.return_value = None
        process.wait.return_value = None
        process.returncode = 0

        monkeypatch.setattr(
            ffmpeg_writer_module,
            "get_ffmpeg_path",
            MagicMock(return_value=r"C:\ffmpeg.exe"),
        )
        monkeypatch.setattr(
            ffmpeg_writer_module.subprocess,
            "Popen",
            MagicMock(return_value=process),
        )

        policy = RetryPolicy(max_attempts=2, initial_delay_s=0.0)
        writer = FFmpegVideoWriter(
            output_path=Path("test.mp4"),
            width=640,
            height=480,
            fps=30,
            retry_policy=policy,
        )
        assert writer.open() is True

        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        result = writer.write(frame)

        assert result is False
        assert writer.is_corrupted is True
        assert process.stdin.write.call_count == 2
