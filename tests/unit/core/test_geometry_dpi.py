"""Юнит-тесты DPI-слоя геометрии (#200).

Проверяют конверсии логика↔физика, поиск монитора-владельца и
нормализацию координат захвата на фиктивных DPI-профилях (125%/150%),
включая mixed-DPI конфигурации.
"""

import ctypes
import sys
from contextlib import ExitStack
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from core.geometry import (
    MAX_DPI_SCALE,
    MIN_DPI_SCALE,
    MonitorDpiProfile,
    convert_rect_to_logical,
    convert_rect_to_physical,
    ensure_process_dpi_awareness,
    find_monitor_for_rect,
    get_monitor_profiles,
    normalize_capture_rect,
    scale_rect_for_dpi,
    unscale_rect_from_dpi,
)

# Mixed-DPI стенд: primary 100% 1920x1080 + secondary 150% 2560x1440
PRIMARY_100 = MonitorDpiProfile(
    monitor_id=1,
    left=0,
    top=0,
    width=1920,
    height=1080,
    dpi_scale=1.0,
    is_primary=True,
)
SECONDARY_150 = MonitorDpiProfile(
    monitor_id=2,
    left=1920,
    top=0,
    width=2560,
    height=1440,
    dpi_scale=1.5,
)
MIXED_PROFILES = [PRIMARY_100, SECONDARY_150]


class TestMonitorDpiProfile:
    """Тесты профиля монитора."""

    def test_physical_bounds_properties(self) -> None:
        """Правая/нижняя границы и центр вычисляются по физике."""
        assert SECONDARY_150.right == 1920 + 2560
        assert SECONDARY_150.bottom == 1440
        assert SECONDARY_150.center_x == 1920 + 1280
        assert SECONDARY_150.center_y == 720

    def test_logical_bounds_for_150_percent(self) -> None:
        """Логические границы secondary-монитора делятся на 1.5."""
        assert SECONDARY_150.logical_left == round(1920 / 1.5)
        assert SECONDARY_150.logical_right == round(4480 / 1.5)
        assert SECONDARY_150.logical_bottom == round(1440 / 1.5)

    def test_contains_point_physical(self) -> None:
        """Точка внутри монитора определяется в физическом пространстве."""
        assert SECONDARY_150.contains_point(1920, 0)
        assert SECONDARY_150.contains_point(4479, 1439)
        assert not SECONDARY_150.contains_point(1919, 0)
        assert not SECONDARY_150.contains_point(4480, 0)

    def test_contains_point_logical(self) -> None:
        """Точка внутри монитора определяется в логическом пространстве."""
        logical_left = SECONDARY_150.logical_left
        logical_right = SECONDARY_150.logical_right
        assert SECONDARY_150.contains_point(logical_left, 0, space="logical")
        assert SECONDARY_150.contains_point(
            logical_right - 1, 0, space="logical"
        )
        assert not SECONDARY_150.contains_point(
            logical_left - 1, 0, space="logical"
        )

    def test_invalid_dpi_scale_raises(self) -> None:
        """Мусорный DPI-фактор (0, отрицательный, гигантский) отвергается."""
        with pytest.raises(ValueError, match="dpi_scale"):
            MonitorDpiProfile(
                monitor_id=1,
                left=0,
                top=0,
                width=1,
                height=1,
                dpi_scale=0.0,
            )
        with pytest.raises(ValueError, match="dpi_scale"):
            MonitorDpiProfile(
                monitor_id=1,
                left=0,
                top=0,
                width=1,
                height=1,
                dpi_scale=MAX_DPI_SCALE * 2,
            )
        MonitorDpiProfile(
            monitor_id=1,
            left=0,
            top=0,
            width=1,
            height=1,
            dpi_scale=MIN_DPI_SCALE,
        )


class TestScaleRectForDpi:
    """Тесты конверсии primary-монитора логика → физика (GUI-граница)."""

    def test_identity_at_100_percent(self) -> None:
        """100% масштаб не меняет координаты."""
        assert scale_rect_for_dpi((100, 50, 500, 400), 1.0) == (
            100,
            50,
            500,
            400,
        )

    def test_scales_at_125_percent(self) -> None:
        """125% масштаб умножает координаты на 1.25."""
        assert scale_rect_for_dpi((200, 100, 600, 400), 1.25) == (
            250,
            125,
            750,
            500,
        )

    def test_scales_at_150_percent(self) -> None:
        """150% масштаб умножает координаты на 1.5 (#200)."""
        assert scale_rect_for_dpi((200, 150, 600, 450), 1.5) == (
            300,
            225,
            900,
            675,
        )

    def test_rounds_to_integer_pixels(self) -> None:
        """Координаты округляются до целых пикселей."""
        assert scale_rect_for_dpi((101, 101, 201, 201), 1.5) == (
            152,
            152,
            302,
            302,
        )

    def test_invalid_scale_raises(self) -> None:
        """Нулевой DPI-фактор отвергается."""
        with pytest.raises(ValueError, match="dpi_scale"):
            scale_rect_for_dpi((0, 0, 10, 10), 0.0)


class TestUnscaleRectFromDpi:
    """Тесты обратной конверсии primary-монитора физика → логика."""

    def test_roundtrip_150_percent(self) -> None:
        """Физика → логика → физика восстанавливает координаты."""
        physical = (300, 225, 900, 675)
        logical = unscale_rect_from_dpi(physical, 1.5)
        assert logical == (200, 150, 600, 450)
        assert scale_rect_for_dpi(logical, 1.5) == physical

    def test_identity_at_100_percent(self) -> None:
        """100% масштаб не меняет координаты."""
        assert unscale_rect_from_dpi((10, 20, 100, 200), 1.0) == (
            10,
            20,
            100,
            200,
        )


class TestConvertRectToPhysical:
    """Тесты конверсии по профилю монитора (виртуальный рабочий стол)."""

    def test_secondary_monitor_with_offset(self) -> None:
        """Rect на secondary-мониторе с offset (1920, 0) конвертируется.

        Логические координаты secondary при 150%: left = 1920/1.5 = 1280.
        Логический rect (1300, 100, 1500, 300) → физический
        (1920 + 20*1.5, 150, 1920 + 220*1.5, 450).
        """
        profile = SECONDARY_150
        result = convert_rect_to_physical((1300, 100, 1500, 300), profile)
        assert result == (1950, 150, 2250, 450)

    def test_primary_monitor_matches_simple_scale(self) -> None:
        """Для primary-монитора совпадает с простым масштабированием."""
        rect = (200, 150, 600, 450)
        assert convert_rect_to_physical(rect, PRIMARY_100) == rect
        assert convert_rect_to_physical(rect, SECONDARY_150) == (
            scale_rect_for_dpi(rect, 1.5)
        )


class TestConvertRectToLogical:
    """Тесты обратной конверсии по профилю монитора."""

    def test_roundtrip_on_secondary_monitor(self) -> None:
        """Логика → физика → логика восстанавливает координаты."""
        logical = (1300, 100, 1500, 300)
        physical = convert_rect_to_physical(logical, SECONDARY_150)
        assert convert_rect_to_logical(physical, SECONDARY_150) == logical

    def test_roundtrip_on_primary_monitor_125(self) -> None:
        """Roundtrip на primary-мониторе со 125% масштабом."""
        profile = MonitorDpiProfile(
            monitor_id=1,
            left=0,
            top=0,
            width=1920,
            height=1080,
            dpi_scale=1.25,
            is_primary=True,
        )
        logical = (200, 150, 600, 450)
        physical = convert_rect_to_physical(logical, profile)
        assert convert_rect_to_logical(physical, profile) == logical


class TestFindMonitorForRect:
    """Тесты поиска монитора-владельца по центру rect."""

    def test_rect_on_secondary_monitor(self) -> None:
        """Rect на secondary-мониторе находит secondary-профиль."""
        rect = (2000, 100, 2400, 500)
        assert find_monitor_for_rect(rect, MIXED_PROFILES) is SECONDARY_150

    def test_rect_on_primary_monitor(self) -> None:
        """Rect на primary-мониторе находит primary-профиль."""
        rect = (100, 100, 500, 400)
        assert find_monitor_for_rect(rect, MIXED_PROFILES) is PRIMARY_100

    def test_rect_outside_desktop_returns_none(self) -> None:
        """Rect вне рабочего стола не имеет владельца."""
        rect = (10000, 10000, 10100, 10100)
        assert find_monitor_for_rect(rect, MIXED_PROFILES) is None

    def test_logical_space_search_unambiguous_stand(self) -> None:
        """Логический поиск однозначен без пересечения пространств.

        Стенд: primary 150% (логика 0..1280) + secondary 100%
        (логика 1920..4480) — логические пространства не пересекаются.
        """
        profiles = [
            MonitorDpiProfile(
                monitor_id=1,
                left=0,
                top=0,
                width=1920,
                height=1080,
                dpi_scale=1.5,
                is_primary=True,
            ),
            MonitorDpiProfile(
                monitor_id=2,
                left=1920,
                top=0,
                width=1920,
                height=1080,
                dpi_scale=1.0,
            ),
        ]
        rect_on_primary = (100, 100, 500, 400)
        assert (
            find_monitor_for_rect(rect_on_primary, profiles, space="logical")
            is profiles[0]
        )
        rect_on_secondary = (2000, 100, 2400, 500)
        assert (
            find_monitor_for_rect(rect_on_secondary, profiles, space="logical")
            is profiles[1]
        )

    def test_empty_profiles_returns_none(self) -> None:
        """Без мониторов владелец не находится."""
        assert find_monitor_for_rect((0, 0, 10, 10), []) is None


class TestNormalizeCaptureRect:
    """Тесты нормализации rect захвата к физическим пикселям."""

    def test_logical_source_with_explicit_owner(self) -> None:
        """Логический rect с явным владельцем конвертируется (#200).

        В mixed-DPI логические пространства пересекаются, поэтому
        GUI передаёт экран, в чьём пространстве выделен rect.
        """
        logical_rect = (1300, 100, 1500, 300)
        result = normalize_capture_rect(
            logical_rect,
            MIXED_PROFILES,
            source="logical",
            owner=SECONDARY_150,
        )
        assert result == (1950, 150, 2250, 450)
        assert result[2] - result[0] == round(200 * 1.5)

    def test_logical_source_without_owner_uses_heuristic(self) -> None:
        """Без владельца работает эвристика по центру rect."""
        logical_rect = (1300, 100, 1500, 300)
        result = normalize_capture_rect(
            logical_rect, MIXED_PROFILES, source="logical"
        )
        # Пересечение логических пространств: первый подходящий — primary
        assert result == convert_rect_to_physical(logical_rect, PRIMARY_100)

    def test_physical_source_unchanged(self) -> None:
        """Физический rect остаётся без изменений."""
        rect = (2000, 100, 2400, 500)
        assert normalize_capture_rect(rect, MIXED_PROFILES) == rect

    def test_unknown_monitor_returns_rect_unchanged(self) -> None:
        """Rect вне рабочего стола возвращается как есть."""
        rect = (10000, 10000, 10100, 10100)
        assert (
            normalize_capture_rect(rect, MIXED_PROFILES, source="logical")
            == rect
        )

    def test_empty_profiles_returns_rect_unchanged(self) -> None:
        """Без профилей мониторов rect возвращается как есть."""
        rect = (10, 10, 50, 50)
        assert normalize_capture_rect(rect, []) == rect


class TestEnsureProcessDpiAwareness:
    """Тесты включения per-monitor DPI-awareness."""

    @staticmethod
    def _patch_win32(set_result: int | None) -> Any:
        """Подменить ctypes.windll.user32 песочницей.

        Args:
            set_result: Возврат SetProcessDpiAwarenessContext
                (1 = TRUE, 0 = FALSE); None — API отсутствует.

        Returns:
            Контекст менеджеров патчей ctypes.
        """

        class FakeUser32:
            @staticmethod
            def SetProcessDpiAwarenessContext(_ctx: object) -> int:
                if set_result is None:
                    raise AttributeError(
                        "SetProcessDpiAwarenessContext не найден"
                    )
                return set_result

        fake_windll = SimpleNamespace(user32=FakeUser32())
        return (
            patch.object(ctypes, "windll", fake_windll),
            patch.object(ctypes, "c_void_p", lambda value: value),
            patch.object(sys, "platform", "win32"),
        )

    def test_non_windows_platform_returns_false(self) -> None:
        """На не-Windows платформе awareness не включается."""
        with patch.object(sys, "platform", "linux"):
            assert ensure_process_dpi_awareness() is False

    def test_windows_success_returns_true(self) -> None:
        """Успешный вызов Win32 возвращает True."""
        with ExitStack() as stack:
            for manager in self._patch_win32(set_result=1):
                stack.enter_context(manager)
            assert ensure_process_dpi_awareness() is True

    def test_already_set_returns_false(self) -> None:
        """FALSE от Win32 (уже установлен, например Qt6) — не ошибка."""
        with ExitStack() as stack:
            for manager in self._patch_win32(set_result=0):
                stack.enter_context(manager)
            assert ensure_process_dpi_awareness() is False

    def test_missing_api_returns_false(self) -> None:
        """Отсутствие Win32 API (старая ОС) — не ошибка."""
        with ExitStack() as stack:
            for manager in self._patch_win32(set_result=None):
                stack.enter_context(manager)
            assert ensure_process_dpi_awareness() is False


class TestGetMonitorProfiles:
    """Тесты фасада получения профилей мониторов."""

    def test_non_windows_returns_empty(self) -> None:
        """На не-Windows платформе профилей нет."""
        with patch.object(sys, "platform", "darwin"):
            assert get_monitor_profiles() == []
