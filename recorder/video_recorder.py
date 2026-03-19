"""
Модуль видеозаписи
==================

Обрабатывает захват экрана и кодирование видео с использованием MSS
для быстрого захвата экрана и OpenCV для записи видео.
"""

import queue
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, Optional

import cv2
import numpy as np

if TYPE_CHECKING:
    import mss

from logger_config import get_module_logger
from recorder.utils import (
    get_available_windows,
    get_screen_size,
    validate_rect_coords,
)

logger = get_module_logger(__name__)


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
    window_title: Optional[str] = None

    @classmethod
    def full_screen(cls, monitor_index: int = 1) -> "CaptureArea":
        """Создание области захвата полного экрана."""
        width, height = get_screen_size()
        return cls(type="full", width=width, height=height)

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

    def to_mss_dict(self) -> Dict[str, int]:
        """Преобразование в формат словаря MSS для монитора."""
        return {
            "left": self.x,
            "top": self.y,
            "width": self.width,
            "height": self.height,
        }


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
    ):
        """
        Инициализация видеозаписи.

        Args:
            fps: Кадров в секунду
            codec: Имя видеокодека
            bitrate: Целевой битрейт (не используется в OpenCV, для справки)
            output_format: Выходной формат (mp4, avi)
        """
        self.fps = fps
        self.codec = codec
        self.bitrate = bitrate
        self.output_format = output_format

        # Состояние
        self._state = RecordingState.IDLE
        self._lock = threading.Lock()
        self._frame_queue: queue.Queue = queue.Queue(maxsize=100)
        self._capture_thread: Optional[threading.Thread] = None
        self._write_thread: Optional[threading.Thread] = None

        # Информация о записи
        self._output_path: Optional[Path] = None
        self._video_writer: Optional[cv2.VideoWriter] = None
        self._capture_area: Optional[CaptureArea] = None
        self._mss_instance: Optional[mss.base.MSSBase] = None

        # Статистика
        self._start_time: float = 0
        self._paused_time: float = 0
        self._total_paused: float = 0
        self._frame_count: int = 0

        # Обратные вызовы
        self._on_frame_captured: Optional[Callable] = None
        self._on_error: Optional[Callable] = None

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
    def output_path(self) -> Optional[Path]:
        """Получение текущего пути вывода."""
        return self._output_path

    @property
    def frame_count(self) -> int:
        """Получение общего количества захваченных кадров."""
        return self._frame_count

    def set_callbacks(
        self,
        on_frame_captured: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
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
        duration: Optional[float] = None,
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

            try:
                self._output_path = Path(output_path)
                self._capture_area = capture_area
                self._duration = duration

                # Убедиться, что директория вывода существует
                self._output_path.parent.mkdir(parents=True, exist_ok=True)

                # MSS будет создан внутри потока захвата, т.к. использует thread-local GDI объекты
                self._mss_instance = None

                # Инициализация видеозаписи
                fourcc_code = self.CODEC_MAP.get(self.codec.lower(), "mp4v")
                fourcc = cv2.VideoWriter_fourcc(*fourcc_code)  # type: ignore[attr-defined]

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
            self._capture_thread.join(timeout=5)

        self._cleanup()

        logger.info(
            f"Запись остановлена: {self._output_path}, кадров: {self._frame_count}"
        )
        return True

    def _capture_loop(self) -> None:
        """Основной цикл захвата в отдельном потоке."""
        import mss

        monitor = self._capture_area.to_mss_dict()  # type: ignore[union-attr]
        frame_interval: float = 1.0 / self.fps
        last_frame_time: float = 0

        # Создаём MSS внутри потока захвата, т.к. он использует thread-local GDI объекты
        self._mss_instance = mss.mss()

        try:
            while self._state not in (
                RecordingState.IDLE,
                RecordingState.STOPPING,
            ):
                if self._state == RecordingState.PAUSED:
                    time.sleep(0.1)
                    continue

                # Контроль частоты кадров
                current_time = time.time()
                elapsed = current_time - last_frame_time
                if elapsed < frame_interval:
                    time.sleep(frame_interval - elapsed)

                last_frame_time = float(time.time())

                # Захват кадра
                try:
                    screenshot = self._mss_instance.grab(monitor)  # type: ignore[union-attr,unused-ignore]
                    frame = np.array(screenshot)

                    # Преобразование BGRA в BGR для OpenCV
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

                    # Запись кадра
                    if self._video_writer is not None:
                        self._video_writer.write(frame)
                        self._frame_count += 1

                    # Обратный вызов для предпросмотра
                    if self._on_frame_captured:
                        self._on_frame_captured(frame)

                except Exception as e:
                    logger.error(f"Ошибка захвата кадра: {e}")

                # Проверка лимита длительности
                if self._duration and self.elapsed_time >= self._duration:
                    logger.info("Достигнут лимит длительности, остановка")
                    break

        except Exception as e:
            logger.error(f"Ошибка цикла захвата: {e}")
            if self._on_error:
                self._on_error(str(e))
        finally:
            # Закрываем MSS в том же потоке, где он был создан
            if self._mss_instance is not None:
                self._mss_instance.close()
                self._mss_instance = None

        # Сигнал завершения
        self._state = RecordingState.IDLE

    def _cleanup(self) -> None:
        """Очистка ресурсов."""
        try:
            if self._video_writer is not None:
                self._video_writer.release()
                self._video_writer = None

            # MSS закрывается в finally блоке _capture_loop, т.к. должен быть
            # закрыт в том же потоке, где был создан (thread-local GDI объекты)
            # Здесь только убеждаемся, что ссылка очищена
            self._mss_instance = None

        except Exception as e:
            logger.error(f"Ошибка при очистке: {e}")

        self._state = RecordingState.IDLE

    def get_preview_frame(self) -> Optional[np.ndarray]:
        """
        Получение кадра предпросмотра без записи.

        Returns:
            Кадр предпросмотра или None при ошибке захвата
        """
        try:
            import mss

            with mss.mss() as sct:
                if self._capture_area:
                    monitor = self._capture_area.to_mss_dict()
                else:
                    # По умолчанию основной монитор
                    monitor = sct.monitors[1]

                screenshot = sct.grab(monitor)
                frame = np.array(screenshot)
                return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)  # type: ignore[no-any-return]

        except Exception as e:
            logger.error(f"Ошибка получения кадра предпросмотра: {e}")
            return None
