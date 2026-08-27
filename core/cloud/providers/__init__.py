"""Пакет реализаций облачных провайдеров."""

from __future__ import annotations

from core.cloud.providers.gdrive import GDriveProvider
from core.cloud.providers.onedrive import OneDriveProvider
from core.cloud.providers.s3 import S3Provider
from core.cloud.providers.webdav import WebDAVProvider

__all__ = [
    "GDriveProvider",
    "OneDriveProvider",
    "S3Provider",
    "WebDAVProvider",
]
