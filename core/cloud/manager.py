"""
Менеджер облачной синхронизации и бэкапа записей (Issue #54).
============================================================
"""

from __future__ import annotations

import json
import queue
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from core.cloud.models import CloudProvider, CloudUploadResult, SyncItemState
from core.cloud.protocol import CloudStorageProvider
from core.cloud.providers.gdrive import GDriveProvider
from core.cloud.providers.onedrive import OneDriveProvider
from core.cloud.providers.s3 import S3Provider
from core.cloud.providers.webdav import WebDAVProvider
from core.event_bus import EventBus
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class CloudSyncManager:
    """Централизованный менеджер фоновой облачной синхронизации."""

    def __init__(
        self,
        config_file: Path | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._config_file = config_file or Path("config/cloud_sync.json")
        self._event_bus = event_bus
        self._provider: CloudStorageProvider | None = None
        self._provider_type: str = "s3"
        self._credentials: dict[str, Any] = {}
        self._auto_sync: bool = False
        self._min_file_size_mb: float = 0.0
        self._remote_folder: str = "Recordings"

        self._upload_queue: queue.Queue[Path] = queue.Queue()
        self._sync_states: dict[str, SyncItemState] = {}
        self._lock = threading.RLock()
        self._running = False
        self._worker_thread: threading.Thread | None = None

        self._load_config()
        self.start()

    @property
    def auto_sync(self) -> bool:
        return self._auto_sync

    @property
    def is_configured(self) -> bool:
        return self._provider is not None and self._provider.test_connection()

    def start(self) -> None:
        """Запуск фонового воркера синхронизации."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._worker_thread = threading.Thread(
                target=self._worker_loop,
                name="CloudSyncWorker",
                daemon=True,
            )
            self._worker_thread.start()

    def stop(self) -> None:
        """Остановка фонового воркера синхронизации."""
        with self._lock:
            self._running = False
            if self._worker_thread and self._worker_thread.is_alive():
                self._worker_thread.join(timeout=2.0)

    def create_provider(self, provider_type: str) -> CloudStorageProvider:
        """Фабрика создания провайдера хранилища."""
        p_clean = provider_type.lower()
        if p_clean == CloudProvider.WEBDAV:
            return WebDAVProvider()
        elif p_clean == CloudProvider.GDRIVE:
            return GDriveProvider()
        elif p_clean == CloudProvider.ONEDRIVE:
            return OneDriveProvider()
        else:
            return S3Provider()

    def configure(
        self,
        provider_type: str,
        credentials: dict[str, Any],
        auto_sync: bool = False,
        min_file_size_mb: float = 0.0,
        remote_folder: str = "Recordings",
    ) -> bool:
        """Настройка провайдера и параметров синхронизации."""
        with self._lock:
            provider = self.create_provider(provider_type)
            ok = provider.configure(credentials)
            if ok:
                self._provider = provider
                self._provider_type = provider_type
                self._credentials = credentials
                self._auto_sync = auto_sync
                self._min_file_size_mb = min_file_size_mb
                self._remote_folder = remote_folder
                self._save_config()
                logger.info(
                    "Облачный провайдер %s успешно настроен", provider_type
                )
                return True
            else:
                logger.warning(
                    "Не удалось настроить облачный провайдер %s", provider_type
                )
                return False

    def test_connection(self) -> bool:
        """Тест соединения с текущим провайдером."""
        with self._lock:
            if not self._provider:
                return False
            return self._provider.test_connection()

    def queue_upload(self, file_path: Path) -> bool:
        """Постановка файла в очередь на загрузку в облако."""
        resolved = file_path.resolve()
        if not resolved.exists():
            return False

        file_size_mb = resolved.stat().st_size / (1024 * 1024)
        if file_size_mb < self._min_file_size_mb:
            logger.info(
                "Файл %s (%.1f MB) пропущен (порог: %.1f MB)",
                resolved.name,
                file_size_mb,
                self._min_file_size_mb,
            )
            return False

        key = str(resolved)
        with self._lock:
            self._sync_states[key] = SyncItemState(
                file_path=key,
                status="pending",
                progress=0.0,
            )
            self._upload_queue.put(resolved)
            logger.info(
                "Файл %s добавлен в очередь облачной синхронизации",
                resolved.name,
            )
            return True

    def get_status(self) -> dict[str, Any]:
        """Возвращает статус облачной синхронизации."""
        with self._lock:
            return {
                "provider": self._provider_type,
                "is_configured": self._provider is not None,
                "auto_sync": self._auto_sync,
                "min_file_size_mb": self._min_file_size_mb,
                "remote_folder": self._remote_folder,
                "queue_size": self._upload_queue.qsize(),
                "sync_status": {
                    k: v.to_dict() for k, v in self._sync_states.items()
                },
            }

    def _worker_loop(self) -> None:
        """Главный цикл фонового воркера."""
        while self._running:
            try:
                try:
                    file_path = self._upload_queue.get(timeout=1.0)
                except queue.Empty:
                    continue

                self._process_single_upload(file_path)
                self._upload_queue.task_done()
            except Exception as e:
                logger.error("Ошибка в цикле облачной синхронизации: %s", e)

    def _process_single_upload(self, file_path: Path) -> None:
        """Загрузка одного файла."""
        key = str(file_path.resolve())
        with self._lock:
            if not self._provider:
                if key in self._sync_states:
                    self._sync_states[key].status = "failed"
                    self._sync_states[key].error = "Провайдер не настроен"
                return

            if key in self._sync_states:
                self._sync_states[key].status = "uploading"

        date_str = datetime.now().strftime("%Y/%m")
        remote_path = (
            f"{self._remote_folder.strip('/')}/{date_str}/{file_path.name}"
        )

        def _progress(prog: float) -> None:
            with self._lock:
                if key in self._sync_states:
                    self._sync_states[key].progress = prog

        res: CloudUploadResult = self._provider.upload_file(
            file_path,
            remote_path,
            progress_callback=_progress,
        )

        with self._lock:
            if key in self._sync_states:
                if res.success:
                    self._sync_states[key].status = "completed"
                    self._sync_states[key].progress = 1.0
                    self._sync_states[key].remote_url = res.remote_url
                    self._sync_states[
                        key
                    ].last_sync = datetime.now().isoformat()
                else:
                    self._sync_states[key].status = "failed"
                    self._sync_states[key].error = res.error

    def _load_config(self) -> None:
        """Загрузка сохранённой конфигурации."""
        if not self._config_file.exists():
            return
        try:
            with open(self._config_file, encoding="utf-8") as f:
                data = json.load(f)
            p_type = data.get("provider", "s3")
            creds = data.get("credentials", {})
            auto = bool(data.get("auto_sync", False))
            min_size = float(data.get("min_file_size_mb", 0.0))
            remote_f = data.get("remote_folder", "Recordings")
            self.configure(p_type, creds, auto, min_size, remote_f)
        except Exception as e:
            logger.warning("Не удалось загрузить конфигурацию облака: %s", e)

    def _save_config(self) -> None:
        """Сохранение конфигурации в JSON."""
        try:
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "provider": self._provider_type,
                "credentials": self._credentials,
                "auto_sync": self._auto_sync,
                "min_file_size_mb": self._min_file_size_mb,
                "remote_folder": self._remote_folder,
            }
            with open(self._config_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Не удалось сохранить конфигурацию облака: %s", e)
