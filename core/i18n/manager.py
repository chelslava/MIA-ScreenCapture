"""
Модуль менеджера локализации и переводов
=========================================

Обеспечивает загрузку каталогов сообщений gettext, потокобезопасное
переключение локалей, поддержку plural forms, контекста сообщений
и надежный механизм fallback.
"""

import ctypes
import gettext
import locale
import os
import sys
import threading
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Final

from logger_config import get_module_logger

from .constants import (
    DEFAULT_LOCALE,
    DOMAIN,
    FALLBACK_LOCALE,
    LOCALE_ALIASES,
    SUPPORTED_LOCALES,
)

logger = get_module_logger(__name__)


def _find_locales_dir() -> Path:
    """Определяет путь к каталогу с переводами с учетом упаковки."""
    # Режим PyInstaller OneFile/OneDir
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        meipass_locales = Path(meipass) / "locales"
        if meipass_locales.exists():
            return meipass_locales

    # Рядом с исполняемым файлом (frozen)
    if getattr(sys, "frozen", False):
        frozen_locales = Path(sys.executable).parent / "locales"
        if frozen_locales.exists():
            return frozen_locales

    # Режим разработки из исходного дерева
    src_locales = Path(__file__).resolve().parent.parent.parent / "locales"
    if src_locales.exists():
        return src_locales

    # Текущий рабочий каталог
    cwd_locales = Path.cwd() / "locales"
    if cwd_locales.exists():
        return cwd_locales

    # Каталог по умолчанию для создания
    return src_locales


class LazyString:
    """Ленивая строка для отложенного перевода на этапе исполнения."""

    def __init__(self, func: Any, *args: Any, **kwargs: Any) -> None:
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def __str__(self) -> str:
        return str(self._func(*self._args, **self._kwargs))

    def __repr__(self) -> str:
        return f"LazyString({self.__str__()!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LazyString):
            return str(self) == str(other)
        return str(self) == other

    def __hash__(self) -> int:
        return hash(str(self))

    def format(self, *args: Any, **kwargs: Any) -> str:
        return str(self).format(*args, **kwargs)


class I18nManager:
    """
    Менеджер локализации приложения.

    Обеспечивает кэширование каталогов gettext, определение языка
    системы/окружения/конфигурации и потокобезопасное управление активной локалью.
    """

    _instance: "I18nManager | None" = None
    _singleton_lock: Final[threading.Lock] = threading.Lock()

    def __init__(self, locales_dir: Path | str | None = None) -> None:
        """
        Инициализация менеджера интернационализации.

        Args:
            locales_dir: Путь к каталогу локалей (None для автоопределения).
        """
        self._locales_dir: Path = (
            Path(locales_dir) if locales_dir else _find_locales_dir()
        )
        self._lock = threading.RLock()
        self._thread_local = threading.local()
        self._global_locale: str = DEFAULT_LOCALE
        self._translations_cache: dict[str, gettext.NullTranslations] = {}

    @classmethod
    def get_instance(
        cls, locales_dir: Path | str | None = None
    ) -> "I18nManager":
        """Возвращает синглтон-экземпляр I18nManager."""
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = cls(locales_dir=locales_dir)
            return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Сбрасывает экземпляр синглтона (используется в тестах)."""
        with cls._singleton_lock:
            cls._instance = None

    @property
    def locales_dir(self) -> Path:
        """Путь к корневому каталогу локалей."""
        return self._locales_dir

    def normalize_locale(self, locale_code: str | None) -> str:
        """
        Нормализует код локали к поддерживаемому базовому формату.

        Args:
            locale_code: Строка локали (например 'ru_RU', 'en-US', 'auto', None).

        Returns:
            Нормализованный код ('ru', 'en' и т.д.) или FALLBACK_LOCALE.
        """
        if not locale_code or locale_code.strip() == "":
            return FALLBACK_LOCALE

        cleaned = locale_code.strip().lower().replace("-", "_")

        # Прямое совпадение с псевдонимами
        if cleaned in LOCALE_ALIASES:
            return LOCALE_ALIASES[cleaned]

        # Базовая часть до знака подчеркивания ('ru_RU.utf8' -> 'ru')
        base = cleaned.split(".")[0].split("_")[0]
        if base in SUPPORTED_LOCALES:
            return base

        if cleaned in SUPPORTED_LOCALES:
            return cleaned

        logger.debug(
            "Неизвестная локаль '%s', используется fallback '%s'",
            locale_code,
            FALLBACK_LOCALE,
        )
        return FALLBACK_LOCALE

    def detect_system_locale(self) -> str:
        """
        Определяет язык операционной системы.

        Приоритет:
        1. Переменные окружения (MIA_LANGUAGE, LC_ALL, LC_MESSAGES, LANG)
        2. Windows UI Language API (ctypes.windll.kernel32)
        3. locale.getdefaultlocale()
        4. Fallback locale

        Returns:
            Нормализованный код локали.
        """
        # 1. Переменные окружения
        for env_var in ("MIA_LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
            val = os.environ.get(env_var)
            if val:
                normalized = self.normalize_locale(val)
                if self.is_locale_supported(normalized):
                    return normalized

        # 2. Windows API
        if sys.platform == "win32":
            try:
                kernel32 = getattr(ctypes, "windll", None)
                if kernel32 and hasattr(kernel32, "kernel32"):
                    lang_id = int(kernel32.kernel32.GetUserDefaultUILanguage())
                    primary_lang_id = lang_id & 0x3FF
                # 0x19: Russian, 0x09: English, 0x07: German, 0x0C: French
                lang_map = {
                    0x19: "ru",
                    0x09: "en",
                    0x07: "de",
                    0x0C: "fr",
                    0x0A: "es",
                    0x04: "zh",
                }
                if primary_lang_id in lang_map:
                    detected = lang_map[primary_lang_id]
                    if self.is_locale_supported(detected):
                        return detected
            except Exception as e:
                logger.debug("Не удалось получить Windows UI Language: %s", e)

        # 3. Python locale stdlib
        try:
            default_loc, _ = locale.getdefaultlocale()
            if default_loc:
                normalized = self.normalize_locale(default_loc)
                if self.is_locale_supported(normalized):
                    return normalized
        except Exception as e:
            logger.debug("Ошибка getdefaultlocale: %s", e)

        return DEFAULT_LOCALE

    def is_locale_supported(self, locale_code: str) -> bool:
        """Проверяет, поддерживается ли указанная локаль."""
        return locale_code in SUPPORTED_LOCALES

    def get_supported_locales(self) -> dict[str, str]:
        """Возвращает словарь поддерживаемых локалей {код: название}."""
        return dict(SUPPORTED_LOCALES)

    def set_locale(self, locale_code: str, thread_only: bool = False) -> str:
        """
        Устанавливает текущую локаль.

        Args:
            locale_code: Код локали ('ru', 'en', 'auto' и др.).
            thread_only: Если True, локаль меняется только для текущего потока.

        Returns:
            Фактически установленный код локали.
        """
        if locale_code == "auto":
            resolved = self.detect_system_locale()
        else:
            resolved = self.normalize_locale(locale_code)

        if thread_only:
            self._thread_local.current_locale = resolved
        else:
            with self._lock:
                self._global_locale = resolved

        # Предзагружаем каталог
        self._get_translation(resolved)
        return resolved

    def get_locale(self) -> str:
        """
        Возвращает текущую активную локаль с учетом потока.

        Returns:
            Код локали ('ru', 'en' и др.).
        """
        thread_loc = getattr(self._thread_local, "current_locale", None)
        if thread_loc:
            return str(thread_loc)
        with self._lock:
            return self._global_locale

    @contextmanager
    def use_locale(self, locale_code: str) -> Generator[str, None, None]:
        """
        Контекстный менеджер для временного переключения локали в текущем потоке.

        Args:
            locale_code: Код локали.
        """
        prev_locale = getattr(self._thread_local, "current_locale", None)
        try:
            active = self.set_locale(locale_code, thread_only=True)
            yield active
        finally:
            if prev_locale is not None:
                self._thread_local.current_locale = prev_locale
            else:
                if hasattr(self._thread_local, "current_locale"):
                    del self._thread_local.current_locale

    def _ensure_mo_file(self, loc: str) -> None:
        """Автоматически компилирует .po в .mo, если бинарный каталог отсутствует или устарел."""
        try:
            lc_messages = self._locales_dir / loc / "LC_MESSAGES"
            po_file = lc_messages / f"{DOMAIN}.po"
            mo_file = lc_messages / f"{DOMAIN}.mo"

            if po_file.exists():
                should_compile = not mo_file.exists() or (
                    po_file.stat().st_mtime > mo_file.stat().st_mtime
                )
                if should_compile:
                    from babel.messages.mofile import write_mo
                    from babel.messages.pofile import read_po

                    with po_file.open("r", encoding="utf-8") as pf:
                        catalog = read_po(pf, locale=loc)
                    lc_messages.mkdir(parents=True, exist_ok=True)
                    with mo_file.open("wb") as mf:
                        write_mo(mf, catalog)
                    logger.debug(
                        "Скомпилирован каталог переводов для '%s' -> %s",
                        loc,
                        mo_file,
                    )
        except Exception as e:
            logger.debug(
                "Не удалось скомпилировать каталог переводов для '%s': %s",
                loc,
                e,
            )

    def _get_translation(self, loc: str) -> gettext.NullTranslations:
        """Загружает и кэширует каталог переводов."""
        with self._lock:
            if loc in self._translations_cache:
                return self._translations_cache[loc]

            self._ensure_mo_file(loc)
            if loc != FALLBACK_LOCALE:
                self._ensure_mo_file(FALLBACK_LOCALE)

            trans: gettext.NullTranslations
            try:
                trans = gettext.translation(
                    domain=DOMAIN,
                    localedir=str(self._locales_dir),
                    languages=[loc, FALLBACK_LOCALE],
                    fallback=True,
                )
            except Exception as e:
                logger.warning(
                    "Ошибка загрузки каталога переводов для '%s': %s. "
                    "Используется NullTranslations.",
                    loc,
                    e,
                )
                trans = gettext.NullTranslations()

            self._translations_cache[loc] = trans
            return trans

    def gettext(self, message: str) -> str:
        """Переводит одиночную строку для текущей локали."""
        if not message:
            return message
        trans = self._get_translation(self.get_locale())
        return trans.gettext(message)

    def ngettext(self, singular: str, plural: str, n: int) -> str:
        """
        Переводит строку с учетом формы множественного числа.

        Args:
            singular: Форма единственного числа.
            plural: Форма множественного числа.
            n: Числовое количество.

        Returns:
            Переведенная строка.
        """
        trans = self._get_translation(self.get_locale())
        return trans.ngettext(singular, plural, n)

    def pgettext(self, context: str, message: str) -> str:
        """
        Переводит строку с учетом контекста (msgctxt в gettext).

        Args:
            context: Контекст сообщения (например 'button', 'status').
            message: Исходная строка.

        Returns:
            Переведенная строка.
        """
        if not message:
            return message
        trans = self._get_translation(self.get_locale())
        pgettext_fn = getattr(trans, "pgettext", None)
        if callable(pgettext_fn):
            return str(pgettext_fn(context, message))

        # Fallback для старых версий gettext (разделитель \x04)
        raw_msg = f"{context}\x04{message}"
        translated = trans.gettext(raw_msg)
        if translated == raw_msg:
            return message
        return translated

    def npgettext(
        self, context: str, singular: str, plural: str, n: int
    ) -> str:
        """Переводит форму множественного числа с учетом контекста."""
        trans = self._get_translation(self.get_locale())
        npgettext_fn = getattr(trans, "npgettext", None)
        if callable(npgettext_fn):
            return str(npgettext_fn(context, singular, plural, n))

        # Fallback
        raw_singular = f"{context}\x04{singular}"
        raw_plural = f"{context}\x04{plural}"
        translated = trans.ngettext(raw_singular, raw_plural, n)
        if "\x04" in translated:
            return translated.split("\x04", 1)[1]
        return translated

    def lazy_gettext(self, message: str) -> LazyString:
        """Создает ленивую строку gettext."""
        return LazyString(self.gettext, message)

    def lazy_pgettext(self, context: str, message: str) -> LazyString:
        """Создает ленивую строку pgettext."""
        return LazyString(self.pgettext, context, message)
