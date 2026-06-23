"""
Представление настроек внешнего вида
=====================================

Компонент UI для выбора темы оформления приложения.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QVBoxLayout,
    QWidget,
)

from gui.accessibility import apply_accessible_metadata
from logger_config import get_module_logger

logger = get_module_logger(__name__)

_THEME_MODES: tuple[tuple[str, str], ...] = (
    ("system", "Как в системе"),
    ("light", "Светлая"),
    ("dark", "Тёмная"),
)


class AppearanceView(QWidget):
    """
    Представление для настройки внешнего вида.

    Содержит:
    - Выбор темы оформления (системная/светлая/тёмная).
    """

    theme_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None):
        """
        Инициализация представления.

        Args:
            parent: Родительский виджет.
        """
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Настройка пользовательского интерфейса."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Внешний вид")
        group_layout = QVBoxLayout(group)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems([label for _, label in _THEME_MODES])
        self._theme_combo.currentIndexChanged.connect(
            self._on_theme_index_changed
        )
        group_layout.addWidget(self._theme_combo)

        self._apply_accessibility_metadata()
        layout.addWidget(group)

    def _apply_accessibility_metadata(self) -> None:
        """Назначение accessibility metadata для настроек внешнего вида."""
        apply_accessible_metadata(
            self._theme_combo,
            "Тема оформления",
            "Выбирает тему оформления приложения: системную, светлую или "
            "тёмную.",
            "Выберите тему оформления.",
        )

    def _on_theme_index_changed(self, index: int) -> None:
        """Обработка выбора пункта темы."""
        if index < 0 or index >= len(_THEME_MODES):
            return
        mode, _ = _THEME_MODES[index]
        self.theme_changed.emit(mode)

    def set_current_mode(self, mode: str) -> None:
        """
        Установить выбранный пункт темы без отправки сигнала.

        Args:
            mode: `"system"`, `"light"` или `"dark"`.
        """
        for index, (mode_value, _) in enumerate(_THEME_MODES):
            if mode_value == mode:
                self._theme_combo.setCurrentIndex(index)
                return

    def get_current_mode(self) -> str:
        """
        Получить текущий выбранный режим темы.

        Returns:
            `"system"`, `"light"` или `"dark"`.
        """
        index = self._theme_combo.currentIndex()
        if 0 <= index < len(_THEME_MODES):
            return _THEME_MODES[index][0]
        return "system"
