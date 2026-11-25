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
from core.updater.rollback import (
    UpdateState,
    confirm_pending_update,
    pop_rollback_notice,
    read_rollback_notice,
    read_update_state,
)
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
    "UpdateState",
    "UpdateStatus",
    "calculate_sha256",
    "confirm_pending_update",
    "is_version_newer",
    "normalize_version",
    "pop_rollback_notice",
    "read_rollback_notice",
    "read_update_state",
]
