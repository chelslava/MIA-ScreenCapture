"""
Unit-тесты для модуля интернационализации (core/i18n)
=====================================================

Проверяет:
- Разрешение и определение локали (explicit, system, env, fallback).
- Перевод строк (English, Russian, fallback).
- Плюрализацию (0, 1, 2, 5, 21, 22, 25, 101, etc.).
- Контекстные переводы (pgettext).
- Locale-aware форматирование чисел, процентов, размеров файлов и дат.
- Потокобезопасность и контекстный менеджер use_locale.
- Интеграцию с CLI и Config.
"""

import threading
from datetime import date, datetime, time

import pytest

from cli.parser import parse_args
from config import AppSettingsSchema
from core.i18n import (
    FALLBACK_LOCALE,
    I18nManager,
    _,
    format_date_locale,
    format_datetime_locale,
    format_decimal_locale,
    format_duration_locale,
    format_filesize_locale,
    format_number_locale,
    format_percent_locale,
    format_time_locale,
    get_locale,
    get_supported_locales,
    is_locale_supported,
    lazy_gettext,
    ngettext,
    pgettext,
    set_locale,
    use_locale,
)
from scripts.i18n import check_catalogs


class TestLocaleResolution:
    """Тестирование нормализации и определения локалей."""

    def setup_method(self) -> None:
        I18nManager.reset_instance()

    def teardown_method(self) -> None:
        I18nManager.reset_instance()

    def test_supported_locales_list(self) -> None:
        supported = get_supported_locales()
        assert "en" in supported
        assert "ru" in supported
        assert is_locale_supported("en") is True
        assert is_locale_supported("ru") is True
        assert is_locale_supported("unsupported_lang") is False

    def test_normalize_locale_standard(self) -> None:
        manager = I18nManager.get_instance()
        assert manager.normalize_locale("ru") == "ru"
        assert manager.normalize_locale("RU") == "ru"
        assert manager.normalize_locale("en") == "en"
        assert manager.normalize_locale("EN") == "en"
        assert manager.normalize_locale("ru_RU") == "ru"
        assert manager.normalize_locale("ru-ru") == "ru"
        assert manager.normalize_locale("en_US") == "en"
        assert manager.normalize_locale("en-gb") == "en"

    def test_normalize_locale_fallback_on_invalid(self) -> None:
        manager = I18nManager.get_instance()
        assert manager.normalize_locale("invalid_code_xyz") == FALLBACK_LOCALE
        assert manager.normalize_locale("") == FALLBACK_LOCALE
        assert manager.normalize_locale(None) == FALLBACK_LOCALE

    def test_detect_system_locale_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manager = I18nManager.get_instance()
        monkeypatch.setenv("MIA_LANGUAGE", "ru")
        assert manager.detect_system_locale() == "ru"

        monkeypatch.setenv("MIA_LANGUAGE", "en_US")
        assert manager.detect_system_locale() == "en"

    def test_set_and_get_locale(self) -> None:
        set_locale("ru")
        assert get_locale() == "ru"

        set_locale("en")
        assert get_locale() == "en"


class TestTranslations:
    """Тестирование перевода строк и плюрализации."""

    def setup_method(self) -> None:
        I18nManager.reset_instance()

    def teardown_method(self) -> None:
        I18nManager.reset_instance()

    def test_russian_translations(self) -> None:
        set_locale("ru")
        assert _("Внешний вид") == "Внешний вид"
        assert _("Горячие клавиши") == "Горячие клавиши"
        assert _("Выход") == "Выход"
        assert _("ПАУЗА") == "ПАУЗА"
        assert _("ЗАПИСЬ") == "ЗАПИСЬ"

    def test_english_translations(self) -> None:
        set_locale("en")
        assert _("Внешний вид") == "Appearance"
        assert _("Горячие клавиши") == "Hotkeys"
        assert _("Выход") == "Exit"
        assert _("ПАУЗА") == "PAUSED"
        assert _("ЗАПИСЬ") == "RECORDING"

    def test_missing_translation_fallback_to_source(self) -> None:
        set_locale("en")
        assert (
            _("Some Untranslated String 12345")
            == "Some Untranslated String 12345"
        )

    def test_empty_string_translation(self) -> None:
        assert _("") == ""

    def test_russian_plural_forms(self) -> None:
        set_locale("ru")
        # 1 задача (msgstr[0])
        assert (
            ngettext(
                "Запланированная задача ({count}):",
                "Запланированные задачи ({count}):",
                1,
            ).format(count=1)
            == "Запланированная задача (1):"
        )
        assert (
            ngettext(
                "Запланированная задача ({count}):",
                "Запланированные задачи ({count}):",
                21,
            ).format(count=21)
            == "Запланированная задача (21):"
        )
        assert (
            ngettext(
                "Запланированная задача ({count}):",
                "Запланированные задачи ({count}):",
                101,
            ).format(count=101)
            == "Запланированная задача (101):"
        )

        # 2, 3, 4 задачи (msgstr[1])
        assert (
            ngettext(
                "Запланированная задача ({count}):",
                "Запланированные задачи ({count}):",
                2,
            ).format(count=2)
            == "Запланированные задачи (2):"
        )
        assert (
            ngettext(
                "Запланированная задача ({count}):",
                "Запланированные задачи ({count}):",
                4,
            ).format(count=4)
            == "Запланированные задачи (4):"
        )
        assert (
            ngettext(
                "Запланированная задача ({count}):",
                "Запланированные задачи ({count}):",
                24,
            ).format(count=24)
            == "Запланированные задачи (24):"
        )

        # 5, 6..20 задач (msgstr[2])
        assert (
            ngettext(
                "Запланированная задача ({count}):",
                "Запланированные задачи ({count}):",
                0,
            ).format(count=0)
            == "Запланированных задач (0):"
        )
        assert (
            ngettext(
                "Запланированная задача ({count}):",
                "Запланированные задачи ({count}):",
                5,
            ).format(count=5)
            == "Запланированных задач (5):"
        )
        assert (
            ngettext(
                "Запланированная задача ({count}):",
                "Запланированные задачи ({count}):",
                11,
            ).format(count=11)
            == "Запланированных задач (11):"
        )
        assert (
            ngettext(
                "Запланированная задача ({count}):",
                "Запланированные задачи ({count}):",
                25,
            ).format(count=25)
            == "Запланированных задач (25):"
        )

    def test_english_plural_forms(self) -> None:
        set_locale("en")
        assert (
            ngettext(
                "Запланированная задача ({count}):",
                "Запланированные задачи ({count}):",
                1,
            ).format(count=1)
            == "Scheduled task (1):"
        )
        assert (
            ngettext(
                "Запланированная задача ({count}):",
                "Запланированные задачи ({count}):",
                0,
            ).format(count=0)
            == "Scheduled tasks (0):"
        )
        assert (
            ngettext(
                "Запланированная задача ({count}):",
                "Запланированные задачи ({count}):",
                2,
            ).format(count=2)
            == "Scheduled tasks (2):"
        )
        assert (
            ngettext(
                "Запланированная задача ({count}):",
                "Запланированные задачи ({count}):",
                5,
            ).format(count=5)
            == "Scheduled tasks (5):"
        )

    def test_context_pgettext(self) -> None:
        set_locale("en")
        # Testing context lookup and fallback
        assert pgettext("button", "Open") == "Open"
        assert pgettext("state", "Open") == "Open"

    def test_lazy_gettext(self) -> None:
        lazy_str = lazy_gettext("Внешний вид")
        set_locale("ru")
        assert str(lazy_str) == "Внешний вид"
        set_locale("en")
        assert str(lazy_str) == "Appearance"


class TestLocaleFormatters:
    """Тестирование форматирования чисел, процентов, размеров файлов и дат."""

    def test_format_number_locale(self) -> None:
        assert format_number_locale(1000, locale_code="en") in (
            "1,000",
            "1000",
        )
        assert format_number_locale(1000, locale_code="ru") in (
            "1 000",
            "1\xa0000",
            "1000",
        )

    def test_format_decimal_locale(self) -> None:
        en_dec = format_decimal_locale(1234.56, locale_code="en")
        assert "1,234.56" in en_dec or "1234.56" in en_dec

        ru_dec = format_decimal_locale(1234.56, locale_code="ru")
        assert (
            "1 234,56" in ru_dec
            or "1\xa0234,56" in ru_dec
            or "1234,56" in ru_dec
        )

    def test_format_percent_locale(self) -> None:
        en_pct = format_percent_locale(0.75, locale_code="en")
        assert "75%" in en_pct

        ru_pct = format_percent_locale(0.75, locale_code="ru")
        assert "75" in ru_pct and "%" in ru_pct

    def test_format_filesize_locale(self) -> None:
        assert "KB" in format_filesize_locale(2048, locale_code="en")
        assert "MB" in format_filesize_locale(1048576 * 5, locale_code="en")

        assert "КБ" in format_filesize_locale(2048, locale_code="ru")
        assert "МБ" in format_filesize_locale(1048576 * 5, locale_code="ru")

    def test_format_duration_locale(self) -> None:
        assert format_duration_locale(45) == "00:45"
        assert format_duration_locale(125) == "02:05"
        assert format_duration_locale(3665) == "01:01:05"

    def test_format_date_and_time_locale(self) -> None:
        d = date(2026, 8, 28)
        dt = datetime(2026, 8, 28, 14, 30, 0)
        t = time(14, 30, 0)

        en_date = format_date_locale(d, locale_code="en")
        assert "2026" in en_date or "Aug" in en_date or "8" in en_date

        ru_date = format_date_locale(d, locale_code="ru")
        assert "2026" in ru_date or "авг" in ru_date or "28" in ru_date

        en_time = format_time_locale(t, locale_code="en")
        assert "2:30" in en_time or "14:30" in en_time

        ru_time = format_time_locale(t, locale_code="ru")
        assert "14:30" in ru_time

        en_dt = format_datetime_locale(dt, locale_code="en")
        assert "2026" in en_dt


class TestThreadSafetyAndContext:
    """Тестирование потокобезопасности и use_locale."""

    def test_use_locale_context_manager(self) -> None:
        set_locale("ru")
        assert _("Внешний вид") == "Внешний вид"

        with use_locale("en") as active:
            assert active == "en"
            assert get_locale() == "en"
            assert _("Внешний вид") == "Appearance"

        assert get_locale() == "ru"
        assert _("Внешний вид") == "Внешний вид"

    def test_multithreaded_locale_isolation(self) -> None:
        set_locale("en")
        results: dict[str, str] = {}

        def thread_task(target_loc: str) -> None:
            with use_locale(target_loc):
                import time as t

                t.sleep(0.01)
                results[target_loc] = _("Внешний вид")

        t1 = threading.Thread(target=thread_task, args=("ru",))
        t2 = threading.Thread(target=thread_task, args=("en",))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results["ru"] == "Внешний вид"
        assert results["en"] == "Appearance"
        assert get_locale() == "en"


class TestCLIAndConfigIntegration:
    """Тестирование интеграции языка с CLI и конфигурацией."""

    def test_cli_language_argument(self) -> None:
        config = parse_args(["--language", "ru", "--headless"])
        assert config.get("language") == "ru"

        config_short = parse_args(["--lang", "en", "--headless"])
        assert config_short.get("language") == "en"

    def test_config_schema_language_validation(self) -> None:
        schema = AppSettingsSchema(language="ru")
        assert schema.language == "ru"

        schema_auto = AppSettingsSchema(language="auto")
        assert schema_auto.language == "auto"

        schema_invalid = AppSettingsSchema(language="unsupported_lang_123")
        assert schema_invalid.language == "en"

    def test_catalog_check_script(self) -> None:
        # Проверка, что скрипт check_catalogs возвращает 0 (валидные каталоги)
        res = check_catalogs(strict=True)
        assert res == 0


class TestI18nManagerExtended:
    """Расширенные тесты для веток core/i18n/manager.py."""

    def setup_method(self) -> None:
        I18nManager.reset_instance()

    def teardown_method(self) -> None:
        I18nManager.reset_instance()

    def test_lazy_string_methods(self) -> None:
        from core.i18n import lazy_pgettext
        from core.i18n.manager import LazyString

        ls = LazyString(lambda: "hello")
        assert repr(ls) == "LazyString('hello')"
        assert ls == "hello"
        assert ls == LazyString(lambda: "hello")
        assert ls != "world"
        assert hash(ls) == hash("hello")

        ls_fmt = LazyString(lambda: "value: {}")
        assert ls_fmt.format(42) == "value: 42"

        lp = lazy_pgettext("button", "Open")
        with use_locale("en"):
            assert str(lp) == "Open"

    def test_find_locales_dir_branches(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        import sys

        from core.i18n.manager import _find_locales_dir

        # 1. MEIPASS
        meipass_loc = tmp_path / "meipass_loc"
        (meipass_loc / "locales").mkdir(parents=True)
        monkeypatch.setattr(sys, "_MEIPASS", str(meipass_loc), raising=False)
        assert _find_locales_dir() == meipass_loc / "locales"

        # 2. Frozen
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        fake_exe = tmp_path / "app.exe"
        (tmp_path / "locales").mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(sys, "executable", str(fake_exe))
        assert _find_locales_dir() == tmp_path / "locales"

    def test_detect_system_locale_windows_api(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        manager = I18nManager.get_instance()
        monkeypatch.delenv("MIA_LANGUAGE", raising=False)
        monkeypatch.delenv("LC_ALL", raising=False)
        monkeypatch.delenv("LC_MESSAGES", raising=False)
        monkeypatch.delenv("LANG", raising=False)

        class MockKernel32:
            def __init__(self, lang_id):
                self._lang_id = lang_id

            def GetUserDefaultUILanguage(self):
                return self._lang_id

        class MockWindll:
            def __init__(self, lang_id):
                self.kernel32 = MockKernel32(lang_id)

        import ctypes

        monkeypatch.setattr(
            ctypes, "windll", MockWindll(0x0419), raising=False
        )  # Russian
        assert manager.detect_system_locale() == "ru"

        monkeypatch.setattr(
            ctypes, "windll", MockWindll(0x0409), raising=False
        )  # English
        assert manager.detect_system_locale() == "en"

        # Auto locale switch
        assert set_locale("auto") in ("ru", "en")

    def test_detect_system_locale_fallback(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import locale
        import sys

        manager = I18nManager.get_instance()
        monkeypatch.delenv("MIA_LANGUAGE", raising=False)
        monkeypatch.delenv("LC_ALL", raising=False)
        monkeypatch.delenv("LC_MESSAGES", raising=False)
        monkeypatch.delenv("LANG", raising=False)
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setattr(
            locale, "getdefaultlocale", lambda: ("fr_FR", "UTF-8")
        )
        assert manager.detect_system_locale() == "ru"

    def test_locales_dir_property(self) -> None:
        manager = I18nManager.get_instance()
        assert manager.locales_dir.exists()

    def test_ensure_mo_file_recompiles_when_missing(self, tmp_path) -> None:
        # Каталог с po, но без mo
        locales_dir = tmp_path / "locales"
        ru_dir = locales_dir / "ru" / "LC_MESSAGES"
        ru_dir.mkdir(parents=True)
        po_file = ru_dir / "mia.po"
        po_file.write_text(
            'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=utf-8\\n"\n\n'
            'msgid "test_str"\nmsgstr "тест_стр"\n',
            encoding="utf-8",
        )
        manager = I18nManager(locales_dir=locales_dir)
        manager._ensure_mo_file("ru")
        assert (ru_dir / "mia.mo").exists()

    def test_npgettext_and_pgettext_fallback(self) -> None:
        from core.i18n import npgettext, pgettext

        # Empty string fast paths
        assert pgettext("ctx", "") == ""
        # npgettext
        assert npgettext("ctx", "item", "items", 1) == "item"
        assert npgettext("ctx", "item", "items", 2) == "items"
