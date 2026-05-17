"""Вкладка планировщика задач GUI."""

from __future__ import annotations

from typing import cast

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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

        layout.addWidget(self.table)

        # Информационная метка
        self.info_label = QLabel("Нет запланированных задач")
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

    def _edit_task(self) -> None:
        """Открытие диалога для редактирования выбранной задачи."""
        row = self.table.currentRow()
        if row < 0 or row >= len(self._tasks):
            return

        task = self._tasks[row]
        dialog = TaskDialog(self, task)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_task_data()
            data["id"] = task.id
            self.task_updated.emit(data)

    def _delete_task(self) -> None:
        """Удаление выбранной задачи."""
        row = self.table.currentRow()
        if row < 0 or row >= len(self._tasks):
            return

        task = self._tasks[row]

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
        row = self.table.currentRow()
        if row < 0 or row >= len(self._tasks):
            return

        task = self._tasks[row]
        self.task_toggled.emit(task.id, not task.enabled)

    def set_tasks(self, tasks: list[ScheduleTask]) -> None:
        """
        Обновление списка задач.

        Args:
            tasks: Список запланированных задач
        """
        self._tasks = tasks
        self._refresh_table()

    def _refresh_table(self) -> None:
        """Обновление таблицы задач."""
        self.table.setRowCount(len(self._tasks))

        for row, task in enumerate(self._tasks):
            # Имя
            self.table.setItem(row, 0, QTableWidgetItem(task.name))

            # Тип
            type_names = {
                ScheduleType.ONCE: "Разовая",
                ScheduleType.DAILY: "Ежедневная",
                ScheduleType.WEEKLY: "Еженедельная",
                ScheduleType.INTERVAL: "Интервал",
                ScheduleType.CRON: "Cron",
            }
            self.table.setItem(
                row,
                1,
                QTableWidgetItem(
                    type_names.get(task.schedule_type, "Неизвестно")
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

        self.info_label.setVisible(len(self._tasks) == 0)

    def _format_schedule(self, task: ScheduleTask) -> str:
        """Форматирование расписания для отображения."""
        if task.schedule_type == ScheduleType.ONCE:
            if task.start_time:
                return cast(str, task.start_time.strftime("%Y-%m-%d %H:%M"))
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
