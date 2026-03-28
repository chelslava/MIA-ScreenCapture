"""
Модуль FFmpeg видеозаписи
========================

Прямая запись видео через FFmpeg pipe без перекодирования.
"""

import subprocess
import threading
import time
from pathlib import Path

import numpy as np

from logger_config import get_module_logger

logger = get_module_logger(__name__)

_FFMPEG_CLOSE_TIMEOUT_SECONDS = 180
_FFMPEG_TERMINATE_GRACE_TIMEOUT_SECONDS = 15


class FFmpegVideoWriter:
    """
    Видеозапись через FFmpeg pipe.

    Позволяет записывать видео напрямую в MP4 с указанным кодеком,
    избегая перекодирования в конце записи.
    """

    CODEC_ARGS = {
        "libx264": [
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "23",
        ],
        "libx264-fast": [
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "23",
        ],
        "h264_nvenc": [
            "-c:v",
            "h264_nvenc",
            "-preset",
            "p1",
            "-rc",
            "vbr",
            "-cq",
            "23",
        ],
        "h264_qsv": [
            "-c:v",
            "h264_qsv",
            "-preset",
            "fast",
            "-global_quality",
            "23",
        ],
        "libx265": [
            "-c:v",
            "libx265",
            "-preset",
            "medium",
            "-crf",
            "28",
        ],
        "hevc_nvenc": [
            "-c:v",
            "hevc_nvenc",
            "-preset",
            "p1",
            "-rc",
            "vbr",
            "-cq",
            "28",
        ],
    }

    def __init__(
        self,
        output_path: Path,
        width: int,
        height: int,
        fps: int = 30,
        codec: str = "libx264",
        bitrate: str = "2M",
        preset: str = "medium",
        pixel_format: str = "bgr24",
    ):
        """
        Инициализация FFmpeg видеозаписи.

        Args:
            output_path: Путь к выходному файлу
            width: Ширина видео
            height: Высота видео
            fps: Частота кадров
            codec: Кодек (libx264, h264_nvenc, h264_qsv, libx265)
            bitrate: Битрейт (2M, 4M, etc.)
            preset: Preset кодирования
            pixel_format: Формат пикселей (bgr24 для OpenCV)
        """
        self._output_path = Path(output_path)
        self._width = width
        self._height = height
        self._fps = fps
        self._codec = codec
        self._bitrate = bitrate
        self._preset = preset
        self._pixel_format = pixel_format

        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._frame_count = 0
        self._start_time = 0.0

    @property
    def frame_count(self) -> int:
        """Количество записанных кадров."""
        return self._frame_count

    @property
    def elapsed_time(self) -> float:
        """Время записи в секундах."""
        if self._start_time == 0:
            return 0
        return time.time() - self._start_time

    @property
    def is_opened(self) -> bool:
        """Проверка что писатель открыт."""
        return self._process is not None and self._process.poll() is None

    def open(self) -> bool:
        """
        Открытие FFmpeg процесса для записи.

        Returns:
            True если успешно открыто
        """
        try:
            self._output_path.parent.mkdir(parents=True, exist_ok=True)

            codec_key = self._codec
            if self._codec == "libx264" and self._preset in (
                "ultrafast",
                "superfast",
                "veryfast",
                "faster",
                "fast",
            ):
                codec_key = "libx264-fast"

            codec_args = list(
                self.CODEC_ARGS.get(codec_key, self.CODEC_ARGS["libx264"])
            )

            if self._preset != "medium" and self._codec.startswith("libx"):
                for i, arg in enumerate(codec_args):
                    if arg == "-preset" and i + 1 < len(codec_args):
                        codec_args[i + 1] = self._preset

            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "rawvideo",
                "-vcodec",
                "rawvideo",
                "-s",
                f"{self._width}x{self._height}",
                "-pix_fmt",
                self._pixel_format,
                "-r",
                str(self._fps),
                "-i",
                "-",
                *codec_args,
                "-b:v",
                self._bitrate,
                "-movflags",
                "+faststart",
                str(self._output_path),
            ]

            logger.info(f"Запуск FFmpeg: {' '.join(cmd)}")

            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )

            self._start_time = time.time()
            self._frame_count = 0

            return True

        except Exception as e:
            logger.error(f"Ошибка открытия FFmpeg: {e}")
            return False

    def write(self, frame: np.ndarray) -> bool:
        """
        Запись кадра в видео.

        Args:
            frame: Кадр в формате numpy array (H, W, C)

        Returns:
            True если кадр успешно записан
        """
        if not self.is_opened:
            return False

        try:
            with self._lock:
                if self._process and self._process.stdin:
                    self._process.stdin.write(frame.tobytes())
                    self._frame_count += 1
                    return True
        except BrokenPipeError:
            logger.error("FFmpeg pipe broken")
            return False
        except Exception as e:
            logger.error(f"Ошибка записи кадра: {e}")
            return False

        return False

    def close(self) -> bool:
        """
        Закрытие FFmpeg процесса и завершение записи.

        Returns:
            True если успешно закрыто
        """
        if self._process is None:
            return True

        process = self._process

        try:
            with self._lock:
                if process.stdin:
                    try:
                        process.stdin.close()
                    except Exception:
                        # Pipe может быть уже закрыт завершившимся процессом.
                        pass

            process.wait(timeout=_FFMPEG_CLOSE_TIMEOUT_SECONDS)

            if process.returncode != 0:
                stderr = process.stderr.read().decode(
                    "utf-8", errors="ignore"
                )
                logger.error(f"FFmpeg error: {stderr}")
                return False

            logger.info(
                f"Запись завершена: {self._output_path} "
                f"({self._frame_count} кадров, {self.elapsed_time:.1f}s)"
            )
            return True

        except subprocess.TimeoutExpired:
            logger.warning(
                "Таймаут ожидания FFmpeg при мягком завершении, "
                "выполняется terminate"
            )
            try:
                process.terminate()
                process.wait(timeout=_FFMPEG_TERMINATE_GRACE_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                logger.error(
                    "FFmpeg не завершился после terminate, выполняется kill"
                )
                process.kill()
                return False
            except Exception as e:
                logger.error(f"Ошибка terminate FFmpeg: {e}")
                process.kill()
                return False

            if process.returncode != 0:
                stderr = process.stderr.read().decode(
                    "utf-8", errors="ignore"
                )
                logger.error(f"FFmpeg завершён с ошибкой: {stderr}")
                return False
            logger.info(
                "FFmpeg завершился после terminate: "
                f"{self._output_path} ({self._frame_count} кадров)"
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка закрытия FFmpeg: {e}")
            return False
        finally:
            self._process = None

    def __enter__(self) -> "FFmpegVideoWriter":
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
