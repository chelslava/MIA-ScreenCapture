"""
Координатор жизненного цикла обновлений (AppUpdater).
=====================================================
"""

from __future__ import annotations

import os
import sys
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from config import ConfigManager, UpdateSettings, get_config
from core.event_bus import EventBus
from core.updater.github_client import GitHubReleaseClient
from core.updater.patcher import UpdatePatcher
from core.updater.types import (
    DownloadProgress,
    ReleaseInfo,
    UpdateCheckResult,
    UpdateStatus,
)
from logger_config import get_module_logger
from version import get_version

logger = get_module_logger(__name__)


class AppUpdater:
    """Оркестратор проверки, скачивания и установки обновлений."""

    def __init__(
        self,
        event_bus: EventBus | None = None,
        config_manager: ConfigManager | None = None,
        github_client: GitHubReleaseClient | None = None,
        patcher: UpdatePatcher | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._config_manager = config_manager
        self._github_client = github_client or GitHubReleaseClient()
        self._patcher = patcher or UpdatePatcher()

        self._status: UpdateStatus = UpdateStatus.IDLE
        self._status_lock = threading.Lock()
        self._latest_release: ReleaseInfo | None = None
        self._downloaded_file: Path | None = None
        self._last_progress: DownloadProgress | None = None
        self._cancel_event = threading.Event()
        self._error_message: str | None = None

    @property
    def status(self) -> UpdateStatus:
        with self._status_lock:
            return self._status

    @property
    def latest_release(self) -> ReleaseInfo | None:
        return self._latest_release

    @property
    def downloaded_file(self) -> Path | None:
        return self._downloaded_file

    def get_status(self) -> dict[str, Any]:
        """Возвращает текущее состояние подсистемы обновления."""
        with self._status_lock:
            return {
                "status": self._status.value,
                "current_version": get_version(),
                "latest_release": (
                    self._latest_release.to_dict()
                    if self._latest_release
                    else None
                ),
                "downloaded_file": (
                    str(self._downloaded_file)
                    if self._downloaded_file
                    else None
                ),
                "progress": (
                    self._last_progress.to_dict()
                    if self._last_progress
                    else None
                ),
                "error_message": self._error_message,
            }

    def _get_settings(self) -> UpdateSettings:
        if self._config_manager:
            return self._config_manager.settings.updates
        try:
            return get_config().settings.updates
        except Exception:
            return UpdateSettings()

    def check_for_updates(
        self,
        force: bool = False,
        callback: Callable[[UpdateCheckResult], None] | None = None,
    ) -> UpdateCheckResult:
        """
        Синхронная проверка обновлений.

        Args:
            force: Игнорировать кэш и настройки интервала.
            callback: Опциональный callback по завершении.
        """
        with self._status_lock:
            if self._status == UpdateStatus.CHECKING:
                logger.info("Проверка обновлений уже выполняется")
                return UpdateCheckResult(
                    update_available=False,
                    current_version=get_version(),
                    error="Проверка уже в процессе",
                )
            self._status = UpdateStatus.CHECKING
            self._error_message = None

        settings = self._get_settings()
        current_version = get_version()

        try:
            res = self._github_client.check_for_updates(
                current_version=current_version,
                channel=settings.channel,
                ignored_version=None if force else settings.ignored_version,
            )

            with self._status_lock:
                if res.error:
                    self._status = UpdateStatus.ERROR
                    self._error_message = res.error
                elif res.update_available:
                    self._status = UpdateStatus.UPDATE_AVAILABLE
                    self._latest_release = res.latest_release
                else:
                    self._status = UpdateStatus.NO_UPDATE
                    self._latest_release = res.latest_release

            # Обновление времени последней проверки
            if self._config_manager:
                now_iso = datetime.now().isoformat()
                self._config_manager.settings.updates.last_checked_at = now_iso

            # Публикация события
            if self._event_bus:
                try:
                    if res.update_available and res.latest_release:
                        from core.event_bus import (
                            RecordingEvent,
                            RecordingEventType,
                        )

                        self._event_bus.publish(
                            RecordingEvent(
                                event_type=RecordingEventType.STATUS,
                                payload={
                                    "type": "update.available",
                                    **res.latest_release.to_dict(),
                                },
                            )
                        )
                except Exception as e:
                    logger.debug(
                        "Ошибка отправки события update.available: %s", e
                    )

            if callback:
                callback(res)
            return res

        except Exception as e:
            logger.error("Ошибка при проверке обновлений: %s", e)
            with self._status_lock:
                self._status = UpdateStatus.ERROR
                self._error_message = str(e)
            res = UpdateCheckResult(
                update_available=False,
                current_version=current_version,
                error=str(e),
            )
            if callback:
                callback(res)
            return res

    def check_for_updates_async(
        self,
        force: bool = False,
        callback: Callable[[UpdateCheckResult], None] | None = None,
    ) -> threading.Thread:
        """Запуск проверки обновлений в фоновом потоке."""
        thread = threading.Thread(
            target=self.check_for_updates,
            args=(force, callback),
            name="AppUpdaterCheckThread",
            daemon=True,
        )
        thread.start()
        return thread

    def download_update(
        self,
        release: ReleaseInfo | None = None,
        callback: Callable[[bool], None] | None = None,
    ) -> bool:
        """
        Синхронное скачивание артефакта обновления.

        Args:
            release: Релиз для скачивания (или latest_release).
            callback: Callback при завершении.
        """
        target_release = release or self._latest_release
        if not target_release or not target_release.primary_download_url:
            logger.error("Нет доступного URL для скачивания обновления")
            with self._status_lock:
                self._status = UpdateStatus.ERROR
                self._error_message = "URL для скачивания не найден"
            if callback:
                callback(False)
            return False

        with self._status_lock:
            self._status = UpdateStatus.DOWNLOADING
            self._cancel_event.clear()
            self._error_message = None
            self._last_progress = None

        url = target_release.primary_download_url
        filename = f"mia_update_{target_release.version}.zip"
        target_file = self._patcher.download_dir / filename

        def on_progress(p: DownloadProgress) -> None:
            self._last_progress = p
            if self._event_bus:
                try:
                    from core.event_bus import (
                        RecordingEvent,
                        RecordingEventType,
                    )

                    self._event_bus.publish(
                        RecordingEvent(
                            event_type=RecordingEventType.PROGRESS,
                            payload={
                                "type": "update.download_progress",
                                **p.to_dict(),
                            },
                        )
                    )
                except Exception:
                    pass

        try:
            success = self._patcher.download_file(
                url=url,
                target_path=target_file,
                expected_sha256=target_release.sha256_checksum,
                progress_callback=on_progress,
                cancel_event=self._cancel_event,
            )

            with self._status_lock:
                if success:
                    self._status = UpdateStatus.READY_TO_INSTALL
                    self._downloaded_file = target_file
                else:
                    if self._cancel_event.is_set():
                        self._status = UpdateStatus.UPDATE_AVAILABLE
                    else:
                        self._status = UpdateStatus.ERROR
                        self._error_message = (
                            "Ошибка при загрузке или проверке SHA-256"
                        )

            if success and self._event_bus:
                try:
                    from core.event_bus import (
                        RecordingEvent,
                        RecordingEventType,
                    )

                    self._event_bus.publish(
                        RecordingEvent(
                            event_type=RecordingEventType.STATUS,
                            payload={
                                "type": "update.ready",
                                "file_path": str(target_file),
                                "version": target_release.version,
                            },
                        )
                    )
                except Exception:
                    pass

            if callback:
                callback(success)
            return success

        except Exception as e:
            logger.error("Исключение при скачивании обновления: %s", e)
            with self._status_lock:
                self._status = UpdateStatus.ERROR
                self._error_message = str(e)
            if callback:
                callback(False)
            return False

    def download_update_async(
        self,
        release: ReleaseInfo | None = None,
        callback: Callable[[bool], None] | None = None,
    ) -> threading.Thread:
        """Запуск скачивания в фоновом потоке."""
        thread = threading.Thread(
            target=self.download_update,
            args=(release, callback),
            name="AppUpdaterDownloadThread",
            daemon=True,
        )
        thread.start()
        return thread

    def cancel_download(self) -> None:
        """Отмена текущей загрузки."""
        self._cancel_event.set()

    def apply_update(
        self,
        target_dir: Path | None = None,
        restart_command: list[str] | None = None,
    ) -> bool:
        """
        Формирует PowerShell-скрипт и запускает процесс обновления.

        Args:
            target_dir: Целевая папка приложения (по умолчанию папка проекта).
            restart_command: Команда для запуска приложения после обновления.

        Returns:
            True, если скрипт успешно сгенерирован и запущен.
        """
        if not self._downloaded_file or not self._downloaded_file.exists():
            logger.error("Файл обновления не найден для установки")
            return False

        app_root = target_dir or Path(__file__).resolve().parent.parent.parent
        cmd = restart_command or [sys.executable, str(app_root / "main.py")]

        with self._status_lock:
            self._status = UpdateStatus.INSTALLING

        try:
            script_path = self._patcher.generate_powershell_updater(
                archive_path=self._downloaded_file,
                target_dir=app_root,
                current_pid=os.getpid(),
                restart_command=cmd,
            )
            return self._patcher.launch_powershell_updater(script_path)
        except Exception as e:
            logger.error("Ошибка при подготовке обновления: %s", e)
            with self._status_lock:
                self._status = UpdateStatus.ERROR
                self._error_message = str(e)
            return False

    def ignore_version(self, version: str) -> None:
        """Игнорирует указанную версию при последующих авто-проверках."""
        if self._config_manager:
            self._config_manager.settings.updates.ignored_version = version
            try:
                self._config_manager.save()
            except Exception as e:
                logger.warning("Не удалось сохранить ignored_version: %s", e)
