"""Проверка покрытия изменённых Python-файлов по `coverage.json`.

Скрипт используется в CI после прогона `pytest --cov-report=json`.
Проверяет только production-файлы, изменённые между base/head.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

PRODUCTION_PATH_PREFIXES = (
    "api/",
    "cli/",
    "core/",
    "gui/",
    "recorder/",
    "scheduler/",
)
PRODUCTION_SINGLE_FILES = {
    "main.py",
    "config.py",
    "logger_config.py",
    "exceptions.py",
    "utils.py",
}


def _normalize_path(path: str) -> str:
    """Нормализует путь в POSIX-вид для сопоставления."""
    return path.replace("\\", "/").lstrip("./")


def _is_production_python_file(path: str) -> bool:
    """Возвращает True, если путь относится к production Python-коду."""
    normalized = _normalize_path(path)
    if not normalized.endswith(".py"):
        return False
    if normalized in PRODUCTION_SINGLE_FILES:
        return True
    return normalized.startswith(PRODUCTION_PATH_PREFIXES)


def _resolve_base_sha(base_sha: str | None, head_sha: str) -> str:
    """Возвращает SHA базы сравнения с безопасным fallback."""
    if base_sha and base_sha.strip() and set(base_sha) != {"0"}:
        return base_sha.strip()

    try:
        resolved = subprocess.run(
            ["git", "rev-parse", f"{head_sha}~1"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Не удалось определить base SHA для diff coverage"
        ) from exc

    if not resolved:
        raise RuntimeError("Получен пустой base SHA для diff coverage")
    return resolved


def _get_changed_python_files(base_sha: str, head_sha: str) -> list[str]:
    """Возвращает список изменённых production Python-файлов."""
    try:
        result = subprocess.run(
            [
                "git",
                "diff",
                "--name-only",
                base_sha,
                head_sha,
                "--",
                "*.py",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        try:
            fallback_base = subprocess.run(
                ["git", "rev-parse", f"{head_sha}~1"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            result = subprocess.run(
                [
                    "git",
                    "diff",
                    "--name-only",
                    fallback_base,
                    head_sha,
                    "--",
                    "*.py",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as fallback_exc:
            raise RuntimeError(
                "Не удалось получить список изменённых файлов через git diff"
            ) from fallback_exc

    files = [
        _normalize_path(line.strip())
        for line in result.stdout.splitlines()
        if line.strip()
    ]
    return [path for path in files if _is_production_python_file(path)]


def _load_coverage_map(coverage_json_path: Path) -> dict[str, float]:
    """Загружает карту `файл -> покрытие` из `coverage.json`."""
    raw = json.loads(coverage_json_path.read_text(encoding="utf-8"))
    files = raw.get("files", {})
    coverage_by_file: dict[str, float] = {}

    for path, payload in files.items():
        normalized = _normalize_path(path)
        summary = payload.get("summary", {})
        percent = float(summary.get("percent_covered", 0.0))
        coverage_by_file[normalized] = percent
    return coverage_by_file


def main() -> int:
    """Точка входа проверки diff coverage."""
    import io

    stdout_utf8 = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    stderr_utf8 = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

    def safe_print(message: str, file=None) -> None:
        target = file or stdout_utf8
        target.write(message + "\n")
        target.flush()

    parser = argparse.ArgumentParser(
        description="Проверка покрытия изменённых Python-файлов",
    )
    parser.add_argument(
        "--coverage-json",
        default="coverage.json",
        help="Путь к coverage json отчёту",
    )
    parser.add_argument("--base-sha", default="", help="Базовый SHA")
    parser.add_argument("--head-sha", default="HEAD", help="Целевой SHA")
    parser.add_argument(
        "--min-file-coverage",
        type=float,
        default=35.0,
        help="Минимальное покрытие для изменённого файла (%)",
    )
    args = parser.parse_args()

    coverage_json_path = Path(args.coverage_json)
    if not coverage_json_path.exists():
        safe_print(
            f"[diff-coverage] Файл не найден: {coverage_json_path}",
            file=stderr_utf8,
        )
        return 2

    try:
        base_sha = _resolve_base_sha(args.base_sha, args.head_sha)
        changed_files = _get_changed_python_files(base_sha, args.head_sha)
    except RuntimeError as exc:
        safe_print(f"[diff-coverage] {exc}", file=stderr_utf8)
        return 2

    if not changed_files:
        safe_print("[diff-coverage] Нет изменённых production Python-файлов.")
        return 0

    coverage_map = _load_coverage_map(coverage_json_path)
    failed: list[tuple[str, float]] = []

    safe_print(
        "[diff-coverage] Проверка изменённых файлов "
        f"(порог: {args.min_file_coverage:.1f}%):"
    )
    for path in changed_files:
        coverage_percent = coverage_map.get(path, 0.0)
        safe_print(f"  - {path}: {coverage_percent:.2f}%")
        if coverage_percent < args.min_file_coverage:
            failed.append((path, coverage_percent))

    if not failed:
        safe_print("[diff-coverage] Все изменённые файлы проходят порог.")
        return 0

    safe_print("[diff-coverage] Файлы ниже порога:")
    for path, coverage_percent in failed:
        safe_print(f"  - {path}: {coverage_percent:.2f}%")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
