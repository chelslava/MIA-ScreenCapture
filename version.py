"""
Единая точка чтения версии пакета
==================================

Версия объявляется один раз в `pyproject.toml` (`[project].version`).
Все остальные места (CLI, REST API, Swagger-документация) читают её
отсюда, а не хранят собственную копию строки версии.
"""

import importlib.metadata
import tomllib
from pathlib import Path

_FALLBACK_VERSION = "unknown"
_PACKAGE_NAME = "mia-screencapture"
_PYPROJECT_PATH = Path(__file__).resolve().parent / "pyproject.toml"


def get_version() -> str:
    """
    Получить версию из метаданных пакета или `pyproject.toml`.

    Сначала читается версия установленного пакета через
    `importlib.metadata.version("mia-screencapture")`. Если метаданные
    недоступны, функция пытается безопасно прочитать `[project].version`
    из корневого `pyproject.toml` рядом с репозиторием. При любой ошибке
    чтения возвращается `_FALLBACK_VERSION`.

    Returns:
        Строка версии или `_FALLBACK_VERSION`.
    """
    try:
        return importlib.metadata.version(_PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError:
        try:
            with _PYPROJECT_PATH.open("rb") as pyproject_file:
                pyproject_data = tomllib.load(pyproject_file)
            project_data = pyproject_data["project"]
            version = project_data["version"]
        except (
            FileNotFoundError,
            KeyError,
            OSError,
            tomllib.TOMLDecodeError,
            TypeError,
        ):
            return _FALLBACK_VERSION

        if isinstance(version, str) and version:
            return version

        return _FALLBACK_VERSION
