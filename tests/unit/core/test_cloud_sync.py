"""
Unit-тесты для облачной синхронизации (core/cloud/, Issue #54).
==============================================================
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from core.cloud.manager import CloudSyncManager
from core.cloud.models import CloudUploadResult, SyncItemState
from core.cloud.providers.gdrive import GDriveProvider
from core.cloud.providers.onedrive import OneDriveProvider
from core.cloud.providers.s3 import S3Provider
from core.cloud.providers.webdav import WebDAVProvider


def test_models_serialization() -> None:
    """Проверка сериализации моделей CloudUploadResult и SyncItemState."""
    res = CloudUploadResult(
        success=True,
        remote_path="Recordings/2026/01/video.mp4",
        remote_url="https://s3.example.com/video.mp4",
        size_bytes=1024,
    )
    d = res.to_dict()
    assert d["success"] is True
    assert d["size_bytes"] == 1024

    state = SyncItemState(
        file_path="/local/video.mp4",
        status="uploading",
        progress=0.5,
    )
    sd = state.to_dict()
    assert sd["status"] == "uploading"
    assert sd["progress"] == 0.5


def test_s3_provider(tmp_path: Path) -> None:
    """Тестирование S3Provider с моком boto3."""
    provider = S3Provider()
    assert provider.name == "s3"

    # Не настроен
    assert provider.configure({}) is False
    assert provider.test_connection() is False

    # Настройка
    creds = {
        "access_key": "fake_key",
        "secret_key": "fake_secret",
        "bucket": "my-recordings",
        "region": "eu-central-1",
    }
    assert provider.configure(creds) is True

    video = tmp_path / "test.mp4"
    video.write_bytes(b"1234567890")

    mock_boto3 = MagicMock()
    mock_s3_client = MagicMock()
    mock_boto3.client.return_value = mock_s3_client

    with patch.dict("sys.modules", {"boto3": mock_boto3}):
        assert provider.test_connection() is True

        progresses: list[float] = []
        res = provider.upload_file(
            video,
            "2026/01/test.mp4",
            progress_callback=progresses.append,
        )

        assert res.success is True
        assert res.size_bytes == 10
        mock_s3_client.upload_file.assert_called_once()


def test_webdav_provider(tmp_path: Path) -> None:
    """Тестирование WebDAVProvider с моком requests."""
    provider = WebDAVProvider()
    assert provider.name == "webdav"

    creds = {
        "url": "https://webdav.example.com/remote.php/webdav",
        "username": "user",
        "password": "pass",
    }
    assert provider.configure(creds) is True

    video = tmp_path / "test_dav.mp4"
    video.write_bytes(b"webdav content")

    mock_requests = MagicMock()
    mock_resp_propfind = MagicMock()
    mock_resp_propfind.status_code = 207
    mock_requests.request.return_value = mock_resp_propfind

    mock_resp_put = MagicMock()
    mock_resp_put.status_code = 201
    mock_requests.put.return_value = mock_resp_put

    with patch.dict("sys.modules", {"requests": mock_requests}):
        assert provider.test_connection() is True
        res = provider.upload_file(video, "Recordings/test_dav.mp4")
        assert res.success is True
        assert res.size_bytes == len(b"webdav content")


def test_gdrive_and_onedrive_providers(tmp_path: Path) -> None:
    """Тестирование провайдеров GDrive и OneDrive."""
    gdrive = GDriveProvider()
    assert gdrive.configure({"token": "fake_token"}) is True
    assert gdrive.test_connection() is True

    onedrive = OneDriveProvider()
    assert onedrive.configure({"access_token": "fake_token"}) is True
    assert onedrive.test_connection() is True

    video = tmp_path / "cloud_vid.mp4"
    video.write_bytes(b"cloud content")

    res_g = gdrive.upload_file(video, "cloud_vid.mp4")
    assert res_g.success is True

    res_o = onedrive.upload_file(video, "cloud_vid.mp4")
    assert res_o.success is True


def test_cloud_sync_manager_workflow(tmp_path: Path) -> None:
    """Полный цикл работы CloudSyncManager: очередь, загрузка, статус, персистентность."""
    cfg_file = tmp_path / "cloud_sync.json"
    manager = CloudSyncManager(config_file=cfg_file)

    # Настройка
    ok = manager.configure(
        provider_type="s3",
        credentials={"access_key": "k", "secret_key": "s", "bucket": "b"},
        auto_sync=True,
        min_file_size_mb=0.00001,
        remote_folder="Archive",
    )
    assert ok is True
    assert cfg_file.exists()

    video = tmp_path / "rec.mp4"
    video.write_bytes(b"large video recording dummy bytes")

    mock_provider = MagicMock()
    mock_provider.name = "mock_s3"
    mock_provider.test_connection.return_value = True
    mock_provider.upload_file.return_value = CloudUploadResult(
        success=True,
        remote_path="Archive/2026/08/rec.mp4",
        remote_url="https://cloud.example.com/rec.mp4",
        size_bytes=video.stat().st_size,
    )
    manager._provider = mock_provider

    assert manager.queue_upload(video) is True

    # Даем фоновому воркеру обработать
    import time

    time.sleep(0.1)

    status = manager.get_status()
    assert status["provider"] == "s3"
    assert status["auto_sync"] is True

    key = str(video.resolve())
    assert key in status["sync_status"]
    assert status["sync_status"][key]["status"] == "completed"

    manager.stop()
