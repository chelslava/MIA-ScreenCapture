"""
Представление настроек аудио
============================

Компонент UI для настройки источников аудио.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from gui.models.recording_state import AudioType
from logger_config import get_module_logger
from recorder.utils import get_audio_devices

logger = get_module_logger(__name__)


class AudioView(QWidget):
    """
    Представление для настройки аудио.

    Содержит:
    - Радиокнопки для выбора типа источника
    - Селектор устройств микрофона
    """

    # Сигналы
    audio_type_changed = pyqtSignal(AudioType)
    mic_device_changed = pyqtSignal(int)  # device index

    def __init__(self, parent: QWidget | None = None):
        """
        Инициализация представления.

        Args:
            parent: Родительский виджет
        """
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Настройка пользовательского интерфейса."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Настройки аудио")
        group_layout = QVBoxLayout(group)

        # Радиокнопки
        self._button_group = QButtonGroup()

        self._no_audio_radio = QRadioButton("Без аудио")
        self._no_audio_radio.setChecked(True)
        self._button_group.addButton(self._no_audio_radio, 0)
        group_layout.addWidget(self._no_audio_radio)

        self._mic_radio = QRadioButton("Микрофон")
        self._button_group.addButton(self._mic_radio, 1)
        group_layout.addWidget(self._mic_radio)

        self._system_audio_radio = QRadioButton("Системное аудио")
        self._button_group.addButton(self._system_audio_radio, 2)
        group_layout.addWidget(self._system_audio_radio)

        self._both_audio_radio = QRadioButton("Микрофон + Системное")
        self._button_group.addButton(self._both_audio_radio, 3)
        group_layout.addWidget(self._both_audio_radio)

        # Селектор микрофона
        mic_layout = QHBoxLayout()
        self._mic_combo = QComboBox()
        self._refresh_audio_devices()

        refresh_mic_btn = QPushButton("Обновить")
        refresh_mic_btn.setMaximumWidth(80)
        refresh_mic_btn.clicked.connect(self._refresh_audio_devices)

        mic_layout.addWidget(QLabel("Устройство:"))
        mic_layout.addWidget(self._mic_combo)
        mic_layout.addWidget(refresh_mic_btn)
        group_layout.addLayout(mic_layout)

        # Подключение сигналов
        self._button_group.buttonClicked.connect(self._on_button_clicked)
        self._mic_combo.currentIndexChanged.connect(
            self._on_mic_device_changed
        )

        layout.addWidget(group)

    def _refresh_audio_devices(self) -> None:
        """Обновление списка аудиоустройств."""
        self._mic_combo.clear()
        devices = get_audio_devices()

        for dev in devices.get("input", []):
            self._mic_combo.addItem(dev["name"], dev["id"])

    def _on_button_clicked(self, button: QRadioButton) -> None:
        """Обработка клика по радиокнопке."""
        # Определение типа аудио
        if button == self._no_audio_radio:
            audio_type = AudioType.NONE
        elif button == self._mic_radio:
            audio_type = AudioType.MIC
        elif button == self._system_audio_radio:
            audio_type = AudioType.SYSTEM
        else:
            audio_type = AudioType.BOTH

        self.audio_type_changed.emit(audio_type)

    def _on_mic_device_changed(self, index: int) -> None:
        """Обработка выбора устройства микрофона."""
        device_id = self._mic_combo.currentData()
        if device_id is not None:
            self.mic_device_changed.emit(device_id)

    def get_audio_type(self) -> AudioType:
        """
        Получить выбранный тип источника аудио.

        Returns:
            Тип источника аудио
        """
        if self._mic_radio.isChecked():
            return AudioType.MIC
        elif self._system_audio_radio.isChecked():
            return AudioType.SYSTEM
        elif self._both_audio_radio.isChecked():
            return AudioType.BOTH
        else:
            return AudioType.NONE

    def get_mic_device_index(self) -> int | None:
        """
        Получить индекс выбранного устройства микрофона.

        Returns:
            Индекс устройства или None
        """
        data = self._mic_combo.currentData()
        if data is None:
            return None
        try:
            return int(data)
        except (TypeError, ValueError):
            logger.warning(f"Некорректный индекс устройства: {data}")
            return None

    def get_mic_device_name(self) -> str:
        """
        Получить имя выбранного устройства микрофона.

        Returns:
            Имя устройства
        """
        return self._mic_combo.currentText()

    def set_audio_type(self, audio_type: AudioType) -> None:
        """
        Установить тип источника аудио.

        Args:
            audio_type: Тип источника аудио
        """
        if audio_type == AudioType.NONE:
            self._no_audio_radio.setChecked(True)
        elif audio_type == AudioType.MIC:
            self._mic_radio.setChecked(True)
        elif audio_type == AudioType.SYSTEM:
            self._system_audio_radio.setChecked(True)
        elif audio_type == AudioType.BOTH:
            self._both_audio_radio.setChecked(True)

    def set_mic_device_index(self, index: int) -> None:
        """
        Установить индекс устройства микрофона.

        Args:
            index: Индекс устройства
        """
        for i in range(self._mic_combo.count()):
            if self._mic_combo.itemData(i) == index:
                self._mic_combo.setCurrentIndex(i)
                break

    def set_mic_device_name(self, name: str) -> None:
        """
        Установить устройство микрофона по имени.

        Args:
            name: Имя устройства
        """
        index = self._mic_combo.findText(name)
        if index >= 0:
            self._mic_combo.setCurrentIndex(index)
