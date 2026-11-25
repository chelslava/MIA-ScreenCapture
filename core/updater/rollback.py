"""
Маркер-состояние обновления и подтверждение успешного апдейта (#191)
====================================================================

PowerShell-установщик перед запуском новой версии кладёт маркер
``update_state.json`` и держит backup предыдущей установки. Приложение,
успешно стартовав (прошли импорты, конфигурация, логирование), удаляет
маркер через :func:`confirm_pending_update` — это сигнал установщику,
что health-check пройден. Если маркер не исчез за отведённое время,
установщик откатывает установку на backup и пишет ``update_rollback.json``.

Инвариант issue #191: после прерванного обновления приложение
остаётся рабочим на предыдущей версии.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Final

from logger_config import get_module_logger

logger = get_module_logger(__name__)

#: Маркер «обновление применено, ожидается подтверждение запуска»
UPDATE_STATE_FILENAME: Final[str] = "update_state.json"
#: Маркер «установщик откатил установку на backup»
UPDATE_ROLLBACK_FILENAME: Final[str] = "update_rollback.json"


@dataclass
class UpdateState:
    """Содержимое маркера применённого обновления.

    Attributes:
        version: Версия, до которой обновились.
        backup_dir: Путь к backup предыдущей установки.
        started_at: UTC-метка применения обновления.
    """

    version: str
    backup_dir: str
    started_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _marker_path(app_root: Path, filename: str) -> Path:
    """Возвращает путь маркера внутри установки приложения."""
    return app_root / filename


def read_update_state(app_root: Path) -> UpdateState | None:
    """Читает маркер применённого обновления.

    Args:
        app_root: Корень установки приложения.

    Returns:
        :class:`UpdateState` или None, если маркера нет/он повреждён.
    """
    path = _marker_path(app_root, UPDATE_STATE_FILENAME)
    if not path.exists():
        return None
    try:
        # utf-8-sig: PowerShell 5.1 пишет UTF-8 с BOM даже при -Encoding utf8
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return UpdateState(
            version=str(data.get("version", "unknown")),
            backup_dir=str(data.get("backup_dir", "")),
            started_at=str(data.get("started_at", "")),
        )
    except Exception as e:
        logger.warning("Повреждён маркер обновления %s: %s", path, e)
        return None


def write_update_state(app_root: Path, state: UpdateState) -> Path:
    """Записывает маркер применённого обновления (для тестов/установщика).

    Args:
        app_root: Корень установки приложения.
        state: Состояние для записи.

    Returns:
        Путь записанного маркера.
    """
    path = _marker_path(app_root, UPDATE_STATE_FILENAME)
    path.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def read_rollback_notice(app_root: Path) -> dict[str, Any] | None:
    """Читает причину последнего отката (если установщик её оставил)."""
    path = _marker_path(app_root, UPDATE_ROLLBACK_FILENAME)
    if not path.exists():
        return None
    try:
        # utf-8-sig: толерантность к BOM от PowerShell 5.1
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else None
    except Exception as e:
        logger.warning("Повреждён маркер отката %s: %s", path, e)
        return None


def pop_rollback_notice(app_root: Path) -> dict[str, Any] | None:
    """Читает причину последнего отката и удаляет маркер.

    Returns:
        Словарь с reason/version/rolled_back_at или None.
    """
    notice = read_rollback_notice(app_root)
    if notice is not None:
        _marker_path(app_root, UPDATE_ROLLBACK_FILENAME).unlink(
            missing_ok=True
        )
    return notice


def confirm_pending_update(app_root: Path) -> UpdateState | None:
    """Подтверждает успешный запуск после обновления и чистит backup.

    Вызывается на старте приложения после успешной инициализации ядра:
    удаление маркера — сигнал health-check установщику об успехе;
    backup предыдущей версии больше не нужен и удаляется.

    Args:
        app_root: Корень установки приложения.

    Returns:
        Подтверждённый :class:`UpdateState` или None (обновления не было).
    """
    state = read_update_state(app_root)
    if state is None:
        return None

    _marker_path(app_root, UPDATE_STATE_FILENAME).unlink(missing_ok=True)
    logger.info(
        "Обновление до версии %s подтверждено успешным запуском", state.version
    )

    backup = Path(state.backup_dir) if state.backup_dir else None
    if backup is not None and backup.exists():
        try:
            shutil.rmtree(backup)
            logger.info("Backup предыдущей установки удалён: %s", backup)
        except Exception as e:
            # Удаление backup не критично: ротация выполнится перед
            # следующим обновлением
            logger.warning(
                "Не удалось удалить backup %s (будет удалён при "
                "следующем обновлении): %s",
                backup,
                e,
            )
    return state
