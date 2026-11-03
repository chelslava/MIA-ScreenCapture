"""Unit-тесты оверлея рисования поверх экрана (#159)."""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from gui.models.draw_document import DrawTool
from gui.views.draw_overlay import (
    DEFAULT_DRAW_COLOR,
    DEFAULT_DRAW_WIDTH,
    DRAW_COLORS,
    DrawOverlayWidget,
    DrawToolbar,
)


class _FakePoint:
    """Точка с x()/y() как QPointF."""

    def __init__(self, x: float, y: float) -> None:
        self._x = x
        self._y = y

    def x(self) -> float:
        return self._x

    def y(self) -> float:
        return self._y


class _FakeEvent:
    """Qt-событие мыши с position()."""

    def __init__(self, x: float, y: float) -> None:
        self._pos = _FakePoint(x, y)

    def position(self) -> _FakePoint:
        return self._pos


class TestDrawToolbar:
    """Тулбар инструментов оверлея."""

    @staticmethod
    def _make_toolbar() -> DrawToolbar:
        toolbar = DrawToolbar()
        return toolbar

    def test_default_tool_is_pen(self) -> None:
        toolbar = self._make_toolbar()

        toolbar.set_tool(DrawTool.PEN.value)

        pen_btn = toolbar._tool_buttons[DrawTool.PEN]
        other_btn = toolbar._tool_buttons[DrawTool.ARROW]
        assert pen_btn.isChecked()
        assert not other_btn.isChecked()

    def test_unknown_tool_is_ignored(self) -> None:
        toolbar = self._make_toolbar()

        toolbar.set_tool("broken")  # не должно упасть

        assert toolbar._tool_buttons[DrawTool.PEN].isChecked()

    def test_tool_changed_signal(self) -> None:
        toolbar = self._make_toolbar()
        received: list[str] = []
        toolbar.tool_changed.connect(received.append)

        toolbar._tool_buttons[DrawTool.RECT].clicked.emit()

        assert received == [DrawTool.RECT.value]

    def test_color_changed_signal(self) -> None:
        toolbar = self._make_toolbar()
        received: list[str] = []

        toolbar.color_changed.connect(received.append)
        toolbar.color_changed.emit("#FF3B30")

        assert received == ["#FF3B30"]
        assert len(DRAW_COLORS) == 5

    def test_width_changed_on_combo(self) -> None:
        toolbar = self._make_toolbar()
        received: list[float] = []
        toolbar.width_changed.connect(received.append)

        toolbar._on_width_index_changed(2)

        assert received == [8.0]

    def test_width_index_out_of_range_defaults_to_4(self) -> None:
        toolbar = self._make_toolbar()
        received: list[float] = []
        toolbar.width_changed.connect(received.append)

        toolbar._on_width_index_changed(-1)

        assert received == [4.0]

    def test_action_signals_routed(self) -> None:
        toolbar = self._make_toolbar()
        got: dict[str, bool] = {}

        toolbar.undo_requested.connect(lambda: got.setdefault("undo", True))
        toolbar.redo_requested.connect(lambda: got.setdefault("redo", True))
        toolbar.clear_requested.connect(lambda: got.setdefault("clear", True))
        toolbar.screenshot_requested.connect(
            lambda: got.setdefault("screenshot", True)
        )
        toolbar.close_requested.connect(lambda: got.setdefault("close", True))

        for action in ("undo", "redo", "clear", "screenshot", "close"):
            toolbar._emit_action(action)

        assert got == {
            "undo": True,
            "redo": True,
            "clear": True,
            "screenshot": True,
            "close": True,
        }


class TestDrawOverlayTools:
    """Состояние инструментов оверлея."""

    @staticmethod
    def _make_overlay() -> DrawOverlayWidget:
        return DrawOverlayWidget()

    def test_defaults(self) -> None:
        overlay = self._make_overlay()

        assert overlay.tool() == DrawTool.PEN.value
        assert overlay.color() == DEFAULT_DRAW_COLOR
        assert overlay.pen_width() == DEFAULT_DRAW_WIDTH
        assert overlay.document.is_empty()

    def test_set_tool_valid_and_invalid(self) -> None:
        overlay = self._make_overlay()

        overlay.set_tool(DrawTool.ELLIPSE.value)
        assert overlay.tool() == DrawTool.ELLIPSE.value

        overlay.set_tool("nope")
        assert overlay.tool() == DrawTool.ELLIPSE.value

    def test_set_color_and_width(self) -> None:
        overlay = self._make_overlay()

        overlay.set_color("#007AFF")
        overlay.set_width(8.0)

        assert overlay.color() == "#007AFF"
        assert overlay.pen_width() == 8.0

    def test_non_positive_width_ignored(self) -> None:
        overlay = self._make_overlay()

        overlay.set_width(0)
        overlay.set_width(-3)

        assert overlay.pen_width() == DEFAULT_DRAW_WIDTH


class TestDrawOverlayDrawing:
    """Мышь: создание фигур, undo/redo, очистка."""

    @staticmethod
    def _make_overlay() -> DrawOverlayWidget:
        overlay = DrawOverlayWidget()
        overlay._request_repaint = MagicMock()
        return overlay

    def test_pen_stroke_flow(self) -> None:
        overlay = self._make_overlay()

        overlay.mousePressEvent(_FakeEvent(10, 20))
        overlay.mouseMoveEvent(_FakeEvent(30, 40))
        overlay.mouseMoveEvent(_FakeEvent(50, 60))
        overlay.mouseReleaseEvent(_FakeEvent(50, 60))

        shapes = overlay.document.shapes()
        assert len(shapes) == 1
        assert shapes[0].tool is DrawTool.PEN
        assert shapes[0].points == [(10.0, 20.0), (30.0, 40.0), (50.0, 60.0)]

    def test_single_click_creates_dot(self) -> None:
        overlay = self._make_overlay()

        overlay.mousePressEvent(_FakeEvent(10, 10))
        overlay.mouseReleaseEvent(_FakeEvent(10, 10))

        shapes = overlay.document.shapes()
        assert shapes[0].points == [(10.0, 10.0), (10.0, 10.0)]

    def test_rect_flow_updates_second_corner(self) -> None:
        overlay = self._make_overlay()
        overlay.set_tool(DrawTool.RECT.value)

        overlay.mousePressEvent(_FakeEvent(0, 0))
        overlay.mouseMoveEvent(_FakeEvent(80, 40))
        overlay.mouseReleaseEvent(_FakeEvent(100, 60))

        shape = overlay.document.shapes()[0]
        assert shape.points == [(0.0, 0.0), (100.0, 60.0)]
        assert shape.color == DEFAULT_DRAW_COLOR

    def test_arrow_flow(self) -> None:
        overlay = self._make_overlay()
        overlay.set_tool(DrawTool.ARROW.value)

        overlay.mousePressEvent(_FakeEvent(5, 5))
        overlay.mouseReleaseEvent(_FakeEvent(95, 95))

        assert overlay.document.shapes()[0].tool is DrawTool.ARROW

    def test_eraser_shape_uses_current_width(self) -> None:
        overlay = self._make_overlay()
        overlay.set_tool(DrawTool.ERASER.value)
        overlay.set_width(6.0)

        overlay.mousePressEvent(_FakeEvent(1, 1))
        overlay.mouseReleaseEvent(_FakeEvent(9, 9))

        shape = overlay.document.shapes()[0]
        assert shape.tool is DrawTool.ERASER
        assert shape.width == 6.0

    def test_move_release_without_press_is_noop(self) -> None:
        overlay = self._make_overlay()

        overlay.mouseMoveEvent(_FakeEvent(1, 1))
        overlay.mouseReleaseEvent(_FakeEvent(2, 2))

        assert overlay.document.is_empty()

    def test_undo_and_redo(self) -> None:
        overlay = self._make_overlay()
        overlay.mousePressEvent(_FakeEvent(0, 0))
        overlay.mouseReleaseEvent(_FakeEvent(9, 9))

        overlay.undo()
        assert overlay.document.is_empty()

        overlay.redo()
        assert len(overlay.document) == 1

    def test_clear_annotations(self) -> None:
        overlay = self._make_overlay()
        overlay.mousePressEvent(_FakeEvent(0, 0))
        overlay.mouseReleaseEvent(_FakeEvent(9, 9))

        overlay.clear_annotations()

        assert overlay.document.is_empty()


class TestDrawOverlayThreeWindows:
    """Схема трёх окон: ловушка ввода + визуальный слой + тулбар (#159)."""

    def test_visual_layer_is_transparent_for_input(self) -> None:
        overlay = DrawOverlayWidget()

        assert overlay.autoFillBackground() is False

    def test_input_window_created_and_linked(self) -> None:
        overlay = DrawOverlayWidget()

        assert overlay._input_window is not None
        assert overlay._input_window._forward is overlay

    def test_toolbar_is_separate_window(self) -> None:
        overlay = DrawOverlayWidget()

        # Тулбар без родителя — самостоятельное топ-левел окно
        assert overlay._toolbar is not None

    def test_open_shows_input_visual_and_toolbar(self) -> None:
        overlay = DrawOverlayWidget()
        overlay.show = MagicMock()
        overlay.raise_ = MagicMock()
        overlay.showFullScreen = MagicMock()
        overlay._input_window = MagicMock()
        overlay._toolbar = MagicMock()

        overlay.open_overlay()

        overlay.show.assert_called_once()
        overlay._input_window.show.assert_called_once()
        overlay._input_window.activateWindow.assert_called_once()
        overlay._toolbar.show.assert_called_once()
        overlay._toolbar.raise_.assert_called_once()

    def test_close_hides_all_three_windows(self) -> None:
        overlay = DrawOverlayWidget()
        overlay.hide = MagicMock()
        overlay.closed = MagicMock()
        overlay._input_window = MagicMock()
        overlay._toolbar = MagicMock()

        overlay.close_overlay()

        overlay.hide.assert_called_once()
        overlay._input_window.hide.assert_called_once()
        overlay._toolbar.hide.assert_called_once()
        overlay.closed.emit.assert_called_once()

    def test_input_forwards_press_to_overlay(self) -> None:
        overlay = DrawOverlayWidget()
        overlay._on_press = MagicMock()
        event = SimpleNamespace(position=lambda: _FakePoint(11, 22))

        overlay._input_window.mousePressEvent(event)

        overlay._on_press.assert_called_once_with(event)

    def test_input_forwards_keys_to_overlay(self) -> None:
        overlay = DrawOverlayWidget()
        overlay.keyPressEvent = MagicMock()
        event = SimpleNamespace()

        overlay._input_window.keyPressEvent(event)

        overlay.keyPressEvent.assert_called_once_with(event)


class TestDrawToolbarKeys:
    """Клавиатура тулбара и флаг ловушки (#159)."""

    def test_toolbar_forwards_keys_to_overlay(self) -> None:
        overlay = DrawOverlayWidget()
        overlay.keyPressEvent = MagicMock()
        event = SimpleNamespace()

        overlay._toolbar.keyPressEvent(event)

        overlay.keyPressEvent.assert_called_once_with(event)

    def test_toolbar_without_forward_is_noop(self) -> None:
        toolbar = DrawToolbar(None)

        toolbar.keyPressEvent(SimpleNamespace())  # не должно упасть

    def test_input_window_does_not_accept_focus(self) -> None:
        # Реальные int-значения Qt.WindowType: под моками conftest
        # setWindowFlags запоминает аргумент
        fake_wt = SimpleNamespace(
            FramelessWindowHint=1,
            WindowStaysOnTopHint=2,
            Tool=4,
            WindowDoesNotAcceptFocus=8,
            WindowTransparentForInput=16,
        )
        # Остальные обращения (CursorShape, FocusPolicy, WidgetAttribute)
        # под моками conftest безразличны — добиваем их MagicMock
        fake_qt = MagicMock()
        fake_qt.WindowType = fake_wt

        with patch("gui.views.draw_overlay.Qt", fake_qt):
            overlay = DrawOverlayWidget()

        flags = overlay._input_window.windowFlags()

        # Ловушка не активируется кликами: иначе поднимается над
        # тулбаром и перехватывает кнопки
        assert flags & 8  # WindowDoesNotAcceptFocus
        assert flags == 1 | 2 | 4 | 8


class TestDrawOverlayLifecycle:
    """Показ/скрытие оверлея и клавиатура."""

    @staticmethod
    def _make_overlay() -> DrawOverlayWidget:
        overlay = DrawOverlayWidget()
        overlay.show = MagicMock()
        overlay.raise_ = MagicMock()
        overlay.hide = MagicMock()
        overlay.closed = MagicMock()
        return overlay

    def test_open_overlay_shows_all_windows(self) -> None:
        overlay = self._make_overlay()
        overlay._input_window = MagicMock()
        overlay._toolbar = MagicMock()

        overlay.open_overlay()

        overlay.show.assert_called_once()
        overlay.raise_.assert_called_once()
        overlay._input_window.show.assert_called_once()
        overlay._toolbar.show.assert_called_once()

    def test_close_overlay_hides_and_emits(self) -> None:
        overlay = self._make_overlay()

        overlay.close_overlay()

        overlay.hide.assert_called_once()
        overlay.closed.emit.assert_called_once()

    def test_close_overlay_drops_active_shape_and_clears(self) -> None:
        overlay = self._make_overlay()
        overlay._request_repaint = MagicMock()
        overlay.mousePressEvent(_FakeEvent(1, 1))
        overlay.mouseReleaseEvent(_FakeEvent(9, 9))
        assert len(overlay.document) == 1

        overlay.close_overlay()

        # Аннотации не переживают выход (черновик поверх экрана)
        assert overlay._active_shape is None
        assert overlay.document.is_empty()

    def test_keypress_escape_closes(self) -> None:
        overlay = self._make_overlay()
        fake_qt = SimpleNamespace(
            KeyboardModifier=SimpleNamespace(
                ControlModifier=MagicMock(name="ctrl")
            ),
            Key=SimpleNamespace(
                Key_Z=MagicMock(), Key_Y=MagicMock(), Key_Escape="esc"
            ),
        )
        event = SimpleNamespace(modifiers=None, key=lambda: "esc")

        with patch("gui.views.draw_overlay.Qt", fake_qt):
            overlay.keyPressEvent(event)

        overlay.hide.assert_called_once()

    def test_keypress_ctrl_z_undoes(self) -> None:
        overlay = self._make_overlay()
        overlay._request_repaint = MagicMock()
        overlay.mousePressEvent(_FakeEvent(0, 0))
        overlay.mouseReleaseEvent(_FakeEvent(9, 9))
        ctrl = MagicMock()
        fake_qt = SimpleNamespace(
            KeyboardModifier=SimpleNamespace(ControlModifier=ctrl),
            Key=SimpleNamespace(Key_Z="z", Key_Y="y", Key_Escape="esc"),
        )
        event = SimpleNamespace(modifiers=ctrl, key=lambda: "z")

        with patch("gui.views.draw_overlay.Qt", fake_qt):
            overlay.keyPressEvent(event)

        assert overlay.document.is_empty()

    def test_keypress_ctrl_y_redoes(self) -> None:
        overlay = self._make_overlay()
        overlay._request_repaint = MagicMock()
        overlay.mousePressEvent(_FakeEvent(0, 0))
        overlay.mouseReleaseEvent(_FakeEvent(9, 9))
        overlay.undo()
        ctrl = MagicMock()
        fake_qt = SimpleNamespace(
            KeyboardModifier=SimpleNamespace(ControlModifier=ctrl),
            Key=SimpleNamespace(Key_Z="z", Key_Y="y", Key_Escape="esc"),
        )
        event = SimpleNamespace(modifiers=ctrl, key=lambda: "y")

        with patch("gui.views.draw_overlay.Qt", fake_qt):
            overlay.keyPressEvent(event)

        assert len(overlay.document) == 1

    def test_keypress_unknown_key_is_noop(self) -> None:
        overlay = self._make_overlay()
        fake_qt = SimpleNamespace(
            KeyboardModifier=SimpleNamespace(ControlModifier=object()),
            Key=SimpleNamespace(Key_Z="z", Key_Y="y", Key_Escape="esc"),
        )
        event = SimpleNamespace(modifiers=None, key=lambda: "f9")

        with patch("gui.views.draw_overlay.Qt", fake_qt):
            overlay.keyPressEvent(event)  # не должно упасть

        overlay.hide.assert_not_called()


class TestDrawOverlayScreenshot:
    """Скриншот аннотированного экрана (#159)."""

    def test_take_screenshot_saves_png(self, tmp_path) -> None:
        overlay = DrawOverlayWidget()
        pixmap = MagicMock()
        pixmap.save.return_value = True
        overlay._grab_composited_screen = MagicMock(return_value=pixmap)
        received: list[str] = []
        overlay.screenshot_taken.connect(received.append)

        result = overlay.take_screenshot(tmp_path)

        assert result is not None
        assert result.parent == tmp_path
        assert result.suffix == ".png"
        pixmap.save.assert_called_once()
        assert received == [str(result)]

    def test_take_screenshot_without_screen_returns_none(
        self, tmp_path
    ) -> None:
        overlay = DrawOverlayWidget()
        overlay._grab_composited_screen = MagicMock(return_value=None)

        assert overlay.take_screenshot(tmp_path) is None

    def test_take_screenshot_save_failure_returns_none(self, tmp_path) -> None:
        overlay = DrawOverlayWidget()
        pixmap = MagicMock()
        pixmap.save.return_value = False
        overlay._grab_composited_screen = MagicMock(return_value=pixmap)

        assert overlay.take_screenshot(tmp_path) is None

    def test_take_screenshot_os_error_returns_none(self, tmp_path) -> None:
        overlay = DrawOverlayWidget()
        pixmap = MagicMock()
        overlay._grab_composited_screen = MagicMock(return_value=pixmap)
        # Каталог-файл вместо папки → OSError при mkdir
        blocking = tmp_path / "blocked"
        blocking.write_text("not a dir", encoding="utf-8")

        assert overlay.take_screenshot(blocking / "sub") is None

    def test_grab_composited_hides_and_restores(self) -> None:
        overlay = DrawOverlayWidget()
        overlay.isVisible = MagicMock(return_value=True)
        overlay.hide = MagicMock()
        overlay.show = MagicMock()
        overlay.render = MagicMock()
        overlay._toolbar = MagicMock()
        overlay._toolbar.isVisible = MagicMock(return_value=True)
        base_pixmap = MagicMock()
        annotations_pixmap = MagicMock()
        screen = MagicMock()
        screen.grabWindow.return_value = base_pixmap
        gui_app = MagicMock(primaryScreen=MagicMock(return_value=screen))

        # from-import внутри метода читает sys.modules — патчим модуль
        gui_module = sys.modules["PyQt6.QtGui"]
        with (
            patch.object(gui_module, "QGuiApplication", gui_app),
            patch("PyQt6.QtWidgets.QApplication") as app_mock,
            patch(
                "gui.views.draw_overlay.QPixmap",
                MagicMock(return_value=annotations_pixmap),
            ),
            patch("gui.views.draw_overlay.QPainter"),
        ):
            result = overlay._grab_composited_screen()

        assert result is base_pixmap
        overlay.hide.assert_called_once()
        overlay.show.assert_called_once()
        overlay._toolbar.hide.assert_called_once()
        overlay._toolbar.show.assert_called_once()
        app_mock.processEvents.assert_called_once()
        annotations_pixmap.fill.assert_called_once()
        overlay.render.assert_called_once_with(annotations_pixmap)

    def test_grab_composited_without_screen_returns_none(self) -> None:
        overlay = DrawOverlayWidget()
        overlay.isVisible = MagicMock(return_value=False)
        gui_app = MagicMock(primaryScreen=MagicMock(return_value=None))

        gui_module = sys.modules["PyQt6.QtGui"]
        with patch.object(gui_module, "QGuiApplication", gui_app):
            assert overlay._grab_composited_screen() is None

    def test_on_screenshot_uses_output_path(self) -> None:
        overlay = DrawOverlayWidget()
        overlay.take_screenshot = MagicMock()
        config_mock = MagicMock()
        config_mock.settings.output.default_path = "D:/out"

        with patch("config.get_config", return_value=config_mock):
            overlay._on_screenshot()

        overlay.take_screenshot.assert_called_once()


class TestDrawOverlayPaint:
    """paintEvent не падает под моками и рисует все фигуры."""

    def test_paint_event_with_shapes(self) -> None:
        overlay = DrawOverlayWidget()
        overlay.set_width(4.0)
        overlay.mousePressEvent(_FakeEvent(0, 0))
        overlay.mouseMoveEvent(_FakeEvent(50, 50))
        overlay.mouseReleaseEvent(_FakeEvent(50, 50))
        overlay.set_tool(DrawTool.RECT.value)
        overlay.mousePressEvent(_FakeEvent(1, 1))
        overlay.mouseReleaseEvent(_FakeEvent(20, 20))
        overlay.set_tool(DrawTool.ELLIPSE.value)
        overlay.mousePressEvent(_FakeEvent(2, 2))
        overlay.mouseReleaseEvent(_FakeEvent(30, 30))
        overlay.set_tool(DrawTool.ARROW.value)
        overlay.mousePressEvent(_FakeEvent(3, 3))
        overlay.mouseReleaseEvent(_FakeEvent(40, 40))
        overlay.set_tool(DrawTool.ERASER.value)
        overlay.mousePressEvent(_FakeEvent(4, 4))
        overlay.mouseReleaseEvent(_FakeEvent(44, 44))
        overlay.set_tool(DrawTool.PEN.value)

        overlay.paintEvent(MagicMock())  # не должно упасть

        assert len(overlay.document) == 5

    def test_paint_event_empty_document(self) -> None:
        overlay = DrawOverlayWidget()

        overlay.paintEvent(MagicMock())

        assert overlay.document.is_empty()

    def test_paint_with_active_shape(self) -> None:
        overlay = DrawOverlayWidget()
        overlay._request_repaint = MagicMock()
        overlay.mousePressEvent(_FakeEvent(7, 7))

        overlay.paintEvent(MagicMock())

        assert overlay._active_shape is not None
        overlay.mouseReleaseEvent(_FakeEvent(8, 8))


class TestDrawOverlayHotkeyIntegration:
    """Интеграция режима рисования с реестром действий (#159)."""

    def test_action_spec_registered(self) -> None:
        from gui.desktop_actions import (
            DesktopActionId,
            get_desktop_action_spec,
        )

        spec = get_desktop_action_spec(DesktopActionId.TOGGLE_DRAW_OVERLAY)

        assert spec.shortcut == "Ctrl+D"
        assert "рисован" in spec.title.lower()

    def test_main_window_toggles_overlay(self) -> None:
        from tests.unit.gui.test_main_window import _build_window

        window = _build_window()
        window._draw_overlay = None
        window.status_bar = MagicMock()
        window._show_toast = MagicMock()

        with patch("gui.main_window.DrawOverlayWidget") as overlay_cls:
            overlay = overlay_cls.return_value
            overlay.isVisible = MagicMock(return_value=False)
            window.toggle_draw_overlay_mode()

        overlay_cls.assert_called_once()
        overlay.open_overlay.assert_called_once()
        overlay.screenshot_taken.connect.assert_called_once()
        window.status_bar.showMessage.assert_called_once()

    def test_main_window_toggles_visible_overlay_closed(self) -> None:
        from tests.unit.gui.test_main_window import _build_window

        window = _build_window()
        overlay = MagicMock()
        overlay.isVisible = MagicMock(return_value=True)
        window._draw_overlay = overlay

        window.toggle_draw_overlay_mode()

        overlay.close_overlay.assert_called_once()

    def test_main_window_desktop_action_executes(self) -> None:
        from gui.desktop_actions import (
            DesktopAction,
            DesktopActionId,
        )
        from tests.unit.gui.test_main_window import _build_window

        window = _build_window()
        window._toggle_draw_overlay = MagicMock()
        window._desktop_actions.register(
            DesktopAction(
                action_id=DesktopActionId.TOGGLE_DRAW_OVERLAY,
                title="Режим рисования",
                description="Тест",
                callback=window._toggle_draw_overlay,
                shortcut="Ctrl+D",
            )
        )

        assert window._desktop_actions.execute(
            DesktopActionId.TOGGLE_DRAW_OVERLAY
        )
        window._toggle_draw_overlay.assert_called_once()

    def test_screenshot_taken_shows_toast(self) -> None:
        from tests.unit.gui.test_main_window import _build_window

        window = _build_window()
        window._show_toast = MagicMock()

        window._on_draw_screenshot_taken("D:/out/annotation_1.png")

        window._show_toast.assert_called_once()
        assert "D:/out/annotation_1.png" in window._show_toast.call_args[0][0]

    def test_close_event_hides_visible_overlay(self) -> None:
        from tests.unit.gui.test_main_window import _build_window

        window = _build_window()
        window.close_requested = MagicMock()
        window._thread_tracker = MagicMock()
        overlay = MagicMock()
        overlay.isVisible = MagicMock(return_value=True)
        window._draw_overlay = overlay
        event = MagicMock()
        event.isAccepted.return_value = True

        window.closeEvent(event)

        overlay.close_overlay.assert_called_once()

    def test_global_hotkey_registered_in_defaults(self) -> None:
        from gui.hotkeys import GlobalHotkeys, HotkeyAction

        assert (
            GlobalHotkeys.DEFAULT_HOTKEYS[HotkeyAction.TOGGLE_DRAW_OVERLAY]
            == "<ctrl>+<alt>+d"
        )

    def test_hotkeys_view_lists_draw_hotkey(self) -> None:
        from gui.views.hotkeys_view import GLOBAL_HOTKEYS

        assert ("Режим рисования поверх экрана", "Ctrl+Alt+D") in (
            GLOBAL_HOTKEYS
        )


@pytest.mark.parametrize("tool", [t.value for t in DrawTool])
def test_every_tool_creates_shape(tool: str) -> None:
    """Каждый инструмент создаёт фигуру своего типа (#159)."""
    overlay = DrawOverlayWidget()
    overlay._request_repaint = MagicMock()
    overlay.set_tool(tool)

    overlay.mousePressEvent(_FakeEvent(1, 1))
    overlay.mouseReleaseEvent(_FakeEvent(25, 25))

    shape = overlay.document.shapes()[0]
    assert shape.tool is DrawTool(tool)
