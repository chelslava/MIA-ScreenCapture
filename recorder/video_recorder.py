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
from enum import Enum
from pathlib import Path

import cv2
import numpy as np

from logger_config import get_module_logger
from recorder.utils import (
    get_available_monitors,
    get_available_windows,
    get_platform,
    validate_rect_coords,
)

logger = get_module_logger(__name__)

_CAPTURE_STOP_TIMEOUT_SECONDS = 15


class RecordingState(Enum):
    """Перечисление состояний записи."""

    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"
    STOPPING = "stopping"


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
    def from_window(cls, window_title: str) -> "CaptureArea":
        """Создание области захвата из заголовка окна."""
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
        # Возврат к полному экрану, если окно не найдено
        logger.warning(
            f"Окно '{window_title}' не найдено, используется полный экран"
        )
        return cls.full_screen()

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

    def __init__(self, on_closed_callback: Callable | None = None) -> None:
        self._capture = None
        self._control = None
        self._last_frame: np.ndarray | None = None
        self._frame_event = threading.Event()
        self._lock = threading.Lock()
        self._closed = False
        self._on_closed_callback = on_closed_callback
        self._capture_lost = False  # Флаг потери захвата

    def start(self, capture_area: CaptureArea) -> None:
        try:
            from windows_capture import InternalCaptureControl, WindowsCapture
        except Exception as e:
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

            # Обычно windows-capture отдаёт BGRA.
            if frame_buffer.ndim == 3 and frame_buffer.shape[2] == 4:
                bgr = frame_buffer[:, :, :3]
            else:
                bgr = frame_buffer

            # Прямоугольная область - пост-обрезка кадра.
            if capture_area.type == "rect":
                x1 = max(capture_area.x, 0)
                y1 = max(capture_area.y, 0)
                x2 = max(capture_area.x + capture_area.width, x1)
                y2 = max(capture_area.y + capture_area.height, y1)
                if bgr.ndim == 3:
                    h, w = bgr.shape[:2]
                    x2 = min(x2, w)
                    y2 = min(y2, h)
                    bgr = bgr[y1:y2, x1:x2]

            with self._lock:
                # Копия нужна, т.к. буфер принадлежит native стороне.
                self._last_frame = np.array(bgr, copy=True)
                self._frame_event.set()

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
                except Exception as e:
                    logger.error(f"Ошибка в on_closed callback: {e}")

        self._capture = capture
        self._control = capture.start_free_threaded()

    def read_frame(self, timeout: float) -> np.ndarray | None:
        if self._capture_lost:
            # Попытка reconnect для window capture
            return None

        if not self._frame_event.wait(timeout=timeout):
            return None
        with self._lock:
            if self._last_frame is None:
                return None
            frame = self._last_frame.copy()
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
            except Exception:
                pass
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
        """
        self.fps = fps
        self.codec = codec
        self.bitrate = bitrate
        self.output_format = output_format
        self.use_ffmpeg = use_ffmpeg
        self.preset = preset

        # Состояние
        self._state = RecordingState.IDLE
        self._lock = threading.Lock()
        self._capture_thread: threading.Thread | None = None

        # Информация о записи
        self._output_path: Path | None = None
        self._video_writer: cv2.VideoWriter | None = None
        self._ffmpeg_writer = None
        self._capture_area: CaptureArea | None = None
        self._capture_session: _WindowsCaptureSession | None = None

        # Статистика
        self._start_time: float = 0
        self._paused_time: float = 0
        self._total_paused: float = 0
        self._frame_count: int = 0

        # Обратные вызовы
        self._on_frame_captured: Callable | None = None
        self._on_error: Callable | None = None
        self._last_captured_frame: np.ndarray | None = None

    @property
    def state(self) -> RecordingState:
        """Получение текущего состояния записи."""
        return self._state

    @property
    def is_recording(self) -> bool:
        """Проверка активности записи."""
        return self._state == RecordingState.RECORDING

    @property
    def is_paused(self) -> bool:
        """Проверка паузы записи."""
        return self._state == RecordingState.PAUSED

    @property
    def elapsed_time(self) -> float:
        """Получение времени записи в секундах."""
        if self._start_time == 0:
            return 0
        elapsed = time.time() - self._start_time - self._total_paused
        if self._state == RecordingState.PAUSED:
            elapsed -= time.time() - self._paused_time
        return max(0, elapsed)

    @property
    def output_path(self) -> Path | None:
        """Получение текущего пути вывода."""
        return self._output_path

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
            if self._state != RecordingState.IDLE:
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
                    )
                    if not self._ffmpeg_writer.open():
                        raise RuntimeError(
                            "Не удалось открыть FFmpeg видеозапись"
                        )
                else:
                    fourcc_code = self.CODEC_MAP.get(
                        self.codec.lower(), "mp4v"
                    )
                    fourcc = cv2.VideoWriter_fourcc(*fourcc_code)

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

                # Запуск потока захвата
                self._state = RecordingState.RECORDING
                self._capture_thread = threading.Thread(
                    target=self._capture_loop, daemon=True
                )
                self._capture_thread.start()

                logger.info(f"Запись начата: {output_path}")
                return True

            except Exception as e:
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
            if self._state != RecordingState.RECORDING:
                return False

            self._state = RecordingState.PAUSED
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
            if self._state != RecordingState.PAUSED:
                return False

            self._total_paused += time.time() - self._paused_time
            self._state = RecordingState.RECORDING
            logger.info("Запись возобновлена")
            return True

    def stop(self) -> bool:
        """
        Остановка записи и сохранение файла.

        Returns:
            True если запись успешно остановлена
        """
        with self._lock:
            if self._state == RecordingState.IDLE:
                return False

            self._state = RecordingState.STOPPING

        # Ожидание завершения потока захвата
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=_CAPTURE_STOP_TIMEOUT_SECONDS)

        cleanup_ok = self._cleanup()

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
        last_frame_time: float = time.perf_counter()

        def on_capture_lost(message: str) -> None:
            logger.error(f"Capture lost: {message}")
            if self._on_error:
                try:
                    self._on_error(message)
                except Exception as e:
                    logger.error(f"Ошибка в on_error callback: {e}")

        session = _WindowsCaptureSession(on_closed_callback=on_capture_lost)
        self._capture_session = session
        self._capture_lost = False

        try:
            session.start(self._capture_area)  # type: ignore[arg-type]
            while self._state not in (
                RecordingState.IDLE,
                RecordingState.STOPPING,
            ):
                if self._state == RecordingState.PAUSED:
                    time.sleep(0.1)
                    continue

                # Проверка потери захвата
                if session.is_capture_lost:
                    logger.warning("Capture lost detected in capture loop")
                    self._capture_lost = True
                    break

                # Контроль частоты кадров с высокой точностью
                current_time = time.perf_counter()
                elapsed = current_time - last_frame_time
                if elapsed < frame_interval:
                    sleep_time = frame_interval - elapsed
                    if sleep_time > 0.001:
                        time.sleep(sleep_time * 0.9)

                last_frame_time = time.perf_counter()

                # Захват кадра
                try:
                    frame = session.read_frame(
                        timeout=max(frame_interval, 0.01)
                    )
                    if frame is None:
                        # Timeout - проверяем, не потерян ли захват
                        if session.is_capture_lost:
                            break
                        continue

                    # Сброс флага потери при успешном захвате
                    self._capture_lost = False

                    # Запись кадра
                    if self._ffmpeg_writer is not None:
                        self._ffmpeg_writer.write(frame)
                        self._frame_count += 1
                        self._last_captured_frame = frame
                    elif self._video_writer is not None:
                        self._video_writer.write(frame)
                        self._frame_count += 1
                        self._last_captured_frame = frame

                    # Обратный вызов для предпросмотра
                    if self._on_frame_captured:
                        self._on_frame_captured(frame)

                except Exception as e:
                    logger.error(f"Ошибка захвата кадра: {e}")
                    # Не прерываем запись при единичных ошибках
                    continue

                # Проверка лимита длительности
                if self._duration and self.elapsed_time >= self._duration:
                    logger.info("Достигнут лимит длительности, остановка")
                    break

        except Exception as e:
            logger.error(f"Ошибка цикла захвата: {e}", exc_info=True)
            if self._on_error:
                self._on_error(str(e))
        finally:
            try:
                session.stop()
            except Exception:
                pass
            self._capture_session = None

        # Сигнал завершения
        self._state = RecordingState.IDLE

    @property
    def is_capture_lost(self) -> bool:
        """Проверка, был ли потерян захват."""
        return getattr(self, "_capture_lost", False)

    def _cleanup(self) -> bool:
        """Очистка ресурсов.

        Returns:
            True, если все критичные ресурсы закрыты корректно.
        """
        success = True
        try:
            if self._ffmpeg_writer is not None:
                ffmpeg_closed = self._ffmpeg_writer.close()
                success = success and ffmpeg_closed
                self._ffmpeg_writer = None
            if self._video_writer is not None:
                self._video_writer.release()
                self._video_writer = None
            if self._capture_session is not None:
                self._capture_session.stop()
                self._capture_session = None

        except Exception as e:
            logger.error(f"Ошибка при очистке: {e}")
            success = False

        self._state = RecordingState.IDLE
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
