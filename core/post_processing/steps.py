"""
Реализации отдельных шагов постобработки видеозаписей
====================================================

Включает:
- базовый класс PostProcessingStep;
- TranscodeStep (перекодирование/смена контейнера через FFmpeg);
- CompressStep (сжатие видео с настраиваемым CRF через FFmpeg);
- TrimSilenceStep (обрезка начальной/конечной тишины в аудио через FFmpeg);
- GenerateGifPreviewStep (генерация анимированного GIF-превью через FFmpeg);
- CopyToFolderStep (копирование видеофайла в целевую директорию);
- OpenInExplorerStep (открытие и выделение файла в проводнике Windows);
- WebhookNotificationStep (отправка подписанного webhook-уведомления).
"""

from __future__ import annotations

import abc
import platform
import shutil
import subprocess
import time
from pathlib import Path

from core.post_processing.types import PostProcessingStepType, StepResult
from core.webhook import WebhookSender, WebhookSigner
from logger_config import get_module_logger
from recorder.utils import get_ffmpeg_path

logger = get_module_logger(__name__)


class PostProcessingStep(abc.ABC):
    """Базовый интерфейс для шага постобработки видеофайла."""

    def __init__(
        self,
        step_type: PostProcessingStepType,
        is_fatal: bool = False,
        timeout_seconds: int = 300,
    ) -> None:
        self.step_type = step_type
        self.is_fatal = is_fatal
        self.timeout_seconds = timeout_seconds

    @abc.abstractmethod
    def execute(self, input_path: Path) -> StepResult:
        """
        Выполнение шага постобработки.

        Args:
            input_path: Путь к входному видеофайлу.

        Returns:
            StepResult с информацией об успехе, результирующем пути и ошибках.
        """
        raise NotImplementedError


class TranscodeStep(PostProcessingStep):
    """Шаг перекодирования / конвертации контейнера (например, MP4 -> WebM/MKV)."""

    def __init__(
        self,
        target_format: str = "webm",
        target_codec: str = "libvpx-vp9",
        is_fatal: bool = False,
        timeout_seconds: int = 600,
    ) -> None:
        super().__init__(
            step_type=PostProcessingStepType.TRANSCODE,
            is_fatal=is_fatal,
            timeout_seconds=timeout_seconds,
        )
        self.target_format = target_format.lstrip(".").lower()
        self.target_codec = target_codec

    def execute(self, input_path: Path) -> StepResult:
        start_time = time.monotonic()
        if not input_path.exists():
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                error_message=f"Файл {input_path} не существует",
                is_fatal=self.is_fatal,
            )

        output_path = input_path.with_name(
            f"{input_path.stem}_transcoded.{self.target_format}"
        )
        ffmpeg_bin = get_ffmpeg_path() or "ffmpeg"

        # Формируем команду FFmpeg для транскодирования
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i",
            str(input_path),
            "-c:v",
            self.target_codec,
            "-b:v",
            "0",
            "-crf",
            "30",
            "-c:a",
            "libopus" if self.target_format == "webm" else "aac",
            str(output_path),
        ]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            duration = time.monotonic() - start_time
            if res.returncode == 0 and output_path.exists():
                return StepResult(
                    step_type=self.step_type,
                    success=True,
                    input_path=input_path,
                    output_path=output_path,
                    duration_seconds=duration,
                    details={
                        "target_format": self.target_format,
                        "target_codec": self.target_codec,
                        "file_size": output_path.stat().st_size,
                    },
                )
            error_msg = res.stderr[-500:] if res.stderr else "FFmpeg error"
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                duration_seconds=duration,
                error_message=f"Ошибка транскодирования (code {res.returncode}): {error_msg}",
                is_fatal=self.is_fatal,
            )
        except subprocess.TimeoutExpired:
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                duration_seconds=time.monotonic() - start_time,
                error_message=f"Таймаут транскодирования ({self.timeout_seconds}с)",
                is_fatal=self.is_fatal,
            )
        except Exception as e:
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                duration_seconds=time.monotonic() - start_time,
                error_message=str(e),
                is_fatal=self.is_fatal,
            )


class CompressStep(PostProcessingStep):
    """Шаг сжатия видеофайла с заданным CRF."""

    def __init__(
        self,
        crf: int = 28,
        preset: str = "medium",
        is_fatal: bool = False,
        timeout_seconds: int = 600,
    ) -> None:
        super().__init__(
            step_type=PostProcessingStepType.COMPRESS,
            is_fatal=is_fatal,
            timeout_seconds=timeout_seconds,
        )
        self.crf = crf
        self.preset = preset

    def execute(self, input_path: Path) -> StepResult:
        start_time = time.monotonic()
        if not input_path.exists():
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                error_message=f"Файл {input_path} не существует",
                is_fatal=self.is_fatal,
            )

        output_path = input_path.with_name(
            f"{input_path.stem}_compressed{input_path.suffix}"
        )
        ffmpeg_bin = get_ffmpeg_path() or "ffmpeg"

        cmd = [
            ffmpeg_bin,
            "-y",
            "-i",
            str(input_path),
            "-c:v",
            "libx264",
            "-crf",
            str(self.crf),
            "-preset",
            self.preset,
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            str(output_path),
        ]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            duration = time.monotonic() - start_time
            if res.returncode == 0 and output_path.exists():
                original_size = input_path.stat().st_size
                compressed_size = output_path.stat().st_size
                compression_ratio = round(
                    (1.0 - compressed_size / max(original_size, 1)) * 100, 1
                )
                return StepResult(
                    step_type=self.step_type,
                    success=True,
                    input_path=input_path,
                    output_path=output_path,
                    duration_seconds=duration,
                    details={
                        "original_size": original_size,
                        "compressed_size": compressed_size,
                        "saved_percent": compression_ratio,
                    },
                )
            error_msg = res.stderr[-500:] if res.stderr else "FFmpeg error"
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                duration_seconds=duration,
                error_message=f"Ошибка сжатия (code {res.returncode}): {error_msg}",
                is_fatal=self.is_fatal,
            )
        except subprocess.TimeoutExpired:
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                duration_seconds=time.monotonic() - start_time,
                error_message=f"Таймаут сжатия ({self.timeout_seconds}с)",
                is_fatal=self.is_fatal,
            )
        except Exception as e:
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                duration_seconds=time.monotonic() - start_time,
                error_message=str(e),
                is_fatal=self.is_fatal,
            )


class TrimSilenceStep(PostProcessingStep):
    """Шаг обрезки тишины в начале и конце аудиодорожки."""

    def __init__(
        self,
        threshold_db: int = -50,
        is_fatal: bool = False,
        timeout_seconds: int = 300,
    ) -> None:
        super().__init__(
            step_type=PostProcessingStepType.TRIM_SILENCE,
            is_fatal=is_fatal,
            timeout_seconds=timeout_seconds,
        )
        self.threshold_db = threshold_db

    def execute(self, input_path: Path) -> StepResult:
        start_time = time.monotonic()
        if not input_path.exists():
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                error_message=f"Файл {input_path} не существует",
                is_fatal=self.is_fatal,
            )

        output_path = input_path.with_name(
            f"{input_path.stem}_trimmed{input_path.suffix}"
        )
        ffmpeg_bin = get_ffmpeg_path() or "ffmpeg"

        # Фильтр silenceremove для удаления тишины в начале
        audio_filter = f"silenceremove=start_periods=1:start_duration=0.5:start_threshold={self.threshold_db}dB"
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i",
            str(input_path),
            "-af",
            audio_filter,
            "-c:v",
            "copy",
            str(output_path),
        ]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            duration = time.monotonic() - start_time
            if res.returncode == 0 and output_path.exists():
                return StepResult(
                    step_type=self.step_type,
                    success=True,
                    input_path=input_path,
                    output_path=output_path,
                    duration_seconds=duration,
                    details={"threshold_db": self.threshold_db},
                )
            error_msg = res.stderr[-500:] if res.stderr else "FFmpeg error"
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                duration_seconds=duration,
                error_message=f"Ошибка обрезки тишины (code {res.returncode}): {error_msg}",
                is_fatal=self.is_fatal,
            )
        except subprocess.TimeoutExpired:
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                duration_seconds=time.monotonic() - start_time,
                error_message=f"Таймаут обрезки тишины ({self.timeout_seconds}с)",
                is_fatal=self.is_fatal,
            )
        except Exception as e:
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                duration_seconds=time.monotonic() - start_time,
                error_message=str(e),
                is_fatal=self.is_fatal,
            )


class GenerateGifPreviewStep(PostProcessingStep):
    """Шаг генерации анимированного GIF-превью первых N секунд видео."""

    def __init__(
        self,
        duration_seconds: int = 5,
        fps: int = 10,
        width: int = 480,
        is_fatal: bool = False,
        timeout_seconds: int = 120,
    ) -> None:
        super().__init__(
            step_type=PostProcessingStepType.GENERATE_GIF,
            is_fatal=is_fatal,
            timeout_seconds=timeout_seconds,
        )
        self.preview_duration = duration_seconds
        self.fps = fps
        self.width = width

    def execute(self, input_path: Path) -> StepResult:
        start_time = time.monotonic()
        if not input_path.exists():
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                error_message=f"Файл {input_path} не существует",
                is_fatal=self.is_fatal,
            )

        output_gif_path = input_path.with_suffix(".gif")
        ffmpeg_bin = get_ffmpeg_path() or "ffmpeg"

        # Двухпроходная качественная палитра для GIF
        filter_complex = (
            f"fps={self.fps},scale={self.width}:-1:flags=lanczos,split[s0][s1];"
            f"[s0]palettegen[p];[s1][p]paletteuse"
        )

        cmd = [
            ffmpeg_bin,
            "-y",
            "-t",
            str(self.preview_duration),
            "-i",
            str(input_path),
            "-vf",
            filter_complex,
            str(output_gif_path),
        ]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
            duration = time.monotonic() - start_time
            if res.returncode == 0 and output_gif_path.exists():
                # Замечание: input_path остается основным видео для последующих шагов конвейера,
                # а GIF-превью сохраняется как сопутствующий артефакт
                return StepResult(
                    step_type=self.step_type,
                    success=True,
                    input_path=input_path,
                    output_path=input_path,  # сохраняем исходное видео для дальнейших шагов
                    duration_seconds=duration,
                    details={
                        "gif_path": str(output_gif_path),
                        "gif_size": output_gif_path.stat().st_size,
                    },
                )
            error_msg = res.stderr[-500:] if res.stderr else "FFmpeg error"
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                duration_seconds=duration,
                error_message=f"Ошибка генерации GIF (code {res.returncode}): {error_msg}",
                is_fatal=self.is_fatal,
            )
        except subprocess.TimeoutExpired:
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                duration_seconds=time.monotonic() - start_time,
                error_message=f"Таймаут генерации GIF ({self.timeout_seconds}с)",
                is_fatal=self.is_fatal,
            )
        except Exception as e:
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                duration_seconds=time.monotonic() - start_time,
                error_message=str(e),
                is_fatal=self.is_fatal,
            )


class CopyToFolderStep(PostProcessingStep):
    """Шаг безопасного копирования результирующего видеофайла в указанную папку."""

    def __init__(
        self,
        target_folder: str | Path,
        is_fatal: bool = False,
        timeout_seconds: int = 120,
    ) -> None:
        super().__init__(
            step_type=PostProcessingStepType.COPY_TO_DIR,
            is_fatal=is_fatal,
            timeout_seconds=timeout_seconds,
        )
        self.target_folder = Path(target_folder) if target_folder else None

    def execute(self, input_path: Path) -> StepResult:
        start_time = time.monotonic()
        if not input_path.exists():
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                error_message=f"Файл {input_path} не существует",
                is_fatal=self.is_fatal,
            )

        if not self.target_folder or str(self.target_folder).strip() == "":
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                error_message="Целевая папка для копирования не указана",
                is_fatal=self.is_fatal,
            )

        try:
            self.target_folder.mkdir(parents=True, exist_ok=True)
            target_path = self.target_folder / input_path.name

            # Разрешение коллизий имен файлов
            counter = 1
            while target_path.exists():
                target_path = (
                    self.target_folder
                    / f"{input_path.stem} ({counter}){input_path.suffix}"
                )
                counter += 1

            shutil.copy2(str(input_path), str(target_path))
            duration = time.monotonic() - start_time

            return StepResult(
                step_type=self.step_type,
                success=True,
                input_path=input_path,
                output_path=input_path,
                duration_seconds=duration,
                details={"copied_to": str(target_path)},
            )
        except Exception as e:
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                duration_seconds=time.monotonic() - start_time,
                error_message=f"Ошибка копирования: {e}",
                is_fatal=self.is_fatal,
            )


class OpenInExplorerStep(PostProcessingStep):
    """Шаг открытия и выделения готового видеофайла в Проводнике Windows."""

    def __init__(
        self,
        is_fatal: bool = False,
        timeout_seconds: int = 10,
    ) -> None:
        super().__init__(
            step_type=PostProcessingStepType.OPEN_EXPLORER,
            is_fatal=is_fatal,
            timeout_seconds=timeout_seconds,
        )

    def execute(self, input_path: Path) -> StepResult:
        start_time = time.monotonic()
        if not input_path.exists():
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                error_message=f"Файл {input_path} не существует",
                is_fatal=self.is_fatal,
            )

        try:
            sys_name = platform.system()
            if sys_name == "Windows":
                # explorer /select,путь_к_файлу
                subprocess.Popen(
                    ["explorer", f"/select,{input_path.resolve()}"]
                )
            elif sys_name == "Darwin":
                subprocess.Popen(["open", "-R", str(input_path.resolve())])
            else:
                subprocess.Popen(
                    ["xdg-open", str(input_path.parent.resolve())]
                )

            return StepResult(
                step_type=self.step_type,
                success=True,
                input_path=input_path,
                output_path=input_path,
                duration_seconds=time.monotonic() - start_time,
                details={"opened_path": str(input_path)},
            )
        except Exception as e:
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                duration_seconds=time.monotonic() - start_time,
                error_message=f"Не удалось открыть в проводнике: {e}",
                is_fatal=self.is_fatal,
            )


class WebhookNotificationStep(PostProcessingStep):
    """Шаг отправки Webhook-уведомления с метаданными о завершении записи."""

    def __init__(
        self,
        webhook_url: str,
        webhook_secret: str | None = None,
        is_fatal: bool = False,
        timeout_seconds: int = 15,
    ) -> None:
        super().__init__(
            step_type=PostProcessingStepType.WEBHOOK,
            is_fatal=is_fatal,
            timeout_seconds=timeout_seconds,
        )
        self.webhook_url = webhook_url
        self.webhook_secret = webhook_secret
        self._sender = WebhookSender(WebhookSigner())

    def execute(self, input_path: Path) -> StepResult:
        start_time = time.monotonic()
        if not self.webhook_url:
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                error_message="URL вебхука не указан",
                is_fatal=self.is_fatal,
            )

        try:
            file_size = input_path.stat().st_size if input_path.exists() else 0
            data = {
                "file_path": str(input_path),
                "file_name": input_path.name,
                "file_size_bytes": file_size,
                "status": "ready",
            }

            success, response_time = self._sender.send(
                url=self.webhook_url,
                event="post_processing.completed",
                data=data,
                secret=self.webhook_secret,
            )

            duration = time.monotonic() - start_time
            if success:
                return StepResult(
                    step_type=self.step_type,
                    success=True,
                    input_path=input_path,
                    output_path=input_path,
                    duration_seconds=duration,
                    details={
                        "webhook_url": self.webhook_url,
                        "response_time_ms": response_time,
                    },
                )
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                duration_seconds=duration,
                error_message=f"Ошибка доставки Webhook на {self.webhook_url}",
                is_fatal=self.is_fatal,
            )
        except Exception as e:
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                duration_seconds=time.monotonic() - start_time,
                error_message=f"Исключение при отправке Webhook: {e}",
                is_fatal=self.is_fatal,
            )
