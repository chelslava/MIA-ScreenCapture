"""Оверлей эффектов курсора при записи (#166).

Маленькое прозрачное click-through окно, следующее за курсором:
полупрозрачная подсветка и расходящиеся кольца при кликах
(ЛКМ — жёлтое, ПКМ — красное). События кликов приходят из потока
pynput-слушателя через queued-сигнал.

Схема окна — по проверенному образцу визуального слоя оверлея
рисования (#159): ``WA_TranslucentBackground`` +
``WindowTransparentForInput`` (WS_EX_TRANSPARENT), поэтому мышь и
клавиатура проходят насквозь, а WGC-захват показывает оверлей в записи.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from core.recording_types import CursorEffectSettings
from logger_config import get_module_logger

logger = get_module_logger(__name__)

EFFECT_WINDOW_SIZE = 160
HIGHLIGHT_RADIUS = 14.0
RIPPLE_START_RADIUS = 10.0
RIPPLE_END_RADIUS = 36.0
RIPPLE_START_ALPHA = 180
RIPPLE_PEN_WIDTH = 3
RIPPLE_DURATION_SECONDS = 0.5
TICK_INTERVAL_MS = 33

LEFT_CLICK_COLOR = QColor("#FFCC00")
RIGHT_CLICK_COLOR = QColor("#FF3B30")
RIPPLE_COLORS: dict[str, QColor] = {
    "left": LEFT_CLICK_COLOR,
    "right": RIGHT_CLICK_COLOR,
}
_HIGHLIGHT_FILL = QColor(255, 204, 0, 70)
_HIGHLIGHT_PEN = QColor(255, 204, 0, 180)


@dataclass(frozen=True)
class _ClickRipple:
    """Зарегистрированный клик с моментом начала анимации."""

    x: int
    y: int
    button: str
    started_at: float


def ripple_progress(started_at: float, now: float) -> float:
    """Прогресс анимации клика (0..1); за пределами — ограничен.

    Args:
        started_at: Момент клика (`time.monotonic()`).
        now: Текущий момент.

    Returns:
        Прогресс от 0.0 до 1.0.
    """
    if RIPPLE_DURATION_SECONDS <= 0:
        return 1.0
    progress = (now - started_at) / RIPPLE_DURATION_SECONDS
    return max(0.0, min(progress, 1.0))


def ripple_radius(progress: float) -> float:
    """Радиус кольца на данном прогрессе анимации.

    Args:
        progress: Прогресс 0..1.

    Returns:
        Радиус в пикселях от `RIPPLE_START_RADIUS` до `RIPPLE_END_RADIUS`.
    """
    return RIPPLE_START_RADIUS + progress * (
        RIPPLE_END_RADIUS - RIPPLE_START_RADIUS
    )


def ripple_alpha(progress: float) -> int:
    """Прозрачность кольца: линейное затухание до нуля.

    Args:
        progress: Прогресс 0..1.

    Returns:
        Альфа 0..`RIPPLE_START_ALPHA`.
    """
    return int(RIPPLE_START_ALPHA * (1.0 - progress))


class CursorEffectsOverlay(QWidget):
    """Прозрачное окно с подсветкой курсора и кольцами кликов (#166).

    Следует за курсором таймером ~30 FPS. Клик-события публикует
    pynput-слушатель из фонового потока через сигнал
    `click_registered`. Полностью click-through: ввод проходит
    насквозь на рабочий стол.
    """

    click_registered = pyqtSignal(str, int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Инициализировать оверлей.

        Args:
            parent: Родительский виджет (обычно None).
        """
        super().__init__(parent)
        self._highlight_enabled = False
        self._click_effects_enabled = False
        self._clicks: list[_ClickRipple] = []
        self._mouse_listener: Any = None  # pynput.mouse.Listener | None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(EFFECT_WINDOW_SIZE, EFFECT_WINDOW_SIZE)

        self._timer = QTimer(self)
        self._timer.setInterval(TICK_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)

        self.click_registered.connect(self.register_click)

    def apply_settings(self, settings: CursorEffectSettings) -> None:
        """Применить настройки эффектов (#166).

        Args:
            settings: Флаги подсветки и эффектов кликов.
        """
        self._highlight_enabled = settings.highlight_enabled
        self._click_effects_enabled = settings.click_effects_enabled

    def start(self) -> None:
        """Показать оверлей и запустить таймер/слушатель кликов."""
        if self._timer.isActive():
            return
        self._start_mouse_listener()
        self._timer.start()
        self.show()
        self.raise_()
        logger.debug("Оверлей эффектов курсора запущен")

    def stop(self) -> None:
        """Скрыть оверлей, остановить таймер и слушатель кликов."""
        self._timer.stop()
        if self._mouse_listener is not None:
            try:
                self._mouse_listener.stop()
            except (OSError, RuntimeError) as e:
                logger.warning("Ошибка остановки слушателя мыши: %s", e)
            self._mouse_listener = None
        self._clicks = []
        self.hide()
        logger.debug("Оверлей эффектов курсора остановлен")

    def register_click(self, button: str, x: int, y: int) -> None:
        """Зарегистрировать клик для анимации кольца.

        Args:
            button: Кнопка ("left" или "right"); прочие игнорируются.
            x: Абсолютная координата курсора.
            y: Абсолютная координата курсора.
        """
        if not self._click_effects_enabled:
            return
        if button not in RIPPLE_COLORS:
            return
        self._clicks.append(
            _ClickRipple(x=x, y=y, button=button, started_at=time.monotonic())
        )

    def active_ripples(self, now: float) -> list[_ClickRipple]:
        """Активные (не затухшие) кольца на момент `now` (#166).

        Args:
            now: Текущий момент `time.monotonic()`.

        Returns:
            Кольца, чья анимация ещё не завершилась.
        """
        return [
            ripple
            for ripple in self._clicks
            if now - ripple.started_at < RIPPLE_DURATION_SECONDS
        ]

    def _start_mouse_listener(self) -> None:
        """Запустить pynput-слушатель кликов (если доступен)."""
        if self._mouse_listener is not None:
            return
        if not self._click_effects_enabled:
            return
        try:
            from pynput import mouse
        except ImportError:
            logger.warning(
                "pynput недоступен — эффекты кликов отключены; "
                "подсветка курсора продолжает работать"
            )
            return
        listener = mouse.Listener(on_click=self._on_native_click)
        listener.daemon = True
        listener.start()
        self._mouse_listener = listener

    def _on_native_click(
        self, x: int, y: int, button: Any, pressed: bool
    ) -> None:
        """Колбэк pynput: пробросить нажатие в GUI-поток.

        Args:
            x: Абсолютная координата.
            y: Абсолютная координата.
            button: Кнопка мыши pynput (`button.name` — "left"/"right").
            pressed: Нажата ли кнопка (отпускания игнорируются).
        """
        if not pressed:
            return
        name = getattr(button, "name", "")
        if name in RIPPLE_COLORS:
            self.click_registered.emit(name, int(x), int(y))

    def _tick(self) -> None:
        """Тик таймера: следовать за курсором и обновлять анимацию."""
        position = QCursor.pos()
        self.move(
            position.x() - EFFECT_WINDOW_SIZE // 2,
            position.y() - EFFECT_WINDOW_SIZE // 2,
        )
        now = time.monotonic()
        self._clicks = self.active_ripples(now)
        self.update()

    def paintEvent(self, _event: Any) -> None:  # noqa: N802
        """Отрисовать подсветку курсора и кольца кликов."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        now = time.monotonic()
        center = QPointF(EFFECT_WINDOW_SIZE / 2, EFFECT_WINDOW_SIZE / 2)

        if self._highlight_enabled:
            painter.setBrush(_HIGHLIGHT_FILL)
            painter.setPen(QPen(_HIGHLIGHT_PEN, 2))
            painter.drawEllipse(center, HIGHLIGHT_RADIUS, HIGHLIGHT_RADIUS)

        for ripple in self._clicks:
            progress = ripple_progress(ripple.started_at, now)
            radius = ripple_radius(progress)
            color = RIPPLE_COLORS.get(ripple.button)
            if color is None:
                continue
            pen_color = QColor(color)
            pen_color.setAlpha(ripple_alpha(progress))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(pen_color, RIPPLE_PEN_WIDTH))
            painter.drawEllipse(center, radius, radius)
