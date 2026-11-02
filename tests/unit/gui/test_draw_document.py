"""Unit-тесты модели быстрых аннотаций (#159)."""

from __future__ import annotations

import pytest

from gui.models.draw_document import (
    DrawDocument,
    DrawShape,
    DrawTool,
    point_segment_distance,
)


def _pen_shape(
    points: list[tuple[float, float]],
    width: float = 4.0,
    color: str = "#FF0000",
) -> DrawShape:
    """Карандашный штрих из списка точек."""
    return DrawShape(
        tool=DrawTool.PEN, points=points, color=color, width=width
    )


class TestDrawShape:
    """Фигура документа."""

    def test_fields_stored(self) -> None:
        shape = DrawShape(
            tool=DrawTool.RECT,
            points=[(0, 0), (10, 20)],
            color="#00FF00",
            width=8.0,
        )

        assert shape.tool is DrawTool.RECT
        assert shape.points == [(0, 0), (10, 20)]
        assert shape.color == "#00FF00"
        assert shape.width == 8.0


class TestPointSegmentDistance:
    """Геометрия расстояния точка-отрезок."""

    def test_perpendicular_distance(self) -> None:
        assert point_segment_distance(5, 3, 0, 0, 10, 0) == 3.0

    def test_beyond_endpoints_clamps(self) -> None:
        # Точка за концом отрезка — расстояние до ближайшего конца
        assert point_segment_distance(15, 0, 0, 0, 10, 0) == 5.0

    def test_degenerate_segment_is_point(self) -> None:
        assert point_segment_distance(3, 4, 0, 0, 0, 0) == 5.0


class TestDrawDocumentBasics:
    """Добавление фигур и чтение документа."""

    def test_empty_document(self) -> None:
        doc = DrawDocument()

        assert doc.is_empty()
        assert len(doc) == 0
        assert doc.shapes() == ()

    def test_add_shape_appends(self) -> None:
        doc = DrawDocument()
        shape = _pen_shape([(0, 0), (1, 1)])

        doc.add_shape(shape)

        assert list(doc) == [shape]
        assert not doc.is_empty()

    def test_add_shape_clears_redo(self) -> None:
        doc = DrawDocument()
        doc.add_shape(_pen_shape([(0, 0), (1, 1)]))
        doc.undo()

        doc.add_shape(_pen_shape([(2, 2), (3, 3)]))

        assert not doc.can_redo()


class TestDrawDocumentUndoRedo:
    """История отмен и возврата."""

    def test_undo_returns_last_shape(self) -> None:
        doc = DrawDocument()
        first = _pen_shape([(0, 0), (1, 1)])
        second = _pen_shape([(2, 2), (3, 3)])
        doc.add_shape(first)
        doc.add_shape(second)

        undone = doc.undo()

        assert undone is second
        assert list(doc) == [first]
        assert doc.can_redo()

    def test_redo_restores_shape(self) -> None:
        doc = DrawDocument()
        shape = _pen_shape([(0, 0), (1, 1)])
        doc.add_shape(shape)
        doc.undo()

        redone = doc.redo()

        assert redone is shape
        assert list(doc) == [shape]
        assert not doc.can_redo()

    def test_undo_on_empty_is_none(self) -> None:
        doc = DrawDocument()

        assert doc.undo() is None
        assert not doc.can_undo()

    def test_redo_without_history_is_none(self) -> None:
        doc = DrawDocument()

        assert doc.redo() is None

    def test_clear_removes_all_and_redo(self) -> None:
        doc = DrawDocument()
        doc.add_shape(_pen_shape([(0, 0), (1, 1)]))
        doc.add_shape(_pen_shape([(2, 2), (3, 3)]))
        doc.undo()

        removed = doc.clear()

        # В документе осталась 1 фигура (вторая была отменена)
        assert removed == 1
        assert doc.is_empty()
        assert not doc.can_redo()
        assert not doc.can_undo()

    @pytest.mark.parametrize("count", [1, 3, 10])
    def test_undo_sequence_depth(self, count: int) -> None:
        doc = DrawDocument()
        for i in range(count):
            doc.add_shape(_pen_shape([(i, i), (i + 1, i + 1)]))

        for _ in range(count):
            doc.undo()

        assert doc.is_empty()
        assert doc.undo() is None


class TestDrawDocumentErase:
    """Объектное стирание фигур ластиком."""

    def test_erase_pen_stroke_near_point(self) -> None:
        doc = DrawDocument()
        shape = _pen_shape([(100, 100), (200, 100)], width=4.0)
        doc.add_shape(shape)

        removed = doc.erase_at(150, 103, radius=5.0)

        assert removed == 1
        assert doc.is_empty()

    def test_erase_misses_distant_shape(self) -> None:
        doc = DrawDocument()
        doc.add_shape(_pen_shape([(100, 100), (200, 100)]))

        removed = doc.erase_at(150, 200, radius=5.0)

        assert removed == 0
        assert len(doc) == 1

    def test_erase_respects_pen_width(self) -> None:
        doc = DrawDocument()
        doc.add_shape(_pen_shape([(100, 100), (200, 100)], width=20.0))

        # 13px от линии: при width=20 порог = 10+radius > 13
        removed = doc.erase_at(150, 113, radius=5.0)

        assert removed == 1

    def test_erase_arrow_segment(self) -> None:
        doc = DrawDocument()
        arrow = DrawShape(
            tool=DrawTool.ARROW,
            points=[(0, 0), (100, 100)],
            color="#000000",
            width=4.0,
        )
        doc.add_shape(arrow)

        assert doc.erase_at(50, 50, radius=5.0) == 1

    def test_erase_rect_boundary_not_interior(self) -> None:
        doc = DrawDocument()
        rect = DrawShape(
            tool=DrawTool.RECT,
            points=[(0, 0), (100, 100)],
            color="#000000",
            width=4.0,
        )
        doc.add_shape(rect)

        # Точка на границе — попадание; внутри далеко от границы — мимо
        assert doc.erase_at(50, 1, radius=5.0) == 1

    def test_rect_interior_far_from_boundary_survives(self) -> None:
        doc = DrawDocument()
        rect = DrawShape(
            tool=DrawTool.RECT,
            points=[(0, 0), (100, 100)],
            color="#000000",
            width=2.0,
        )
        doc.add_shape(rect)

        assert doc.erase_at(50, 50, radius=5.0) == 0
        assert len(doc) == 1

    def test_erase_ellipse_boundary(self) -> None:
        doc = DrawDocument()
        ellipse = DrawShape(
            tool=DrawTool.ELLIPSE,
            points=[(0, 0), (200, 100)],
            color="#000000",
            width=4.0,
        )
        doc.add_shape(ellipse)
        # Центр эллипса (100, 50); граница справа (200, 50)
        assert doc.erase_at(200, 50, radius=6.0) == 1

    def test_eraser_strokes_not_deleted_by_erase_at(self) -> None:
        doc = DrawDocument()
        eraser = DrawShape(
            tool=DrawTool.ERASER,
            points=[(50, 50), (60, 60)],
            color="#000000",
            width=4.0,
        )
        doc.add_shape(eraser)

        assert doc.erase_at(55, 55, radius=10.0) == 0
        assert len(doc) == 1

    def test_erase_clears_redo_stack(self) -> None:
        doc = DrawDocument()
        doc.add_shape(_pen_shape([(0, 0), (10, 10)]))
        doc.add_shape(_pen_shape([(20, 20), (30, 30)]))
        doc.undo()

        doc.erase_at(5, 5, radius=5.0)

        assert not doc.can_redo()

    def test_erase_nothing_keeps_redo_stack(self) -> None:
        doc = DrawDocument()
        doc.add_shape(_pen_shape([(0, 0), (10, 10)]))
        doc.undo()

        doc.erase_at(500, 500, radius=5.0)

        assert doc.can_redo()
