"""
Утилита длительного smoke-прогона API.

Запускает периодические запросы к API в течение заданного времени
и сохраняет краткий отчёт в markdown-файл для релизных заметок.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import requests

HEALTH_PATH: Final[str] = "/health"
STATUS_PATH: Final[str] = "/api/v1/status"
CONFIG_PATH: Final[str] = "/api/v1/config"
DEFAULT_DURATION_MINUTES: Final[int] = 30
DEFAULT_INTERVAL_SECONDS: Final[int] = 15
DEFAULT_TIMEOUT_SECONDS: Final[float] = 3.0
DEFAULT_NOTE_PATH: Final[Path] = Path("plans/release-note-v1.4.5-smoke.md")


@dataclass(slots=True)
class EndpointStat:
    """Статистика по одному endpoint."""

    path: str
    ok: int = 0
    failed: int = 0
    last_error: str | None = None
    last_status_code: int | None = None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Длительный smoke-прогон API (health/status/config) "
            "с сохранением отчёта в release-note."
        )
    )
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:5010",
        help="Базовый URL API (по умолчанию: http://127.0.0.1:5010)",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="API ключ для защищённых endpoint (X-API-Key).",
    )
    parser.add_argument(
        "--duration-minutes",
        type=int,
        default=DEFAULT_DURATION_MINUTES,
        help=f"Длительность прогона в минутах (по умолчанию: {DEFAULT_DURATION_MINUTES}).",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=DEFAULT_INTERVAL_SECONDS,
        help=(
            "Пауза между циклами запросов в секундах "
            f"(по умолчанию: {DEFAULT_INTERVAL_SECONDS})."
        ),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=(
            "Таймаут одного HTTP запроса в секундах "
            f"(по умолчанию: {DEFAULT_TIMEOUT_SECONDS})."
        ),
    )
    parser.add_argument(
        "--note-path",
        type=Path,
        default=DEFAULT_NOTE_PATH,
        help=(
            "Путь к markdown-файлу, куда добавить итог "
            f"(по умолчанию: {DEFAULT_NOTE_PATH})."
        ),
    )
    return parser


def _request(
    session: requests.Session,
    base_url: str,
    stat: EndpointStat,
    timeout_seconds: float,
    headers: dict[str, str],
) -> None:
    """Выполняет один запрос и обновляет статистику."""
    url = f"{base_url}{stat.path}"
    try:
        response = session.get(url, timeout=timeout_seconds, headers=headers)
    except requests.RequestException as exc:
        stat.failed += 1
        stat.last_error = str(exc)
        return

    stat.last_status_code = response.status_code
    if response.status_code == 200:
        stat.ok += 1
        return

    stat.failed += 1
    try:
        error_data = response.json()
        stat.last_error = json.dumps(error_data, ensure_ascii=False)
    except ValueError:
        stat.last_error = response.text[:300]


def _format_report(
    *,
    started_at: datetime,
    finished_at: datetime,
    base_url: str,
    duration_minutes: int,
    interval_seconds: int,
    stats: list[EndpointStat],
) -> str:
    total_ok = sum(item.ok for item in stats)
    total_failed = sum(item.failed for item in stats)
    total_requests = total_ok + total_failed

    lines = [
        "",
        "## Авто-отчёт smoke-run",
        "",
        f"- Старт: `{started_at.isoformat()}`",
        f"- Финиш: `{finished_at.isoformat()}`",
        f"- Base URL: `{base_url}`",
        f"- Длительность: `{duration_minutes}` минут",
        f"- Интервал цикла: `{interval_seconds}` секунд",
        f"- Всего запросов: `{total_requests}`",
        f"- Успешных (200): `{total_ok}`",
        f"- Ошибок: `{total_failed}`",
        "",
        "### Детализация по endpoint",
        "",
    ]

    for item in stats:
        lines.extend(
            [
                f"- `{item.path}`: ok={item.ok}, failed={item.failed}, "
                f"last_status={item.last_status_code}",
            ]
        )
        if item.last_error:
            lines.append(f"  last_error: `{item.last_error[:400]}`")

    lines.append("")
    return "\n".join(lines)


def _append_report(note_path: Path, report: str) -> None:
    note_path.parent.mkdir(parents=True, exist_ok=True)
    if note_path.exists():
        original = note_path.read_text(encoding="utf-8")
    else:
        original = "# Smoke Run Report\n"
    updated = f"{original.rstrip()}\n{report}\n"
    note_path.write_text(updated, encoding="utf-8")


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    if args.duration_minutes <= 0:
        parser.error("--duration-minutes должен быть > 0")
    if args.interval_seconds <= 0:
        parser.error("--interval-seconds должен быть > 0")
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds должен быть > 0")

    started_at = datetime.now(UTC)
    deadline = time.monotonic() + args.duration_minutes * 60

    stats = [
        EndpointStat(path=HEALTH_PATH),
        EndpointStat(path=STATUS_PATH),
        EndpointStat(path=CONFIG_PATH),
    ]
    headers = (
        {"X-API-Key": args.api_key.strip()} if args.api_key.strip() else {}
    )

    with requests.Session() as session:
        while time.monotonic() < deadline:
            for endpoint_stat in stats:
                _request(
                    session=session,
                    base_url=args.base_url.rstrip("/"),
                    stat=endpoint_stat,
                    timeout_seconds=args.timeout_seconds,
                    headers=headers,
                )
            time.sleep(args.interval_seconds)

    finished_at = datetime.now(UTC)
    report = _format_report(
        started_at=started_at,
        finished_at=finished_at,
        base_url=args.base_url.rstrip("/"),
        duration_minutes=args.duration_minutes,
        interval_seconds=args.interval_seconds,
        stats=stats,
    )
    _append_report(args.note_path, report)

    print("Smoke-run завершён.")
    print(report)
    print(f"Отчёт добавлен в: {args.note_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
