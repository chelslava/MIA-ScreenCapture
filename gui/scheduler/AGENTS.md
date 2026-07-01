<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-06-23 -->

# gui/scheduler/

## Purpose
UI-компоненты планировщика задач. Содержит вкладку планировщика (`SchedulerTab`) с таблицей задач и диалог создания/редактирования задачи (`TaskDialog`).

## Key Files

| Файл | Описание |
|------|----------|
| `scheduler_tab.py` | `SchedulerTab(QWidget)` — вкладка с таблицей задач, кнопками добавления/удаления/редактирования |
| `task_dialog.py` | `TaskDialog(QDialog)` — диалог создания и редактирования задачи планировщика |

## Subdirectories

Нет поддиректорий.

## For AI Agents

### Working In This Directory
- `SchedulerTab` использует `QTableWidget` для отображения задач.
- Взаимодействие с `scheduler/task_scheduler.py` — через `ApplicationFacade` (методы `get_schedule`, `create_schedule`, `delete_schedule`, `update_schedule`).
- `TaskDialog` — модальный диалог, возвращает `dict` с параметрами задачи.
- `apply_accessible_metadata` вызывается для каждого виджета диалога.

### Testing Requirements
- `tests/unit/test_scheduler_tab.py` — тесты вкладки планировщика
- Запуск: `uv run pytest tests/unit/test_scheduler_tab.py -v`

### Common Patterns
```python
class SchedulerTab(QWidget):
    task_created = pyqtSignal(dict)
    task_deleted = pyqtSignal(str)

    def _on_add_clicked(self) -> None:
        dialog = TaskDialog(parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.task_created.emit(dialog.get_task_data())
```

## Dependencies

### Internal
- `scheduler/task_scheduler.py` — `ScheduleTask`, `ScheduleType`
- `gui/accessibility.py` — `apply_accessible_metadata`
- `core/application_facade.py` — через сигналы → main_window

### External
- `PyQt6.QtWidgets`, `PyQt6.QtCore`

<!-- MANUAL: -->
