"""Тесты диагностики FFmpeg writer."""

import io
import logging
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

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
