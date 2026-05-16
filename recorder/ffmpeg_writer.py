"""
Модуль FFmpeg видеозаписи
========================

Прямая запись видео через FFmpeg pipe без перекодирования.
"""

import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

import numpy as np

from logger_config import get_module_logger
from recorder.utils import get_ffmpeg_path, get_subprocess_creationflags

logger = get_module_logger(__name__)

_T = TypeVar("_T")


@dataclass
class RetryPolicy:
    """Политика повторных попыток для операций с FFmpeg."""

    max_attempts: int = 3
    initial_delay_s: float = 0.5
    backoff_factor: float = 2.0
    max_delay_s: float = 10.0


def retry_with_backoff(
    fn: Callable[[], _T],
    policy: RetryPolicy,
    *,
    retriable_exceptions: tuple[type[Exception], ...] = (IOError, OSError),
) -> _T:
    """Вызывает fn() с повторами при retriable_exceptions согласно policy.

    Каждая неудачная попытка логируется через logging.warning с номером попытки,
    описанием ошибки и задержкой до следующей попытки.

    Args:
        fn: Вызываемый объект без аргументов.
        policy: Параметры retry.
        retriable_exceptions: Типы исключений, при которых делается повтор.

    Returns:
        Результат fn() при успехе.

    Raises:
        Последнее исключение если все попытки исчерпаны.
    """
    delay = policy.initial_delay_s
    last_exc: Exception | None = None

    for attempt in range(1, policy.max_attempts + 1):
        try:
            return fn()
        except retriable_exceptions as exc:
            last_exc = exc
            if attempt < policy.max_attempts:
                logger.warning(
                    "Попытка %d/%d не удалась: %s. Следующая через %.2f с",
                    attempt,
                    policy.max_attempts,
                    exc,
                    delay,
                )
                time.sleep(delay)
                delay = min(delay * policy.backoff_factor, policy.max_delay_s)
            else:
                logger.warning(
                    "Попытка %d/%d не удалась: %s. Попытки исчерпаны",
                    attempt,
                    policy.max_attempts,
                    exc,
                )

    raise last_exc  # type: ignore[misc]


_FFMPEG_CLOSE_TIMEOUT_SECONDS = 180
_FFMPEG_TERMINATE_GRACE_TIMEOUT_SECONDS = 15
_FFMPEG_STDERR_TAIL_LINES = 50
_STDERR_READER_JOIN_TIMEOUT_SECONDS = 2.0


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
        retry_policy: RetryPolicy | None = None,
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
            retry_policy: Политика повторных попыток; None = RetryPolicy()
        """
        self._output_path = Path(output_path)
        self._width = width
        self._height = height
        self._fps = fps
        self._codec = codec
        self._bitrate = bitrate
        self._preset = preset
        self._pixel_format = pixel_format
        self._retry_policy = (
            retry_policy if retry_policy is not None else RetryPolicy()
        )
        self._ffmpeg_path = get_ffmpeg_path()

        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._frame_count = 0
        self._start_time = 0.0
        self._stderr_tail: deque[str] = deque(maxlen=_FFMPEG_STDERR_TAIL_LINES)
        self._stderr_reader: threading.Thread | None = None
        self._stderr_stream: Any | None = None
        self._is_corrupted = False

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

    @property
    def is_corrupted(self) -> bool:
        """Проверка что файл повреждён (запись прервана)."""
        return self._is_corrupted

    def mark_corrupted(self) -> None:
        """Пометить файл как повреждённый."""
        self._is_corrupted = True

    def _terminate_process_safely(self) -> None:
        """Безопасно завершает FFmpeg процесс при ошибке."""
        process = self._process
        if process is None:
            return

        stdin = process.stdin
        if stdin is not None:
            try:
                stdin.close()
            except Exception:
                pass

        try:
            process.terminate()
            process.wait(timeout=_FFMPEG_TERMINATE_GRACE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            logger.warning(
                "FFmpeg не завершился после terminate, выполняется kill"
            )
            process.kill()
        except Exception as e:
            logger.warning(f"Ошибка при terminate FFmpeg: {e}")
            try:
                process.kill()
            except Exception:
                pass

        self._stop_stderr_reader()

    def cleanup_corrupted_file(self) -> bool:
        """
        Удалить повреждённый файл.

        Returns:
            True если файл удалён или не существовал
        """
        if not self._is_corrupted:
            return True

        try:
            if self._output_path.exists():
                self._output_path.unlink()
                logger.info(f"Удалён повреждённый файл: {self._output_path}")
            return True
        except OSError as e:
            logger.error(f"Не удалось удалить повреждённый файл: {e}")
            return False

    def open(self) -> bool:
        """
        Открытие FFmpeg процесса для записи.

        Returns:
            True если успешно открыто
        """
        try:
            ffmpeg_bin = self._ffmpeg_path
            if ffmpeg_bin is None:
                logger.error("FFmpeg не найден")
                return False

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
                ffmpeg_bin,
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

            creationflags = get_subprocess_creationflags()
            popen_kwargs: dict[str, Any] = {
                "stdin": subprocess.PIPE,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.PIPE,
                "text": False,
                "bufsize": 0,
            }
            if creationflags:
                popen_kwargs["creationflags"] = creationflags

            self._process = subprocess.Popen(cmd, **popen_kwargs)

            self._stderr_tail.clear()
            self._start_stderr_reader(self._process.stderr)

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
        if self._is_corrupted:
            return False

        try:
            with self._lock:
                if self._process is None:
                    return False
                if self._process.poll() is not None:
                    self._is_corrupted = True
                    dead_process = True
                else:
                    dead_process = False
                    if self._process.stdin:
                        # Используем memoryview для zero-copy если кадр
                        # уже contiguous C-order — иначе tobytes() как fallback.
                        contiguous = np.ascontiguousarray(frame)
                        frame_data: bytes | memoryview = memoryview(contiguous)
                        stdin = self._process.stdin

                        def _write_frame() -> None:
                            stdin.write(frame_data)

                        retry_with_backoff(
                            _write_frame,
                            self._retry_policy,
                            retriable_exceptions=(IOError, OSError),
                        )
                        self._frame_count += 1

            if dead_process:
                self._log_stderr_tail(
                    "процесс завершился неожиданно во время write"
                )
                return False
            return True
        except BrokenPipeError:
            logger.error("FFmpeg pipe broken, помечаем файл как повреждённый")
            self._is_corrupted = True
            self._terminate_process_safely()
            return False
        except OSError as e:
            logger.error(f"Ошибка записи кадра после всех попыток: {e}")
            self._is_corrupted = True
            self._terminate_process_safely()
            return False
        except Exception as e:
            logger.error(f"Ошибка записи кадра: {e}")
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
                logger.error(
                    "FFmpeg завершился с кодом %s при записи %s",
                    process.returncode,
                    self._output_path,
                )
                self._log_stderr_tail("ошибочное завершение")
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
                self._log_stderr_tail("таймаут завершения")
                return False
            except Exception as e:
                logger.error(f"Ошибка terminate FFmpeg: {e}")
                process.kill()
                self._log_stderr_tail("ошибка terminate")
                return False

            if process.returncode != 0:
                logger.error(
                    "FFmpeg завершён с кодом %s после terminate (%s)",
                    process.returncode,
                    self._output_path,
                )
                self._log_stderr_tail("ошибочное завершение после terminate")
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
            self._stop_stderr_reader()

    def _start_stderr_reader(self, stream: Any | None) -> None:
        """
        Запуск фонового чтения stderr.

        Args:
            stream: Поток stderr процесса FFmpeg.
        """
        if stream is None:
            return

        self._stderr_stream = stream

        reader = threading.Thread(
            target=self._read_stderr,
            args=(stream,),
            daemon=True,
            name="ffmpeg-stderr-reader",
        )
        self._stderr_reader = reader
        reader.start()

    def _stop_stderr_reader(self) -> None:
        """Останавливает stderr-reader и дожидается завершения потока."""
        stream = self._stderr_stream
        reader = self._stderr_reader
        self._stderr_stream = None
        self._stderr_reader = None

        if stream is not None:
            try:
                stream.close()
            except Exception:
                logger.debug("Не удалось закрыть stderr stream FFmpeg")

        if reader is None:
            return

        is_alive = getattr(reader, "is_alive", None)
        join = getattr(reader, "join", None)
        if callable(is_alive) and callable(join) and is_alive():
            join(timeout=_STDERR_READER_JOIN_TIMEOUT_SECONDS)
            if is_alive():
                logger.warning(
                    "stderr-reader поток FFmpeg не завершился за %.1f секунд",
                    _STDERR_READER_JOIN_TIMEOUT_SECONDS,
                )

    def _read_stderr(self, stream: Any) -> None:
        """
        Чтение stderr FFmpeg в фоновом потоке.

        Args:
            stream: Поток stderr процесса FFmpeg.
        """
        try:
            while self._process is not None:
                line = stream.readline()
                if not line:
                    break

                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")

                cleaned_line = line.rstrip("\r\n")
                with self._lock:
                    self._stderr_tail.append(cleaned_line)
        except Exception as e:
            logger.debug(f"Ошибка чтения stderr FFmpeg: {e}")

    def _log_stderr_tail(self, reason: str) -> None:
        """
        Логирование хвоста stderr при ошибочном завершении.

        Args:
            reason: Причина логирования.
        """
        with self._lock:
            tail_lines = list(self._stderr_tail)

        if not tail_lines:
            logger.error("FFmpeg stderr пуст после %s", reason)
            return

        tail_text = "\n".join(tail_lines[-_FFMPEG_STDERR_TAIL_LINES:])
        logger.error(
            "FFmpeg stderr tail после %s (последние %s строк):\n%s",
            reason,
            len(tail_lines),
            tail_text,
        )

    def __enter__(self) -> "FFmpegVideoWriter":
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
