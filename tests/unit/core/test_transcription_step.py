"""
Unit-тесты для шага транскрибации аудиодорожки с помощью OpenAI Whisper (Issue #123).
=====================================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from config import PostProcessingSettings
from core.post_processing.manager import PostProcessingManager
from core.post_processing.transcription import (
    TranscriptionStep,
    format_srt_timestamp,
    format_vtt_timestamp,
    segments_to_srt,
    segments_to_txt,
    segments_to_vtt,
)
from core.post_processing.types import PostProcessingStepType


def test_timestamp_formatting() -> None:
    """Проверка форматирования таймкодов для SRT и VTT."""
    # 0 секунд
    assert format_srt_timestamp(0.0) == "00:00:00,000"
    assert format_vtt_timestamp(0.0) == "00:00:00.000"

    # 65.5 секунд -> 00:01:05,500
    assert format_srt_timestamp(65.5) == "00:01:05,500"
    assert format_vtt_timestamp(65.5) == "00:01:05.500"

    # 3661.123 секунд -> 01:01:01,123
    assert format_srt_timestamp(3661.123) == "01:01:01,123"
    assert format_vtt_timestamp(3661.123) == "01:01:01.123"


def test_segments_converters() -> None:
    """Проверка конвертации сегментов Whisper в форматы SRT, VTT, TXT."""
    segments = [
        {"start": 0.0, "end": 2.5, "text": "Привет мир"},
        {"start": 3.0, "end": 5.2, "text": "Тестовая запись"},
    ]

    srt = segments_to_srt(segments)
    assert "1\n00:00:00,000 --> 00:00:02,500\nПривет мир" in srt
    assert "2\n00:00:03,000 --> 00:00:05,200\nТестовая запись" in srt

    vtt = segments_to_vtt(segments)
    assert vtt.startswith("WEBVTT\n")
    assert "00:00:00.000 --> 00:00:02.500" in vtt

    txt = segments_to_txt(segments)
    assert txt == "Привет мир\nТестовая запись"


def test_transcription_step_file_not_found(tmp_path: Path) -> None:
    """Шаг транскрибации завершается ошибкой, если файл не существует."""
    non_existent = tmp_path / "missing.mp4"
    step = TranscriptionStep()
    result = step.execute(non_existent)

    assert result.success is False
    assert result.step_type == PostProcessingStepType.TRANSCRIPTION
    assert "не существует" in (result.error_message or "")


def test_transcription_step_audio_extract_fails(tmp_path: Path) -> None:
    """Если аудио не удалось извлечь, возвращается понятная ошибка."""
    video_file = tmp_path / "test.mp4"
    video_file.write_text("video dummy content", encoding="utf-8")

    step = TranscriptionStep()
    with patch.object(step, "_extract_audio", return_value=None):
        result = step.execute(video_file)

    assert result.success is False
    assert "Не удалось извлечь аудиодорожку" in (result.error_message or "")


def test_transcription_step_local_success(tmp_path: Path) -> None:
    """Успешная локальная транскрибация через whisper."""
    video_file = tmp_path / "test.mp4"
    video_file.write_text("video dummy content", encoding="utf-8")

    fake_audio = tmp_path / "temp.wav"
    fake_audio.write_bytes(b"RIFF dummy wav")

    step = TranscriptionStep(mode="local", model="base", output_format="srt")

    mock_whisper = MagicMock()
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {
        "segments": [{"start": 0.0, "end": 2.0, "text": "Локальный тест"}]
    }
    mock_whisper.load_model.return_value = mock_model

    with (
        patch.object(step, "_extract_audio", return_value=fake_audio),
        patch.dict(sys.modules, {"whisper": mock_whisper}),
    ):
        result = step.execute(video_file)

    assert result.success is True
    srt_file = tmp_path / "test.srt"
    assert srt_file.exists()
    content = srt_file.read_text(encoding="utf-8")
    assert "Локальный тест" in content
    assert result.details.get("subtitles_path") == str(srt_file)


def test_transcription_step_api_success(tmp_path: Path) -> None:
    """Успешная транскрибация через OpenAI API."""
    video_file = tmp_path / "test.mp4"
    video_file.write_text("video dummy content", encoding="utf-8")

    fake_audio = tmp_path / "temp.wav"
    fake_audio.write_bytes(b"RIFF dummy wav")

    step = TranscriptionStep(
        mode="api",
        model="whisper-1",
        output_format="vtt",
        api_key="sk-fake-key",
    )

    mock_openai_module = MagicMock()
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = (
        "WEBVTT\n1\n00:00:00.000 --> 00:00:02.000\nAPI тест"
    )
    mock_openai_module.OpenAI.return_value = mock_client

    with (
        patch.object(step, "_extract_audio", return_value=fake_audio),
        patch.dict(sys.modules, {"openai": mock_openai_module}),
    ):
        result = step.execute(video_file)

    assert result.success is True
    vtt_file = tmp_path / "test.vtt"
    assert vtt_file.exists()
    content = vtt_file.read_text(encoding="utf-8")
    assert "API тест" in content


def test_transcription_step_missing_local_whisper(tmp_path: Path) -> None:
    """При отсутствии библиотеки openai-whisper возвращается понятная ошибка."""
    video_file = tmp_path / "test.mp4"
    video_file.write_text("video dummy content", encoding="utf-8")

    fake_audio = tmp_path / "temp.wav"
    fake_audio.write_bytes(b"RIFF dummy wav")

    step = TranscriptionStep(mode="local")

    with (
        patch.object(step, "_extract_audio", return_value=fake_audio),
        patch.dict(sys.modules, {"whisper": None}),
    ):
        result = step.execute(video_file)

    assert result.success is False
    assert "openai-whisper не установлена" in (result.error_message or "")


def test_post_processing_manager_builds_transcription_step() -> None:
    """PostProcessingManager создаёт TranscriptionStep при transcription_enabled=True."""
    ppm = PostProcessingManager()
    settings = PostProcessingSettings(
        enabled=True,
        transcription_enabled=True,
        transcription_mode="local",
        transcription_model="tiny",
        transcription_output_format="vtt",
        transcription_language="ru",
    )

    steps = ppm.build_steps_from_settings(settings)
    transcription_steps = [
        s for s in steps if isinstance(s, TranscriptionStep)
    ]
    assert len(transcription_steps) == 1
    t_step = transcription_steps[0]
    assert t_step.mode == "local"
    assert t_step.model == "tiny"
    assert t_step.output_format == "vtt"
    assert t_step.language == "ru"
