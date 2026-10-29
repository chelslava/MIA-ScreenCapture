"""
Список недавних записей с multi-select и drag-out (#160)
=========================================================

QListWidget с расширенным выделением (Ctrl/Shift+клик, Ctrl+A) и
перетаскиванием файлов в проводник / папку библиотеки: mime содержит
``text/uri-list``, поэтому копирование выполняет получатель — UI-поток
не блокируется даже на крупных файлах.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QMimeData, Qt, QUrl
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QWidget,
)


class RecordingsListWidget(QListWidget):
    """Список записей: ExtendedSelection + drag-out file URL'ов."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)

    def selected_file_paths(self) -> list[Path]:
        """Пути файлов всех выделенных элементов (с существующими путями)."""
        paths: list[Path] = []
        for item in self.selectedItems():
            raw = item.data(Qt.ItemDataRole.UserRole)
            if raw:
                paths.append(Path(str(raw)))
        return paths

    def mimeData(self, items: list[QListWidgetItem]) -> QMimeData:  # type: ignore[override]
        """Mime с uri-list выделенных записей для drag-out (#160)."""
        mime = super().mimeData(items) or QMimeData()
        urls = self._build_urls(items)
        if urls:
            mime.setUrls(urls)
        return mime

    @staticmethod
    def _build_urls(items: list[QListWidgetItem]) -> list[QUrl]:
        """File-URL'ы элементов с UserRole-путём (#160)."""
        urls: list[QUrl] = []
        for item in items:
            raw = item.data(Qt.ItemDataRole.UserRole)
            if raw:
                urls.append(QUrl.fromLocalFile(str(Path(str(raw)))))
        return urls
