"""Тесты storage-слоя scheduler задач."""

import json
from pathlib import Path

from scheduler.task_storage import TaskStorage


class TestTaskStorage:
    """Проверки загрузки и сохранения payload задач."""

    def test_save_and_load_tasks_payload(self, tmp_path: Path) -> None:
        """TaskStorage должен сохранять и загружать payload без потерь."""
        storage = TaskStorage(tmp_path / "tasks.json")
        payload = [{"id": "task-1", "name": "Task One"}]

        storage.save_tasks_payload(payload)
        loaded = storage.load_tasks_payload()

        assert loaded == payload

    def test_load_returns_empty_list_for_invalid_tasks_value(
        self, tmp_path: Path
    ) -> None:
        """Некорректное поле tasks должно нормализоваться в пустой список."""
        persist_path = tmp_path / "tasks.json"
        persist_path.write_text(
            json.dumps({"tasks": "invalid"}),
            encoding="utf-8",
        )
        storage = TaskStorage(persist_path)

        loaded = storage.load_tasks_payload()

        assert loaded == []
