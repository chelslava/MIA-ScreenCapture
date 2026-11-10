"""Единый bump версии проекта.

Обновляет версию сразу во всех местах, где она захардкожена, и по
желанию создаёт git-тег. Использование:

    uv run python scripts/bump_version.py 1.8.0 [--dry-run] [--tag]

Порядок релиза:
    1. Перенести секцию [Unreleased] в `## [1.8.0] - YYYY-MM-DD` в
       CHANGELOG.md (скрипт проверяет наличие записи и предупреждает).
    2. Запустить скрипт — он обновит pyproject.toml и заголовки README.
    3. Пуш тега `v1.8.0` запускает релизный workflow (.github/workflows/
       release.yml), который сам сверяет тег с версией pyproject.toml.
"""

import argparse
import io
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_PYPROJECT = PROJECT_ROOT / "pyproject.toml"
_CHANGELOG = PROJECT_ROOT / "CHANGELOG.md"
_READMES = (PROJECT_ROOT / "README.md", PROJECT_ROOT / "README.ru.md")

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_VERSION_LINE_RE = re.compile(r'^version = "\d+\.\d+\.\d+"$')
_TITLE_RE = re.compile(r"^(# MIA-ScreenCapture v)\d+\.\d+\.\d+$")


def _validate_version(new_version: str) -> None:
    """Проверяет формат версии X.Y.Z и отличает её от текущей.

    Args:
        new_version: Новая версия в формате SemVer.

    Raises:
        SystemExit: Некорректный формат версии.
    """
    if not _SEMVER_RE.match(new_version):
        raise SystemExit(
            f"Ошибка: версия '{new_version}' не соответствует "
            f"формату X.Y.Z (например, 1.8.0)."
        )


def _read_current_version() -> str:
    """Читает текущую версию из [project] pyproject.toml.

    Returns:
        Строка текущей версии.

    Raises:
        SystemExit: Строка версии не найдена или дублируется.
    """
    lines = _PYPROJECT.read_text(encoding="utf-8").splitlines()
    matches = [ln for ln in lines if _VERSION_LINE_RE.match(ln)]
    if len(matches) != 1:
        raise SystemExit(
            f"Ошибка: ожидалась одна строка 'version = \"X.Y.Z\"' в "
            f"pyproject.toml, найдено {len(matches)}."
        )
    return matches[0].split('"')[1]


def _update_pyproject(new_version: str) -> None:
    """Заменяет строку version в секции [project] pyproject.toml."""
    text = _PYPROJECT.read_text(encoding="utf-8")
    updated, count = _VERSION_LINE_RE.subn(
        f'version = "{new_version}"', text, count=1
    )
    if count != 1:
        raise SystemExit(
            "Ошибка: не удалось заменить версию в pyproject.toml."
        )
    _PYPROJECT.write_text(updated, encoding="utf-8")


def _update_readmes(new_version: str) -> None:
    """Обновляет заголовки '# MIA-ScreenCapture vX.Y.Z' в README."""
    for readme in _READMES:
        text = readme.read_text(encoding="utf-8")
        updated, count = _TITLE_RE.subn(rf"\g<1>{new_version}", text, count=1)
        if count != 1:
            print(
                f"Предупреждение: заголовок версии не найден в "
                f"{readme.name} — пропущен."
            )
            continue
        readme.write_text(updated, encoding="utf-8")


def _check_changelog(new_version: str) -> None:
    """Предупреждает, если в CHANGELOG нет записи для новой версии."""
    text = _CHANGELOG.read_text(encoding="utf-8")
    if f"## [{new_version}]" not in text:
        print(
            f"Предупреждение: в CHANGELOG.md нет секции "
            f"'## [{new_version}]'. Перенесите содержимое секции "
            f"[Unreleased] в запись релиза перед пушем тега."
        )


def _create_tag(new_version: str) -> None:
    """Создаёт аннотированный git-тег vX.Y.Z на текущем HEAD.

    Raises:
        SystemExit: Тег уже существует или git вернул ошибку.
    """
    tag = f"v{new_version}"
    result = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        raise SystemExit(f"Ошибка: тег {tag} уже существует.")
    subprocess.run(
        ["git", "tag", "-a", tag, "-m", f"Release {new_version}"],
        check=True,
    )
    print(f"Создан тег {tag}. Публикация: git push origin {tag}")


def main() -> None:
    """Точка входа: парсит аргументы и выполняет bump версии."""
    # Консоль Windows по умолчанию в cp1251/cp866 — кириллица в
    # сообщениях ломается без явного UTF-8
    if isinstance(sys.stdout, io.TextIOWrapper):
        encoding = sys.stdout.encoding or ""
        if encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="Обновить версию проекта в pyproject.toml и README."
    )
    parser.add_argument("new_version", help="Новая версия в формате X.Y.Z")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать изменения, не записывать файлы",
    )
    parser.add_argument(
        "--tag",
        action="store_true",
        help="Создать аннотированный git-тег v<версия> после обновления",
    )
    args = parser.parse_args()

    _validate_version(args.new_version)
    current = _read_current_version()
    print(f"Текущая версия: {current} -> новая: {args.new_version}")

    if args.new_version == current:
        raise SystemExit("Ошибка: новая версия совпадает с текущей.")

    if not args.dry_run:
        _update_pyproject(args.new_version)
        _update_readmes(args.new_version)
        print("Обновлены: pyproject.toml, README.md, README.ru.md")
        _check_changelog(args.new_version)
    else:
        print("Режим --dry-run: файлы не изменены.")
        _check_changelog(args.new_version)

    if args.tag and not args.dry_run:
        _create_tag(args.new_version)


if __name__ == "__main__":
    main()
