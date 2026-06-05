<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-05-07 | Updated: 2026-06-05 -->

# gui/styles/

## Purpose
Кастомная тема оформления для PyQt6 GUI. Определяет цветовую палитру, шрифты и CSS-стили для всех виджетов приложения.

## Key Files

| Файл | Описание |
|------|----------|
| `theme.py` | `Theme` dataclass с цветовой палитрой, шрифтами, стилями. Метод `apply_theme(app)` для глобальной установки. Переопределение `QPalette` для системных цветов. |

## For AI Agents

### Working In This Directory
- Все цвета определяй в `Theme` — не хардкодь в виджетах.
- `apply_theme()` использует `QApplication.setPalette()` — вызывай один раз при старте.
- Новые стили добавляй в соответствующий атрибут `Theme`, не в отдельные файлы.
- `noqa: N802` допустим для PyQt6 event overrides (`paintEvent` и др.).

### Common Patterns
```python
from gui.styles.theme import Theme

theme = Theme()
theme.apply_theme(app)
```
