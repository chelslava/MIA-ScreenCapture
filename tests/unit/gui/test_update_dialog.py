"""
Unit-тесты диалога обновления (gui/views/update_dialog.py).
==========================================================
"""

from __future__ import annotations

from core.updater.types import DownloadProgress, ReleaseInfo
from gui.views.update_dialog import UpdateDialog


class TestUpdateDialog:
    """Тесты UpdateDialog."""

    def test_update_dialog_init(self) -> None:
        release = ReleaseInfo(
            version="2.0.0",
            tag_name="v2.0.0",
            name="Version 2.0.0",
            release_notes="* New feature 1\n* Bugfix 2",
            published_at="2026-08-18",
            size_bytes=1048576,
        )
        dialog = UpdateDialog(release_info=release)
        assert dialog.release_info.version == "2.0.0"
        assert dialog._action_btn.text() == "Скачать и установить"

    def test_progress_and_completion_states(self) -> None:
        release = ReleaseInfo(
            version="2.0.0",
            tag_name="v2.0.0",
            name="Version 2.0.0",
            release_notes="",
            published_at="2026-08-18",
        )
        dialog = UpdateDialog(release_info=release)

        dialog.set_progress(
            DownloadProgress(
                total_bytes=1000,
                downloaded_bytes=500,
                percent=50.0,
                speed_bytes_per_sec=10240,
            )
        )
        assert dialog._progress_bar.isVisible()
        assert dialog._progress_bar.value() == 50

        dialog.set_download_completed()
        assert dialog._action_btn.text() == "Перезапустить и обновить"
