"""
Протокол облачного провайдера хранилища (Issue #54).
===================================================
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from core.cloud.models import CloudUploadResult


@runtime_checkable
class CloudStorageProvider(Protocol):
    """Интерфейс облачного хранилища."""

    @property
    def name(self) -> str:
        """Имя или тип провайдера (напр. 's3', 'webdav')."""
        ...

    def configure(self, credentials: dict[str, Any]) -> bool:
        """Настройка параметров доступа (ключи, токены, bucket, URL)."""
        ...

    def test_connection(self) -> bool:
        """Проверка доступности удалённого хранилища."""
        ...

    def upload_file(
        self,
        local_path: Path,
        remote_path: str,
        progress_callback: Callable[[float], None] | None = None,
    ) -> CloudUploadResult:
        """Загрузка файла в облако."""
        ...
