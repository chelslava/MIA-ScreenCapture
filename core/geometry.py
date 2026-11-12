"""
Geometry utilities for working with coordinates.
================================================

Provides functions for validating and normalizing
rectangular coordinates for screen capture area, including
DPI-aware conversion between Qt logical coordinates and
physical pixels of the virtual desktop (#200).

Coordinate contract: rect coordinates passed downstream
(settings, API, recorder) are always physical pixels — the same
space WGC frames live in. Qt GUI components work in logical
coordinates and convert at the boundary (see
gui.views.area_selector.AreaSelectorDialog.select_area).
"""

import ctypes
import sys
from dataclasses import dataclass
from typing import Any, Final, Literal

from logger_config import get_module_logger

logger = get_module_logger(__name__)

RectCoords = tuple[int, int, int, int]
PointCoords = tuple[int, int]

# Пространство координат: логическое (Qt DIP) или физическое (кадр WGC)
CoordinateSpace = Literal["logical", "physical"]

# Стандартный логический DPI Windows при 100% масштабе
DEFAULT_DPI: Final = 96.0

# Разумные границы DPI-фактора: отбраковка мусорных значений
# от драйверов/моков (0, отрицательных, заведомо нереалистичных)
MIN_DPI_SCALE: Final = 0.5
MAX_DPI_SCALE: Final = 6.0

# DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 (Windows 10 1703+)
_PMV2_DPI_AWARENESS_CONTEXT: Final = -4

# MDT_EFFECTIVE_DPI для GetDpiForMonitor
_MDT_EFFECTIVE_DPI: Final = 0


def validate_rect_coords(
    x1: int, y1: int, x2: int, y2: int, *, strict: bool = False
) -> tuple[int, int, int, int]:
    """
    Validate and normalize rectangle coordinates.

    Processes coordinates of rectangle corners (x1, y1) and (x2, y2),
    ensuring correct order and minimum area size.

    Args:
        x1, y1: Coordinates of the first corner (can be top-left or bottom-right).
        x2, y2: Coordinates of the second corner.
        strict: If True, raises ValueError for invalid coordinates.
            If False (default), automatically normalizes coordinates via min/max.

    Returns:
        Tuple (left, top, right, bottom) - normalized coordinates.

    Raises:
        ValueError: If strict=True and coordinates are invalid:
            - Wrong number of coordinates
            - x2 <= x1 or y2 <= y1
            - Negative coordinates

    Examples:
        # Normalization (automatic ordering):
        >>> validate_rect_coords(800, 600, 100, 100)
        (100, 100, 800, 600)

        # Strict validation (exception on wrong order):
        >>> validate_rect_coords(800, 600, 100, 100, strict=True)
        Traceback (most recent call last):
            ...
        ValueError: x2 must be greater than x1

        # Minimum size:
        >>> validate_rect_coords(100, 100, 105, 105)
        (100, 100, 110, 110)
    """
    left = min(x1, x2)
    top = min(y1, y2)
    right = max(x1, x2)
    bottom = max(y1, y2)

    # Enforce minimum size of 10x10 pixels
    if right - left < 10:
        right = left + 10
    if bottom - top < 10:
        bottom = top + 10

    if strict:
        # Checks only when strict=True
        if x2 <= x1:
            raise ValueError(f"x2 must be greater than x1: x1={x1}, x2={x2}")
        if y2 <= y1:
            raise ValueError(f"y2 must be greater than y1: y1={y1}, y2={y2}")
        if left < 0 or top < 0:
            raise ValueError(
                f"Coordinates must not be negative: "
                f"[{left}, {top}, {right}, {bottom}]"
            )

    return left, top, right, bottom


def _validated_dpi_scale(dpi_scale: float) -> float:
    """Проверить DPI-фактор на реалистичность.

    Args:
        dpi_scale: Масштаб монитора (1.0 = 100%, 1.5 = 150%).

    Returns:
        Проверенный фактор.

    Raises:
        ValueError: Если фактор вне диапазона [MIN_DPI_SCALE,
            MAX_DPI_SCALE] — признак мусорных данных, а не реального
            масштаба.
    """
    scale = float(dpi_scale)
    if not MIN_DPI_SCALE <= scale <= MAX_DPI_SCALE:
        raise ValueError(
            f"dpi_scale must be in [{MIN_DPI_SCALE}, {MAX_DPI_SCALE}], "
            f"got {dpi_scale}"
        )
    return scale


@dataclass(frozen=True)
class MonitorDpiProfile:
    """Профиль монитора: физические границы и DPI-фактор.

    Границы заданы в физических пикселях виртуального рабочего стола
    (пространство кадров WGC). Логические границы (Qt DIP) вычисляются
    делением на DPI-фактор — стандартная семантика Qt.

    Attributes:
        monitor_id: Порядковый номер монитора (с 1).
        left: Физическая левая граница.
        top: Физическая верхняя граница.
        width: Физическая ширина.
        height: Физическая высота.
        dpi_scale: DPI-фактор (1.0 = 100%, 1.5 = 150%).
        is_primary: Является ли монитор primary (origin 0,0).
    """

    monitor_id: int
    left: int
    top: int
    width: int
    height: int
    dpi_scale: float
    is_primary: bool = False

    def __post_init__(self) -> None:
        # frozen-дата-класс: валидация через object.__setattr__ невозможна
        # без обмана type-checker'ов, поэтому garbage-значения отвергаем.
        _validated_dpi_scale(self.dpi_scale)

    @property
    def right(self) -> int:
        """Физическая правая граница (исключающая)."""
        return self.left + self.width

    @property
    def bottom(self) -> int:
        """Физическая нижняя граница (исключающая)."""
        return self.top + self.height

    @property
    def center_x(self) -> int:
        """Физическая X-координата центра."""
        return self.left + self.width // 2

    @property
    def center_y(self) -> int:
        """Физическая Y-координата центра."""
        return self.top + self.height // 2

    @property
    def logical_left(self) -> int:
        """Логическая левая граница."""
        return round(self.left / self.dpi_scale)

    @property
    def logical_top(self) -> int:
        """Логическая верхняя граница."""
        return round(self.top / self.dpi_scale)

    @property
    def logical_right(self) -> int:
        """Логическая правая граница (исключающая)."""
        return round(self.right / self.dpi_scale)

    @property
    def logical_bottom(self) -> int:
        """Логическая нижняя граница (исключающая)."""
        return round(self.bottom / self.dpi_scale)

    def contains_point(
        self,
        x: int,
        y: int,
        space: CoordinateSpace = "physical",
    ) -> bool:
        """Проверить, лежит ли точка внутри монитора.

        Args:
            x: X-координата.
            y: Y-координата.
            space: Пространство координат точки.

        Returns:
            `True`, если точка принадлежит монитору.
        """
        if space == "logical":
            return (
                self.logical_left <= x < self.logical_right
                and self.logical_top <= y < self.logical_bottom
            )
        return self.left <= x < self.right and self.top <= y < self.bottom


def scale_rect_for_dpi(rect: RectCoords, dpi_scale: float) -> RectCoords:
    """Конвертировать rect primary-монитора: логика → физика.

    У primary-монитора физический origin в Windows всегда (0, 0) и
    логический origin в Qt тоже (0, 0), поэтому масштабирование
    относительно origin — точное преобразование.

    Args:
        rect: Логические координаты (x1, y1, x2, y2).
        dpi_scale: DPI-фактор primary-монитора.

    Returns:
        Физические координаты (округлённые).

    Raises:
        ValueError: Если dpi_scale вне допустимого диапазона.
    """
    scale = _validated_dpi_scale(dpi_scale)
    x1, y1, x2, y2 = rect
    return (
        round(x1 * scale),
        round(y1 * scale),
        round(x2 * scale),
        round(y2 * scale),
    )


def unscale_rect_from_dpi(rect: RectCoords, dpi_scale: float) -> RectCoords:
    """Конвертировать rect primary-монитора: физика → логика.

    Обратное к `scale_rect_for_dpi`; используется при передаче
    сохранённого физического rect обратно в логический диалог.

    Args:
        rect: Физические координаты (x1, y1, x2, y2).
        dpi_scale: DPI-фактор primary-монитора.

    Returns:
        Логические координаты (округлённые).

    Raises:
        ValueError: Если dpi_scale вне допустимого диапазона.
    """
    scale = _validated_dpi_scale(dpi_scale)
    x1, y1, x2, y2 = rect
    return (
        round(x1 / scale),
        round(y1 / scale),
        round(x2 / scale),
        round(y2 / scale),
    )


def convert_rect_to_physical(
    rect: RectCoords,
    profile: MonitorDpiProfile,
) -> RectCoords:
    """Конвертировать rect из логики в физику по профилю монитора.

    Точка p логического пространства монитора отображается как
    ``profile.left + (p - logical_left) * dpi_scale``.

    Args:
        rect: Логические координаты (x1, y1, x2, y2).
        profile: Профиль монитора-владельца.

    Returns:
        Физические координаты.

    Raises:
        ValueError: Если dpi_scale профиля вне допустимого диапазона.
    """
    scale = _validated_dpi_scale(profile.dpi_scale)
    x1, y1, x2, y2 = rect
    return (
        profile.left + round((x1 - profile.logical_left) * scale),
        profile.top + round((y1 - profile.logical_top) * scale),
        profile.left + round((x2 - profile.logical_left) * scale),
        profile.top + round((y2 - profile.logical_top) * scale),
    )


def convert_rect_to_logical(
    rect: RectCoords,
    profile: MonitorDpiProfile,
) -> RectCoords:
    """Конвертировать rect из физики в логику по профилю монитора.

    Обратное к `convert_rect_to_physical`.

    Args:
        rect: Физические координаты (x1, y1, x2, y2).
        profile: Профиль монитора-владельца.

    Returns:
        Логические координаты.

    Raises:
        ValueError: Если dpi_scale профиля вне допустимого диапазона.
    """
    scale = _validated_dpi_scale(profile.dpi_scale)
    x1, y1, x2, y2 = rect
    return (
        profile.logical_left + round((x1 - profile.left) / scale),
        profile.logical_top + round((y1 - profile.top) / scale),
        profile.logical_left + round((x2 - profile.left) / scale),
        profile.logical_top + round((y2 - profile.top) / scale),
    )


def find_monitor_for_rect(
    rect: RectCoords,
    profiles: list[MonitorDpiProfile],
    space: CoordinateSpace = "physical",
) -> MonitorDpiProfile | None:
    """Найти монитор-владелец прямоугольника по его центру.

    Владелец определяется по центру rect (стандартная эвристика для
    прямоугольников, пересекающих несколько мониторов): захват ведётся
    с того монитора, где находится большая часть области.

    Ограничение: в mixed-DPI конфигурациях логические пространства
    мониторов могут пересекаться, тогда поиск в space="logical"
    возвращает первый подходящий монитор. Для однозначного результата
    используйте физические координаты или передайте владельца явно
    в `normalize_capture_rect`.

    Args:
        rect: Прямоугольник (x1, y1, x2, y2) в координатах `space`.
        profiles: Профили мониторов.
        space: Пространство координат rect.

    Returns:
        Профиль монитора-владельца или None (вне рабочего стола).
    """
    x1, y1, x2, y2 = rect
    center_x = (x1 + x2) // 2
    center_y = (y1 + y2) // 2
    for profile in profiles:
        if profile.contains_point(center_x, center_y, space=space):
            return profile
    return None


def normalize_capture_rect(
    rect: RectCoords,
    profiles: list[MonitorDpiProfile],
    *,
    source: CoordinateSpace = "physical",
    owner: MonitorDpiProfile | None = None,
) -> RectCoords:
    """Нормализовать rect захвата к физическим пикселям (#200).

    Каноническая точка входа DPI-нормализации: переводит координаты
    из пространства `source` в физические пиксели виртуального рабочего
    стола — пространство кадров WGC.

    Для logical-источника монитор-владелец берётся из `owner`; без
    него используется эвристика поиска по центру rect. Важно: в
    mixed-DPI конфигурациях логические пространства мониторов
    пересекаются (логические границы = физика / собственный масштаб),
    поэтому только по координатам владелец неоднозначен — источник
    логических координат обязан передать экран явно.

    Args:
        rect: Прямоугольник (x1, y1, x2, y2).
        profiles: Профили мониторов (см. `get_monitor_profiles`).
        source: Пространство входных координат.
        owner: Явный монитор-владелец для logical-источника.

    Returns:
        Прямоугольник в физических пикселях. Без подходящего монитора
        rect возвращается как есть: кроп кадра WGC всё равно ограничен
        границами кадра.
    """
    if source != "logical":
        return rect

    monitor = owner or find_monitor_for_rect(rect, profiles, space="logical")
    if monitor is None:
        return rect
    return convert_rect_to_physical(rect, monitor)


def get_monitor_profiles() -> list[MonitorDpiProfile]:
    """Получить профили всех активных мониторов.

    Безопасный фасад над `WindowsMonitorDpiProvider`: на не-Windows
    платформе или при ошибке перечисления возвращает пустой список.

    Returns:
        Список профилей мониторов.
    """
    return WindowsMonitorDpiProvider().get_profiles()


class WindowsMonitorDpiProvider:
    """Поставщик пер-мониторных DPI-профилей через Win32 API.

    Использует EnumDisplayMonitors (физические границы) и
    GetDpiForMonitor (эффективный DPI). Требует per-monitor
    DPI-awareness процесса (см. `ensure_process_dpi_awareness`):
    для DPI-unaware процесса система вернёт виртуализованные
    координаты и 96 DPI.
    """

    def get_profiles(self) -> list[MonitorDpiProfile]:
        """Собрать профили всех мониторов.

        Returns:
            Список профилей; пустой список на не-Windows или при
            ошибке перечисления.
        """
        if sys.platform != "win32":
            return []

        profiles: list[MonitorDpiProfile] = []
        try:
            from ctypes import wintypes

            class _MonitorRect(ctypes.Structure):
                _fields_ = [
                    ("left", wintypes.LONG),
                    ("top", wintypes.LONG),
                    ("right", wintypes.LONG),
                    ("bottom", wintypes.LONG),
                ]

            # Windows-specific: ctypes.WINFUNCTYPE не доступен в type stubs
            monitor_enum_proc: Any = ctypes.WINFUNCTYPE(  # type: ignore[attr-defined, unused-ignore]
                ctypes.c_int,
                wintypes.HMONITOR,
                wintypes.HDC,
                ctypes.POINTER(_MonitorRect),
                wintypes.LPARAM,
            )

            def _on_monitor(
                hmonitor: Any,
                _hdc: Any,
                rect_ptr: Any,
                _data: Any,
            ) -> int:
                rect = rect_ptr.contents
                left, top = int(rect.left), int(rect.top)
                profiles.append(
                    MonitorDpiProfile(
                        monitor_id=len(profiles) + 1,
                        left=left,
                        top=top,
                        width=int(rect.right - rect.left),
                        height=int(rect.bottom - rect.top),
                        dpi_scale=_query_monitor_dpi_scale(hmonitor),
                        is_primary=left == 0 and top == 0,
                    )
                )
                return 1

            user32 = ctypes.windll.user32
            callback = monitor_enum_proc(_on_monitor)
            if not user32.EnumDisplayMonitors(None, None, callback, 0):
                logger.debug("EnumDisplayMonitors не вернул мониторы")
            del callback
        except (AttributeError, OSError, ValueError) as e:
            # ValueError: ctypes.wintypes недоступен вне Windows
            logger.debug("Перечисление мониторов не удалось: %s", e)
            return []
        return profiles


def _query_monitor_dpi_scale(hmonitor: Any) -> float:
    """Запросить эффективный DPI-фактор монитора.

    Args:
        hmonitor: Дескриптор HMONITOR из EnumDisplayMonitors.

    Returns:
        DPI-фактор (1.0 = 100%); 1.0 при недоступности API —
        координаты в этом случае корректны на 100%-конфигурациях.
    """
    try:
        from ctypes import wintypes

        shcore = ctypes.WinDLL("shcore")
        dpi_x = wintypes.UINT()
        dpi_y = wintypes.UINT()
        result = shcore.GetDpiForMonitor(
            hmonitor,
            _MDT_EFFECTIVE_DPI,
            ctypes.byref(dpi_x),
            ctypes.byref(dpi_y),
        )
        if result == 0 and dpi_x.value > 0:
            return dpi_x.value / DEFAULT_DPI
    except (AttributeError, OSError, ValueError) as e:
        logger.debug("GetDpiForMonitor недоступен: %s", e)
    return 1.0


def ensure_process_dpi_awareness() -> bool:
    """Включить per-monitor v2 DPI-awareness процесса (Windows).

    Без awareness Win32 (EnumDisplayMonitors, GetSystemMetrics,
    GetDpiForMonitor) возвращает виртуализованные координаты, не
    совпадающие с физическими кадрами WGC, — источник «съехавшей»
    записи на scaled-мониторах. Qt6 выставляет awareness при создании
    QApplication; явный ранний вызов гарантирует единый DPI-контекст
    и в headless-режиме (API/CLI/Service), где Qt не инициализируется.

    Вызывать до любого обращения к геометрии мониторов.

    Returns:
        True, если awareness установлен этим вызовом; False — если
        уже установлен ранее, платформа не Windows или вызов не
        удался (это не ошибка работы приложения).
    """
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.windll.user32
        context = ctypes.c_void_p(_PMV2_DPI_AWARENESS_CONTEXT)
        if user32.SetProcessDpiAwarenessContext(context):
            return True
        # FALSE означает, что awareness уже установлен (например Qt6)
        # или ОС не поддерживает API — оба случая штатны.
        logger.debug("SetProcessDpiAwarenessContext не применён")
        return False
    except (AttributeError, OSError) as e:
        logger.debug("DPI-awareness недоступен: %s", e)
        return False
