"""
Пакет облачной синхронизации и резервного копирования (Issue #54).
=================================================================
"""

from __future__ import annotations

from core.cloud.manager import CloudSyncManager
from core.cloud.models import CloudProvider, CloudUploadResult, SyncItemState
from core.cloud.protocol import CloudStorageProvider

__all__ = [
    "CloudProvider",
    "CloudStorageProvider",
    "CloudSyncManager",
    "CloudUploadResult",
    "SyncItemState",
]
