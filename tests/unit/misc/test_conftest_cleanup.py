"""Тесты retry-очистки stale pytest-директорий (#163)."""

from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import patch

from tests import conftest  # noqa: E402  — namespace-пакет репозитория


class TestCleanupStalePytestDirs:
    """Очистка tests/.local_tmp/system/pytest_* с бэкоффом."""

    def test_removes_stale_and_keeps_fresh(self, tmp_path: Path) -> None:
        stale = tmp_path / "pytest_stale"
        stale.mkdir()
        (stale / "junk.bin").write_bytes(b"x")
        fresh = tmp_path / "pytest_fresh"
        fresh.mkdir()

        old_time = time.time() - 48 * 3600
        os.utime(stale, (old_time, old_time))

        with patch.object(conftest, "_LOCAL_SYSTEM_TMP", tmp_path):
            conftest._cleanup_stale_pytest_dirs(max_age_hours=24.0)

        assert not stale.exists()
        assert fresh.exists()

    def test_retries_on_locked_directory(self, tmp_path: Path) -> None:
        """Занятый каталог удаляется со второй попытки (backoff)."""
        stale = tmp_path / "pytest_locked"
        stale.mkdir()
        old_time = time.time() - 48 * 3600
        os.utime(stale, (old_time, old_time))

        real_rmtree = conftest.shutil.rmtree
        attempts: list[Path] = []

        def flaky_rmtree(path, *args, **kwargs):
            attempts.append(Path(path))
            if len(attempts) == 1:
                raise PermissionError(5, "Отказано в доступе")
            return real_rmtree(path, *args, **kwargs)

        with (
            patch.object(conftest, "_LOCAL_SYSTEM_TMP", tmp_path),
            patch.object(conftest.shutil, "rmtree", flaky_rmtree),
        ):
            conftest._cleanup_stale_pytest_dirs(
                retries=3, backoff_seconds=0.001
            )

        assert len(attempts) == 2
        assert not stale.exists()

    def test_persistent_lock_does_not_raise(self, tmp_path: Path) -> None:
        """Вечно занятый каталог не ломает очистку (best-effort)."""
        stale = tmp_path / "pytest_stuck"
        stale.mkdir()
        old_time = time.time() - 48 * 3600
        os.utime(stale, (old_time, old_time))

        def always_locked(path, *args, **kwargs):
            raise PermissionError(5, "Отказано в доступе")

        with (
            patch.object(conftest, "_LOCAL_SYSTEM_TMP", tmp_path),
            patch.object(conftest.shutil, "rmtree", always_locked),
        ):
            conftest._cleanup_stale_pytest_dirs(
                retries=2, backoff_seconds=0.001
            )

        assert stale.exists()
