"""
Unit-тесты fallback-поведения версии (version.py)
==================================================

Проверяют, что `get_version()` корректно возвращает `_FALLBACK_VERSION`
при отсутствии метаданных пакета и недоступном/повреждённом
`pyproject.toml`.
"""

import importlib.metadata
from pathlib import Path

import pytest

import version


class TestVersionFallback:
    """Fallback на _FALLBACK_VERSION при ошибках чтения."""

    def test_unknown_when_pyproject_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Нет метаданных и нет pyproject.toml → 'unknown'."""
        monkeypatch.setattr(
            "version.importlib.metadata.version",
            _raise_package_not_found,
        )
        missing = tmp_path / "no-such-dir" / "pyproject.toml"
        monkeypatch.setattr(version, "_PYPROJECT_PATH", missing)

        assert version.get_version() == version._FALLBACK_VERSION

    def test_unknown_when_pyproject_is_toml_broken(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Повреждённый TOML → 'unknown', без исключения наружу."""
        broken = tmp_path / "pyproject.toml"
        broken.write_text("[project\nversion = ", encoding="utf-8")
        monkeypatch.setattr(
            "version.importlib.metadata.version",
            _raise_package_not_found,
        )
        monkeypatch.setattr(version, "_PYPROJECT_PATH", broken)

        assert version.get_version() == version._FALLBACK_VERSION

    def test_unknown_when_version_key_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """В pyproject.toml нет [project].version → 'unknown'."""
        no_version = tmp_path / "pyproject.toml"
        no_version.write_text(
            '[project]\nname = "mia-screencapture"\n', encoding="utf-8"
        )
        monkeypatch.setattr(
            "version.importlib.metadata.version",
            _raise_package_not_found,
        )
        monkeypatch.setattr(version, "_PYPROJECT_PATH", no_version)

        assert version.get_version() == version._FALLBACK_VERSION

    def test_unknown_when_version_empty(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Пустая строка версии → 'unknown'."""
        empty_version = tmp_path / "pyproject.toml"
        empty_version.write_text('[project]\nversion = ""\n', encoding="utf-8")
        monkeypatch.setattr(
            "version.importlib.metadata.version",
            _raise_package_not_found,
        )
        monkeypatch.setattr(version, "_PYPROJECT_PATH", empty_version)

        assert version.get_version() == version._FALLBACK_VERSION

    def test_unknown_when_not_a_pyproject(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Файл без секции project → 'unknown' (KeyError внутри)."""
        not_pyproject = tmp_path / "pyproject.toml"
        not_pyproject.write_text(
            "[tool.ruff]\nline-length = 79\n", encoding="utf-8"
        )
        monkeypatch.setattr(
            "version.importlib.metadata.version",
            _raise_package_not_found,
        )
        monkeypatch.setattr(version, "_PYPROJECT_PATH", not_pyproject)

        assert version.get_version() == version._FALLBACK_VERSION


def _raise_package_not_found(_name: str) -> str:
    """Заглушка: имитирует отсутствие установленного пакета."""
    raise importlib.metadata.PackageNotFoundError(_name)
