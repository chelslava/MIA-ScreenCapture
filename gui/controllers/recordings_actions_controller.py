"""
Операции над записями в главном окне (#164)
===========================================

Миксин ``RecordingsActionsControllerMixin`` вынесен из
``gui/main_window.py``: открытие записей и папок, копирование пути,
контекстное меню списка, постобработка, перемещение и удаление
выделенных записей. ``MainWindow`` наследует миксин — методы
доступны как раньше.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QFileDialog,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QStatusBar,
)

from config import get_config
from gui.views.recordings_list import RecordingsListWidget

if TYPE_CHECKING:
    from core.application_facade import ApplicationFacade
    from gui.controllers.settings_controller import SettingsController


if TYPE_CHECKING:
    _QWindowBase = QMainWindow
else:
    # В рантайме миксин — обычный класс (без metaclass-конфликтов
    # с PyQt); QMainWindow приходит от MainWindow напрямую.
    _QWindowBase = object


class RecordingsActionsControllerMixin(_QWindowBase):
    """Действия пользователя над записями из списка последних."""

    if TYPE_CHECKING:
        # Общие атрибуты окна
        recordings_list: RecordingsListWidget
        _settings_controller: SettingsController
        _application_facade: ApplicationFacade | None
        status_bar: QStatusBar

        # Методы MainWindow
        _refresh_recent_recordings: Callable[[], None]
        _show_non_modal_error: Callable[[str], None]

    def _open_recording(self, item: QListWidgetItem) -> None:
        """Открытие файла записи."""
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self._open_file(str(path))

    def _open_selected_recording(self) -> None:
        """Открытие выбранного файла записи."""
        item = self.recordings_list.currentItem()
        if item:
            self._open_recording(item)

    def _open_latest_recording(self) -> None:
        """Открытие самой свежей записи из списка."""
        item = self.recordings_list.item(0)
        if item:
            self._open_recording(item)

    def _clear_recent_recordings(self) -> None:
        """Очистка списка последних записей."""
        self._settings_controller.clear_recent_recordings()
        self._refresh_recent_recordings()
        self.status_bar.showMessage("Список последних записей очищен", 5000)

    def _open_recording_folder(self) -> None:
        """Открытие папки с выбранной записью."""
        item = self.recordings_list.currentItem()
        if item:
            path = Path(item.data(Qt.ItemDataRole.UserRole))
            if path.parent.exists():
                self._open_folder(str(path.parent))

    def _copy_selected_recording_path(self) -> None:
        """Копирование пути выбранной записи в буфер обмена."""
        item = self.recordings_list.currentItem()
        if not item:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return

        from PyQt6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(str(path))
        self.status_bar.showMessage(
            "Путь записи скопирован в буфер обмена", 5000
        )

    def _selected_recording_paths(self) -> list[Path]:
        """Пути всех выделенных записей (multi-select, #160)."""
        widget = self.recordings_list
        if isinstance(widget, RecordingsListWidget):
            return widget.selected_file_paths()
        item = widget.currentItem()
        if item and item.data(Qt.ItemDataRole.UserRole):
            return [Path(str(item.data(Qt.ItemDataRole.UserRole)))]
        return []

    def _show_recordings_context_menu(self, pos: Any) -> None:
        """Контекстное меню по правому клику на записи в списке."""
        item = self.recordings_list.itemAt(pos)
        if item is None:
            return
        self.recordings_list.setCurrentItem(item)

        selected_paths = self._selected_recording_paths()
        count = len(selected_paths)
        count_suffix = f" ({count})" if count > 1 else ""

        menu = QMenu(self)

        open_action = QAction("Открыть файл", menu)
        open_action.triggered.connect(self._open_selected_recording)
        menu.addAction(open_action)

        folder_action = QAction("Открыть папку", menu)
        folder_action.triggered.connect(self._open_recording_folder)
        menu.addAction(folder_action)

        menu.addSeparator()

        copy_action = QAction(f"Копировать путь{count_suffix}", menu)
        copy_action.triggered.connect(self._copy_selected_recording_path)
        menu.addAction(copy_action)

        pp_action = QAction(f"Добавить в постобработку{count_suffix}", menu)
        pp_action.triggered.connect(self._post_process_selected_recordings)
        menu.addAction(pp_action)

        move_action = QAction(f"Переместить в папку…{count_suffix}", menu)
        move_action.triggered.connect(self._move_selected_recordings)
        menu.addAction(move_action)

        menu.addSeparator()

        delete_action = QAction(f"Удалить из списка…{count_suffix}", menu)
        delete_action.triggered.connect(self._delete_selected_recordings)
        menu.addAction(delete_action)

        menu.exec(self.recordings_list.mapToGlobal(pos))

    def _post_process_selected_recordings(self) -> None:
        """Постановка выделенных записей в очередь постобработки (#160)."""
        paths = self._selected_recording_paths()
        facade = self._application_facade
        if not paths or facade is None:
            return
        queued = 0
        for path in paths:
            result = facade.run_post_processing(str(path))
            if result.get("success"):
                queued += 1
        if queued:
            self.status_bar.showMessage(
                f"В постобработку добавлено файлов: {queued}", 5000
            )
        else:
            self._show_non_modal_error(
                "Не удалось добавить записи в постобработку "
                "(файлы не найдены или конвейер недоступен)"
            )

    def _move_selected_recordings(self) -> None:
        """Перемещение выделенных записей в выбранную папку (#160)."""
        paths = self._selected_recording_paths()
        if not paths:
            return

        dest_dir = QFileDialog.getExistingDirectory(
            self, "Выбрать папку для перемещения"
        )
        if not dest_dir:
            return

        moved = 0
        errors: list[str] = []
        for path in paths:
            try:
                if not path.exists():
                    errors.append(f"{path.name}: файл не найден")
                    continue
                shutil.move(str(path), str(Path(dest_dir) / path.name))
                moved += 1
            except (OSError, shutil.Error) as e:
                errors.append(f"{path.name}: {e}")

        if moved:
            self._refresh_recent_recordings()
        if errors:
            self._show_non_modal_error(
                f"Перемещено: {moved}; ошибки: " + "; ".join(errors[:3])
            )
        else:
            self.status_bar.showMessage(f"Перемещено файлов: {moved}", 5000)

    def _delete_selected_recordings(self) -> None:
        """Удаление выделенных записей из списка недавних (#160)."""
        paths = self._selected_recording_paths()
        if not paths:
            return

        reply = QMessageBox.question(
            self,
            "Удаление из списка",
            (
                f"Удалить записи из списка недавних ({len(paths)})?\n"
                "Файлы на диске не удаляются."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        removed = get_config().remove_recent_recordings(
            [str(p) for p in paths]
        )
        self._refresh_recent_recordings()
        self.status_bar.showMessage(
            f"Удалено из списка записей: {removed}", 5000
        )

    def _open_file(self, path: str) -> None:
        """Открытие файла с помощью системного приложения по умолчанию."""
        system = platform.system()
        if system == "Windows":
            # os.startfile is Windows-specific and not in type stubs
            os.startfile(path)  # type: ignore[attr-defined, unused-ignore]
        elif system == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])

    def _open_folder(self, path: str) -> None:
        """Открытие папки в файловом менеджере."""
        system = platform.system()
        if system == "Windows":
            subprocess.run(["explorer", path])
        elif system == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])
