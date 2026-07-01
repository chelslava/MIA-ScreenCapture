"""Централизованные style helpers для GUI."""

from __future__ import annotations

import sys
from dataclasses import dataclass


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

BLUE_PALETTE = ColorPalette(
    background="#EAEEF6",
    surface="#DCE4F0",
    border="#A9B7C6",
    text_primary="#1A2733",
    text_secondary="#51637A",
    accent="#005AC1",
    accent_hover="#0846A3",
    selection="#BCD2EE",
)

DARK_PALETTE = ColorPalette(
    background="#1E1E1E",
    surface="#2D2D30",
    border="#3F3F46",
    text_primary="#F1F1F1",
    text_secondary="#A0A0A0",
    accent="#007ACC",
    accent_hover="#1C97EA",
    selection="#264F78",
)

DARK_CONTRAST_PALETTE = ColorPalette(
    background="#000000",
    surface="#1A1A1A",
    border="#6B6B6B",
    text_primary="#FFFFFF",
    text_secondary="#D0D0D0",
    accent="#3FB6FF",
    accent_hover="#6FCBFF",
    selection="#1F6FB2",
)

THEME_REGISTRY: dict[str, ColorPalette] = {
    "light": LIGHT_PALETTE,
    "blue": BLUE_PALETTE,
    "dark": DARK_PALETTE,
    "dark_contrast": DARK_CONTRAST_PALETTE,
}

THEME_LABELS: dict[str, str] = {
    "light": "Светлая",
    "blue": "Голубая",
    "dark": "Тёмная",
    "dark_contrast": "Тёмная (контраст)",
}

VALID_THEME_MODES = ("system", *THEME_REGISTRY.keys())


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
    Преобразовать режим темы из настроек в конкретный ключ палитры.

    Args:
        mode: `"system"` или один из ключей `THEME_REGISTRY`
            (`"light"`, `"blue"`, `"dark"`, `"dark_contrast"`).

    Returns:
        Ключ `THEME_REGISTRY` (`"system"` разрешается в `"light"`/`"dark"`
        через определение системной темы Windows).
    """
    if mode in THEME_REGISTRY:
        return mode
    if mode == "system":
        return detect_system_theme()
    return "light"


def get_palette(resolved: str) -> ColorPalette:
    """Вернуть палитру для разрешённого ключа темы из `THEME_REGISTRY`."""
    return THEME_REGISTRY.get(resolved, LIGHT_PALETTE)


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
        QCheckBox, QRadioButton {{
            color: {palette.text_primary};
            spacing: 6px;
        }}
        QCheckBox::indicator, QRadioButton::indicator {{
            width: 14px;
            height: 14px;
            border: 1px solid {palette.border};
            background-color: {palette.background};
        }}
        QCheckBox::indicator {{
            border-radius: 3px;
        }}
        QRadioButton::indicator {{
            border-radius: 8px;
        }}
        QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
            border-color: {palette.accent};
        }}
        QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
            background-color: {palette.accent};
            border-color: {palette.accent};
        }}
        QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
            border-color: {palette.border};
            background-color: {palette.surface};
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
        mode: `"system"` или один из ключей `THEME_REGISTRY`.

    Returns:
        Фактически применённый ключ темы из `THEME_REGISTRY`.
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

    # Единая шкала отступов для layout.setContentsMargins()/setSpacing().
    MARGIN = 4
    SPACING = 6

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

    @classmethod
    def apply_error_status(
        cls,
        status_label: object,
        status_bar: object,
        message: str,
        duration_ms: int = 10000,
        label_text: str = "Ошибка",
    ) -> None:
        """
        Показать неблокирующую (non-modal) ambient-ошибку приложения.

        Единая точка для всех ambient app-level ошибок, которые не должны
        блокировать UI (в отличие от валидации форм внутри уже открытого
        модального диалога — там по-прежнему уместен блокирующий
        `QMessageBox.warning`/`critical`). См. конвенцию в `gui/AGENTS.md`.

        Args:
            status_label: Виджет с методами `setText`/`setStyleSheet`.
            status_bar: Виджет с методом `showMessage`.
            message: Текст ошибки для status bar.
            duration_ms: Длительность отображения сообщения.
            label_text: Краткая подпись статус-метки (по умолчанию «Ошибка»).
        """
        status_label.setText(label_text)  # type: ignore[attr-defined]
        status_label.setStyleSheet(  # type: ignore[attr-defined]
            cls.status_style("danger")
        )
        status_bar.showMessage(message, duration_ms)  # type: ignore[attr-defined]

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
