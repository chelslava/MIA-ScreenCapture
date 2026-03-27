"""
Представление области захвата
=============================

Компонент UI для выбора области захвата экрана.
"""


from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from gui.models.recording_state import CaptureType
from logger_config import get_module_logger
from recorder.utils import get_available_windows, get_screen_size

logger = get_module_logger(__name__)


class CaptureView(QWidget):
    """
    Представление для выбора области захвата.

    Содержит:
    - Радиокнопки для выбора типа области
    - Селектор окон
    - Поле ввода координат прямоугольника
    """

    # Сигналы
    capture_type_changed = pyqtSignal(CaptureType)
    window_selected = pyqtSignal(str)
    rect_selected = pyqtSignal(tuple)  # (x1, y1, x2, y2)

    def __init__(self, parent: QWidget | None = None):
        """
        Инициализация представления.

        Args:
            parent: Родительский виджет
        """
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Настройка пользовательского интерфейса."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Область захвата")
        group_layout = QVBoxLayout(group)

        # Радиокнопки
        self._button_group = QButtonGroup()

        self._full_screen_radio = QRadioButton("Весь экран")
        self._full_screen_radio.setChecked(True)
        self._button_group.addButton(self._full_screen_radio, 0)
        group_layout.addWidget(self._full_screen_radio)

        self._window_radio = QRadioButton("Окно")
        self._button_group.addButton(self._window_radio, 1)
        group_layout.addWidget(self._window_radio)

        # Селектор окон
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

        # Координаты прямоугольника
        rect_layout = QHBoxLayout()
        self._rect_edit = QLineEdit()
        self._rect_edit.setPlaceholderText("X1, Y1, X2, Y2")
        self._rect_edit.setEnabled(False)

        select_rect_btn = QPushButton("Выбрать")
        select_rect_btn.setMaximumWidth(80)
        select_rect_btn.clicked.connect(self._select_rectangle)

        rect_layout.addWidget(QLabel("Координаты:"))
        rect_layout.addWidget(self._rect_edit)
        rect_layout.addWidget(select_rect_btn)
        group_layout.addLayout(rect_layout)

        # Подключение сигналов
        self._button_group.buttonClicked.connect(self._on_button_clicked)
        self._window_combo.currentTextChanged.connect(self._on_window_changed)

        # Начальное состояние
        self._update_enabled_state()

        layout.addWidget(group)

    def _refresh_windows(self) -> None:
        """Обновление списка доступных окон."""
        self._window_combo.clear()
        windows = get_available_windows()

        for win in windows:
            self._window_combo.addItem(win["title"])

    def _select_rectangle(self) -> None:
        """Открытие диалога для выбора прямоугольника."""
        screen_width, screen_height = get_screen_size()

        text, ok = QInputDialog.getText(
            self,
            "Выбор области",
            "Введите координаты (x1, y1, x2, y2):",
            QLineEdit.EchoMode.Normal,
            f"0, 0, {screen_width}, {screen_height}",
        )

        if ok:
            self._rect_edit.setText(text)
            self._rect_radio.setChecked(True)
            self._on_button_clicked(self._rect_radio)

    def _on_button_clicked(self, button: QRadioButton) -> None:
        """Обработка клика по радиокнопке."""
        self._update_enabled_state()

        # Определение типа захвата
        if button == self._full_screen_radio:
            capture_type = CaptureType.FULL_SCREEN
        elif button == self._window_radio:
            capture_type = CaptureType.WINDOW
        else:
            capture_type = CaptureType.RECTANGLE

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

    def get_capture_type(self) -> CaptureType:
        """
        Получить выбранный тип области захвата.

        Returns:
            Тип области захвата
        """
        if self._full_screen_radio.isChecked():
            return CaptureType.FULL_SCREEN
        elif self._window_radio.isChecked():
            return CaptureType.WINDOW
        else:
            return CaptureType.RECTANGLE

    def get_window_title(self) -> str:
        """
        Получить выбранный заголовок окна.

        Returns:
            Заголовок окна
        """
        return self._window_combo.currentText()

    def get_rect_coords(self) -> tuple[int, int, int, int] | None:
        """
        Получить координаты прямоугольника.

        Returns:
            Кортеж (x1, y1, x2, y2) или None при ошибке
        """
        coords_text = self._rect_edit.text()
        try:
            coords = [int(x.strip()) for x in coords_text.split(",")]
            if len(coords) == 4:
                return (coords[0], coords[1], coords[2], coords[3])
        except ValueError:
            pass
        return None

    def set_capture_type(self, capture_type: CaptureType) -> None:
        """
        Установить тип области захвата.

        Args:
            capture_type: Тип области захвата
        """
        if capture_type == CaptureType.FULL_SCREEN:
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
            title: Заголовок окна
        """
        index = self._window_combo.findText(title)
        if index >= 0:
            self._window_combo.setCurrentIndex(index)

    def set_rect_coords(self, coords: tuple[int, int, int, int]) -> None:
        """
        Установить координаты прямоугольника.

        Args:
            coords: Кортеж (x1, y1, x2, y2)
        """
        self._rect_edit.setText(
            f"{coords[0]}, {coords[1]}, {coords[2]}, {coords[3]}"
        )
