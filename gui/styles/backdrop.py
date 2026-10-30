"""
Материалы Windows 11 (Mica/Acrylic) через DWM (#157)
====================================================

Опциональный системный фон окна: ``DwmSetWindowAttribute`` с
``DWMWA_SYSTEMBACKDROP_TYPE``. На Windows 10 / старом dwmapi деградирует
тихо — окно остаётся с обычной QSS-темой.
"""

from __future__ import annotations

import ctypes
import platform
from typing import Final

from logger_config import get_module_logger

logger = get_module_logger(__name__)

# Windows 11 = сборка 22000+
_WIN11_BUILD: Final[int] = 22000

# DWMWA_SYSTEMBACKDROP_TYPE (Windows 11 22H2+)
_DWMWA_SYSTEMBACKDROP_TYPE: Final[int] = 38
# DWMSBT_MAINWINDOW — материал Mica
_DWMSBT_MAINWINDOW: Final[int] = 2


def is_windows_11() -> bool:
    """Запущено ли приложение на Windows 11 (сборка 22000+)."""
    if platform.system() != "Windows":
        return False
    version = platform.version()  # "10.0.22000" и т.п.
    try:
        build = int(version.split(".")[2])
    except (IndexError, ValueError):
        return False
    return build >= _WIN11_BUILD


def backdrop_supported() -> bool:
    """Доступен ли системный материал в текущем окружении."""
    return is_windows_11()


def resolve_backdrop_active(enabled: bool) -> bool:
    """Итоговая активность материала: настройка пользователя и поддержка ОС.

    Args:
        enabled: Пользовательская настройка ``win11_backdrop``.

    Returns:
        True, если материал нужно включить (обе проверки).
    """
    return bool(enabled) and backdrop_supported()


def apply_mica_backdrop(hwnd: int) -> bool:
    """
    Включить материал Mica для окна (best-effort, #157).

    Args:
        hwnd: Дескриптор окна (``int(widget.winId())``).

    Returns:
        True, если DWM применил материал; False на Windows 10, старом
        dwmapi или при ошибке вызова — окно остаётся с обычной темой.
    """
    if not is_windows_11():
        logger.debug("Mica недоступен: ОС ниже Windows 11")
        return False

    try:
        dwmapi = ctypes.windll.dwmapi
        value = _DWMSBT_MAINWINDOW
        result = dwmapi.DwmSetWindowAttribute(
            hwnd,
            _DWMWA_SYSTEMBACKDROP_TYPE,
            ctypes.byref(ctypes.c_int(value)),
            ctypes.sizeof(ctypes.c_int),
        )
        if result == 0:
            logger.info("Материал Mica применён к окну")
            return True
        logger.debug("DwmSetWindowAttribute вернул HRESULT=%s", result)
        return False
    except Exception as e:
        logger.debug("Не удалось применить Mica: %s", e)
        return False
