"""Storage-слой для загрузки и сохранения задач планировщика."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from logger_config import get_module_logger
from utils import atomic_write_json

logger = get_module_logger(__name__)


class TaskStorage:
    """Потокобезопасный I/O-слой хранения scheduler задач."""

    def __init__(self, persist_path: Path):
        self._persist_path = persist_path

    def load_tasks_payload(self) -> list[dict[str, Any]]:
        """Загружает tasks payload из файла хранения."""
        if not self._persist_path.exists():
            return []

        with self._persist_path.open(encoding="utf-8") as file:
            data = json.load(file)
        tasks = data.get("tasks", [])
        return tasks if isinstance(tasks, list) else []

    def save_tasks_payload(self, tasks: list[dict[str, Any]]) -> None:
        """Сохраняет tasks payload в файл через атомарную запись."""
        data = {
            "tasks": tasks,
            "last_updated": datetime.now().isoformat(),
        }
        atomic_write_json(self._persist_path, data)

    @property
    def persist_path(self) -> Path:
        """Возвращает путь файла хранения задач."""
        return self._persist_path
