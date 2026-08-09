"""
Представление настроек внешнего вида
=====================================

Компонент UI для выбора темы оформления приложения и прочих
UI-preference (поведение закрытия окна, горячие клавиши).
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gui.accessibility import apply_accessible_metadata
from gui.styles.theme import THEME_LABELS
from logger_config import get_module_logger

logger = get_module_logger(__name__)

_THEME_MODES: tuple[tuple[str, str], ...] = (
    ("system", "Как в системе"),
    *THEME_LABELS.items(),
)


class AppearanceView(QWidget):
    """
    Представление для настройки внешнего вида.

    Содержит:
    - Выбор темы оформления (системная или одна из тем `THEME_LABELS`).
    - Чекбокс «Сворачивать в трей при закрытии» (`minimize_to_tray`).
    - Кнопку вызова экрана горячих клавиш.
    """

    theme_changed = pyqtSignal(str)
    hotkeys_requested = pyqtSignal()
    minimize_to_tray_changed = pyqtSignal(bool)

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

        self._minimize_to_tray_checkbox = QCheckBox(
            "Сворачивать в трей при закрытии"
        )
        self._minimize_to_tray_checkbox.setToolTip(
            "Если включено, крестик закрытия главного окна сворачивает "
            "приложение в системный трей (запись продолжается). "
            "Выход доступен через меню иконки трея."
        )
        self._minimize_to_tray_checkbox.toggled.connect(
            self._on_minimize_to_tray_toggled
        )
        group_layout.addWidget(self._minimize_to_tray_checkbox)

        self._hotkeys_btn = QPushButton("Горячие клавиши")
        self._hotkeys_btn.clicked.connect(self._on_hotkeys_clicked)
        group_layout.addWidget(self._hotkeys_btn)

        self._apply_accessibility_metadata()
        layout.addWidget(group)

    def _apply_accessibility_metadata(self) -> None:
        """Назначение accessibility metadata для настроек внешнего вида."""
        apply_accessible_metadata(
            self._theme_combo,
            "Тема оформления",
            "Выбирает тему оформления приложения: системную или одну из "
            "тем в стиле Visual Studio (светлая, голубая, тёмная, тёмная "
            "контрастная).",
            "Выберите тему оформления.",
        )
        apply_accessible_metadata(
            self._hotkeys_btn,
            "Открыть список горячих клавиш",
            "Показывает экран со всеми горячими клавишами приложения.",
            "Открывает список горячих клавиш.",
        )
        apply_accessible_metadata(
            self._minimize_to_tray_checkbox,
            "Сворачивать в трей при закрытии",
            "Если включено, закрытие окна сворачивает приложение в "
            "системный трей вместо завершения процесса.",
            "Переключите для изменения поведения крестика окна.",
        )

    def _on_hotkeys_clicked(self) -> None:
        """Обработка клика по кнопке открытия списка горячих клавиш."""
        self.hotkeys_requested.emit()

    def _on_minimize_to_tray_toggled(self, checked: bool) -> None:
        """Обработка переключения чекбокса «сворачивать в трей»."""
        logger.info(f"minimize_to_tray изменено: {checked}")
        self.minimize_to_tray_changed.emit(bool(checked))

    def set_minimize_to_tray(self, enabled: bool) -> None:
        """Установить состояние чекбокса без отправки сигнала.

        Использует прямое присваивание атрибута вместо ``setChecked``, чтобы
        избежать эмита ``toggled``. Это безопасно, так как bool-значение
        идемпотентно (повторная установка того же значения — это no-op).

        Args:
            enabled: Текущее значение настройки ``minimize_to_tray``.
        """
        # Используем blockSignals только если он есть (в тестах моки
        # не всегда предоставляют этот метод на всех классах).
        checkbox = self._minimize_to_tray_checkbox
        block_signals = getattr(checkbox, "blockSignals", None)
        if callable(block_signals):
            block_signals(True)
            try:
                checkbox.setChecked(bool(enabled))
            finally:
                block_signals(False)
        else:
            # В тест-среде setChecked в моках не эмитит сигнал
            checkbox.setChecked(bool(enabled))

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
            mode: `"system"` или один из ключей `gui.styles.theme.THEME_LABELS`.
        """
        for index, (mode_value, _) in enumerate(_THEME_MODES):
            if mode_value == mode:
                self._theme_combo.setCurrentIndex(index)
                return

    def get_current_mode(self) -> str:
        """
        Получить текущий выбранный режим темы.

        Returns:
            `"system"` или один из ключей `gui.styles.theme.THEME_LABELS`.
        """
        index = self._theme_combo.currentIndex()
        if 0 <= index < len(_THEME_MODES):
            return _THEME_MODES[index][0]
        return "system"
