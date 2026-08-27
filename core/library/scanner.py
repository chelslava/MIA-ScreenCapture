"""
Сканер метаданных и генератор превью для библиотеки записей (Issue #119).
========================================================================
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path

from core.library.models import RecordingMetadata
from logger_config import get_module_logger
from recorder.utils import get_ffmpeg_path

logger = get_module_logger(__name__)


def get_ffprobe_path() -> str | None:
    """Возвращает путь к утилите ffprobe рядом с ffmpeg."""
    ffmpeg_bin = get_ffmpeg_path()
    if not ffmpeg_bin:
        return None
    ffprobe_candidate = Path(ffmpeg_bin).with_name(
        "ffprobe.exe" if os_is_win() else "ffprobe"
    )
    if ffprobe_candidate.exists():
        return str(ffprobe_candidate)
    return "ffprobe"


def os_is_win() -> bool:
    import os

    return os.name == "nt"


def extract_video_metadata(video_path: Path) -> RecordingMetadata:
    """
    Извлекает технические метаданные видеозаписи с помощью ffprobe или файловой системы.

    Args:
        video_path: Путь к видеофайлу.

    Returns:
        Экземпляр RecordingMetadata.
    """
    size_bytes = video_path.stat().st_size if video_path.exists() else 0
    created_ts = video_path.stat().st_ctime if video_path.exists() else 0
    created_at = (
        datetime.fromtimestamp(created_ts).isoformat()
        if created_ts > 0
        else datetime.now().isoformat()
    )

    width = 0
    height = 0
    fps = 0.0
    duration_sec = 0.0
    video_codec = "unknown"
    audio_codec: str | None = None

    ffprobe = get_ffprobe_path()
    if ffprobe:
        try:
            cmd = [
                ffprobe,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(video_path),
            ]
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=10,
                check=False,
            )
            if result.returncode == 0 and result.stdout:
                info = json.loads(result.stdout)
                streams = info.get("streams", [])
                format_info = info.get("format", {})

                if "duration" in format_info:
                    try:
                        duration_sec = float(format_info["duration"])
                    except (ValueError, TypeError):
                        pass

                for s in streams:
                    codec_type = s.get("codec_type")
                    if codec_type == "video" and width == 0:
                        width = int(s.get("width", 0))
                        height = int(s.get("height", 0))
                        video_codec = s.get("codec_name", "unknown")
                        r_frame_rate = s.get("r_frame_rate", "")
                        if "/" in r_frame_rate:
                            num, den = r_frame_rate.split("/")
                            if float(den) > 0:
                                fps = round(float(num) / float(den), 2)
                        elif r_frame_rate:
                            try:
                                fps = round(float(r_frame_rate), 2)
                            except ValueError:
                                pass
                        if duration_sec == 0.0 and "duration" in s:
                            try:
                                duration_sec = float(s["duration"])
                            except (ValueError, TypeError):
                                pass
                    elif codec_type == "audio" and audio_codec is None:
                        audio_codec = s.get("codec_name")

        except Exception as e:
            logger.debug(
                "Не удалось извлечь метаданные через ffprobe для %s: %s",
                video_path,
                e,
            )

    return RecordingMetadata(
        path=video_path,
        duration_sec=duration_sec,
        size_bytes=size_bytes,
        width=width,
        height=height,
        fps=fps,
        codec=video_codec,
        audio_codec=audio_codec,
        created_at=created_at,
    )


def generate_thumbnail(
    video_path: Path,
    output_dir: Path,
    width: int = 320,
    height: int = 180,
) -> Path | None:
    """
    Генерирует превью-изображение (PNG) для видеозаписи.

    Args:
        video_path: Путь к исходному видео.
        output_dir: Директория для сохранения thumbnail.
        width: Ширина превью в пикселях.
        height: Высота превью в пикселях.

    Returns:
        Путь к созданному файлу превью или None при неудаче.
    """
    if not video_path.exists():
        return None

    ffmpeg_bin = get_ffmpeg_path()
    if not ffmpeg_bin:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = output_dir / f"{video_path.stem}_thumb.png"

    # Если превью уже существует и новее видеофайла — возвращаем его
    if (
        thumb_path.exists()
        and thumb_path.stat().st_mtime >= video_path.stat().st_mtime
    ):
        return thumb_path

    cmd = [
        ffmpeg_bin,
        "-y",
        "-ss",
        "00:00:01",
        "-i",
        str(video_path),
        "-vframes",
        "1",
        "-s",
        f"{width}x{height}",
        str(thumb_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            check=False,
        )
        if (
            result.returncode != 0
            or not thumb_path.exists()
            or thumb_path.stat().st_size == 0
        ):
            # Попытка захватить самый первый кадр с позиции 0
            fallback_cmd = [
                ffmpeg_bin,
                "-y",
                "-ss",
                "00:00:00",
                "-i",
                str(video_path),
                "-vframes",
                "1",
                "-s",
                f"{width}x{height}",
                str(thumb_path),
            ]
            fallback_res = subprocess.run(
                fallback_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
                check=False,
            )
            if (
                fallback_res.returncode != 0
                or not thumb_path.exists()
                or thumb_path.stat().st_size == 0
            ):
                if thumb_path.exists():
                    thumb_path.unlink()
                return None

        return thumb_path
    except Exception as e:
        logger.debug("Ошибка генерации thumbnail для %s: %s", video_path, e)
        if thumb_path.exists():
            try:
                thumb_path.unlink()
            except OSError:
                pass
        return None
