"""Композитинг PiP-оверлея веб-камеры поверх основного видео (#165).

Выполняется один раз при остановке записи: FFmpeg накладывает
уменьшенное видео камеры в выбранный угол основного файла.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from core.recording_types import PiPPosition, PiPSettings
from logger_config import get_module_logger
from recorder.utils import get_subprocess_creationflags

logger = get_module_logger(__name__)

FFMPEG_BINARY = "ffmpeg"
COMPOSE_TIMEOUT_SECONDS = 900.0


def pip_overlay_position_expr(
    position: PiPPosition,
    margin_px: int = 24,
) -> tuple[str, str]:
    """Вычислить выражения x/y для FFmpeg overlay (#165).

    Используются переменные фильтра `main_w`/`main_h`/`overlay_w`/
    `overlay_h`, поэтому итоговая геометрия считается самим FFmpeg
    и не требует знания размеров в Python.

    Args:
        position: Угол основного видео.
        margin_px: Отступ от краёв, px.

    Returns:
        Пара выражений `(x, y)` для фильтра overlay.
    """
    margin = max(int(margin_px), 0)
    match position:
        case PiPPosition.BOTTOM_LEFT:
            return (str(margin), f"main_h-overlay_h-{margin}")
        case PiPPosition.TOP_LEFT:
            return (str(margin), str(margin))
        case PiPPosition.TOP_RIGHT:
            return (f"main_w-overlay_w-{margin}", str(margin))
        case PiPPosition.BOTTOM_RIGHT | _:
            return (
                f"main_w-overlay_w-{margin}",
                f"main_h-overlay_h-{margin}",
            )


def build_pip_filter_complex(settings: PiPSettings) -> str:
    """Построить filter_complex для наложения камеры (#165).

    Args:
        settings: Настройки PiP.

    Returns:
        Строка filter_complex: масштабирование камеры по ширине
        (с сохранением пропорций) и overlay в выбранном углу.
    """
    camera_width = f"main_w*{max(settings.size_percent, 1)}/100"
    x_expr, y_expr = pip_overlay_position_expr(
        settings.position, settings.margin_px
    )
    return (
        f"[1:v]scale={camera_width}:-2[cam];"
        f"[0:v][cam]overlay=x={x_expr}:y={y_expr}"
    )


def compose_pip_overlay(
    base_video: Path,
    camera_video: Path,
    output_path: Path,
    settings: PiPSettings,
    codec: str = "libx264",
    bitrate: str = "2M",
    ffmpeg_binary: str = FFMPEG_BINARY,
) -> tuple[bool, str | None]:
    """Наложить видео камеры на основное видео (#165).

    Основное видео перекодируется вместе с наложением; аудиодорожка
    базового файла (если есть) копируется без перекодирования.

    Args:
        base_video: Основной видеофайл.
        camera_video: Отдельный файл записи камеры.
        output_path: Путь результата (может совпадать с base_video —
            в этом случае запись идёт во временный файл с заменой).
        settings: Настройки PiP.
        codec: Видеокодек результата.
        bitrate: Битрейт результата.
        ffmpeg_binary: Путь к FFmpeg (для тестов).

    Returns:
        Кортеж `(успех, сообщение об ошибке или None)`.
    """
    if not base_video.exists():
        return False, f"Основной файл не найден: {base_video}"
    if not camera_video.exists():
        return False, f"Файл камеры не найден: {camera_video}"

    replace_in_place = output_path == base_video
    target = (
        output_path.with_name(
            f"{output_path.stem}_pip_tmp{output_path.suffix}"
        )
        if replace_in_place
        else output_path
    )

    cmd = [
        ffmpeg_binary,
        "-hide_banner",
        "-y",
        "-i",
        str(base_video),
        "-i",
        str(camera_video),
        "-filter_complex",
        build_pip_filter_complex(settings),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        codec,
        "-b:v",
        bitrate,
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(target),
    ]
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=COMPOSE_TIMEOUT_SECONDS,
            creationflags=get_subprocess_creationflags(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"Ошибка запуска FFmpeg для PiP: {e}"

    if result.returncode != 0:
        stderr_tail = (result.stderr or "")[-500:]
        return (
            False,
            f"FFmpeg завершился с кодом {result.returncode}: {stderr_tail}",
        )
    if not target.exists():
        return False, f"FFmpeg не создал файл: {target}"

    if replace_in_place:
        try:
            base_video.unlink()
            target.rename(output_path)
        except OSError as e:
            logger.warning("Не удалось заменить базовый файл PiP: %s", e)
            return False, f"Не удалось заменить базовый файл: {e}"

    logger.info("PiP-оверлей наложен: %s", output_path)
    return True, None
