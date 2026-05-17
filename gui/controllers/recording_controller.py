"""
Контроллер записи
=================

Управляет процессом записи видео и аудио.
Отделяет бизнес-логику от UI.
"""

import time
from pathlib import Path
from typing import TYPE_CHECKING

from core.recording_state import (
    AudioSettings,
    CaptureSettings,
    RecordingState,
    VideoSettings,
)
from core.recording_types import AudioMode, CaptureMode
from logger_config import get_module_logger
from recorder.audio_recorder import AudioRecorder, SystemAudioRecorder
from recorder.encoder import EncodingSettings, RecordingEncoder
from recorder.utils import check_disk_space, check_ffmpeg
from recorder.video_recorder import CaptureArea, VideoRecorder

if TYPE_CHECKING:
    pass

logger = get_module_logger(__name__)

_FFMPEG_CHECK_TTL_SECONDS = 30.0


class RecordingController:
    """
    Контроллер для управления процессом записи.

    Отвечает за:
    - Запуск, остановку, паузу записи
    - Координацию видео и аудио рекордеров
    - Управление кодировщиком
    """

    def __init__(self, state: RecordingState | None = None):
        """
        Инициализация контроллера.

        Args:
            state: Модель состояния записи (создаётся новая, если не указана)
        """
        self._state = state or RecordingState()
        self._video_recorder: VideoRecorder | None = None
        self._audio_recorder: AudioRecorder | None = None
        self._encoder: RecordingEncoder | None = None
        self._temp_video: Path | None = None
        self._temp_audio: Path | None = None
        self._ffmpeg_check_cache: tuple[float, bool, str | None] | None = None

    @property
    def state(self) -> RecordingState:
        """Получить текущее состояние."""
        return self._state

    @property
    def elapsed_time(self) -> float:
        """Получить время записи."""
        if self._video_recorder:
            return float(self._video_recorder.elapsed_time)
        return 0.0

    def build_capture_area(self, capture: CaptureSettings) -> CaptureArea:
        """
        Построить область захвата из настроек.

        Args:
            capture: Настройки области захвата

        Returns:
            Объект CaptureArea для VideoRecorder

        Raises:
            ValueError: Если strict_window_match=True и окно не найдено
        """
        if capture.capture_type == CaptureMode.FULL:
            return CaptureArea.full_screen()
        elif capture.capture_type == CaptureMode.WINDOW:
            return CaptureArea.from_window(
                capture.window_title,
                raise_if_not_found=capture.strict_window_match,
            )
        elif capture.capture_type == CaptureMode.RECT:
            return CaptureArea.from_rect(*capture.rect_coords)

        return CaptureArea.full_screen()

    def _ensure_ffmpeg_available(self) -> tuple[bool, str | None]:
        """
        Проверить доступность FFmpeg с кэшированием результата.

        Returns:
            Кортеж `(доступен, версия)`.
        """
        now = time.monotonic()
        if self._ffmpeg_check_cache is not None:
            checked_at, available, version = self._ffmpeg_check_cache
            if now - checked_at < _FFMPEG_CHECK_TTL_SECONDS:
                return available, version

        available, version = check_ffmpeg()
        self._ffmpeg_check_cache = (now, available, version)
        return available, version

    def start_recording(
        self,
        output_path: Path,
        capture: CaptureSettings,
        audio: AudioSettings,
        video: VideoSettings,
        duration: int | None = None,
    ) -> tuple[bool, str | None]:
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
        ffmpeg_available, ffmpeg_version = self._ensure_ffmpeg_available()
        if not ffmpeg_available:
            error_msg = (
                "FFmpeg недоступен. Проверьте установку FFmpeg и наличие "
                "исполняемого файла в PATH."
            )
            logger.error(error_msg)
            return False, error_msg

        if ffmpeg_version:
            logger.debug(
                "Pre-start health-check FFmpeg OK: %s", ffmpeg_version
            )

        try:
            if output_path.exists() and output_path.is_dir():
                if output_path.suffix:
                    try:
                        output_path.rmdir()
                        logger.warning(
                            "Удалена ошибочно созданная директория: %s",
                            output_path,
                        )
                    except OSError:
                        return (
                            False,
                            "Путь вывода указывает на директорию с "
                            "расширением файла. Удалите её вручную "
                            "и повторите запись.",
                        )
            target_dir = (
                output_path.parent if output_path.suffix else output_path
            )
            if not target_dir.exists():
                try:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    logger.info(
                        "Создана директория для записи: %s", target_dir
                    )
                except OSError as e:
                    error_msg = f"Путь недоступен: {e}"
                    logger.error(error_msg)
                    return False, error_msg
            # Проверка свободного места на диске
            min_space_mb = 100
            ok, free_bytes, disk_error_msg = check_disk_space(
                output_path, min_space_mb=min_space_mb
            )
            if not ok:
                error_msg = (
                    disk_error_msg or "Недостаточно места на диске для записи."
                )
                logger.error(error_msg)
                return False, error_msg

            free_mb = free_bytes / (1024 * 1024)
            logger.info(
                f"Доступно места на диске: {free_mb:.0f} МБ "
                f"(требуется минимум {min_space_mb} МБ)"
            )

            # Настройка кодировщика
            preset = getattr(video, "preset", "medium")
            settings = EncodingSettings(
                codec=video.codec, bitrate=video.bitrate, preset=preset
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
            preset = getattr(video, "preset", "medium")
            self._video_recorder = VideoRecorder(
                fps=video.fps,
                codec=video.codec,
                bitrate=video.bitrate,
                use_ffmpeg=True,
                preset=preset,
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
            if audio.audio_type in (AudioMode.MIC, AudioMode.BOTH):
                self._audio_recorder = AudioRecorder()
                self._audio_recorder.set_callbacks(
                    on_chunks_dropped=self._on_audio_chunks_dropped
                )
                audio_started = self._audio_recorder.start(
                    self._temp_audio,
                    device_index=audio.mic_device_index,
                    duration=duration,
                )
                if not audio_started:
                    self._cleanup()
                    return False, "Не удалось запустить аудиозапись"
            elif audio.audio_type == AudioMode.SYSTEM:
                try:
                    self._audio_recorder = SystemAudioRecorder()
                    self._audio_recorder.set_callbacks(
                        on_chunks_dropped=self._on_audio_chunks_dropped
                    )
                    audio_started = self._audio_recorder.start(
                        self._temp_audio, duration=duration
                    )
                    if not audio_started:
                        self._cleanup()
                        return (
                            False,
                            "Не удалось запустить запись системного аудио",
                        )
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

    def stop_recording(self) -> Path | None:
        """
        Остановка записи и финализация.

        Returns:
            Путь к выходному файлу или None при ошибке
        """
        if not self._state.is_recording() and not self._state.is_paused():
            return None

        # Если запись на паузе, возобновляем для корректной остановки
        if self._state.is_paused():
            if self._video_recorder:
                self._video_recorder.resume()
            if self._audio_recorder:
                self._audio_recorder.resume()
            self._state.resume_recording()

        # Остановка видео
        video_stopped = True
        if self._video_recorder:
            video_stopped = self._video_recorder.stop()

        # Остановка аудио
        has_audio = self._audio_recorder is not None
        if self._audio_recorder:
            self._audio_recorder.stop()

        if not video_stopped:
            logger.error(
                "Остановка видео завершилась с ошибкой, "
                "финализация записи пропущена"
            )
            if self._encoder:
                self._encoder.cancel()
            self._state.stop_recording()
            return None

        # Финализация (объединение видео и аудио)
        output_path = None
        if self._encoder:
            success, error = self._encoder.finalize(has_audio=has_audio)
            if success:
                output_path = self._encoder.output_path
                self._state.current_output = output_path
            else:
                logger.error(f"Не удалось финализировать запись: {error}")

        self._state.stop_recording()
        logger.info(f"Запись остановлена: {output_path}")
        return output_path

    def request_stop_cancellation(self) -> bool:
        """
        Запросить отмену долгой остановки/финализации записи.

        Returns:
            `True`, если запрос отмены отправлен.
        """
        if self._encoder and self._encoder.is_finalizing:
            self._encoder.cancel()
            logger.info("Запрошена отмена финализации записи")
            return True
        return False

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

    def _on_audio_chunks_dropped(self, count: int) -> None:
        """
        Callback при потере аудио-чанков.

        Args:
            count: Общее количество потерянных чанков
        """
        logger.warning(f"Потеряно аудио-чанков: {count}")

    @property
    def dropped_audio_chunks(self) -> int:
        """Количество потерянных аудио-чанков."""
        if self._audio_recorder:
            return int(self._audio_recorder.dropped_chunks)
        return 0
