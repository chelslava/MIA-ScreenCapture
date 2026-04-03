"""
Представление области захвата.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from gui.models.recording_state import CaptureType
from gui.views.area_selector import (
    AreaSelectorDialog,
    SelectionPreviewWidget,
    describe_rect,
    format_rect_coords,
)
from recorder.utils import get_available_windows, get_screen_size


class CaptureView(QWidget):
    """
    Представление для выбора области захвата.

    Содержит:
    - Радиокнопки для выбора типа области.
    - Селектор окон.
    - Графический выбор прямоугольной области.
    """

    capture_type_changed = pyqtSignal(CaptureType)
    window_selected = pyqtSignal(str)
    rect_selected = pyqtSignal(tuple)

    def __init__(self, parent: QWidget | None = None):
        """
        Инициализация представления.

        Args:
            parent: Родительский виджет.
        """
        super().__init__(parent)
        self._rect_coords: tuple[int, int, int, int] | None = None
        self._screen_size = get_screen_size()
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Настройка пользовательского интерфейса."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Область захвата")
        group_layout = QVBoxLayout(group)

        self._button_group = QButtonGroup()

        self._full_screen_radio = QRadioButton("Весь экран")
        self._full_screen_radio.setChecked(True)
        self._button_group.addButton(self._full_screen_radio, 0)
        group_layout.addWidget(self._full_screen_radio)

        self._window_radio = QRadioButton("Окно")
        self._button_group.addButton(self._window_radio, 1)
        group_layout.addWidget(self._window_radio)

        window_layout = QHBoxLayout()
        self._window_combo = QComboBox()
        self._window_combo.setMinimumWidth(200)
        self._refresh_windows()

        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self._refresh_windows)
        refresh_btn.setMaximumWidth(80)

        window_layout.addWidget(QLabel("Окно:"))
        window_layout.addWidget(self._window_combo)
        window_layout.addWidget(refresh_btn)
        group_layout.addLayout(window_layout)

        self._rect_radio = QRadioButton("Прямоугольник")
        self._button_group.addButton(self._rect_radio, 2)
        group_layout.addWidget(self._rect_radio)

        rect_layout = QHBoxLayout()
        self._rect_edit = QLineEdit()
        self._rect_edit.setPlaceholderText("Область не выбрана")
        self._rect_edit.setReadOnly(True)
        self._rect_edit.setEnabled(False)

        self._select_rect_btn = QPushButton("Выбрать")
        self._select_rect_btn.setMaximumWidth(90)
        self._select_rect_btn.clicked.connect(self._select_rectangle)

        rect_layout.addWidget(QLabel("Область:"))
        rect_layout.addWidget(self._rect_edit)
        rect_layout.addWidget(self._select_rect_btn)
        group_layout.addLayout(rect_layout)

        self._rect_summary_label = QLabel()
        self._rect_summary_label.setText("Область не выбрана")
        group_layout.addWidget(self._rect_summary_label)

        self._rect_preview = SelectionPreviewWidget()
        self._rect_preview.set_screen_size(*self._screen_size)
        group_layout.addWidget(self._rect_preview)

        self._button_group.buttonClicked.connect(self._on_button_clicked)
        self._window_combo.currentTextChanged.connect(self._on_window_changed)

        self._update_enabled_state()
        layout.addWidget(group)

    def _refresh_windows(self) -> None:
        """Обновление списка доступных окон."""
        self._window_combo.clear()
        windows = get_available_windows()

        for win in windows:
            self._window_combo.addItem(win["title"])

    def _select_rectangle(self) -> None:
        """Открыть overlay для графического выбора области."""
        coords = AreaSelectorDialog.select_area(
            self,
            initial_rect=self._rect_coords,
        )

        if coords is not None:
            self.set_rect_coords(coords)
            self.set_capture_type(CaptureType.RECT)
            self._on_button_clicked(self._rect_radio)
            self.rect_selected.emit(coords)

    def _on_button_clicked(self, button: QRadioButton) -> None:
        """Обработка клика по радиокнопке."""
        self._update_enabled_state()

        if button == self._full_screen_radio:
            capture_type = CaptureType.FULL
        elif button == self._window_radio:
            capture_type = CaptureType.WINDOW
        else:
            capture_type = CaptureType.RECT

        self.capture_type_changed.emit(capture_type)

    def _on_window_changed(self, window_title: str) -> None:
        """Обработка выбора окна."""
        self.window_selected.emit(window_title)

    def _update_enabled_state(self) -> None:
        """Обновление состояния элементов управления."""
        is_window = self._window_radio.isChecked()
        is_rect = self._rect_radio.isChecked()

        self._window_combo.setEnabled(is_window)
        self._rect_edit.setEnabled(is_rect)
        self._rect_summary_label.setEnabled(is_rect)
        self._rect_preview.setEnabled(is_rect)

    def get_capture_type(self) -> CaptureType:
        """
        Получить выбранный тип области захвата.

        Returns:
            Тип области захвата.
        """
        if self._rect_radio.isChecked():
            return CaptureType.RECT
        if self._window_radio.isChecked():
            return CaptureType.WINDOW
        return CaptureType.FULL

    def get_window_title(self) -> str:
        """
        Получить выбранный заголовок окна.

        Returns:
            Заголовок окна.
        """
        return self._window_combo.currentText()

    def get_rect_coords(self) -> tuple[int, int, int, int] | None:
        """
        Получить координаты прямоугольника.

        Returns:
            Кортеж `(x1, y1, x2, y2)` или `None`.
        """
        return self._rect_coords

    def set_capture_type(self, capture_type: CaptureType) -> None:
        """
        Установить тип области захвата.

        Args:
            capture_type: Тип области захвата.
        """
        self._full_screen_radio.setChecked(False)
        self._window_radio.setChecked(False)
        self._rect_radio.setChecked(False)
        if capture_type == CaptureType.FULL:
            self._full_screen_radio.setChecked(True)
        elif capture_type == CaptureType.WINDOW:
            self._window_radio.setChecked(True)
        else:
            self._rect_radio.setChecked(True)
        self._update_enabled_state()

    def set_window_title(self, title: str) -> None:
        """
        Установить выбранный заголовок окна.

        Args:
            title: Заголовок окна.
        """
        if hasattr(self._window_combo, "findText"):
            index = self._window_combo.findText(title)
        else:
            index = -1
            for current_index in range(self._window_combo.count()):
                if self._window_combo.itemText(current_index) == title:
                    index = current_index
                    break
        if index >= 0:
            self._window_combo.setCurrentIndex(index)

    def set_rect_coords(self, coords: tuple[int, int, int, int]) -> None:
        """
        Установить координаты прямоугольника.

        Args:
            coords: Кортеж `(x1, y1, x2, y2)`.
        """
        self._rect_coords = coords
        self._rect_edit.setText(format_rect_coords(coords))
        self._rect_summary_label.setText(describe_rect(coords))
        self._rect_preview.set_rect_coords(coords)
