"""Централизованные style helpers для GUI."""

from __future__ import annotations


class Theme:
    """Единый источник базовых style helpers для GUI."""

    COLORS = {
        "danger": "#dc2626",
        "warning": "#f59e0b",
        "success": "#16a34a",
        "info": "#2563eb",
        "muted": "#6b7280",
    }

    @classmethod
    def title_style(cls) -> str:
        """Стиль заголовков секций и вкладок."""
        return "font-size: 16px; font-weight: bold;"

    @classmethod
    def secondary_text_style(cls) -> str:
        """Стиль вторичного текста и подписи."""
        return f"color: {cls.COLORS['muted']};"

    @classmethod
    def secondary_hint_style(cls) -> str:
        """Стиль вторичного служебного текста меньшего размера."""
        return f"color: {cls.COLORS['muted']}; font-size: 11px;"

    @classmethod
    def status_style(cls, tone: str) -> str:
        """
        Стиль статусной подписи с цветовым тоном.

        Args:
            tone: Один из ключей `COLORS`.
        """
        color = cls.COLORS.get(tone, cls.COLORS["muted"])
        return f"font-weight: bold; color: {color};"

    @staticmethod
    def apply_style(widget: object, style: str) -> None:
        """
        Безопасно применить stylesheet к Qt-виджету или тестовому mock.

        Args:
            widget: Целевой виджет.
            style: Строка stylesheet.
        """
        widget._style_sheet = style  # type: ignore[attr-defined]
        setter = getattr(widget, "setStyleSheet", None)
        if callable(setter):
            setter(style)
