"""
Типы и структуры данных подсистемы автоматического обновления (Issue #128).
==========================================================================
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class UpdateStatus(StrEnum):
    """Статусы жизненного цикла обновления."""

    IDLE = "idle"
    CHECKING = "checking"
    UPDATE_AVAILABLE = "update_available"
    NO_UPDATE = "no_update"
    DOWNLOADING = "downloading"
    READY_TO_INSTALL = "ready_to_install"
    INSTALLING = "installing"
    ERROR = "error"


@dataclass
class ReleaseAsset:
    """Информация об артефакте релиза."""

    name: str
    download_url: str
    size_bytes: int = 0
    content_type: str = "application/octet-stream"
    sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReleaseInfo:
    """Информация о релизе GitHub."""

    version: str
    tag_name: str
    name: str
    release_notes: str
    published_at: str
    is_prerelease: bool = False
    assets: list[ReleaseAsset] = field(default_factory=list)
    primary_download_url: str | None = None
    sha256_checksum: str | None = None
    size_bytes: int = 0
    is_delta: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "tag_name": self.tag_name,
            "name": self.name,
            "release_notes": self.release_notes,
            "published_at": self.published_at,
            "is_prerelease": self.is_prerelease,
            "assets": [a.to_dict() for a in self.assets],
            "primary_download_url": self.primary_download_url,
            "sha256_checksum": self.sha256_checksum,
            "size_bytes": self.size_bytes,
            "is_delta": self.is_delta,
        }


@dataclass
class UpdateCheckResult:
    """Результат проверки обновлений."""

    update_available: bool
    current_version: str
    latest_release: ReleaseInfo | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "update_available": self.update_available,
            "current_version": self.current_version,
            "latest_release": (
                self.latest_release.to_dict() if self.latest_release else None
            ),
            "error": self.error,
        }


@dataclass
class DownloadProgress:
    """Прогресс скачивания обновления."""

    total_bytes: int
    downloaded_bytes: int
    percent: float = 0.0
    speed_bytes_per_sec: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
