"""
Тесты визуального индикатора активной записи.
"""

import importlib

from core.recording_state import CaptureSettings
from core.recording_types import CaptureMode
from gui import views as gui_views
from gui.views.recording_indicator import (
    RecordingIndicatorOverlay,
    resolve_indicator_rect,
)


class TestResolveIndicatorRect:
    """Тесты расчёта области индикатора."""

    def test_recording_indicator_exported_from_gui_views(self) -> None:
        """Индикатор доступен через пакетный импорт gui.views."""
        importlib.reload(gui_views)
        assert gui_views.RecordingIndicatorOverlay is RecordingIndicatorOverlay

    def test_resolve_full_screen_rect(self) -> None:
        """Для full mode берётся весь экран."""
        capture = CaptureSettings(capture_type=CaptureMode.FULL)
        assert resolve_indicator_rect(capture, screen_size=(1920, 1080)) == (
            0,
            0,
            1920,
            1080,
        )

    def test_resolve_rect_mode(self) -> None:
        """Для rect mode возвращаются сохранённые координаты."""
        capture = CaptureSettings(
            capture_type=CaptureMode.RECT,
            rect_coords=(10, 20, 300, 200),
        )
        assert resolve_indicator_rect(capture) == (10, 20, 300, 200)

    def test_resolve_window_mode(self) -> None:
        """Для window mode координаты ищутся по заголовку окна."""
        capture = CaptureSettings(
            capture_type=CaptureMode.WINDOW,
            window_title="Editor",
        )
        windows = [
            {
                "title": "Editor - Project",
                "x": 50,
                "y": 60,
                "width": 700,
                "height": 500,
            }
        ]
        assert resolve_indicator_rect(capture, windows=windows) == (
            50,
            60,
            750,
            560,
        )

    def test_resolve_window_mode_returns_none_when_missing(self) -> None:
        """Если окно не найдено, индикатор не показывается."""
        capture = CaptureSettings(
            capture_type=CaptureMode.WINDOW,
            window_title="Missing",
        )
        assert resolve_indicator_rect(capture, windows=[]) is None


class TestRecordingIndicatorOverlay:
    """Тесты служебной логики overlay."""

    def test_show_for_capture_sets_visibility(self) -> None:
        """После show_for_capture overlay становится видимым."""
        overlay = RecordingIndicatorOverlay()
        capture = CaptureSettings(
            capture_type=CaptureMode.RECT,
            rect_coords=(10, 20, 110, 220),
        )

        result = overlay.show_for_capture(capture)

        assert result is True
        assert overlay.isVisible() is True
        assert overlay._bounds is not None

    def test_set_paused_changes_alpha(self) -> None:
        """Пауза переводит индикатор в приглушённое состояние."""
        overlay = RecordingIndicatorOverlay()
        overlay.set_paused(True)
        paused_alpha = overlay._pulse_alpha
        overlay.set_paused(False)
        active_alpha = overlay._pulse_alpha

        assert paused_alpha != active_alpha

    def test_hide_indicator_resets_visibility(self) -> None:
        """Скрытие рамки сбрасывает видимость и геометрию."""
        overlay = RecordingIndicatorOverlay()
        capture = CaptureSettings(
            capture_type=CaptureMode.RECT,
            rect_coords=(10, 20, 110, 220),
        )
        overlay.show_for_capture(capture)

        overlay.hide_indicator()

        assert overlay.isVisible() is False
        assert overlay._bounds is None
