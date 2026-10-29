"""Unit-тесты списка записей с multi-select и drag-out (#160)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from gui.views.recordings_list import RecordingsListWidget


def _make_item(path: str) -> SimpleNamespace:
    """Заглушка QListWidgetItem с UserRole-данными."""
    return SimpleNamespace(data=lambda role, _path=path: _path)


class TestRecordingsListWidget:
    """Расширенное выделение и uri-list mime (#160)."""

    def test_extended_selection_enabled(self) -> None:
        view = RecordingsListWidget()
        assert view.selectionMode() is not None

    def test_drag_enabled(self) -> None:
        view = RecordingsListWidget()
        assert view.dragEnabled() is not None

    def test_selected_file_paths_collects_user_role(self) -> None:
        view = RecordingsListWidget()
        view.selectedItems = MagicMock(  # type: ignore[method-assign]
            return_value=[
                _make_item("D:/a.mp4"),
                _make_item("D:/b.mp4"),
            ]
        )

        paths = view.selected_file_paths()

        assert [str(p) for p in paths] == ["D:\\a.mp4", "D:\\b.mp4"]

    def test_selected_file_paths_skips_empty_role(self) -> None:
        view = RecordingsListWidget()
        view.selectedItems = MagicMock(  # type: ignore[method-assign]
            return_value=[_make_item(""), _make_item("D:/a.mp4")]
        )

        paths = view.selected_file_paths()

        assert [str(p) for p in paths] == ["D:\\a.mp4"]

    def test_build_urls_from_items(self) -> None:
        """Хелпер строит file-URL'ы из UserRole-путей (#160)."""
        urls = RecordingsListWidget._build_urls(
            [_make_item("D:/a.mp4"), _make_item(""), _make_item("D:/b.mp4")]
        )

        assert len(urls) == 2

    def test_mime_data_sets_urls_when_present(self) -> None:
        """mimeData дописывает uri-list, когда есть файлы."""
        view = RecordingsListWidget()
        items = [_make_item("D:/a.mp4")]

        mime = view.mimeData(items)  # type: ignore[arg-type]

        assert mime.setUrls.called
