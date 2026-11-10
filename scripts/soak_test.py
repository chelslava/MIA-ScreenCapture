"""Soak-тест длинной записи: стабильность FFmpeg-пайплайна (#174).

Кормит `FFmpegVideoWriter` синтетическими кадрами с целевым FPS заданное
время, периодически замеряет RSS процесса FFmpeg, затем проверяет
целостность и длительность файла через ffprobe. Кадры — движущийся
градиент: застревание потока сразу видно на артефактах.

Захват WGC в CI недетерминирован (виртуальный дисплей), поэтому тестируется
именно writer-пайплайн — источник утечек и дрейфа PTS.

Запуск: `uv run python scripts/soak_test.py --duration 7200 --report soak-report.json`
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import psutil

from logger_config import get_module_logger
from recorder.ffmpeg_writer import FFmpegVideoWriter
from recorder.utils import verify_video_integrity

logger = get_module_logger(__name__)

DEFAULT_DURATION_S = 7200.0
DEFAULT_FPS = 30
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
RSS_SAMPLE_INTERVAL_S = 10.0
# Порог роста RSS: 10 МБ/мин на протяжении часов — явная утечка
RSS_GROWTH_THRESHOLD_MB_PER_MIN = 10.0
# Допуск длительности файла против ожидаемой (секунды)
DURATION_TOLERANCE_S = 5.0
# Минимальная доля записанных кадров от целевого
MIN_FRAMES_RATIO = 0.98
GET_FFMPEG_CHILD_TIMEOUT_S = 5.0


def build_frame(index: int, width: int, height: int) -> np.ndarray:
    """Синтетический кадр: горизонтальный градиент со сдвигом по времени.

    Args:
        index: Номер кадра.
        width: Ширина кадра.
        height: Высота кадра.

    Returns:
        BGR-кадр высотой `height` и шириной `width`.
    """
    row = np.linspace(0, 255, width, dtype=np.uint8)
    frame = np.broadcast_to(row[None, :, None], (height, width, 3)).copy()
    shift = index % width
    if shift:
        frame = np.roll(frame, shift, axis=1)
    return frame


def find_ffmpeg_child_pid() -> int | None:
    """Найти PID дочернего процесса FFmpeg текущего скрипта.

    Returns:
        PID или `None`, если процесс не найден.
    """
    try:
        for child in psutil.Process().children(recursive=True):
            if child.name().lower().startswith("ffmpeg"):
                return int(child.pid)
    except (psutil.Error, OSError) as e:
        logger.warning("Не удалось найти процесс FFmpeg: %s", e)
    return None


def sample_rss_mb(pid: int | None) -> float | None:
    """Текущий RSS процесса в МБ.

    Args:
        pid: PID процесса FFmpeg.

    Returns:
        RSS в МБ или `None`, если процесс недоступен.
    """
    if pid is None:
        return None
    try:
        return float(psutil.Process(pid).memory_info().rss / (1024 * 1024))
    except (psutil.Error, OSError):
        return None


def rss_growth_mb_per_min(
    samples: list[tuple[float, float]],
) -> float | None:
    """Скорость роста RSS между первым и последним замером.

    Args:
        samples: Пары `(elapsed_s, rss_mb)`.

    Returns:
        МБ/мин (может быть отрицательным) или `None` при < 2 замеров.
    """
    if len(samples) < 2:
        return None
    first_t, first_rss = samples[0]
    last_t, last_rss = samples[-1]
    if last_t <= first_t:
        return None
    return (last_rss - first_rss) * 60.0 / (last_t - first_t)


def evaluate_soak_checks(report: dict[str, Any]) -> list[str]:
    """Проверить отчёт soak-теста на признаки деградации (#174).

    Args:
        report: Отчёт из `run_soak`.

    Returns:
        Список нарушений; пустой список — деградации не обнаружено.
    """
    failures: list[str] = []

    if not report.get("closed_ok"):
        failures.append("Финализация контейнера завершилась с ошибкой")

    integrity = report.get("integrity") or {}
    if not integrity.get("valid"):
        failures.append(
            f"Файл не прошёл проверку целостности: {integrity.get('error')}"
        )

    expected = float(report.get("expected_duration_s", 0.0))
    duration = integrity.get("duration_s")
    if duration is None:
        failures.append("ffprobe не вернул длительность файла")
    elif abs(float(duration) - expected) > DURATION_TOLERANCE_S:
        failures.append(
            f"Дрейф длительности: файл {duration:.2f}s против "
            f"ожидаемых {expected:.2f}s (допуск ±{DURATION_TOLERANCE_S}s)"
        )

    written = int(report.get("frames_written", 0))
    target_frames = float(report.get("target_frames", 0))
    if target_frames > 0 and written < target_frames * MIN_FRAMES_RATIO:
        failures.append(
            f"Потеря кадров: записано {written} из {target_frames:.0f}"
        )

    growth = report.get("rss_growth_mb_per_min")
    if growth is not None and growth > RSS_GROWTH_THRESHOLD_MB_PER_MIN:
        failures.append(
            f"Рост RSS {growth:.2f} МБ/мин превышает порог "
            f"{RSS_GROWTH_THRESHOLD_MB_PER_MIN} МБ/мин"
        )

    return failures


def run_soak(
    output_path: Path,
    duration_s: float = DEFAULT_DURATION_S,
    fps: int = DEFAULT_FPS,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    rss_sample_interval_s: float = RSS_SAMPLE_INTERVAL_S,
) -> dict[str, Any]:
    """Выполнить soak-запись и собрать отчёт (#174).

    Args:
        output_path: Путь к выходному файлу.
        duration_s: Длительность записи в секундах.
        fps: Целевой FPS.
        width: Ширина кадра.
        height: Высота кадра.
        rss_sample_interval_s: Интервал замеров RSS.

    Returns:
        Отчёт с метриками (см. `evaluate_soak_checks`).
    """
    report: dict[str, Any] = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_s": duration_s,
        "fps": fps,
        "width": width,
        "height": height,
        "output_path": str(output_path),
    }
    target_frames = int(duration_s * fps)
    report["target_frames"] = target_frames

    writer = FFmpegVideoWriter(
        output_path=output_path,
        width=width,
        height=height,
        fps=fps,
    )
    if not writer.open():
        report["closed_ok"] = False
        report["error"] = "Не удалось открыть FFmpeg writer"
        return report

    ffmpeg_pid = find_ffmpeg_child_pid()
    report["ffmpeg_pid"] = ffmpeg_pid

    rss_samples: list[tuple[float, float]] = []
    write_failures = 0
    frames_written = 0
    frame_interval = 1.0 / fps
    start_monotonic = time.monotonic()
    next_frame_time = time.perf_counter()
    next_sample_time = start_monotonic + rss_sample_interval_s

    while True:
        now = time.monotonic()
        if now - start_monotonic >= duration_s:
            break

        if writer.write(build_frame(frames_written, width, height)):
            frames_written += 1
        else:
            write_failures += 1

        next_frame_time += frame_interval
        sleep_s = next_frame_time - time.perf_counter()
        if sleep_s > 0:
            time.sleep(sleep_s)

        if now >= next_sample_time:
            rss = sample_rss_mb(ffmpeg_pid)
            if rss is not None:
                rss_samples.append((now - start_monotonic, rss))
            next_sample_time += rss_sample_interval_s

    elapsed = time.monotonic() - start_monotonic
    report["elapsed_s"] = round(elapsed, 2)
    report["frames_written"] = frames_written
    report["write_failures"] = write_failures
    report["rss_samples"] = len(rss_samples)
    report["rss_growth_mb_per_min"] = (
        round(v, 3)
        if (v := rss_growth_mb_per_min(rss_samples)) is not None
        else None
    )
    if rss_samples:
        report["rss_first_mb"] = round(rss_samples[0][1], 1)
        report["rss_last_mb"] = round(rss_samples[-1][1], 1)

    report["closed_ok"] = bool(writer.close(finalize_segments=True))

    integrity = verify_video_integrity(output_path)
    report["integrity"] = {
        "valid": integrity.valid,
        "duration_s": integrity.duration_s,
        "codec_name": integrity.codec_name,
        "width": integrity.width,
        "height": integrity.height,
        "error": integrity.error,
    }
    return report


def main() -> int:
    """Точка входа soak-теста.

    Returns:
        0 — деградаций не обнаружено; 1 — есть нарушения.
    """
    parser = argparse.ArgumentParser(description="Soak-тест записи (#174)")
    parser.add_argument(
        "--duration",
        type=float,
        default=DEFAULT_DURATION_S,
        help="Длительность записи в секундах",
    )
    parser.add_argument(
        "--fps", type=int, default=DEFAULT_FPS, help="Целевой FPS"
    )
    parser.add_argument(
        "--width", type=int, default=DEFAULT_WIDTH, help="Ширина кадра"
    )
    parser.add_argument(
        "--height", type=int, default=DEFAULT_HEIGHT, help="Высота кадра"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("soak-output.mp4"),
        help="Путь к выходному файлу",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("soak-report.json"),
        help="Путь к JSON-отчёту",
    )
    args = parser.parse_args()

    logger.info(
        "Soak-тест: %s сек, %s fps, %sx%s",
        args.duration,
        args.fps,
        args.width,
        args.height,
    )
    report = run_soak(
        output_path=args.output,
        duration_s=args.duration,
        fps=args.fps,
        width=args.width,
        height=args.height,
    )
    report["failures"] = evaluate_soak_checks(report)

    # Каталог отчёта может не существовать (workflow не создаёт его)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Отчёт soak-теста: %s", args.report)

    if report["failures"]:
        for failure in report["failures"]:
            logger.error("Soak: %s", failure)
        return 1
    logger.info("Soak-тест пройден: деградаций не обнаружено")
    return 0


if __name__ == "__main__":
    sys.exit(main())
