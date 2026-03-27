"""
Представление настроек вывода
=============================

Компонент UI для настройки пути вывода.
"""

from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.models.recording_state import OutputSettings
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class OutputView(QWidget):
    """
    Представление для настройки вывода.

    Содержит:
    - Поле ввода пути к выходному файлу
    - Кнопку выбора файла через диалог
    """

    # Сигналы
    output_path_changed = pyqtSignal(str)
    browse_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        """
        Инициализация представления.

        Args:
            parent: Родительский виджет
        """
        super().__init__(parent)
        self._default_format = "mp4"
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Настройка пользовательского интерфейса."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Вывод")
        group_layout = QHBoxLayout(group)

        group_layout.addWidget(QLabel("Сохранить в:"))
        self._output_edit = QLineEdit()
        self._output_edit.textChanged.connect(self._on_output_changed)
        group_layout.addWidget(self._output_edit)

        browse_btn = QPushButton("Обзор")
        browse_btn.clicked.connect(self._browse_output)
        group_layout.addWidget(browse_btn)

        layout.addWidget(group)

    def _browse_output(self) -> None:
        """Выбор места сохранения выходного файла."""
        default_name = f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{self._default_format}"

        # Определяем начальный путь для диалога
        current_text = self._output_edit.text()
        if current_text:
            current_path = Path(current_text)
            # Если указан существующий файл, используем его директорию
            if current_path.is_file():
                initial_path = str(current_path.parent / default_name)
            # Если указана директория, добавляем имя файла
            elif current_path.is_dir():
                initial_path = str(current_path / default_name)
            # Иначе считаем что это путь к файлу
            else:
                initial_path = current_text
        else:
            initial_path = default_name

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить запись",
            initial_path,
            "MP4 файлы (*.mp4);;AVI файлы (*.avi);;MKV файлы (*.mkv);;Все файлы (*)",
        )

        if file_path:
            self._output_edit.setText(file_path)
            self.browse_requested.emit()

    def _on_output_changed(self, text: str) -> None:
        """Обработка изменения пути вывода."""
        self.output_path_changed.emit(text)

    def get_output_path(self) -> str:
        """
        Получить путь к выходному файлу.

        Returns:
            Путь к выходному файлу
        """
        return self._output_edit.text()

    def get_output_path_as_path(self) -> Path:
        """
        Получить путь к выходному файлу как Path.

        Returns:
            Путь к выходному файлу
        """
        return (
            Path(self._output_edit.text())
            if self._output_edit.text()
            else Path()
        )

    def set_output_path(self, path: str) -> None:
        """
        Установить путь к выходному файлу.

        Args:
            path: Путь к выходному файлу
        """
        self._output_edit.setText(path)

    def set_default_format(self, format: str) -> None:
        """
        Установить формат файла по умолчанию.

        Args:
            format: Формат файла (mp4, avi, mkv)
        """
        self._default_format = format

    def get_settings(self) -> OutputSettings:
        """
        Получить текущие настройки вывода.

        Returns:
            Объект OutputSettings
        """
        return OutputSettings(output_path=self._output_edit.text())

    def set_settings(self, settings: OutputSettings) -> None:
        """
        Установить настройки вывода.

        Args:
            settings: Объект OutputSettings
        """
        if settings.default_path:
            self._output_edit.setText(settings.default_path)
