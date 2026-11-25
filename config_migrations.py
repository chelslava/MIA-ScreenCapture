"""
Миграции схемы config.json (#190)
=================================

История схемы версионируется полем ``schema_version`` в корне config.json.
Конфигурации без этого поля считаются схемой v1 (эпоха до v1.9.0).

Цепочка миграций строится по реестру :data:`CONFIG_MIGRATIONS`: ключ —
версия исходной схемы, значение — функция, преобразующая данные к версии
``n + 1``. Загрузка применяет миграции последовательно до текущей версии.

Инвариант issue #190: настройки пользователя не теряются молча — все
преобразования миграций логируются и попадают в уведомление загрузки.
"""

import json
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from logger_config import get_module_logger

logger = get_module_logger(__name__)

#: Текущая версия схемы config.json. При несовместимом изменении схемы
#: увеличить и добавить миграцию в :data:`CONFIG_MIGRATIONS`.
CURRENT_SCHEMA_VERSION: Final[int] = 2

#: Версия, назначаемая конфигам без поля ``schema_version`` (до v1.9.0).
LEGACY_SCHEMA_VERSION: Final[int] = 1


@dataclass
class MigrationResult:
    """Результат применения цепочки миграций к данным конфига.

    Attributes:
        data: Преобразованные данные (глубокая копия входных).
        from_version: Версия схемы до миграций.
        to_version: Версия схемы после миграций.
        notes: Человекочитаемые шаги миграции (для уведомления и лога).
    """

    data: dict[str, Any]
    from_version: int
    to_version: int
    notes: list[str] = field(default_factory=list)


MigrationFunc = Callable[[dict[str, Any]], dict[str, Any]]

# Реестр миграций: {версия N: функция N -> N+1}. Несовместимые изменения
# схемы оформляются новыми записями, старые не удаляются — конфиг с
# любой исторической версией должен подниматься до актуальной.
CONFIG_MIGRATIONS: Final[dict[int, MigrationFunc]] = {}


def _normalize_language(data: dict[str, Any]) -> None:
    """Нормализует legacy-значение ``language`` (регистр, пробелы).

    Валидатор схемы сам приводит значение, но миграция делает
    преобразование явным шагом с логом, а не молчаливой заменой.
    """
    raw = data.get("language")
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if normalized != raw:
            logger.info(
                "Миграция: language %r нормализован в %r", raw, normalized
            )
            data["language"] = normalized


def migrate_v1_to_v2(data: dict[str, Any]) -> dict[str, Any]:
    """Миграция схемы v1 -> v2.

    Все исторические изменения схемы v1 были аддитивными (новые поля с
    дефолтами), поэтому тело миграции — явная нормализация legacy-значений
    и штамп версии. Точка расширения для будущих переименований полей.
    """
    _normalize_language(data)
    data["schema_version"] = CURRENT_SCHEMA_VERSION
    return data


CONFIG_MIGRATIONS[LEGACY_SCHEMA_VERSION] = migrate_v1_to_v2


def detect_schema_version(data: dict[str, Any]) -> int:
    """Определяет версию схемы данных конфигурации.

    Args:
        data: Словарь, разобранный из config.json.

    Returns:
        Значение ``schema_version`` или :data:`LEGACY_SCHEMA_VERSION`,
        если поле отсутствует (конфиг эпохи до v1.9.0).
    """
    raw = data.get("schema_version", LEGACY_SCHEMA_VERSION)
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 1:
        # Битое поле версии трактуем как legacy: миграции идемпотентны,
        # а Pydantic-валидация отсеет несовместимые значения полей.
        logger.warning(
            "Некорректное schema_version=%r, трактуется как версия %d",
            raw,
            LEGACY_SCHEMA_VERSION,
        )
        return LEGACY_SCHEMA_VERSION
    return int(raw)


def migrate_config_data(data: dict[str, Any]) -> MigrationResult:
    """Поднимает данные конфига до :data:`CURRENT_SCHEMA_VERSION`.

    Применяет цепочку миграций из :data:`CONFIG_MIGRATIONS`. Схема
    новее текущей (конфиг из более новой версии приложения) передаётся
    без изменений — Pydantic-валидация на месте отсечёт несовместимое,
    а данные не будут переписаны более старой схемой.

    Args:
        data: Словарь, разобранный из config.json.

    Returns:
        :class:`MigrationResult` с копией данных и списком шагов.
    """
    working = deepcopy(data)
    version = detect_schema_version(working)
    result = MigrationResult(
        data=working, from_version=version, to_version=version
    )

    if version > CURRENT_SCHEMA_VERSION:
        logger.warning(
            "schema_version=%d новее поддерживаемой %d; миграции не "
            "применяются, конфиг загружается как есть",
            version,
            CURRENT_SCHEMA_VERSION,
        )
        return result

    while version < CURRENT_SCHEMA_VERSION:
        migration = CONFIG_MIGRATIONS.get(version)
        if migration is None:
            # Дыра в реестре: прерываем, чтобы не потерять данные
            # половинным преобразованием; валидация решит судьбу файла.
            logger.error(
                "Нет миграции %d -> %d; остановка цепочки на версии %d",
                version,
                version + 1,
                version,
            )
            return result
        working = migration(working)
        version += 1
        result.notes.append(
            f"миграция схемы: версия {version - 1} -> {version}"
        )
        logger.info(
            "Конфигурация мигрирована: версия схемы %d -> %d",
            version - 1,
            version,
        )

    result.data = working
    result.to_version = version
    return result


def parse_config_file(path: Path) -> dict[str, Any]:
    """Читает и разбирает JSON-файл конфигурации.

    Args:
        path: Путь к файлу конфигурации.

    Returns:
        Словарь с данными конфигурации.

    Raises:
        ValueError: Если файл не является корректным JSON-объектом.
        OSError: Если файл не читается.
    """
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError(
            "Конфигурация должна быть JSON-объектом, "
            f"получен {type(data).__name__}"
        )
    return data
