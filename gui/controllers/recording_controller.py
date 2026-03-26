"""
Контроллер записи
=================

Управляет процессом записи видео и аудио.
Отделяет бизнес-логику от UI.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from core.recording_state import (
    AudioSettings,
    AudioType,
    CaptureSettings,
    CaptureType,
    RecordingState,
    VideoSettings,
)
from logger_config import get_module_logger
from recorder.audio_recorder import AudioRecorder, SystemAudioRecorder
from recorder.encoder import EncodingSettings, RecordingEncoder
from recorder.video_recorder import CaptureArea, VideoRecorder

if TYPE_CHECKING:
    pass

logger = get_module_logger(__name__)


class RecordingController:
    """
    Контроллер для управления процессом записи.

    Отвечает за:
    - Запуск, остановку, паузу записи
    - Координацию видео и аудио рекордеров
    - Управление кодировщиком
    """

    def __init__(self, state: Optional[RecordingState] = None):
        """
        Инициализация контроллера.

        Args:
            state: Модель состояния записи (создаётся новая, если не указана)
        """
        self._state = state or RecordingState()
        self._video_recorder: Optional[VideoRecorder] = None
        self._audio_recorder: Optional[AudioRecorder] = None
        self._encoder: Optional[RecordingEncoder] = None
        self._temp_video: Optional[Path] = None
        self._temp_audio: Optional[Path] = None

    @property
    def state(self) -> RecordingState:
        """Получить текущее состояние."""
        return self._state

    @property
    def elapsed_time(self) -> float:
        """Получить время записи."""
        if self._video_recorder:
            return self._video_recorder.elapsed_time
        return 0.0

    def build_capture_area(self, capture: CaptureSettings) -> CaptureArea:
        """
        Построить область захвата из настроек.

        Args:
            capture: Настройки области захвата

        Returns:
            Объект CaptureArea для VideoRecorder
        """
        if capture.capture_type == CaptureType.FULL_SCREEN:
            return CaptureArea.full_screen()
        elif capture.capture_type == CaptureType.WINDOW:
            return CaptureArea.from_window(capture.window_title)
        elif capture.capture_type == CaptureType.RECTANGLE:
            return CaptureArea.from_rect(*capture.rect_coords)

        return CaptureArea.full_screen()

    def start_recording(
        self,
        output_path: Path,
        capture: CaptureSettings,
        audio: AudioSettings,
        video: VideoSettings,
        duration: Optional[int] = None,
    ) -> tuple[bool, Optional[str]]:
        """
        Запуск записи.

        Args:
            output_path: Путь к выходному файлу
            capture: Настройки области захвата
            audio: Настройки аудио
            video: Настройки видео
            duration: Длительность записи в секундах (опционально)

        Returns:
            Кортеж (успех, сообщение об ошибке или None)
        """
        try:
            # Настройка кодировщика
            settings = EncodingSettings(
                codec=video.codec, bitrate=video.bitrate
            )
            self._encoder = RecordingEncoder(output_path, settings)
            self._temp_video, self._temp_audio = self._encoder.setup()

        except OSError as e:
            error_msg = f"Ошибка файловой системы: {e}"
            logger.error(error_msg)
            self._cleanup()
            return False, error_msg

        try:
            # Инициализация видеозаписи
            self._video_recorder = VideoRecorder(
                fps=video.fps, codec=video.codec, bitrate=video.bitrate
            )

            # Построение области захвата
            capture_area = self.build_capture_area(capture)

            # Запуск видеозаписи
            if not self._video_recorder.start(
                self._temp_video, capture_area, duration
            ):
                self._cleanup()
                return False, "Не удалось запустить видеозапись"

            # Запуск аудиозаписи при необходимости
            if audio.audio_type in (AudioType.MICROPHONE, AudioType.BOTH):
                self._audio_recorder = AudioRecorder()
                audio_started = self._audio_recorder.start(
                    self._temp_audio,
                    device_index=audio.mic_device_index,
                    duration=duration,
                )
                if not audio_started:
                    self._cleanup()
                    return False, "Не удалось запустить аудиозапись"
            elif audio.audio_type == AudioType.SYSTEM:
                try:
                    self._audio_recorder = SystemAudioRecorder()
                    audio_started = self._audio_recorder.start(
                        self._temp_audio, duration=duration
                    )
                    if not audio_started:
                        self._cleanup()
                        return False, "Не удалось запустить запись системного аудио"
                except Exception as e:
                    logger.warning(f"Системное аудио недоступно: {e}")
                    self._audio_recorder = None

            # Обновление состояния
            self._state.start_recording(output_path)
            logger.info(f"Запись запущена: {output_path}")
            return True, None

        except RuntimeError as e:
            error_msg = f"Ошибка запуска записи: {e}"
            logger.error(error_msg)
            self._cleanup()
            return False, error_msg
        except Exception as e:
            error_msg = f"Неожиданная ошибка: {e}"
            logger.error(error_msg, exc_info=True)
            self._cleanup()
            return False, error_msg

    def pause_recording(self) -> bool:
        """
        Приостановка записи.

        Returns:
            True если пауза успешно установлена
        """
        if not self._state.is_recording() or self._state.is_paused():
            return False

        if self._video_recorder:
            self._video_recorder.pause()
        if self._audio_recorder:
            self._audio_recorder.pause()

        self._state.pause_recording()
        logger.info("Запись приостановлена")
        return True

    def resume_recording(self) -> bool:
        """
        Возобновление записи.

        Returns:
            True если запись успешно возобновлена
        """
        if not self._state.is_paused():
            return False

        if self._video_recorder:
            self._video_recorder.resume()
        if self._audio_recorder:
            self._audio_recorder.resume()

        self._state.resume_recording()
        logger.info("Запись возобновлена")
        return True

    def stop_recording(self) -> Optional[Path]:
        """
        Остановка записи и финализация.

        Returns:
            Путь к выходному файлу или None при ошибке
        """
        if not self._state.is_recording() and not self._state.is_paused():
            return None

        # Остановка видео
        if self._video_recorder:
            self._video_recorder.stop()

        # Остановка аудио
        has_audio = self._audio_recorder is not None
        if self._audio_recorder:
            self._audio_recorder.stop()

        # Финализация (объединение видео и аудио)
        output_path = None
        if self._encoder:
            success, error = self._encoder.finalize(has_audio=has_audio)
            if success:
                output_path = self._state.current_output
            else:
                logger.error(f"Не удалось финализировать запись: {error}")

        self._state.stop_recording()
        logger.info(f"Запись остановлена: {output_path}")
        return output_path

    def cancel_recording(self) -> None:
        """Отмена записи без сохранения."""
        self._cleanup()
        self._temp_video = None
        self._temp_audio = None
        self._state.stop_recording()
        logger.info("Запись отменена")

    def _cleanup(self) -> None:
        """Очистка ресурсов."""
        if self._video_recorder:
            try:
                self._video_recorder.stop()
            except Exception as e:
                logger.warning(f"Ошибка при остановке видео: {e}")
            self._video_recorder = None
        if self._audio_recorder:
            try:
                self._audio_recorder.stop()
            except Exception as e:
                logger.warning(f"Ошибка при остановке аудио: {e}")
            self._audio_recorder = None
        if self._encoder:
            try:
                self._encoder.cancel()
            except Exception as e:
                logger.warning(f"Ошибка при отмене кодировщика: {e}")
            self._encoder = None
        self._temp_video = None
        self._temp_audio = None
