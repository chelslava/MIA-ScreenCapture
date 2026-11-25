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
        # utf-8-sig: PowerShell 5.1 требует BOM для кириллицы
        content = script.read_text(encoding="utf-8-sig")
        assert "Wait-Process -Id 1234" in content
        # Статический ZipFile::ExtractToDirectory вместо Expand-Archive:
        # баг 3-арговой перегрузки на старых runner'ах PS 5.1 (#191)
        assert "ZipFile]::ExtractToDirectory($ArchivePath, $TargetDir)" in (
            content
        )
        assert "python.exe" in content

    def test_generate_updater_contains_rollback_flow(
        self, tmp_path: Path
    ) -> None:
        """Скрипт включает backup, откат и health-check (#191)."""
        patcher = UpdatePatcher(download_dir=tmp_path)
        archive = tmp_path / "update.zip"
        archive.write_bytes(b"zip")
        backup = tmp_path / "app.backup-1"

        script = patcher.generate_powershell_updater(
            archive_path=archive,
            target_dir=tmp_path / "app",
            current_pid=1234,
            restart_command=["python.exe", str(tmp_path / "app" / "main.py")],
            version="2.1.0",
            verify_paths=["main.py", "app.exe"],
            health_timeout_s=45,
            backup_dir=backup,
        )
        content = script.read_text(encoding="utf-8-sig")

        assert "Invoke-Rollback" in content
        assert "Move-Item" in content
        assert "taskkill" in content
        assert "update_state.json" in content
        assert "update_rollback.json" in content
        assert str(backup) in content
        assert "main.py" in content and "app.exe" in content
        assert "-Milliseconds 500" in content

    def test_backup_dir_for_is_deterministic_path(
        self, tmp_path: Path
    ) -> None:
        """Backup-директория находится рядом с установкой."""
        target = tmp_path / "MIA-ScreenCapture"

        backup = UpdatePatcher.backup_dir_for(target)

        assert backup.parent == target.parent
        assert backup.name.startswith("MIA-ScreenCapture.backup-")

    def test_make_backup_restart_command_swaps_root(self) -> None:
        """Команда отката перенаправляет запуск в backup-директорию."""
        target = Path("D:/Apps/MIA-ScreenCapture")
        backup = Path("D:/Apps/MIA-ScreenCapture.backup-1")
        cmd = ["py", str(target / "main.py"), "--headless"]

        rollback_cmd = UpdatePatcher.make_backup_restart_command(
            cmd, target, backup
        )

        assert rollback_cmd == [
            "py",
            str(backup / "main.py"),
            "--headless",
        ]

    def test_cleanup_old_backups_keeps_recent(self, tmp_path: Path) -> None:
        """Ротация backup оставляет последние, удаляет старые."""
        patcher = UpdatePatcher(download_dir=tmp_path)
        target = tmp_path / "app"
        target.mkdir()
        backups = []
        for i in range(3):
            b = tmp_path / f"app.backup-{i}"
            b.mkdir()
            (b / "f.txt").write_text("x", encoding="utf-8")
            backups.append(b)
            # Гарантируем разные mtime
            import os
            import time as time_mod

            stamp = time_mod.time() + i
            os.utime(b, (stamp, stamp))

        removed = patcher.cleanup_old_backups(target, keep=1)

        assert removed == 2
        leftovers = list(tmp_path.glob("app.backup-*"))
        assert len(leftovers) == 1
        assert leftovers[0] == backups[-1]

    def test_cleanup_old_backups_nothing_to_remove(
        self, tmp_path: Path
    ) -> None:
        """Отсутствие backup — удалений нет."""
        patcher = UpdatePatcher(download_dir=tmp_path)

        assert patcher.cleanup_old_backups(tmp_path / "app") == 0
