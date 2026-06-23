"""Тесты theme helper layer для GUI."""

from gui.styles.theme import Theme


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

    def test_secondary_styles(self) -> None:
        """Вторичный текст должен использовать muted палитру."""
        assert Theme.COLORS["muted"] in Theme.secondary_text_style()
        assert Theme.COLORS["muted"] in Theme.secondary_hint_style()
