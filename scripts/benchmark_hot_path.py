"""Регрессионный бенчмарк hot-path записи (#173).

Питает `FFmpegVideoWriter` синтетическими кадрами с целевым FPS и
замеряет: достигнутый FPS, p50/p99 длительности `write()`, долю
«медленных» записей и пик RSS процесса FFmpeg. WGC-захват на раннере
недетерминирован, поэтому бенчмарк защищает именно writer-конвейер —
тот же подход, что и soak-тест (#174), но короче и с порогами.

Абсолютные пороги вместо сравнения с бейслайном: шум runner'ов GitHub
делает дельта-сравнение ненадёжным, а деградация алгоритмической
сложности (например, O(n²) на кадр) видна на абсолютных порогах.

Запуск: `uv run python scripts/benchmark_hot_path.py --duration 60 --report bench.json`
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

import psutil

from logger_config import get_module_logger
from scripts.soak_test import build_frame, find_ffmpeg_child_pid

logger = get_module_logger(__name__)

DEFAULT_DURATION_S = 60.0
DEFAULT_FPS = 30
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
# Достигнутый FPS не ниже 95% целевого
MIN_FPS_RATIO = 0.95
# p99 записи кадра не дольше 25 мс (кадр 1280x720 — единицы мс)
MAX_WRITE_P99_MS = 25.0
# Доля записей дольше 10 мс не выше 2%
MAX_SLOW_WRITE_RATIO = 0.02
SLOW_WRITE_THRESHOLD_MS = 10.0
# RSS FFmpeg не выше 700 МБ для 720p-конвейера
MAX_RSS_MB = 700.0
# Допуск длительности контейнера против записанных кадров (секунды)
DURATION_TOLERANCE_S = 5.0


def percentile(sorted_values: list[float], q: float) -> float:
    """Персентиль отсортированного списка (0..1).

    Args:
        sorted_values: Отсортированные по возрастанию значения.
        q: Квантиль от 0.0 до 1.0.

    Returns:
        Значение персентиля; 0.0 для пустого списка.
    """
    if not sorted_values:
        return 0.0
    # nearest-rank: ceil — p99 маленькой выборки не занижается
    index = min(math.ceil(q * len(sorted_values)) - 1, len(sorted_values) - 1)
    return sorted_values[max(index, 0)]


def evaluate_benchmark(report: dict[str, Any]) -> list[str]:
    """Проверить отчёт бенчмарка на регресс производительности (#173).

    Args:
        report: Отчёт из `run_benchmark`.

    Returns:
        Список нарушений; пустой список — пороги соблюдены.
    """
    failures: list[str] = []

    target_fps = float(report.get("fps", 0))
    elapsed = float(report.get("elapsed_s", 0))
    written = int(report.get("frames_written", 0))
    if elapsed > 0 and target_fps > 0:
        achieved_fps = written / elapsed
        if achieved_fps < target_fps * MIN_FPS_RATIO:
            failures.append(
                f"FPS просел: {achieved_fps:.1f} < "
                f"{target_fps * MIN_FPS_RATIO:.1f} (95% от целевого)"
            )

    write_p99_ms = report.get("write_p99_ms")
    if write_p99_ms is not None and write_p99_ms > MAX_WRITE_P99_MS:
        failures.append(
            f"p99 write() {write_p99_ms:.1f} мс > {MAX_WRITE_P99_MS} мс"
        )

    slow_ratio = report.get("slow_write_ratio")
    if slow_ratio is not None and slow_ratio > MAX_SLOW_WRITE_RATIO:
        failures.append(
            f"Доля медленных записей {slow_ratio * 100:.1f}% > "
            f"{MAX_SLOW_WRITE_RATIO * 100:.0f}%"
        )

    rss_peak = report.get("rss_peak_mb")
    if rss_peak is not None and rss_peak > MAX_RSS_MB:
        failures.append(f"Пик RSS FFmpeg {rss_peak:.0f} МБ > {MAX_RSS_MB} МБ")

    # Дрейф длительности контейнера: рассинхрон pixel_format или PTS
    # виден как расхождение длины файла с числом записанных кадров
    expected = report.get("expected_duration_s")
    file_duration = report.get("file_duration_s")
    if expected is not None and file_duration is not None:
        if abs(float(file_duration) - float(expected)) > DURATION_TOLERANCE_S:
            failures.append(
                f"Дрейф длительности: файл {file_duration:.2f}s против "
                f"ожидаемых {expected:.2f}s (допуск ±{DURATION_TOLERANCE_S}s)"
            )

    return failures


def run_benchmark(
    output_path: Path,
    duration_s: float = DEFAULT_DURATION_S,
    fps: int = DEFAULT_FPS,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> dict[str, Any]:
    """Выполнить бенчмарк writer-конвейера и собрать отчёт (#173).

    Args:
        output_path: Путь к выходному файлу.
        duration_s: Длительность замера в секундах.
        fps: Целевой FPS.
        width: Ширина кадра.
        height: Высота кадра.

    Returns:
        Отчёт с метриками (см. `evaluate_benchmark`).
    """
    from recorder.ffmpeg_writer import FFmpegVideoWriter
    from recorder.utils import verify_video_integrity

    report: dict[str, Any] = {
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "duration_s": duration_s,
        "fps": fps,
        "width": width,
        "height": height,
        "output_path": str(output_path),
        "target_frames": int(duration_s * fps),
    }

    writer = FFmpegVideoWriter(
        output_path=output_path,
        width=width,
        height=height,
        fps=fps,
    )
    if not writer.open():
        report["error"] = "Не удалось открыть FFmpeg writer"
        return report

    ffmpeg_pid = find_ffmpeg_child_pid()
    rss_peak = 0.0
    write_durations_ms: list[float] = []
    frames_written = 0
    write_failures = 0
    frame_interval = 1.0 / fps
    start_monotonic = time.monotonic()
    next_frame_time = time.perf_counter()
    next_sample_time = start_monotonic + 1.0

    while True:
        now = time.monotonic()
        if now - start_monotonic >= duration_s:
            break

        frame = build_frame(frames_written, width, height)
        write_start = time.perf_counter()
        ok = writer.write(frame)
        write_ms = (time.perf_counter() - write_start) * 1000.0
        write_durations_ms.append(write_ms)
        if ok:
            frames_written += 1
        else:
            write_failures += 1

        next_frame_time += frame_interval
        sleep_s = next_frame_time - time.perf_counter()
        if sleep_s > 0:
            time.sleep(sleep_s)

        if now >= next_sample_time:
            if ffmpeg_pid is not None:
                try:
                    rss = psutil.Process(ffmpeg_pid).memory_info().rss / (
                        1024 * 1024
                    )
                    rss_peak = max(rss_peak, float(rss))
                except (psutil.Error, OSError):
                    pass
            next_sample_time += 1.0

    elapsed = time.monotonic() - start_monotonic
    write_durations_ms.sort()

    report["elapsed_s"] = round(elapsed, 2)
    report["frames_written"] = frames_written
    report["write_failures"] = write_failures
    report["achieved_fps"] = (
        round(frames_written / elapsed, 1) if elapsed > 0 else 0.0
    )
    report["write_p50_ms"] = round(percentile(write_durations_ms, 0.50), 2)
    report["write_p99_ms"] = round(percentile(write_durations_ms, 0.99), 2)
    report["write_mean_ms"] = (
        round(statistics.fmean(write_durations_ms), 2)
        if write_durations_ms
        else 0.0
    )
    slow_writes = sum(
        1 for ms in write_durations_ms if ms > SLOW_WRITE_THRESHOLD_MS
    )
    report["slow_write_ratio"] = (
        round(slow_writes / len(write_durations_ms), 4)
        if write_durations_ms
        else 0.0
    )
    report["rss_peak_mb"] = round(rss_peak, 1) if rss_peak else None

    # Ожидаемая длительность — из фактически записанных кадров
    report["expected_duration_s"] = round(frames_written / fps, 3)

    report["closed_ok"] = bool(writer.close(finalize_segments=True))
    integrity = verify_video_integrity(output_path)
    report["integrity_valid"] = integrity.valid
    report["file_duration_s"] = integrity.duration_s

    return report


def main() -> int:
    """Точка входа бенчмарка.

    Returns:
        0 — пороги соблюдены; 1 — регресс производительности.
    """
    parser = argparse.ArgumentParser(
        description="Регрессионный бенчмарк hot-path записи (#173)"
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=DEFAULT_DURATION_S,
        help="Длительность замера в секундах",
    )
    parser.add_argument(
        "--fps", type=int, default=DEFAULT_FPS, help="Целевой FPS"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("benchmark-output.mp4"),
        help="Путь к выходному файлу",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("benchmark-report.json"),
        help="Путь к JSON-отчёту",
    )
    args = parser.parse_args()

    logger.info(
        "Бенчмарк: %s сек, %s fps, %sx%s",
        args.duration,
        args.fps,
        1280,
        720,
    )
    report = run_benchmark(
        output_path=args.output,
        duration_s=args.duration,
        fps=args.fps,
    )
    report["failures"] = evaluate_benchmark(report)

    # Каталог отчёта может не существовать (workflow не создаёт его)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Отчёт бенчмарка: %s", args.report)

    if report["failures"]:
        for failure in report["failures"]:
            logger.error("Бенчмарк: %s", failure)
        return 1
    logger.info("Бенчмарк пройден: пороги производительности соблюдены")
    return 0


if __name__ == "__main__":
    sys.exit(main())
