"""
Пакет автоматического обновления приложения (Issue #128).
========================================================
"""

from core.updater.github_client import (
    GitHubReleaseClient,
    is_version_newer,
    normalize_version,
)
from core.updater.patcher import UpdatePatcher, calculate_sha256
from core.updater.types import (
    DownloadProgress,
    ReleaseAsset,
    ReleaseInfo,
    UpdateCheckResult,
    UpdateStatus,
)
from core.updater.updater import AppUpdater

__all__ = [
    "AppUpdater",
    "DownloadProgress",
    "GitHubReleaseClient",
    "ReleaseAsset",
    "ReleaseInfo",
    "UpdateCheckResult",
    "UpdatePatcher",
    "UpdateStatus",
    "calculate_sha256",
    "is_version_newer",
    "normalize_version",
]
