"""
Модели данных для библиотеки записей (Issue #119).
=================================================
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class RecordingMetadata:
    """Метаданные видеозаписи в библиотеке."""

    path: Path
    duration_sec: float = 0.0
    size_bytes: int = 0
    width: int = 0
    height: int = 0
    fps: float = 0.0
    codec: str = "unknown"
    audio_codec: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    thumbnail_path: Path | None = None
    tags: list[str] = field(default_factory=list)

    @property
    def filename(self) -> str:
        """Имя файла видеозаписи."""
        return self.path.name

    @property
    def resolution_str(self) -> str:
        """Строковое представление разрешения (напр. '1920x1080')."""
        if self.width > 0 and self.height > 0:
            return f"{self.width}x{self.height}"
        return "н/д"

    @property
    def duration_str(self) -> str:
        """Форматированная длительность (напр. '02:45' или '01:15:30')."""
        total = int(self.duration_sec)
        hrs = total // 3600
        mins = (total % 3600) // 60
        secs = total % 60
        if hrs > 0:
            return f"{hrs:02d}:{mins:02d}:{secs:02d}"
        return f"{mins:02d}:{secs:02d}"

    @property
    def size_mb_str(self) -> str:
        """Размер файла в мегабайтах."""
        mb = self.size_bytes / (1024 * 1024)
        if mb >= 1024:
            return f"{mb / 1024:.2f} GB"
        return f"{mb:.1f} MB"

    def to_dict(self) -> dict[str, Any]:
        """Сериализация в словарь для JSON/API."""
        res = asdict(self)
        res["path"] = str(self.path)
        res["thumbnail_path"] = (
            str(self.thumbnail_path) if self.thumbnail_path else None
        )
        res["filename"] = self.filename
        res["resolution"] = self.resolution_str
        res["duration_str"] = self.duration_str
        res["size_str"] = self.size_mb_str
        return res

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecordingMetadata:
        """Восстановление объекта из словаря."""
        path = Path(data["path"])
        thumb_raw = data.get("thumbnail_path")
        thumb = Path(thumb_raw) if thumb_raw else None
        return cls(
            path=path,
            duration_sec=float(data.get("duration_sec", 0.0)),
            size_bytes=int(data.get("size_bytes", 0)),
            width=int(data.get("width", 0)),
            height=int(data.get("height", 0)),
            fps=float(data.get("fps", 0.0)),
            codec=str(data.get("codec", "unknown")),
            audio_codec=data.get("audio_codec"),
            created_at=str(data.get("created_at", datetime.now().isoformat())),
            thumbnail_path=thumb,
            tags=list(data.get("tags", [])),
        )
