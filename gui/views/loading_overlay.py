"""
Отображение индикатора загрузки для асинхронных операций.
"""

from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LoadingOverlay(QWidget):
    """
    Полупрозрачный оверлей для отображения состояния загрузки.

    Используется для визуальной обратной связи во время длительных
    асинхронных операций (перечисление устройств, проверка FFmpeg,
    загрузка списка окон).

    Overlay неблокирующий - содержимое родительского виджета
    остается видимым под полупрозрачным слоем.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        message: str = "Загрузка...",
    ) -> None:
        """
        Создать оверлей загрузки.

        Args:
            parent: Родительский виджет.
            message: Текст сообщения по умолчанию.
        """
        super().__init__(parent)
        self._message = message
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Настройка пользовательского интерфейса оверлея."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel(self._message)
        self._label.setStyleSheet(
            "color: #FFFFFF; font-size: 14px; font-weight: bold; qproperty-alignment: AlignCenter;"
        )
        layout.addWidget(self._label)

        self.setVisible(False)

    def show(self) -> None:
        """Показать оверлей поверх родительского виджета."""
        parent = getattr(self, "parentWidget", None)
        if callable(parent):
            parent_widget = parent()
            if isinstance(parent_widget, QWidget):
                geometry = getattr(parent_widget, "geometry", None)
                set_geometry = getattr(self, "setGeometry", None)
                if callable(geometry) and callable(set_geometry):
                    set_geometry(geometry())
        self.setVisible(True)

    def hide(self) -> None:
        """Скрыть оверлей."""
        self.setVisible(False)

    def setMessage(self, text: str) -> None:
        """Обновить отображаемое сообщение."""
        self._message = text
        set_text = getattr(self._label, "setText", None)
        if callable(set_text):
            set_text(text)
