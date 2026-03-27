"""
Модуль кодировщика
==================

Обрабатывает объединение видео/аудио и кодирование с использованием FFmpeg.
Предоставляет функциональность для объединения отдельных видеофайлов и аудиофайлов
в итоговый выходной файл с соответствующими настройками кодирования.
"""

import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from logger_config import get_module_logger
from recorder.utils import check_ffmpeg, get_ffmpeg_path

logger = get_module_logger(__name__)


@dataclass
class EncodingSettings:
    """Настройки кодирования видео."""

    codec: str = "libx264"
    bitrate: str = "2M"
    preset: str = "medium"  # ultrafast, fast, medium, slow
    crf: int = 23  # Качество (0-51, меньше - лучше)
    audio_codec: str = "aac"
    audio_bitrate: str = "192k"
    format: str = "mp4"


class Encoder:
    """
    Кодировщик на базе FFmpeg для объединения и кодирования видео/аудио.

    Предоставляет методы для:
    - Объединения видеофайлов и аудиофайлов
    - Перекодирования видео с определёнными настройками
    - Извлечения аудио из видео
    - Конвертации между форматами
    """

    def __init__(self, settings: EncodingSettings | None = None):
        """
        Инициализация кодировщика.

        Args:
            settings: Настройки кодирования (используются по умолчанию если не указаны)
        """
        self.settings = settings or EncodingSettings()
        self._ffmpeg_path = get_ffmpeg_path()
        self._ffprobe_path = self._get_ffprobe_path()

        # Проверка доступности FFmpeg
        self._check_ffmpeg()

    def _check_ffmpeg(self) -> bool:
        """
        Проверка доступности FFmpeg.

        Returns:
            True если FFmpeg доступен
        """
        available, version = check_ffmpeg()
        if not available:
            logger.error(
                "FFmpeg не найден! Пожалуйста, установите FFmpeg и добавьте в PATH. "
                "Скачать: https://ffmpeg.org/download.html"
            )
        return available

    def _get_ffprobe_path(self) -> str | None:
        """Получение пути к исполняемому файлу ffprobe."""
        return shutil.which("ffprobe")

    @property
    def is_available(self) -> bool:
        """Проверка доступности FFmpeg."""
        return self._ffmpeg_path is not None

    def merge_video_audio(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
        keep_originals: bool = True,
        progress_callback: Callable[[float], None] | None = None,
    ) -> tuple[bool, str | None]:
        """
        Объединение видеофайла и аудиофайла в один выходной файл.

        Args:
            video_path: Путь к видеофайлу (без аудио)
            audio_path: Путь к аудиофайлу (WAV)
            output_path: Путь для выходного файла
            keep_originals: Сохранять ли оригинальные файлы после объединения
            progress_callback: Опциональный обратный вызов для обновления прогресса

        Returns:
            Кортеж (успех, сообщение_об_ошибке)
        """
        if not self.is_available:
            return False, "FFmpeg недоступен"

        video_path = Path(video_path)
        audio_path = Path(audio_path)
        output_path = Path(output_path)

        # Проверка входных данных
        if not video_path.exists():
            return False, f"Видеофайл не найден: {video_path}"
        if not audio_path.exists():
            return False, f"Аудиофайл не найден: {audio_path}"

        # Убедиться, что директория вывода существует
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Формирование команды FFmpeg
            cmd = [
                "ffmpeg",
                "-y",  # Перезапись вывода
                "-i",
                str(video_path),  # Видеовход
                "-i",
                str(audio_path),  # Аудиовход
                "-c:v",
                self.settings.codec,  # Видеокодек
                "-preset",
                self.settings.preset,
                "-b:v",
                self.settings.bitrate,
                "-c:a",
                self.settings.audio_codec,  # Аудиокодек
                "-b:a",
                self.settings.audio_bitrate,
                "-map",
                "0:v:0",  # Использовать видео из первого входа
                "-map",
                "1:a:0",  # Использовать аудио из второго входа
                "-shortest",  # Завершить когда заканчивается короткий поток
                str(output_path),
            ]

            logger.info(f"Запуск FFmpeg: {' '.join(cmd)}")

            # Запуск FFmpeg
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # Таймаут 1 час
            )

            if result.returncode != 0:
                error_msg = result.stderr or "Неизвестная ошибка FFmpeg"
                logger.error(f"Ошибка FFmpeg: {error_msg}")
                return False, error_msg

            # Проверка вывода
            if not output_path.exists():
                return False, "Выходной файл не был создан"

            # Удаление оригиналов если запрошено
            if not keep_originals:
                try:
                    video_path.unlink()
                    audio_path.unlink()
                    logger.info("Оригинальные файлы удалены")
                except Exception as e:
                    logger.warning(
                        f"Не удалось удалить оригинальные файлы: {e}"
                    )

            logger.info(f"Успешно объединено в: {output_path}")
            return True, None

        except subprocess.TimeoutExpired:
            return False, "Таймаут процесса FFmpeg"
        except Exception as e:
            logger.error(f"Ошибка при объединении: {e}")
            return False, str(e)

    def encode_video(
        self,
        input_path: Path,
        output_path: Path,
        settings: EncodingSettings | None = None,
        progress_callback: Callable[[float], None] | None = None,
    ) -> tuple[bool, str | None]:
        """
        Перекодирование видео с указанными настройками.

        Args:
            input_path: Путь к входному видеофайлу
            output_path: Путь для выходного файла
            settings: Настройки кодирования (используются по умолчанию если не указаны)
            progress_callback: Опциональный обратный вызов для обновления прогресса

        Returns:
            Кортеж (успех, сообщение_об_ошибке)
        """
        if not self.is_available:
            return False, "FFmpeg недоступен"

        settings = settings or self.settings
        input_path = Path(input_path)
        output_path = Path(output_path)

        if not input_path.exists():
            return False, f"Входной файл не найден: {input_path}"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(input_path),
                "-c:v",
                settings.codec,
                "-preset",
                settings.preset,
                "-b:v",
                settings.bitrate,
                "-c:a",
                settings.audio_codec,
                "-b:a",
                settings.audio_bitrate,
                str(output_path),
            ]

            logger.info(f"Кодирование видео: {' '.join(cmd)}")

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=3600
            )

            if result.returncode != 0:
                return False, result.stderr or "Неизвестная ошибка FFmpeg"

            return True, None

        except Exception as e:
            return False, str(e)

    def get_video_info(self, video_path: Path) -> dict[str, Any] | None:
        """
        Получение информации о видеофайле с использованием ffprobe.

        Args:
            video_path: Путь к видеофайлу

        Returns:
            Словарь с информацией о видео или None при ошибке
        """
        try:
            ffprobe_bin = self._ffprobe_path or "ffprobe"
            cmd = [
                ffprobe_bin,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(video_path),
            ]

            import json

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )

            if result.returncode == 0:
                return json.loads(result.stdout)  # type: ignore[no-any-return]

        except Exception as e:
            logger.error(f"Ошибка получения информации о видео: {e}")

        return None

    def get_duration(self, video_path: Path) -> float | None:
        """
        Получение длительности видео в секундах.

        Args:
            video_path: Путь к видеофайлу

        Returns:
            Длительность в секундах или None при ошибке
        """
        info = self.get_video_info(video_path)
        if info and "format" in info:
            return float(info["format"].get("duration", 0))
        return None

    def extract_audio(
        self,
        video_path: Path,
        audio_path: Path,
        audio_codec: str = "pcm_s16le",
    ) -> tuple[bool, str | None]:
        """
        Извлечение аудио из видеофайла.

        Args:
            video_path: Путь к видеофайлу
            audio_path: Путь для выходного аудиофайла
            audio_codec: Аудиокодек для извлечения

        Returns:
            Кортеж (успех, сообщение_об_ошибке)
        """
        if not self.is_available:
            return False, "FFmpeg недоступен"

        try:
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(video_path),
                "-vn",  # Без видео
                "-acodec",
                audio_codec,
                str(audio_path),
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600
            )

            if result.returncode != 0:
                return False, result.stderr

            return True, None

        except Exception as e:
            return False, str(e)

    def create_thumbnail(
        self, video_path: Path, output_path: Path, timestamp: float = 0
    ) -> tuple[bool, str | None]:
        """
        Создание миниатюры из видео в указанной временной метке.

        Args:
            video_path: Путь к видеофайлу
            output_path: Путь для изображения миниатюры
            timestamp: Временная метка в секундах

        Returns:
            Кортеж (успех, сообщение_об_ошибке)
        """
        if not self.is_available:
            return False, "FFmpeg недоступен"

        try:
            cmd = [
                "ffmpeg",
                "-y",
                "-ss",
                str(timestamp),
                "-i",
                str(video_path),
                "-vframes",
                "1",
                str(output_path),
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )

            if result.returncode != 0:
                return False, result.stderr

            return True, None

        except Exception as e:
            return False, str(e)


class RecordingEncoder:
    """
    Высокоуровневый кодировщик для обработки полного рабочего процесса записи.

    Управляет процессом:
    1. Запись видео во временный файл
    2. Запись аудио во временный файл
    3. Объединение и кодирование в итоговый вывод
    """

    def __init__(
        self, output_path: Path, settings: EncodingSettings | None = None
    ):
        """
        Инициализация кодировщика записи.

        Args:
            output_path: Итоговый путь вывода
            settings: Настройки кодирования
        """
        self.output_path = Path(output_path)
        self.settings = settings or EncodingSettings()
        self.encoder = Encoder(settings)

        # Временные файлы
        self._temp_dir: Path | None = None
        self._temp_video: Path | None = None
        self._temp_audio: Path | None = None

    def setup(self) -> tuple[Path, Path]:
        """
        Настройка временных файлов для записи.

        Returns:
            Кортеж (путь_временного_видео, путь_временного_аудио)
        """
        # Создание временной директории
        self._temp_dir = Path(tempfile.mkdtemp(prefix="recorder_"))

        # Создание путей временных файлов
        self._temp_video = self._temp_dir / "video_temp.mp4"
        self._temp_audio = self._temp_dir / "audio_temp.wav"

        logger.info(f"Временные файлы созданы в: {self._temp_dir}")
        return self._temp_video, self._temp_audio

    def finalize(
        self,
        has_audio: bool = True,
        progress_callback: Callable[[float], None] | None = None,
    ) -> tuple[bool, str | None]:
        """
        Завершение записи объединением видео и аудио.

        Args:
            has_audio: Было ли записано аудио
            progress_callback: Опциональный обратный вызов прогресса

        Returns:
            Кортеж (успех, сообщение_об_ошибке)
        """
        if not self._temp_video or not self._temp_video.exists():
            return False, "Нет видеофайла для обработки"

        try:
            if has_audio and self._temp_audio and self._temp_audio.exists():
                # Объединение видео и аудио
                success, error = self.encoder.merge_video_audio(
                    self._temp_video,
                    self._temp_audio,
                    self.output_path,
                    keep_originals=False,
                    progress_callback=progress_callback,
                )
            else:
                # Просто копирование видео в вывод
                success, error = self.encoder.encode_video(
                    self._temp_video,
                    self.output_path,
                    progress_callback=progress_callback,
                )

            if success:
                logger.info(f"Запись завершена: {self.output_path}")

            return success, error

        finally:
            # Очистка временных файлов
            self._cleanup()

    def _cleanup(self) -> None:
        """Очистка временных файлов."""
        try:
            if self._temp_dir and self._temp_dir.exists():
                shutil.rmtree(self._temp_dir)
                logger.info(f"Временная директория очищена: {self._temp_dir}")
        except Exception as e:
            logger.warning(f"Не удалось очистить временную директорию: {e}")

        self._temp_dir = None
        self._temp_video = None
        self._temp_audio = None

    def cancel(self) -> None:
        """Отмена записи и очистка."""
        self._cleanup()
        logger.info("Запись отменена, временные файлы очищены")
