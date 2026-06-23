"""
Единая точка чтения версии пакета
==================================

Версия объявляется один раз в `pyproject.toml` (`[project].version`).
Все остальные места (CLI, REST API, Swagger-документация) читают её
отсюда, а не хранят собственную копию строки версии.
"""

import importlib.metadata

_FALLBACK_VERSION = "unknown"


def get_version() -> str:
    """
    Получить версию пакета из метаданных установленного пакета.

    Возвращает версию, под которой пакет фактически установлен в текущее
    окружение (обновляется при `uv sync`/переустановке после правки
    `pyproject.toml`).

    Returns:
        Строка версии или `_FALLBACK_VERSION`, если пакет не установлен
        (например, запуск исходников без `pip install -e .`/`uv sync`).
    """
    try:
        return importlib.metadata.version("mia-screencapture")
    except importlib.metadata.PackageNotFoundError:
        return _FALLBACK_VERSION
