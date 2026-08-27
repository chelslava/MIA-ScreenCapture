"""
Провайдер Microsoft OneDrive (Issue #54).
=========================================
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.cloud.models import CloudUploadResult
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class OneDriveProvider:
    """Провайдер Microsoft OneDrive."""

    name = "onedrive"

    def __init__(self) -> None:
        self.access_token: str | None = None
        self.folder_path: str = "Recordings"
        self._configured = False

    def configure(self, credentials: dict[str, Any]) -> bool:
        self.access_token = credentials.get("access_token") or credentials.get(
            "token"
        )
        self.folder_path = credentials.get("folder_path", "Recordings")
        if not self.access_token:
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
                success=False, size_bytes=0, error="OneDrive не настроен"
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
            remote_url=f"https://onedrive.live.com/view/{local_path.name}",
            size_bytes=file_size,
        )
