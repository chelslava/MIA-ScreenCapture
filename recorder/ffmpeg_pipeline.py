"""Слой сервисов FFmpeg-пайплайна.

Декомпозирует логику encoder.py на явные компоненты:

- ProcessSupervisor — жизненный цикл FFmpeg-процесса
- RecoveryPolicy    — политики восстановления и fallback-перемещения
- FinalizeService   — финализация записи (merge/encode + валидация + перемещение)
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from logger_config import get_module_logger
from recorder.utils import get_subprocess_creationflags

logger = get_module_logger(__name__)

_STDERR_TAIL_BYTES = 16 * 1024
_CANCEL_POLL_INTERVAL = 0.1


# ---------------------------------------------------------------------------
# ProcessSupervisor
# ---------------------------------------------------------------------------


@dataclass
class ProcessResult:
    """Результат выполнения FFmpeg-процесса."""

    returncode: int
    stderr_tail: str | None
    cancelled: bool = False


class ProcessSupervisor:
    """Управляет жизненным циклом FFmpeg-процесса.

    Запускает процесс, следит за таймаутом, обрабатывает сигналы отмены
    и возвращает структурированный результат с хвостом stderr.
    """

    def __init__(self, ffmpeg_path: str) -> None:
        self._ffmpeg_path = ffmpeg_path

    def run(
        self,
        cmd: list[str],
        timeout: int,
        cancel_event: threading.Event | None = None,
    ) -> ProcessResult:
        """Запустить FFmpeg-процесс и ждать завершения.

        stderr пишется во временный файл: при ошибке возвращается только
        ограниченный хвост, а не всё содержимое.

        Args:
            cmd: Полная команда FFmpeg включая путь к бинарю.
            timeout: Таймаут в секундах.
            cancel_event: При установке — процесс terminate→kill.

        Returns:
            ProcessResult с returncode, stderr_tail и флагом cancelled.
        """
        creationflags = get_subprocess_creationflags()
        stderr_temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix="ffmpeg_stderr_",
                suffix=".log",
                delete=False,
            ) as stderr_file:
                stderr_temp_path = Path(stderr_file.name)
                result = self._run_with_stderr_file(
                    cmd,
                    stderr_file,
                    timeout,
                    cancel_event,
                    creationflags,
                )

            stderr_tail = self._read_stderr_tail(
                stderr_temp_path, result.returncode, result.cancelled
            )
            return ProcessResult(
                returncode=result.returncode,
                stderr_tail=stderr_tail,
                cancelled=result.cancelled,
            )
        finally:
            if stderr_temp_path is not None:
                try:
                    stderr_temp_path.unlink(missing_ok=True)
                except Exception as exc:
                    logger.debug(
                        "Не удалось удалить временный stderr лог %s: %s",
                        stderr_temp_path,
                        exc,
                    )

    def _run_with_stderr_file(
        self,
        cmd: list[str],
        stderr_file: Any,
        timeout: int,
        cancel_event: threading.Event | None,
        creationflags: int,
    ) -> _RawProcessOutcome:
        if cancel_event is None:
            return self._run_simple(cmd, stderr_file, timeout, creationflags)
        return self._run_cancellable(
            cmd, stderr_file, timeout, cancel_event, creationflags
        )

    def _run_simple(
        self,
        cmd: list[str],
        stderr_file: Any,
        timeout: int,
        creationflags: int,
    ) -> _RawProcessOutcome:
        kwargs: dict[str, Any] = {
            "stdout": subprocess.DEVNULL,
            "stderr": stderr_file,
            "timeout": timeout,
        }
        if creationflags:
            kwargs["creationflags"] = creationflags
        proc = subprocess.run(cmd, **kwargs)
        return _RawProcessOutcome(returncode=proc.returncode, cancelled=False)

    def _run_cancellable(
        self,
        cmd: list[str],
        stderr_file: Any,
        timeout: int,
        cancel_event: threading.Event,
        creationflags: int,
    ) -> _RawProcessOutcome:
        popen_kwargs: dict[str, Any] = {
            "stdout": subprocess.DEVNULL,
            "stderr": stderr_file,
        }
        if creationflags:
            popen_kwargs["creationflags"] = creationflags

        process = subprocess.Popen(cmd, **popen_kwargs)
        deadline = time.monotonic() + timeout

        while True:
            if cancel_event.is_set():
                self._terminate(process)
                return _RawProcessOutcome(
                    returncode=process.returncode or -1, cancelled=True
                )

            if process.poll() is not None:
                break

            if time.monotonic() >= deadline:
                process.kill()
                process.wait(timeout=5)
                raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)

            time.sleep(_CANCEL_POLL_INTERVAL)

        return _RawProcessOutcome(
            returncode=process.returncode, cancelled=False
        )

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

    def _read_stderr_tail(
        self, path: Path, returncode: int, cancelled: bool
    ) -> str | None:
        if returncode == 0 and not cancelled:
            return None
        if not path.exists():
            return None
        try:
            with open(path, "rb") as file:
                file.seek(0, 2)
                size = file.tell()
                offset = max(0, size - _STDERR_TAIL_BYTES)
                file.seek(offset)
                data = file.read()
            return data.decode("utf-8", errors="replace").strip() or None
        except Exception:
            return None


@dataclass
class _RawProcessOutcome:
    returncode: int
    cancelled: bool


# ---------------------------------------------------------------------------
# RecoveryPolicy
# ---------------------------------------------------------------------------


class RecoveryPolicy:
    """Политики восстановления при ошибках FFmpeg-пайплайна.

    Предоставляет:
    - move_with_fallback: перемещение файла в целевую директорию с fallback
    - cleanup_corrupted: удаление повреждённых/неполных файлов
    """

    def __init__(
        self,
        fallback_dir: Path | None = None,
    ) -> None:
        self._fallback_dir = fallback_dir or (
            Path.home() / "Videos" / "Recordings"
        )

    def move_with_fallback(
        self, src: Path, dst: Path
    ) -> tuple[Path, str | None]:
        """Переместить src в dst, при ошибке — в fallback_dir.

        Args:
            src: Исходный (временный) файл.
            dst: Целевой путь.

        Returns:
            Кортеж (итоговый_путь, сообщение_об_ошибке | None).
        """
        try:
            src.replace(dst)
            return dst, None
        except PermissionError as perm_err:
            return self._fallback_copy(src, dst, perm_err)
        except Exception as exc:
            return dst, f"Не удалось переместить файл: {exc}"

    def _fallback_copy(
        self,
        src: Path,
        dst: Path,
        original_error: Exception,
    ) -> tuple[Path, str | None]:
        try:
            shutil.copy2(src, dst)
            src.unlink(missing_ok=True)
            return dst, None
        except Exception:
            return self._emergency_copy(src, dst, original_error)

    def _emergency_copy(
        self,
        src: Path,
        dst: Path,
        original_error: Exception,
    ) -> tuple[Path, str | None]:
        try:
            self._fallback_dir.mkdir(parents=True, exist_ok=True)
            fallback_path = self._fallback_dir / dst.name
            shutil.copy2(src, fallback_path)
            src.unlink(missing_ok=True)
            logger.warning(
                "Файл сохранён в резервную директорию: %s", fallback_path
            )
            return fallback_path, None
        except Exception as fallback_err:
            return (
                dst,
                (
                    f"Не удалось переместить файл: {original_error} "
                    f"(fallback: {fallback_err})"
                ),
            )

    def cleanup_corrupted(self, path: Path) -> None:
        """Удалить повреждённый/неполный файл.

        Args:
            path: Путь к повреждённому файлу.
        """
        if not path.exists():
            return
        try:
            path.unlink()
            logger.info("Повреждённый файл удалён: %s", path)
        except Exception as exc:
            logger.warning(
                "Не удалось удалить повреждённый файл %s: %s", path, exc
            )


# ---------------------------------------------------------------------------
# FinalizeService
# ---------------------------------------------------------------------------


@dataclass
class FinalizeResult:
    """Результат финализации записи."""

    success: bool
    output_path: Path | None
    error: str | None


class FinalizeService:
    """Финализация записи: merge/encode, валидация, перемещение в output.

    Принимает временные видео/аудио файлы, объединяет их через FFmpeg,
    проверяет результат и перемещает в указанный output_path.
    """

    def __init__(
        self,
        supervisor: ProcessSupervisor,
        recovery: RecoveryPolicy,
        ffmpeg_path: str,
        codec: str = "libx264",
        preset: str = "medium",
        bitrate: str = "2M",
        audio_codec: str = "aac",
        audio_bitrate: str = "192k",
    ) -> None:
        self._supervisor = supervisor
        self._recovery = recovery
        self._ffmpeg = ffmpeg_path
        self._codec = codec
        self._preset = preset
        self._bitrate = bitrate
        self._audio_codec = audio_codec
        self._audio_bitrate = audio_bitrate

    def finalize(
        self,
        video_path: Path,
        audio_path: Path | None,
        output_path: Path,
        cancel_event: threading.Event | None = None,
        timeout: int = 3600,
    ) -> FinalizeResult:
        """Объединить видео/аудио, проверить и переместить в output_path.

        Args:
            video_path: Временный видеофайл.
            audio_path: Временный аудиофайл или None (только видео).
            output_path: Куда сохранить итоговый файл.
            cancel_event: При установке — отменяет FFmpeg-процесс.
            timeout: Таймаут FFmpeg в секундах.

        Returns:
            FinalizeResult с итоговым путём или описанием ошибки.
        """
        if not video_path.exists():
            return FinalizeResult(
                success=False, output_path=None, error="Видеофайл не найден"
            )

        temp_output = video_path.parent / f"_final{output_path.suffix}"
        try:
            if audio_path is not None and audio_path.exists():
                result = self._merge(
                    video_path, audio_path, temp_output, cancel_event, timeout
                )
            else:
                result = self._encode_only(
                    video_path, temp_output, cancel_event, timeout
                )

            if result.cancelled:
                return FinalizeResult(
                    success=False, output_path=None, error="Отменено"
                )
            if result.returncode != 0:
                return FinalizeResult(
                    success=False,
                    output_path=None,
                    error=result.stderr_tail or "Ошибка FFmpeg",
                )

            valid, validate_error = self.validate_output(temp_output)
            if not valid:
                self._recovery.cleanup_corrupted(temp_output)
                return FinalizeResult(
                    success=False,
                    output_path=None,
                    error=validate_error or "Файл повреждён",
                )

            final_path, move_error = self._recovery.move_with_fallback(
                temp_output, output_path
            )
            if move_error:
                return FinalizeResult(
                    success=False, output_path=None, error=move_error
                )

            logger.info("Запись финализирована: %s", final_path)
            return FinalizeResult(
                success=True, output_path=final_path, error=None
            )

        finally:
            temp_output.unlink(missing_ok=True)

    def validate_output(self, path: Path) -> tuple[bool, str | None]:
        """Проверить, что выходной файл корректен.

        Минимальная проверка: файл существует и не пуст.

        Args:
            path: Путь к файлу для проверки.

        Returns:
            Кортеж (ok, сообщение_об_ошибке | None).
        """
        if not path.exists():
            return False, f"Файл не найден: {path}"
        try:
            size = path.stat().st_size
        except OSError as exc:
            return False, f"Не удалось прочитать файл: {exc}"
        if size == 0:
            return False, "Выходной файл пуст"
        return True, None

    def _merge(
        self,
        video: Path,
        audio: Path,
        output: Path,
        cancel_event: threading.Event | None,
        timeout: int,
    ) -> ProcessResult:
        cmd = [
            self._ffmpeg,
            "-y",
            "-i",
            str(video),
            "-i",
            str(audio),
            "-c:v",
            self._codec,
            "-preset",
            self._preset,
            "-b:v",
            self._bitrate,
            "-c:a",
            self._audio_codec,
            "-b:a",
            self._audio_bitrate,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-shortest",
            str(output),
        ]
        return self._supervisor.run(cmd, timeout, cancel_event)

    def _encode_only(
        self,
        video: Path,
        output: Path,
        cancel_event: threading.Event | None,
        timeout: int,
    ) -> ProcessResult:
        cmd = [
            self._ffmpeg,
            "-y",
            "-i",
            str(video),
            "-c:v",
            self._codec,
            "-preset",
            self._preset,
            "-b:v",
            self._bitrate,
            str(output),
        ]
        return self._supervisor.run(cmd, timeout, cancel_event)
