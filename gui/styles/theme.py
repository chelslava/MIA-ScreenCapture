"""Централизованные style helpers для GUI."""

from __future__ import annotations

import sys
from dataclasses import dataclass

VALID_THEME_MODES = ("system", "light", "dark")


@dataclass(frozen=True)
class ColorPalette:
    """Набор цветовых токенов для построения QSS-темы."""

    background: str
    surface: str
    border: str
    text_primary: str
    text_secondary: str
    accent: str
    accent_hover: str
    selection: str


LIGHT_PALETTE = ColorPalette(
    background="#FFFFFF",
    surface="#F3F3F3",
    border="#E0E0E0",
    text_primary="#1F1F1F",
    text_secondary="#616161",
    accent="#0078D4",
    accent_hover="#106EBE",
    selection="#CCE4F7",
)

DARK_PALETTE = ColorPalette(
    background="#1E1E1E",
    surface="#252526",
    border="#3C3C3C",
    text_primary="#CCCCCC",
    text_secondary="#9D9D9D",
    accent="#0A84FF",
    accent_hover="#3794FF",
    selection="#264F78",
)


def detect_system_theme() -> str:
    """
    Определить тему Windows из реестра.

    Returns:
        `"light"` или `"dark"`; `"light"` как безопасный fallback на
        не-Windows платформах или если ключ реестра недоступен.
    """
    if sys.platform != "win32":
        return "light"
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if value else "dark"
    except OSError:
        return "light"


def resolve_theme(mode: str) -> str:
    """
    Преобразовать режим темы из настроек в конкретную палитру.

    Args:
        mode: `"system"`, `"light"` или `"dark"`.

    Returns:
        `"light"` или `"dark"`.
    """
    if mode == "dark":
        return "dark"
    if mode == "light":
        return "light"
    if mode == "system":
        return detect_system_theme()
    return "light"


def get_palette(resolved: str) -> ColorPalette:
    """Вернуть палитру для разрешённой темы (`"light"`/`"dark"`)."""
    return DARK_PALETTE if resolved == "dark" else LIGHT_PALETTE


def build_stylesheet(palette: ColorPalette) -> str:
    """Собрать глобальный QSS из набора цветовых токенов."""
    return f"""
        QWidget, QMainWindow {{
            background-color: {palette.background};
            color: {palette.text_primary};
        }}
        QGroupBox {{
            background-color: {palette.surface};
            border: 1px solid {palette.border};
            border-radius: 6px;
            margin-top: 8px;
            padding-top: 8px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px;
            color: {palette.text_primary};
        }}
        QPushButton {{
            background-color: {palette.surface};
            border: 1px solid {palette.border};
            border-radius: 4px;
            padding: 4px 10px;
            color: {palette.text_primary};
        }}
        QPushButton:hover {{
            background-color: {palette.accent_hover};
            border-color: {palette.accent_hover};
            color: #FFFFFF;
        }}
        QPushButton:pressed {{
            background-color: {palette.accent};
            border-color: {palette.accent};
            color: #FFFFFF;
        }}
        QPushButton:disabled {{
            color: {palette.text_secondary};
            border-color: {palette.border};
        }}
        QLineEdit, QComboBox, QSpinBox {{
            background-color: {palette.background};
            border: 1px solid {palette.border};
            border-radius: 4px;
            padding: 2px 4px;
            color: {palette.text_primary};
        }}
        QLineEdit:focus, QComboBox:focus, QSpinBox:focus {{
            border: 1px solid {palette.accent};
        }}
        QListWidget {{
            background-color: {palette.surface};
            border: none;
        }}
        QListWidget::item {{
            padding: 6px;
            color: {palette.text_primary};
        }}
        QListWidget::item:hover {{
            background-color: {palette.accent_hover};
            color: #FFFFFF;
        }}
        QListWidget::item:selected {{
            background-color: {palette.selection};
            color: {palette.text_primary};
        }}
        QStatusBar {{
            background-color: {palette.surface};
            border-top: 1px solid {palette.border};
            color: {palette.text_secondary};
        }}
        QTableWidget {{
            background-color: {palette.background};
            gridline-color: {palette.border};
            color: {palette.text_primary};
        }}
        QHeaderView::section {{
            background-color: {palette.surface};
            border: 1px solid {palette.border};
            padding: 4px;
            color: {palette.text_primary};
        }}
        QScrollBar:vertical, QScrollBar:horizontal {{
            background-color: {palette.surface};
        }}
        QScrollBar::handle {{
            background-color: {palette.border};
            border-radius: 3px;
        }}
        QScrollBar::handle:hover {{
            background-color: {palette.accent};
        }}
    """


def apply_theme(app: object, mode: str) -> str:
    """
    Применить тему к приложению.

    Args:
        app: Объект с методом `setStyleSheet` (как правило `QApplication`).
        mode: `"system"`, `"light"` или `"dark"`.

    Returns:
        Фактически применённая тема (`"light"`/`"dark"`).
    """
    resolved = resolve_theme(mode)
    palette = get_palette(resolved)
    set_stylesheet = getattr(app, "setStyleSheet", None)
    if callable(set_stylesheet):
        set_stylesheet(build_stylesheet(palette))
    return resolved


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
