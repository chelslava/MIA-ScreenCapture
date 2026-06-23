<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-07 | Updated: 2026-06-24 -->

# gui/styles/

## Purpose
Кастомная тема оформления для PyQt6 GUI: программно генерируемый QSS из
реестра именованных цветовых палитр (`THEME_REGISTRY`) + статусные стили
(`Theme.COLORS`/`status_style`/...) для отдельных виджетов.

## Key Files

| Файл | Описание |
|------|----------|
| `theme.py` | `ColorPalette` (dataclass с цветовыми токенами) + `THEME_REGISTRY` (реестр тем: `light`/`blue`/`dark`/`dark_contrast`, в стиле Visual Studio) + `THEME_LABELS` (русские подписи для UI). `resolve_theme(mode)` разрешает `"system"`/ключ реестра в конкретный ключ темы; `build_stylesheet(palette)` — чистая string-builder функция; `apply_theme(app, mode)` применяет тему к `QApplication`. Отдельно `Theme` — статичные style-хелперы (`COLORS`, `status_style`, `title_style`...) для точечных стилей виджетов, не связанные с палитрой темы. |

## For AI Agents

### Working In This Directory
- Цветовые токены темы — только в `ColorPalette`/`THEME_REGISTRY`, не хардкодь в виджетах.
- Новую тему добавляй как новую запись в `THEME_REGISTRY` + `THEME_LABELS` —
  `resolve_theme`/`get_palette`/`AppearanceView` подхватывают её автоматически
  без других правок.
- `VALID_THEME_MODES` здесь и валидатор `theme` в `config.py`
  (`_VALID_THEME_MODES`) должны оставаться синхронными — `config.py`
  сознательно не импортирует этот модуль (core/config не зависит от
  GUI-слоя с PyQt6, нужен для headless API-сценариев).
- `apply_theme(app, mode)` вызывается и в `app_runtime/gui_coordinator.py`
  (до создания `MainWindow`, чтобы не было мерцания), и live при выборе в
  `gui/views/appearance_view.py`.
- Статусные цвета (`Theme.COLORS`: danger/warning/success/info/muted) не
  входят в `ColorPalette` и не меняются между темами — они читаемы на любом
  фоне намеренно (ADR-011).
- `noqa: N802` допустим для PyQt6 event overrides (`paintEvent` и др.).

### Common Patterns
```python
from gui.styles.theme import apply_theme

apply_theme(app, "blue")  # или "system"/"light"/"dark"/"dark_contrast"
```
