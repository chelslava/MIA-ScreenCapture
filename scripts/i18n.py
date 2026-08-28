"""
Скрипт управления каталогами локализации (i18n CLI)
===================================================

Предоставляет команды для извлечения строк, инициализации новых языков,
обновления, компиляции и проверки каталогов переводов.

Использование:
    python scripts/i18n.py extract
    python scripts/i18n.py init de
    python scripts/i18n.py update
    python scripts/i18n.py compile
    python scripts/i18n.py check
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import babel.messages.frontend as babel_cli
from babel.messages.pofile import read_po

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCALES_DIR = PROJECT_ROOT / "locales"
POT_FILE = LOCALES_DIR / "mia.pot"
BABEL_CFG = PROJECT_ROOT / "babel.cfg"
DOMAIN = "mia"


def _ensure_babel_cfg() -> Path:
    """Создает файл конфигурации babel.cfg, если он отсутствует."""
    if not BABEL_CFG.exists():
        BABEL_CFG.write_text(
            "[python: **.py]\n"
            "encoding = utf-8\n"
            "keywords = _ gettext ngettext:1,2 pgettext:1c,2 npgettext:1c,2,3 lazy_gettext lazy_pgettext:1c,2\n",
            encoding="utf-8",
        )
    return BABEL_CFG


def extract_messages() -> int:
    """Извлекает переводимые строки из исходного кода в шаблон POT."""
    LOCALES_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_babel_cfg()

    cmd = [
        "pybabel",
        "extract",
        "-F",
        str(BABEL_CFG),
        "-o",
        str(POT_FILE),
        "--project",
        "MIA-ScreenCapture",
        "--version",
        "1.5.0",
        "--msgid-bugs-address",
        "support@mia-screencapture.local",
        "--copyright-holder",
        "MIA Development Team",
        str(PROJECT_ROOT),
    ]

    try:
        babel_cli.CommandLineInterface().run(cmd)
        print(f"[OK] Шаблон сообщений успешно создан: {POT_FILE}")
        return 0
    except Exception as e:
        print(f"[ERROR] Ошибка извлечения сообщений: {e}", file=sys.stderr)
        return 1


def init_catalog(locale_code: str) -> int:
    """Инициализирует каталог перевода для нового языка."""
    if not POT_FILE.exists():
        extract_res = extract_messages()
        if extract_res != 0:
            return extract_res

    po_file = LOCALES_DIR / locale_code / "LC_MESSAGES" / f"{DOMAIN}.po"
    if po_file.exists():
        print(
            f"[WARN] Каталог для языка '{locale_code}' уже существует: {po_file}"
        )
        return 0

    cmd = [
        "pybabel",
        "init",
        "-i",
        str(POT_FILE),
        "-d",
        str(LOCALES_DIR),
        "-l",
        locale_code,
        "-D",
        DOMAIN,
    ]

    try:
        babel_cli.CommandLineInterface().run(cmd)
        print(f"[OK] Инициализирован новый каталог перевода: {po_file}")
        return 0
    except Exception as e:
        print(
            f"[ERROR] Ошибка инициализации каталога '{locale_code}': {e}",
            file=sys.stderr,
        )
        return 1


def update_catalogs() -> int:
    """Обновляет существующие каталоги .po из шаблона .pot."""
    if not POT_FILE.exists():
        extract_res = extract_messages()
        if extract_res != 0:
            return extract_res

    cmd = [
        "pybabel",
        "update",
        "-i",
        str(POT_FILE),
        "-d",
        str(LOCALES_DIR),
        "-D",
        DOMAIN,
    ]

    try:
        babel_cli.CommandLineInterface().run(cmd)
        print(f"[OK] Каталоги перевода обновлены из шаблона {POT_FILE}")
        return 0
    except Exception as e:
        print(f"[ERROR] Ошибка обновления каталогов: {e}", file=sys.stderr)
        return 1


def compile_catalogs() -> int:
    """Компилирует все файлы .po в бинарные .mo."""
    cmd = [
        "pybabel",
        "compile",
        "-d",
        str(LOCALES_DIR),
        "-D",
        DOMAIN,
    ]

    try:
        babel_cli.CommandLineInterface().run(cmd)
        print(f"[OK] Каталоги сообщений скомпилированы в {LOCALES_DIR}")
        return 0
    except Exception as e:
        print(f"[ERROR] Ошибка компиляции каталогов: {e}", file=sys.stderr)
        return 1


def _extract_placeholders(text: str) -> set[str]:
    """Извлекает имена плейсхолдеров {name} из строки."""
    return set(re.findall(r"\{([a-zA-Z0-9_]+)\}", text))


def check_catalogs(strict: bool = False) -> int:
    """
    Проверяет корректность каталогов переводов:
    - отсутствие синтаксических ошибок
    - соответствие именованных плейсхолдеров
    - наличие непереведенных или fuzzy строк (в strict режиме)
    """
    if not LOCALES_DIR.exists():
        print(
            f"[ERROR] Каталог локалей не найден: {LOCALES_DIR}",
            file=sys.stderr,
        )
        return 1

    po_files = list(LOCALES_DIR.glob(f"*/LC_MESSAGES/{DOMAIN}.po"))
    if not po_files:
        print(
            f"[ERROR] Файлы переводов {DOMAIN}.po не найдены в {LOCALES_DIR}",
            file=sys.stderr,
        )
        return 1

    errors_count = 0
    warnings_count = 0

    for po_path in po_files:
        locale_name = po_path.parent.parent.name
        try:
            with open(po_path, encoding="utf-8") as f:
                catalog = read_po(f)
        except Exception as e:
            print(
                f"[ERROR] [{locale_name}] Не удалось прочитать {po_path}: {e}"
            )
            errors_count += 1
            continue

        total_messages = 0
        untranslated = 0
        fuzzy_count = 0
        placeholder_mismatches = 0

        for message in catalog:
            if not message.id:
                continue  # Header

            total_messages += 1

            if message.fuzzy:
                fuzzy_count += 1
                if strict:
                    errors_count += 1
                    print(
                        f"  [STRICT ERROR] [{locale_name}] Fuzzy перевод: {message.id}"
                    )
                else:
                    warnings_count += 1

            if not message.string:
                untranslated += 1
                if strict:
                    errors_count += 1
                    print(
                        f"  [STRICT ERROR] [{locale_name}] Не переведено: {message.id}"
                    )
                else:
                    warnings_count += 1
                continue

            # Проверка плейсхолдеров
            if isinstance(message.id, str) and isinstance(message.string, str):
                orig_placeholders = _extract_placeholders(message.id)
                trans_placeholders = _extract_placeholders(message.string)
                if orig_placeholders != trans_placeholders:
                    print(
                        f"  [ERROR] [{locale_name}] Несовпадение плейсхолдеров!\n"
                        f"    ID:    {message.id} -> {orig_placeholders}\n"
                        f"    TRANS: {message.string} -> {trans_placeholders}"
                    )
                    placeholder_mismatches += 1
                    errors_count += 1

        print(
            f"[{locale_name}] Проверено сообщений: {total_messages} | "
            f"Не переведено: {untranslated} | Fuzzy: {fuzzy_count} | Ошибок плейсхолдеров: {placeholder_mismatches}"
        )

    # Проверка компиляции
    compile_code = compile_catalogs()
    if compile_code != 0:
        errors_count += 1

    if errors_count > 0:
        print(
            f"\n[FAILED] Проверка завершилась с ошибками ({errors_count} ошибок, {warnings_count} предупреждений)"
        )
        return 1

    print(
        f"\n[PASSED] Все каталоги переводов валидны! ({warnings_count} предупреждений)"
    )
    return 0


def main() -> int:
    """Точка входа CLI."""
    parser = argparse.ArgumentParser(
        description="Инструмент управления переводами MIA-ScreenCapture"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("extract", help="Извлечь строки в .pot")

    init_parser = subparsers.add_parser("init", help="Инициализировать язык")
    init_parser.add_argument("locale", help="Код языка (например, ru, en, de)")

    subparsers.add_parser("update", help="Обновить каталоги .po из .pot")
    subparsers.add_parser("compile", help="Скомпилировать .po в .mo")

    check_parser = subparsers.add_parser(
        "check", help="Проверить валидность каталогов"
    )
    check_parser.add_argument(
        "--strict",
        action="store_true",
        help="Строгий режим (ошибка при наличии fuzzy или непереведенных строк)",
    )

    args = parser.parse_args()

    if args.command == "extract":
        return extract_messages()
    elif args.command == "init":
        return init_catalog(args.locale)
    elif args.command == "update":
        return update_catalogs()
    elif args.command == "compile":
        return compile_catalogs()
    elif args.command == "check":
        return check_catalogs(strict=args.strict)

    return 0


if __name__ == "__main__":
    sys.exit(main())
