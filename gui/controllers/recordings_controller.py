"""
Контроллер управления списком недавних записей и миниатюрами
============================================================

Отвечает за:
- отображение и фильтрацию списка недавних записей в GUI;
- асинхронную генерацию и обновление миниатюр видеофайлов;
- операции над файлами записей (открытие, показ в проводнике, удаление, копирование пути).
"""

from __future__ import annotations

import os
import platform
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QGuiApplication, QIcon
from PyQt6.QtWidgets import (
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QStatusBar,
    QStyle,
    QWidget,
)

from logger_config import get_module_logger, open_logs_folder
from recorder.utils import format_filesize, generate_thumbnail

if TYPE_CHECKING:
    from gui.controllers.settings_controller import SettingsController
    from gui.models.recording_state import RecordingState

logger = get_module_logger(__name__)


class RecordingsController:
    """Контроллер управления историей записей и миниатюрами."""

    def __init__(
        self,
        state: RecordingState,
        settings_controller: SettingsController,
        recordings_list: QListWidget,
        filter_input: QLineEdit,
        status_bar: QStatusBar | None = None,
        track_thread: Callable[[threading.Thread], threading.Thread]
        | None = None,
    ) -> None:
        self._state = state
        self._settings_controller = settings_controller
        self._recordings_list = recordings_list
        self._filter_input = filter_input
        self._status_bar = status_bar
        self._track_thread = track_thread or (lambda t: t)

    def refresh_recent_recordings(self) -> None:
        """Обновление списка недавних записей с учётом фильтра."""
        self._recordings_list.clear()
        filter_text = self.normalized_recordings_filter()
        for rec in self._state.recent_recordings:
            if not rec.path.exists():
                continue
            if not self.recording_matches_filter(
                rec.path.name, rec.date, filter_text
            ):
                continue
            item_text = (
                f"{rec.path.name} - {format_filesize(rec.size)} - {rec.date}"
            )
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, str(rec.path))

            thumbnail_path = generate_thumbnail(rec.path)
            if thumbnail_path:
                item.setIcon(QIcon(str(thumbnail_path)))
            else:
                item.setIcon(self.get_recorded_video_icon())

            self._recordings_list.addItem(item)

    def clear_recordings_filter(self) -> None:
        """Сброс фильтра списка недавних записей."""
        self._filter_input.setText("")
        self.refresh_recent_recordings()

    def normalized_recordings_filter(self) -> str:
        """Нормализация текста фильтра для сравнения."""
        return str(self._filter_input.text().strip().lower())

    @staticmethod
    def recording_matches_filter(
        filename: str, date_text: str, filter_text: str
    ) -> bool:
        """Проверка попадания записи под фильтр."""
        normalized_filter = filter_text.strip().lower()
        if not normalized_filter:
            return True
        haystack = f"{filename.lower()} {date_text.lower()}"
        return normalized_filter in haystack

    def open_recording(self, item: QListWidgetItem) -> None:
        """Открытие файла записи из элемента списка."""
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.open_file(str(path))

    def open_selected_recording(self) -> None:
        """Открытие выбранного файла записи."""
        item = self._recordings_list.currentItem()
        if item:
            self.open_recording(item)

    def open_latest_recording(self) -> None:
        """Открытие самой свежей записи из списка."""
        item = self._recordings_list.item(0)
        if item:
            self.open_recording(item)

    def clear_recent_recordings(self) -> None:
        """Очистка списка последних записей."""
        self._settings_controller.clear_recent_recordings()
        self.refresh_recent_recordings()
        if self._status_bar is not None:
            self._status_bar.showMessage(
                "Список последних записей очищен", 5000
            )

    def open_recording_folder(self) -> None:
        """Открытие папки с выбранной записью."""
        item = self._recordings_list.currentItem()
        if item:
            path = Path(item.data(Qt.ItemDataRole.UserRole))
            if path.parent.exists():
                self.open_folder(str(path.parent))

    def copy_selected_recording_path(self) -> None:
        """Копирование пути выбранной записи в буфер обмена."""
        item = self._recordings_list.currentItem()
        if not item:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return

        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(str(path))
        if self._status_bar is not None:
            self._status_bar.showMessage(
                "Путь записи скопирован в буфер обмена", 5000
            )

    def show_recordings_context_menu(
        self, pos: Any, parent_widget: QWidget
    ) -> None:
        """Контекстное меню по правому клику на записи в списке."""
        item = self._recordings_list.itemAt(pos)
        if item is None:
            return
        self._recordings_list.setCurrentItem(item)

        menu = QMenu(parent_widget)

        open_action = QAction("Открыть файл", menu)
        open_action.triggered.connect(self.open_selected_recording)
        menu.addAction(open_action)

        folder_action = QAction("Открыть папку", menu)
        folder_action.triggered.connect(self.open_recording_folder)
        menu.addAction(folder_action)

        menu.addSeparator()

        copy_action = QAction("Копировать путь", menu)
        copy_action.triggered.connect(self.copy_selected_recording_path)
        menu.addAction(copy_action)

        menu.exec(self._recordings_list.mapToGlobal(pos))

    def generate_thumbnail_for_recording(self, output_path: Path) -> None:
        """Генерировать миниатюру для новой записи в фоновом потоке."""
        t = threading.Thread(
            target=self._generate_thumbnail_worker,
            args=(output_path,),
            daemon=True,
        )
        self._track_thread(t)
        t.start()

    def _generate_thumbnail_worker(self, output_path: Path) -> None:
        """Фоновый worker для генерации миниатюры."""
        thumbnail_path = generate_thumbnail(output_path)
        if thumbnail_path:
            QTimer.singleShot(
                0,
                lambda: self._update_thumbnail_icon(
                    output_path, thumbnail_path
                ),
            )
        else:
            QTimer.singleShot(
                0, lambda: self._update_thumbnail_icon(output_path, None)
            )

    def _update_thumbnail_icon(
        self, output_path: Path, thumbnail_path: Path | None
    ) -> None:
        """Обновить иконку миниатюры для элемента списка записей."""
        for i in range(self._recordings_list.count()):
            item = self._recordings_list.item(i)
            if item is None:
                continue
            item_path = item.data(Qt.ItemDataRole.UserRole)
            if item_path is None:
                continue
            if Path(item_path) == output_path:
                if thumbnail_path:
                    item.setIcon(QIcon(str(thumbnail_path)))
                else:
                    item.setIcon(self.get_recorded_video_icon())
                break

    def get_recorded_video_icon(self) -> QIcon:
        """Получить placeholder иконку для записи без миниатюры."""
        style = self._recordings_list.style()
        if style is not None:
            return style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        return QIcon()

    def open_file(self, path: str) -> None:
        """Открытие файла с помощью системного приложения по умолчанию."""
        system = platform.system()
        if system == "Windows":
            os.startfile(path)  # type: ignore[attr-defined, unused-ignore]
        elif system == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])

    def open_folder(self, path: str) -> None:
        """Открытие папки в файловом менеджере."""
        system = platform.system()
        if system == "Windows":
            subprocess.run(["explorer", path])
        elif system == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])

    def open_application_logs(
        self, error_callback: Callable[[str], None] | None = None
    ) -> None:
        """Открыть папку логов приложения."""
        try:
            open_logs_folder()
        except Exception as error:
            logger.error("Не удалось открыть папку логов: %s", error)
            if error_callback:
                error_callback(f"Не удалось открыть папку логов: {error}")
            return
        if self._status_bar is not None:
            self._status_bar.showMessage(
                "Открыта папка логов приложения", 5000
            )
