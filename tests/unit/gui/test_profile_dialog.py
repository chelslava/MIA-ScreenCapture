"""
Unit-тесты для диалога управления профилями (gui/views/profile_dialog.py)
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PyQt6.QtWidgets import QApplication

from core.profiles import ProfileStorage
from gui.views.profile_dialog import ProfileDialog


@pytest.fixture
def mock_storage(tmp_path: Path) -> ProfileStorage:
    """Создает изолированное хранилище профилей."""
    storage_file = tmp_path / "profiles.json"
    return ProfileStorage(storage_path=storage_file)


class TestProfileDialog:
    """Тесты диалога ProfileDialog."""

    def test_init_populates_list(
        self, qapp: QApplication, mock_storage: ProfileStorage
    ) -> None:
        dialog = ProfileDialog(storage=mock_storage)
        assert dialog._profile_list.count() >= 3
        assert dialog._current_profile_id is not None

    def test_select_profile_populates_form(
        self, qapp: QApplication, mock_storage: ProfileStorage
    ) -> None:
        dialog = ProfileDialog(storage=mock_storage)
        # Выбираем профиль "gaming"
        for i in range(dialog._profile_list.count()):
            item = dialog._profile_list.item(i)
            if item.data(1) == "gaming" or "Игровой" in item.text():
                dialog._profile_list.setCurrentRow(i)
                break

        assert dialog._edit_name.text() == "Игровой"
        assert dialog._combo_fps.currentText() == "60"
        assert dialog._combo_bitrate.currentText() == "8M"

    def test_create_new_profile(
        self, qapp: QApplication, mock_storage: ProfileStorage
    ) -> None:
        dialog = ProfileDialog(storage=mock_storage)
        initial_count = dialog._profile_list.count()

        dialog._create_new_profile()
        assert dialog._profile_list.count() == initial_count + 1
        assert dialog._edit_name.text() == "Новый профиль"

    def test_duplicate_profile(
        self, qapp: QApplication, mock_storage: ProfileStorage
    ) -> None:
        dialog = ProfileDialog(storage=mock_storage)
        dialog._current_profile_id = "gaming"
        dialog._duplicate_selected_profile()

        names = [
            mock_storage.get_profile(p.id).name
            for p in mock_storage.list_profiles()
        ]
        assert any("Игровой (Копия)" in n for n in names)

    def test_save_current_profile(
        self, qapp: QApplication, mock_storage: ProfileStorage
    ) -> None:
        dialog = ProfileDialog(storage=mock_storage)
        custom_prof = mock_storage.create_profile(name="Тестовый")
        dialog._current_profile_id = custom_prof.id
        dialog._load_profiles_list()

        dialog._edit_name.setText("Измененное имя")
        dialog._edit_desc.setText("Новое описание")
        dialog._combo_fps.setCurrentText("120")

        with patch("PyQt6.QtWidgets.QMessageBox.information"):
            dialog._save_current_profile()

        saved = mock_storage.get_profile(custom_prof.id)
        assert saved is not None
        assert saved.name == "Измененное имя"
        assert saved.description == "Новое описание"
        assert saved.video.fps == 120

    def test_set_default(
        self, qapp: QApplication, mock_storage: ProfileStorage
    ) -> None:
        dialog = ProfileDialog(storage=mock_storage)
        custom_prof = mock_storage.create_profile(name="Будущий дефолт")
        dialog._current_profile_id = custom_prof.id

        dialog._set_selected_default()
        assert mock_storage.get_default_profile().id == custom_prof.id

    def test_delete_profile(
        self, qapp: QApplication, mock_storage: ProfileStorage
    ) -> None:
        dialog = ProfileDialog(storage=mock_storage)
        custom_prof = mock_storage.create_profile(name="Удаляемый")
        dialog._current_profile_id = custom_prof.id

        from PyQt6.QtWidgets import QMessageBox

        with patch(
            "PyQt6.QtWidgets.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            dialog._delete_selected_profile()

        assert mock_storage.get_profile(custom_prof.id) is None

    def test_apply_current_profile(
        self, qapp: QApplication, mock_storage: ProfileStorage
    ) -> None:
        dialog = ProfileDialog(storage=mock_storage)
        dialog._current_profile_id = "gaming"

        received: list[str] = []
        dialog.profile_applied.connect(received.append)

        with patch("PyQt6.QtWidgets.QMessageBox.information"):
            dialog._apply_current_profile()

        assert "gaming" in received
