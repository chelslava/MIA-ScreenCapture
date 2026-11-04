"""Полноэкранный оверлей обратного отсчёта перед стартом записи (#167).

Показывает крупные цифры поверх экрана, давая пользователю время
переключиться на нужное окно. Отмена — клавишей Esc.
"""

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication, QKeyEvent
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from logger_config import get_module_logger

logger = get_module_logger(__name__)

_DIGIT_STYLESHEET = (
    "color: #ffffff;font-size: 160px;font-weight: 700;background: transparent;"
)
_HINT_STYLESHEET = "color: rgba(255, 255, 255, 180); font-size: 16px;"
_VEIL_STYLESHEET = "background-color: rgba(0, 0, 0, 100);"


class CountdownOverlay(QWidget):
    """Полноэкранный оверлей с обратным отсчётом перед записью.

    Размещается на весь экран (по геометрии основного монитора) поверх
    всех окон. Каждый тик таймера уменьшает счётчик; по достижении нуля
    оверлей скрывается и публикует сигнал `countdown_finished`.
    """

    countdown_finished = pyqtSignal()
    countdown_cancelled = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Инициализация оверлея.

        Args:
            parent: Родительский виджет (обычно None — независимое окно).
        """
        super().__init__(parent)
        self._remaining = 0

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(_VEIL_STYLESHEET)

        layout = QVBoxLayout(self)
        self._digit_label = QLabel(self)
        self._digit_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._digit_label.setStyleSheet(_DIGIT_STYLESHEET)
        self._hint_label = QLabel("Esc — отмена", self)
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint_label.setStyleSheet(_HINT_STYLESHEET)
        layout.addStretch(1)
        layout.addWidget(self._digit_label)
        layout.addWidget(self._hint_label)
        layout.addStretch(2)

    def start(self, seconds: int) -> None:
        """Запустить отсчёт.

        Args:
            seconds: Длительность отсчёта в секундах. Значение <= 0
                считается отсутствием отсчёта: оверлей не показывается,
                сразу публикуется `countdown_finished`.
        """
        if seconds <= 0:
            logger.debug("Отсчёт пропущен: seconds=%s", seconds)
            self.countdown_finished.emit()
            return

        self._remaining = seconds
        self._digit_label.setText(str(seconds))

        screen = QGuiApplication.primaryScreen()
        if screen is not None:
            self.setGeometry(screen.geometry())

        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self._timer.start()
        logger.info("Обратный отсчёт перед записью: %s сек", seconds)

    def cancel(self) -> None:
        """Отменить отсчёт (Esc или внешний вызов).

        Идемпотентно: если отсчёт не активен, сигнал не публикуется.
        """
        if not self._timer.isActive():
            return
        self._timer.stop()
        self.hide()
        logger.info("Обратный отсчёт отменён пользователем")
        self.countdown_cancelled.emit()

    def remaining_seconds(self) -> int:
        """Текущее значение счётчика (для тестов и отладки)."""
        return self._remaining

    def _tick(self) -> None:
        """Тик таймера: уменьшить счётчик или завершить отсчёт."""
        self._remaining -= 1
        if self._remaining <= 0:
            self._timer.stop()
            self.hide()
            self.countdown_finished.emit()
            return
        self._digit_label.setText(str(self._remaining))

    def keyPressEvent(self, event: QKeyEvent | None) -> None:
        """Обработка клавиш: Esc отменяет отсчёт.

        Args:
            event: Событие клавиатуры.
        """
        if event is not None and event.key() == Qt.Key.Key_Escape:
            self.cancel()
            return
        super().keyPressEvent(event)
