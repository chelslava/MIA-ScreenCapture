"""
Визуальная индикация активной области записи.
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from core.recording_state import CaptureSettings
from core.recording_types import CaptureMode
from logger_config import get_module_logger
from recorder.utils import get_available_windows, get_screen_size

logger = get_module_logger(__name__)

IndicatorRect = tuple[int, int, int, int]

_INDICATOR_TICK_MS = 450
_INDICATOR_MARGIN = 2
_INDICATOR_LINE_WIDTH = 4
_ACTIVE_ALPHA = 180
_DIM_ALPHA = 100
_PAUSED_ALPHA = 130


@dataclass(frozen=True)
class WindowBounds:
    """Границы области подсветки."""

    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        """Ширина прямоугольника."""
        return self.right - self.left

    @property
    def height(self) -> int:
        """Высота прямоугольника."""
        return self.bottom - self.top


def resolve_indicator_rect(
    capture: CaptureSettings,
    screen_size: tuple[int, int] | None = None,
    windows: list[dict[str, int | str]] | None = None,
) -> IndicatorRect | None:
    """
    Определить прямоугольник для индикации активной записи.

    Args:
        capture: Настройки области захвата.
        screen_size: Размер экрана для режима `full`.
        windows: Список доступных окон для режима `window`.

    Returns:
        Координаты рамки `(x1, y1, x2, y2)` или `None`.
    """
    if capture.capture_type == CaptureMode.RECT:
        x1, y1, x2, y2 = capture.rect_coords
        return (int(x1), int(y1), int(x2), int(y2))

    if capture.capture_type == CaptureMode.FULL:
        width, height = screen_size or get_screen_size()
        return (0, 0, width, height)

    if capture.capture_type != CaptureMode.WINDOW:
        return None

    window_title = capture.window_title.strip().lower()
    if not window_title:
        return None

    available_windows = windows or get_available_windows()
    for window_info in available_windows:
        current_title = str(window_info.get("title", ""))
        if window_title in current_title.lower():
            x = int(window_info.get("x", 0))
            y = int(window_info.get("y", 0))
            width = int(window_info.get("width", 0))
            height = int(window_info.get("height", 0))
            return (x, y, x + width, y + height)

    return None


class RecordingIndicatorOverlay(QWidget):
    """
    Полупрозрачная рамка вокруг активной области записи.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Создать overlay-индикатор.

        Args:
            parent: Родительский виджет.
        """
        super().__init__(parent)
        self._bounds: WindowBounds | None = None
        self._pulse_alpha = _ACTIVE_ALPHA
        self._pulse_dimmed = False
        self._paused = False
        self._timer = QTimer()
        if hasattr(self._timer, "timeout") and hasattr(
            self._timer.timeout,
            "connect",
        ):
            self._timer.timeout.connect(self._advance_pulse)
        self._configure_window()
        self.setVisible(False)

    def _configure_window(self) -> None:
        """Настроить свойства overlay-окна."""
        if hasattr(self, "setWindowFlags"):
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
        if hasattr(self, "setAttribute") and hasattr(Qt, "WidgetAttribute"):
            if hasattr(Qt.WidgetAttribute, "WA_TransparentForMouseEvents"):
                self.setAttribute(
                    Qt.WidgetAttribute.WA_TransparentForMouseEvents,
                    True,
                )
            if hasattr(Qt.WidgetAttribute, "WA_TranslucentBackground"):
                self.setAttribute(
                    Qt.WidgetAttribute.WA_TranslucentBackground,
                    True,
                )

    def show_for_capture(self, capture: CaptureSettings) -> bool:
        """
        Показать рамку для активной области записи.

        Args:
            capture: Настройки области захвата.

        Returns:
            `True`, если рамка успешно показана.
        """
        rect = resolve_indicator_rect(capture)
        if rect is None:
            logger.warning(
                "Не удалось определить область для индикатора записи"
            )
            self.hide_indicator()
            return False

        self._bounds = WindowBounds(*rect)
        self._paused = False
        self._pulse_dimmed = False
        self._pulse_alpha = _ACTIVE_ALPHA
        self._apply_geometry()
        self.setVisible(True)
        if hasattr(self._timer, "start"):
            self._timer.start(_INDICATOR_TICK_MS)
        if hasattr(self, "update"):
            self.update()
        return True

    def hide_indicator(self) -> None:
        """Скрыть рамку записи."""
        if hasattr(self._timer, "stop"):
            self._timer.stop()
        self._bounds = None
        self.setVisible(False)
        if hasattr(self, "update"):
            self.update()

    def set_paused(self, paused: bool) -> None:
        """
        Переключить визуальное состояние паузы.

        Args:
            paused: Флаг паузы записи.
        """
        self._paused = paused
        self._pulse_alpha = _PAUSED_ALPHA if paused else _ACTIVE_ALPHA
        if hasattr(self, "update"):
            self.update()

    def _advance_pulse(self) -> None:
        """Изменить яркость рамки для эффекта мягкой пульсации."""
        if self._paused:
            self._pulse_alpha = _PAUSED_ALPHA
        else:
            self._pulse_dimmed = not self._pulse_dimmed
            self._pulse_alpha = (
                _DIM_ALPHA if self._pulse_dimmed else _ACTIVE_ALPHA
            )
        if hasattr(self, "update"):
            self.update()

    def _apply_geometry(self) -> None:
        """Применить геометрию окна по сохранённым границам."""
        if self._bounds is None or not hasattr(self, "setGeometry"):
            return

        self.setGeometry(
            self._bounds.left - _INDICATOR_MARGIN,
            self._bounds.top - _INDICATOR_MARGIN,
            self._bounds.width + _INDICATOR_MARGIN * 2,
            self._bounds.height + _INDICATOR_MARGIN * 2,
        )

    def paintEvent(self, _event) -> None:  # noqa: N802
        """Отрисовать рамку активной записи."""
        if self._bounds is None:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        color = QColor("#ef4444")
        color.setAlpha(self._pulse_alpha)
        painter.setPen(QPen(color, _INDICATOR_LINE_WIDTH))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect())
