"""
Представление тонких параметров записи (#155)
=============================================

Секция «Расширенные параметры записи» на вкладке настроек: frame-skip,
попытки восстановления FFmpeg/аудио, пороги свободного места, лимиты
сегментов и интервал health-check. Дефолты идентичны прежнему поведению
конструкторов рекордеров.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from config import RecordingTunables
from gui.accessibility import apply_accessible_metadata
from logger_config import get_module_logger

logger = get_module_logger(__name__)

# 0 в поле лимита сегмента означает «без лимита» (None в конфиге)
_NO_SEGMENT_LIMIT = 0


class RecordingTunablesView(QWidget):
    """Виджет тонких параметров записи (frame-skip, recovery, пороги)."""

    settings_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Расширенные параметры записи")
        form = QFormLayout(group)

        self._frame_skip_cb = QCheckBox(
            "Пропускать кадры при отставании записи"
        )
        self._frame_skip_cb.toggled.connect(self._emit_change)
        form.addRow(self._frame_skip_cb)

        self._recovery_spin = QSpinBox()
        self._recovery_spin.setRange(1, 10)
        self._recovery_spin.setValue(3)
        self._recovery_spin.setSuffix(" поп.")
        self._recovery_spin.valueChanged.connect(self._emit_change)
        form.addRow("Попыток восстановления FFmpeg:", self._recovery_spin)

        self._audio_recovery_spin = QSpinBox()
        self._audio_recovery_spin.setRange(1, 10)
        self._audio_recovery_spin.setValue(3)
        self._audio_recovery_spin.setSuffix(" поп.")
        self._audio_recovery_spin.valueChanged.connect(self._emit_change)
        form.addRow("Попыток восстановления аудио:", self._audio_recovery_spin)

        self._disk_warning_spin = QDoubleSpinBox()
        self._disk_warning_spin.setRange(0.0, 2_000_000.0)
        self._disk_warning_spin.setValue(1024.0)
        self._disk_warning_spin.setSuffix(" МБ")
        self._disk_warning_spin.setDecimals(0)
        self._disk_warning_spin.valueChanged.connect(
            self._on_warning_threshold_changed
        )
        form.addRow(
            "Предупреждение о месте на диске:", self._disk_warning_spin
        )

        self._disk_critical_spin = QDoubleSpinBox()
        self._disk_critical_spin.setRange(0.0, 2_000_000.0)
        self._disk_critical_spin.setValue(100.0)
        self._disk_critical_spin.setSuffix(" МБ")
        self._disk_critical_spin.setDecimals(0)
        self._disk_critical_spin.valueChanged.connect(self._emit_change)
        form.addRow(
            "Остановка при критическом месте:", self._disk_critical_spin
        )

        self._disk_check_interval_spin = QDoubleSpinBox()
        self._disk_check_interval_spin.setRange(1.0, 600.0)
        self._disk_check_interval_spin.setValue(30.0)
        self._disk_check_interval_spin.setSuffix(" с")
        self._disk_check_interval_spin.setDecimals(0)
        self._disk_check_interval_spin.valueChanged.connect(self._emit_change)
        form.addRow(
            "Интервал проверки места на диске:", self._disk_check_interval_spin
        )

        self._segment_size_spin = QDoubleSpinBox()
        self._segment_size_spin.setRange(0.0, 1_000_000.0)
        self._segment_size_spin.setValue(_NO_SEGMENT_LIMIT)
        self._segment_size_spin.setSpecialValueText("Без лимита")
        self._segment_size_spin.setSuffix(" МБ")
        self._segment_size_spin.setDecimals(0)
        self._segment_size_spin.valueChanged.connect(self._emit_change)
        form.addRow("Лимит размера сегмента:", self._segment_size_spin)

        self._segment_duration_spin = QDoubleSpinBox()
        self._segment_duration_spin.setRange(0.0, 86_400.0)
        self._segment_duration_spin.setValue(_NO_SEGMENT_LIMIT)
        self._segment_duration_spin.setSpecialValueText("Без лимита")
        self._segment_duration_spin.setSuffix(" с")
        self._segment_duration_spin.setDecimals(0)
        self._segment_duration_spin.valueChanged.connect(self._emit_change)
        form.addRow(
            "Лимит длительности сегмента:", self._segment_duration_spin
        )

        self._health_check_spin = QDoubleSpinBox()
        self._health_check_spin.setRange(0.1, 60.0)
        self._health_check_spin.setValue(1.0)
        self._health_check_spin.setSuffix(" с")
        self._health_check_spin.setDecimals(1)
        self._health_check_spin.setSingleStep(0.5)
        self._health_check_spin.valueChanged.connect(self._emit_change)
        form.addRow("Интервал health-check FFmpeg:", self._health_check_spin)

        layout.addWidget(group)
        layout.addStretch()

        apply_accessible_metadata(
            group,
            "Расширенные параметры записи",
            "Тонкая настройка frame-skip, восстановления и порогов диска.",
            "Изменения сохраняются автоматически.",
        )

    def _emit_change(self, *_args: Any) -> None:
        """Сигнал изменения любой настройки."""
        self.settings_changed.emit()

    def _on_warning_threshold_changed(self, value: float) -> None:
        """Критический порог не может превышать предупреждение."""
        critical = self._disk_critical_spin.value()
        if critical > value:
            self._disk_critical_spin.setValue(value)
        self._emit_change()

    def get_settings(self) -> RecordingTunables:
        """Считывание настроек из полей формы.

        Критический порог диска клампится к warning независимо от порядка
        правок полей — иначе config.save() отклонил бы невалидную пару.
        """
        segment_size = self._segment_size_spin.value()
        segment_duration = self._segment_duration_spin.value()
        disk_warning = self._disk_warning_spin.value()
        return RecordingTunables(
            enable_frame_skip=self._frame_skip_cb.isChecked(),
            max_recovery_attempts=self._recovery_spin.value(),
            audio_max_recovery_attempts=self._audio_recovery_spin.value(),
            disk_warning_mb=disk_warning,
            disk_critical_mb=min(
                self._disk_critical_spin.value(), disk_warning
            ),
            disk_check_interval_s=self._disk_check_interval_spin.value(),
            max_segment_size_mb=(
                segment_size if segment_size > _NO_SEGMENT_LIMIT else None
            ),
            max_segment_duration_s=(
                segment_duration
                if segment_duration > _NO_SEGMENT_LIMIT
                else None
            ),
            health_check_interval_s=self._health_check_spin.value(),
        )

    def set_settings(self, settings: RecordingTunables) -> None:
        """Заполнение формы переданными настройками."""
        self._frame_skip_cb.setChecked(settings.enable_frame_skip)
        self._recovery_spin.setValue(settings.max_recovery_attempts)
        self._audio_recovery_spin.setValue(
            settings.audio_max_recovery_attempts
        )
        self._disk_warning_spin.setValue(settings.disk_warning_mb)
        self._disk_critical_spin.setValue(settings.disk_critical_mb)
        self._disk_check_interval_spin.setValue(settings.disk_check_interval_s)
        self._segment_size_spin.setValue(
            settings.max_segment_size_mb or _NO_SEGMENT_LIMIT
        )
        self._segment_duration_spin.setValue(
            settings.max_segment_duration_s or _NO_SEGMENT_LIMIT
        )
        self._health_check_spin.setValue(settings.health_check_interval_s)
