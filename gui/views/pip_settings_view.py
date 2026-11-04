"""Настройки PiP-оверлея веб-камеры на странице записи (#165).

Компактная группа: включение, выбор устройства, позиция и размер
окна камеры. Список устройств загружается в фоне — вызов
`ffmpeg -list_devices` может занимать несколько секунд.
"""

from __future__ import annotations

import threading

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.recording_types import PiPPosition, PiPSettings
from gui.accessibility import apply_accessible_metadata
from logger_config import get_module_logger
from recorder.camera_capture import list_cameras

logger = get_module_logger(__name__)

_POSITION_LABELS: list[tuple[str, PiPPosition]] = [
    ("Справа внизу", PiPPosition.BOTTOM_RIGHT),
    ("Слева внизу", PiPPosition.BOTTOM_LEFT),
    ("Справа сверху", PiPPosition.TOP_RIGHT),
    ("Слева сверху", PiPPosition.TOP_LEFT),
]


class PipSettingsView(QWidget):
    """Группа настроек наложения веб-камеры (PiP) (#165)."""

    devices_load_completed = pyqtSignal(list)
    enabled_changed = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Инициализировать группу настроек PiP.

        Args:
            parent: Родительский виджет.
        """
        super().__init__(parent)
        self._device_names: list[str] = []
        self._setup_ui()
        self.devices_load_completed.connect(self._on_devices_load_completed)

    def _setup_ui(self) -> None:
        """Настроить пользовательский интерфейс."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Веб-камера (PiP)")
        group_layout = QVBoxLayout(group)

        self._enabled_check = QCheckBox("Наложить веб-камеру на запись")
        self._enabled_check.toggled.connect(self._on_enabled_toggled)
        apply_accessible_metadata(
            self._enabled_check,
            "Наложение веб-камеры",
            "Пишет камеру во время записи и вкомпозитирует её "
            "в угол итогового видео.",
        )
        group_layout.addWidget(self._enabled_check)

        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("Камера:"))
        self._device_combo = QComboBox()
        self._device_combo.setMinimumWidth(200)
        device_layout.addWidget(self._device_combo)
        self._refresh_btn = QPushButton("Обновить")
        self._refresh_btn.setMaximumWidth(90)
        self._refresh_btn.clicked.connect(self._refresh_devices)
        device_layout.addWidget(self._refresh_btn)
        group_layout.addLayout(device_layout)

        position_layout = QHBoxLayout()
        position_layout.addWidget(QLabel("Позиция:"))
        self._position_combo = QComboBox()
        for label, _position in _POSITION_LABELS:
            self._position_combo.addItem(label)
        position_layout.addWidget(self._position_combo)
        position_layout.addWidget(QLabel("Ширина:"))
        self._size_spin = QSpinBox()
        self._size_spin.setRange(10, 50)
        self._size_spin.setValue(20)
        self._size_spin.setSuffix("%")
        self._size_spin.setToolTip(
            "Ширина окна камеры в процентах от ширины основного видео"
        )
        position_layout.addWidget(self._size_spin)
        position_layout.addStretch(1)
        group_layout.addLayout(position_layout)

        self._hint_label = QLabel(
            "Камера пишется во время записи; наложение выполняется "
            "при остановке. Отсутствие камеры не мешает записи."
        )
        if hasattr(self._hint_label, "setWordWrap"):
            self._hint_label.setWordWrap(True)
        group_layout.addWidget(self._hint_label)

        layout.addWidget(group)
        self._update_controls_enabled()

    def _on_enabled_toggled(self, checked: bool) -> None:
        """Включить/отключить контролы настройки камеры.

        Args:
            checked: Новое состояние чекбокса.
        """
        self._update_controls_enabled()
        self.enabled_changed.emit(checked)
        if checked and not self._device_names:
            self._refresh_devices()

    def _update_controls_enabled(self) -> None:
        """Синхронизировать доступность контролов с чекбоксом."""
        enabled = self._enabled_check.isChecked()
        self._device_combo.setEnabled(enabled)
        self._refresh_btn.setEnabled(enabled)
        self._position_combo.setEnabled(enabled)
        self._size_spin.setEnabled(enabled)

    def _refresh_devices(self) -> None:
        """Запустить фоновое перечисление камер (#165)."""
        threading.Thread(target=self._load_devices_worker, daemon=True).start()

    def _load_devices_worker(self) -> None:
        """Перечислить камеры в фоне и отправить результат в GUI-поток."""
        try:
            names = [device.name for device in list_cameras()]
        except (OSError, RuntimeError) as e:
            logger.warning("Ошибка перечисления камер: %s", e)
            names = []
        self.devices_load_completed.emit(names)

    def _on_devices_load_completed(self, names: list) -> None:
        """Заполнить список устройств результатами фоновой загрузки.

        Args:
            names: Имена найденных камер.
        """
        current = self._device_combo.currentText()
        self._device_names = list(names)
        self._device_combo.clear()
        if names:
            self._device_combo.addItems(names)
            index = self._device_combo.findText(current)
            if index >= 0:
                self._device_combo.setCurrentIndex(index)
        else:
            self._device_combo.addItem("Камеры не найдены")

    def get_pip_settings(self) -> PiPSettings | None:
        """Собрать настройки PiP из контролов (#165).

        Returns:
            `PiPSettings` при включённом чекбоксе, иначе `None`.
            Пустой выбор устройства означает «первая найденная камера».
        """
        if not self._enabled_check.isChecked():
            return None

        index = self._position_combo.currentIndex()
        if 0 <= index < len(_POSITION_LABELS):
            position = _POSITION_LABELS[index][1]
        else:
            position = PiPPosition.BOTTOM_RIGHT

        device = self._device_combo.currentText().strip()
        if device == "Камеры не найдены":
            device = ""

        return PiPSettings(
            enabled=True,
            device_name=device,
            position=position,
            size_percent=int(self._size_spin.value()),
        )
