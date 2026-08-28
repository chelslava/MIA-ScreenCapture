"""
Модуль locale-aware форматирования
==================================

Предоставляет функции форматирования чисел, дат, времени, размеров файлов
и процентов в соответствии с правилами текущей или указанной локали.
Использует библиотеку Babel с надежными fallback-реализациями.
"""

from datetime import date, datetime, time

import babel.dates
import babel.numbers

from logger_config import get_module_logger

from .manager import I18nManager

logger = get_module_logger(__name__)


def _get_effective_locale(loc: str | None = None) -> str:
    """Возвращает код локали для форматирования."""
    if loc:
        return I18nManager.get_instance().normalize_locale(loc)
    return I18nManager.get_instance().get_locale()


def format_date_locale(
    d: date | datetime | str | None,
    format: str = "medium",
    locale_code: str | None = None,
) -> str:
    """
    Форматирует дату согласно локали.

    Args:
        d: Дата (date, datetime или ISO-строка).
        format: 'short', 'medium', 'long', 'full' или шаблон формата.
        locale_code: Код локали (None для текущей активной).

    Returns:
        Отформатированная строка даты.
    """
    if d is None:
        return ""
    if isinstance(d, str):
        try:
            d = datetime.fromisoformat(d)
        except Exception:
            return str(d)

    loc = _get_effective_locale(locale_code)
    try:
        return str(babel.dates.format_date(d, format=format, locale=loc))
    except Exception as e:
        logger.debug("Ошибка Babel format_date: %s", e)
        if isinstance(d, (date, datetime)):
            return d.strftime("%Y-%m-%d")
        return str(d)


def format_datetime_locale(
    dt: datetime | str | None,
    format: str = "medium",
    locale_code: str | None = None,
) -> str:
    """
    Форматирует дату и время согласно локали.

    Args:
        dt: Дата и время (datetime или ISO-строка).
        format: 'short', 'medium', 'long', 'full'.
        locale_code: Код локали.

    Returns:
        Отформатированная строка даты и времени.
    """
    if dt is None:
        return ""
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return str(dt)

    loc = _get_effective_locale(locale_code)
    try:
        return str(babel.dates.format_datetime(dt, format=format, locale=loc))
    except Exception as e:
        logger.debug("Ошибка Babel format_datetime: %s", e)
        if isinstance(dt, datetime):
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return str(dt)


def format_time_locale(
    t: time | datetime | float | int | str | None,
    format: str = "medium",
    locale_code: str | None = None,
) -> str:
    """
    Форматирует время суток согласно локали.

    Args:
        t: Время суток (time, datetime или ISO-строка).
        format: 'short', 'medium', 'long', 'full'.
        locale_code: Код локали.

    Returns:
        Отформатированная строка времени.
    """
    if t is None:
        return ""
    if isinstance(t, str):
        try:
            t = time.fromisoformat(t)
        except Exception:
            return str(t)

    loc = _get_effective_locale(locale_code)
    try:
        return str(babel.dates.format_time(t, format=format, locale=loc))
    except Exception as e:
        logger.debug("Ошибка Babel format_time: %s", e)
        if isinstance(t, (time, datetime)):
            return t.strftime("%H:%M:%S")
        return str(t)


def format_number_locale(
    number: int | float | None,
    locale_code: str | None = None,
) -> str:
    """
    Форматирует число с разделителями тысяч и десятичной точкой по локали.

    Args:
        number: Число.
        locale_code: Код локали.

    Returns:
        Отформатированная строка числа.
    """
    if number is None:
        return ""
    loc = _get_effective_locale(locale_code)
    try:
        return str(babel.numbers.format_number(number, locale=loc))
    except Exception as e:
        logger.debug("Ошибка Babel format_number: %s", e)
        return str(number)


def format_decimal_locale(
    number: int | float | None,
    format: str | None = None,
    locale_code: str | None = None,
) -> str:
    """Форматирует десятичное число с поддержкой шаблонов."""
    if number is None:
        return ""
    loc = _get_effective_locale(locale_code)
    try:
        return str(
            babel.numbers.format_decimal(number, format=format, locale=loc)
        )
    except Exception as e:
        logger.debug("Ошибка Babel format_decimal: %s", e)
        return f"{number:.2f}"


def format_percent_locale(
    number: float | None,
    format: str | None = None,
    locale_code: str | None = None,
) -> str:
    """Форматирует значение в процентах (0.25 -> '25%')."""
    if number is None:
        return ""
    loc = _get_effective_locale(locale_code)
    try:
        return str(
            babel.numbers.format_percent(number, format=format, locale=loc)
        )
    except Exception as e:
        logger.debug("Ошибка Babel format_percent: %s", e)
        return f"{number * 100:.1f}%"


def format_filesize_locale(
    size_bytes: int | float,
    locale_code: str | None = None,
) -> str:
    """
    Форматирует размер файла с локализованными единицами измерения.

    Args:
        size_bytes: Размер в байтах.
        locale_code: Код локали.

    Returns:
        Строка размера (например: "1,5 МБ" для ru, "1.5 MB" для en).
    """
    loc = _get_effective_locale(locale_code)

    units_ru = ["Б", "КБ", "МБ", "ГБ", "ТБ", "ПБ"]
    units_en = ["B", "KB", "MB", "GB", "TB", "PB"]
    units = units_ru if loc == "ru" else units_en

    size: float = float(size_bytes)
    for unit in units[:-1]:
        if size < 1024:
            formatted_num = format_decimal_locale(
                size, format="#,##0.0", locale_code=loc
            )
            return f"{formatted_num} {unit}"
        size /= 1024

    formatted_num = format_decimal_locale(
        size, format="#,##0.0", locale_code=loc
    )
    return f"{formatted_num} {units[-1]}"


def format_duration_locale(
    seconds: float | int,
    locale_code: str | None = None,
) -> str:
    """
    Форматирует длительность в формат ЧЧ:ММ:СС или ММ:СС.

    Args:
        seconds: Количество секунд.
        locale_code: Код локали.

    Returns:
        Строка времени.
    """
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
