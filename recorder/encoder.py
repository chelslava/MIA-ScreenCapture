"""
Модуль кодировщика
==================

Обрабатывает объединение видео/аудио и кодирование с использованием FFmpeg.
Предоставляет функциональность для объединения отдельных видеофайлов и аудиофайлов
в итоговый выходной файл с соответствующими настройками кодирования.
"""

import re
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from logger_config import get_module_logger
from recorder.utils import (
    check_ffmpeg,
    get_ffmpeg_path,
    get_ffprobe_path,
    get_subprocess_creationflags,
)

logger = get_module_logger(__name__)
_FFMPEG_ERROR_TAIL_BYTES = 16 * 1024

# Регулярка извлечения текущей позиции из stderr FFmpeg (`time=HH:MM:SS.MS`).
_FFMPEG_TIME_RE = re.compile(
    r"\btime=(\d{1,2}):(\d{2}):(\d{2}(?:\.\d+)?)",
)


class FinalizationProgressCallback(Protocol):
    """Контракт обратного вызова прогресса финализации.

    Используется для передачи ``(percent, stage)`` из фонового FFmpeg-
    процесса наружу (GUI или API). Значение percent — float 0.0..100.0,
    stage — короткая строка вида "Объединение видео", "Перенос файла".
    """

    def __call__(self, percent: float, stage: str) -> None:
        """Обработать очередное обновление прогресса."""


class FinalizationProgressTracker:
    """Трекер прогресса финализации записи (#96).

    Агрегирует события от нескольких источников (merge, encode,
    move) и хранит последний известный прогресс в потокобезопасном
    виде — для опроса из GUI (через callback) и REST API (через
    endpoint ``/api/v1/recording/finalization-status``).
    """

    def __init__(self) -> None:
        """Инициализация пустого трекера."""
        self._lock = threading.Lock()
        self._percent: float = 0.0
        self._stage: str = ""
        self._duration_seconds: float | None = None
        self._callback: FinalizationProgressCallback | None = None

    def set_total_duration(self, seconds: float | None) -> None:
        """Установить полную длительность видео (для нормализации)."""
        with self._lock:
            self._duration_seconds = (
                float(seconds) if seconds and seconds > 0 else None
            )

    def set_callback(
        self, callback: FinalizationProgressCallback | None
    ) -> None:
        """Зарегистрировать callback обновлений (обычно из GUI)."""
        with self._lock:
            self._callback = callback

    def reset(self) -> None:
        """Сбросить состояние перед новой операцией финализации."""
        with self._lock:
            self._percent = 0.0
            self._stage = ""
            # duration и callback сохраняются между вызовами

    def update(
        self,
        percent: float | None = None,
        stage: str | None = None,
    ) -> None:
        """Обновить текущее состояние и вызвать callback (если задан).

        Args:
            percent: Новый прогресс 0–100. Если None — оставить текущий.
            stage: Имя этапа. Если None — оставить текущий.
        """
        callback: FinalizationProgressCallback | None
        with self._lock:
            if percent is not None:
                # Клампим в диапазон 0..100
                self._percent = max(0.0, min(100.0, float(percent)))
            if stage is not None:
                self._stage = stage
            current_percent = self._percent
            current_stage = self._stage
            callback = self._callback

        # Вызов callback вне лока, чтобы не держать его во время
        # пользовательского кода.
        if callback is not None:
            try:
                callback(current_percent, current_stage)
            except Exception as e:
                logger.warning(f"Ошибка в callback прогресса: {e}")

    def snapshot(self) -> dict[str, Any]:
        """Снимок текущего состояния для API.

        Returns:
            Словарь с полями ``percent``, ``stage``, ``active``.
        """
        with self._lock:
            return {
                "percent": self._percent,
                "stage": self._stage,
                "active": bool(self._stage),
            }

    def update_from_ffmpeg_stderr(
        self, stderr_text: str, *, stage: str
    ) -> None:
        """Извлечь ``time=...`` из stderr FFmpeg и обновить прогресс.

        Ищет последнее вхождение ``time=HH:MM:SS.MS`` и пересчитывает
        его в проценты от ``_duration_seconds``. Если длительность
        неизвестна — обновляет только stage.

        Args:
            stderr_text: Текущий накопленный хвост stderr FFmpeg.
            stage: Человекочитаемая метка этапа (например, "Объединение").
        """
        match = None
        for match in _FFMPEG_TIME_RE.finditer(stderr_text):
            pass  # берём последнее совпадение

        if match is None:
            self.update(stage=stage)
            return

        try:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            seconds = float(match.group(3))
        except (TypeError, ValueError):
            self.update(stage=stage)
            return

        current_seconds = hours * 3600 + minutes * 60 + seconds

        with self._lock:
            total = self._duration_seconds

        if total is None or total <= 0:
            self.update(stage=stage)
            return

        percent = (current_seconds / total) * 100.0
        self.update(percent=percent, stage=stage)


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


@dataclass
class EncoderRuntime:
    """Runtime-контекст кодировщика для общего прогресса/трекера."""

    progress_tracker: FinalizationProgressTracker = field(
        default_factory=FinalizationProgressTracker
    )


class Encoder:
    """
    Кодировщик на базе FFmpeg для объединения и кодирования видео/аудио.

    Предоставляет методы для:
    - Объединения видеофайлов и аудиофайлов
    - Перекодирования видео с определёнными настройками
    - Извлечения аудио из видео
    - Конвертации между форматами
    """

    def __init__(
        self,
        settings: EncodingSettings | None = None,
        progress_tracker: FinalizationProgressTracker | None = None,
    ):
        """
        Инициализация кодировщика.

        Args:
            settings: Настройки кодирования (используются по умолчанию если не указаны)
            progress_tracker: Опциональный трекер прогресса финализации (#96).
                Если не передан — создаётся пустой (no-op с точки зрения GUI).
        """
        self.settings = settings or EncodingSettings()
        self.progress_tracker = (
            progress_tracker
            if progress_tracker is not None
            else FinalizationProgressTracker()
        )
        self._ffmpeg_path = get_ffmpeg_path()
        self._ffprobe_path = get_ffprobe_path()

        # Проверка доступности FFmpeg
        self._check_ffmpeg()

    def _check_ffmpeg(self) -> bool:
        """
        Проверка доступности FFmpeg.

        Returns:
            True если FFmpeg доступен
        """
        status = check_ffmpeg()
        available = status.available
        if not available:
            logger.error(
                "FFmpeg не найден! Пожалуйста, установите FFmpeg и добавьте в PATH. "
                "Скачать: https://ffmpeg.org/download.html"
            )
        return bool(available)

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
        cancel_event: threading.Event | None = None,
        progress_stage: str = "Объединение видео и аудио",
    ) -> tuple[bool, str | None]:
        """
        Объединение видеофайла и аудиофайла в один выходной файл.

        Args:
            video_path: Путь к видеофайлу (без аудио)
            audio_path: Путь к аудиофайлу (WAV)
            output_path: Путь для выходного файла
            keep_originals: Сохранять ли оригинальные файлы после объединения
            progress_callback: Опциональный обратный вызов для обновления прогресса
            cancel_event: Опциональное событие отмены операции
            progress_stage: Текст этапа для внутреннего трекера прогресса
                (используется только если задан progress_callback).

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
            ffmpeg_bin = self._ffmpeg_path
            if ffmpeg_bin is None:
                return False, "FFmpeg недоступен"

            # Формирование команды FFmpeg
            cmd = [
                ffmpeg_bin,
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
            # Активируем прогресс-трекинг только если есть внешний подписчик —
            # иначе оставляем legacy-поведение (subprocess.run, mockable).
            effective_stage: str | None = None
            if progress_callback is not None:
                duration = self.get_duration(video_path)
                self.progress_tracker.set_total_duration(duration)
                self.progress_tracker.set_callback(
                    lambda pct, _stage: progress_callback(pct)
                )
                self.progress_tracker.reset()
                effective_stage = progress_stage

            result = self._run_ffmpeg_long_process(
                cmd,
                timeout=3600,
                cancel_event=cancel_event,
                progress_stage=effective_stage,
            )

            if result.cancelled:
                return False, "Операция кодирования отменена пользователем"

            if result.returncode != 0:
                error_msg = result.stderr_tail or "Неизвестная ошибка FFmpeg"
                logger.error(f"Ошибка FFmpeg: {error_msg}")
                return False, error_msg

            # Проверка вывода
            if not output_path.exists():
                return False, "Выходной файл не был создан"
            try:
                if output_path.stat().st_size == 0:
                    return False, "Выходной файл пуст"
            except OSError:
                pass

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
        cancel_event: threading.Event | None = None,
        progress_stage: str = "Перекодирование видео",
    ) -> tuple[bool, str | None]:
        """
        Перекодирование видео с указанными настройками.

        Args:
            input_path: Путь к входному видеофайлу
            output_path: Путь для выходного файла
            settings: Настройки кодирования (используются по умолчанию если не указаны)
            progress_callback: Опциональный обратный вызов для обновления прогресса
            cancel_event: Опциональное событие отмены операции
            progress_stage: Метка этапа для внутреннего трекера прогресса
                (используется только если задан progress_callback).

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
            ffmpeg_bin = self._ffmpeg_path
            if ffmpeg_bin is None:
                return False, "FFmpeg недоступен"

            cmd = [
                ffmpeg_bin,
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
            effective_stage: str | None = None
            if progress_callback is not None:
                duration = self.get_duration(input_path)
                self.progress_tracker.set_total_duration(duration)
                self.progress_tracker.set_callback(
                    lambda pct, _stage: progress_callback(pct)
                )
                self.progress_tracker.reset()
                effective_stage = progress_stage

            result = self._run_ffmpeg_long_process(
                cmd,
                timeout=3600,
                cancel_event=cancel_event,
                progress_stage=effective_stage,
            )

            if result.cancelled:
                return False, "Операция кодирования отменена пользователем"

            if result.returncode != 0:
                return (
                    False,
                    result.stderr_tail or "Неизвестная ошибка FFmpeg",
                )

            if not output_path.exists():
                return False, "Выходной файл не был создан"
            try:
                if output_path.stat().st_size == 0:
                    return False, "Выходной файл пуст"
            except OSError:
                pass

            return True, None

        except Exception as e:
            return False, str(e)

    @dataclass
    class _FFmpegProcessResult:
        returncode: int
        stderr_tail: str | None
        cancelled: bool = False

    def _read_file_tail(self, path: Path, max_bytes: int) -> str:
        """Читает хвост текстового файла безопасно по размеру."""
        if not path.exists():
            return ""
        with open(path, "rb") as file:
            file.seek(0, 2)
            size = file.tell()
            offset = max(0, size - max_bytes)
            file.seek(offset)
            data = file.read()
        return data.decode("utf-8", errors="replace").strip()

    def _run_ffmpeg_long_process(
        self,
        cmd: list[str],
        timeout: int,
        cancel_event: threading.Event | None = None,
        progress_stage: str | None = None,
    ) -> _FFmpegProcessResult:
        """
        Выполняет долгий FFmpeg-процесс без накопления stderr в памяти.

        stderr пишется во временный файл, а при ошибке возвращается только
        ограниченный хвост.

        Если задан ``progress_stage`` — stderr периодически сканируется
        на предмет ``time=HH:MM:SS.MS``, и прогресс отправляется в
        ``self.progress_tracker`` под указанной меткой этапа (#96).

        Args:
            cmd: Команда FFmpeg.
            timeout: Таймаут в секундах.
            cancel_event: Опциональное событие отмены.
            progress_stage: Метка этапа для прогресс-трекера. Если None —
                прогресс не отслеживается (legacy-поведение).
        """
        stderr_temp_path: Path | None = None
        creationflags = get_subprocess_creationflags()
        last_progress_poll = 0.0
        last_reported_time_seconds = -1.0

        def _poll_progress(now: float) -> None:
            """Периодический polling stderr для извлечения time=... (#96)."""
            nonlocal last_progress_poll, last_reported_time_seconds
            if progress_stage is None:
                return
            if now - last_progress_poll < 0.4:
                return
            last_progress_poll = now
            if stderr_temp_path is None:
                return
            try:
                tail = self._read_file_tail(stderr_temp_path, max_bytes=4096)
                if not tail:
                    return
                match = None
                for match in _FFMPEG_TIME_RE.finditer(tail):
                    pass
                if match is None:
                    return
                try:
                    hours = int(match.group(1))
                    minutes = int(match.group(2))
                    seconds = float(match.group(3))
                    current = hours * 3600 + minutes * 60 + seconds
                except (TypeError, ValueError):
                    return
                if current <= last_reported_time_seconds:
                    return
                last_reported_time_seconds = current
                with self.progress_tracker._lock:
                    total = self.progress_tracker._duration_seconds
                if total is None or total <= 0:
                    self.progress_tracker.update(stage=progress_stage)
                    return
                percent = (current / total) * 100.0
                self.progress_tracker.update(
                    percent=percent, stage=progress_stage
                )
            except Exception as e:
                logger.debug(f"Polling прогресса FFmpeg: {e}")

        try:
            with tempfile.NamedTemporaryFile(
                prefix="ffmpeg_stderr_",
                suffix=".log",
                delete=False,
            ) as stderr_file:
                stderr_temp_path = Path(stderr_file.name)
                cancelled = False
                process: Any

                # Лёгкий путь (без отмены и без прогресса): даём шанс
                # существующим тестам мокировать subprocess.run (#96).
                use_simple_run = (
                    cancel_event is None and progress_stage is None
                )
                if use_simple_run:
                    if creationflags:
                        process = subprocess.run(
                            cmd,
                            stdout=subprocess.DEVNULL,
                            stderr=stderr_file,
                            timeout=timeout,
                            creationflags=creationflags,
                        )
                    else:
                        process = subprocess.run(
                            cmd,
                            stdout=subprocess.DEVNULL,
                            stderr=stderr_file,
                            timeout=timeout,
                        )
                else:
                    popen_kwargs: dict[str, Any] = {
                        "stdout": subprocess.DEVNULL,
                        "stderr": stderr_file,
                    }
                    if creationflags:
                        popen_kwargs["creationflags"] = creationflags

                    process = subprocess.Popen(cmd, **popen_kwargs)
                    deadline = time.monotonic() + timeout

                    if progress_stage is not None:
                        self.progress_tracker.update(
                            percent=0.0, stage=progress_stage
                        )

                    while True:
                        if cancel_event is not None and cancel_event.is_set():
                            cancelled = True
                            process.terminate()
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait(timeout=5)
                            break

                        if process.poll() is not None:
                            break

                        if time.monotonic() >= deadline:
                            process.kill()
                            raise subprocess.TimeoutExpired(
                                cmd=cmd, timeout=timeout
                            )

                        _poll_progress(time.monotonic())
                        time.sleep(0.1)

                    # Финальный опрос: зафиксировать 100% если успех.
                    _poll_progress(time.monotonic() + 1.0)
                    if progress_stage is not None and not cancelled:
                        if process.returncode == 0:
                            self.progress_tracker.update(
                                percent=100.0, stage=progress_stage
                            )
            stderr_tail = None
            if (
                process.returncode != 0 or cancelled
            ) and stderr_temp_path is not None:
                stderr_tail = self._read_file_tail(
                    stderr_temp_path,
                    max_bytes=_FFMPEG_ERROR_TAIL_BYTES,
                )
                if not stderr_tail:
                    process_stderr = getattr(process, "stderr", None)
                    if isinstance(process_stderr, str):
                        stderr_tail = process_stderr.strip() or None
            return self._FFmpegProcessResult(
                returncode=process.returncode,
                stderr_tail=stderr_tail,
                cancelled=cancelled,
            )
        finally:
            if stderr_temp_path is not None:
                try:
                    stderr_temp_path.unlink(missing_ok=True)
                except Exception as e:
                    logger.debug(
                        "Не удалось удалить временный stderr лог %s: %s",
                        stderr_temp_path,
                        e,
                    )

    def get_video_info(self, video_path: Path) -> dict[str, Any] | None:
        """
        Получение информации о видеофайле с использованием ffprobe.

        Args:
            video_path: Путь к видеофайлу

        Returns:
            Словарь с информацией о видео или None при ошибке
        """
        try:
            ffprobe_bin = self._ffprobe_path
            if ffprobe_bin is None:
                logger.warning("FFprobe недоступен")
                return None

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

            creationflags = get_subprocess_creationflags()
            if creationflags:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    creationflags=creationflags,
                )
            else:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=30
                )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                if isinstance(data, dict):
                    return data

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
            ffmpeg_bin = self._ffmpeg_path
            if ffmpeg_bin is None:
                return False, "FFmpeg недоступен"

            cmd = [
                ffmpeg_bin,
                "-y",
                "-i",
                str(video_path),
                "-vn",  # Без видео
                "-acodec",
                audio_codec,
                str(audio_path),
            ]

            creationflags = get_subprocess_creationflags()
            if creationflags:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600,
                    creationflags=creationflags,
                )
            else:
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
            ffmpeg_bin = self._ffmpeg_path
            if ffmpeg_bin is None:
                return False, "FFmpeg недоступен"

            cmd = [
                ffmpeg_bin,
                "-y",
                "-ss",
                str(timestamp),
                "-i",
                str(video_path),
                "-vframes",
                "1",
                str(output_path),
            ]

            creationflags = get_subprocess_creationflags()
            if creationflags:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    creationflags=creationflags,
                )
            else:
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
        self,
        output_path: Path,
        settings: EncodingSettings | None = None,
        progress_tracker: FinalizationProgressTracker | None = None,
    ):
        """
        Инициализация кодировщика записи.

        Args:
            output_path: Итоговый путь вывода
            settings: Настройки кодирования
            progress_tracker: Общий трекер прогресса финализации (#96).
                Если не передан, создаётся локальный экземпляр; для
                GUI/API имеет смысл передавать общий экземпляр.
        """
        self.output_path = Path(output_path)
        self.settings = settings or EncodingSettings()
        self.progress_tracker = (
            progress_tracker
            if progress_tracker is not None
            else FinalizationProgressTracker()
        )
        self.encoder = Encoder(
            settings, progress_tracker=self.progress_tracker
        )

        # Временные файлы
        self._temp_dir: Path | None = None
        self._temp_video: Path | None = None
        self._temp_audio: Path | None = None
        self._cancel_requested = threading.Event()
        self._is_finalizing = False

    @property
    def is_finalizing(self) -> bool:
        """Показывает, идёт ли финализация записи."""
        return self._is_finalizing

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

        Прогресс публикуется в ``self.progress_tracker`` (доступен через
        ``snapshot()`` для API). Если передан внешний ``progress_callback`` —
        он регистрируется в трекере и получает промежуточные обновления
        от FFmpeg (процент 0–100) (#96).

        Args:
            has_audio: Было ли записано аудио
            progress_callback: Опциональный обратный вызов прогресса
                (вызовы делаются из worker-потока; для GUI используйте
                Qt-механизм ``QueuedConnection``, чтобы не трогать
                виджеты напрямую из фонового потока).

        Returns:
            Кортеж (успех, сообщение_об_ошибке)
        """
        if not self._temp_video or not self._temp_video.exists():
            return False, "Нет видеофайла для обработки"
        if self._temp_dir is None:
            return False, "Нет временной директории для обработки"

        self._cancel_requested.clear()
        self._is_finalizing = True
        # Сброс состояния перед новой финализацией (PR I9).
        self.progress_tracker.reset()
        try:
            temp_output_path = self._temp_dir / (
                f"final_temp{self.output_path.suffix}"
            )
            if has_audio and self._temp_audio and self._temp_audio.exists():
                # Объединение видео и аудио (stage поднимается внутри
                # merge_video_audio через _run_ffmpeg_long_process).
                success, error = self.encoder.merge_video_audio(
                    self._temp_video,
                    self._temp_audio,
                    temp_output_path,
                    keep_originals=False,
                    progress_callback=progress_callback,
                    cancel_event=self._cancel_requested,
                )
            else:
                # Просто копирование видео в вывод
                success, error = self.encoder.encode_video(
                    self._temp_video,
                    temp_output_path,
                    progress_callback=progress_callback,
                    cancel_event=self._cancel_requested,
                )

            if success:
                self.progress_tracker.update(
                    percent=100.0, stage="Перенос файла"
                )
                moved, move_error = self._move_final_output(temp_output_path)
                if not moved:
                    return False, move_error
                logger.info(f"Запись завершена: {self.output_path}")

            return success, error

        finally:
            self._is_finalizing = False
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

    def _move_final_output(
        self, temp_output_path: Path
    ) -> tuple[bool, str | None]:
        """Переносит финальный файл в целевую директорию.

        Args:
            temp_output_path: Путь к временному выходному файлу.

        Returns:
            Кортеж (успех, сообщение_об_ошибке или None)
        """
        try:
            temp_output_path.replace(self.output_path)
            return True, None
        except PermissionError as e:
            # Пытаемся копированием, если rename/replace запрещён политиками.
            try:
                shutil.copy2(temp_output_path, self.output_path)
                temp_output_path.unlink(missing_ok=True)
                return True, None
            except Exception:
                # Падение доступа к целевой папке — пробуем безопасный fallback.
                fallback_dir = Path.home() / "Videos" / "Recordings"
                try:
                    fallback_dir.mkdir(parents=True, exist_ok=True)
                    fallback_path = fallback_dir / self.output_path.name
                    shutil.copy2(temp_output_path, fallback_path)
                    temp_output_path.unlink(missing_ok=True)
                    self.output_path = fallback_path
                    logger.warning(
                        "Файл сохранён в резервную директорию: %s",
                        self.output_path,
                    )
                    return True, None
                except Exception as fallback_error:
                    return (
                        False,
                        f"Не удалось переместить файл: {e} "
                        f"(fallback: {fallback_error})",
                    )
        except Exception as e:
            return False, f"Не удалось переместить файл: {e}"

    def cancel(self) -> None:
        """Отмена записи и очистка."""
        self._cancel_requested.set()
        if self._is_finalizing:
            logger.info("Запрошена отмена текущей финализации записи")
            return
        self._cleanup()
        logger.info("Запись отменена, временные файлы очищены")
