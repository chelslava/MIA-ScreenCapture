"""
Плавные переходы вкладок (#161)
===============================

Fade-анимация входа страницы QStackedWidget с уважением к reduced-motion:
системная настройка Windows «анимации элементов интерфейса» и
пользовательский флаг ``ui_animations`` в config.json.
"""

from __future__ import annotations

import platform
from typing import Any, Final

from logger_config import get_module_logger

logger = get_module_logger(__name__)

ANIMATION_DURATION_MS: Final[int] = 180

# SPI_GETCLIENTAREAANIMATION: системный переключатель анимаций Windows
_SPI_GETCLIENTAREAANIMATION = 0x1042


def _query_client_area_animation() -> bool | None:
    """
    Читает системный флаг анимаций Windows (SPI_GETCLIENTAREAANIMATION).

    Returns:
        True — анимации включены, False — отключены, None — не удалось
        прочитать (не Windows или ошибка API).
    """
    if platform.system() != "Windows":
        return None
    try:
        import ctypes
        import ctypes.wintypes

        enabled = ctypes.wintypes.BOOL()
        result = ctypes.windll.user32.SystemParametersInfoW(
            _SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(enabled), 0
        )
        if result:
            return bool(enabled.value)
    except Exception as e:  # pragma: no cover - защитная ветка
        logger.debug("Не удалось прочитать системные анимации: %s", e)
    return None


def reduced_motion_preferred() -> bool:
    """
    Предпочитает ли система ограничение анимаций (reduced motion).

    На Windows читает ``SystemParametersInfo(SPI_GETCLIENTAREAANIMATION)``:
    пользователь, отключивший анимации интерфейса в системе, не должен
    получать fade-переходы. На других платформах и при ошибке чтения —
    False (анимации разрешены).

    Returns:
        True, если системные анимации отключены.
    """
    system_animations = _query_client_area_animation()
    if system_animations is None:
        return False
    return not system_animations


def animate_page_in(
    page: Any, duration_ms: int = ANIMATION_DURATION_MS
) -> None:
    """
    Плавное появление страницы стека (fade-in, #161).

    Повторный вызов во время активной анимации игнорируется (защита
    от быстрого переключения вкладок). Эффект снимается по завершении,
    чтобы не влиять на дальнейший рендер.

    Args:
        page: Виджет-страница QStackedWidget.
        duration_ms: Длительность анимации в мс; <= 0 — no-op.
    """
    if duration_ms <= 0 or page is None:
        return
    if getattr(page, "_fade_in_animation", None) is not None:
        # Анимация этой страницы уже идёт
        return

    from PyQt6.QtCore import (
        QEasingCurve,
        QPropertyAnimation,
    )
    from PyQt6.QtWidgets import QGraphicsOpacityEffect

    effect = QGraphicsOpacityEffect(page)
    effect.setOpacity(0.0)
    page.setGraphicsEffect(effect)

    animation = QPropertyAnimation(effect, b"opacity", page)
    animation.setDuration(duration_ms)
    animation.setStartValue(0.0)
    animation.setEndValue(1.0)
    animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _cleanup() -> None:
        page.setGraphicsEffect(None)
        page._fade_in_animation = None

    animation.finished.connect(_cleanup)

    page._fade_in_animation = animation
    animation.start()
