"""Тесты theme helper layer для GUI."""

from unittest.mock import MagicMock, patch

from gui.styles.theme import (
    BLUE_PALETTE,
    DARK_CONTRAST_PALETTE,
    DARK_PALETTE,
    LIGHT_PALETTE,
    THEME_LABELS,
    THEME_REGISTRY,
    Theme,
    apply_theme,
    build_stylesheet,
    detect_system_theme,
    get_palette,
    resolve_theme,
)


class TestThemeHelpers:
    """Проверки централизованных theme helper-ов."""

    def test_title_style(self) -> None:
        """Заголовочный стиль должен оставаться стабильным."""
        assert Theme.title_style() == "font-size: 16px; font-weight: bold;"

    def test_status_style_variants(self) -> None:
        """Статусные стили должны содержать ожидаемые цвета."""
        assert Theme.COLORS["danger"] in Theme.status_style("danger")
        assert Theme.COLORS["warning"] in Theme.status_style("warning")
        assert Theme.COLORS["success"] in Theme.status_style("success")

    def test_apply_error_status_updates_label_and_status_bar(self) -> None:
        """Единый non-modal error helper должен обновлять оба виджета."""
        status_label = MagicMock()
        status_bar = MagicMock()

        Theme.apply_error_status(status_label, status_bar, "Что-то сломалось")

        status_label.setText.assert_called_once_with("Ошибка")
        status_label.setStyleSheet.assert_called_once_with(
            Theme.status_style("danger")
        )
        status_bar.showMessage.assert_called_once_with(
            "Что-то сломалось", 10000
        )

    def test_apply_error_status_custom_duration_and_label(self) -> None:
        """Длительность и текст метки должны быть переопределяемы."""
        status_label = MagicMock()
        status_bar = MagicMock()

        Theme.apply_error_status(
            status_label,
            status_bar,
            "Предупреждение",
            duration_ms=3000,
            label_text="Внимание",
        )

        status_label.setText.assert_called_once_with("Внимание")
        status_bar.showMessage.assert_called_once_with("Предупреждение", 3000)

    def test_secondary_styles(self) -> None:
        """Вторичный текст должен использовать muted палитру."""
        assert Theme.COLORS["muted"] in Theme.secondary_text_style()
        assert Theme.COLORS["muted"] in Theme.secondary_hint_style()


class TestResolveTheme:
    """Проверки разрешения режима темы в конкретную палитру."""

    def test_resolve_theme_explicit_light(self) -> None:
        assert resolve_theme("light") == "light"

    def test_resolve_theme_explicit_dark(self) -> None:
        assert resolve_theme("dark") == "dark"

    def test_resolve_theme_explicit_blue(self) -> None:
        assert resolve_theme("blue") == "blue"

    def test_resolve_theme_explicit_dark_contrast(self) -> None:
        assert resolve_theme("dark_contrast") == "dark_contrast"

    def test_resolve_theme_system_delegates_to_detection(self) -> None:
        with patch(
            "gui.styles.theme.detect_system_theme", return_value="dark"
        ) as mocked:
            assert resolve_theme("system") == "dark"
            mocked.assert_called_once()

    def test_resolve_theme_invalid_falls_back_to_light(self) -> None:
        assert resolve_theme("not-a-real-mode") == "light"


class TestThemeRegistry:
    """Проверки реестра VS-style тем и его согласованности."""

    def test_registry_and_labels_have_matching_keys(self) -> None:
        assert set(THEME_REGISTRY.keys()) == set(THEME_LABELS.keys())

    def test_registry_contains_two_light_and_two_dark_style_themes(
        self,
    ) -> None:
        assert THEME_REGISTRY["light"] is LIGHT_PALETTE
        assert THEME_REGISTRY["blue"] is BLUE_PALETTE
        assert THEME_REGISTRY["dark"] is DARK_PALETTE
        assert THEME_REGISTRY["dark_contrast"] is DARK_CONTRAST_PALETTE


class TestDetectSystemTheme:
    """Проверки определения системной темы Windows через реестр."""

    def test_non_windows_falls_back_to_light(self) -> None:
        with patch("sys.platform", "linux"):
            assert detect_system_theme() == "light"

    def test_dark_from_registry(self) -> None:
        mock_key = MagicMock()
        mock_key.__enter__ = MagicMock(return_value=mock_key)
        mock_key.__exit__ = MagicMock(return_value=False)
        with (
            patch("sys.platform", "win32"),
            patch("winreg.OpenKey", return_value=mock_key),
            patch("winreg.QueryValueEx", return_value=(0, 4)),
        ):
            assert detect_system_theme() == "dark"

    def test_light_from_registry(self) -> None:
        mock_key = MagicMock()
        mock_key.__enter__ = MagicMock(return_value=mock_key)
        mock_key.__exit__ = MagicMock(return_value=False)
        with (
            patch("sys.platform", "win32"),
            patch("winreg.OpenKey", return_value=mock_key),
            patch("winreg.QueryValueEx", return_value=(1, 4)),
        ):
            assert detect_system_theme() == "light"

    def test_missing_key_falls_back_to_light(self) -> None:
        with (
            patch("sys.platform", "win32"),
            patch("winreg.OpenKey", side_effect=FileNotFoundError()),
        ):
            assert detect_system_theme() == "light"


class TestBuildStylesheet:
    """Проверки генерации QSS из палитры."""

    def test_light_stylesheet_contains_tokens(self) -> None:
        qss = build_stylesheet(LIGHT_PALETTE)
        assert LIGHT_PALETTE.background in qss
        assert LIGHT_PALETTE.surface in qss
        assert LIGHT_PALETTE.accent in qss

    def test_dark_stylesheet_contains_tokens(self) -> None:
        qss = build_stylesheet(DARK_PALETTE)
        assert DARK_PALETTE.background in qss
        assert DARK_PALETTE.surface in qss
        assert DARK_PALETTE.accent in qss

    def test_blue_stylesheet_contains_tokens(self) -> None:
        qss = build_stylesheet(BLUE_PALETTE)
        assert BLUE_PALETTE.background in qss
        assert BLUE_PALETTE.surface in qss
        assert BLUE_PALETTE.accent in qss

    def test_dark_contrast_stylesheet_contains_tokens(self) -> None:
        qss = build_stylesheet(DARK_CONTRAST_PALETTE)
        assert DARK_CONTRAST_PALETTE.background in qss
        assert DARK_CONTRAST_PALETTE.surface in qss
        assert DARK_CONTRAST_PALETTE.accent in qss

    def test_get_palette_dispatch(self) -> None:
        assert get_palette("dark") is DARK_PALETTE
        assert get_palette("light") is LIGHT_PALETTE
        assert get_palette("blue") is BLUE_PALETTE
        assert get_palette("dark_contrast") is DARK_CONTRAST_PALETTE
        assert get_palette("system") is LIGHT_PALETTE


class TestApplyTheme:
    """Проверки применения темы к объекту приложения."""

    def test_apply_theme_calls_set_stylesheet(self) -> None:
        app = MagicMock()
        resolved = apply_theme(app, "dark")
        assert resolved == "dark"
        app.setStyleSheet.assert_called_once()
        applied_qss = app.setStyleSheet.call_args[0][0]
        assert DARK_PALETTE.background in applied_qss

    def test_apply_theme_ignores_object_without_set_stylesheet(self) -> None:
        resolved = apply_theme(object(), "light")
        assert resolved == "light"

    def test_apply_theme_calls_set_stylesheet_for_blue(self) -> None:
        app = MagicMock()
        resolved = apply_theme(app, "blue")
        assert resolved == "blue"
        applied_qss = app.setStyleSheet.call_args[0][0]
        assert BLUE_PALETTE.background in applied_qss

    def test_apply_theme_calls_set_stylesheet_for_dark_contrast(self) -> None:
        app = MagicMock()
        resolved = apply_theme(app, "dark_contrast")
        assert resolved == "dark_contrast"
        applied_qss = app.setStyleSheet.call_args[0][0]
        assert DARK_CONTRAST_PALETTE.background in applied_qss
