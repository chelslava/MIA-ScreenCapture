"""
Модели данных для облачной синхронизации (Issue #54).
===================================================
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class CloudProvider(StrEnum):
    """Поддерживаемые типы облачных провайдеров."""

    S3 = "s3"
    WEBDAV = "webdav"
    GDRIVE = "gdrive"
    ONEDRIVE = "onedrive"


@dataclass
class CloudUploadResult:
    """Результат загрузки файла в облако."""

    success: bool
    remote_path: str | None = None
    remote_url: str | None = None
    size_bytes: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SyncItemState:
    """Состояние синхронизации конкретного файла."""

    file_path: str
    status: str = "pending"  # pending, uploading, completed, failed
    progress: float = 0.0
    remote_url: str | None = None
    last_sync: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
