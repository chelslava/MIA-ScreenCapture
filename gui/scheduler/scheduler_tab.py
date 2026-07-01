"""Вкладка планировщика задач GUI."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.accessibility import apply_accessible_metadata
from logger_config import get_module_logger
from scheduler.task_scheduler import ScheduleTask, ScheduleType

from .task_dialog import TaskDialog

logger = get_module_logger(__name__)

_EMPTY_TASKS_TEXT = "Нет запланированных задач"
_EMPTY_FILTER_TEXT = "Нет задач, соответствующих фильтру"

_TYPE_LABELS = {
    ScheduleType.ONCE: "Разовая",
    ScheduleType.DAILY: "Ежедневная",
    ScheduleType.WEEKLY: "Еженедельная",
    ScheduleType.INTERVAL: "Интервал",
    ScheduleType.CRON: "Cron",
}


class SchedulerTab(QWidget):
    """Виджет вкладки для управления запланированными задачами."""

    # Сигналы
    task_created = pyqtSignal(dict)
    task_updated = pyqtSignal(dict)
    task_deleted = pyqtSignal(str)
    task_toggled = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        """Инициализация вкладки планировщика."""
        super().__init__(parent)

        self._tasks: list[ScheduleTask] = []
        self._visible_tasks: list[ScheduleTask] = []

        self._setup_ui()

    def _setup_ui(self) -> None:
        """Настройка UI вкладки."""
        layout = QVBoxLayout(self)

        # Панель инструментов
        toolbar = QHBoxLayout()

        self.add_btn = QPushButton("Добавить задачу")
        self.add_btn.clicked.connect(self._add_task)
        toolbar.addWidget(self.add_btn)

        self.edit_btn = QPushButton("Редактировать")
        self.edit_btn.clicked.connect(self._edit_task)
        self.edit_btn.setEnabled(False)
        toolbar.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("Удалить")
        self.delete_btn.clicked.connect(self._delete_task)
        self.delete_btn.setEnabled(False)
        toolbar.addWidget(self.delete_btn)

        self.toggle_btn = QPushButton("Включить/Отключить")
        self.toggle_btn.clicked.connect(self._toggle_task)
        self.toggle_btn.setEnabled(False)
        toolbar.addWidget(self.toggle_btn)

        toolbar.addStretch()

        layout.addLayout(toolbar)

        # Фильтр задач
        filter_layout = QHBoxLayout()

        self._filter_input = QLineEdit()
        self._filter_input.setPlaceholderText("Поиск по имени задачи")
        self._filter_input.textChanged.connect(self._on_filter_text_changed)
        filter_layout.addWidget(self._filter_input)

        self._clear_filter_btn = QPushButton("Сбросить")
        self._clear_filter_btn.clicked.connect(self._clear_filter)
        filter_layout.addWidget(self._clear_filter_btn)

        layout.addLayout(filter_layout)

        # Таблица задач
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            [
                "Имя",
                "Тип",
                "Расписание",
                "Следующий запуск",
                "Статус",
                "Запуски",
            ]
        )
        header = self.table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(self._edit_task)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(
            self._show_table_context_menu
        )

        layout.addWidget(self.table)

        # Информационная метка
        self.info_label = QLabel(_EMPTY_TASKS_TEXT)
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.info_label)
        self._apply_accessibility_metadata()

    def _apply_accessibility_metadata(self) -> None:
        """Назначение accessibility metadata для controls планировщика."""
        apply_accessible_metadata(
            self.add_btn,
            "Добавить задачу планировщика",
            "Открывает форму создания новой задачи расписания.",
            "Добавляет новую задачу расписания.",
        )
        apply_accessible_metadata(
            self.edit_btn,
            "Редактировать задачу планировщика",
            "Открывает форму редактирования выбранной задачи.",
            "Редактирует выбранную задачу.",
        )
        apply_accessible_metadata(
            self.delete_btn,
            "Удалить задачу планировщика",
            "Удаляет выбранную задачу после подтверждения.",
            "Удаляет выбранную задачу.",
        )
        apply_accessible_metadata(
            self.toggle_btn,
            "Включить или отключить задачу планировщика",
            "Переключает состояние выбранной задачи расписания.",
            "Включает или отключает выбранную задачу.",
        )
        apply_accessible_metadata(
            self._filter_input,
            "Поиск задач планировщика",
            "Фильтрует список задач по имени, типу и расписанию.",
            "Фильтрует задачи планировщика.",
        )
        apply_accessible_metadata(
            self._clear_filter_btn,
            "Сбросить фильтр задач планировщика",
            "Очищает текст фильтра и показывает все задачи.",
            "Сбрасывает фильтр задач планировщика.",
        )
        apply_accessible_metadata(
            self.table,
            "Список задач планировщика",
            "Показывает все созданные задачи и их состояние.",
        )
        apply_accessible_metadata(
            self.info_label,
            "Статус списка задач планировщика",
            "Показывает, есть ли в таблице задачи расписания.",
        )

    def _on_selection_changed(self) -> None:
        """Обработка изменения выбора в таблице."""
        has_selection = len(self.table.selectedItems()) > 0
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        self.toggle_btn.setEnabled(has_selection)

    def _add_task(self) -> None:
        """Открытие диалога для добавления новой задачи."""
        dialog = TaskDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_task_data()
            self.task_created.emit(data)

    def _task_at_row(self, row: int) -> ScheduleTask | None:
        """Задача для строки таблицы с учётом активного фильтра."""
        tasks = getattr(self, "_visible_tasks", None)
        if tasks is None:
            tasks = self._tasks
        if row < 0 or row >= len(tasks):
            return None
        return tasks[row]

    def _edit_task(self) -> None:
        """Открытие диалога для редактирования выбранной задачи."""
        task = self._task_at_row(self.table.currentRow())
        if task is None:
            return

        dialog = TaskDialog(self, task)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_task_data()
            data["id"] = task.id
            self.task_updated.emit(data)

    def _delete_task(self) -> None:
        """Удаление выбранной задачи."""
        task = self._task_at_row(self.table.currentRow())
        if task is None:
            return

        reply = QMessageBox.question(
            self,
            "Удаление задачи",
            f"Вы уверены, что хотите удалить '{task.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.task_deleted.emit(task.id)

    def _toggle_task(self) -> None:
        """Переключение состояния включения выбранной задачи."""
        task = self._task_at_row(self.table.currentRow())
        if task is None:
            return

        self.task_toggled.emit(task.id, not task.enabled)

    def _show_table_context_menu(self, pos: Any) -> None:
        """Контекстное меню по правому клику на задаче в таблице."""
        row = self.table.rowAt(pos.y())
        if self._task_at_row(row) is None:
            return
        self.table.setCurrentCell(row, 0)

        menu = QMenu(self)

        edit_action = QAction("Редактировать", menu)
        edit_action.triggered.connect(self._edit_task)
        menu.addAction(edit_action)

        toggle_action = QAction("Включить/Отключить", menu)
        toggle_action.triggered.connect(self._toggle_task)
        menu.addAction(toggle_action)

        menu.addSeparator()

        delete_action = QAction("Удалить", menu)
        delete_action.triggered.connect(self._delete_task)
        menu.addAction(delete_action)

        viewport = self.table.viewport()
        global_pos = viewport.mapToGlobal(pos) if viewport else pos
        menu.exec(global_pos)

    def _on_filter_text_changed(self, _text: str) -> None:
        """Реакция на изменение текста фильтра поиска задач."""
        self._refresh_table()

    def _clear_filter(self) -> None:
        """Сброс фильтра поиска задач."""
        self._filter_input.setText("")
        self._refresh_table()

    def _normalized_filter(self) -> str:
        """Нормализация текста фильтра для сравнения."""
        filter_input = getattr(self, "_filter_input", None)
        if filter_input is None:
            return ""
        return str(filter_input.text()).strip().lower()

    def _task_matches_filter(
        self, task: ScheduleTask, filter_text: str
    ) -> bool:
        """Проверка попадания задачи под фильтр по имени и расписанию."""
        haystack = " ".join(
            [
                task.name.lower(),
                _TYPE_LABELS.get(task.schedule_type, "").lower(),
                self._format_schedule(task).lower(),
            ]
        )
        return filter_text in haystack

    def _filtered_tasks(self) -> list[ScheduleTask]:
        """Список задач, прошедших текущий фильтр поиска."""
        filter_text = self._normalized_filter()
        if not filter_text:
            return list(self._tasks)
        return [
            task
            for task in self._tasks
            if self._task_matches_filter(task, filter_text)
        ]

    def set_tasks(self, tasks: list[ScheduleTask]) -> None:
        """
        Обновление списка задач.

        Args:
            tasks: Список запланированных задач
        """
        self._tasks = tasks
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Обновление таблицы задач с учётом активного фильтра."""
        self._visible_tasks = self._filtered_tasks()
        self.table.setRowCount(len(self._visible_tasks))

        for row, task in enumerate(self._visible_tasks):
            # Имя
            self.table.setItem(row, 0, QTableWidgetItem(task.name))

            # Тип
            self.table.setItem(
                row,
                1,
                QTableWidgetItem(
                    _TYPE_LABELS.get(task.schedule_type, "Неизвестно")
                ),
            )

            # Расписание
            schedule_text = self._format_schedule(task)
            self.table.setItem(row, 2, QTableWidgetItem(schedule_text))

            # Следующий запуск
            next_run = (
                task.next_run.strftime("%Y-%m-%d %H:%M")
                if task.next_run
                else "-"
            )
            self.table.setItem(row, 3, QTableWidgetItem(next_run))

            # Статус
            status = "Включено" if task.enabled else "Отключено"
            status_item = QTableWidgetItem(status)
            if not task.enabled:
                status_item.setForeground(Qt.GlobalColor.gray)
            self.table.setItem(row, 4, status_item)

            # Количество запусков
            self.table.setItem(row, 5, QTableWidgetItem(str(task.run_count)))

        if not self._tasks:
            self.info_label.setText(_EMPTY_TASKS_TEXT)
            self.info_label.setVisible(True)
        elif not self._visible_tasks:
            self.info_label.setText(_EMPTY_FILTER_TEXT)
            self.info_label.setVisible(True)
        else:
            self.info_label.setVisible(False)

    def _format_schedule(self, task: ScheduleTask) -> str:
        """Форматирование расписания для отображения."""
        if task.schedule_type == ScheduleType.ONCE:
            if task.start_time:
                return task.start_time.strftime("%Y-%m-%d %H:%M")
        elif task.schedule_type == ScheduleType.DAILY:
            return f"Ежедневно в {task.time_of_day}"
        elif task.schedule_type == ScheduleType.WEEKLY:
            days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
            day_str = ", ".join(days[d] for d in (task.days_of_week or []))
            return f"Еженедельно ({day_str}) в {task.time_of_day}"
        elif task.schedule_type == ScheduleType.INTERVAL:
            parts = []
            if task.interval_hours:
                parts.append(f"{task.interval_hours}ч")
            if task.interval_minutes:
                parts.append(f"{task.interval_minutes}м")
            return f"Каждые {' '.join(parts)}"
        elif task.schedule_type == ScheduleType.CRON:
            return f"Cron: {task.cron_expression or 'не указан'}"
        return "Неизвестно"
