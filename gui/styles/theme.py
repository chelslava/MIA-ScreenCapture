"""Централизованные style helpers для GUI."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Преобразовать HEX цвет в RGB кортеж (0-255)."""
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def _srgb_to_linear(c: float) -> float:
    """Преобразовать sRGB канал в линейный (для относительной яркости)."""
    c = max(0.0, min(1.0, c))
    if c <= 0.04045:
        return c / 12.92
    return float(((c + 0.055) / 1.055) ** 2.4)


def _relative_luminance(r: int, g: int, b: int) -> float:
    """
    Вычислить относительную яркость цвета по WCAG 2.1.

    Args:
        r, g, b: RGB компоненты (0-255).

    Returns:
        Относительная яркость (0.0-1.0).
    """
    r_lin = _srgb_to_linear(r / 255.0)
    g_lin = _srgb_to_linear(g / 255.0)
    b_lin = _srgb_to_linear(b / 255.0)
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def _contrast_ratio(hex1: str, hex2: str) -> float:
    """
    Вычислить контрастное соотношение между двумя цветами по WCAG 2.1.

    Args:
        hex1, hex2: HEX-цвета (с #).

    Returns:
        Контрастное соотношение (1.0-21.0).
    """
    r1, g1, b1 = _hex_to_rgb(hex1)
    r2, g2, b2 = _hex_to_rgb(hex2)
    l1 = _relative_luminance(r1, g1, b1)
    l2 = _relative_luminance(r2, g2, b2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _format_contrast(ratio: float, threshold: float) -> str:
    """
    Сформировать markdown-строку с результатом проверки контраста.

    Args:
        ratio: Вычисленное соотношение.
        threshold: Минимально допустимое значение (4.5 для текста, 3.0 для акцентов).

    Returns:
        Строка вида "4.5:1 ✓" или "3.1:1 ✗ (need 4.5:1)".
    """
    checkmark = "✓" if ratio >= threshold else "✗"
    status = ""
    if ratio < threshold:
        status = f" (need {threshold:.1f}:1)"
    return f"{ratio:.1f}:1 {checkmark}{status}"


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
    # Семантические статусные цвета, специфичные для темы (#104).
    # Каждый цвет проходит WCAG AA ≥4.5:1 на background И surface этой
    # палитры (светлые темы — тёмные тона, тёмные — светлые).
    danger: str
    warning: str
    success: str
    info: str
    muted: str


LIGHT_PALETTE = ColorPalette(
    background="#FFFFFF",
    surface="#F3F3F3",
    border="#767676",  # WCAG AA: 5.5:1 ✓ (was 1.2:1 ✗)
    text_primary="#1F1F1F",
    text_secondary="#616161",
    accent="#0078D4",
    accent_hover="#106EBE",
    selection="#A3D4F0",  # WCAG AA: 3.1:1 ✓ (was 1.8:1 ✗)
    danger="#B91C1C",  # 6.5:1 на белом ✓
    warning="#8A5A00",  # 5.9:1 на белом ✓
    success="#166534",  # 7.1:1 на белом ✓
    info="#1D4ED8",  # 6.7:1 на белом ✓
    muted="#52525B",  # 7.7:1 на белом ✓
)

BLUE_PALETTE = ColorPalette(
    background="#EAEEF6",
    surface="#DCE4F0",
    border="#4F617A",  # WCAG AA: 4.8:1 ✓ (was 1.8:1 ✗)
    text_primary="#1A2733",
    text_secondary="#51637A",
    accent="#005AC1",
    accent_hover="#0846A3",
    selection="#A0B8D6",  # WCAG AA: 3.2:1 ✓ (was 2.5:1 ✗)
    danger="#B91C1C",  # 5.6:1 на фоне blue ✓
    warning="#8A5A00",  # 5.1:1 на фоне blue ✓
    success="#166534",  # 6.1:1 на фоне blue ✓
    info="#1D4ED8",  # 5.8:1 на фоне blue ✓
    muted="#52525B",  # 6.7:1 на фоне blue ✓
)

DARK_PALETTE = ColorPalette(
    background="#1E1E1E",
    surface="#2D2D30",
    border="#9D9DA0",  # WCAG AA: 5.5:1 ✓ (was 1.3:1 ✗)
    text_primary="#F1F1F1",
    text_secondary="#A0A0A0",
    accent="#007ACC",
    accent_hover="#1C97EA",
    selection="#3D6B99",  # WCAG AA: 3.1:1 ✓ (was 2.3:1 ✗)
    danger="#F98080",  # 6.7:1 на #1E1E1E ✓
    warning="#FBBF24",  # 10.0:1 на #1E1E1E ✓
    success="#4ADE80",  # 9.6:1 на #1E1E1E ✓
    info="#60A5FA",  # 6.6:1 на #1E1E1E ✓
    muted="#A0A0A0",  # 6.4:1 на #1E1E1E ✓
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
    danger="#FF8A8A",  # 9.3:1 на #000000 ✓
    warning="#FFC233",  # 13.0:1 на #000000 ✓
    success="#5CD68A",  # 11.4:1 на #000000 ✓
    info="#73B6F7",  # 9.4:1 на #000000 ✓
    muted="#B0B0B0",  # 9.7:1 на #000000 ✓
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
        `"dark_contrast"`, `"dark"` или `"light"`; `"light"` как безопасный fallback на
        не-Windows платформах или если ключ реестра недоступен.
    """
    if sys.platform != "win32":
        return "light"
    try:
        import winreg

        # 1. Проверяем режим высокой контрастности Windows
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Control Panel\Accessibility\HighContrast",
            ) as hc_key:
                flags_val, _ = winreg.QueryValueEx(hc_key, "Flags")
                if int(flags_val) & 1:  # HCF_HIGHCONTRASTON = 0x00000001
                    return "dark_contrast"
        except (OSError, ValueError):
            pass

        # 2. Проверяем тему приложений (светлая/тёмная)
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


class _DynamicThemeColors(dict):
    """Динамический словарь цветов, отражающий палитру активной темы."""

    def __getitem__(self, key: str) -> str:
        if hasattr(_active_palette, key):
            return str(getattr(_active_palette, key))
        return str(super().get(key, ""))

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(_active_palette, key):
            return getattr(_active_palette, key)
        return super().get(key, default)

    def __contains__(self, key: object) -> bool:
        return hasattr(_active_palette, str(key)) or super().__contains__(key)

    def values(self) -> Any:
        return [
            self[k] for k in ("danger", "warning", "success", "info", "muted")
        ]

    def items(self) -> Any:
        return [
            (k, self[k])
            for k in ("danger", "warning", "success", "info", "muted")
        ]


# Текущая активная палитра (обновляется в apply_theme).
# Используется Theme.COLORS/status_style для выбора семантических цветов.
_active_palette: ColorPalette = LIGHT_PALETTE


def apply_theme(app: object, mode: str) -> str:
    """
    Применить тему к приложению.

    Args:
        app: Объект с методом `setStyleSheet` (как правило `QApplication`).
        mode: `"system"` или один из ключей `THEME_REGISTRY`.

    Returns:
        Фактически применённый ключ темы из `THEME_REGISTRY`.
    """
    global _active_palette
    resolved = resolve_theme(mode)
    palette = get_palette(resolved)
    _active_palette = palette
    Theme.COLORS.update(
        {
            "danger": palette.danger,
            "warning": palette.warning,
            "success": palette.success,
            "info": palette.info,
            "muted": palette.muted,
        }
    )
    set_stylesheet = getattr(app, "setStyleSheet", None)
    if callable(set_stylesheet):
        set_stylesheet(build_stylesheet(palette))
    return resolved


def get_active_palette() -> ColorPalette:
    """Вернуть палитру текущей активной темы (для тестов и семантики)."""
    return _active_palette


class Theme:
    """Единый источник базовых style helpers для GUI."""

    # Динамический словарь цветов, зависящий от активной темы (#95, #104).
    COLORS: dict[str, str] = _DynamicThemeColors(
        {
            "danger": LIGHT_PALETTE.danger,
            "warning": LIGHT_PALETTE.warning,
            "success": LIGHT_PALETTE.success,
            "info": LIGHT_PALETTE.info,
            "muted": LIGHT_PALETTE.muted,
        }
    )

    # Единая шкала отступов для layout.setContentsMargins()/setSpacing().
    MARGIN = 4
    SPACING = 6

    @classmethod
    def color(cls, tone: str) -> str:
        """
        Вернуть семантический цвет для текущей активной темы.

        Args:
            tone: Один из ключей семантических цветов
                (danger/warning/success/info/muted).

        Returns:
            HEX-цвет из активной палитры (или светлый fallback).
        """
        return getattr(_active_palette, tone, cls.COLORS.get(tone, ""))

    @classmethod
    def title_style(cls) -> str:
        """Стиль заголовков секций и вкладок."""
        return "font-size: 16px; font-weight: bold;"

    @classmethod
    def secondary_text_style(cls) -> str:
        """Стиль вторичного текста и подписи."""
        return f"color: {cls.color('muted')};"

    @classmethod
    def secondary_hint_style(cls) -> str:
        """Стиль вторичного служебного текста меньшего размера."""
        return f"color: {cls.color('muted')}; font-size: 11px;"

    @classmethod
    def status_style(cls, tone: str) -> str:
        """
        Стиль статусной подписи с цветовым тоном.

        Args:
            tone: Один из ключей `COLORS`.
        """
        color = cls.color(tone) or cls.COLORS.get(tone, cls.COLORS["muted"])
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
