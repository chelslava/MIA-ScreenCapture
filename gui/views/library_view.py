"""
Представление библиотеки записей (Issue #119).
==============================================

Компонент UI для просмотра, поиска, фильтрации и управления
медиазаписями (Grid/List виды, теги, превью, контекстное меню).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.library.manager import LibraryManager
from core.library.models import RecordingMetadata
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class LibraryCardWidget(QFrame):
    """Виджет карточки видеозаписи для режима Grid."""

    clicked = pyqtSignal(object)
    context_menu_requested = pyqtSignal(object, object)

    def __init__(
        self, item: RecordingMetadata, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.item = item
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(
            lambda pos: self.context_menu_requested.emit(
                self.item, self.mapToGlobal(pos)
            )
        )
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setFixedWidth(240)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Превью изображение
        self.thumb_label = QLabel()
        self.thumb_label.setFixedSize(228, 128)
        self.thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumb_label.setStyleSheet(
            "background-color: #1e1e1e; border-radius: 4px;"
        )

        if self.item.thumbnail_path and self.item.thumbnail_path.exists():
            pixmap = QPixmap(str(self.item.thumbnail_path)).scaled(
                228,
                128,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.thumb_label.setPixmap(pixmap)
        else:
            self.thumb_label.setText("🎬 Нет превью")
            self.thumb_label.setStyleSheet(
                "background-color: #2b2b2b; color: #888; border-radius: 4px;"
            )

        layout.addWidget(self.thumb_label)

        # Имя файла
        title_label = QLabel(self.item.filename)
        title_label.setStyleSheet("font-weight: bold; font-size: 11px;")
        title_label.setWordWrap(True)
        title_label.setMaximumHeight(34)
        layout.addWidget(title_label)

        # Метаинформация (длительность / размер)
        meta_label = QLabel(
            f"⏱ {self.item.duration_str}  •  💾 {self.item.size_mb_str}"
        )
        meta_label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(meta_label)

        # Теги
        if self.item.tags:
            tags_str = " ".join(f"#{t}" for t in self.item.tags[:3])
            tags_label = QLabel(tags_str)
            tags_label.setStyleSheet("color: #4a9eff; font-size: 10px;")
            layout.addWidget(tags_label)

    def mouseDoubleClickEvent(self, event: Any) -> None:
        self.clicked.emit(self.item)


class LibraryView(QWidget):
    """Основное представление библиотеки записей."""

    recording_opened = pyqtSignal(str)
    recording_deleted = pyqtSignal(str)

    def __init__(
        self,
        manager: LibraryManager | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._manager = manager or LibraryManager()
        self._view_mode = "grid"  # 'grid' или 'list'
        self._setup_ui()
        self.refresh()

    def set_manager(self, manager: LibraryManager) -> None:
        """Устанавливает экземпляр LibraryManager."""
        self._manager = manager
        self.refresh()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Панель управления и фильтрации
        controls_group = QGroupBox("Управление библиотекой")
        controls_layout = QHBoxLayout(controls_group)
        controls_layout.setContentsMargins(8, 8, 8, 8)
        controls_layout.setSpacing(8)

        # Поиск
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("🔍 Поиск по имени или тегам...")
        self.search_edit.textChanged.connect(self._on_filter_changed)
        controls_layout.addWidget(self.search_edit, stretch=2)

        # Фильтр тегов
        self.tag_combo = QComboBox()
        self.tag_combo.addItem("Все теги", None)
        self.tag_combo.currentIndexChanged.connect(self._on_filter_changed)
        controls_layout.addWidget(self.tag_combo, stretch=1)

        # Сортировка
        self.sort_combo = QComboBox()
        self.sort_combo.addItem("Сначала новые", ("date", True))
        self.sort_combo.addItem("Сначала старые", ("date", False))
        self.sort_combo.addItem("По длительности", ("duration", True))
        self.sort_combo.addItem("По размеру", ("size", True))
        self.sort_combo.addItem("По имени (А-Я)", ("name", False))
        self.sort_combo.currentIndexChanged.connect(self._on_filter_changed)
        controls_layout.addWidget(self.sort_combo, stretch=1)

        # Переключатель видов
        self.btn_grid = QPushButton("⊞ Сетка")
        self.btn_grid.setCheckable(True)
        self.btn_grid.setChecked(True)
        self.btn_grid.clicked.connect(lambda: self._set_view_mode("grid"))
        controls_layout.addWidget(self.btn_grid)

        self.btn_list = QPushButton("☰ Список")
        self.btn_list.setCheckable(True)
        self.btn_list.clicked.connect(lambda: self._set_view_mode("list"))
        controls_layout.addWidget(self.btn_list)

        # Кнопка обновить
        self.btn_refresh = QPushButton("🔄")
        self.btn_refresh.setToolTip("Обновить библиотеку")
        self.btn_refresh.clicked.connect(self.refresh)
        controls_layout.addWidget(self.btn_refresh)

        main_layout.addWidget(controls_group)

        # Контейнер для отображения (Grid vs List)
        # 1. Grid контейнер
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setSpacing(12)
        self.scroll_area.setWidget(self.grid_container)
        main_layout.addWidget(self.scroll_area, stretch=1)

        # 2. List таблица
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(7)
        self.table_widget.setHorizontalHeaderLabels(
            [
                "Имя файла",
                "Длительность",
                "Размер",
                "Разрешение",
                "Кодек",
                "Теги",
                "Дата создания",
            ]
        )
        header = self.table_widget.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_widget.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table_widget.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.table_widget.customContextMenuRequested.connect(
            self._on_table_context_menu
        )
        self.table_widget.doubleClicked.connect(self._on_table_double_clicked)
        self.table_widget.hide()
        main_layout.addWidget(self.table_widget, stretch=1)

    def _set_view_mode(self, mode: str) -> None:
        """Переключает режим отображения между сеткой и списком."""
        self._view_mode = mode
        if mode == "grid":
            self.btn_grid.setChecked(True)
            self.btn_list.setChecked(False)
            self.table_widget.hide()
            self.scroll_area.show()
        else:
            self.btn_grid.setChecked(False)
            self.btn_list.setChecked(True)
            self.scroll_area.hide()
            self.table_widget.show()
        self._render_items()

    def refresh(self) -> None:
        """Обновляет теги и перерисовывает элементы библиотеки."""
        # Обновление выпадающего списка тегов
        current_tag = self.tag_combo.currentData()
        self.tag_combo.blockSignals(True)
        self.tag_combo.clear()
        self.tag_combo.addItem("Все теги", None)
        all_tags = self._manager.get_all_tags()
        for t in all_tags:
            self.tag_combo.addItem(f"#{t}", t)
        if current_tag in all_tags:
            idx = self.tag_combo.findData(current_tag)
            if idx >= 0:
                self.tag_combo.setCurrentIndex(idx)
        self.tag_combo.blockSignals(False)

        self._render_items()

    def _on_filter_changed(self) -> None:
        self._render_items()

    def _render_items(self) -> None:
        """Отрисовывает элементы в активном режиме отображения."""
        query = self.search_edit.text()
        tag = self.tag_combo.currentData()
        sort_data = self.sort_combo.currentData()
        sort_by, sort_desc = sort_data if sort_data else ("date", True)

        items = self._manager.get_items(
            query=query,
            tag=tag,
            sort_by=sort_by,
            sort_desc=sort_desc,
        )

        if self._view_mode == "grid":
            self._render_grid(items)
        else:
            self._render_table(items)

    def _render_grid(self, items: list[RecordingMetadata]) -> None:
        """Заполняет сетку карточками."""
        # Очистка текущих элементов
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child is not None:
                w = child.widget()
                if w is not None:
                    w.deleteLater()

        columns = 3
        for idx, it in enumerate(items):
            card = LibraryCardWidget(it)
            card.clicked.connect(self._open_recording)
            card.context_menu_requested.connect(self._show_context_menu)
            row = idx // columns
            col = idx % columns
            self.grid_layout.addWidget(card, row, col)

        # Выравнивание по верхнему краю
        self.grid_layout.setRowStretch(len(items) // columns + 1, 1)

    def _render_table(self, items: list[RecordingMetadata]) -> None:
        """Заполняет таблицу записями."""
        self.table_widget.setRowCount(len(items))
        for row, it in enumerate(items):
            self.table_widget.setItem(row, 0, QTableWidgetItem(it.filename))
            self.table_widget.setItem(
                row, 1, QTableWidgetItem(it.duration_str)
            )
            self.table_widget.setItem(row, 2, QTableWidgetItem(it.size_mb_str))
            self.table_widget.setItem(
                row, 3, QTableWidgetItem(it.resolution_str)
            )
            self.table_widget.setItem(row, 4, QTableWidgetItem(it.codec))
            self.table_widget.setItem(
                row, 5, QTableWidgetItem(", ".join(it.tags))
            )
            self.table_widget.setItem(
                row, 6, QTableWidgetItem(it.created_at[:19].replace("T", " "))
            )
            # Сохраняем ссылку на объект метаданных в первом элементе
            cell = self.table_widget.item(row, 0)
            if cell is not None:
                cell.setData(Qt.ItemDataRole.UserRole, it)

    def _open_recording(self, item: RecordingMetadata) -> None:
        """Открывает видеозапись в системном проигрывателе."""
        if item.path.exists():
            try:
                os.startfile(str(item.path))
                self.recording_opened.emit(str(item.path))
            except Exception as e:
                logger.error(
                    "Не удалось открыть видеофайл %s: %s", item.path, e
                )

    def _on_table_double_clicked(self) -> None:
        current_row = self.table_widget.currentRow()
        if current_row >= 0:
            cell = self.table_widget.item(current_row, 0)
            if cell is not None:
                item_obj = cell.data(Qt.ItemDataRole.UserRole)
                if isinstance(item_obj, RecordingMetadata):
                    self._open_recording(item_obj)

    def _on_table_context_menu(self, pos: Any) -> None:
        current_row = self.table_widget.currentRow()
        if current_row >= 0:
            cell = self.table_widget.item(current_row, 0)
            if cell is not None:
                item_obj = cell.data(Qt.ItemDataRole.UserRole)
                if isinstance(item_obj, RecordingMetadata):
                    self._show_context_menu(
                        item_obj, self.table_widget.mapToGlobal(pos)
                    )

    def _show_context_menu(
        self, item: RecordingMetadata, global_pos: Any
    ) -> None:
        """Отображает контекстное меню быстрых действий для записи."""
        menu = QMenu(self)

        action_open = menu.addAction("▶ Воспроизвести")
        action_explore = menu.addAction("📁 Показать в проводнике")
        action_copy_path = menu.addAction("📋 Копировать путь")
        menu.addSeparator()
        action_add_tag = menu.addAction("🏷 Добавить тег...")
        if item.tags:
            action_remove_tag = menu.addAction("❌ Удалить тег...")
        else:
            action_remove_tag = None
        menu.addSeparator()
        action_delete = menu.addAction("🗑 Удалить запись...")

        chosen = menu.exec(global_pos)
        if chosen == action_open:
            self._open_recording(item)
        elif chosen == action_explore:
            self._reveal_in_explorer(item.path)
        elif chosen == action_copy_path:
            clipboard = QGuiApplication.clipboard()
            if clipboard:
                clipboard.setText(str(item.path))
        elif chosen == action_add_tag:
            self._prompt_add_tag(item)
        elif action_remove_tag and chosen == action_remove_tag:
            self._prompt_remove_tag(item)
        elif chosen == action_delete:
            self._confirm_delete(item)

    def _reveal_in_explorer(self, path: Path) -> None:
        """Открывает и выделяет файл в проводнике Windows."""
        if not path.exists():
            return
        try:
            subprocess.Popen(["explorer", f"/select,{path}"])
        except Exception as e:
            logger.error("Ошибка открытия проводника для %s: %s", path, e)

    def _prompt_add_tag(self, item: RecordingMetadata) -> None:
        """Диалог добавления тега."""
        tag, ok = QInputDialog.getText(
            self, "Добавить тег", f"Введите тег для '{item.filename}':"
        )
        if ok and tag.strip():
            self._manager.add_tag(item.path, tag.strip())
            self.refresh()

    def _prompt_remove_tag(self, item: RecordingMetadata) -> None:
        """Диалог удаления тега."""
        if not item.tags:
            return
        tag, ok = QInputDialog.getItem(
            self,
            "Удалить тег",
            "Выберите тег для удаления:",
            item.tags,
            0,
            False,
        )
        if ok and tag:
            self._manager.remove_tag(item.path, tag)
            self.refresh()

    def _confirm_delete(self, item: RecordingMetadata) -> None:
        """Диалог подтверждения удаления записи."""
        reply = QMessageBox.question(
            self,
            "Удаление записи",
            f"Вы уверены, что хотите удалить запись '{item.filename}' с диска?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._manager.delete_recording(item.path, delete_file=True)
            self.recording_deleted.emit(str(item.path))
            self.refresh()
