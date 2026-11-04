"""Тесты оверлея эффектов курсора (#166)."""

import time
from unittest.mock import MagicMock

from gui.views.cursor_effects_overlay import (
    RIPPLE_END_RADIUS,
    RIPPLE_START_RADIUS,
    CursorEffectsOverlay,
    ripple_alpha,
    ripple_progress,
    ripple_radius,
)


class TestRippleMath:
    """Чистая математика анимации кольца клика (#166)."""

    def test_progress_bounds(self) -> None:
        """Прогресс ограничен диапазоном 0..1."""
        assert ripple_progress(10.0, 10.0) == 0.0
        assert ripple_progress(10.0, 10.5) == 1.0  # duration = 0.5
        assert ripple_progress(10.0, 9.9) == 0.0

    def test_radius_grows(self) -> None:
        """Радиус растёт от начального к конечному."""
        assert ripple_radius(0.0) == RIPPLE_START_RADIUS
        assert ripple_radius(1.0) == RIPPLE_END_RADIUS
        assert (
            ripple_radius(0.5) == (RIPPLE_START_RADIUS + RIPPLE_END_RADIUS) / 2
        )

    def test_alpha_fades_to_zero(self) -> None:
        """Альфа линейно затухает до нуля."""
        assert ripple_alpha(0.0) == 180
        assert ripple_alpha(1.0) == 0
        assert ripple_alpha(0.5) == 90


class TestCursorEffectsOverlay:
    """Оверлей эффектов курсора (#166)."""

    def _make_overlay(self) -> CursorEffectsOverlay:
        return CursorEffectsOverlay()

    def test_register_click_ignored_when_disabled(self) -> None:
        """Клики не регистрируются без включённых эффектов."""
        overlay = self._make_overlay()
        overlay.register_click("left", 100, 100)
        assert overlay.active_ripples(time.monotonic()) == []

    def test_register_click_left_and_right(self) -> None:
        """ЛКМ и ПКМ регистрируются при включённых эффектах."""
        overlay = self._make_overlay()
        overlay.apply_settings(
            MagicMock(highlight_enabled=False, click_effects_enabled=True)
        )
        overlay.register_click("left", 100, 100)
        overlay.register_click("right", 200, 200)
        overlay.register_click("middle", 300, 300)  # не анимируется

        ripples = overlay.active_ripples(time.monotonic())
        assert len(ripples) == 2
        assert {r.button for r in ripples} == {"left", "right"}

    def test_old_ripples_expire(self) -> None:
        """Затухшие кольца выпадают из активных."""
        overlay = self._make_overlay()
        overlay.apply_settings(
            MagicMock(highlight_enabled=False, click_effects_enabled=True)
        )
        overlay.register_click("left", 100, 100)
        # duration = 0.5s: клик минутной давности уже не активен
        assert overlay.active_ripples(time.monotonic() + 60.0) == []

    def test_apply_settings_enables_highlight(self) -> None:
        """apply_settings переносит флаги настроек."""
        overlay = self._make_overlay()
        overlay.apply_settings(
            MagicMock(highlight_enabled=True, click_effects_enabled=False)
        )
        assert overlay._highlight_enabled is True
        assert overlay._click_effects_enabled is False

    def test_stop_clears_state(self) -> None:
        """stop() сбрасывает кольца и скрывает окно."""
        overlay = self._make_overlay()
        overlay.apply_settings(
            MagicMock(highlight_enabled=True, click_effects_enabled=True)
        )
        overlay.register_click("left", 100, 100)
        overlay.hide = MagicMock()
        overlay._timer = MagicMock()

        overlay.stop()

        overlay._timer.stop.assert_called_once()
        overlay.hide.assert_called_once()
        assert overlay._clicks == []
        assert overlay._mouse_listener is None

    def test_start_without_click_effects_skips_listener(self) -> None:
        """Без эффектов кликов pynput-слушатель не запускается."""
        overlay = self._make_overlay()
        overlay.apply_settings(
            MagicMock(highlight_enabled=True, click_effects_enabled=False)
        )
        overlay.show = MagicMock()
        overlay.raise_ = MagicMock()
        overlay._timer = MagicMock()
        overlay._timer.isActive.return_value = False

        overlay.start()

        assert overlay._mouse_listener is None
        overlay._timer.start.assert_called_once()

    def test_native_click_emits_signal(self) -> None:
        """pynput-колбэк публикует сигнал для нажатий ЛКМ/ПКМ."""
        overlay = self._make_overlay()
        overlay.click_registered = MagicMock()
        button = MagicMock()
        button.name = "left"

        overlay._on_native_click(150, 250, button, True)
        overlay._on_native_click(150, 250, button, False)  # отпускание

        overlay.click_registered.emit.assert_called_once_with("left", 150, 250)

    def test_native_click_ignores_unknown_buttons(self) -> None:
        """Средняя кнопка и кнопки без имени не публикуются."""
        overlay = self._make_overlay()
        overlay.click_registered = MagicMock()
        button = MagicMock()
        button.name = "middle"

        overlay._on_native_click(150, 250, button, True)

        overlay.click_registered.emit.assert_not_called()
