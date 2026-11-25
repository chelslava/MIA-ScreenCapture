"""
Загрузчик и установщик обновлений с SHA-256 верификацией и скриптом обновления.
=============================================================================
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
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

    @staticmethod
    def backup_dir_for(target_dir: Path) -> Path:
        """Вычисляет путь backup-директории для установки (#191).

        Backup создаётся переименованием на том же томе — операция
        мгновенная и не боится обрыва процесса.
        """
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return target_dir.parent / f"{target_dir.name}.backup-{stamp}"

    @staticmethod
    def make_backup_restart_command(
        restart_command: list[str],
        target_dir: Path,
        backup_dir: Path,
    ) -> list[str]:
        """Строит команду перезапуска приложения из backup-директории.

        Args:
            restart_command: Обычная команда перезапуска (новая версия).
            target_dir: Текущая директория установки.
            backup_dir: Директория backup предыдущей версии.

        Returns:
            Команда с заменой префикса target_dir на backup_dir.
        """
        old_root = str(target_dir)
        new_root = str(backup_dir)
        return [
            new_root + arg[len(old_root) :]
            if arg.startswith(old_root)
            else arg
            for arg in restart_command
        ]

    def cleanup_old_backups(self, target_dir: Path, keep: int = 1) -> int:
        """Удаляет старые backup-директории, оставляя последние (#191).

        Args:
            target_dir: Директория установки приложения.
            keep: Сколько свежих backup сохранить.

        Returns:
            Количество удалённых backup-директорий.
        """
        pattern = f"{target_dir.name}.backup-*"
        backups = sorted(
            (p for p in target_dir.parent.glob(pattern) if p.is_dir()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        removed = 0
        for stale in backups[keep:]:
            try:
                shutil.rmtree(stale)
                removed += 1
                logger.info("Удалён старый backup: %s", stale)
            except Exception as e:
                logger.warning("Не удалось удалить backup %s: %s", stale, e)
        return removed

    def generate_powershell_updater(
        self,
        archive_path: Path,
        target_dir: Path,
        current_pid: int | None = None,
        restart_command: list[str] | None = None,
        *,
        version: str = "unknown",
        verify_paths: list[str] | None = None,
        health_timeout_s: int = 60,
        backup_dir: Path | None = None,
        restart_command_backup: list[str] | None = None,
    ) -> Path:
        """
        Создает PowerShell-скрипт обновления с backup и откатом (#191).

        Сценарий: backup переименованием -> распаковка -> проверка
        обязательных файлов -> маркер update_state.json -> запуск новой
        версии -> health-check (приложение удаляет маркер после успешного
        старта). Любой провал до подтверждения откатывает установку на
        backup и запускает предыдущую версию.

        Args:
            archive_path: Путь к скачанному архиву обновления (.zip).
            target_dir: Директория приложения для обновления.
            current_pid: PID текущего процесса приложения для ожидания.
            restart_command: Команда для перезапуска приложения после обновления.
            version: Версия устанавливаемого обновления (для маркера).
            verify_paths: Относительные пути, обязательные после распаковки.
            health_timeout_s: Сколько секунд ждать подтверждения запуска.
            backup_dir: Путь backup (по умолчанию рядом с target_dir).
            restart_command_backup: Команда перезапуска из backup при откате.

        Returns:
            Путь к созданному .ps1 скрипту.
        """
        script_path = self.download_dir / "apply_update.ps1"
        pid_to_wait = current_pid or os.getpid()
        backup = backup_dir or self.backup_dir_for(target_dir)
        checks = verify_paths or ["main.py"]
        if restart_command is None:
            restart_command = [sys.executable, str(target_dir / "main.py")]
        rollback_command = restart_command_backup or (
            self.make_backup_restart_command(
                restart_command, target_dir, backup
            )
        )

        # PS-массив требует запятые-разделители, не пробелы
        checks_literal = ", ".join(f'"{p}"' for p in checks)
        new_args_str = " ".join(f'"{a}"' for a in restart_command[1:])
        old_args_str = " ".join(f'"{a}"' for a in rollback_command[1:])
        state_started_at = datetime.now(UTC).isoformat()

        script_content = f"""# PowerShell Update Script for MIA-ScreenCapture (#191)
# Backup -> Extract -> Verify -> Health-check -> Rollback on failure
$ErrorActionPreference = "Stop"

$ArchivePath   = "{archive_path}"
$TargetDir     = "{target_dir}"
$BackupDir     = "{backup}"
$StatePath     = Join-Path $TargetDir "update_state.json"
$RollbackPath  = Join-Path $TargetDir "update_rollback.json"
$Version       = "{version}"
$StartedAt     = "{state_started_at}"
$HealthTimeout = {int(health_timeout_s)}
$VerifyPaths   = @({checks_literal})
$NewExe        = "{restart_command[0]}"
$NewArgs       = '{new_args_str}'
$OldExe        = "{rollback_command[0]}"
$OldArgs       = '{old_args_str}'
$script:AppProcess = $null

function Invoke-Rollback {{
    param([string]$Reason)
    Write-Host "ОТКАТ обновления: $Reason"
    if ($script:AppProcess -and -not $script:AppProcess.HasExited) {{
        try {{ taskkill /PID $script:AppProcess.Id /T /F 2>$null }} catch {{}}
    }}
    Remove-Item -LiteralPath $TargetDir -Recurse -Force -ErrorAction SilentlyContinue
    Move-Item -LiteralPath $BackupDir -Destination $TargetDir -Force
    @{{
        reason = $Reason
        version = $Version
        rolled_back_at = (Get-Date).ToUniversalTime().ToString("o")
    }} | ConvertTo-Json | ForEach-Object {{ [System.IO.File]::WriteAllText($RollbackPath, $_) }}
    Write-Host "Запуск предыдущей версии из backup..."
    try {{
        Start-Process -FilePath $OldExe -ArgumentList $OldArgs | Out-Null
    }} catch {{
        Write-Error "Не удалось запустить предыдущую версию: $_"
    }}
    exit 2
}}

Write-Host "Ожидание завершения процесса PID {pid_to_wait}..."
try {{
    Wait-Process -Id {pid_to_wait} -Timeout 30 -ErrorAction SilentlyContinue
}} catch {{
    # Процесс уже завершился
}}

Start-Sleep -Seconds 1

# Шаг 1. Backup предыдущей установки переименованием на том же томе
if (Test-Path -LiteralPath $TargetDir) {{
    try {{
        Move-Item -LiteralPath $TargetDir -Destination $BackupDir -ErrorAction Stop
        Write-Host "Backup создан: $BackupDir"
    }} catch {{
        Write-Error "Нельзя создать backup (файлы заняты?): $_"
        exit 1
    }}
}}

# Шаг 2. Распаковка в чистую директорию
Write-Host "Применение обновления из $ArchivePath в $TargetDir..."
try {{
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
    Expand-Archive -LiteralPath $ArchivePath -DestinationPath $TargetDir -Force -ErrorAction Stop
    Write-Host "Обновление успешно распаковано."
}} catch {{
    Invoke-Rollback "распаковка: $_"
}}

# Шаг 3. Проверка обязательных файлов новой версии
foreach ($p in $VerifyPaths) {{
    if (-not (Test-Path -LiteralPath (Join-Path $TargetDir $p))) {{
        Invoke-Rollback "после распаковки отсутствует $p"
    }}
}}

# Шаг 4. Маркер «обновление применено, ожидается подтверждение»
# WriteAllText вместо Set-Content: PS 5.1 пишет utf8 с BOM, а Python-сторона
# читает маркер json-парсером
@{{
    version = $Version
    backup_dir = $BackupDir
    started_at = $StartedAt
}} | ConvertTo-Json | ForEach-Object {{ [System.IO.File]::WriteAllText($StatePath, $_) }}

# Шаг 5. Запуск новой версии
Write-Host "Запуск обновленного приложения..."
try {{
    $script:AppProcess = Start-Process -FilePath $NewExe -ArgumentList $NewArgs -PassThru -ErrorAction Stop
}} catch {{
    Invoke-Rollback "не удалось запустить новую версию: $_"
}}

# Шаг 6. Health-check: приложение удаляет маркер после успешного старта
$deadline = (Get-Date).AddSeconds($HealthTimeout)
$confirmed = $false
while ((Get-Date) -lt $deadline) {{
    if (-not (Test-Path -LiteralPath $StatePath)) {{
        $confirmed = $true
        break
    }}
    if ($script:AppProcess.HasExited) {{
        Invoke-Rollback "новая версия завершилась до подтверждения запуска"
    }}
    Start-Sleep -Milliseconds 500
}}
if (-not $confirmed) {{
    Invoke-Rollback "health-check: приложение не подтвердило запуск за $HealthTimeout c"
}}

Write-Host "Обновление до версии $Version подтверждено."
Remove-Item -LiteralPath $ArchivePath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
exit 0
"""
        # utf-8-sig: PowerShell 5.1 читает BOM-less файлы в ANSI и
        # портит кириллицу в сообщениях
        script_path.write_text(script_content, encoding="utf-8-sig")
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
