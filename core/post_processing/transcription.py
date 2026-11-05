"""
Модуль транскрибации аудиозаписей с помощью OpenAI Whisper (Issue #123).
========================================================================

Поддерживает:
- локальный режим через пакет openai-whisper;
- облачный режим через OpenAI API;
- экспорт субтитров в форматах SRT, VTT и TXT.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from core.post_processing.steps import PostProcessingStep
from core.post_processing.types import PostProcessingStepType, StepResult
from logger_config import get_module_logger
from recorder.utils import get_ffmpeg_path

logger = get_module_logger(__name__)


def format_srt_timestamp(seconds: float) -> str:
    """Форматирует секунды в таймкод формата SRT (HH:MM:SS,mmm)."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        secs += 1
        millis = 0
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def format_vtt_timestamp(seconds: float) -> str:
    """Форматирует секунды в таймкод формата WebVTT (HH:MM:SS.mmm)."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        secs += 1
        millis = 0
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"


def segments_to_srt(segments: list[dict[str, Any]]) -> str:
    """Преобразует список сегментов Whisper в формат SRT."""
    lines: list[str] = []
    for idx, seg in enumerate(segments, start=1):
        start = format_srt_timestamp(float(seg.get("start", 0.0)))
        end = format_srt_timestamp(float(seg.get("end", 0.0)))
        text = str(seg.get("text", "")).strip()
        lines.append(f"{idx}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def segments_to_vtt(segments: list[dict[str, Any]]) -> str:
    """Преобразует список сегментов Whisper в формат WebVTT."""
    lines: list[str] = ["WEBVTT\n"]
    for idx, seg in enumerate(segments, start=1):
        start = format_vtt_timestamp(float(seg.get("start", 0.0)))
        end = format_vtt_timestamp(float(seg.get("end", 0.0)))
        text = str(seg.get("text", "")).strip()
        lines.append(f"{idx}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def segments_to_txt(segments: list[dict[str, Any]]) -> str:
    """Преобразует список сегментов Whisper в простой текст."""
    texts = [str(seg.get("text", "")).strip() for seg in segments]
    return "\n".join(t for t in texts if t)


class TranscriptionStep(PostProcessingStep):
    """
    Шаг постобработки для автоматической транскрибации аудиодорожки видеозаписи.
    """

    def __init__(
        self,
        mode: str = "local",
        model: str = "base",
        output_format: str = "srt",
        language: str | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
        is_fatal: bool = False,
        timeout_seconds: int = 600,
    ) -> None:
        super().__init__(
            step_type=PostProcessingStepType.TRANSCRIPTION,
            is_fatal=is_fatal,
            timeout_seconds=timeout_seconds,
        )
        self.mode = mode.lower()
        self.model = model
        self.output_format = output_format.lower()
        self.language = language
        self.api_key = api_key
        self.api_base = api_base

    def execute(self, input_path: Path) -> StepResult:
        """
        Извлекает аудио и транскрибирует запись в файл субтитров/текста.

        Args:
            input_path: Путь к видеофайлу.

        Returns:
            StepResult с результатом транскрибации и путём к субтитрам.
        """
        start_time = time.monotonic()
        if not input_path.exists():
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                error_message=f"Файл {input_path} не существует",
                is_fatal=self.is_fatal,
            )

        temp_audio: Path | None = None
        try:
            # 1. Извлечение аудиодорожки
            temp_audio = self._extract_audio(input_path)
            if not temp_audio or not temp_audio.exists():
                return StepResult(
                    step_type=self.step_type,
                    success=False,
                    input_path=input_path,
                    error_message="Не удалось извлечь аудиодорожку из видеофайла (возможно, аудио отсутствует)",
                    is_fatal=self.is_fatal,
                )

            # 2. Транскрибация
            if self.mode == "api":
                transcript_content = self._transcribe_api(temp_audio)
            elif self.mode == "faster-whisper":
                transcript_content = self._transcribe_faster_whisper(
                    temp_audio
                )
            else:
                transcript_content = self._transcribe_local(temp_audio)

            # 3. Сохранение файла субтитров рядом с видео
            output_subtitles = input_path.with_suffix(f".{self.output_format}")
            output_subtitles.write_text(transcript_content, encoding="utf-8")

            duration = time.monotonic() - start_time
            logger.info(
                "Транскрибация завершена успешно: %s (формат %s, режим %s, время %.1f с)",
                output_subtitles.name,
                self.output_format,
                self.mode,
                duration,
            )

            return StepResult(
                step_type=self.step_type,
                success=True,
                input_path=input_path,
                output_path=input_path,
                duration_seconds=duration,
                details={
                    "subtitles_path": str(output_subtitles),
                    "output_format": self.output_format,
                    "mode": self.mode,
                    "model": self.model,
                },
            )

        except Exception as e:
            duration = time.monotonic() - start_time
            error_msg = f"Ошибка при транскрибации аудио ({self.mode}): {e}"
            logger.exception(error_msg)
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                duration_seconds=duration,
                error_message=error_msg,
                is_fatal=self.is_fatal,
            )
        finally:
            if temp_audio and temp_audio.exists():
                try:
                    temp_audio.unlink()
                except OSError:
                    pass

    def _extract_audio(self, video_path: Path) -> Path | None:
        """Извлекает 16kHz mono WAV аудио из видеофайла через FFmpeg."""
        ffmpeg_bin = get_ffmpeg_path()
        if not ffmpeg_bin:
            raise RuntimeError("FFmpeg не найден в системе")

        fd, temp_path_str = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        temp_wav = Path(temp_path_str)

        cmd = [
            ffmpeg_bin,
            "-y",
            "-i",
            str(video_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(temp_wav),
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )

        if (
            result.returncode != 0
            or not temp_wav.exists()
            or temp_wav.stat().st_size == 0
        ):
            if temp_wav.exists():
                temp_wav.unlink()
            logger.warning(
                "FFmpeg не смог извлечь аудиодорожку: %s", result.stderr
            )
            return None

        return temp_wav

    def _transcribe_local(self, audio_path: Path) -> str:
        """Локальная транскрибация через библиотеку openai-whisper."""
        try:
            import importlib

            whisper = importlib.import_module("whisper")
        except ImportError as e:
            raise RuntimeError(
                "Библиотека openai-whisper не установлена. "
                "Установите её командой: pip install openai-whisper"
            ) from e

        model = _load_whisper_model(whisper, self.model)

        options: dict[str, Any] = {}
        if self.language:
            options["language"] = self.language
        # Явный fp16=False на CPU: без него openai-whisper предупреждает
        # на каждом вызове и всё равно откатывается на FP32 (#182)
        options["fp16"] = False

        result = model.transcribe(str(audio_path), **options)
        segments = result.get("segments", [])

        if self.output_format == "vtt":
            return segments_to_vtt(segments)
        elif self.output_format == "txt":
            return segments_to_txt(segments)
        else:
            return segments_to_srt(segments)

    def _transcribe_faster_whisper(self, audio_path: Path) -> str:
        """Транскрибация через faster-whisper (CTranslate2) (#182).

        ~4x быстрее openai-whisper на CPU (int8-квантование, CTranslate2).
        Пакет не входит в обязательные зависимости — импортируется по
        требованию с понятной ошибкой установки.

        Args:
            audio_path: Путь к извлечённому WAV-файлу.

        Returns:
            Содержимое файла субтитров/текста.

        Raises:
            RuntimeError: если пакет faster-whisper не установлен.
        """
        try:
            import importlib

            fw = importlib.import_module("faster_whisper")
        except ImportError as e:
            raise RuntimeError(
                "Пакет faster-whisper не установлен. "
                "Установите его командой: pip install faster-whisper"
            ) from e

        model = _load_faster_whisper_model(fw, self.model)
        segments, _info = model.transcribe(str(audio_path))
        segment_list = [
            {"start": s.start, "end": s.end, "text": s.text} for s in segments
        ]

        if self.output_format == "vtt":
            return segments_to_vtt(segment_list)
        elif self.output_format == "txt":
            return segments_to_txt(segment_list)
        return segments_to_srt(segment_list)

    def _transcribe_api(self, audio_path: Path) -> str:
        """Транскрибация через OpenAI Whisper API."""
        try:
            import importlib

            openai_mod = importlib.import_module("openai")
            openai_cls = openai_mod.OpenAI
        except (ImportError, AttributeError) as e:
            raise RuntimeError(
                "Библиотека openai не установлена. "
                "Установите её командой: pip install openai"
            ) from e

        api_key = self.api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("Не указан API ключ OpenAI (OPENAI_API_KEY)")

        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if self.api_base:
            client_kwargs["base_url"] = self.api_base

        client = openai_cls(**client_kwargs)

        response_format = (
            "srt"
            if self.output_format == "srt"
            else ("vtt" if self.output_format == "vtt" else "text")
        )

        with open(audio_path, "rb") as audio_file:
            kwargs: dict[str, Any] = {
                "file": audio_file,
                "model": self.model if self.model != "base" else "whisper-1",
                "response_format": response_format,
            }
            if self.language:
                kwargs["language"] = self.language

            response = client.audio.transcriptions.create(**kwargs)

        return str(response)


# Кэш загруженных моделей (#182): веса грузятся с диска один раз
# на процесс; повторные шаги транскрибации используют готовую модель.
_WHISPER_MODEL_CACHE: dict[str, Any] = {}
_FASTER_WHISPER_MODEL_CACHE: dict[str, Any] = {}


def _load_whisper_model(whisper: Any, model_name: str) -> Any:
    """Загрузить модель openai-whisper с кэшированием (#182).

    Args:
        whisper: Модуль openai-whisper.
        model_name: Имя модели ("base", "small", ...).

    Returns:
        Загруженная модель (из кэша при повторном вызове).
    """
    if model_name not in _WHISPER_MODEL_CACHE:
        logger.info("Загрузка модели Whisper '%s'...", model_name)
        _WHISPER_MODEL_CACHE[model_name] = whisper.load_model(model_name)
    return _WHISPER_MODEL_CACHE[model_name]


def _load_faster_whisper_model(fw: Any, model_name: str) -> Any:
    """Загрузить модель faster-whisper с кэшированием (#182).

    Аргументы: int8 на CPU (быстрее и меньше RAM), автодетект device.

    Args:
        fw: Модуль faster_whisper.
        model_name: Имя модели ("base", "small", ...).

    Returns:
        Загруженная модель (из кэша при повторном вызове).
    """
    if model_name not in _FASTER_WHISPER_MODEL_CACHE:
        logger.info("Загрузка модели faster-whisper '%s'...", model_name)
        _FASTER_WHISPER_MODEL_CACHE[model_name] = fw.WhisperModel(
            model_name, device="auto", compute_type="int8"
        )
    return _FASTER_WHISPER_MODEL_CACHE[model_name]
