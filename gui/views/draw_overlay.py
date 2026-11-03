"""
Оверлей быстрого рисования поверх экрана (#159)
===============================================

Полупрозрачный fullscreen-виджет поверх всего: карандаш, стрелка,
прямоугольник, эллипс, ластик, выбор цвета/толщины, undo/redo,
очистка, скриншот аннотированного экрана и выход (Esc).

Модель фигур — ``gui.models.draw_document.DrawDocument``. Виджет
тонкий: транслирует события мыши в точки документа и рисует их
QPainter'ом. Скриншот аннотаций пока не попадает в видеоклип —
композитинг в конвейер кадров вынесен в общий слой наложений (#51).
"""

from __future__ import annotations

import math
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QPushButton,
    QWidget,
)

from gui.models.draw_document import DrawDocument, DrawShape, DrawTool
from logger_config import get_module_logger

logger = get_module_logger(__name__)

# Палитра быстрых цветов тулбара
DRAW_COLORS: tuple[str, ...] = (
    "#FF3B30",  # красный
    "#FFCC00",  # жёлтый
    "#34C759",  # зелёный
    "#007AFF",  # синий
    "#FFFFFF",  # белый
)

# Толщины пера, доступные в тулбаре
DRAW_WIDTHS: tuple[int, ...] = (2, 4, 8, 12)

DEFAULT_DRAW_COLOR = DRAW_COLORS[0]
DEFAULT_DRAW_WIDTH: float = float(DRAW_WIDTHS[1])

# Ластик толще пера: масштаб ширины штриха
_ERASER_WIDTH_SCALE: float = 5.0
# Длина наконечника стрелки
_ARROWHEAD_BASE_LEN: float = 14.0
# Угол наконечника стрелки (радианы)
_ARROWHEAD_ANGLE: float = 0.45  # ~26°

_TOOLBAR_WIDTH = 660
_TOOLBAR_HEIGHT = 48
_TOOLBAR_MARGIN = 8


class DrawToolbar(QWidget):
    """Панель инструментов оверлея рисования.

    Эммитит сигналы выбора инструмента/цвета/толщины и запросов
    undo/redo/очистки/скриншота/закрытия. Не содержит логики
    рисования — только маршрутизация пользовательского ввода.
    """

    tool_changed = pyqtSignal(str)
    color_changed = pyqtSignal(str)
    width_changed = pyqtSignal(float)
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    screenshot_requested = pyqtSignal()
    close_requested = pyqtSignal()

    _TOOL_LABELS: tuple[tuple[DrawTool, str], ...] = (
        (DrawTool.PEN, "✏"),
        (DrawTool.ARROW, "➜"),
        (DrawTool.RECT, "▭"),
        (DrawTool.ELLIPSE, "◯"),
        (DrawTool.ERASER, "⌫"),
    )

    _ACTION_LABELS: tuple[tuple[str, str], ...] = (
        ("↩", "undo"),
        ("↪", "redo"),
        ("🗑", "clear"),
        ("📷", "screenshot"),
        ("✕", "close"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        """Создать тулбар с кнопками инструментов и действий."""
        super().__init__(parent)
        self.setFixedSize(_TOOLBAR_WIDTH, _TOOLBAR_HEIGHT)
        self._tool_buttons: dict[DrawTool, QPushButton] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        """Собрать кнопки инструментов, цветов и действий."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        for tool, label in self._TOOL_LABELS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedWidth(36)
            btn.setToolTip(f"Инструмент: {tool.value}")
            btn.clicked.connect(
                lambda _=False, t=tool: self.tool_changed.emit(t.value)
            )
            self._tool_buttons[tool] = btn
            layout.addWidget(btn)

        for color in DRAW_COLORS:
            swatch = QPushButton()
            swatch.setFixedSize(22, 22)
            swatch.setToolTip(f"Цвет {color}")
            swatch.setStyleSheet(
                f"background-color: {color}; border: 1px solid #888;"
                "border-radius: 4px;"
            )
            swatch.clicked.connect(
                lambda _=False, c=color: self.color_changed.emit(c)
            )
            layout.addWidget(swatch)

        self._width_combo = QComboBox()
        for width in DRAW_WIDTHS:
            self._width_combo.addItem(f"{width} px", width)
        self._width_combo.setCurrentIndex(1)
        self._width_combo.currentIndexChanged.connect(
            self._on_width_index_changed
        )
        layout.addWidget(self._width_combo)

        for label, action in self._ACTION_LABELS:
            btn = QPushButton(label)
            btn.setFixedWidth(36)
            btn.setToolTip(f"Действие: {action}")
            btn.clicked.connect(lambda _=False, a=action: self._emit_action(a))
            layout.addWidget(btn)

        self.set_tool(DrawTool.PEN.value)

    def _on_width_index_changed(self, index: int) -> None:
        """Переслать выбранную толщину пера."""
        width = DRAW_WIDTHS[index] if 0 <= index < len(DRAW_WIDTHS) else 4
        self.width_changed.emit(float(width))

    def _emit_action(self, action: str) -> None:
        """Отправить сигнал действия по его имени."""
        if action == "undo":
            self.undo_requested.emit()
        elif action == "redo":
            self.redo_requested.emit()
        elif action == "clear":
            self.clear_requested.emit()
        elif action == "screenshot":
            self.screenshot_requested.emit()
        elif action == "close":
            self.close_requested.emit()

    # === Состояние визуального выделения ===

    def set_tool(self, tool_value: str) -> None:
        """Выделить активный инструмент кнопкой.

        Args:
            tool_value: Значение `DrawTool` в виде строки.
        """
        try:
            tool = DrawTool(tool_value)
        except ValueError:
            return
        for known_tool, btn in self._tool_buttons.items():
            btn.setChecked(known_tool is tool)


class DrawOverlayWidget(QWidget):
    """Fullscreen-оверлей с аннотациями поверх экрана.

    Прозрачный для системы (WA_TranslucentBackground), всегда поверх
    остальных окон, захватывает все события мыши. Рисование через
    QPainter по фигурам `DrawDocument`; перерисовка только по
    коалесцированному update() — фризов UI при активном штрихе нет.
    """

    closed = pyqtSignal()
    screenshot_taken = pyqtSignal(str)

    def __init__(
        self,
        document: DrawDocument | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Создать оверлей с тулбаром и пустым документом.

        Args:
            document: Внешний документ аннотаций (по умолчанию новый).
            parent: Родительский виджет.
        """
        super().__init__(parent)
        self._document = document if document is not None else DrawDocument()
        self._tool = DrawTool.PEN
        self._color = DEFAULT_DRAW_COLOR
        self._width = DEFAULT_DRAW_WIDTH
        self._active_shape: DrawShape | None = None
        # Прозрачный щит на весь экран: top-level layered-окно hit-тестит
        # по альфе и пропускает клики сквозь прозрачные пиксели; child
        # виджет ловит мышь по геометрии (#159, живая проверка).
        self._input_shield = QWidget(self)
        self._input_shield.setMouseTracking(True)
        self._input_shield.installEventFilter(self)
        self._toolbar = DrawToolbar(self)
        self._setup_window()
        self._connect_toolbar()

    # === Настройка окна ===

    def _setup_window(self) -> None:
        """Флаги поверх всех окон, прозрачность, курсор-крестик."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _connect_toolbar(self) -> None:
        """Подключить сигналы тулбара к оверлею."""
        self._toolbar.tool_changed.connect(self.set_tool)
        self._toolbar.color_changed.connect(self.set_color)
        self._toolbar.width_changed.connect(self.set_width)
        self._toolbar.undo_requested.connect(self.undo)
        self._toolbar.redo_requested.connect(self.redo)
        self._toolbar.clear_requested.connect(self.clear_annotations)
        self._toolbar.screenshot_requested.connect(self._on_screenshot)
        self._toolbar.close_requested.connect(self.close_overlay)

    # === Публичное состояние ===

    @property
    def document(self) -> DrawDocument:
        """Документ аннотаций оверлея."""
        return self._document

    def tool(self) -> str:
        """Текущий инструмент."""
        return self._tool.value

    def color(self) -> str:
        """Текущий цвет пера."""
        return self._color

    def pen_width(self) -> float:
        """Текущая толщина пера (не путать с QWidget.width)."""
        return self._width

    def set_tool(self, tool_value: str) -> None:
        """Переключить активный инструмент.

        Args:
            tool_value: Значение `DrawTool` в виде строки.
        """
        try:
            self._tool = DrawTool(tool_value)
        except ValueError:
            return
        self._toolbar.set_tool(tool_value)

    def set_color(self, color: str) -> None:
        """Установить цвет пера.

        Args:
            color: HEX-цвет (например ``#FF3B30``).
        """
        self._color = color

    def set_width(self, width: float) -> None:
        """Установить толщину пера.

        Args:
            width: Толщина в пикселях (> 0).
        """
        if width > 0:
            self._width = float(width)

    # === Управление режимом ===

    def open_overlay(self) -> None:
        """Показать оверлей на весь экран и передать ему фокус.

        setGeometry + show (как в area_selector): showFullScreen на
        Windows с WA_TranslucentBackground не доставляет события мыши
        по прозрачным областям.
        """
        try:
            from PyQt6.QtGui import QGuiApplication

            screen = QGuiApplication.primaryScreen()
            if screen is not None:
                geometry = screen.geometry()
                self.setGeometry(
                    geometry.x(),
                    geometry.y(),
                    geometry.width(),
                    geometry.height(),
                )
        except Exception as e:
            logger.warning("Геометрия оверлея не установлена: %s", e)
        if hasattr(self, "_input_shield") and hasattr(self, "size"):
            size = self.size()
            self._input_shield.resize(size.width(), size.height())
        if hasattr(self, "show"):
            self.show()
        if hasattr(self, "raise_"):
            self.raise_()
        if hasattr(self, "activateWindow"):
            self.activateWindow()

    def close_overlay(self) -> None:
        """Скрыть оверлей, сохранив аннотации в документе."""
        self._active_shape = None
        if hasattr(self, "hide"):
            self.hide()
        self.closed.emit()

    def undo(self) -> None:
        """Отменить последнюю фигуру."""
        self._document.undo()
        self._request_repaint()

    def redo(self) -> None:
        """Вернуть последнюю отменённую фигуру."""
        self._document.redo()
        self._request_repaint()

    def clear_annotations(self) -> None:
        """Удалить все аннотации с экрана."""
        removed = self._document.clear()
        if removed:
            logger.info("Очищено аннотаций: %d", removed)
        self._request_repaint()

    # === Скриншот ===

    def take_screenshot(self, directory: Path) -> Path | None:
        """Сохранить снимок экрана с аннотациями.

        Args:
            directory: Каталог сохранения (создаётся при отсутствии).

        Returns:
            Путь к PNG или None, если снять/сохранить не удалось.
        """
        pixmap = self._grab_composited_screen()
        if pixmap is None:
            return None
        try:
            target_dir = Path(directory)
            target_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = target_dir / f"annotation_{timestamp}.png"
            saved = pixmap.save(str(path), "PNG")
        except (OSError, ValueError) as e:
            logger.error("Не удалось сохранить скриншот: %s", e)
            return None
        if saved:
            self.screenshot_taken.emit(str(path))
            return path
        return None

    def _on_screenshot(self) -> None:
        """Скриншот по кнопке тулбара — в папку вывода приложения."""
        from config import get_config

        directory = Path(str(get_config().settings.output.default_path))
        self.take_screenshot(directory)

    def _grab_composited_screen(self) -> QPixmap | None:
        """Снять экран и наложить поверх аннотации оверлея.

        Оверлей временно скрывается, чтобы аннотации не попали в
        базовый снимок дважды (layered windows может захватывать
        grabWindow).
        """
        from PyQt6.QtGui import QGuiApplication

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return None
        was_visible = bool(self.isVisible())
        if was_visible and hasattr(self, "hide"):
            self.hide()
        try:
            from PyQt6.QtWidgets import QApplication

            QApplication.processEvents()
            base = cast(Any, screen).grabWindow(0)
            if hasattr(self, "size"):
                annotations = QPixmap(self.size())
            else:
                annotations = QPixmap()
            annotations.fill(Qt.GlobalColor.transparent)
            if hasattr(self, "render"):
                self.render(annotations)
            painter = QPainter(base)
            try:
                painter.drawPixmap(0, 0, annotations)
            finally:
                painter.end()
        except Exception as e:
            logger.error("Не удалось снять экран с аннотациями: %s", e)
            return None
        finally:
            if was_visible and hasattr(self, "show"):
                self.show()
        return cast(QPixmap, base)

    # === События мыши ===

    def eventFilter(self, obj: Any, event: Any) -> bool:
        """Маршрут мышиных событий щита в рисование (#159)."""
        if obj is getattr(self, "_input_shield", None):
            event_type = getattr(event, "type", lambda: None)()
            if event_type == QEvent.Type.MouseButtonPress:
                self._on_press(event)
                return True
            if event_type == QEvent.Type.MouseMove:
                self._on_move(event)
                return True
            if event_type == QEvent.Type.MouseButtonRelease:
                self._on_release(event)
                return True
        return (
            bool(super().eventFilter(obj, event))
            if hasattr(super(), "eventFilter")
            else False
        )

    def mousePressEvent(self, event: Any) -> None:
        """Начать фигуру (прямые события окна, кроме щита)."""
        self._on_press(event)

    def mouseMoveEvent(self, event: Any) -> None:
        """Продлить штрих (прямые события окна, кроме щита)."""
        self._on_move(event)

    def mouseReleaseEvent(self, event: Any) -> None:
        """Зафиксировать фигуру (прямые события окна, кроме щита)."""
        self._on_release(event)

    def _on_press(self, event: Any) -> None:
        """Начать фигуру в точке нажатия."""
        pos = event.position()
        logger.info("Штрих начат: (%.0f, %.0f)", pos.x(), pos.y())
        self._start_shape(float(pos.x()), float(pos.y()))

    def _on_move(self, event: Any) -> None:
        """Продлить активный штрих (коалесцированная перерисовка)."""
        if self._active_shape is None:
            return
        pos = event.position()
        x, y = float(pos.x()), float(pos.y())
        if self._tool in (DrawTool.ARROW, DrawTool.RECT, DrawTool.ELLIPSE):
            self._active_shape.points[1] = (x, y)
        else:
            self._active_shape.points.append((x, y))
        self._request_repaint()

    def _on_release(self, event: Any) -> None:
        """Завершить фигуру и зафиксировать её в документе."""
        if self._active_shape is None:
            return
        pos = event.position()
        x, y = float(pos.x()), float(pos.y())
        if self._tool in (DrawTool.ARROW, DrawTool.RECT, DrawTool.ELLIPSE):
            self._active_shape.points[1] = (x, y)
        elif len(self._active_shape.points) < 2:
            # Одиночный клик — точка (дублируем координату)
            self._active_shape.points.append((x, y))
        shape = self._active_shape
        self._active_shape = None
        self._document.add_shape(shape)
        logger.info(
            "Штрих зафиксирован: %s, точек: %d",
            shape.tool.value,
            len(shape.points),
        )
        self._request_repaint()

    def keyPressEvent(self, event: Any) -> None:
        """Горячие клавиши оверлея: Ctrl+Z/Y (undo/redo), Esc (выход)."""
        key = getattr(event, "key", lambda: None)()
        modifiers = getattr(event, "modifiers", None)
        has_control = False
        if modifiers is not None:
            try:
                has_control = bool(
                    modifiers & Qt.KeyboardModifier.ControlModifier
                )
            except TypeError:
                has_control = False
        if has_control and key == Qt.Key.Key_Z:
            self.undo()
            return
        if has_control and key == Qt.Key.Key_Y:
            self.redo()
            return
        if key == Qt.Key.Key_Escape:
            self.close_overlay()
            return
        if hasattr(super(), "keyPressEvent"):
            super().keyPressEvent(event)

    # === Внутреннее ===

    def _start_shape(self, x: float, y: float) -> None:
        """Создать активную фигуру по инструменту."""
        if self._tool in (DrawTool.ARROW, DrawTool.RECT, DrawTool.ELLIPSE):
            points: list[tuple[float, float]] = [(x, y), (x, y)]
        else:
            points = [(x, y)]
        self._active_shape = DrawShape(
            tool=self._tool,
            points=points,
            color=self._color,
            width=self._width,
        )

    def _request_repaint(self) -> None:
        """Запросить перерисовку, если виджет умеет update()."""
        if hasattr(self, "update"):
            self.update()

    # === Отрисовка ===

    def paintEvent(self, event: Any) -> None:
        """Нарисовать все фигуры документа и активный штрих."""
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            for shape in self._document:
                self._draw_shape(painter, shape)
            if self._active_shape is not None:
                self._draw_shape(painter, self._active_shape)
        finally:
            painter.end()

    def _draw_shape(self, painter: QPainter, shape: DrawShape) -> None:
        """Отрисовать одну фигуру с параметрами её инструмента."""
        if shape.tool is DrawTool.ERASER:
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_Clear
            )
            pen_width = shape.width * _ERASER_WIDTH_SCALE
            pen_color = QColor("#000000")
        else:
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceOver
            )
            pen_width = shape.width
            pen_color = QColor(shape.color)

        pen = QPen(pen_color, pen_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)

        if shape.tool is DrawTool.ARROW:
            self._draw_arrow(painter, shape)
        elif shape.tool is DrawTool.RECT:
            (x1, y1), (x2, y2) = shape.points[0], shape.points[-1]
            painter.drawRect(
                int(min(x1, x2)),
                int(min(y1, y2)),
                int(abs(x2 - x1)),
                int(abs(y2 - y1)),
            )
        elif shape.tool is DrawTool.ELLIPSE:
            (x1, y1), (x2, y2) = shape.points[0], shape.points[-1]
            painter.drawEllipse(
                int(min(x1, x2)),
                int(min(y1, y2)),
                int(abs(x2 - x1)),
                int(abs(y2 - y1)),
            )
        else:
            self._draw_polyline(painter, shape.points)

    @staticmethod
    def _draw_polyline(
        painter: QPainter, points: list[tuple[float, float]]
    ) -> None:
        """Нарисовать ломаную (штрих карандаша или ластика)."""
        if not points:
            return
        if len(points) == 1:
            x, y = points[0]
            painter.drawPoint(int(x), int(y))
            return
        for i in range(len(points) - 1):
            painter.drawLine(
                int(points[i][0]),
                int(points[i][1]),
                int(points[i + 1][0]),
                int(points[i + 1][1]),
            )

    def _draw_arrow(self, painter: QPainter, shape: DrawShape) -> None:
        """Нарисовать линию с наконечником стрелки."""
        (x1, y1), (x2, y2) = shape.points[0], shape.points[-1]
        painter.drawLine(int(x1), int(y1), int(x2), int(y2))
        head_len = _ARROWHEAD_BASE_LEN + shape.width * 2
        dx, dy = x2 - x1, y2 - y1
        length = (dx * dx + dy * dy) ** 0.5
        if length < 1e-6:
            return
        ux, uy = dx / length, dy / length
        cos_a = math.cos(_ARROWHEAD_ANGLE)
        sin_a = math.sin(_ARROWHEAD_ANGLE)
        for sign in (1.0, -1.0):
            # Назад от конца линии, поворот на ±угол
            wx = -ux * cos_a + uy * sign * sin_a
            wy = -uy * cos_a - ux * sign * sin_a
            painter.drawLine(
                int(x2),
                int(y2),
                int(x2 + wx * head_len),
                int(y2 + wy * head_len),
            )

    def resizeEvent(self, event: Any) -> None:
        """Держать тулбар по центру верхней кромки, щит — на весь экран."""
        if (
            hasattr(self, "_input_shield")
            and hasattr(self._input_shield, "resize")
            and hasattr(self, "size")
        ):
            size = self.size()
            self._input_shield.resize(size.width(), size.height())
        toolbar_width = self._toolbar.width()
        if isinstance(toolbar_width, int):
            self._toolbar.move(
                int(max((self.width() - toolbar_width) // 2, 0)),
                _TOOLBAR_MARGIN,
            )
        if hasattr(super(), "resizeEvent"):
            super().resizeEvent(event)
