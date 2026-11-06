"""Тесты LibraryView на моках PyQt6 (#186)."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from core.library.models import RecordingMetadata
from gui.views.library_view import LibraryView


def _make_manager() -> MagicMock:
    """Мок LibraryManager с пустой библиотекой."""
    manager = MagicMock()
    manager.get_all_tags.return_value = []
    manager.get_items.return_value = []
    manager.find_duplicate_groups.return_value = []
    return manager


def _make_view(manager: MagicMock | None = None) -> LibraryView:
    """LibraryView с моком менеджера."""
    return LibraryView(manager=manager or _make_manager())


def _make_item(path: Path, **kwargs: Any) -> RecordingMetadata:
    """Метаданные записи для тестов."""
    return RecordingMetadata(path=path, **kwargs)


class _FakeMenu:
    """QMenu-подоба: действия ключуются текстом, exec возвращает выбор."""

    instances: list["_FakeMenu"] = []
    chosen_text: str | None = None

    def __init__(self, _parent: Any = None) -> None:
        self.by_text: dict[str, Any] = {}
        _FakeMenu.instances.append(self)

    def addAction(self, action: Any) -> Any:
        self.by_text[str(action)] = action
        return action

    def addSeparator(self) -> None:
        pass

    def exec(self, _pos: Any) -> Any:
        menu = _FakeMenu.instances[-1]
        return menu.by_text.get(_FakeMenu.chosen_text)


class TestLibraryViewDetailsPanel:
    """Панель деталей выбранной записи (#186)."""

    def test_details_update_on_select(self, tmp_path: Path) -> None:
        """Выбор записи заполняет панель и включает кнопки."""
        view = _make_view()
        view._details_thumb = MagicMock()
        view._details_title = MagicMock()
        view._details_info = MagicMock()
        view._details_open_btn = MagicMock()
        view._details_rename_btn = MagicMock()

        item = _make_item(
            tmp_path / "clip.mp4",
            duration_sec=125.0,
            size_bytes=1024 * 1024,
            width=1920,
            height=1080,
            fps=60.0,
            codec="h264",
            audio_codec="aac",
        )
        view._update_details(item)

        view._details_title.setText.assert_called_once_with("clip.mp4")
        view._details_open_btn.setEnabled.assert_called_once_with(True)
        view._details_rename_btn.setEnabled.assert_called_once_with(True)
        assert view.selected_item is item

    def test_details_open_button_opens_recording(self, tmp_path: Path) -> None:
        """Кнопка «Открыть» открывает выбранную запись."""
        view = _make_view()
        item = _make_item(tmp_path / "clip.mp4")
        item.path.write_bytes(b"x")
        view._selected_item = item

        with patch("gui.views.library_view.os.startfile") as startfile:
            view._open_selected()

        startfile.assert_called_once_with(str(item.path))

    def test_details_reset_disables_buttons(self) -> None:
        """Сброс панели отключает кнопки действий."""
        view = _make_view()
        view._details_open_btn = MagicMock()
        view._details_rename_btn = MagicMock()

        view._reset_details()

        view._details_open_btn.setEnabled.assert_called_once_with(False)
        view._details_rename_btn.setEnabled.assert_called_once_with(False)


class TestLibraryViewRename:
    """Переименование записи из библиотеки (#186)."""

    def test_prompt_rename_calls_manager(self, tmp_path: Path) -> None:
        """Диалог переименования вызывает менеджер и обновляет вью."""
        manager = _make_manager()
        view = _make_view(manager)
        item = _make_item(tmp_path / "old.mp4")
        manager.rename_recording.return_value = tmp_path / "new.mp4"

        with (
            patch(
                "gui.views.library_view.QInputDialog.getText",
                return_value=("new", True),
            ),
            patch("gui.views.library_view.QMessageBox") as msgbox,
        ):
            view._prompt_rename(item)

        manager.rename_recording.assert_called_once_with(item.path, "new")
        msgbox.warning.assert_not_called()

    def test_prompt_rename_cancelled_is_noop(self, tmp_path: Path) -> None:
        """Отмена диалога не трогает менеджер."""
        manager = _make_manager()
        view = _make_view(manager)
        item = _make_item(tmp_path / "old.mp4")

        with patch(
            "gui.views.library_view.QInputDialog.getText",
            return_value=("new", False),
        ):
            view._prompt_rename(item)

        manager.rename_recording.assert_not_called()

    def test_prompt_rename_failure_shows_warning(self, tmp_path: Path) -> None:
        """Неудача менеджера показывает предупреждение."""
        manager = _make_manager()
        view = _make_view(manager)
        item = _make_item(tmp_path / "old.mp4")
        manager.rename_recording.return_value = None

        with (
            patch(
                "gui.views.library_view.QInputDialog.getText",
                return_value=("taken", True),
            ),
            patch("gui.views.library_view.QMessageBox") as msgbox,
        ):
            view._prompt_rename(item)

        msgbox.warning.assert_called_once()


class TestLibraryViewDuplicates:
    """Баннер и фильтр дубликатов (#186)."""

    def test_duplicates_toggle_filters_items(self, tmp_path: Path) -> None:
        """Режим «только дубликаты» фильтрует отрисовку."""
        manager = _make_manager()
        dup1 = _make_item(tmp_path / "dup.mp4", size_bytes=10)
        dup2 = _make_item(tmp_path / "dup_copy.mp4", size_bytes=10)
        unique = _make_item(tmp_path / "unique.mp4", size_bytes=5)
        manager.get_items.return_value = [dup1, dup2, unique]
        manager.find_duplicate_groups.return_value = [[dup1, dup2]]
        view = _make_view(manager)
        view._render_grid = MagicMock()

        view._toggle_duplicates_only()

        assert view._duplicates_only is True
        rendered = view._render_grid.call_args.args[0]
        assert [it.filename for it in rendered] == ["dup.mp4", "dup_copy.mp4"]

    def test_no_duplicates_banner_hidden(self) -> None:
        """Без дубликатов баннер скрыт и фильтр сброшен."""
        view = _make_view()
        view._duplicates_only = True
        view._dup_banner = MagicMock()

        view._update_duplicates_banner()

        view._dup_banner.hide.assert_called_once()
        assert view._duplicates_only is False


class TestLibraryViewMisc:
    """Прочее поведение LibraryView."""

    def test_set_manager_replaces_and_refreshes(self) -> None:
        """set_manager заменяет менеджер и обновляет данные."""
        view = _make_view()
        new_manager = _make_manager()

        view.set_manager(new_manager)

        assert view._manager is new_manager

    def test_context_menu_post_processing_emits_signal(
        self, tmp_path: Path
    ) -> None:
        """Пункт меню постобработки эмитит сигнал (#186)."""
        view = _make_view()
        item = _make_item(tmp_path / "clip.mp4", tags=["t"])
        received: list[str] = []
        view.post_processing_requested.connect(received.append)

        with (
            patch("gui.views.library_view.QMenu", _FakeMenu),
            patch("gui.views.library_view.QMessageBox"),
        ):
            _FakeMenu.instances = []
            _FakeMenu.chosen_text = "🧹 Добавить в постобработку"
            view._show_context_menu(item, None)

        assert received == [str(item.path)]

    def test_context_menu_delete_calls_manager(self, tmp_path: Path) -> None:
        """Пункт меню удаления удаляет запись через менеджер."""
        from PyQt6.QtWidgets import QMessageBox

        manager = _make_manager()
        view = _make_view(manager)
        item = _make_item(tmp_path / "clip.mp4")
        item.path.write_bytes(b"x")

        with (
            patch("gui.views.library_view.QMenu", _FakeMenu),
            patch(
                "gui.views.library_view.QMessageBox.question",
                return_value=QMessageBox.StandardButton.Yes,
            ),
        ):
            _FakeMenu.instances = []
            _FakeMenu.chosen_text = "🗑 Удалить запись..."
            view._show_context_menu(item, None)

        manager.delete_recording.assert_called_once_with(
            item.path, delete_file=True
        )
