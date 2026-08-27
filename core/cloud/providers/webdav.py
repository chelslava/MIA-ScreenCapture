"""
Провайдер хранилища WebDAV (Nextcloud, ownCloud, Yandex.Disk и др.) (Issue #54).
=============================================================================
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.cloud.models import CloudUploadResult
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class WebDAVProvider:
    """Провайдер WebDAV хранилища."""

    name = "webdav"

    def __init__(self) -> None:
        self.url: str | None = None
        self.username: str | None = None
        self.password: str | None = None
        self._configured = False

    def configure(self, credentials: dict[str, Any]) -> bool:
        """Настройка параметров WebDAV."""
        self.url = credentials.get("url")
        self.username = credentials.get("username")
        self.password = credentials.get("password")

        if not self.url or not self.username or not self.password:
            self._configured = False
            return False

        self._configured = True
        return True

    def test_connection(self) -> bool:
        """Проверка доступности WebDAV сервера через PROPFIND / OPTIONS."""
        if not self._configured or not self.url:
            return False
        try:
            import requests

            auth = (self.username or "", self.password or "")
            resp = requests.request(
                "PROPFIND",
                self.url,
                auth=auth,
                headers={"Depth": "0"},
                timeout=10,
            )
            return resp.status_code in (200, 201, 204, 207)
        except Exception as e:
            logger.warning("Ошибка проверки соединения WebDAV: %s", e)
            return False

    def upload_file(
        self,
        local_path: Path,
        remote_path: str,
        progress_callback: Callable[[float], None] | None = None,
    ) -> CloudUploadResult:
        """Загрузка файла на WebDAV сервер через HTTP PUT."""
        if not self._configured or not self.url:
            return CloudUploadResult(
                success=False,
                size_bytes=0,
                error="WebDAV провайдер не настроен",
            )

        if not local_path.exists():
            return CloudUploadResult(
                success=False,
                size_bytes=0,
                error=f"Файл {local_path} не найден",
            )

        file_size = local_path.stat().st_size
        target_url = f"{self.url.rstrip('/')}/{remote_path.lstrip('/')}"
        try:
            import requests

            auth = (self.username or "", self.password or "")

            with open(local_path, "rb") as f:
                resp = requests.put(target_url, data=f, auth=auth, timeout=300)

            if resp.status_code in (200, 201, 204):
                if progress_callback:
                    progress_callback(1.0)
                return CloudUploadResult(
                    success=True,
                    remote_path=remote_path,
                    remote_url=target_url,
                    size_bytes=file_size,
                )
            else:
                return CloudUploadResult(
                    success=False,
                    remote_path=remote_path,
                    size_bytes=file_size,
                    error=f"HTTP {resp.status_code}: {resp.text[:200]}",
                )
        except Exception as e:
            logger.error("Ошибка загрузки файла на WebDAV: %s", e)
            return CloudUploadResult(
                success=False,
                remote_path=remote_path,
                size_bytes=file_size,
                error=str(e),
            )
