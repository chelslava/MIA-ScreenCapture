"""
Unit-тесты для utils.py
========================
"""

from pathlib import Path

import pytest

from utils import get_app_icon_path


class TestGetAppIconPath:
    """Тесты резолва пути к .ico приложения."""

    def test_dev_mode_resolves_relative_to_repo_root(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """В dev-режиме (не frozen) путь строится от каталога repo root."""
        monkeypatch.delattr("sys.frozen", raising=False)

        path = get_app_icon_path()

        assert path == (
            Path(__file__).parent.parent.parent
            / "docs"
            / "assets"
            / "MIA-ScreenCapture.ico"
        )

    def test_frozen_mode_resolves_relative_to_meipass(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """В frozen-сборке путь строится от sys._MEIPASS."""
        monkeypatch.setattr("sys.frozen", True, raising=False)
        monkeypatch.setattr("sys._MEIPASS", str(tmp_path), raising=False)

        path = get_app_icon_path()

        assert path == tmp_path / "docs" / "assets" / "MIA-ScreenCapture.ico"

    def test_returns_path_even_if_file_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Функция не проверяет существование файла — это забота вызывающего."""
        monkeypatch.delattr("sys.frozen", raising=False)

        path = get_app_icon_path()

        assert isinstance(path, Path)
