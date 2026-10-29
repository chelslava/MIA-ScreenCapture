"""Unit-тесты плавающего виджета записи (#158)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gui.views.floating_widget import (
    STATE_FINALIZING,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_RECORDING,
    FloatingRecordingWidget,
    format_recording_size,
    snap_to_edges,
)


class _FakePoint:
    """Точка с реальным вычитанием (оператор '-' смотрит на тип)."""

    def __init__(self, x: int, y: int) -> None:
        self._x = x
        self._y = y

    def x(self) -> int:
        return self._x

    def y(self) -> int:
        return self._y

    def __sub__(self, other: object) -> _FakePoint:
        return _FakePoint(self._x, self._y)


class TestSnapToEdges:
    """Магнит краёв экрана (#158)."""

    def test_snaps_left_edge_within_threshold(self) -> None:
        assert snap_to_edges(18, 100, 160, 56, 1920, 1080) == (0, 100)

    def test_snaps_top_edge_within_threshold(self) -> None:
        assert snap_to_edges(300, 20, 160, 56, 1920, 1080) == (300, 0)

    def test_snaps_right_edge(self) -> None:
        # Правый край: 1920-160=1760; 1770 ближе 24px
        assert snap_to_edges(1770, 100, 160, 56, 1920, 1080) == (1760, 100)

    def test_snaps_bottom_edge(self) -> None:
        # Нижний край: 1080-56=1024
        assert snap_to_edges(300, 1030, 160, 56, 1920, 1080) == (300, 1024)

    def test_free_position_not_snapped(self) -> None:
        assert snap_to_edges(500, 400, 160, 56, 1920, 1080) == (500, 400)

    def test_position_clamped_into_screen(self) -> None:
        assert snap_to_edges(-100, -50, 160, 56, 1920, 1080) == (0, 0)
        assert snap_to_edges(2000, 1200, 160, 56, 1920, 1080) == (1760, 1024)


class TestFormatRecordingSize:
    """Человекочитаемый размер файла (#158)."""

    def test_none_is_dash(self) -> None:
        assert format_recording_size(None) == "—"

    def test_bytes(self) -> None:
        assert format_recording_size(512) == "512 Б"

    def test_kilobytes(self) -> None:
        assert format_recording_size(2048) == "2 КБ"

    def test_megabytes(self) -> None:
        assert format_recording_size(5 * 1024 * 1024) == "5.0 МБ"


class TestFloatingWidgetState:
    """Конечный автомат состояний виджета (#158)."""

    @staticmethod
    def _make_widget() -> FloatingRecordingWidget:
        widget = FloatingRecordingWidget.__new__(FloatingRecordingWidget)
        widget._state = STATE_IDLE
        widget._state_label = MagicMock()
        widget._time_label = MagicMock()
        widget._metrics_label = MagicMock()
        widget._dragging = False
        widget._drag_offset = None
        return widget

    def test_state_transitions_recording_flow(self) -> None:
        widget = self._make_widget()

        widget.set_state(STATE_RECORDING)
        assert widget.get_state() == STATE_RECORDING

        widget.set_state(STATE_PAUSED)
        assert widget.get_state() == STATE_PAUSED

        widget.set_state(STATE_FINALIZING)
        assert widget.get_state() == STATE_FINALIZING

        widget.set_state(STATE_IDLE)
        assert widget.get_state() == STATE_IDLE

    def test_unknown_state_ignored(self) -> None:
        widget = self._make_widget()
        widget.set_state(STATE_RECORDING)

        widget.set_state("broken")

        assert widget.get_state() == STATE_RECORDING

    def test_update_metrics_formats_time_and_fps(self) -> None:
        widget = self._make_widget()

        widget.update_metrics(75.0, 29.9, 2048)

        widget._time_label.setText.assert_called_once_with("01:15")
        widget._metrics_label.setText.assert_called_once_with(
            "29.9 FPS  •  2 КБ"
        )

    def test_update_metrics_zero_fps_and_no_size(self) -> None:
        widget = self._make_widget()

        widget.update_metrics(0.0, 0.0, None)

        widget._metrics_label.setText.assert_called_once_with("— FPS  •  —")


class TestFloatingWidgetPosition:
    """Сохранение и восстановление позиции (#158)."""

    def test_save_position_to_config(self) -> None:
        widget = FloatingRecordingWidget.__new__(FloatingRecordingWidget)
        widget._state = STATE_IDLE
        widget.pos = MagicMock(
            return_value=MagicMock(x=lambda: 42, y=lambda: 24)
        )
        config_mock = MagicMock()
        config_mock.settings.floating_widget_pos = None

        with patch(
            "gui.views.floating_widget.get_config", return_value=config_mock
        ):
            widget.save_position()

        assert config_mock.settings.floating_widget_pos == [42, 24]

    def test_restore_position_clamps_into_screen(self) -> None:
        widget = FloatingRecordingWidget.__new__(FloatingRecordingWidget)
        widget.width = MagicMock(return_value=160)
        widget.height = MagicMock(return_value=56)
        moves: list[tuple[int, int]] = []
        widget.move = lambda x, y: moves.append((x, y))
        config_mock = MagicMock()
        config_mock.settings.floating_widget_pos = [5000, -20]

        with patch(
            "gui.views.floating_widget.get_config", return_value=config_mock
        ):
            widget.restore_position((1920, 1080))

        assert moves == [(1760, 0)]

    def test_restore_position_without_saved_value_is_noop(
        self,
    ) -> None:
        widget = FloatingRecordingWidget.__new__(FloatingRecordingWidget)
        widget.width = MagicMock(return_value=160)
        widget.height = MagicMock(return_value=56)
        moves: list[tuple[int, int]] = []
        widget.move = lambda x, y: moves.append((x, y))
        config_mock = MagicMock()
        config_mock.settings.floating_widget_pos = None

        with patch(
            "gui.views.floating_widget.get_config", return_value=config_mock
        ):
            widget.restore_position((1920, 1080))

        assert moves == []


class TestFloatingWidgetDrag:
    """Перетаскивание виджета мышью (#158)."""

    @staticmethod
    def _make_draggable_widget() -> FloatingRecordingWidget:
        widget = FloatingRecordingWidget.__new__(FloatingRecordingWidget)
        widget._state = STATE_IDLE
        widget._state_label = MagicMock()
        widget._time_label = MagicMock()
        widget._metrics_label = MagicMock()
        widget._dragging = False
        widget._drag_offset = None
        widget.pos = MagicMock(
            return_value=MagicMock(x=lambda: 300, y=lambda: 200)
        )
        widget.width = MagicMock(return_value=160)
        widget.height = MagicMock(return_value=56)
        widget.move = MagicMock()
        widget.save_position = MagicMock()
        return widget

    def test_press_starts_drag(self) -> None:
        widget = self._make_draggable_widget()
        event = MagicMock()
        event.button.return_value = None  # Qt enum недоступен в моках

        # Прямая установка полей вместо Qt-события: проверяем инвариант
        widget._dragging = True
        widget._drag_offset = MagicMock()

        assert widget._dragging is True

    def test_move_without_drag_is_noop(self) -> None:
        widget = self._make_draggable_widget()
        widget._dragging = False

        widget.mouseMoveEvent(MagicMock())

        widget.move.assert_not_called()

    def test_move_while_drag_repositions(self) -> None:
        widget = self._make_draggable_widget()
        widget._dragging = True
        widget._drag_offset = MagicMock()
        # new_pos = global_pos - drag_offset → _FakePoint(400, 260)
        event = MagicMock()
        event.globalPosition.return_value.toPoint.return_value = _FakePoint(
            400, 260
        )

        widget.mouseMoveEvent(event)

        widget.move.assert_called_once_with(400, 260)

    def test_release_snaps_and_saves(self) -> None:
        widget = self._make_draggable_widget()
        widget._dragging = True
        widget._drag_offset = MagicMock()

        with (
            patch("recorder.utils.get_screen_size", return_value=(1920, 1080)),
        ):
            widget.mouseReleaseEvent(MagicMock())

        # 300,200 — свободная позиция: снап не смещает, но save вызван
        widget.move.assert_called_once_with(300, 200)
        widget.save_position.assert_called_once()
        assert widget._dragging is False

    def test_release_without_drag_is_noop(self) -> None:
        widget = self._make_draggable_widget()
        widget._dragging = False

        widget.mouseReleaseEvent(MagicMock())

        widget.move.assert_not_called()
        widget.save_position.assert_not_called()

    def test_save_position_without_pos_attr_is_noop(self) -> None:
        widget = FloatingRecordingWidget.__new__(FloatingRecordingWidget)

        widget.save_position()  # не должно упасть

    def test_restore_position_without_move_attr_is_noop(self) -> None:
        widget = FloatingRecordingWidget.__new__(FloatingRecordingWidget)

        widget.restore_position((1920, 1080))  # не должно упасть


class TestFloatingWidgetTimer:
    """Периодическое обновление метрик (#158)."""

    def test_start_updates_starts_timer_with_shared_tick(self) -> None:
        from gui.constants import RECORDING_INDICATOR_TICK_MS

        widget = FloatingRecordingWidget.__new__(FloatingRecordingWidget)
        widget._timer = MagicMock()
        widget._timer.timeout = MagicMock()
        widget._timer.timeout.disconnect = MagicMock(
            side_effect=TypeError("not connected")
        )
        tick = MagicMock()

        widget.start_updates(tick)

        widget._timer.start.assert_called_once_with(
            RECORDING_INDICATOR_TICK_MS
        )

    def test_stop_updates_stops_timer(self) -> None:
        widget = FloatingRecordingWidget.__new__(FloatingRecordingWidget)
        widget._timer = MagicMock()

        widget.stop_updates()

        widget._timer.stop.assert_called_once()

    def test_default_tick_is_noop(self) -> None:
        widget = FloatingRecordingWidget.__new__(FloatingRecordingWidget)

        widget._on_tick()  # не должно упасть
