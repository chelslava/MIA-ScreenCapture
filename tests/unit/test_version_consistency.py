"""
Unit-тесты консистентности версии (version.py)
===============================================

Проверяют, что `get_version()` возвращает версию, объявленную в
`pyproject.toml` (`[project].version`), когда метаданные пакета
недоступны, и что установленные метаданные имеют приоритет.
"""

import importlib.metadata
import tomllib
from pathlib import Path

import pytest

import version


def _read_pyproject_version(pyproject_path: Path) -> str:
    """Читает `[project].version` из заданного pyproject.toml."""
    with pyproject_path.open("rb") as pyproject_file:
        data = tomllib.load(pyproject_file)
    return data["project"]["version"]


class TestVersionConsistency:
    """Консистентность get_version() с источником истины."""

    def test_matches_pyproject_toml(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Без установленных метаданных версия берётся из pyproject.toml."""
        monkeypatch.setattr(
            "version.importlib.metadata.version",
            _raise_package_not_found,
        )

        expected = _read_pyproject_version(version._PYPROJECT_PATH)

        assert version.get_version() == expected

    def test_installed_metadata_takes_priority(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Установленные метаданные пакета приоритетнее pyproject.toml."""
        monkeypatch.setattr(
            "version.importlib.metadata.version", lambda _name: "9.9.9"
        )

        assert version.get_version() == "9.9.9"

    def test_reads_pyproject_when_not_installed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Fallback на pyproject.toml при PackageNotFoundError."""
        fake_pyproject = tmp_path / "pyproject.toml"
        fake_pyproject.write_text(
            '[project]\nversion = "2.0.0"\n', encoding="utf-8"
        )
        monkeypatch.setattr(
            "version.importlib.metadata.version",
            _raise_package_not_found,
        )
        monkeypatch.setattr(version, "_PYPROJECT_PATH", fake_pyproject)

        assert version.get_version() == "2.0.0"

    def test_returns_str_not_pyproject_float(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Невалидный тип версии (не str) → fallback 'unknown'."""
        fake_pyproject = tmp_path / "pyproject.toml"
        fake_pyproject.write_text(
            "[project]\nversion = 1.5\n", encoding="utf-8"
        )
        monkeypatch.setattr(
            "version.importlib.metadata.version",
            _raise_package_not_found,
        )
        monkeypatch.setattr(version, "_PYPROJECT_PATH", fake_pyproject)

        assert version.get_version() == version._FALLBACK_VERSION


def _raise_package_not_found(_name: str) -> str:
    """Заглушка: имитирует отсутствие установленного пакета."""
    raise importlib.metadata.PackageNotFoundError(_name)
