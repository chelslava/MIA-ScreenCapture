"""Диалог создания и редактирования задач планировщика."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from PyQt6.QtCore import QDate, QTime
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from cli.templates import get_preset, list_presets
from logger_config import get_module_logger
from scheduler.task_scheduler import (
    RecordingParams,
    ScheduleTask,
    ScheduleType,
)
from scheduler.trigger_builder import create_trigger

logger = get_module_logger(__name__)
_SCHEDULE_PREVIEW_COUNT = 5


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
        self._preset_names: list[str] = [""]
        self._existing_next_run_text = (
            task.next_run.strftime("%Y-%m-%d %H:%M")
            if task is not None and task.next_run is not None
            else ""
        )
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

        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Без preset")
        self._preset_names = [""]
        for preset in list_presets():
            preset_name = str(preset.get("name", "")).strip()
            if not preset_name:
                continue
            display_name = str(preset.get("display_name", preset_name)).strip()
            self.preset_combo.addItem(f"{display_name} ({preset_name})")
            self._preset_names.append(preset_name)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        form_layout.addRow("Preset:", self.preset_combo)

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

        preview_group = QGroupBox("Preview расписания")
        preview_layout = QVBoxLayout(preview_group)
        self._inline_validation_label = QLabel("")
        self._inline_validation_label.setStyleSheet("color: #ef4444;")
        self._inline_validation_label.setVisible(False)
        preview_layout.addWidget(self._inline_validation_label)

        self._schedule_preview_label = QLabel(
            "Следующие запуски будут показаны после заполнения расписания."
        )
        self._schedule_preview_label.setWordWrap(True)
        preview_layout.addWidget(self._schedule_preview_label)

        self._existing_next_run_label = QLabel("")
        self._existing_next_run_label.setVisible(False)
        preview_layout.addWidget(self._existing_next_run_label)
        layout.addWidget(preview_group)

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
        self._connect_live_preview_signals()
        self._refresh_schedule_preview()

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
        if hasattr(self, "_schedule_preview_label"):
            self._refresh_schedule_preview()

    def _connect_live_preview_signals(self) -> None:
        """Подключить live-preview и inline-validation обновления."""
        self.name_edit.textChanged.connect(
            lambda *_args: self._refresh_schedule_preview()
        )
        self.date_edit.dateChanged.connect(
            lambda *_args: self._refresh_schedule_preview()
        )
        self.time_edit.timeChanged.connect(
            lambda *_args: self._refresh_schedule_preview()
        )
        self.interval_hours.valueChanged.connect(
            lambda *_args: self._refresh_schedule_preview()
        )
        self.interval_minutes.valueChanged.connect(
            lambda *_args: self._refresh_schedule_preview()
        )
        self.cron_edit.textChanged.connect(
            lambda *_args: self._refresh_schedule_preview()
        )
        self.duration_spin.valueChanged.connect(
            lambda *_args: self._refresh_schedule_preview()
        )
        self.duration_unit_combo.currentIndexChanged.connect(
            lambda *_args: self._refresh_schedule_preview()
        )
        for day_check in self.day_checks:
            day_check.stateChanged.connect(
                lambda *_args: self._refresh_schedule_preview()
            )

    def _on_preset_changed(self, index: int) -> None:
        """Применение выбранного preset из CLI-контракта."""
        if not (0 <= index < len(self._preset_names)):
            self._refresh_schedule_preview()
            return

        preset_name = self._preset_names[index]
        if not preset_name:
            self._refresh_schedule_preview()
            return

        preset = get_preset(preset_name)
        if preset is None:
            return
        self._apply_preset(preset)

    def _apply_preset(self, preset: dict[str, Any]) -> None:
        """Применить preset к форме диалога."""
        trigger_type = str(preset.get("trigger", "daily"))
        type_index_map = {
            "once": 0,
            "daily": 1,
            "weekly": 2,
            "interval": 3,
            "cron": 4,
        }
        self.type_combo.setCurrentIndex(type_index_map.get(trigger_type, 1))

        preset_title = str(preset.get("name", "")).strip()
        if preset_title:
            self.name_edit.setText(preset_title)

        preset_time = str(preset.get("time", "")).strip()
        if preset_time:
            parts = preset_time.split(":")
            if len(parts) >= 2:
                self.time_edit.setTime(QTime(int(parts[0]), int(parts[1])))

        for day_check in self.day_checks:
            day_check.setChecked(False)
        for day in preset.get("days_of_week", []):
            if 0 <= day < len(self.day_checks):
                self.day_checks[day].setChecked(True)

        self.interval_hours.setValue(int(preset.get("interval_hours", 0) or 0))
        self.interval_minutes.setValue(
            int(preset.get("interval_minutes", 0) or 0)
        )
        self.cron_edit.setText(str(preset.get("cron_expression", "")).strip())

        params = cast(dict[str, Any], preset.get("params", {}))
        area_map = {"full": 0, "window": 1, "rect": 2}
        if "area" in params:
            self.area_combo.setCurrentIndex(
                area_map.get(str(params["area"]), 0)
            )

        audio_map = {"none": 0, "mic": 1, "system": 2, "both": 3}
        if "audio" in params:
            self.audio_combo.setCurrentIndex(
                audio_map.get(str(params["audio"]), 0)
            )

        duration_value = params.get("duration")
        if isinstance(duration_value, int) and duration_value > 0:
            if duration_value % 60 == 0:
                self.duration_spin.setValue(duration_value // 60)
                self.duration_unit_combo.setCurrentIndex(1)
            else:
                self.duration_spin.setValue(duration_value)
                self.duration_unit_combo.setCurrentIndex(0)
        else:
            self.duration_spin.setValue(0)
            self.duration_unit_combo.setCurrentIndex(1)

        self._refresh_schedule_preview()

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
        self._refresh_schedule_preview()

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

    def _validate_schedule_inputs(self) -> str | None:
        """Проверка расписания до submit для inline/preview сценариев."""
        schedule_type_index = self.type_combo.currentIndex()

        if schedule_type_index == 2:  # Еженедельная
            selected_days = [c for c in self.day_checks if c.isChecked()]
            if not selected_days:
                return "Для еженедельной задачи выберите хотя бы один день."

        if schedule_type_index == 3:  # Интервал
            hours = self.interval_hours.value()
            minutes = self.interval_minutes.value()
            if hours <= 0 and minutes <= 0:
                return "Интервал должен быть больше нуля."

        if schedule_type_index == 4:  # Cron
            cron_expression = self.cron_edit.text().strip()
            if not cron_expression:
                return "Укажите cron-выражение."

        if schedule_type_index == 0:  # Разовая
            start_time = datetime(
                self.date_edit.date().year(),
                self.date_edit.date().month(),
                self.date_edit.date().day(),
                self.time_edit.time().hour(),
                self.time_edit.time().minute(),
            )
            if start_time <= datetime.now():
                return "Для разовой задачи выберите время в будущем."

        return None

    def _build_preview_task(self) -> ScheduleTask:
        """Собрать временную задачу для расчёта preview запусков."""
        data = self.get_task_data()
        params = RecordingParams(
            area_type=str(data.get("area_type", "full")),
            window_title=str(data.get("window_title", "")),
            audio_type=str(data.get("audio_type", "none")),
            fps=int(data.get("fps", 30)),
            duration=cast(int | None, data.get("duration")),
        )
        return ScheduleTask(
            id="preview-task",
            name=str(data.get("name", "Preview")),
            schedule_type=cast(ScheduleType, data["schedule_type"]),
            params=params,
            enabled=True,
            start_time=cast(datetime | None, data.get("start_time")),
            time_of_day=cast(str | None, data.get("time_of_day")),
            days_of_week=cast(list[int] | None, data.get("days_of_week")),
            interval_hours=cast(int | None, data.get("interval_hours")),
            interval_minutes=cast(int | None, data.get("interval_minutes")),
            cron_expression=cast(str | None, data.get("cron_expression")),
        )

    def _calculate_schedule_preview(
        self,
        count: int = _SCHEDULE_PREVIEW_COUNT,
    ) -> tuple[list[datetime], str | None]:
        """Рассчитать следующие запуски для текущей формы задачи."""
        try:
            task = self._build_preview_task()
            trigger = create_trigger(task, self._parse_time_of_day)
            if trigger is None:
                return [], "Не удалось построить расписание для preview."

            preview_runs: list[datetime] = []
            previous_fire_time = None
            now = datetime.now()
            for _ in range(count):
                next_fire_time = trigger.get_next_fire_time(
                    previous_fire_time,
                    now,
                )
                if next_fire_time is None:
                    break
                preview_runs.append(next_fire_time)
                previous_fire_time = next_fire_time
                now = next_fire_time
            return preview_runs, None
        except Exception as error:
            logger.debug("Ошибка preview расписания: %s", error)
            return [], str(error)

    @staticmethod
    def _parse_time_of_day(value: str) -> tuple[int, int]:
        """Преобразует строку HH:MM в часы и минуты с валидацией."""
        parts = value.split(":")
        if len(parts) != 2:
            raise ValueError("time_of_day должен быть в формате HH:MM")
        hour = int(parts[0])
        minute = int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError(
                "time_of_day должен быть в диапазоне 00:00..23:59"
            )
        return hour, minute

    def _set_inline_validation_message(self, message: str | None) -> None:
        """Показать или скрыть inline validation сообщение."""
        if message is None:
            self._inline_validation_label.setText("")
            self._inline_validation_label.setVisible(False)
            return
        self._inline_validation_label.setText(message)
        self._inline_validation_label.setVisible(True)

    def _refresh_schedule_preview(self) -> None:
        """Обновить preview следующих запусков и inline validation."""
        existing_next_run_text = self._existing_next_run_text
        if existing_next_run_text:
            self._existing_next_run_label.setText(
                f"Сохранённый next_run: {existing_next_run_text}"
            )
            self._existing_next_run_label.setVisible(True)
        else:
            self._existing_next_run_label.setVisible(False)

        validation_error = self._validate_schedule_inputs()
        if validation_error is not None:
            self._set_inline_validation_message(validation_error)
            self._schedule_preview_label.setText(
                "Исправьте ошибки расписания, чтобы увидеть preview запусков."
            )
            return

        preview_runs, preview_error = self._calculate_schedule_preview()
        if preview_error is not None:
            self._set_inline_validation_message(
                f"Не удалось рассчитать preview: {preview_error}"
            )
            self._schedule_preview_label.setText(
                "Preview запусков недоступен."
            )
            return

        self._set_inline_validation_message(None)
        if not preview_runs:
            self._schedule_preview_label.setText(
                "Нет предстоящих запусков для текущих параметров."
            )
            return

        preview_text = "\n".join(
            f"{index}. {run.strftime('%Y-%m-%d %H:%M')}"
            for index, run in enumerate(preview_runs, start=1)
        )
        self._schedule_preview_label.setText(preview_text)

    def accept(self) -> None:
        """
        Валидирует данные формы перед закрытием диалога.

        Блокирует сохранение заведомо невыполнимых сценариев:
        - weekly без выбранных дней;
        - interval с нулевым интервалом.
        """
        validation_error = self._validate_schedule_inputs()
        if validation_error is not None:
            self._set_inline_validation_message(validation_error)
            QMessageBox.warning(
                self,
                "Некорректное расписание",
                validation_error,
            )
            return

        super().accept()
