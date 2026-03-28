"""Тесты для конфигурации логирования."""

from __future__ import annotations

import logging
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import logger_config


def _make_record(message: str, pathname: str) -> logging.LogRecord:
    """Создаёт запись лога для тестов."""
    return logging.LogRecord(
        name="video_recorder.test",
        level=logging.INFO,
        pathname=pathname,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


def _make_local_temp_dir() -> Path:
    """Создаёт локальную временную папку в рабочей директории проекта."""
    path = Path("tests/.local_tmp") / f"logger_config_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_api_filter_allows_only_api_modules() -> None:
    """Фильтр API пропускает только модули из папки `api`."""
    filt = logger_config._ApiModuleFilter()
    api_record = _make_record("api", "D:/Repo/MIA-ScreenCapture/api/routes.py")
    gui_record = _make_record("gui", "D:/Repo/MIA-ScreenCapture/gui/main.py")

    assert filt.filter(api_record) is True
    assert filt.filter(gui_record) is False


def test_daily_handler_switches_file_on_date_change(
    monkeypatch,
) -> None:
    """Обработчик переключает файл при смене даты."""
    current = {"value": datetime(2026, 3, 28, 23, 59, 59)}
    local_tmp = _make_local_temp_dir()

    def fake_now() -> datetime:
        return current["value"]

    monkeypatch.setattr(logger_config, "_now", fake_now)

    handler = logger_config._DailyLogFileHandler(
        log_dir=local_tmp,
        prefix="api",
        backup_days=30,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(message)s"))

    handler.emit(_make_record("line-before-midnight", "D:/x/api/server.py"))
    day1 = local_tmp / "api_2026-03-28.log"
    assert day1.exists()
    assert "line-before-midnight" in day1.read_text(encoding="utf-8")

    current["value"] = datetime(2026, 3, 29, 0, 0, 1)
    handler.emit(_make_record("line-after-midnight", "D:/x/api/server.py"))

    day2 = local_tmp / "api_2026-03-29.log"
    assert day2.exists()
    assert "line-after-midnight" in day2.read_text(encoding="utf-8")
    assert "line-after-midnight" not in day1.read_text(encoding="utf-8")
    handler.close()
    shutil.rmtree(local_tmp, ignore_errors=True)


def test_daily_handler_removes_old_files(monkeypatch) -> None:
    """Обработчик удаляет файлы старше `backup_days`."""
    local_tmp = _make_local_temp_dir()
    monkeypatch.setattr(
        logger_config,
        "_now",
        lambda: datetime(2026, 3, 28, 10, 0, 0),
    )

    stale = local_tmp / "api_2026-03-10.log"
    fresh = local_tmp / "api_2026-03-26.log"
    stale.write_text("old", encoding="utf-8")
    fresh.write_text("new", encoding="utf-8")

    handler = logger_config._DailyLogFileHandler(
        log_dir=local_tmp,
        prefix="api",
        backup_days=7,
        encoding="utf-8",
    )
    handler.close()

    assert not stale.exists()
    assert fresh.exists()
    shutil.rmtree(local_tmp, ignore_errors=True)
