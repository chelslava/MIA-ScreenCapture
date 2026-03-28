"""Тесты устойчивого завершения FFmpeg writer."""

import io
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from recorder.ffmpeg_writer import FFmpegVideoWriter


class TestFFmpegVideoWriterClose:
    """Проверки сценариев завершения процесса FFmpeg."""

    def test_close_uses_terminate_after_soft_timeout(self) -> None:
        """После таймаута мягкого ожидания должен использоваться terminate."""
        writer = FFmpegVideoWriter(
            output_path=Path("test.mp4"),
            width=1920,
            height=1080,
            fps=30,
        )
        process = MagicMock()
        process.stdin = MagicMock()
        process.stderr = io.BytesIO(b"")
        process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="ffmpeg", timeout=180),
            None,
        ]
        process.returncode = 0
        writer._process = process

        assert writer.close() is True
        process.terminate.assert_called_once()
        process.kill.assert_not_called()

    def test_close_kills_process_after_terminate_timeout(self) -> None:
        """Если terminate не помог, процесс должен быть принудительно убит."""
        writer = FFmpegVideoWriter(
            output_path=Path("test.mp4"),
            width=1920,
            height=1080,
            fps=30,
        )
        process = MagicMock()
        process.stdin = MagicMock()
        process.stderr = io.BytesIO(b"")
        process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="ffmpeg", timeout=180),
            subprocess.TimeoutExpired(cmd="ffmpeg", timeout=15),
        ]
        process.returncode = None
        writer._process = process

        assert writer.close() is False
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
