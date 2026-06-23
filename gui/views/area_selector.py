"""
Графический выбор и предпросмотр области захвата.
"""

from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PyQt6.QtWidgets import QDialog, QWidget

from logger_config import get_module_logger

logger = get_module_logger(__name__)

RectCoords = tuple[int, int, int, int]
PointCoords = tuple[int, int]

MIN_SELECTION_SIZE = 8
RESIZE_HANDLE_SIZE = 12
PREVIEW_MARGIN = 10


def normalize_rect_coords(start: PointCoords, end: PointCoords) -> RectCoords:
    """
    Нормализовать координаты прямоугольника.

    Args:
        start: Первая точка.
        end: Вторая точка.

    Returns:
        Кортеж координат `(x1, y1, x2, y2)` с упорядоченными углами.
    """
    x1, y1 = start
    x2, y2 = end
    return (
        min(x1, x2),
        min(y1, y2),
        max(x1, x2),
        max(y1, y2),
    )


def rect_size(rect: RectCoords) -> tuple[int, int]:
    """
    Получить размер прямоугольника.

    Args:
        rect: Координаты прямоугольника.

    Returns:
        Ширина и высота.
    """
    return rect[2] - rect[0], rect[3] - rect[1]


def format_rect_coords(rect: RectCoords | None) -> str:
    """
    Сформировать строку с координатами области.

    Args:
        rect: Координаты прямоугольника.

    Returns:
        Строка для отображения в UI.
    """
    if rect is None:
        return ""
    return f"{rect[0]}, {rect[1]}, {rect[2]}, {rect[3]}"


def describe_rect(rect: RectCoords | None) -> str:
    """
    Сформировать краткое описание выбранной области.

    Args:
        rect: Координаты прямоугольника.

    Returns:
        Человекочитаемая сводка.
    """
    if rect is None:
        return "Область не выбрана"

    width, height = rect_size(rect)
    return f"Позиция: {rect[0]}, {rect[1]} · Размер: {width} × {height} px"


def point_in_rect(point: PointCoords, rect: RectCoords) -> bool:
    """
    Проверить, находится ли точка внутри прямоугольника.

    Args:
        point: Проверяемая точка.
        rect: Координаты прямоугольника.

    Returns:
        `True`, если точка лежит внутри прямоугольника.
    """
    x, y = point
    return rect[0] <= x <= rect[2] and rect[1] <= y <= rect[3]


def point_in_resize_handle(
    point: PointCoords,
    rect: RectCoords,
    handle_size: int = RESIZE_HANDLE_SIZE,
) -> bool:
    """
    Проверить попадание в маркер изменения размера.

    Args:
        point: Проверяемая точка.
        rect: Координаты прямоугольника.
        handle_size: Размер зоны маркера.

    Returns:
        `True`, если точка попала в правый нижний маркер.
    """
    x, y = point
    return (
        rect[2] - handle_size <= x <= rect[2] + handle_size
        and rect[3] - handle_size <= y <= rect[3] + handle_size
    )


def clamp_rect_to_bounds(
    rect: RectCoords,
    bounds: RectCoords,
) -> RectCoords:
    """
    Ограничить прямоугольник границами экрана.

    Args:
        rect: Координаты прямоугольника.
        bounds: Границы рабочей области.

    Returns:
        Прямоугольник, целиком помещающийся в границы.
    """
    left, top, right, bottom = rect
    min_x, min_y, max_x, max_y = bounds

    left = max(min_x, min(left, max_x))
    right = max(min_x, min(right, max_x))
    top = max(min_y, min(top, max_y))
    bottom = max(min_y, min(bottom, max_y))
    return normalize_rect_coords((left, top), (right, bottom))


def move_rect(
    rect: RectCoords,
    top_left: PointCoords,
    bounds: RectCoords,
) -> RectCoords:
    """
    Переместить прямоугольник, не выходя за границы экрана.

    Args:
        rect: Исходный прямоугольник.
        top_left: Новая верхняя левая точка.
        bounds: Границы экрана.

    Returns:
        Перемещённый прямоугольник.
    """
    width, height = rect_size(rect)
    min_x, min_y, max_x, max_y = bounds

    max_left = max(min_x, max_x - width)
    max_top = max(min_y, max_y - height)
    left = max(min_x, min(top_left[0], max_left))
    top = max(min_y, min(top_left[1], max_top))
    return (left, top, left + width, top + height)


def resize_rect(
    anchor: PointCoords,
    point: PointCoords,
    bounds: RectCoords,
) -> RectCoords:
    """
    Изменить размер прямоугольника от фиксированной опорной точки.

    Args:
        anchor: Зафиксированная точка прямоугольника.
        point: Новая точка перетаскивания.
        bounds: Границы экрана.

    Returns:
        Нормализованный и ограниченный прямоугольник.
    """
    return clamp_rect_to_bounds(
        normalize_rect_coords(anchor, point),
        bounds,
    )


def is_valid_selection(rect: RectCoords | None) -> bool:
    """
    Проверить, достаточно ли велика выбранная область.

    Args:
        rect: Координаты прямоугольника.

    Returns:
        `True`, если прямоугольник пригоден для использования.
    """
    if rect is None:
        return False
    width, height = rect_size(rect)
    return width >= MIN_SELECTION_SIZE and height >= MIN_SELECTION_SIZE


@dataclass(frozen=True)
class ScreenSize:
    """Размер экрана для превью."""

    width: int
    height: int


class SelectionPreviewWidget(QWidget):
    """
    Компактный виджет предпросмотра выбранной области.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Инициализировать виджет предпросмотра.

        Args:
            parent: Родительский виджет.
        """
        super().__init__(parent)
        self._screen = ScreenSize(width=1920, height=1080)
        self._rect_coords: RectCoords | None = None
        self.setMinimumHeight(96)

    def set_screen_size(self, width: int, height: int) -> None:
        """
        Обновить размер экрана, относительно которого строится превью.

        Args:
            width: Ширина экрана.
            height: Высота экрана.
        """
        self._screen = ScreenSize(
            width=max(width, 1),
            height=max(height, 1),
        )
        if hasattr(self, "update"):
            self.update()

    def set_rect_coords(self, coords: RectCoords | None) -> None:
        """
        Обновить выбранный прямоугольник.

        Args:
            coords: Координаты выбранной области.
        """
        self._rect_coords = coords
        if hasattr(self, "update"):
            self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        """Отрисовать мини-превью прямоугольной области."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        width = max(self.width(), 1)
        height = max(self.height(), 1)
        available_width = max(width - PREVIEW_MARGIN * 2, 1)
        available_height = max(height - PREVIEW_MARGIN * 2, 1)
        scale = min(
            available_width / self._screen.width,
            available_height / self._screen.height,
        )

        preview_width = int(self._screen.width * scale)
        preview_height = int(self._screen.height * scale)
        left = (width - preview_width) // 2
        top = (height - preview_height) // 2

        painter.setPen(QPen(QColor("#6b7280"), 1))
        painter.setBrush(QColor("#111827"))
        painter.drawRect(left, top, preview_width, preview_height)

        if self._rect_coords is None:
            painter.setPen(QColor("#9ca3af"))
            painter.drawText(
                left + 12,
                top + preview_height // 2,
                "Область пока не выбрана",
            )
            return

        rect_left = left + int(self._rect_coords[0] * scale)
        rect_top = top + int(self._rect_coords[1] * scale)
        rect_width = int((self._rect_coords[2] - self._rect_coords[0]) * scale)
        rect_height = int(
            (self._rect_coords[3] - self._rect_coords[1]) * scale
        )

        painter.setPen(QPen(QColor("#ef4444"), 2))
        painter.setBrush(QColor(239, 68, 68, 60))
        painter.drawRect(rect_left, rect_top, rect_width, rect_height)


class AreaSelectorDialog(QDialog):
    """
    Полноэкранный overlay для выбора прямоугольной области мышью.
    """

    selection_completed = pyqtSignal(tuple)

    def __init__(
        self,
        initial_rect: RectCoords | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """
        Инициализировать overlay выбора области.

        Args:
            initial_rect: Исходная выбранная область.
            parent: Родительский виджет.
        """
        super().__init__(parent)
        self._selection: RectCoords | None = initial_rect
        self._bounds = self._get_screen_bounds()
        self._drag_mode: str | None = None
        self._drag_origin: PointCoords | None = None
        self._move_offset: PointCoords = (0, 0)
        self._resize_anchor: PointCoords | None = None

        self._setup_window()

    @classmethod
    def select_area(
        cls,
        parent: QWidget | None = None,
        initial_rect: RectCoords | None = None,
    ) -> RectCoords | None:
        """
        Открыть overlay и вернуть выбранную область.

        Args:
            parent: Родительский виджет.
            initial_rect: Текущая область для повторного редактирования.

        Returns:
            Выбранные координаты или `None`, если пользователь отменил выбор.
        """
        selector = cls(initial_rect=initial_rect, parent=parent)
        result = selector.exec()
        dialog_code = getattr(QDialog, "DialogCode", None)
        if dialog_code is not None:
            return (
                selector.get_selected_rect()
                if result == QDialog.DialogCode.Accepted
                else None
            )
        return selector.get_selected_rect() if result else None

    def _setup_window(self) -> None:
        """Настроить свойства overlay-окна."""
        self.setWindowTitle("Выбор области захвата")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setModal(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        if hasattr(Qt, "WidgetAttribute") and hasattr(
            Qt.WidgetAttribute,
            "WA_TranslucentBackground",
        ):
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        left, top, right, bottom = self._bounds
        self.setGeometry(left, top, right - left, bottom - top)

    def _get_screen_bounds(self) -> RectCoords:
        """
        Получить геометрию основного экрана.

        Returns:
            Координаты границ экрана.
        """
        app = QGuiApplication.instance()
        if app is None:
            app = QGuiApplication([])

        screen = QGuiApplication.primaryScreen()
        if screen is None:
            logger.warning(
                "Не удалось получить primaryScreen, используется fallback"
            )
            return (0, 0, 1920, 1080)

        geometry = screen.geometry()
        return (
            geometry.left(),
            geometry.top(),
            geometry.right(),
            geometry.bottom(),
        )

    def get_selected_rect(self) -> RectCoords | None:
        """
        Получить текущую выбранную область.

        Returns:
            Координаты прямоугольника или `None`.
        """
        if is_valid_selection(self._selection):
            return self._selection
        return None

    def _event_point(self, event) -> PointCoords:
        """
        Извлечь координаты точки из Qt-события.

        Args:
            event: Qt mouse event.

        Returns:
            Пара координат.
        """
        position = getattr(event, "position", None)
        if callable(position):
            point = position()
            return int(point.x()), int(point.y())

        point = event.pos()
        return int(point.x()), int(point.y())

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """Начать создание, перемещение или изменение размера области."""
        if event.button() != Qt.MouseButton.LeftButton:
            return

        point = self._event_point(event)
        selection = self.get_selected_rect()

        if selection is not None and point_in_resize_handle(point, selection):
            self._drag_mode = "resize"
            self._resize_anchor = (selection[0], selection[1])
            return

        if selection is not None and point_in_rect(point, selection):
            self._drag_mode = "move"
            self._move_offset = (
                point[0] - selection[0],
                point[1] - selection[1],
            )
            return

        self._drag_mode = "new"
        self._drag_origin = point
        self._selection = normalize_rect_coords(point, point)
        if hasattr(self, "update"):
            self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        """Обновить текущую область по движению мыши."""
        if self._drag_mode is None:
            return

        point = self._event_point(event)

        if self._drag_mode == "new" and self._drag_origin is not None:
            self._selection = resize_rect(
                self._drag_origin,
                point,
                self._bounds,
            )
        elif self._drag_mode == "resize" and self._resize_anchor is not None:
            self._selection = resize_rect(
                self._resize_anchor,
                point,
                self._bounds,
            )
        elif self._drag_mode == "move" and self._selection is not None:
            self._selection = move_rect(
                self._selection,
                (
                    point[0] - self._move_offset[0],
                    point[1] - self._move_offset[1],
                ),
                self._bounds,
            )

        if hasattr(self, "update"):
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """Завершить текущее действие мышью."""
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if not is_valid_selection(self._selection):
            self._selection = None

        self._drag_mode = None
        self._drag_origin = None
        self._resize_anchor = None

        if hasattr(self, "update"):
            self.update()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        """Подтвердить выбор двойным кликом внутри области."""
        selection = self.get_selected_rect()
        if selection is None:
            return

        if point_in_rect(self._event_point(event), selection):
            self.selection_completed.emit(selection)
            self.accept()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        """Обработать горячие клавиши overlay."""
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.reject()
            return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            selection = self.get_selected_rect()
            if selection is not None:
                self.selection_completed.emit(selection)
                self.accept()
            return

        super().keyPressEvent(event)

    def paintEvent(self, _event) -> None:  # noqa: N802
        """Отрисовать затемнение, рамку выделения и подсказку."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 90))

        painter.setPen(QPen(QColor("#ffffff"), 1))
        painter.drawText(
            QRect(24, 12, self.width() - 48, 90),
            int(Qt.AlignmentFlag.AlignLeft | Qt.TextFlag.TextWordWrap),
            (
                "Потяните мышью для выбора области. "
                "Перетащите внутри рамки для перемещения, "
                "тяните правый нижний маркер для изменения размера, "
                "Enter — подтвердить, Esc — отменить."
            ),
        )

        selection = self.get_selected_rect()
        if selection is None:
            return

        width, height = rect_size(selection)

        painter.setPen(QPen(QColor("#ef4444"), 2))
        painter.setBrush(QColor(239, 68, 68, 45))
        painter.drawRect(
            selection[0],
            selection[1],
            width,
            height,
        )

        painter.setBrush(QColor("#ef4444"))
        painter.drawRect(
            selection[2] - 5,
            selection[3] - 5,
            10,
            10,
        )

        painter.setPen(QColor("#ffffff"))
        painter.drawText(
            selection[0],
            max(selection[1] - 10, 20),
            f"{width} × {height} px",
        )
