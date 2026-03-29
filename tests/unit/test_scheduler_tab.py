"""Поведенческие тесты вкладки планировщика."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from gui import scheduler_tab
from scheduler.task_scheduler import (
    RecordingParams,
    ScheduleTask,
    ScheduleType,
)


class _Emitter:
    """Простой collector для emitted сигналов."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def emit(self, *args: Any) -> None:
        self.calls.append(args)


@dataclass
class _FakeButton:
    """Минимальная кнопка с поддержкой enabled state."""

    enabled: bool = False

    def setEnabled(self, value: bool) -> None:  # noqa: N802 (Qt naming)
        self.enabled = value

    def isEnabled(self) -> bool:  # noqa: N802
        return self.enabled


class _FakeTable:
    """Минимальная таблица для тестов SchedulerTab."""

    def __init__(self) -> None:
        self._current_row = -1
        self._selected_items: list[int] = []
        self.row_count = 0
        self.items: dict[tuple[int, int], Any] = {}

    def currentRow(self) -> int:  # noqa: N802
        return self._current_row

    def setCurrentRow(self, row: int) -> None:  # noqa: N802
        self._current_row = row

    def selectedItems(self) -> list[int]:  # noqa: N802
        return list(self._selected_items)

    def set_selected(self, has_selection: bool) -> None:
        self._selected_items = [1] if has_selection else []

    def setRowCount(self, count: int) -> None:  # noqa: N802
        self.row_count = count

    def setItem(self, row: int, column: int, item: Any) -> None:  # noqa: N802
        self.items[(row, column)] = item


@dataclass
class _FakeLabel:
    """Минимальная метка с поддержкой visible state."""

    visible: bool = True

    def setVisible(self, value: bool) -> None:  # noqa: N802
        self.visible = value


def _make_task(
    task_id: str = "task-1",
    schedule_type: ScheduleType = ScheduleType.DAILY,
    enabled: bool = True,
) -> ScheduleTask:
    """Создаёт задачу для тестов."""
    return ScheduleTask(
        id=task_id,
        name=f"Task {task_id}",
        schedule_type=schedule_type,
        params=RecordingParams(),
        enabled=enabled,
        time_of_day="10:00",
        days_of_week=[0, 2, 4],
        interval_hours=1,
        interval_minutes=30,
        cron_expression="0 9 * * 1-5",
    )


def _build_scheduler_tab() -> scheduler_tab.SchedulerTab:
    """Создаёт SchedulerTab без вызова Qt-инициализации."""
    tab = scheduler_tab.SchedulerTab.__new__(scheduler_tab.SchedulerTab)
    tab._tasks = []
    tab.table = _FakeTable()
    tab.edit_btn = _FakeButton()
    tab.delete_btn = _FakeButton()
    tab.toggle_btn = _FakeButton()
    tab.info_label = _FakeLabel()
    tab.task_created = _Emitter()
    tab.task_updated = _Emitter()
    tab.task_deleted = _Emitter()
    tab.task_toggled = _Emitter()
    return tab


def test_scheduler_tab_module_exists() -> None:
    """Проверка доступности модуля."""
    assert scheduler_tab is not None


def test_selection_changes_button_states() -> None:
    """Кнопки edit/delete/toggle зависят от выбора строки."""
    tab = _build_scheduler_tab()

    tab.table.set_selected(False)
    tab._on_selection_changed()
    assert tab.edit_btn.isEnabled() is False
    assert tab.delete_btn.isEnabled() is False
    assert tab.toggle_btn.isEnabled() is False

    tab.table.set_selected(True)
    tab._on_selection_changed()
    assert tab.edit_btn.isEnabled() is True
    assert tab.delete_btn.isEnabled() is True
    assert tab.toggle_btn.isEnabled() is True


def test_set_tasks_refreshes_table_and_empty_label() -> None:
    """set_tasks обновляет row count и скрывает empty label."""
    tab = _build_scheduler_tab()
    tasks = [_make_task("task-1"), _make_task("task-2")]

    tab.set_tasks(tasks)

    assert tab.table.row_count == 2
    assert tab.info_label.visible is False


def test_add_task_emits_task_created(monkeypatch) -> None:
    """Добавление задачи эмитит task_created с payload."""
    tab = _build_scheduler_tab()
    payload = {"name": "Created Task", "schedule_type": ScheduleType.ONCE}
    monkeypatch.setattr(
        scheduler_tab.QDialog,
        "DialogCode",
        SimpleNamespace(Accepted=1),
        raising=False,
    )

    class _FakeDialog:
        def __init__(self, _parent) -> None:
            return None

        def exec(self) -> int:  # noqa: A003
            return scheduler_tab.QDialog.DialogCode.Accepted

        def get_task_data(self) -> dict[str, Any]:
            return payload

    monkeypatch.setattr(scheduler_tab, "TaskDialog", _FakeDialog)
    tab._add_task()

    assert tab.task_created.calls == [(payload,)]


def test_edit_task_emits_task_updated_with_id(monkeypatch) -> None:
    """Редактирование добавляет id текущей задачи и эмитит task_updated."""
    tab = _build_scheduler_tab()
    existing = _make_task("task-77")
    tab._tasks = [existing]
    tab.table.setCurrentRow(0)
    payload = {"name": "Updated"}
    monkeypatch.setattr(
        scheduler_tab.QDialog,
        "DialogCode",
        SimpleNamespace(Accepted=1),
        raising=False,
    )

    class _FakeDialog:
        def __init__(self, _parent, task) -> None:
            assert task is existing

        def exec(self) -> int:  # noqa: A003
            return scheduler_tab.QDialog.DialogCode.Accepted

        def get_task_data(self) -> dict[str, Any]:
            return dict(payload)

    monkeypatch.setattr(scheduler_tab, "TaskDialog", _FakeDialog)
    tab._edit_task()

    assert tab.task_updated.calls == [({"name": "Updated", "id": "task-77"},)]


def test_delete_task_emits_task_deleted_on_confirm_yes(monkeypatch) -> None:
    """Удаление эмитит task_deleted после подтверждения."""
    tab = _build_scheduler_tab()
    task = _make_task("task-del")
    tab._tasks = [task]
    tab.table.setCurrentRow(0)

    monkeypatch.setattr(
        scheduler_tab.QMessageBox,
        "question",
        lambda *args, **kwargs: scheduler_tab.QMessageBox.StandardButton.Yes,
    )
    tab._delete_task()

    assert tab.task_deleted.calls == [("task-del",)]


def test_toggle_task_emits_inverse_enabled_state() -> None:
    """toggle эмитит id и инвертированный enabled флаг."""
    tab = _build_scheduler_tab()
    task = _make_task("task-toggle", enabled=True)
    tab._tasks = [task]
    tab.table.setCurrentRow(0)

    tab._toggle_task()

    assert tab.task_toggled.calls == [("task-toggle", False)]


def test_edit_task_does_nothing_for_invalid_row() -> None:
    """Редактирование с невалидным row не эмитит событие."""
    tab = _build_scheduler_tab()
    tab._tasks = [_make_task("task-1")]
    tab.table.setCurrentRow(-1)

    tab._edit_task()

    assert tab.task_updated.calls == []


def test_format_schedule_for_weekly() -> None:
    """Weekly-задача форматируется с днями и временем."""
    tab = _build_scheduler_tab()
    task = _make_task("task-weekly", schedule_type=ScheduleType.WEEKLY)
    task.time_of_day = "09:30"
    task.days_of_week = [0, 2, 4]

    text = tab._format_schedule(task)

    assert "Еженедельно" in text
    assert "Пн, Ср, Пт" in text
    assert "09:30" in text


def test_task_dialog_get_task_data_for_weekly() -> None:
    """TaskDialog возвращает expected payload для weekly."""
    dialog = scheduler_tab.TaskDialog.__new__(scheduler_tab.TaskDialog)
    dialog.name_edit = SimpleNamespace(text=lambda: "Weekly task")
    dialog.type_combo = SimpleNamespace(currentIndex=lambda: 2)
    dialog.area_combo = SimpleNamespace(currentIndex=lambda: 0)
    dialog.audio_combo = SimpleNamespace(currentIndex=lambda: 0)
    dialog.fps_spin = SimpleNamespace(value=lambda: 30)
    dialog.duration_spin = SimpleNamespace(value=lambda: 0)
    dialog.duration_unit_combo = SimpleNamespace(currentIndex=lambda: 1)
    dialog.time_edit = SimpleNamespace(
        time=lambda: SimpleNamespace(hour=lambda: 8, minute=lambda: 45)
    )
    dialog.day_checks = [
        SimpleNamespace(isChecked=lambda: True),
        SimpleNamespace(isChecked=lambda: False),
        SimpleNamespace(isChecked=lambda: True),
        SimpleNamespace(isChecked=lambda: False),
        SimpleNamespace(isChecked=lambda: True),
        SimpleNamespace(isChecked=lambda: False),
        SimpleNamespace(isChecked=lambda: False),
    ]
    dialog.interval_hours = SimpleNamespace(value=lambda: 0)
    dialog.interval_minutes = SimpleNamespace(value=lambda: 0)
    dialog.cron_edit = SimpleNamespace(text=lambda: "")
    dialog.window_edit = SimpleNamespace(text=lambda: "")
    dialog.date_edit = SimpleNamespace(
        date=lambda: SimpleNamespace(
            year=lambda: 2026, month=lambda: 3, day=lambda: 29
        )
    )

    data = dialog.get_task_data()

    assert data["name"] == "Weekly task"
    assert data["schedule_type"] == ScheduleType.WEEKLY
    assert data["time_of_day"] == "08:45"
    assert data["days_of_week"] == [0, 2, 4]


def test_task_dialog_accept_rejects_weekly_without_days(monkeypatch) -> None:
    """Диалог блокирует weekly без выбранных дней."""
    dialog = scheduler_tab.TaskDialog.__new__(scheduler_tab.TaskDialog)
    dialog.type_combo = SimpleNamespace(currentIndex=lambda: 2)
    dialog.day_checks = [SimpleNamespace(isChecked=lambda: False)] * 7
    dialog.interval_hours = SimpleNamespace(value=lambda: 1)
    dialog.interval_minutes = SimpleNamespace(value=lambda: 0)

    warning_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        scheduler_tab.QMessageBox,
        "warning",
        lambda *args: warning_calls.append(args),
    )

    dialog.accept()

    assert len(warning_calls) == 1
    assert "еженедельной" in str(warning_calls[0][2]).lower()


def test_task_dialog_accept_rejects_zero_interval(monkeypatch) -> None:
    """Диалог блокирует interval с нулевым интервалом."""
    dialog = scheduler_tab.TaskDialog.__new__(scheduler_tab.TaskDialog)
    dialog.type_combo = SimpleNamespace(currentIndex=lambda: 3)
    dialog.day_checks = [SimpleNamespace(isChecked=lambda: True)] * 7
    dialog.interval_hours = SimpleNamespace(value=lambda: 0)
    dialog.interval_minutes = SimpleNamespace(value=lambda: 0)

    warning_calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        scheduler_tab.QMessageBox,
        "warning",
        lambda *args: warning_calls.append(args),
    )

    dialog.accept()

    assert len(warning_calls) == 1
    assert "интервал" in str(warning_calls[0][2]).lower()
