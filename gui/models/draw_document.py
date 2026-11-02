"""
Модель быстрых аннотаций (#159)
===============================

Чистый Python-документ фигур для overlay-рисования: штрихи карандаша,
стрелки, прямоугольники, эллипсы и ластик (штрих, вырезающий
нарисованное). Не зависит от Qt — вся геометрия в кортежах float,
что позволяет юнит-тестировать undo/redo/eraser без QPainter.

Слой QSS-отрисовки — ``gui.views.draw_overlay.DrawOverlayWidget``.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum

# Радиус захвата ластика по умолчанию вокруг курсора
DEFAULT_ERASER_RADIUS = 12.0
# Количество сегментов при аппроксимации границы эллипса
_ELLIPSE_APPROX_SEGMENTS = 48


class DrawTool(StrEnum):
    """Инструменты режима рисования."""

    PEN = "pen"
    ARROW = "arrow"
    RECT = "rect"
    ELLIPSE = "ellipse"
    ERASER = "eraser"


@dataclass(slots=True)
class DrawShape:
    """Одна фигура на документе аннотаций.

    Attributes:
        tool: Инструмент, которым фигура создана.
        points: Опорные точки. Для pen/eraser — последовательные точки
            штриха (>= 2); для arrow — [начало, конец]; для rect/ellipse —
            [первый угол, противоположный угол].
        color: HEX-цвет пера (для eraser игнорируется).
        width: Толщина пера в пикселях.
    """

    tool: DrawTool
    points: list[tuple[float, float]]
    color: str
    width: float


def point_segment_distance(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
) -> float:
    """Расстояние от точки до отрезка (для захвата ластика)."""
    dx = bx - ax
    dy = by - ay
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-9:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / length_sq
    t = max(0.0, min(1.0, t))
    closest_x = ax + t * dx
    closest_y = ay + t * dy
    return math.hypot(px - closest_x, py - closest_y)


class DrawDocument:
    """Документ аннотаций с undo/redo и стиранием.

    Ластик — это обычный штрих с ``tool=ERASER``: при отрисовке он
    вырезает прозрачность, а undo/redo работают с ним так же, как с
    любой другой фигурой.
    """

    def __init__(self) -> None:
        self._shapes: list[DrawShape] = []
        self._redo_stack: list[DrawShape] = []

    # === Чтение ===

    def shapes(self) -> tuple[DrawShape, ...]:
        """Все фигуры документа в порядке добавления."""
        return tuple(self._shapes)

    def __iter__(self) -> Iterator[DrawShape]:
        return iter(self._shapes)

    def __len__(self) -> int:
        return len(self._shapes)

    def is_empty(self) -> bool:
        """Нет ли на документе ни одной фигуры."""
        return not self._shapes

    # === Изменение ===

    def add_shape(self, shape: DrawShape) -> None:
        """Добавить фигуру; история redo сбрасывается.

        Args:
            shape: Готовая фигура (создаётся вью-слоем).
        """
        self._shapes.append(shape)
        self._redo_stack.clear()

    def undo(self) -> DrawShape | None:
        """Отменить последнюю фигуру.

        Returns:
            Отменённая фигура или None, если документ пуст.
        """
        if not self._shapes:
            return None
        shape = self._shapes.pop()
        self._redo_stack.append(shape)
        return shape

    def redo(self) -> DrawShape | None:
        """Вернуть последнюю отменённую фигуру.

        Returns:
            Возвращённая фигура или None, если redo-история пуста.
        """
        if not self._redo_stack:
            return None
        shape = self._redo_stack.pop()
        self._shapes.append(shape)
        return shape

    def can_undo(self) -> bool:
        """Можно ли отменить последнюю фигуру."""
        return bool(self._shapes)

    def can_redo(self) -> bool:
        """Есть ли отменённые фигуры для возврата."""
        return bool(self._redo_stack)

    def clear(self) -> int:
        """Очистить документ целиком.

        Returns:
            Количество удалённых фигур.
        """
        removed = len(self._shapes)
        self._shapes.clear()
        self._redo_stack.clear()
        return removed

    # === Стирание ===

    def erase_at(self, x: float, y: float, radius: float) -> int:
        """Удалить фигуры, задетые точкой с радиусом захвата.

        Используется объектным ластиком (клик/drag по фигуре). Штрихи
        ластика ``tool=ERASER`` в документе сами по себе не удаляются
        этим методом — они и есть «резинка» при отрисовке.

        Args:
            x: X точки курсора.
            y: Y точки курсора.
            radius: Радиус захвата вокруг точки.

        Returns:
            Количество удалённых фигур.
        """
        remaining: list[DrawShape] = []
        removed = 0
        for shape in self._shapes:
            if shape.tool is DrawTool.ERASER or not self._hit_shape(
                shape, x, y, radius
            ):
                remaining.append(shape)
            else:
                removed += 1
        if removed:
            self._shapes = remaining
            self._redo_stack.clear()
        return removed

    @staticmethod
    def _hit_shape(
        shape: DrawShape, x: float, y: float, radius: float
    ) -> bool:
        """Проверить, задевает ли точка с радиусом фигуру."""
        threshold = shape.width / 2 + radius
        if shape.tool in (DrawTool.PEN, DrawTool.ERASER):
            pts = shape.points
            if len(pts) == 1:
                return math.hypot(x - pts[0][0], y - pts[0][1]) <= threshold
            return any(
                point_segment_distance(
                    x, y, pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1]
                )
                <= threshold
                for i in range(len(pts) - 1)
            )
        if shape.tool is DrawTool.ARROW:
            (ax, ay), (bx, by) = shape.points[0], shape.points[-1]
            return point_segment_distance(x, y, ax, ay, bx, by) <= threshold
        if shape.tool is DrawTool.RECT:
            (x1, y1), (x2, y2) = shape.points[0], shape.points[-1]
            left, right = min(x1, x2), max(x1, x2)
            top, bottom = min(y1, y2), max(y1, y2)
            corners = [
                (left, top),
                (right, top),
                (right, bottom),
                (left, bottom),
            ]
            # Граница прямоугольника = четыре отрезка-стороны
            return any(
                point_segment_distance(
                    x,
                    y,
                    corners[i][0],
                    corners[i][1],
                    corners[(i + 1) % 4][0],
                    corners[(i + 1) % 4][1],
                )
                <= threshold
                for i in range(4)
            )
        # ELLIPSE: аппроксимация границы сегментами
        (x1, y1), (x2, y2) = shape.points[0], shape.points[-1]
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        rx, ry = abs(x2 - x1) / 2, abs(y2 - y1) / 2
        if rx <= 1e-9 and ry <= 1e-9:
            return math.hypot(x - cx, y - cy) <= threshold
        prev = (cx + rx, cy)
        for i in range(1, _ELLIPSE_APPROX_SEGMENTS + 1):
            angle = 2 * math.pi * i / _ELLIPSE_APPROX_SEGMENTS
            cur = (cx + rx * math.cos(angle), cy + ry * math.sin(angle))
            if (
                point_segment_distance(x, y, prev[0], prev[1], cur[0], cur[1])
                <= threshold
            ):
                return True
            prev = cur
        return False
