"""
Unit-тесты оркестратора обновлений AppUpdater (core/updater/updater.py).
======================================================================
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from core.event_bus import InMemoryEventBus
from core.updater.types import (
    ReleaseInfo,
    UpdateCheckResult,
    UpdateStatus,
)
from core.updater.updater import AppUpdater


class TestAppUpdater:
    """Тесты AppUpdater."""

    def test_init_state(self) -> None:
        updater = AppUpdater()
        assert updater.status == UpdateStatus.IDLE
        assert updater.latest_release is None

    def test_check_for_updates_available_publishes_event(self) -> None:
        from core.event_bus import RecordingEventType

        event_bus = InMemoryEventBus()
        events: list[dict] = []
        event_bus.subscribe(
            RecordingEventType.STATUS, lambda e: events.append(e.payload)
        )

        mock_client = MagicMock()
        mock_release = ReleaseInfo(
            version="2.0.0",
            tag_name="v2.0.0",
            name="2.0.0",
            release_notes="Notes",
            published_at="2026-08-18",
            primary_download_url="https://example.com/v2.zip",
        )
        mock_client.check_for_updates.return_value = UpdateCheckResult(
            update_available=True,
            current_version="1.0.0",
            latest_release=mock_release,
        )

        updater = AppUpdater(event_bus=event_bus, github_client=mock_client)
        result = updater.check_for_updates()

        assert result.update_available is True
        assert updater.status == UpdateStatus.UPDATE_AVAILABLE
        assert len(events) == 1
        assert events[0]["version"] == "2.0.0"

    def test_download_update_flow(self, tmp_path: Path) -> None:
        from core.event_bus import RecordingEventType

        event_bus = InMemoryEventBus()
        events: list[dict] = []
        event_bus.subscribe(
            RecordingEventType.STATUS, lambda e: events.append(e.payload)
        )

        mock_patcher = MagicMock()
        mock_patcher.download_dir = tmp_path
        mock_patcher.download_file.return_value = True

        mock_release = ReleaseInfo(
            version="2.0.0",
            tag_name="v2.0.0",
            name="2.0.0",
            release_notes="Notes",
            published_at="2026-08-18",
            primary_download_url="https://example.com/v2.zip",
        )

        updater = AppUpdater(event_bus=event_bus, patcher=mock_patcher)
        success = updater.download_update(release=mock_release)

        assert success is True
        assert updater.status == UpdateStatus.READY_TO_INSTALL
        assert len(events) == 1

    def test_apply_update_delegates_to_patcher(self, tmp_path: Path) -> None:
        mock_patcher = MagicMock()
        fake_archive = tmp_path / "mia_update_2.0.0.zip"
        fake_archive.write_bytes(b"content")

        mock_patcher.generate_powershell_updater.return_value = (
            tmp_path / "apply_update.ps1"
        )
        mock_patcher.launch_powershell_updater.return_value = True

        updater = AppUpdater(patcher=mock_patcher)
        updater._downloaded_file = fake_archive

        applied = updater.apply_update()
        assert applied is True
        assert updater.status == UpdateStatus.INSTALLING
