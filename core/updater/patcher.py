"""
Загрузчик и установщик обновлений с SHA-256 верификацией и скриптом обновления.
=============================================================================
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path

from core.updater.types import DownloadProgress
from logger_config import get_module_logger

logger = get_module_logger(__name__)

DEFAULT_CHUNK_SIZE = 64 * 1024  # 64 KB


def calculate_sha256(file_path: Path) -> str:
    """Вычисляет SHA-256 хеш файла."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(DEFAULT_CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


class UpdatePatcher:
    """Управляет загрузкой, проверкой целостности и применением обновлений."""

    def __init__(self, download_dir: Path | None = None) -> None:
        self.download_dir = download_dir or (
            Path.home() / ".mia_screencapture" / "updates"
        )
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def download_file(
        self,
        url: str,
        target_path: Path,
        expected_sha256: str | None = None,
        progress_callback: Callable[[DownloadProgress], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> bool:
        """
        Скачивает файл обновления с отслеживанием прогресса и проверкой хеша.

        Args:
            url: Прямая ссылка на файл.
            target_path: Путь сохранения.
            expected_sha256: Ожидаемый хеш SHA-256 (если известен).
            progress_callback: Callback для уведомления о прогрессе.
            cancel_event: Флаг отмены загрузки.

        Returns:
            True при успешном завершении, иначе False.
        """
        temp_path = target_path.with_suffix(f"{target_path.suffix}.tmp")
        headers = {
            "User-Agent": "MIA-ScreenCapture-Updater/1.0",
            "Accept": "application/octet-stream",
        }

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30.0) as resp:
                total_size = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                start_time = time.monotonic()
                hasher = hashlib.sha256()

                with open(temp_path, "wb") as out_file:
                    while True:
                        if cancel_event and cancel_event.is_set():
                            logger.info("Загрузка обновления отменена.")
                            if temp_path.exists():
                                temp_path.unlink(missing_ok=True)
                            return False

                        chunk = resp.read(DEFAULT_CHUNK_SIZE)
                        if not chunk:
                            break

                        out_file.write(chunk)
                        hasher.update(chunk)
                        downloaded += len(chunk)

                        elapsed = time.monotonic() - start_time
                        speed = downloaded / elapsed if elapsed > 0 else 0.0
                        percent = (
                            (downloaded / total_size * 100.0)
                            if total_size > 0
                            else 0.0
                        )

                        if progress_callback:
                            progress_callback(
                                DownloadProgress(
                                    total_bytes=total_size,
                                    downloaded_bytes=downloaded,
                                    percent=round(percent, 1),
                                    speed_bytes_per_sec=round(speed, 1),
                                )
                            )

            # Проверка SHA-256
            computed_hash = hasher.hexdigest().lower()
            if expected_sha256:
                norm_expected = expected_sha256.strip().lower()
                if computed_hash != norm_expected:
                    logger.error(
                        "Несовпадение контрольной суммы SHA-256: "
                        "получено %s, ожидалось %s",
                        computed_hash,
                        norm_expected,
                    )
                    if temp_path.exists():
                        temp_path.unlink(missing_ok=True)
                    return False

            if target_path.exists():
                target_path.unlink(missing_ok=True)
            temp_path.rename(target_path)
            logger.info("Обновление успешно скачано: %s", target_path)
            return True

        except Exception as e:
            logger.error("Ошибка при скачивании обновления: %s", e)
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            return False

    def generate_powershell_updater(
        self,
        archive_path: Path,
        target_dir: Path,
        current_pid: int | None = None,
        restart_command: list[str] | None = None,
    ) -> Path:
        """
        Создает PowerShell-скрипт для безопасного применения обновления после выхода.

        Args:
            archive_path: Путь к скачанному архиву обновления (.zip).
            target_dir: Директория приложения для обновления.
            current_pid: PID текущего процесса приложения для ожидания.
            restart_command: Команда для перезапуска приложения после обновления.

        Returns:
            Путь к созданному .ps1 скрипту.
        """
        script_path = self.download_dir / "apply_update.ps1"
        pid_to_wait = current_pid or os.getpid()

        restart_block = ""
        if restart_command:
            exe = restart_command[0]
            args_str = " ".join(f'"{a}"' for a in restart_command[1:])
            restart_block = f"""
Write-Host "Запуск обновленного приложения..."
Start-Process -FilePath "{exe}" -ArgumentList '{args_str}'
"""

        script_content = f"""# PowerShell Update Script for MIA-ScreenCapture
param()
$ErrorActionPreference = "Continue"

Write-Host "Ожидание завершения процесса PID {pid_to_wait}..."
try {{
    Wait-Process -Id {pid_to_wait} -Timeout 30 -ErrorAction SilentlyContinue
}} catch {{
    # Процесс уже завершился
}}

Start-Sleep -Seconds 1

Write-Host "Применение обновления из {archive_path} в {target_dir}..."
try {{
    Expand-Archive -Path "{archive_path}" -DestinationPath "{target_dir}" -Force
    Write-Host "Обновление успешно распаковано."
}} catch {{
    Write-Error "Ошибка при распаковке архива: $_"
}}

{restart_block}

# Очистка временных файлов
Start-Sleep -Seconds 2
try {{
    Remove-Item -Path "{archive_path}" -Force -ErrorAction SilentlyContinue
    Remove-Item -Path "$PSCommandPath" -Force -ErrorAction SilentlyContinue
}} catch {{
    # Игнорировать ошибки удаления
}}
"""
        script_path.write_text(script_content, encoding="utf-8")
        return script_path

    def launch_powershell_updater(self, script_path: Path) -> bool:
        """Запускает сформированный PowerShell-скрипт в отдельном фоновом процессе."""
        if sys.platform != "win32":
            logger.warning(
                "Автоматическое применение скрипта поддерживается только на Windows"
            )
            return False

        try:
            cmd = [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-WindowStyle",
                "Hidden",
                "-File",
                str(script_path),
            ]
            subprocess.Popen(
                cmd,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                close_fds=True,
            )
            logger.info("Запущен фоновый процесс обновления: %s", script_path)
            return True
        except Exception as e:
            logger.error("Не удалось запустить скрипт обновления: %s", e)
            return False
