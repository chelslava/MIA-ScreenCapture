"""
Модуль вкладки планировщика
===========================

Вкладка GUI для управления запланированными задачами записи.
"""

from datetime import datetime
from typing import Any, cast

from PyQt6.QtCore import QDate, Qt, QTime, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from gui.accessibility import apply_accessible_metadata
from logger_config import get_module_logger
from scheduler.task_scheduler import (
    ScheduleTask,
    ScheduleType,
)

logger = get_module_logger(__name__)


class TaskDialog(QDialog):
    """Диалог для создания/редактирования запланированных задач."""

    def __init__(self, parent=None, task: ScheduleTask | None = None):
        """
        Инициализация диалога задачи.

        Args:
            parent: Родительский виджет
            task: Существующая задача для редактирования (опционально)
        """
        super().__init__(parent)
        self.task = task
        self.setWindowTitle(
            "Редактирование задачи" if task else "Новая задача"
        )
        self.setMinimumWidth(500)

        self._setup_ui()

        if task:
            self._load_task(task)

    def _setup_ui(self) -> None:
        """Настройка UI диалога."""
        layout = QVBoxLayout(self)

        # Имя задачи
        form_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Введите имя задачи")
        form_layout.addRow("Имя:", self.name_edit)

        # Тип расписания
        self.type_combo = QComboBox()
        self.type_combo.addItems(
            ["Разовая", "Ежедневная", "Еженедельная", "Интервал", "Cron"]
        )
        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        form_layout.addRow("Тип расписания:", self.type_combo)

        layout.addLayout(form_layout)

        # Опции специфичные для расписания
        self.schedule_group = QGroupBox("Расписание")
        schedule_layout = QFormLayout(self.schedule_group)

        # Разовая: дата и время
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        schedule_layout.addRow("Дата:", self.date_edit)

        # Время для ежедневной/еженедельной
        self.time_edit = QTimeEdit()
        self.time_edit.setTime(QTime(12, 0))
        schedule_layout.addRow("Время:", self.time_edit)

        # Дни недели для еженедельной
        self.days_widget = QWidget()
        days_layout = QHBoxLayout(self.days_widget)
        days_layout.setContentsMargins(0, 0, 0, 0)
        self.day_checks = []
        day_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        for _i, name in enumerate(day_names):
            check = QCheckBox(name)
            self.day_checks.append(check)
            days_layout.addWidget(check)
        schedule_layout.addRow("Дни:", self.days_widget)

        # Интервал
        self.interval_widget = QWidget()
        interval_layout = QHBoxLayout(self.interval_widget)
        interval_layout.setContentsMargins(0, 0, 0, 0)

        self.interval_hours = QSpinBox()
        self.interval_hours.setRange(0, 168)
        self.interval_hours.setValue(0)
        interval_layout.addWidget(QLabel("Часы:"))
        interval_layout.addWidget(self.interval_hours)

        self.interval_minutes = QSpinBox()
        self.interval_minutes.setRange(0, 59)
        self.interval_minutes.setValue(30)
        interval_layout.addWidget(QLabel("Минуты:"))
        interval_layout.addWidget(self.interval_minutes)

        schedule_layout.addRow("Интервал:", self.interval_widget)

        # Cron-выражение
        self.cron_widget = QWidget()
        cron_layout = QHBoxLayout(self.cron_widget)
        cron_layout.setContentsMargins(0, 0, 0, 0)

        self.cron_edit = QLineEdit()
        self.cron_edit.setPlaceholderText(
            "Например: 0 9 * * 1-5 (каждый будний день в 9:00)"
        )
        cron_layout.addWidget(self.cron_edit)

        schedule_layout.addRow("Cron:", self.cron_widget)

        layout.addWidget(self.schedule_group)

        # Параметры записи
        params_group = QGroupBox("Параметры записи")
        params_layout = QFormLayout(params_group)

        # Тип области
        self.area_combo = QComboBox()
        self.area_combo.addItems(["Полный экран", "Окно", "Прямоугольник"])
        params_layout.addRow("Область захвата:", self.area_combo)

        # Заголовок окна
        self.window_edit = QLineEdit()
        self.window_edit.setPlaceholderText(
            "Заголовок окна (частичное совпадение)"
        )
        params_layout.addRow("Окно:", self.window_edit)

        # Аудио
        self.audio_combo = QComboBox()
        self.audio_combo.addItems(
            ["Нет", "Микрофон", "Системное аудио", "Оба"]
        )
        params_layout.addRow("Аудио:", self.audio_combo)

        # Длительность
        self.duration_widget = QWidget()
        duration_layout = QHBoxLayout(self.duration_widget)
        duration_layout.setContentsMargins(0, 0, 0, 0)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(
            0, 1440
        )  # Максимум 24 часа в минутах или секундах
        self.duration_spin.setValue(0)
        self.duration_spin.setSpecialValueText("Без ограничения")
        duration_layout.addWidget(self.duration_spin)

        self.duration_unit_combo = QComboBox()
        self.duration_unit_combo.addItems(["секунд", "минут"])
        self.duration_unit_combo.setCurrentIndex(1)  # По умолчанию минуты
        duration_layout.addWidget(self.duration_unit_combo)

        params_layout.addRow("Длительность:", self.duration_widget)

        # FPS
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 120)
        self.fps_spin.setValue(30)
        params_layout.addRow("FPS:", self.fps_spin)

        layout.addWidget(params_group)

        # Кнопки
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Начальное состояние
        self._on_type_changed(0)

    def _on_type_changed(self, index: int) -> None:
        """Обработка изменения типа расписания."""
        schedule_type = index

        # Показ/скрытие виджетов в зависимости от типа
        is_once = schedule_type == 0
        is_daily = schedule_type == 1
        is_weekly = schedule_type == 2
        is_interval = schedule_type == 3
        is_cron = schedule_type == 4

        self.date_edit.setVisible(is_once)
        self.time_edit.setVisible(is_once or is_daily or is_weekly)
        self.days_widget.setVisible(is_weekly)
        self.interval_widget.setVisible(is_interval)
        self.cron_widget.setVisible(is_cron)

    def _load_task(self, task: ScheduleTask) -> None:
        """Загрузка данных существующей задачи в диалог."""
        self.name_edit.setText(task.name)

        # Установка типа расписания
        type_map = {
            ScheduleType.ONCE: 0,
            ScheduleType.DAILY: 1,
            ScheduleType.WEEKLY: 2,
            ScheduleType.INTERVAL: 3,
            ScheduleType.CRON: 4,
        }
        self.type_combo.setCurrentIndex(type_map.get(task.schedule_type, 0))

        # Загрузка данных специфичных для расписания
        if task.start_time:
            self.date_edit.setDate(
                QDate(
                    task.start_time.year,
                    task.start_time.month,
                    task.start_time.day,
                )
            )
            self.time_edit.setTime(
                QTime(task.start_time.hour, task.start_time.minute)
            )

        if task.time_of_day:
            parts = task.time_of_day.split(":")
            if len(parts) >= 2:
                self.time_edit.setTime(QTime(int(parts[0]), int(parts[1])))

        if task.days_of_week:
            for day in task.days_of_week:
                if 0 <= day < len(self.day_checks):
                    self.day_checks[day].setChecked(True)

        if task.interval_hours:
            self.interval_hours.setValue(task.interval_hours)
        if task.interval_minutes:
            self.interval_minutes.setValue(task.interval_minutes)

        # Загрузка cron-выражения
        if task.cron_expression:
            self.cron_edit.setText(task.cron_expression)

        # Загрузка параметров записи
        area_map = {"full": 0, "window": 1, "rect": 2}
        self.area_combo.setCurrentIndex(area_map.get(task.params.area_type, 0))

        if task.params.window_title:
            self.window_edit.setText(task.params.window_title)

        audio_map = {"none": 0, "mic": 1, "system": 2, "both": 3}
        self.audio_combo.setCurrentIndex(
            audio_map.get(task.params.audio_type, 0)
        )

        if task.params.duration:
            # Если длительность кратна 60 секундам, показываем в минутах
            if task.params.duration % 60 == 0:
                self.duration_spin.setValue(task.params.duration // 60)
                self.duration_unit_combo.setCurrentIndex(1)  # Минуты
            else:
                self.duration_spin.setValue(task.params.duration)
                self.duration_unit_combo.setCurrentIndex(0)  # Секунды

        self.fps_spin.setValue(task.params.fps)

    def get_task_data(self) -> dict[str, Any]:
        """Получение данных задачи из диалога."""
        schedule_types = [
            ScheduleType.ONCE,
            ScheduleType.DAILY,
            ScheduleType.WEEKLY,
            ScheduleType.INTERVAL,
            ScheduleType.CRON,
        ]

        area_types = ["full", "window", "rect"]
        audio_types = ["none", "mic", "system", "both"]

        # Вычисление длительности с учётом единиц измерения
        duration_spin_value = self.duration_spin.value()
        duration_value: int | None = None
        if duration_spin_value > 0:
            # Если выбраны минуты (индекс 1), конвертируем в секунды
            if self.duration_unit_combo.currentIndex() == 1:
                duration_value = duration_spin_value * 60
            else:
                duration_value = duration_spin_value

        data = {
            "name": self.name_edit.text() or "Безымянная задача",
            "schedule_type": schedule_types[self.type_combo.currentIndex()],
            "area_type": area_types[self.area_combo.currentIndex()],
            "audio_type": audio_types[self.audio_combo.currentIndex()],
            "fps": self.fps_spin.value(),
            "duration": duration_value,
        }

        # Данные специфичные для расписания
        if self.type_combo.currentIndex() == 0:  # Разовая
            data["start_time"] = datetime(
                self.date_edit.date().year(),
                self.date_edit.date().month(),
                self.date_edit.date().day(),
                self.time_edit.time().hour(),
                self.time_edit.time().minute(),
            )
        elif self.type_combo.currentIndex() in (
            1,
            2,
        ):  # Ежедневная или Еженедельная
            data["time_of_day"] = (
                f"{self.time_edit.time().hour():02d}:{self.time_edit.time().minute():02d}"
            )

            if self.type_combo.currentIndex() == 2:  # Еженедельная
                days = [
                    i
                    for i, check in enumerate(self.day_checks)
                    if check.isChecked()
                ]
                data["days_of_week"] = days
        elif self.type_combo.currentIndex() == 3:  # Интервал
            data["interval_hours"] = self.interval_hours.value()
            data["interval_minutes"] = self.interval_minutes.value()
        elif self.type_combo.currentIndex() == 4:  # Cron
            data["cron_expression"] = self.cron_edit.text().strip()

        # Заголовок окна
        if self.area_combo.currentIndex() == 1:  # Окно
            data["window_title"] = self.window_edit.text()

        return data

    def accept(self) -> None:
        """
        Валидирует данные формы перед закрытием диалога.

        Блокирует сохранение заведомо невыполнимых сценариев:
        - weekly без выбранных дней;
        - interval с нулевым интервалом.
        """
        schedule_type_index = self.type_combo.currentIndex()
        if schedule_type_index == 2:  # Еженедельная
            selected_days = [c for c in self.day_checks if c.isChecked()]
            if not selected_days:
                QMessageBox.warning(
                    self,
                    "Некорректное расписание",
                    "Для еженедельной задачи выберите хотя бы один день.",
                )
                return

        if schedule_type_index == 3:  # Интервал
            hours = self.interval_hours.value()
            minutes = self.interval_minutes.value()
            if hours <= 0 and minutes <= 0:
                QMessageBox.warning(
                    self,
                    "Некорректное расписание",
                    "Интервал должен быть больше нуля.",
                )
                return

        super().accept()


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
