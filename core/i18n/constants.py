"""
Константы модуля интернационализации
====================================

Определяет поддерживаемые языки, псевдонимы локалей и параметры по умолчанию.
"""

from typing import Final

DEFAULT_LOCALE: Final[str] = "ru"
FALLBACK_LOCALE: Final[str] = "ru"
DOMAIN: Final[str] = "mia"

SUPPORTED_LOCALES: Final[dict[str, str]] = {
    "en": "English",
    "ru": "Русский",
}

# Псевдонимы и маппинг региональных локалей к поддерживаемым базовым кодам
LOCALE_ALIASES: Final[dict[str, str]] = {
    "ru": "ru",
    "ru_ru": "ru",
    "ru-ru": "ru",
    "ru_by": "ru",
    "ru_kz": "ru",
    "ru_ua": "ru",
    "en": "en",
    "en_us": "en",
    "en-us": "en",
    "en_gb": "en",
    "en-gb": "en",
    "en_ca": "en",
    "en_au": "en",
}
