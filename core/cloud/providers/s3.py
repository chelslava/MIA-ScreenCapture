"""
Провайдер хранилища Amazon S3 / MinIO (Issue #54).
=================================================
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.cloud.models import CloudUploadResult
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class S3Provider:
    """Провайдер S3-совместимого объектного хранилища."""

    name = "s3"

    def __init__(self) -> None:
        self.access_key: str | None = None
        self.secret_key: str | None = None
        self.bucket: str | None = None
        self.region: str = "us-east-1"
        self.endpoint_url: str | None = None
        self._configured = False

    def configure(self, credentials: dict[str, Any]) -> bool:
        """Настройка учётных данных S3."""
        self.access_key = credentials.get("access_key")
        self.secret_key = credentials.get("secret_key")
        self.bucket = credentials.get("bucket")
        self.region = credentials.get("region", "us-east-1")
        self.endpoint_url = credentials.get("endpoint_url")

        if not self.access_key or not self.secret_key or not self.bucket:
            self._configured = False
            return False

        self._configured = True
        return True

    def test_connection(self) -> bool:
        """Проверка соединения с S3 бакетом."""
        if not self._configured or not self.bucket:
            return False
        try:
            import importlib

            boto3 = importlib.import_module("boto3")
            s3 = boto3.client(
                "s3",
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                endpoint_url=self.endpoint_url,
            )
            s3.head_bucket(Bucket=self.bucket)
            return True
        except Exception as e:
            logger.warning("Ошибка проверки соединения S3: %s", e)
            return False

    def upload_file(
        self,
        local_path: Path,
        remote_path: str,
        progress_callback: Callable[[float], None] | None = None,
    ) -> CloudUploadResult:
        """Загрузка файла в S3 бакет."""
        if not self._configured or not self.bucket:
            return CloudUploadResult(
                success=False,
                size_bytes=0,
                error="S3 провайдер не настроен",
            )

        if not local_path.exists():
            return CloudUploadResult(
                success=False,
                size_bytes=0,
                error=f"Файл {local_path} не найден",
            )

        file_size = local_path.stat().st_size
        try:
            import importlib

            boto3 = importlib.import_module("boto3")
            s3 = boto3.client(
                "s3",
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                endpoint_url=self.endpoint_url,
            )

            uploaded_bytes = 0

            def _callback(bytes_amount: int) -> None:
                nonlocal uploaded_bytes
                uploaded_bytes += bytes_amount
                if progress_callback and file_size > 0:
                    progress_callback(min(1.0, uploaded_bytes / file_size))

            s3.upload_file(
                str(local_path),
                self.bucket,
                remote_path,
                Callback=_callback if progress_callback else None,
            )

            remote_url = f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{remote_path}"
            if self.endpoint_url:
                remote_url = f"{self.endpoint_url.rstrip('/')}/{self.bucket}/{remote_path}"

            return CloudUploadResult(
                success=True,
                remote_path=remote_path,
                remote_url=remote_url,
                size_bytes=file_size,
            )
        except Exception as e:
            logger.error("Ошибка загрузки файла в S3: %s", e)
            return CloudUploadResult(
                success=False,
                remote_path=remote_path,
                size_bytes=file_size,
                error=str(e),
            )
