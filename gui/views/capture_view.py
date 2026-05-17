"""
Представление области захвата.
"""

import threading

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

from gui.accessibility import apply_accessible_metadata
from gui.models.recording_state import CaptureType
from gui.styles.theme import Theme
from gui.views.area_selector import (
    AreaSelectorDialog,
    SelectionPreviewWidget,
    describe_rect,
    format_rect_coords,
)
from recorder.utils import get_available_windows, get_screen_size

_WINDOWS_LOADING_TEXT = "Загрузка списка окон..."
_WINDOWS_EMPTY_TEXT = "Окна для захвата не найдены."


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
    windows_load_completed = pyqtSignal(int, object, object)

    def __init__(self, parent: QWidget | None = None):
        """
        Инициализация представления.

        Args:
            parent: Родительский виджет.
        """
        super().__init__(parent)
        self._rect_coords: tuple[int, int, int, int] | None = None
        self._screen_size = get_screen_size()
        self._window_request_id = 0
        self._pending_window_title = ""
        self._window_provider = get_available_windows
        self.windows_load_completed.connect(self._on_windows_load_completed)
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
        self._window_combo.setEnabled(False)

        self._refresh_windows_btn = QPushButton("Обновить")
        self._refresh_windows_btn.clicked.connect(self._refresh_windows)
        self._refresh_windows_btn.setMaximumWidth(80)

        window_layout.addWidget(QLabel("Окно:"))
        window_layout.addWidget(self._window_combo)
        window_layout.addWidget(self._refresh_windows_btn)
        group_layout.addLayout(window_layout)

        self._window_status_label = QLabel(_WINDOWS_LOADING_TEXT)
        Theme.apply_style(
            self._window_status_label,
            Theme.secondary_text_style(),
        )
        group_layout.addWidget(self._window_status_label)

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

        self._apply_accessibility_metadata()
        self._update_enabled_state()
        self._refresh_windows()
        layout.addWidget(group)

    def _apply_accessibility_metadata(self) -> None:
        """Назначение accessibility metadata для controls захвата."""
        apply_accessible_metadata(
            self._full_screen_radio,
            "Захват всего экрана",
            "Выбирает режим записи всего экрана.",
        )
        apply_accessible_metadata(
            self._window_radio,
            "Захват окна",
            "Выбирает режим записи отдельного окна.",
        )
        apply_accessible_metadata(
            self._window_combo,
            "Список доступных окон",
            "Позволяет выбрать окно для записи в режиме window capture.",
            "Выберите окно из списка.",
        )
        apply_accessible_metadata(
            self._refresh_windows_btn,
            "Обновить список окон",
            "Перечитывает список доступных окон для захвата.",
            "Обновляет список окон.",
        )
        apply_accessible_metadata(
            self._window_status_label,
            "Статус загрузки окон",
            "Показывает загрузку, ошибки и доступность списка окон.",
        )
        apply_accessible_metadata(
            self._rect_radio,
            "Захват прямоугольной области",
            "Выбирает режим записи прямоугольной области экрана.",
        )
        apply_accessible_metadata(
            self._rect_edit,
            "Координаты области захвата",
            "Показывает выбранные координаты прямоугольной области.",
        )
        apply_accessible_metadata(
            self._select_rect_btn,
            "Выбрать область захвата",
            "Открывает инструмент выбора прямоугольной области.",
            "Открывает выбор области захвата.",
        )
        apply_accessible_metadata(
            self._rect_summary_label,
            "Сводка по области захвата",
            "Показывает краткое описание выбранной прямоугольной области.",
        )

    def _refresh_windows(self) -> None:
        """Обновление списка доступных окон."""
        self._window_request_id += 1
        request_id = self._window_request_id
        self._set_windows_loading_state()
        threading.Thread(
            target=self._load_windows_worker,
            args=(request_id,),
            daemon=True,
        ).start()

    def _load_windows_worker(self, request_id: int) -> None:
        """Загрузить список окон в фоне и вернуть результат в UI."""
        try:
            windows = self._window_provider()
            self.windows_load_completed.emit(request_id, windows, None)
        except Exception as error:
            self.windows_load_completed.emit(request_id, None, str(error))

    def _on_windows_load_completed(
        self,
        request_id: int,
        windows: object,
        error: object,
    ) -> None:
        """Применить результат фоновой загрузки списка окон."""
        if request_id != self._window_request_id:
            return

        if error is not None:
            self._set_windows_error_state(str(error))
            return

        window_list = [
            item.get("title", "")
            for item in (windows if isinstance(windows, list) else [])
            if isinstance(item, dict) and item.get("title")
        ]

        current_title = self.get_window_title()
        self._window_combo.clear()
        for title in window_list:
            self._window_combo.addItem(title)

        if not window_list:
            self._pending_window_title = current_title
            self._set_windows_empty_state()
            return

        self._set_windows_ready_state(len(window_list))
        restored = self._restore_window_title(current_title)
        if not restored and hasattr(self._window_combo, "setCurrentIndex"):
            self._window_combo.setCurrentIndex(0)
        self._update_enabled_state()

    def _restore_window_title(self, title: str) -> bool:
        """Восстановить выбранный заголовок окна после refresh."""
        target_title = title or self._pending_window_title
        if not target_title:
            return False

        index = self._window_combo.findText(target_title)
        if index < 0:
            return False

        self._window_combo.setCurrentIndex(index)
        self._pending_window_title = ""
        return True

    def _set_windows_loading_state(self) -> None:
        """Показать состояние загрузки списка окон."""
        self._window_status_label.setText(_WINDOWS_LOADING_TEXT)
        Theme.apply_style(
            self._window_status_label,
            Theme.secondary_text_style(),
        )
        self._window_combo.setEnabled(False)

    def _set_windows_empty_state(self) -> None:
        """Показать состояние отсутствия доступных окон."""
        self._window_status_label.setText(_WINDOWS_EMPTY_TEXT)
        Theme.apply_style(
            self._window_status_label,
            f"color: {Theme.COLORS['warning']};",
        )
        self._window_combo.setEnabled(False)

    def _set_windows_error_state(self, message: str) -> None:
        """Показать ошибку загрузки списка окон."""
        self._window_status_label.setText(
            f"Не удалось загрузить окна: {message}"
        )
        Theme.apply_style(
            self._window_status_label,
            f"color: {Theme.COLORS['danger']};",
        )
        self._window_combo.setEnabled(False)

    def _set_windows_ready_state(self, count: int) -> None:
        """Показать успешную загрузку списка окон."""
        self._window_status_label.setText(f"Доступно окон: {count}")
        Theme.apply_style(
            self._window_status_label,
            Theme.secondary_text_style(),
        )

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

        self._window_combo.setEnabled(
            is_window and self._window_combo.count() > 0
        )
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
        current_title = self._window_combo.currentText()
        if current_title:
            return str(current_title)
        return str(self._pending_window_title)

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
        self._pending_window_title = title
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
            self._pending_window_title = ""

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

    def refresh_windows(self) -> None:
        """Публичный метод обновления списка доступных окон."""
        self._refresh_windows()

    def focus_window_combo(self) -> None:
        """Установить фокус на комбобокс выбора окна."""
        if hasattr(self, "_window_combo"):
            self._window_combo.setFocus()
