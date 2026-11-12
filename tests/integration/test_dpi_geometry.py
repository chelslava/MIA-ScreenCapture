"""Интеграционные тесты DPI-геометрии захвата (#200).

Регресс-тест критерия приёмки issue #200: выделенная область на
scaled-мониторе (125%/150%) совпадает с записанной областью. Пайплайн
эмулируется с фиктивными DPI-профилями: логический rect GUI →
DPI-нормализация → кроп физического кадра WGC (та же логика среза,
что в `_WindowsCaptureSession.start`).
"""

import numpy as np
import pytest

from core.geometry import (
    MonitorDpiProfile,
    find_monitor_for_rect,
    normalize_capture_rect,
    scale_rect_for_dpi,
)

BGRA_CHANNELS = 4


def _build_physical_frame(width: int, height: int) -> np.ndarray:
    """Создать синтетический физический кадр WGC (BGRA).

    Args:
        width: Ширина кадра в физических пикселях.
        height: Высота кадра в физических пикселях.

    Returns:
        Массив (height, width, 4) uint8, заполненный нулями.
    """
    return np.zeros((height, width, BGRA_CHANNELS), dtype=np.uint8)


def _crop_frame_like_recorder(
    frame: np.ndarray, rect: tuple[int, int, int, int]
) -> np.ndarray:
    """Воспроизвести кроп кадра из `_WindowsCaptureSession.start`.

    Args:
        frame: Физический кадр (height, width, channels).
        rect: Физический rect (x1, y1, x2, y2).

    Returns:
        Обрезанная область (без цветовой конвертации, как в рекордере).
    """
    x1, y1, x2, y2 = rect
    h, w = frame.shape[:2]
    x2 = min(max(x2, x1), w)
    y2 = min(max(y2, y1), h)
    x1 = max(x1, 0)
    y1 = max(y1, 0)
    return np.ascontiguousarray(frame[y1:y2, x1:x2])


def _paint_border(frame: np.ndarray, rect: tuple[int, int, int, int]) -> None:
    """Нарисовать яркую рамку по границам физического rect.

    Позволяет проверить, что кроп попал ровно в выделенную область:
    края результата должны быть рамкой, а внешние пиксели — фоном.

    Args:
        frame: Физический кадр.
        rect: Физический rect (x1, y1, x2, y2).
    """
    x1, y1, x2, y2 = rect
    frame[y1:y2, x1] = 255
    frame[y1:y2, x2 - 1] = 255
    frame[y1, x1:x2] = 255
    frame[y2 - 1, x1:x2] = 255


@pytest.mark.integration
class TestSelectionMatchesRecording:
    """Регресс #200: выделение области = записанная область."""

    @pytest.mark.parametrize(
        ("dpi_scale", "logical_screen"),
        [
            (1.25, (2048, 1152)),
            (1.5, (1707, 960)),
        ],
        ids=["125%", "150%"],
    )
    def test_selection_frame_matches_on_scaled_monitor(
        self,
        dpi_scale: float,
        logical_screen: tuple[int, int],
    ) -> None:
        """Выделение на scaled-мониторе даёт ровно тот же кадр.

        Стенд: single-монитор физически 2560x1440, логически
        2048x1152 (125%) или ~1707x960 (150%), Qt DIP. Пользователь
        выделяет логический rect; GUI конвертирует его в физику
        (scale_rect_for_dpi), рекордер кропает физический кадр.
        Размер и содержимое кропа обязаны соответствовать выделению.
        """
        # Физический монитор и кадр WGC
        physical_width, physical_height = 2560, 1440
        frame = _build_physical_frame(physical_width, physical_height)

        # Пользователь выделяет область в логических координатах Qt
        logical_rect = (200, 150, 600, 450)
        assert logical_rect[2] <= logical_screen[0]
        assert logical_rect[3] <= logical_screen[1]

        # Граница GUI: логика → физика (#200). Края маппятся как
        # round(edge * scale); без нормализации кроп остался бы в
        # логических координатах и съехал бы в 1/dpi_scale раз.
        physical_rect = scale_rect_for_dpi(logical_rect, dpi_scale)
        assert physical_rect == tuple(
            round(coord * dpi_scale) for coord in logical_rect
        )

        # Маркер по границам выделения и кроп, как в рекордере
        _paint_border(frame, physical_rect)
        recorded = _crop_frame_like_recorder(frame, physical_rect)

        # Записанная область = выделенная область: размер в физике
        # (округление краёв даёт допуск 1px на дробных масштабах)
        ideal_w = (logical_rect[2] - logical_rect[0]) * dpi_scale
        ideal_h = (logical_rect[3] - logical_rect[1]) * dpi_scale
        assert abs(recorded.shape[1] - ideal_w) <= 1
        assert abs(recorded.shape[0] - ideal_h) <= 1

        # Рамка попала на края кадра записи, фон — нет: область не «съехала»
        assert recorded[0].all() and recorded[-1].all()
        assert recorded[:, 0].all() and recorded[:, -1].all()
        # Внутри рамки — фон (пусто)
        assert not recorded[1:-1, 1:-1].any()

    def test_full_monitor_capture_matches_physical_size(self) -> None:
        """Full-захват scaled-монитора даёт физический размер кадра."""
        profile = MonitorDpiProfile(
            monitor_id=1,
            left=0,
            top=0,
            width=2560,
            height=1440,
            dpi_scale=1.5,
            is_primary=True,
        )
        frame = _build_physical_frame(profile.width, profile.height)
        recorded = _crop_frame_like_recorder(
            frame, (0, 0, profile.width, profile.height)
        )
        # WGC захватывает физическое разрешение, а не логическое 1707x960
        assert recorded.shape[:2] == (1440, 2560)


@pytest.mark.integration
class TestMixedDpiSelection:
    """Выделение на secondary-мониторе mixed-DPI конфигурации."""

    MIXED = [
        MonitorDpiProfile(
            monitor_id=1,
            left=0,
            top=0,
            width=1920,
            height=1080,
            dpi_scale=1.0,
            is_primary=True,
        ),
        MonitorDpiProfile(
            monitor_id=2,
            left=1920,
            top=0,
            width=2560,
            height=1440,
            dpi_scale=1.5,
        ),
    ]

    def test_selection_on_secondary_150_monitor_matches_frame(self) -> None:
        """Выделение на 150%-мониторе справа даёт совпадающий кадр.

        Логический rect (1300, 100, 1500, 300) принадлежит logical
        пространству secondary (1280..2987), которое пересекается с
        primary (0..1920): владелец передаётся явно, как это делает
        источник логических координат. Без DPI-нормализации кроп
        остался бы в логике и оказался бы в 1.5 раза меньше.
        """
        logical_rect = (1300, 100, 1500, 300)
        secondary = self.MIXED[1]

        # Нормализация к физике виртуального рабочего стола
        physical_rect = normalize_capture_rect(
            logical_rect, self.MIXED, source="logical", owner=secondary
        )
        assert physical_rect == (1950, 150, 2250, 450)

        # Кроп физического кадра secondary-монитора: 200x200 логики
        # → 300x300 физики (1.5x)
        frame = _build_physical_frame(secondary.width, secondary.height)
        _paint_border(frame, physical_rect)
        recorded = _crop_frame_like_recorder(frame, physical_rect)

        assert recorded.shape == (300, 300, BGRA_CHANNELS)
        assert recorded[0].all() and recorded[-1].all()
        assert not recorded[1:-1, 1:-1].any()

    def test_api_physical_rect_on_secondary_matches_frame(self) -> None:
        """Физический rect из API на secondary даёт совпадающий кадр.

        Контракт API: rect в физических пикселях виртуального рабочего
        стола. Поиск владельца в физическом пространстве однозначен.
        """
        physical_rect = (2000, 100, 2450, 550)
        monitor = find_monitor_for_rect(physical_rect, self.MIXED)
        assert monitor is self.MIXED[1]

        frame = _build_physical_frame(monitor.width, monitor.height)
        _paint_border(frame, physical_rect)
        recorded = _crop_frame_like_recorder(frame, physical_rect)

        assert recorded.shape == (450, 450, BGRA_CHANNELS)
        assert recorded[0].all() and recorded[-1].all()
        assert not recorded[1:-1, 1:-1].any()
