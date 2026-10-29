"""
Плавающий виджет активной записи (#158)
========================================

Компактная always-on-top панель: состояние (recording/paused/finalizing),
таймер, live FPS и размер файла. Перетаскивается мышью с привязкой к краям
экрана; позиция сохраняется в config.json.

Чистая логика (снап, форматирование) вынесена в static-методы — тестируется
без инициализации Qt (см. tests/unit/gui/test_floating_widget.py).
"""

from __future__ import annotations

from typing import Any, Final

from PyQt6.QtCore import QPoint, Qt, QTimer
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from config import get_config
from gui.constants import RECORDING_INDICATOR_TICK_MS
from gui.styles.theme import Theme
from logger_config import get_module_logger

logger = get_module_logger(__name__)

# Состояния виджета (#158): конечный автомат idle → recording → paused →
# finalizing (обратно в idle при скрытии)
STATE_IDLE = "idle"
STATE_RECORDING = "recording"
STATE_PAUSED = "paused"
STATE_FINALIZING = "finalizing"

# Состояние → (текст статуса, цвет из палитры темы)
_STATE_LABELS: Final[dict[str, tuple[str, str]]] = {
    STATE_IDLE: ("", "muted"),
    STATE_RECORDING: ("● REC", "danger"),
    STATE_PAUSED: ("⏸ Пауза", "warning"),
    STATE_FINALIZING: ("⟳ Сохранение", "success"),
}

# Порог привязки к краю экрана (px)
SNAP_THRESHOLD_PX: Final[int] = 24
# Форматирование размера: до 1 КБ показываем байты
_SIZE_KB = 1024
_SIZE_MB = _SIZE_KB * 1024


def format_recording_size(size_bytes: int | None) -> str:
    """Человекочитаемый размер файла записи (#158)."""
    if size_bytes is None:
        return "—"
    if size_bytes >= _SIZE_MB:
        return f"{size_bytes / _SIZE_MB:.1f} МБ"
    if size_bytes >= _SIZE_KB:
        return f"{size_bytes / _SIZE_KB:.0f} КБ"
    return f"{size_bytes} Б"


def snap_to_edges(
    x: int,
    y: int,
    widget_w: int,
    widget_h: int,
    screen_w: int,
    screen_h: int,
    threshold: int = SNAP_THRESHOLD_PX,
) -> tuple[int, int]:
    """Привязка позиции к краям экрана (#158).

    Args:
        x, y: Текущая позиция левого верхнего угла.
        widget_w, widget_h: Размер виджета.
        screen_w, screen_h: Размер экрана.
        threshold: Дистанция магнита в пикселях.

    Returns:
        Привязанная позиция (x, y); позиция всегда зажимается в экран.
    """
    x = max(0, min(x, screen_w - widget_w))
    y = max(0, min(y, screen_h - widget_h))

    if abs(x) <= threshold:
        x = 0
    elif abs(screen_w - widget_w - x) <= threshold:
        x = screen_w - widget_w

    if abs(y) <= threshold:
        y = 0
    elif abs(screen_h - widget_h - y) <= threshold:
        y = screen_h - widget_h

    return x, y


class FloatingRecordingWidget(QWidget):
    """Компактный плавающий индикатор активной записи (#158)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = STATE_IDLE
        self._drag_offset: QPoint | None = None
        self._dragging = False

        self.setWindowTitle("MIA-ScreenCapture — запись")
        if hasattr(self, "setWindowFlags"):
            self.setWindowFlags(
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
        if hasattr(self, "setAttribute") and hasattr(
            Qt.WidgetAttribute, "WA_TranslucentBackground"
        ):
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        self._state_label = QLabel("")
        self._state_label.setStyleSheet(Theme.status_style("muted"))
        self._time_label = QLabel("00:00")
        self._time_label.setStyleSheet(Theme.secondary_hint_style())
        self._metrics_label = QLabel("")
        self._metrics_label.setStyleSheet(Theme.secondary_hint_style())

        top_row = QHBoxLayout()
        top_row.addWidget(self._state_label)
        top_row.addStretch()
        top_row.addWidget(self._time_label)
        layout.addLayout(top_row)
        layout.addWidget(self._metrics_label)

        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            "background-color: rgba(30, 30, 30, 220); border-radius: 6px;"
        )

        # Тик обновляет метрики из контроллера, как строка состояния
        self._timer = QTimer()
        if hasattr(self._timer, "timeout"):
            self._timer.timeout.connect(self._on_tick)

    # ------------------------------------------------------------------
    # Состояние и метрики
    # ------------------------------------------------------------------

    def set_state(self, state: str) -> None:
        """Переключить состояние индикатора (#158).

        Args:
            state: ``idle`` | ``recording`` | ``paused`` | ``finalizing``.
        """
        if state not in _STATE_LABELS:
            logger.warning(
                "Неизвестное состояние плавающего виджета: %s", state
            )
            return
        self._state = state
        label, color = _STATE_LABELS[state]
        self._state_label.setText(label)
        self._state_label.setStyleSheet(Theme.status_style(color))

    def get_state(self) -> str:
        """Текущее состояние виджета."""
        return self._state

    def update_metrics(
        self,
        elapsed_s: float,
        fps: float,
        size_bytes: int | None,
    ) -> None:
        """Обновить таймер, FPS и размер файла (#158)."""
        minutes, seconds = divmod(max(0, int(elapsed_s)), 60)
        self._time_label.setText(f"{minutes:02d}:{seconds:02d}")
        fps_text = f"{fps:.1f} FPS" if fps > 0 else "— FPS"
        self._metrics_label.setText(
            f"{fps_text}  •  {format_recording_size(size_bytes)}"
        )

    def start_updates(self, on_tick: Any) -> None:
        """Запустить периодическое обновление метрик (#158)."""
        if hasattr(self._timer, "timeout"):
            try:
                self._timer.timeout.disconnect(self._on_tick)
            except TypeError:
                pass  # ещё не подключён
            self._timer.timeout.connect(on_tick)
        if hasattr(self._timer, "start"):
            self._timer.start(RECORDING_INDICATOR_TICK_MS)

    def stop_updates(self) -> None:
        """Остановить периодическое обновление."""
        if hasattr(self._timer, "stop"):
            self._timer.stop()

    def _on_tick(self) -> None:
        """Дефолтный тик (переопределяется start_updates)."""

    # ------------------------------------------------------------------
    # Позиция: drag + snap + persistence
    # ------------------------------------------------------------------

    def save_position(self) -> None:
        """Сохранить текущую позицию в конфигурацию (#158)."""
        if not hasattr(self, "pos"):
            return
        pos = self.pos()
        get_config().settings.floating_widget_pos = [pos.x(), pos.y()]

    def restore_position(self, screen_size: tuple[int, int]) -> None:
        """Восстановить сохранённую позицию с зажимом в экран (#158).

        Args:
            screen_size: (ширина, высота) экрана.
        """
        if not hasattr(self, "move"):
            return
        pos = get_config().settings.floating_widget_pos
        if pos is None:
            return
        w = self.width() if hasattr(self, "width") else 160
        h = self.height() if hasattr(self, "height") else 56
        clamped_x, clamped_y = snap_to_edges(
            pos[0], pos[1], w, h, screen_size[0], screen_size[1], threshold=0
        )
        self.move(clamped_x, clamped_y)

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802
        """Начало перетаскивания левой кнопкой (#158)."""
        if (
            hasattr(event, "button")
            and event.button() == Qt.MouseButton.LeftButton
            and hasattr(self, "pos")
            and hasattr(event, "globalPosition")
        ):
            self._dragging = True
            global_pos = event.globalPosition().toPoint()
            self._drag_offset = global_pos - self.pos()
            event.accept()

    def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802
        """Перетаскивание: позиция следует за курсором (#158)."""
        if not self._dragging or self._drag_offset is None:
            return
        if not hasattr(event, "globalPosition"):
            return
        global_pos = event.globalPosition().toPoint()
        new_pos = global_pos - self._drag_offset
        self.move(new_pos.x(), new_pos.y())
        event.accept()

    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802
        """Конец перетаскивания: снап к краям и сохранение (#158)."""
        if not self._dragging:
            return
        self._dragging = False
        self._drag_offset = None

        from recorder.utils import get_screen_size

        try:
            screen_w, screen_h = get_screen_size()
        except Exception:
            screen_w, screen_h = 0, 0
        if screen_w > 0 and screen_h > 0 and hasattr(self, "pos"):
            pos = self.pos()
            w = self.width() if hasattr(self, "width") else 160
            h = self.height() if hasattr(self, "height") else 56
            snapped_x, snapped_y = snap_to_edges(
                pos.x(), pos.y(), w, h, screen_w, screen_h
            )
            self.move(snapped_x, snapped_y)
        self.save_position()
        event.accept()
