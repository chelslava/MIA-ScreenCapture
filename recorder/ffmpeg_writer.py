"""
Модуль FFmpeg видеозаписи
========================

Прямая запись видео через FFmpeg pipe без перекодирования.
"""

import subprocess
import tempfile
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import IO, Any, TypeVar

import numpy as np

from core.event_bus import EventBus, RecordingEvent, RecordingEventType
from logger_config import get_module_logger
from recorder.utils import (
    get_available_disk_space,
    get_ffmpeg_path,
    get_subprocess_creationflags,
    verify_video_integrity,
)

logger = get_module_logger(__name__)

_FFMPEG_CLOSE_TIMEOUT_SECONDS = 180
_FFMPEG_TERMINATE_GRACE_TIMEOUT_SECONDS = 15
_FFMPEG_STDERR_TAIL_LINES = 50
_FFMPEG_STDERR_READER_JOIN_TIMEOUT_SECONDS = 2.0

_T = TypeVar("_T")


@dataclass
class RetryPolicy:
    """
    Политика повторных попыток для операций записи.

    Attributes:
        max_attempts: Максимальное число попыток.
        initial_delay_s: Начальная задержка перед повтором.
        backoff_factor: Множитель задержки после каждой попытки.
        max_delay_s: Максимальная задержка между попытками.
    """

    max_attempts: int = 3
    initial_delay_s: float = 0.5
    backoff_factor: float = 2.0
    max_delay_s: float = 10.0


def retry_with_backoff(
    func: Callable[[], _T],
    policy: RetryPolicy,
) -> _T:
    """
    Повторяет вызов func при возникновении OSError или RuntimeError.

    RuntimeError считается временной ошибкой записи в pipe FFmpeg
    (например, отсоединение буфера или сбой подсистемы ввода-вывода),
    поэтому такие ошибки тоже обрабатываются повторными попытками.

    Args:
        func: Функция без аргументов, возвращающая результат.
        policy: Политика повторных попыток.

    Returns:
        Результат успешного вызова func.

    Raises:
        OSError: Исключение ввода-вывода, которое не удалось обработать.
        RuntimeError: Ошибка выполнения, которую не удалось обработать.
    """
    attempt = 0
    delay = policy.initial_delay_s

    while True:
        try:
            return func()
        except (OSError, RuntimeError) as e:
            attempt += 1
            if attempt >= policy.max_attempts:
                raise

            logger.warning(
                "Ошибка записи %s/%s: %s; повтор через %.1fс",
                attempt,
                policy.max_attempts,
                e,
                delay,
            )
            time.sleep(delay)
            delay = min(delay * policy.backoff_factor, policy.max_delay_s)


class DiskSpaceLevel(Enum):
    """Уровень свободного места на диске для текущего сегмента записи."""

    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


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
        max_recovery_attempts: int = 3,
        disk_warning_mb: float = 1024.0,
        disk_critical_mb: float = 100.0,
        disk_check_interval_s: float = 30.0,
        max_segment_size_mb: float | None = None,
        max_segment_duration_s: float | None = None,
        event_bus: "EventBus | None" = None,
        health_check_interval_s: float = 1.0,
        enable_frame_skip: bool = False,
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
            retry_policy: Политика повторных попыток при ошибках записи.
            max_recovery_attempts: Сколько раз пытаться перезапустить
                FFmpeg-процесс при его аварийном завершении, прежде чем
                пометить запись повреждённой. Каждый успешный перезапуск
                продолжает запись в новый файл-сегмент
                (`{stem}_part{N}{suffix}`) — см. `segment_paths`.
            disk_warning_mb: Порог свободного места (MB), ниже которого
                фиксируется предупреждение (запись продолжается).
            disk_critical_mb: Порог свободного места (MB), ниже которого
                запись останавливается превентивно (graceful stop), чтобы
                не допустить падения FFmpeg из-за нехватки места.
            disk_check_interval_s: Минимальный интервал между проверками
                свободного места (секунды), чтобы не дёргать `shutil`
                на каждый кадр.
            max_segment_size_mb: Если задано, при достижении этого размера
                текущий сегмент завершается штатно и запись продолжается
                в новом файле-сегменте (`{stem}_part{N}{suffix}`, та же
                нумерация, что и при crash-recovery). `None` — разбиение
                по размеру отключено.
            max_segment_duration_s: Аналогично `max_segment_size_mb`, но по
                длительности текущего сегмента. `None` — отключено.
        """
        self._output_path = Path(output_path)
        self._width = width
        self._height = height
        self._fps = fps
        self._codec = codec
        self._bitrate = bitrate
        self._preset = preset
        self._pixel_format = pixel_format
        self._ffmpeg_path = get_ffmpeg_path()
        self._retry_policy = (
            retry_policy if retry_policy is not None else RetryPolicy()
        )
        self._max_recovery_attempts = max_recovery_attempts
        self._disk_warning_mb = disk_warning_mb
        self._disk_critical_mb = disk_critical_mb
        self._disk_check_interval_s = disk_check_interval_s
        self._max_segment_size_mb = max_segment_size_mb
        self._max_segment_duration_s = max_segment_duration_s
        self._event_bus = event_bus

        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._frame_count = 0
        self._start_time = 0.0
        self._stderr_tail: deque[str] = deque(maxlen=_FFMPEG_STDERR_TAIL_LINES)
        self._stderr_reader: threading.Thread | None = None
        self._stderr_stream: IO[bytes] | None = None
        self._is_corrupted = False

        self._current_segment_path = self._output_path
        self._segment_paths: list[Path] = []
        self._recovery_count = 0
        self._total_downtime_s = 0.0

        self._last_disk_check_time = 0.0
        self._disk_space_critical = False
        self._disk_space_warning_logged = False
        self._last_free_mb: float | None = None

        self._current_segment_bytes = 0
        self._segment_start_time = 0.0
        self._segment_rotation_failed = False

        # Health-check мониторинг FFmpeg-процесса (#85): фоновый поток
        # с периодом health_check_interval_s дёргает process.poll() и
        # логирует падение *между* write() — иначе окно потери кадров
        # ограничено только частотой записи.
        self._health_check_interval_s = max(0.1, health_check_interval_s)
        self._health_thread: threading.Thread | None = None
        self._health_stop = threading.Event()
        self._health_fail_logged = False

        # Frame-skip при перегрузке (#87): при превышении целевого
        # интервала кадра на 2× подряд — раз в max_consecutive_late_frames
        # кадр скипнуть, чтобы не буферизировать. Пользовательский
        # opt-in — по умолчанию совместимость (все кадры пишутся).
        self._enable_frame_skip = enable_frame_skip
        self._expected_frame_interval_s = 1.0 / max(fps, 1)
        self._last_frame_write_end = 0.0
        self._consecutive_late_frames = 0
        self._max_consecutive_late_frames = 5
        self._skipped_frames = 0

    @property
    def skipped_frames(self) -> int:
        """Кадров скипнуто из-за перегрузки (#87)."""
        return self._skipped_frames

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

    @property
    def recovery_count(self) -> int:
        """Количество успешных перезапусков FFmpeg после сбоя процесса."""
        return self._recovery_count

    @property
    def total_downtime_s(self) -> float:
        """Суммарное время простоя записи во время восстановлений (сек)."""
        return self._total_downtime_s

    @property
    def is_disk_space_critical(self) -> bool:
        """Признак, что запись остановлена из-за критической нехватки места."""
        return self._disk_space_critical

    @property
    def last_known_free_mb(self) -> float | None:
        """Последнее известное свободное место (MB) на диске сегмента."""
        return self._last_free_mb

    @property
    def is_segment_rotation_failed(self) -> bool:
        """
        Признак, что плановая ротация сегмента (#53) не смогла открыть
        новый файл-сегмент.

        В отличие от `is_corrupted`, предыдущие сегменты при этом валидны
        и штатно закрыты — останов не аварийный, файл не должен удаляться.
        """
        return self._segment_rotation_failed

    @property
    def segment_paths(self) -> list[Path]:
        """
        Пути всех файлов-сегментов записи.

        Пустой список, если восстановлений после сбоя не было (запись —
        единственный файл `output_path`). Иначе — все сегменты, включая
        текущий активный, в порядке записи.
        """
        if (
            not self._segment_paths
            and self._current_segment_path == self._output_path
        ):
            return []
        return [*self._segment_paths, self._current_segment_path]

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
        self._current_segment_path = self._output_path
        self._start_time = time.time()
        self._segment_start_time = self._start_time
        self._current_segment_bytes = 0
        self._frame_count = 0
        # Сброс frame-skip счётчиков (#87)
        self._last_frame_write_end = 0.0
        self._consecutive_late_frames = 0
        self._skipped_frames = 0
        ok = self._open_process(self._output_path)
        if ok:
            self._start_health_monitor()
        return ok

    def _next_segment_path(self) -> Path:
        """Возвращает путь для следующего сегмента восстановления."""
        part_number = len(self._segment_paths) + 2
        stem = self._output_path.stem
        suffix = self._output_path.suffix
        return self._output_path.with_name(f"{stem}_part{part_number}{suffix}")

    def _attempt_recovery(self) -> bool:
        """
        Пытается перезапустить FFmpeg-процесс в новом файле-сегменте.

        Returns:
            True, если новый процесс успешно открыт.
        """
        if self._recovery_count >= self._max_recovery_attempts:
            logger.error(
                "Превышен лимит попыток восстановления FFmpeg (%s)",
                self._max_recovery_attempts,
            )
            if self._event_bus:
                self._event_bus.publish(
                    RecordingEvent(
                        event_type=RecordingEventType.ERROR,
                        payload={
                            "type": "ffmpeg_crash",
                            "message": "FFmpeg crash, all recovery attempts failed",
                        },
                    )
                )
            return False

        recovery_start = time.time()
        attempt_number = self._recovery_count + 1
        logger.warning(
            "FFmpeg процесс прервался, попытка восстановления %s/%s",
            attempt_number,
            self._max_recovery_attempts,
        )

        if self._event_bus:
            self._event_bus.publish(
                RecordingEvent(
                    event_type=RecordingEventType.WARNING,
                    payload={
                        "type": "ffmpeg_recovery",
                        "message": f"FFmpeg crash, attempt {attempt_number}/{self._max_recovery_attempts}",
                    },
                )
            )

        self._terminate_process_safely()

        new_segment_path = self._next_segment_path()
        if not self._open_process(new_segment_path):
            logger.error(
                "Не удалось открыть новый сегмент при восстановлении: %s",
                new_segment_path,
            )
            if self._event_bus:
                self._event_bus.publish(
                    RecordingEvent(
                        event_type=RecordingEventType.ERROR,
                        payload={
                            "type": "ffmpeg_crash",
                            "message": f"FFmpeg crash, attempt {attempt_number}/{self._max_recovery_attempts} failed",
                        },
                    )
                )
            return False

        self._segment_paths.append(self._current_segment_path)
        self._current_segment_path = new_segment_path
        self._recovery_count += 1
        self._total_downtime_s += time.time() - recovery_start
        self._current_segment_bytes = 0
        self._segment_start_time = time.time()

        logger.warning(
            "FFmpeg восстановлен (попытка %s/%s), запись продолжена в новом сегменте: %s",
            attempt_number,
            self._max_recovery_attempts,
            new_segment_path,
        )
        return True

    def _open_process(self, output_path: Path) -> bool:
        """
        Запускает FFmpeg-процесс для записи в указанный файл.

        Args:
            output_path: Путь к файлу-сегменту, в который пишет этот процесс.

        Returns:
            True если успешно открыто
        """
        try:
            ffmpeg_bin = self._ffmpeg_path
            if ffmpeg_bin is None:
                logger.error("FFmpeg не найден")
                return False

            output_path.parent.mkdir(parents=True, exist_ok=True)

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
                str(output_path),
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

            return True

        except Exception as e:
            logger.error(f"Ошибка открытия FFmpeg: {e}")
            return False

    def _check_disk_space(self) -> DiskSpaceLevel:
        """
        Проверяет свободное место на диске текущего сегмента записи.

        Rate-limited интервалом `disk_check_interval_s`, чтобы не вызывать
        `shutil.disk_usage` на каждый кадр. Между проверками возвращает
        последний известный уровень.

        Returns:
            Текущий (или последний известный) уровень свободного места.
        """
        now = time.time()
        if now - self._last_disk_check_time < self._disk_check_interval_s:
            if self._disk_space_critical:
                return DiskSpaceLevel.CRITICAL
            if self._disk_space_warning_logged:
                return DiskSpaceLevel.WARNING
            return DiskSpaceLevel.OK

        self._last_disk_check_time = now

        try:
            free_bytes = get_available_disk_space(self._current_segment_path)
        except OSError as e:
            logger.warning("Не удалось проверить свободное место: %s", e)
            return DiskSpaceLevel.OK

        free_mb = free_bytes / (1024 * 1024)
        self._last_free_mb = free_mb

        if free_mb < self._disk_critical_mb:
            return DiskSpaceLevel.CRITICAL

        if free_mb < self._disk_warning_mb:
            if not self._disk_space_warning_logged:
                logger.warning(
                    "Мало места на диске: %.1f MB свободно (порог %.1f MB)",
                    free_mb,
                    self._disk_warning_mb,
                )
                self._disk_space_warning_logged = True
            return DiskSpaceLevel.WARNING

        self._disk_space_warning_logged = False
        return DiskSpaceLevel.OK

    def _should_rotate_segment(self) -> bool:
        """Проверяет, нужно ли начать новый плановый сегмент записи (#53)."""
        if (
            self._max_segment_size_mb is not None
            and self._current_segment_bytes / (1024 * 1024)
            >= self._max_segment_size_mb
        ):
            return True

        return (
            self._max_segment_duration_s is not None
            and time.time() - self._segment_start_time
            >= self._max_segment_duration_s
        )

    def _rotate_segment(
        self,
        new_width: int | None = None,
        new_height: int | None = None,
    ) -> bool:
        """
        Завершает текущий сегмент штатно и открывает следующий.

        Переиспользует `close()` (тот же graceful-путь, что и при
        финальном завершении записи — корректный moov atom) и
        `_next_segment_path()`/`_segment_paths` — те же примитивы, что
        использует crash-recovery (#45), так что плановые и
        восстановительные сегменты делят единую нумерацию `_partN`.

        Args:
            new_width: Если задано, новый сегмент открывается с этой
                шириной кадра (#48 — смена источника захвата на лету).
            new_height: Аналогично `new_width`, для высоты кадра.

        Returns:
            True, если новый сегмент успешно открыт.
        """
        previous_segment_path = self._current_segment_path
        finalized_ok = self.close(finalize_segments=False)
        if not finalized_ok:
            logger.warning(
                "Сегмент %s завершён с ошибкой при плановой ротации",
                previous_segment_path,
            )

        if new_width is not None:
            self._width = new_width
        if new_height is not None:
            self._height = new_height

        new_segment_path = self._next_segment_path()
        if not self._open_process(new_segment_path):
            logger.error(
                "Не удалось открыть новый сегмент при плановой ротации: %s",
                new_segment_path,
            )
            return False

        self._segment_paths.append(previous_segment_path)
        self._current_segment_path = new_segment_path
        self._current_segment_bytes = 0
        self._segment_start_time = time.time()

        logger.info(
            "Плановая ротация сегмента записи (лимит размера/длительности): %s",
            new_segment_path,
        )
        return True

    def switch_resolution(self, width: int, height: int) -> bool:
        """
        Продолжает запись в новом сегменте с другим разрешением кадра (#48).

        Используется при горячем переключении источника захвата на источник
        другого размера (например, монитор -> окно). Текущий сегмент
        завершается штатно, новый открывается с указанными `width`/`height`
        и делит нумерацию `_partN` с остальными сегментами этой записи.

        Args:
            width: Ширина кадра нового источника.
            height: Высота кадра нового источника.

        Returns:
            True, если новый сегмент успешно открыт с новым разрешением.
        """
        return self._rotate_segment(new_width=width, new_height=height)

    def write(self, frame: np.ndarray) -> bool:
        if self._is_corrupted:
            return False

        if self._segment_rotation_failed:
            return False

        # Frame skip при перегрузке (#87): если запись стабильно отстаёт —
        # скипаем каждый N-й кадр, чтобы не буферизировать.
        if self._enable_frame_skip and self._consecutive_late_frames >= (
            self._max_consecutive_late_frames
        ):
            self._skipped_frames += 1
            self._consecutive_late_frames = 0
            logger.debug(
                "Пропуск кадра #%d из-за перегрузки "
                "(consecutive_late=%d, threshold=%.3fс)",
                self._frame_count,
                self._consecutive_late_frames,
                self._expected_frame_interval_s,
            )
            return True  # кадр "записан" — это скип, не ошибка

        if not self._disk_space_critical:
            disk_level = self._check_disk_space()
            if disk_level is DiskSpaceLevel.CRITICAL:
                self._disk_space_critical = True
                logger.error(
                    "Критическая нехватка места на диске (%.1f MB) — "
                    "запись останавливается превентивно, без потери "
                    "уже записанных данных",
                    self._last_free_mb
                    if self._last_free_mb is not None
                    else 0.0,
                )

        if self._disk_space_critical:
            return False

        def _do_write() -> None:
            if self._process is None or self._process.poll() is not None:
                raise OSError("process died")
            if self._process.stdin:
                self._process.stdin.write(frame.tobytes())

        for _ in range(self._max_recovery_attempts + 1):
            if not self.is_opened:
                if self._process is None or not self._attempt_recovery():
                    self._is_corrupted = True
                    self._terminate_process_safely()
                    return False
                continue

            try:
                write_start = time.time()
                retry_with_backoff(_do_write, self._retry_policy)
                write_end = time.time()
                if self._enable_frame_skip:
                    # Измеряем время записи кадра — основа для skip-решения
                    # на следующих вызовах (#87). Late когда > 2× target.
                    write_dt = write_end - write_start
                    if write_dt > 2.0 * self._expected_frame_interval_s:
                        self._consecutive_late_frames += 1
                    else:
                        self._consecutive_late_frames = 0
                    self._last_frame_write_end = write_end
                with self._lock:
                    self._frame_count += 1
                self._current_segment_bytes += frame.nbytes
                if (
                    self._should_rotate_segment()
                    and not self._rotate_segment()
                ):
                    self._segment_rotation_failed = True
                return True
            except OSError as e:
                logger.warning(
                    "Ошибка записи кадра после %s попыток: %s",
                    self._retry_policy.max_attempts,
                    e,
                )
                if self.is_opened:
                    # Процесс жив, но запись стабильно не проходит
                    # (например, диск заполнен) — перезапуск FFmpeg не
                    # устранит причину, восстановление здесь не поможет.
                    self._is_corrupted = True
                    self._terminate_process_safely()
                    return False
                continue
            except Exception as e:
                logger.error("Ошибка записи кадра: %s", e)
                if self.is_opened:
                    # Процесс жив, но запись стабильно не проходит по
                    # не-I/O причине (например, повреждён буфер кадра).
                    # Восстановление FFmpeg не устранит причину —
                    # помечаем файл повреждённым, чтобы не потерять
                    # запись молча.
                    self._is_corrupted = True
                    self._terminate_process_safely()
                    return False
                # Процесс мёртв — следующая итерация цикла попробует
                # восстановить запись в новый сегмент.
                continue

        self._is_corrupted = True
        self._terminate_process_safely()
        return False

    def _merge_segments(self) -> bool:
        """
        Объединяет сегменты через временный файл рядом с итоговым.

        Канонический файл заменяется атомарно только после успешного FFmpeg и
        проверки целостности. При любой ошибке исходные сегменты сохраняются.

        Returns:
            True при успешном слиянии, иначе False.
        """
        segments = self.segment_paths
        if len(segments) <= 1:
            return True

        logger.info(
            "Начинается слияние %s сегментов записи в единый файл",
            len(segments),
        )

        # Build FFmpeg concat command
        ffmpeg_bin = self._ffmpeg_path
        if ffmpeg_bin is None:
            logger.error("FFmpeg не найден для слияния сегментов")
            return False

        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        concat_file: Path | None = None
        merge_output_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix=f".{self._output_path.stem}.segments-",
                suffix=".concat",
                dir=self._output_path.parent,
                delete=False,
            ) as concat_stream:
                concat_file = Path(concat_stream.name)
                for segment_path in segments:
                    escaped_path = str(segment_path).replace("'", "'\"'\"'")
                    concat_stream.write(f"file '{escaped_path}'\n")

            with tempfile.NamedTemporaryFile(
                prefix=f".{self._output_path.stem}.merge-",
                suffix=self._output_path.suffix,
                dir=self._output_path.parent,
                delete=False,
            ) as merge_output:
                merge_output_path = Path(merge_output.name)

            cmd = [
                ffmpeg_bin,
                "-nostdin",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_file),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(merge_output_path),
            ]

            logger.info(
                "FFmpeg concat command: %s",
                " ".join(cmd),
            )

            creationflags = get_subprocess_creationflags()
            popen_kwargs: dict[str, Any] = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.PIPE,
                "text": False,
            }
            if creationflags:
                popen_kwargs["creationflags"] = creationflags

            process = subprocess.Popen(cmd, **popen_kwargs)
            try:
                _, stderr = process.communicate(
                    timeout=_FFMPEG_CLOSE_TIMEOUT_SECONDS
                )
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
                logger.error(
                    "Таймаут слияния сегментов FFmpeg после %s секунд",
                    _FFMPEG_CLOSE_TIMEOUT_SECONDS,
                )
                return False

            if process.returncode != 0:
                stderr_text = stderr.decode("utf-8", errors="replace").strip()
                logger.error(
                    "Ошибка слияния сегментов (ffmpeg code %s): %s",
                    process.returncode,
                    stderr_text,
                )
                return False

            if merge_output_path.stat().st_size == 0:
                logger.error("FFmpeg создал пустой файл при слиянии сегментов")
                return False

            integrity_result = verify_video_integrity(merge_output_path)
            if not integrity_result.valid:
                logger.error(
                    "Объединённый файл не прошёл проверку целостности: %s",
                    integrity_result.error,
                )
                return False

            merge_output_path.replace(self._output_path)

            logger.info(
                "Сегменты успешно объединены: %s → %s",
                len(segments),
                self._output_path,
            )

            for segment_path in segments:
                if segment_path != self._output_path:
                    try:
                        segment_path.unlink(missing_ok=True)
                    except OSError as e:
                        logger.warning(
                            "Не удалось удалить устаревший сегмент %s: %s",
                            segment_path,
                            e,
                        )

            return True

        except OSError as e:
            logger.error("Ошибка слияния сегментов: %s", e)
            return False
        finally:
            for temporary_path in (concat_file, merge_output_path):
                if temporary_path is None:
                    continue
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError as e:
                    logger.warning(
                        "Не удалось удалить временный файл %s: %s",
                        temporary_path,
                        e,
                    )

    def close(self, *, finalize_segments: bool = True) -> bool:
        """
        Закрытие FFmpeg процесса и завершение записи.

        Args:
            finalize_segments: Выполнять итоговое слияние накопленных сегментов.

        Returns:
            True если успешно закрыто
        """
        if self._process is None:
            return True

        process = self._process
        merge_result = False

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
                merge_result = False

            else:
                logger.info(
                    f"Запись завершена: {self._output_path} "
                    f"({self._frame_count} кадров, {self.elapsed_time:.1f}s)"
                )
                merge_result = True

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
                merge_result = False

            if process.returncode != 0:
                logger.error(
                    "FFmpeg завершён с кодом %s после terminate (%s)",
                    process.returncode,
                    self._output_path,
                )
                self._log_stderr_tail("ошибочное завершение после terminate")
                merge_result = False
            else:
                logger.info(
                    "FFmpeg завершился после terminate: "
                    f"{self._output_path} ({self._frame_count} кадров)"
                )
                merge_result = True
        except Exception as e:
            logger.error(f"Ошибка закрытия FFmpeg: {e}")
            merge_result = False

        finally:
            self._process = None
            self._stop_health_monitor()
            self._stop_stderr_reader()

            segments = self.segment_paths
            if not finalize_segments or not segments:
                pass

            elif not merge_result:
                logger.warning(
                    "Слияние не запущено после ошибки завершения FFmpeg; "
                    "исходные сегменты сохранены: %s",
                    [str(p) for p in segments],
                )

            elif len(segments) <= 1:
                if self._segment_paths:
                    logger.info(
                        "Запись восстановлена после %s сбоев FFmpeg, сохранена в %s частях: %s",
                        self._recovery_count,
                        len(self._segment_paths) + 1,
                        [str(p) for p in segments],
                    )

            elif not self._merge_segments():
                logger.warning(
                    "Ошибка слияния сегментов, исходные файлы сохранены: %s",
                    [str(p) for p in segments],
                )
                merge_result = False

            else:
                logger.info(
                    "Запись завершена и сегменты объединены: %s → %s",
                    len(segments),
                    self._output_path,
                )
                if self._segment_paths:
                    logger.info(
                        "Запись восстановлена после %s сбоев FFmpeg и сегменты объединены: %s",
                        self._recovery_count,
                        [str(p) for p in segments],
                    )

        return merge_result

    def _start_stderr_reader(self, stream: IO[bytes] | None) -> None:
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
            join(timeout=_FFMPEG_STDERR_READER_JOIN_TIMEOUT_SECONDS)
            if is_alive():
                logger.warning(
                    "stderr-reader поток FFmpeg не завершился за %.1f секунд",
                    _FFMPEG_STDERR_READER_JOIN_TIMEOUT_SECONDS,
                )

    # === Health monitor (#85) ===

    def _start_health_monitor(self) -> None:
        """Запустить фоновый мониторинг процесса FFmpeg.

        Поток каждые ``_health_check_interval_s`` секунд опрашивает
        ``process.poll()``; при обнаружении падения процесса между
        вызовами ``write()`` кладёт предупреждение в лог и сохраняет
        stderr tail — иначе эти падения видны только на следующей
        записи кадра (что может затянуться при низком fps).

        Избегаем создания потока если threading.Thread подменён тестом —
        unit-тесты используют синхронный `_ImmediateThread`, который
        исполняет target прямо в текущем потоке и блокируется в wait().
        """
        self._stop_health_monitor()  # идемпотентно при повторном open
        self._health_stop.clear()
        self._health_fail_logged = False
        if threading.Thread.__module__ != "threading":
            # threading.Thread замокан в тестах — поток будет синхронным
            # и заблокирует текущий поток. Health-monitor пропускаем.
            logger.debug(
                "Health-monitor пропущен: threading.Thread замокан (тесты)"
            )
            return
        thread = threading.Thread(
            target=self._health_monitor_loop,
            daemon=True,
            name="ffmpeg-health-monitor",
        )
        self._health_thread = thread
        thread.start()

    def _stop_health_monitor(self) -> None:
        """Остановить health-monitor и дождаться завершения потока."""
        thread = self._health_thread
        self._health_thread = None
        if thread is None:
            return
        self._health_stop.set()
        thread.join(timeout=2.0)
        if thread.is_alive():
            logger.debug("Health-monitor FFmpeg не завершился за таймаут")

    def _health_monitor_loop(self) -> None:
        """Бесконечный polling process.poll() до сигнала остановки."""
        while not self._health_stop.wait(self._health_check_interval_s):
            process = self._process
            if process is None:
                return
            rc = process.poll()
            if rc is not None:
                if not self._health_fail_logged:
                    self._health_fail_logged = True
                    elapsed = (
                        time.time() - self._start_time
                        if self._start_time
                        else 0.0
                    )
                    logger.error(
                        "FFmpeg упал между кадрами: rc=%s, "
                        "uptime=%.1fs, кадров записано=%d, "
                        "восстановлений=%d. Следующий write запустит "
                        "recovery-процедуру.",
                        rc,
                        elapsed,
                        self._frame_count,
                        self._recovery_count,
                    )
                    # Выкладываем tail stderr — критично для диагностики
                    self._log_stderr_tail("падение FFmpeg (health-check)")
                # Не спамим — один лог на каждое падение.
                self._health_stop.wait(self._health_check_interval_s)

    def _read_stderr(self, stream: IO[bytes]) -> None:
        """
        Чтение stderr FFmpeg в фоновом потоке.

        Args:
            stream: Поток stderr процесса FFmpeg.
        """
        try:
            while self._process is not None:
                raw_line = stream.readline()
                if not raw_line:
                    break

                text_line = (
                    raw_line.decode("utf-8", errors="replace")
                    if isinstance(raw_line, bytes)
                    else raw_line
                )

                cleaned_line = text_line.rstrip("\r\n")
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
