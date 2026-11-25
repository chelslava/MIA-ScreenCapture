"""
Тесты маркера-состояния обновления и подтверждения запуска (#191)
=================================================================
"""

import json
from pathlib import Path

from core.updater.rollback import (
    UPDATE_ROLLBACK_FILENAME,
    UPDATE_STATE_FILENAME,
    UpdateState,
    confirm_pending_update,
    pop_rollback_notice,
    read_rollback_notice,
    read_update_state,
    write_update_state,
)


class TestUpdateStateMarkers:
    """Тесты чтения/записи маркеров обновления."""

    def test_roundtrip(self, tmp_path: Path) -> None:
        """Маркер записывается и читается без потерь."""
        state = UpdateState(
            version="2.1.0",
            backup_dir=str(tmp_path / "app.backup-1"),
            started_at="2026-11-25T12:00:00+00:00",
        )
        write_update_state(tmp_path, state)

        assert read_update_state(tmp_path) == state

    def test_missing_marker_returns_none(self, tmp_path: Path) -> None:
        """Отсутствие маркера — это не обновление (None)."""
        assert read_update_state(tmp_path) is None
        assert read_rollback_notice(tmp_path) is None

    def test_bom_tolerated(self, tmp_path: Path) -> None:
        """BOM от PowerShell 5.1 не ломает разбор маркера."""
        raw = json.dumps(
            {"version": "2.1.0", "backup_dir": "b", "started_at": ""}
        )
        (tmp_path / UPDATE_STATE_FILENAME).write_text(
            "\ufeff" + raw, encoding="utf-8"
        )

        state = read_update_state(tmp_path)
        assert state is not None
        assert state.version == "2.1.0"

    def test_corrupted_marker_returns_none(self, tmp_path: Path) -> None:
        """Битый JSON маркера трактуется как отсутствие обновления."""
        (tmp_path / UPDATE_STATE_FILENAME).write_text(
            "{битый", encoding="utf-8"
        )
        (tmp_path / UPDATE_ROLLBACK_FILENAME).write_text(
            "{битый", encoding="utf-8"
        )

        assert read_update_state(tmp_path) is None
        assert read_rollback_notice(tmp_path) is None


class TestConfirmPendingUpdate:
    """Тесты подтверждения обновления на старте приложения."""

    def test_confirm_removes_marker_and_backup(self, tmp_path: Path) -> None:
        """Подтверждение удаляет маркер и backup предыдущей версии."""
        backup = tmp_path / "app.backup-1"
        backup.mkdir()
        (backup / "main.py").write_text("# старая версия", encoding="utf-8")
        write_update_state(
            tmp_path, UpdateState(version="2.1.0", backup_dir=str(backup))
        )

        state = confirm_pending_update(tmp_path)

        assert state is not None
        assert state.version == "2.1.0"
        assert read_update_state(tmp_path) is None
        assert not backup.exists(), "backup чистится после подтверждения"

    def test_confirm_without_update_is_noop(self, tmp_path: Path) -> None:
        """Без маркера подтверждение ничего не делает."""
        assert confirm_pending_update(tmp_path) is None

    def test_confirm_tolerates_backup_removal_failure(
        self, tmp_path: Path
    ) -> None:
        """Невозможность удалить backup не рушит подтверждение."""
        backup = tmp_path / "app.backup-1"
        backup.mkdir()
        locked = backup / "locked.dll"
        locked.write_text("data", encoding="utf-8")
        write_update_state(
            tmp_path, UpdateState(version="2.1.0", backup_dir=str(backup))
        )

        # Windows блокирует удаление открытых файлов; мокаем rmtree
        import unittest.mock

        with unittest.mock.patch(
            "core.updater.rollback.shutil.rmtree",
            side_effect=PermissionError("занят"),
        ):
            state = confirm_pending_update(tmp_path)

        assert state is not None
        assert read_update_state(tmp_path) is None
        assert locked.exists()


class TestRollbackNotice:
    """Тесты маркера отката от установщика."""

    def test_pop_reads_and_clears(self, tmp_path: Path) -> None:
        """pop_rollback_notice читает причину и удаляет маркер."""
        (tmp_path / UPDATE_ROLLBACK_FILENAME).write_text(
            json.dumps(
                {
                    "reason": "распаковка: битый архив",
                    "version": "2.1.0",
                    "rolled_back_at": "2026-11-25T12:00:00Z",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        notice = pop_rollback_notice(tmp_path)
        assert notice is not None
        assert "битый архив" in notice["reason"]
        assert pop_rollback_notice(tmp_path) is None
        assert not (tmp_path / UPDATE_ROLLBACK_FILENAME).exists()
