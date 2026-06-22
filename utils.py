"""
Общие утилиты для приложения.
"""

import json
import os
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


def atomic_write_json(path: Path, data: Any) -> bool:
    """
    Атомарная запись JSON в файл через временный файл в той же директории.

    Args:
        path: Путь к целевому файлу
        data: Данные для записи (будут сериализованы в JSON)

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
