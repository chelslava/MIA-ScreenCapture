"""
Unit-тесты для шагов постобработки видеозаписей (Issue #118)
============================================================
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.post_processing.steps import (
    CompressStep,
    CopyToFolderStep,
    GenerateGifPreviewStep,
    OpenInExplorerStep,
    TranscodeStep,
    TrimSilenceStep,
    WebhookNotificationStep,
)
from core.post_processing.types import PostProcessingStepType


class TestTranscodeStep:
    """Тесты для шага перекодирования TranscodeStep."""

    def test_missing_input_file_returns_error(self, tmp_path: Path) -> None:
        step = TranscodeStep(target_format="webm", target_codec="libvpx-vp9")
        missing_file = tmp_path / "not_found.mp4"
        res = step.execute(missing_file)
        assert not res.success
        assert "не существует" in (res.error_message or "")
        assert res.step_type == PostProcessingStepType.TRANSCODE

    @patch("subprocess.run")
    def test_successful_transcode(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        input_file = tmp_path / "video.mp4"
        input_file.write_bytes(b"dummy video data")

        def side_effect(cmd, **kwargs):
            # create output file
            out_file = tmp_path / "video_transcoded.webm"
            out_file.write_bytes(b"transcoded video")
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        mock_run.side_effect = side_effect
        step = TranscodeStep(target_format="webm", target_codec="libvpx-vp9")
        res = step.execute(input_file)

        assert res.success
        assert res.output_path is not None
        assert res.output_path.name == "video_transcoded.webm"
        assert res.details.get("target_format") == "webm"

    @patch("subprocess.run")
    def test_transcode_ffmpeg_error(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        input_file = tmp_path / "video.mp4"
        input_file.write_bytes(b"dummy")
        mock_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="Unknown codec error"
        )
        step = TranscodeStep()
        res = step.execute(input_file)
        assert not res.success
        assert "Unknown codec error" in (res.error_message or "")

    @patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=10),
    )
    def test_transcode_timeout(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        input_file = tmp_path / "video.mp4"
        input_file.write_bytes(b"dummy")
        step = TranscodeStep(timeout_seconds=10)
        res = step.execute(input_file)
        assert not res.success
        assert "Таймаут" in (res.error_message or "")


class TestCompressStep:
    """Тесты для шага сжатия CompressStep."""

    @patch("subprocess.run")
    def test_successful_compression(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        input_file = tmp_path / "sample.mp4"
        input_file.write_bytes(b"0" * 1000)

        def side_effect(cmd, **kwargs):
            out_file = tmp_path / "sample_compressed.mp4"
            out_file.write_bytes(b"0" * 400)
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        mock_run.side_effect = side_effect
        step = CompressStep(crf=28)
        res = step.execute(input_file)

        assert res.success
        assert res.output_path is not None
        assert res.details.get("saved_percent") == 60.0


class TestTrimSilenceStep:
    """Тесты для шага обрезки тишины TrimSilenceStep."""

    @patch("subprocess.run")
    def test_successful_trim_silence(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        input_file = tmp_path / "audio_video.mp4"
        input_file.write_bytes(b"data")

        def side_effect(cmd, **kwargs):
            out_file = tmp_path / "audio_video_trimmed.mp4"
            out_file.write_bytes(b"trimmed data")
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        mock_run.side_effect = side_effect
        step = TrimSilenceStep(threshold_db=-45)
        res = step.execute(input_file)

        assert res.success
        assert res.output_path is not None
        assert res.details.get("threshold_db") == -45


class TestGenerateGifPreviewStep:
    """Тесты для шага создания GIF-превью GenerateGifPreviewStep."""

    @patch("subprocess.run")
    def test_successful_gif_generation(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        input_file = tmp_path / "clip.mp4"
        input_file.write_bytes(b"video stream")

        def side_effect(cmd, **kwargs):
            out_gif = tmp_path / "clip.gif"
            out_gif.write_bytes(b"GIF89a...")
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout="", stderr=""
            )

        mock_run.side_effect = side_effect
        step = GenerateGifPreviewStep(duration_seconds=3, fps=12)
        res = step.execute(input_file)

        assert res.success
        # Основное видео сохраняется как output_path для конвейера
        assert res.output_path == input_file
        assert "clip.gif" in res.details.get("gif_path", "")


class TestCopyToFolderStep:
    """Тесты для шага копирования CopyToFolderStep."""

    def test_empty_target_folder_error(self, tmp_path: Path) -> None:
        input_file = tmp_path / "file.mp4"
        input_file.write_bytes(b"content")
        step = CopyToFolderStep(target_folder="")
        res = step.execute(input_file)
        assert not res.success
        assert "не указана" in (res.error_message or "")

    def test_successful_copy_and_collision_handling(
        self, tmp_path: Path
    ) -> None:
        input_file = tmp_path / "record.mp4"
        input_file.write_bytes(b"video bytes")

        target_dir = tmp_path / "dest"
        target_dir.mkdir()
        # Имитируем существующий файл для проверки разрешения коллизий
        (target_dir / "record.mp4").write_bytes(b"existing")

        step = CopyToFolderStep(target_folder=target_dir)
        res = step.execute(input_file)

        assert res.success
        copied_path = Path(res.details["copied_to"])
        assert copied_path.name == "record (1).mp4"
        assert copied_path.read_bytes() == b"video bytes"


class TestOpenInExplorerStep:
    """Тесты для шага открытия проводника OpenInExplorerStep."""

    @patch("subprocess.Popen")
    def test_successful_open(
        self, mock_popen: MagicMock, tmp_path: Path
    ) -> None:
        input_file = tmp_path / "item.mp4"
        input_file.write_bytes(b"data")

        step = OpenInExplorerStep()
        res = step.execute(input_file)
        assert res.success
        mock_popen.assert_called_once()


class TestWebhookNotificationStep:
    """Тесты для шага отправки WebhookNotificationStep."""

    def test_empty_url_returns_error(self, tmp_path: Path) -> None:
        input_file = tmp_path / "rec.mp4"
        input_file.write_bytes(b"data")
        step = WebhookNotificationStep(webhook_url="")
        res = step.execute(input_file)
        assert not res.success
        assert "не указан" in (res.error_message or "")

    @patch("core.post_processing.steps.WebhookSender")
    def test_successful_webhook_send(
        self, mock_sender_cls: MagicMock, tmp_path: Path
    ) -> None:
        input_file = tmp_path / "rec.mp4"
        input_file.write_bytes(b"data")

        mock_instance = MagicMock()
        mock_instance.send.return_value = (True, 25.0)
        mock_sender_cls.return_value = mock_instance

        step = WebhookNotificationStep(
            webhook_url="https://hooks.example.com/recordings"
        )
        res = step.execute(input_file)
        assert res.success
        assert (
            res.details.get("webhook_url")
            == "https://hooks.example.com/recordings"
        )
