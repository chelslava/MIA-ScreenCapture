"""Unit-тесты плавных переходов вкладок (#161)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import gui.transitions as transitions
from gui.transitions import ANIMATION_DURATION_MS, animate_page_in


class TestAnimatePageIn:
    """Fade-анимация входа страницы стека."""

    def test_wires_opacity_effect_and_animation(self) -> None:
        page = MagicMock()
        page._fade_in_animation = None

        with (
            patch("PyQt6.QtWidgets.QGraphicsOpacityEffect") as effect_cls,
            patch("PyQt6.QtCore.QPropertyAnimation") as anim_cls,
        ):
            animate_page_in(page)

        page.setGraphicsEffect.assert_called_once_with(effect_cls.return_value)
        effect_cls.return_value.setOpacity.assert_called_once_with(0.0)
        anim_cls.return_value.setDuration.assert_called_once_with(
            ANIMATION_DURATION_MS
        )
        anim_cls.return_value.setStartValue.assert_called_once_with(0.0)
        anim_cls.return_value.setEndValue.assert_called_once_with(1.0)
        anim_cls.return_value.start.assert_called_once()
        assert page._fade_in_animation is anim_cls.return_value

    def test_reentrant_call_ignored(self) -> None:
        """Повторный вызов во время анимации — no-op."""
        page = MagicMock()
        page._fade_in_animation = MagicMock()

        with patch("PyQt6.QtWidgets.QGraphicsOpacityEffect") as effect_cls:
            animate_page_in(page)

        effect_cls.assert_not_called()
        page.setGraphicsEffect.assert_not_called()

    def test_zero_duration_is_noop(self) -> None:
        page = MagicMock()

        animate_page_in(page, duration_ms=0)

        page.setGraphicsEffect.assert_not_called()

    def test_none_page_is_noop(self) -> None:
        animate_page_in(None)  # не должно упасть

    def test_cleanup_resets_animation_handle(self) -> None:
        """По завершении эффект снимается, хэндл очищается."""
        page = MagicMock()
        page._fade_in_animation = None

        with (
            patch("PyQt6.QtWidgets.QGraphicsOpacityEffect"),
            patch("PyQt6.QtCore.QPropertyAnimation") as anim_cls,
        ):
            animate_page_in(page)
            finished_handler = (
                anim_cls.return_value.finished.connect.call_args.args[0]
            )
            finished_handler()

        page.setGraphicsEffect.assert_called_with(None)
        assert page._fade_in_animation is None


class TestReducedMotion:
    """Уважение системных настроек анимаций (reduced motion)."""

    def test_non_windows_query_returns_none(self, monkeypatch) -> None:
        monkeypatch.setattr(transitions.platform, "system", lambda: "Linux")
        assert transitions._query_client_area_animation() is None
        assert transitions.reduced_motion_preferred() is False

    def test_animations_disabled_is_reduced_motion(self, monkeypatch) -> None:
        """SPI-флаг 0 (анимации отключены системой) → reduced motion."""
        monkeypatch.setattr(
            transitions,
            "_query_client_area_animation",
            lambda: False,
        )
        assert transitions.reduced_motion_preferred() is True

    def test_animations_enabled_allows_fades(self, monkeypatch) -> None:
        monkeypatch.setattr(
            transitions,
            "_query_client_area_animation",
            lambda: True,
        )
        assert transitions.reduced_motion_preferred() is False

    def test_query_failure_allows_animations(self, monkeypatch) -> None:
        """Ошибка чтения системного флага не запрещает анимации."""
        monkeypatch.setattr(
            transitions,
            "_query_client_area_animation",
            lambda: None,
        )
        assert transitions.reduced_motion_preferred() is False
