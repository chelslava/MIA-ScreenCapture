<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-06-23 -->

# gui/

## Purpose
PyQt6 GUI-слой приложения. Реализует MVC-паттерн: модели в `models/`, представления в `views/`, контроллеры в `controllers/`. Главное окно в `main_window.py`. Содержит также системный трей, горячие клавиши, уведомления, специальные возможности (accessibility) и UI планировщика.

## Key Files

| Файл | Описание |
|------|----------|
| `main_window.py` | `MainWindow(QMainWindow)` — главное окно со всеми вкладками |
| `tray_icon.py` | `TrayIcon` — иконка в системном трее с контекстным меню |
| `hotkeys.py` | `HotkeyManager` — глобальные горячие клавиши через keyboard/pynput |
| `desktop_actions.py` | `DesktopActions` — действия рабочего стола (уведомления, открытие файлов) |
| `accessibility.py` | Accessibility атрибуты и ARIA-роли для виджетов |
| `notifications.py` | `NotificationManager` — системные уведомления через plyer |

## Subdirectories

| Директория | Назначение |
|-----------|---------|
| `views/` | PyQt6 виджеты-представления (вкладки главного окна) (см. `views/AGENTS.md`) |
| `controllers/` | Контроллеры MVC — связывают представления с доменной логикой (см. `controllers/AGENTS.md`) |
| `models/` | Модели данных GUI — состояние, кодеки, WebSocket (см. `models/AGENTS.md`) |
| `backends/` | `RecordingBackend` — реализация протокола записи для GUI (см. `backends/AGENTS.md`) |
| `styles/` | `theme.py` — цветовые темы и стили PyQt6 (см. `styles/AGENTS.md`) |
| `scheduler/` | UI планировщика: `scheduler_tab.py`, `task_dialog.py` (см. `scheduler/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Все GUI-операции должны выполняться в главном потоке Qt. Используй `QMetaObject.invokeMethod` или сигналы для вызова из фона.
- Сигналы объявляй на уровне класса как `pyqtSignal(...)`.
- Не вызывай `ApplicationFacade` напрямую из views — только через controllers.
- `accessibility.py` добавляет `setAccessibleName`/`setAccessibleDescription` к виджетам.
- При изменении темы — только в `styles/theme.py`.
- Две конвенции для ошибок/предупреждений (см. UX-аудит, [[development-log]]
  в базе знаний проекта): блокирующий `QMessageBox.warning`/`critical` —
  только для валидации форм внутри уже открытого модального диалога
  (пример: `scheduler/task_dialog.py`); неблокирующий
  `Theme.apply_error_status(status_label, status_bar, message)` — для всех
  ambient app-level ошибок (пример: `main_window._show_non_modal_error`).
  `QMessageBox.question` для подтверждения деструктивных действий
  (выход/удаление) — отдельная категория, не относится к этим двум. Новый
  третий паттерн отображения ошибок не вводить без явного решения.

### Testing Requirements
- `tests/unit/test_main_window.py` — тесты главного окна
- `tests/unit/test_tray_icon.py` — тесты трея
- `tests/unit/test_hotkeys.py` — тесты горячих клавиш
- `tests/unit/test_notifications.py` — тесты уведомлений
- `tests/unit/test_desktop_actions.py` — тесты desktop actions
- `tests/unit/test_view_accessibility.py` — тесты доступности
- PyQt6 мокируется через `conftest.py` для headless тестирования

### Common Patterns
```python
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout

class MyView(QWidget):
    some_action = pyqtSignal(str)  # сигнал на уровне класса

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        # ...
```

## Dependencies

### Internal
- `core/application_facade.py` — через controllers
- `core/event_bus.py` — подписка на события записи
- `app_runtime/` — координаторы runtime

### External
- `PyQt6` — виджеты, сигналы, главный цикл
- `plyer` — системные уведомления
- `keyboard` / `pynput` — глобальные горячие клавиши

<!-- MANUAL: -->
