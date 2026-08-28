"""
Пакет интернационализации и локализации (i18n / l10n)
=====================================================

Предоставляет функции перевода строк, pluralization, context-aware переводов
и locale-aware форматирования дат, времени, чисел и размеров файлов.
"""

from typing import Any

from .constants import (
    DEFAULT_LOCALE,
    DOMAIN,
    FALLBACK_LOCALE,
    LOCALE_ALIASES,
    SUPPORTED_LOCALES,
)
from .formatters import (
    format_date_locale,
    format_datetime_locale,
    format_decimal_locale,
    format_duration_locale,
    format_filesize_locale,
    format_number_locale,
    format_percent_locale,
    format_time_locale,
)
from .manager import I18nManager, LazyString


def _(message: str) -> str:
    """Переводит одиночную строку для текущей локали."""
    return I18nManager.get_instance().gettext(message)


def gettext(message: str) -> str:
    """Переводит одиночную строку для текущей локали."""
    return I18nManager.get_instance().gettext(message)


def ngettext(singular: str, plural: str, n: int) -> str:
    """Переводит строку с учетом формы множественного числа."""
    return I18nManager.get_instance().ngettext(singular, plural, n)


def pgettext(context: str, message: str) -> str:
    """Переводит строку с учетом контекста сообщения."""
    return I18nManager.get_instance().pgettext(context, message)


def npgettext(context: str, singular: str, plural: str, n: int) -> str:
    """Переводит строку множественного числа с учетом контекста."""
    return I18nManager.get_instance().npgettext(context, singular, plural, n)


def lazy_gettext(message: str) -> LazyString:
    """Ленивый перевод одиночной строки."""
    return I18nManager.get_instance().lazy_gettext(message)


def lazy_pgettext(context: str, message: str) -> LazyString:
    """Ленивый перевод строки с контекстом."""
    return I18nManager.get_instance().lazy_pgettext(context, message)


def set_locale(locale_code: str, thread_only: bool = False) -> str:
    """Устанавливает активную локаль."""
    return I18nManager.get_instance().set_locale(
        locale_code, thread_only=thread_only
    )


def get_locale() -> str:
    """Возвращает текущую активную локаль."""
    return I18nManager.get_instance().get_locale()


def use_locale(locale_code: str) -> Any:
    """Контекстный менеджер временного переключения локали."""
    return I18nManager.get_instance().use_locale(locale_code)


def get_supported_locales() -> dict[str, str]:
    """Возвращает словарь поддерживаемых локалей {код: название}."""
    return I18nManager.get_instance().get_supported_locales()


def is_locale_supported(locale_code: str) -> bool:
    """Проверяет, поддерживается ли локаль."""
    return I18nManager.get_instance().is_locale_supported(locale_code)


__all__ = [
    "_",
    "gettext",
    "ngettext",
    "pgettext",
    "npgettext",
    "lazy_gettext",
    "lazy_pgettext",
    "set_locale",
    "get_locale",
    "use_locale",
    "get_supported_locales",
    "is_locale_supported",
    "format_date_locale",
    "format_datetime_locale",
    "format_time_locale",
    "format_number_locale",
    "format_decimal_locale",
    "format_percent_locale",
    "format_filesize_locale",
    "format_duration_locale",
    "I18nManager",
    "LazyString",
    "SUPPORTED_LOCALES",
    "DEFAULT_LOCALE",
    "FALLBACK_LOCALE",
    "LOCALE_ALIASES",
    "DOMAIN",
]
