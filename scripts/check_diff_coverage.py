"""Проверка покрытия изменённых строк Python-кода по `coverage.json`.

Скрипт используется в CI после прогона `pytest --cov-report=json`.
Вычисляет покрытие ТОЛЬКО изменённых (добавленных) строк между
base/head — классический diff coverage: долг с покрытием legacy-кода
не блокирует новые изменения, при этом порог держит давление на
новом коде. Проверяются только production-файлы.
"""

from __future__ import annotations

import argparse
import json
import re
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

# Заголовок hunk-а unified diff: @@ -a,b +c,d @@
_HUNK_HEADER_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def _normalize_path(path: str) -> str:
    """Нормализует путь в POSIX-вид для сопоставления."""
    return path.replace("\\", "/").lstrip("./")


def _is_production_python_file(path: str) -> bool:
    """Возвращает True, если путь относится к production Python-коду."""
    normalized = _normalize_path(path)
    if (
        not normalized.endswith(".py")
        or normalized.endswith("/__init__.py")
        or normalized == "__init__.py"
    ):
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


def _run_git_diff(base_sha: str, head_sha: str) -> str:
    """Возвращает unified diff `git diff -U0` между SHA."""
    try:
        result = subprocess.run(
            [
                "git",
                "diff",
                "-U0",
                "--no-color",
                base_sha,
                head_sha,
                "--",
                "*.py",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            "Не удалось получить diff между base и head"
        ) from exc
    return result.stdout


def _parse_changed_lines(diff_text: str) -> dict[str, set[int]]:
    """
    Извлекает из unified diff номера добавленных строк по файлам.

    Returns:
        Словарь `путь (POSIX) -> множество номеров строк в новой
        версии` только для production-файлов.
    """
    changed: dict[str, set[int]] = {}
    current_file: str | None = None

    for line in diff_text.splitlines():
        if line.startswith("diff ") or line.startswith("index "):
            continue
        if line.startswith("--- "):
            continue
        if line.startswith("+++ "):
            if line.startswith("+++ b/"):
                current_file = _normalize_path(line[len("+++ b/") :])
                changed.setdefault(current_file, set())
            else:
                # +++ /dev/null — файл удалён, добавленных строк нет
                current_file = None
            continue
        if current_file is None:
            continue
        header = _HUNK_HEADER_RE.match(line)
        if header is not None:
            start = int(header.group(1))
            count = int(header.group(2)) if header.group(2) else 1
            if count > 0:
                changed[current_file].update(range(start, start + count))

    return {
        path: lines
        for path, lines in changed.items()
        if lines and _is_production_python_file(path)
    }


def _load_coverage_map(
    coverage_json_path: Path,
) -> dict[str, tuple[set[int], set[int]]]:
    """
    Загружает карту `файл -> (исполненные строки, пропущенные строки)`.

    Raises:
        ValueError: если в coverage.json нет построчных данных
            (executed_lines/missing_lines).
    """
    raw = json.loads(coverage_json_path.read_text(encoding="utf-8"))
    files = raw.get("files", {})
    coverage_by_file: dict[str, tuple[set[int], set[int]]] = {}

    for path, payload in files.items():
        normalized = _normalize_path(path)
        executed = payload.get("executed_lines")
        missing = payload.get("missing_lines")
        if executed is None or missing is None:
            raise ValueError(
                "coverage.json не содержит построчных данных "
                f"(executed_lines/missing_lines) для {path}: "
                "перегенерируйте отчёт командой "
                "`pytest --cov --cov-report=json`"
            )
        coverage_by_file[normalized] = (
            {int(n) for n in executed},
            {int(n) for n in missing},
        )
    return coverage_by_file


def _diff_coverage_percent(
    changed_lines: set[int],
    executed: set[int],
    missing: set[int],
) -> float | None:
    """
    Считает покрытие изменённых строк файла.

    Returns:
        Процент покрытия изменённых строк или None, если среди
        изменённых строк нет исполняемых (docstring/комментарии).
    """
    executable_changed = changed_lines & (executed | missing)
    if not executable_changed:
        return None
    covered_changed = executable_changed & executed
    return len(covered_changed) / len(executable_changed) * 100.0


def main() -> int:
    """Точка входа проверки diff coverage."""

    def safe_print(message: str, file: object | None = None) -> None:
        target = file or sys.stdout
        try:
            target.write(message + "\n")  # type: ignore[union-attr]
            target.flush()
        except (AttributeError, UnicodeEncodeError):
            encoded = message.encode("ascii", "backslashreplace").decode(
                "ascii"
            )
            try:
                target.write(encoded + "\n")  # type: ignore[union-attr]
                target.flush()
            except Exception:
                print(encoded)

    parser = argparse.ArgumentParser(
        description="Проверка покрытия изменённых строк Python-кода",
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
        default=70.0,
        help="Минимальное покрытие изменённых строк файла (%)",
    )
    args = parser.parse_args()

    coverage_json_path = Path(args.coverage_json)
    if not coverage_json_path.exists():
        safe_print(
            f"[diff-coverage] Файл не найден: {coverage_json_path}",
            file=sys.stderr,
        )
        return 2

    try:
        base_sha = _resolve_base_sha(args.base_sha, args.head_sha)
        changed_lines_by_file = _parse_changed_lines(
            _run_git_diff(base_sha, args.head_sha)
        )
        coverage_map = _load_coverage_map(coverage_json_path)
    except (RuntimeError, ValueError) as exc:
        safe_print(f"[diff-coverage] {exc}", file=sys.stderr)
        return 2

    if not changed_lines_by_file:
        safe_print("[diff-coverage] Нет изменённых строк в production-файлах.")
        return 0

    failed: list[tuple[str, float]] = []
    skipped: list[str] = []

    safe_print(
        "[diff-coverage] Покрытие изменённых строк "
        f"(порог: {args.min_file_coverage:.1f}%):"
    )
    for path, changed_lines in sorted(changed_lines_by_file.items()):
        if path not in coverage_map:
            # Файл изменён, но отсутствует в отчёте покрытия —
            # считаем это ошибкой конфигурации, а не успехом.
            safe_print(f"  - {path}: нет данных покрытия")
            failed.append((path, 0.0))
            continue
        executed, missing = coverage_map[path]
        percent = _diff_coverage_percent(changed_lines, executed, missing)
        if percent is None:
            skipped.append(path)
            continue
        safe_print(f"  - {path}: {percent:.2f}%")
        if percent < args.min_file_coverage:
            failed.append((path, percent))

    for path in skipped:
        safe_print(f"  - {path}: нет исполняемых изменённых строк (ok)")

    if not failed:
        safe_print("[diff-coverage] Все изменённые файлы проходят порог.")
        return 0

    safe_print("[diff-coverage] Файлы ниже порога:")
    for path, coverage_percent in failed:
        safe_print(f"  - {path}: {coverage_percent:.2f}%")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
