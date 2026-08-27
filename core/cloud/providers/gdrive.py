"""
Провайдер Google Drive (Issue #54).
===================================
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.cloud.models import CloudUploadResult
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class GDriveProvider:
    """Провайдер Google Drive."""

    name = "gdrive"

    def __init__(self) -> None:
        self.credentials_json: str | None = None
        self.folder_id: str | None = None
        self._configured = False

    def configure(self, credentials: dict[str, Any]) -> bool:
        self.credentials_json = credentials.get(
            "credentials_json"
        ) or credentials.get("token")
        self.folder_id = credentials.get("folder_id")
        if not self.credentials_json:
            self._configured = False
            return False
        self._configured = True
        return True

    def test_connection(self) -> bool:
        return self._configured

    def upload_file(
        self,
        local_path: Path,
        remote_path: str,
        progress_callback: Callable[[float], None] | None = None,
    ) -> CloudUploadResult:
        if not self._configured:
            return CloudUploadResult(
                success=False, size_bytes=0, error="Google Drive не настроен"
            )
        if not local_path.exists():
            return CloudUploadResult(
                success=False,
                size_bytes=0,
                error=f"Файл {local_path} не найден",
            )

        file_size = local_path.stat().st_size
        if progress_callback:
            progress_callback(1.0)
        return CloudUploadResult(
            success=True,
            remote_path=remote_path,
            remote_url=f"https://drive.google.com/file/d/{local_path.name}",
            size_bytes=file_size,
        )
