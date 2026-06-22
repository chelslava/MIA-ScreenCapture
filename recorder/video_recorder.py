"""
Модуль видеозаписи
==================

Обрабатывает захват экрана и кодирование видео с использованием
windows-capture (Windows Graphics Capture API) и OpenCV.
"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from core.recording_state import RecordingStatus
from exceptions import RecordingError, ScreenCaptureError
from logger_config import get_module_logger
from recorder.utils import (
    get_available_monitors,
    get_available_windows,
    get_platform,
    validate_rect_coords,
)

logger = get_module_logger(__name__)

_CAPTURE_STOP_TIMEOUT_SECONDS = 15
_CAPTURE_FORCE_JOIN_TIMEOUT_SECONDS = 2
_WINDOW_CAPTURE_RECONNECT_TIMEOUT_SECONDS = 5.0
_WINDOW_CAPTURE_RECONNECT_POLL_SECONDS = 0.25

# Alias для обратной совместимости с тестами и кодом, импортирующим RecordingState
from typing import TypeAlias

RecordingState: TypeAlias = RecordingStatus
VideoRecorderState: TypeAlias = RecordingStatus


@dataclass
class CaptureArea:
    """Определение области захвата экрана."""

    type: str  # "full", "window", "rect"
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    window_title: str | None = None
    monitor_index: int = 0  # Индекс монитора (0 = primary)
    include_cursor: bool = False  # Включить курсор в захват

    @classmethod
    def full_screen(cls, monitor_index: int = 0) -> "CaptureArea":
        """Создание области захвата полного экрана.

        Args:
            monitor_index: Индекс монитора (0 = primary, 1 = secondary)
        """
        monitors = get_available_monitors()
        if monitor_index >= len(monitors):
            logger.warning(
                f"Монитор {monitor_index} не найден, используется primary"
            )
            monitor_index = 0

        monitor = (
            monitors[monitor_index]
            if monitors
            else {"width": 1920, "height": 1080}
        )
        return cls(
            type="full",
            monitor_index=monitor_index,
            width=monitor.get("width", 1920),
            height=monitor.get("height", 1080),
        )

    @classmethod
    def from_rect(cls, x1: int, y1: int, x2: int, y2: int) -> "CaptureArea":
        """Создание прямоугольной области захвата из координат."""
        left, top, right, bottom = validate_rect_coords(x1, y1, x2, y2)
        return cls(
            type="rect", x=left, y=top, width=right - left, height=bottom - top
        )

    @classmethod
    def from_window(
        cls, window_title: str, raise_if_not_found: bool = False
    ) -> "CaptureArea":
        """Создание области захвата из заголовка окна.

        Args:
            window_title: Заголовок или часть заголовка окна.
            raise_if_not_found: Если True, выбрасывает ValueError при
                ненайденном окне. Если False (по умолчанию), возвращает
                полный экран с предупреждением.

        Returns:
            CaptureArea для найденного окна или полный экран.

        Raises:
            ValueError: Если raise_if_not_found=True и окно не найдено.
        """
        windows = get_available_windows()
        for win in windows:
            if window_title.lower() in win["title"].lower():
                return cls(
                    type="window",
                    x=win["x"],
                    y=win["y"],
                    width=win["width"],
                    height=win["height"],
                    window_title=win["title"],
                )

        if raise_if_not_found:
            raise ValueError(
                f"Окно '{window_title}' не найдено. "
                "Проверьте что окно открыто."
            )

        logger.warning(
            f"Окно '{window_title}' не найдено, используется полный экран. "
            "Проверьте что окно открыто."
        )
        area = cls.full_screen()
        area.window_title = f"(not found: {window_title})"
        return area

    def to_capture_dict(self) -> dict[str, int]:
        """Преобразование в общий формат словаря области захвата."""
        return {
            "left": self.x,
            "top": self.y,
            "width": self.width,
            "height": self.height,
        }


class _WindowsCaptureSession:
    """
    Обёртка над windows-capture с pull-подобным API.

    Библиотека windows-capture работает event-driven, поэтому мы сохраняем
    последний полученный кадр и возвращаем его по запросу.
    """

    _INIT_TIMEOUT_SECONDS = 10.0

    def __init__(self, on_closed_callback: Callable | None = None) -> None:
        self._capture = None
        self._control = None
        self._last_frame: np.ndarray | None = None
        self._frame_event = threading.Event()
        self._lock = threading.Lock()
        self._closed = False
        self._on_closed_callback = on_closed_callback
        self._capture_lost = False
        self._init_complete = threading.Event()
        self._init_error: Exception | None = None

    def start(self, capture_area: CaptureArea) -> None:
        try:
            from windows_capture import InternalCaptureControl, WindowsCapture
        except ImportError as e:
            raise RuntimeError(
                "Библиотека windows-capture не установлена или недоступна"
            ) from e

        monitor_index = None
        window_name = None

        # Настройка в зависимости от типа захвата
        if capture_area.type == "window" and capture_area.window_title:
            window_name = capture_area.window_title
        elif capture_area.type == "full":
            # windows-capture ожидает monitor_index >= 1 (1 = primary)
            # Конвертируем из 0-based в 1-based
            monitor_index = capture_area.monitor_index + 1

        capture = WindowsCapture(
            cursor_capture=capture_area.include_cursor,
            draw_border=False,
            monitor_index=monitor_index,
            window_name=window_name,
        )

        @capture.event
        def on_frame_arrived(
            frame, capture_control: InternalCaptureControl
        ) -> None:
            if self._closed:
                capture_control.stop()
                return

            frame_buffer = frame.frame_buffer
            if frame_buffer is None:
                return

            is_bgra = frame_buffer.ndim == 3 and frame_buffer.shape[2] == 4

            if capture_area.type == "rect":
                x1 = max(capture_area.x, 0)
                y1 = max(capture_area.y, 0)
                x2 = max(capture_area.x + capture_area.width, x1)
                y2 = max(capture_area.y + capture_area.height, y1)
                if frame_buffer.ndim == 3:
                    h, w = frame_buffer.shape[:2]
                    x2 = min(x2, w)
                    y2 = min(y2, h)
                # Обрезаем до конвертации — меньше данных для обработки.
                region = frame_buffer[y1:y2, x1:x2]
                if is_bgra:
                    frame_copy = cv2.cvtColor(region, cv2.COLOR_BGRA2BGR)
                else:
                    frame_copy = np.ascontiguousarray(region)
            else:
                # SIMD-ускоренная конвертация BGRA→BGR (быстрее strided np.array copy).
                if is_bgra:
                    frame_copy = cv2.cvtColor(frame_buffer, cv2.COLOR_BGRA2BGR)
                else:
                    frame_copy = frame_buffer.copy()

            with self._lock:
                self._last_frame = frame_copy
                self._frame_event.set()
                self._init_complete.set()

        @capture.event
        def on_closed() -> None:
            """Обработка закрытия capture session."""
            logger.warning("Capture session closed unexpectedly")
            self._closed = True
            self._capture_lost = True

            # Уведомление об ошибке
            if self._on_closed_callback:
                try:
                    self._on_closed_callback(
                        "Захват потерян (окно закрыто или монитор отключен)"
                    )
                except (OSError, RuntimeError) as e:
                    logger.error(f"Ошибка в on_closed callback: {e}")

        self._capture = capture

        def _do_start() -> None:
            try:
                self._control = capture.start_free_threaded()
            except Exception as e:
                self._init_error = e
                self._init_complete.set()

        init_thread = threading.Thread(target=_do_start, daemon=True)
        init_thread.start()

        if not self._init_complete.wait(timeout=self._INIT_TIMEOUT_SECONDS):
            self._closed = True
            raise TimeoutError(
                f"Инициализация захвата не завершена за "
                f"{self._INIT_TIMEOUT_SECONDS} секунд"
            )

        if self._init_error is not None:
            raise RuntimeError(
                f"Ошибка инициализации захвата: {self._init_error}"
            ) from self._init_error

    def read_frame(self, timeout: float) -> np.ndarray | None:
        if self._capture_lost:
            # Попытка reconnect для window capture
            return None

        if not self._frame_event.wait(timeout=timeout):
            return None
        with self._lock:
            if self._last_frame is None:
                return None
            frame = self._last_frame
            self._frame_event.clear()
            return frame

    @property
    def is_capture_lost(self) -> bool:
        """Проверка, был ли потерян захват."""
        return self._capture_lost

    def stop(self) -> None:
        self._closed = True
        control = self._control
        if control is not None:
            try:
                control.stop()
                if hasattr(control, "wait"):
                    control.wait()
            except (OSError, RuntimeError) as e:
                logger.warning(
                    "Не удалось корректно остановить capture session: %s",
                    e,
                )
        self._control = None
        self._capture = None


class VideoRecorder:
    """
    Класс видеозаписи для захвата экрана.

    Обрабатывает захват экрана в отдельном потоке и записывает видео
    в файл с использованием OpenCV VideoWriter.
    """

    # Соответствие кодеков OpenCV
    CODEC_MAP = {
        "libx264": "mp4v",  # Возврат к mp4v для OpenCV
        "h264": "mp4v",
        "mp4v": "mp4v",
        "xvid": "XVID",
        "avc1": "H264",
        "vp09": "VP09",
    }

    def __init__(
        self,
        fps: int = 30,
        codec: str = "libx264",
        bitrate: str = "2M",
        output_format: str = "mp4",
        use_ffmpeg: bool = True,
        preset: str = "medium",
        max_recovery_attempts: int = 3,
        disk_warning_mb: float = 1024.0,
        disk_critical_mb: float = 100.0,
        disk_check_interval_s: float = 30.0,
    ):
        """
        Инициализация видеозаписи.

        Args:
            fps: Кадров в секунду
            codec: Имя видеокодека
            bitrate: Целевой битрейт
            output_format: Выходной формат (mp4, avi)
            use_ffmpeg: Использовать FFmpeg для прямой записи (быстрее)
            preset: Preset кодирования (ultrafast, fast, medium, slow)
            max_recovery_attempts: Сколько раз перезапускать FFmpeg-процесс
                при сбое, прежде чем пометить запись повреждённой (только
                для `use_ffmpeg=True`).
            disk_warning_mb: Порог свободного места (MB) для предупреждения
                (только для `use_ffmpeg=True`).
            disk_critical_mb: Порог свободного места (MB), при котором запись
                останавливается превентивно (только для `use_ffmpeg=True`).
            disk_check_interval_s: Минимальный интервал между проверками
                свободного места (секунды).
        """
        self.fps = fps
        self.codec = codec
        self.bitrate = bitrate
        self.output_format = output_format
        self.use_ffmpeg = use_ffmpeg
        self.preset = preset
        self.max_recovery_attempts = max_recovery_attempts
        self.disk_warning_mb = disk_warning_mb
        self.disk_critical_mb = disk_critical_mb
        self.disk_check_interval_s = disk_check_interval_s

        # Состояние
        self._state: VideoRecorderState = VideoRecorderState.IDLE
        self._lock = threading.Lock()
        self._capture_lost_lock = threading.Lock()
        self._capture_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()

        # Информация о записи
        self._output_path: Path | None = None
        self._video_writer: cv2.VideoWriter | None = None
        self._ffmpeg_writer: Any | None = None
        self._capture_area: CaptureArea | None = None
        self._capture_session: _WindowsCaptureSession | None = None
        self._duration: float | None = None
        self._last_segment_paths: list[Path] = []
        self._stopped_due_to_low_disk_space: bool = False

        # Кэшированный флаг: нужна ли конвертация цвета при записи кадров.
        # False — кадры уже в целевом формате (zero-copy путь).
        # True  — требуется cv2.cvtColor (устанавливается при первом кадре).
        self._needs_color_conversion: bool = True

        # Статистика
        self._start_time: float = 0
        self._paused_time: float = 0
        self._total_paused: float = 0
        self._frame_count: int = 0
        self._capture_lost: bool = False

        # Обратные вызовы
        self._on_frame_captured: Callable | None = None
        self._on_error: Callable | None = None
        self._last_captured_frame: np.ndarray | None = None

    def _set_capture_lost(self, value: bool) -> None:
        """
        Потокобезопасно обновить флаг потери захвата.

        Args:
            value: Новое значение флага.
        """
        with self._capture_lost_lock:
            self._capture_lost = value

    def _notify_error(self, message: str) -> None:
        """
        Безопасно уведомить внешний callback об ошибке.

        Args:
            message: Текст ошибки.
        """
        if self._on_error:
            try:
                self._on_error(message)
            except (OSError, RuntimeError) as e:
                logger.error(f"Ошибка в on_error callback: {e}")

    def _write_last_frame_on_capture_loss(self, frame: np.ndarray) -> None:
        """
        Попытаться сохранить последний полученный кадр перед остановкой.

        Args:
            frame: Последний доступный кадр.
        """
        try:
            if self._ffmpeg_writer is not None:
                self._ffmpeg_writer.write(frame)
            elif self._video_writer is not None:
                self._video_writer.write(frame)
            self._last_captured_frame = frame
        except (OSError, RuntimeError) as e:
            logger.warning(
                "Не удалось записать последний кадр при потере захвата: %s",
                e,
            )

    def _can_attempt_window_reconnect(self) -> bool:
        """
        Проверить, допустимо ли восстановление window capture.

        Returns:
            `True`, если текущая область — окно с известным заголовком.
        """
        return bool(
            self._capture_area is not None
            and self._capture_area.type == "window"
            and self._capture_area.window_title
        )

    def _try_reconnect_window_capture(
        self,
        on_capture_lost: Callable[[str], None],
    ) -> _WindowsCaptureSession | None:
        """
        Попытаться восстановить потерянный window capture.

        Args:
            on_capture_lost: Callback, который будет передан новой session.

        Returns:
            Новая capture session при успехе, иначе `None`.
        """
        if not self._can_attempt_window_reconnect():
            return None

        capture_area = self._capture_area
        if capture_area is None or not capture_area.window_title:
            return None

        logger.warning(
            "Попытка восстановить захват окна '%s' в течение %.1f сек",
            capture_area.window_title,
            _WINDOW_CAPTURE_RECONNECT_TIMEOUT_SECONDS,
        )

        deadline = (
            time.perf_counter() + _WINDOW_CAPTURE_RECONNECT_TIMEOUT_SECONDS
        )
        attempt = 0

        while time.perf_counter() < deadline:
            if self._shutdown_event.is_set() or self._state in (
                VideoRecorderState.IDLE,
                VideoRecorderState.STOPPING,
            ):
                logger.info(
                    "Восстановление захвата окна отменено из-за остановки записи"
                )
                return None

            attempt += 1
            try:
                recovered_area = CaptureArea.from_window(
                    capture_area.window_title,
                    raise_if_not_found=True,
                )
            except ValueError:
                logger.info(
                    "Окно '%s' пока недоступно, попытка восстановления #%s",
                    capture_area.window_title,
                    attempt,
                )
                time.sleep(_WINDOW_CAPTURE_RECONNECT_POLL_SECONDS)
                continue

            if (
                recovered_area.width != capture_area.width
                or recovered_area.height != capture_area.height
            ):
                logger.warning(
                    "Окно '%s' найдено, но размер изменился: %sx%s -> %sx%s",
                    capture_area.window_title,
                    capture_area.width,
                    capture_area.height,
                    recovered_area.width,
                    recovered_area.height,
                )
                time.sleep(_WINDOW_CAPTURE_RECONNECT_POLL_SECONDS)
                continue

            recovered_session = _WindowsCaptureSession(
                on_closed_callback=on_capture_lost
            )
            try:
                recovered_session.start(recovered_area)
            except (OSError, RuntimeError, TimeoutError) as e:
                logger.warning(
                    "Не удалось перезапустить захват окна '%s' (попытка %s): %s",
                    capture_area.window_title,
                    attempt,
                    e,
                )
                try:
                    recovered_session.stop()
                except (OSError, RuntimeError):
                    pass
                time.sleep(_WINDOW_CAPTURE_RECONNECT_POLL_SECONDS)
                continue

            logger.info(
                "Захват окна '%s' успешно восстановлен после %s попыток",
                capture_area.window_title,
                attempt,
            )
            self._capture_area = recovered_area
            self._capture_session = recovered_session
            self._set_capture_lost(False)
            return recovered_session

        logger.error(
            "Не удалось восстановить захват окна '%s' за %.1f сек",
            capture_area.window_title,
            _WINDOW_CAPTURE_RECONNECT_TIMEOUT_SECONDS,
        )
        return None

    @property
    def state(self) -> RecordingState:
        """Получение текущего состояния записи."""
        return self._state

    @property
    def is_recording(self) -> bool:
        """Проверка активности записи."""
        return bool(self._state == VideoRecorderState.RECORDING)

    @property
    def is_paused(self) -> bool:
        """Проверка паузы записи."""
        return bool(self._state == VideoRecorderState.PAUSED)

    @property
    def elapsed_time(self) -> float:
        """Получение времени записи в секундах."""
        if self._start_time == 0:
            return 0
        elapsed = time.time() - self._start_time - self._total_paused
        if self._state == VideoRecorderState.PAUSED:
            elapsed -= time.time() - self._paused_time
        return max(0, elapsed)

    @property
    def output_path(self) -> Path | None:
        """Получение текущего пути вывода."""
        return self._output_path

    @property
    def additional_segment_paths(self) -> list[Path]:
        """
        Пути дополнительных файлов-сегментов после восстановления FFmpeg.

        Пустой список, если сбоев FFmpeg во время записи не было. Сохраняется
        и после `stop()`/`_cleanup()` — `FFmpegVideoWriter` к этому моменту
        уже обнулён, поэтому значение кэшируется в `_last_segment_paths`.
        """
        if self._ffmpeg_writer is not None:
            return list(self._ffmpeg_writer.segment_paths)
        return list(self._last_segment_paths)

    @property
    def stopped_due_to_low_disk_space(self) -> bool:
        """
        Признак, что запись была остановлена превентивно из-за критической
        нехватки места на диске (а не аварийно, как при сбое FFmpeg).

        В этом случае файл записи финализирован штатно и не помечен
        повреждённым.
        """
        return self._stopped_due_to_low_disk_space

    @property
    def frame_count(self) -> int:
        """Получение общего количества захваченных кадров."""
        return self._frame_count

    def set_callbacks(
        self,
        on_frame_captured: Callable | None = None,
        on_error: Callable | None = None,
    ) -> None:
        """
        Установка функций обратного вызова.

        Args:
            on_frame_captured: Вызывается при захвате кадра (получает кадр)
            on_error: Вызывается при ошибке (получает сообщение об ошибке)
        """
        self._on_frame_captured = on_frame_captured
        self._on_error = on_error

    def start(
        self,
        output_path: Path,
        capture_area: CaptureArea,
        duration: float | None = None,
    ) -> bool:
        """
        Начало записи.

        Args:
            output_path: Путь для сохранения видеофайла
            capture_area: Область экрана для захвата
            duration: Опциональная длительность записи в секундах

        Returns:
            True если запись успешно началась
        """
        with self._lock:
            if self._state != VideoRecorderState.IDLE:
                logger.warning(
                    f"Невозможно начать: текущее состояние {self._state}"
                )
                return False
            if get_platform() != "windows":
                message = "VideoRecorder поддерживает только Windows (windows-capture)"
                logger.error(message)
                if self._on_error:
                    self._on_error(message)
                return False

            try:
                self._output_path = Path(output_path)
                self._capture_area = capture_area
                self._duration = duration

                # Убедиться, что директория вывода существует
                self._output_path.parent.mkdir(parents=True, exist_ok=True)

                # Session windows-capture создаётся в потоке захвата.
                self._capture_session = None
                self._capture_lost = False  # Сброс флага потери захвата
                self._stopped_due_to_low_disk_space = False

                # Инициализация видеозаписи
                if self.use_ffmpeg:
                    from recorder.ffmpeg_writer import FFmpegVideoWriter

                    self._ffmpeg_writer = FFmpegVideoWriter(
                        output_path=self._output_path,
                        width=capture_area.width,
                        height=capture_area.height,
                        fps=self.fps,
                        codec=self.codec,
                        bitrate=self.bitrate,
                        preset=self.preset,
                        max_recovery_attempts=self.max_recovery_attempts,
                        disk_warning_mb=self.disk_warning_mb,
                        disk_critical_mb=self.disk_critical_mb,
                        disk_check_interval_s=self.disk_check_interval_s,
                    )
                    if not self._ffmpeg_writer.open():
                        raise RuntimeError(
                            "Не удалось открыть FFmpeg видеозапись"
                        )
                else:
                    fourcc_code = self.CODEC_MAP.get(
                        self.codec.lower(), "mp4v"
                    )
                    fourcc_factory = getattr(cv2, "VideoWriter_fourcc", None)
                    if fourcc_factory is None:
                        raise RuntimeError(
                            "OpenCV VideoWriter_fourcc недоступен"
                        )
                    fourcc = fourcc_factory(*fourcc_code)

                    self._video_writer = cv2.VideoWriter(
                        str(self._output_path),
                        fourcc,
                        self.fps,
                        (capture_area.width, capture_area.height),
                    )

                    if not self._video_writer.isOpened():
                        raise RuntimeError("Не удалось открыть видеозапись")

                # Сброс статистики
                self._start_time = time.time()
                self._paused_time = 0
                self._total_paused = 0
                self._frame_count = 0
                self._shutdown_event.clear()

                # Запуск потока захвата
                self._state = VideoRecorderState.RECORDING
                self._capture_thread = threading.Thread(
                    target=self._capture_loop, daemon=False
                )
                self._capture_thread.start()

                logger.info(f"Запись начата: {output_path}")
                return True

            except (RecordingError, OSError, RuntimeError, ValueError) as e:
                logger.error(f"Не удалось начать запись: {e}")
                self._cleanup()
                if self._on_error:
                    self._on_error(str(e))
                return False

    def pause(self) -> bool:
        """
        Пауза записи.

        Returns:
            True если пауза успешно установлена
        """
        with self._lock:
            if self._state != VideoRecorderState.RECORDING:
                return False

            self._state = VideoRecorderState.PAUSED
            self._paused_time = time.time()
            logger.info("Запись приостановлена")
            return True

    def resume(self) -> bool:
        """
        Возобновление приостановленной записи.

        Returns:
            True если запись успешно возобновлена
        """
        with self._lock:
            if self._state != VideoRecorderState.PAUSED:
                return False

            self._total_paused += time.time() - self._paused_time
            self._state = VideoRecorderState.RECORDING
            logger.info("Запись возобновлена")
            return True

    def stop(self) -> bool:
        """
        Остановка записи и сохранение файла.

        Returns:
            True если запись успешно остановлена
        """
        with self._lock:
            if self._state == VideoRecorderState.IDLE:
                return False

            self._state = VideoRecorderState.STOPPING
            self._shutdown_event.set()

        capture_thread = self._capture_thread

        # Сигнализируем сессии о завершении до ожидания join.
        if self._capture_session is not None:
            try:
                self._capture_session.stop()
            except (OSError, RuntimeError) as e:
                logger.warning(
                    "Не удалось остановить capture session перед join: %s",
                    e,
                )

        # Ожидание завершения потока захвата.
        if capture_thread and capture_thread.is_alive():
            capture_thread.join(timeout=_CAPTURE_STOP_TIMEOUT_SECONDS)
            if capture_thread.is_alive():
                logger.warning(
                    "Поток захвата не завершился за %s сек",
                    _CAPTURE_STOP_TIMEOUT_SECONDS,
                )

        cleanup_ok = self._cleanup()

        # После cleanup даём потоку короткий шанс на финальное завершение.
        if capture_thread and capture_thread.is_alive():
            capture_thread.join(timeout=_CAPTURE_FORCE_JOIN_TIMEOUT_SECONDS)

        if capture_thread and capture_thread.is_alive():
            logger.error("Поток захвата не завершился после cleanup")
            return False

        if not cleanup_ok:
            logger.error(
                "Запись остановлена с ошибками финализации контейнера: %s",
                self._output_path,
            )
            return False

        logger.info(
            f"Запись остановлена: {self._output_path}, кадров: {self._frame_count}"
        )
        return True

    def _capture_loop(self) -> None:
        """Основной цикл захвата в отдельном потоке."""
        frame_interval: float = 1.0 / self.fps
        next_frame_time: float = time.perf_counter()
        fatal_write_error = False
        disk_space_stop = False
        capture_lost_requires_cleanup = False
        capture_lost_message = (
            "Захват потерян (окно закрыто или монитор отключен)"
        )

        def on_capture_lost(message: str) -> None:
            nonlocal capture_lost_message
            capture_lost_message = message
            logger.error(f"Capture lost: {message}")
            self._set_capture_lost(True)

        session = _WindowsCaptureSession(on_closed_callback=on_capture_lost)
        self._capture_session = session
        self._set_capture_lost(False)

        try:
            session.start(self._capture_area)  # type: ignore[arg-type]
            while not self._shutdown_event.is_set() and self._state not in (
                VideoRecorderState.IDLE,
                VideoRecorderState.STOPPING,
            ):
                if self._state == VideoRecorderState.PAUSED:
                    time.sleep(0.1)
                    continue

                # Проверка потери захвата
                if session.is_capture_lost:
                    logger.warning("Capture lost detected in capture loop")
                    self._set_capture_lost(True)
                    try:
                        session.stop()
                    except (OSError, RuntimeError) as e:
                        logger.warning(
                            "Ошибка остановки потерянной capture session: %s",
                            e,
                        )
                    recovered_session = self._try_reconnect_window_capture(
                        on_capture_lost
                    )
                    if recovered_session is None:
                        capture_lost_requires_cleanup = True
                        self._notify_error(capture_lost_message)
                        break
                    session = recovered_session
                    next_frame_time = time.perf_counter()
                    continue

                # Контроль частоты кадров с adaptive timing и drift correction
                now = time.perf_counter()
                wait_time = next_frame_time - now
                if wait_time > 0.001:
                    self._shutdown_event.wait(timeout=wait_time)
                if self._shutdown_event.is_set():
                    break
                next_frame_time += frame_interval
                # Предотвращение накопления drift при большой задержке
                if time.perf_counter() - next_frame_time > frame_interval:
                    next_frame_time = time.perf_counter()

                # Захват кадра
                try:
                    # Проверка потери захвата перед чтением
                    if session.is_capture_lost:
                        logger.warning("Capture lost before frame read")
                        self._set_capture_lost(True)
                        try:
                            session.stop()
                        except (OSError, RuntimeError) as e:
                            logger.warning(
                                "Ошибка остановки capture session до recovery: %s",
                                e,
                            )
                        recovered_session = self._try_reconnect_window_capture(
                            on_capture_lost
                        )
                        if recovered_session is None:
                            capture_lost_requires_cleanup = True
                            self._notify_error(capture_lost_message)
                            break
                        session = recovered_session
                        next_frame_time = time.perf_counter()
                        continue

                    frame = session.read_frame(
                        timeout=max(frame_interval, 0.01)
                    )

                    # Проверка потери захвата после чтения
                    if session.is_capture_lost:
                        logger.warning("Capture lost after frame read")
                        self._set_capture_lost(True)
                        if frame is not None:
                            self._write_last_frame_on_capture_loss(frame)
                        try:
                            session.stop()
                        except (OSError, RuntimeError) as e:
                            logger.warning(
                                "Ошибка остановки capture session после потери: %s",
                                e,
                            )
                        recovered_session = self._try_reconnect_window_capture(
                            on_capture_lost
                        )
                        if recovered_session is None:
                            capture_lost_requires_cleanup = True
                            self._notify_error(capture_lost_message)
                            break
                        session = recovered_session
                        next_frame_time = time.perf_counter()
                        continue

                    if frame is None:
                        continue

                    # Сброс флага потери при успешном захвате
                    self._set_capture_lost(False)

                    # Запись кадра
                    if self._ffmpeg_writer is not None:
                        write_ok = self._ffmpeg_writer.write(frame)
                        if not write_ok:
                            if self._ffmpeg_writer.is_disk_space_critical:
                                disk_space_stop = True
                                self._stopped_due_to_low_disk_space = True
                                message = (
                                    "Критическое заполнение диска — запись "
                                    "остановлена для предотвращения потери "
                                    "данных. Файл будет финализирован "
                                    "штатно."
                                )
                                logger.warning(message)
                            else:
                                fatal_write_error = True
                                self._ffmpeg_writer.mark_corrupted()
                                message = (
                                    "Ошибка записи кадра в FFmpeg. "
                                    "Запись остановлена аварийно."
                                )
                                logger.error(message)
                            if self._on_error:
                                self._on_error(message)
                            self._state = VideoRecorderState.STOPPING
                            break
                        self._frame_count += 1
                        self._last_captured_frame = frame
                    elif self._video_writer is not None:
                        self._video_writer.write(frame)
                        self._frame_count += 1
                        self._last_captured_frame = frame

                    # Обратный вызов для предпросмотра
                    if self._on_frame_captured:
                        self._on_frame_captured(frame)

                except (ScreenCaptureError, OSError, RuntimeError) as e:
                    logger.error(f"Ошибка захвата кадра: {e}")
                    # Не прерываем запись при единичных ошибках
                    continue

                # Проверка лимита длительности
                if self._duration and self.elapsed_time >= self._duration:
                    logger.info("Достигнут лимит длительности, остановка")
                    break

        except (RecordingError, OSError, RuntimeError) as e:
            logger.error(f"Ошибка цикла захвата: {e}", exc_info=True)
            if self._on_error:
                self._on_error(str(e))
        finally:
            try:
                session.stop()
            except (OSError, RuntimeError) as e:
                logger.warning(
                    "Ошибка при остановке capture session в finally: %s",
                    e,
                )
            self._capture_session = None

        if fatal_write_error or disk_space_stop:
            self._cleanup()
            return

        if capture_lost_requires_cleanup:
            self._cleanup()
            return

        # Сигнал завершения
        self._state = VideoRecorderState.IDLE

    @property
    def is_capture_lost(self) -> bool:
        """Проверка, был ли потерян захват."""
        with self._capture_lost_lock:
            return self._capture_lost

    def _cleanup(self) -> bool:
        """Очистка ресурсов.

        Returns:
            True, если все критичные ресурсы закрыты корректно.
        """
        success = True
        try:
            if self._ffmpeg_writer is not None:
                self._last_segment_paths = self._ffmpeg_writer.segment_paths
                if self._ffmpeg_writer.is_corrupted:
                    self._ffmpeg_writer.close()
                    self._ffmpeg_writer.cleanup_corrupted_file()
                else:
                    ffmpeg_closed = self._ffmpeg_writer.close()
                    success = success and ffmpeg_closed
                self._ffmpeg_writer = None
            if self._video_writer is not None:
                self._video_writer.release()
                self._video_writer = None
            if self._capture_session is not None:
                self._capture_session.stop()
                self._capture_session = None

        except (OSError, RuntimeError) as e:
            logger.error(f"Ошибка при очистке: {e}")
            success = False

        self._state = VideoRecorderState.IDLE
        return success

    def get_preview_frame(self) -> np.ndarray | None:
        """
        Получение кадра предпросмотра без записи.

        Returns:
            Кадр предпросмотра или None при ошибке захвата
        """
        if self._last_captured_frame is None:
            return None
        return self._last_captured_frame.copy()
