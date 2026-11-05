"""Цепочки FFmpeg-фильтров шумоподавления для микрофона (#169).

Применяются только к микрофонной дорожке на этапе объединения с видео
(``-af``); системный звук не обрабатывается. Модели RNNoise (``arnndn``)
не используются: требуют поставляемого файла модели с отдельной лицензией.
"""

from __future__ import annotations

from typing import Final

NOISE_SUPPRESSION_LEVELS: Final[tuple[str, ...]] = (
    "off",
    "light",
    "strong",
)
DEFAULT_NOISE_SUPPRESSION_LEVEL = "off"

# «Лёгкое»: срез низкочастотного гула и верхов + мягкое FFT-подавление
_LIGHT_FILTERS: Final[str] = "highpass=f=80,lowpass=f=8000,afftdn=nr=10:nf=-25"
# «Сильное»: те же полосы + агрессивное подавление с адаптивным минимумом
_STRONG_FILTERS: Final[str] = (
    "highpass=f=100,lowpass=f=7500,afftdn=nr=24:nf=-35:tn=1"
)


def normalize_noise_suppression_level(level: str | None) -> str:
    """Нормализовать уровень шумоподавления (#169).

    Args:
        level: Строка уровня из конфига/API; `None` — как «off».

    Returns:
        Один из `NOISE_SUPPRESSION_LEVELS`; неизвестные значения
        заменяются на `DEFAULT_NOISE_SUPPRESSION_LEVEL`.
    """
    if not level:
        return DEFAULT_NOISE_SUPPRESSION_LEVEL
    normalized = str(level).strip().lower()
    if normalized not in NOISE_SUPPRESSION_LEVELS:
        return DEFAULT_NOISE_SUPPRESSION_LEVEL
    return normalized


def build_noise_filter_chain(level: str | None) -> str | None:
    """Построить цепочку аудио-фильтров для уровня (#169).

    Args:
        level: Уровень шумоподавления ("off"/"light"/"strong").

    Returns:
        Строка для FFmpeg ``-af`` или `None`, если подавление выключено
        или уровень неизвестен.
    """
    normalized = normalize_noise_suppression_level(level)
    if normalized == "light":
        return _LIGHT_FILTERS
    if normalized == "strong":
        return _STRONG_FILTERS
    return None
