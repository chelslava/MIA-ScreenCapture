"""
Общие утилиты для приложения.
"""

import json
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any

from logger_config import get_module_logger

logger = get_module_logger(__name__)


def get_app_icon_path() -> Path:
    """
    Путь к .ico приложения для брендирования окна/трея/EXE.

    В frozen-сборке (PyInstaller) ресурсы распаковываются во временный
    каталог `sys._MEIPASS`, поэтому путь относительно `__file__` там
    не работает — отсюда ветвление по `sys.frozen`, как в
    `logger_config.get_log_dir()`.

    Returns:
        Путь к `docs/assets/MIA-ScreenCapture.ico` (может не существовать —
        вызывающий код должен проверить `.exists()`).
    """
    if getattr(sys, "frozen", False):
        base_path = Path(getattr(sys, "_MEIPASS", "."))
    else:
        base_path = Path(__file__).parent
    return base_path / "docs" / "assets" / "MIA-ScreenCapture.ico"


def _restrict_file_permissions(path: Path, mode: int) -> None:
    """
    Устанавливает restricted permissions на файл.

    Args:
        path: Путь к файлу
        mode: Запрашиваемые права (например, 0o600)
    """
    try:
        os.chmod(path, mode)
        logger.debug("Установлены права %s на %s", oct(mode), path)
    except OSError as e:
        # На Windows без elevated rights chmod может не сработать —
        # логируем предупреждение, не падаем
        logger.warning(
            "Не удалось установить права %s на %s: %s",
            oct(mode),
            path,
            e,
        )


def _check_permissions(path: Path, expected_mode: int) -> None:
    """
    Проверяет, что права файла не шире запрошенных.

    Args:
        path: Путь к файлу
        expected_mode: Ожидаемые права
    """
    try:
        file_stat = os.stat(path)
        actual_mode = stat.S_IMODE(file_stat.st_mode)
        # Проверяем: actual должен быть подмножеством expected
        # (т.е. не шире, чем мы запрашивали)
        if actual_mode & ~expected_mode:
            logger.warning(
                "Файл %s имеет слишком широкие права: %s (ожидается подмножество %s)",
                path,
                oct(actual_mode),
                oct(expected_mode),
            )
    except OSError:
        pass  # stat-ошибка не критична


def atomic_write_json(path: Path, data: Any, *, mode: int = 0o600) -> bool:
    """
    Атомарная запись JSON в файл через временный файл в той же директории.

    Args:
        path: Путь к целевому файлу
        data: Данные для записи (будут сериализованы в JSON)
        mode: Права на файл после записи (по умолчанию 0o600)

    Returns:
        True если запись успешна, False в противном случае
    """
    temp_path: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp_file:
            temp_path = Path(tmp_file.name)
            json.dump(data, tmp_file, indent=2, ensure_ascii=False)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())

        os.replace(temp_path, path)
        temp_path = None  # os.replace удалил temp, больше не нужно

        _restrict_file_permissions(path, mode)
        _check_permissions(path, mode)
        return True
    except Exception as e:
        logger.error(f"Ошибка атомарной записи в {path}: {e}")
        return False
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
