"""
Unit-тесты загрузчика и установщика обновлений (core/updater/patcher.py).
=======================================================================
"""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.updater.patcher import (
    UpdatePatcher,
    calculate_sha256,
)


class TestUpdatePatcher:
    """Тесты UpdatePatcher."""

    def test_calculate_sha256(self, tmp_path: Path) -> None:
        test_file = tmp_path / "sample.bin"
        test_content = b"MIA ScreenCapture update payload"
        test_file.write_bytes(test_content)

        expected = hashlib.sha256(test_content).hexdigest().lower()
        assert calculate_sha256(test_file) == expected

    @patch("urllib.request.urlopen")
    def test_download_file_success_with_sha256(
        self, mock_urlopen: MagicMock, tmp_path: Path
    ) -> None:
        content = b"new_version_bytes_12345"
        expected_sha = hashlib.sha256(content).hexdigest().lower()

        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": str(len(content))}
        mock_resp.read.side_effect = [content, b""]
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        patcher = UpdatePatcher(download_dir=tmp_path)
        target = tmp_path / "update.zip"

        progress_mock = MagicMock()
        success = patcher.download_file(
            url="https://example.com/update.zip",
            target_path=target,
            expected_sha256=expected_sha,
            progress_callback=progress_mock,
        )

        assert success is True
        assert target.exists()
        assert target.read_bytes() == content
        assert progress_mock.called

    @patch("urllib.request.urlopen")
    def test_download_file_sha_mismatch_fails(
        self, mock_urlopen: MagicMock, tmp_path: Path
    ) -> None:
        content = b"compromised_data"
        wrong_sha = "0" * 64

        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": str(len(content))}
        mock_resp.read.side_effect = [content, b""]
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        patcher = UpdatePatcher(download_dir=tmp_path)
        target = tmp_path / "update.zip"

        success = patcher.download_file(
            url="https://example.com/update.zip",
            target_path=target,
            expected_sha256=wrong_sha,
        )

        assert success is False
        assert not target.exists()

    @patch("urllib.request.urlopen")
    def test_download_file_cancelled(
        self, mock_urlopen: MagicMock, tmp_path: Path
    ) -> None:
        cancel_evt = threading.Event()
        cancel_evt.set()

        mock_resp = MagicMock()
        mock_resp.headers = {"Content-Length": "1000"}
        mock_resp.read.return_value = b"some data"
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        patcher = UpdatePatcher(download_dir=tmp_path)
        target = tmp_path / "update.zip"

        success = patcher.download_file(
            url="https://example.com/update.zip",
            target_path=target,
            cancel_event=cancel_evt,
        )

        assert success is False
        assert not target.exists()

    def test_generate_powershell_updater(self, tmp_path: Path) -> None:
        patcher = UpdatePatcher(download_dir=tmp_path)
        archive = tmp_path / "update.zip"
        archive.write_bytes(b"zip")

        script = patcher.generate_powershell_updater(
            archive_path=archive,
            target_dir=tmp_path / "app",
            current_pid=1234,
            restart_command=["python.exe", "main.py"],
        )

        assert script.exists()
        content = script.read_text(encoding="utf-8")
        assert "Wait-Process -Id 1234" in content
        assert "Expand-Archive" in content
        assert "python.exe" in content
