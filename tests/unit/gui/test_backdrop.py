"""Unit-тесты материала Windows 11 (Mica) (#157)."""

from __future__ import annotations

from unittest.mock import MagicMock

import gui.styles.backdrop as backdrop
from gui.styles.backdrop import (
    apply_mica_backdrop,
    backdrop_supported,
    is_windows_11,
)


class TestIsWindows11:
    """Определение Windows 11 по сборке."""

    def test_non_windows_is_false(self, monkeypatch) -> None:
        monkeypatch.setattr(backdrop.platform, "system", lambda: "Linux")
        monkeypatch.setattr(backdrop.platform, "version", lambda: "5.15.0")
        assert is_windows_11() is False

    def test_windows_10_build_19045_is_false(self, monkeypatch) -> None:
        monkeypatch.setattr(backdrop.platform, "system", lambda: "Windows")
        monkeypatch.setattr(backdrop.platform, "version", lambda: "10.0.19045")
        assert is_windows_11() is False

    def test_windows_11_build_22000_is_true(self, monkeypatch) -> None:
        monkeypatch.setattr(backdrop.platform, "system", lambda: "Windows")
        monkeypatch.setattr(backdrop.platform, "version", lambda: "10.0.22000")
        assert is_windows_11() is True

    def test_windows_11_build_22631_is_true(self, monkeypatch) -> None:
        monkeypatch.setattr(backdrop.platform, "system", lambda: "Windows")
        monkeypatch.setattr(backdrop.platform, "version", lambda: "10.0.22631")
        assert is_windows_11() is True

    def test_unparsable_version_is_false(self, monkeypatch) -> None:
        monkeypatch.setattr(backdrop.platform, "system", lambda: "Windows")
        monkeypatch.setattr(backdrop.platform, "version", lambda: "weird")
        assert is_windows_11() is False


class TestBackdropSupported:
    """Совместимость материала с окружением."""

    def test_follows_windows_11_check(self, monkeypatch) -> None:
        monkeypatch.setattr(backdrop, "is_windows_11", lambda: True)
        assert backdrop_supported() is True
        monkeypatch.setattr(backdrop, "is_windows_11", lambda: False)
        assert backdrop_supported() is False


class TestApplyMicaBackdrop:
    """Применение DWM-материала (best-effort)."""

    def test_rejected_below_windows_11(self, monkeypatch) -> None:
        monkeypatch.setattr(backdrop, "is_windows_11", lambda: False)
        assert apply_mica_backdrop(12345) is False

    def test_success_on_hresult_zero(self, monkeypatch) -> None:
        """Патчим атрибут ctypes модуля backdrop (без inner-import)."""
        monkeypatch.setattr(backdrop, "is_windows_11", lambda: True)
        dwmapi = MagicMock()
        dwmapi.DwmSetWindowAttribute.return_value = 0
        fake_ctypes = MagicMock()
        fake_ctypes.windll.dwmapi = dwmapi
        monkeypatch.setattr(backdrop, "ctypes", fake_ctypes)

        assert apply_mica_backdrop(12345) is True
        args = dwmapi.DwmSetWindowAttribute.call_args.args
        assert args[0] == 12345
        assert args[1] == 38  # DWMWA_SYSTEMBACKDROP_TYPE

    def test_false_on_hresult_error(self, monkeypatch) -> None:
        monkeypatch.setattr(backdrop, "is_windows_11", lambda: True)
        dwmapi = MagicMock()
        dwmapi.DwmSetWindowAttribute.return_value = -1
        fake_ctypes = MagicMock()
        fake_ctypes.windll.dwmapi = dwmapi
        monkeypatch.setattr(backdrop, "ctypes", fake_ctypes)

        assert apply_mica_backdrop(12345) is False

    def test_false_when_dwmapi_missing(self, monkeypatch) -> None:
        """Windows без dwmapi — тихая деградация (Win10 LTSC и т.п.)."""
        monkeypatch.setattr(backdrop, "is_windows_11", lambda: True)

        class _NoDwmapiLoader:
            """windll-заглушка без dwmapi (dunder на типе — не MagicMock)."""

            def __getattr__(self, name: str) -> None:
                raise AttributeError(name)

        fake_ctypes = MagicMock()
        fake_ctypes.windll = _NoDwmapiLoader()
        monkeypatch.setattr(backdrop, "ctypes", fake_ctypes)

        assert apply_mica_backdrop(12345) is False


class TestTranslucentStylesheet:
    """Полупрозрачный фон QSS под материал (#157)."""

    def test_default_stylesheet_opaque(self) -> None:
        from gui.styles.theme import LIGHT_PALETTE, build_stylesheet

        qss = build_stylesheet(LIGHT_PALETTE)
        assert LIGHT_PALETTE.background in qss

    def test_translucent_stylesheet_uses_rgba(self) -> None:
        from gui.styles.theme import LIGHT_PALETTE, build_stylesheet

        qss = build_stylesheet(LIGHT_PALETTE, translucent_background=True)
        hex_bg = LIGHT_PALETTE.background.lstrip("#")
        r, g, b = hex_bg[:2], hex_bg[2:4], hex_bg[4:6]
        assert f"rgba({int(r, 16)}, {int(g, 16)}, {int(b, 16)}, 205)" in qss

    def test_set_backdrop_active_switches_next_apply(self) -> None:
        """Флаг действует на следующий apply_theme (и сбрасывается)."""
        from gui.styles import theme as theme_module

        app = MagicMock()
        theme_module.set_backdrop_active(True)
        try:
            theme_module.apply_theme(app, "light")
            qss = app.setStyleSheet.call_args.args[0]
            assert "rgba(" in qss.split("background-color:", 1)[1][:40]

            theme_module.set_backdrop_active(False)
            theme_module.apply_theme(app, "light")
            qss = app.setStyleSheet.call_args.args[0]
            assert "rgba(" not in qss.split("background-color:", 1)[1][:40]
        finally:
            theme_module.set_backdrop_active(False)
