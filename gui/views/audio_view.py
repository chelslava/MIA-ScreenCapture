"""
Представление настроек аудио
============================

Компонент UI для настройки источников аудио.
"""

import threading

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

from gui.accessibility import apply_accessible_metadata
from gui.models.recording_state import AudioType
from gui.styles.theme import Theme
from logger_config import get_module_logger
from recorder.utils import get_audio_devices

logger = get_module_logger(__name__)
_AUDIO_LOADING_TEXT = "Загрузка списка микрофонов..."
_AUDIO_EMPTY_TEXT = "Доступные устройства ввода не найдены."


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
    devices_load_completed = pyqtSignal(int, object, object)

    def __init__(self, parent: QWidget | None = None):
        """
        Инициализация представления.

        Args:
            parent: Родительский виджет
        """
        super().__init__(parent)
        self._device_request_id = 0
        self._pending_mic_device_index: int | None = None
        self._pending_mic_device_name = ""
        self._audio_devices_provider = get_audio_devices
        self.devices_load_completed.connect(self._on_devices_load_completed)
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
        self._mic_combo.setEnabled(False)

        self._refresh_mic_btn = QPushButton("Обновить")
        self._refresh_mic_btn.setMaximumWidth(80)
        self._refresh_mic_btn.clicked.connect(self._refresh_audio_devices)

        mic_layout.addWidget(QLabel("Устройство:"))
        mic_layout.addWidget(self._mic_combo)
        mic_layout.addWidget(self._refresh_mic_btn)
        group_layout.addLayout(mic_layout)

        self._mic_status_label = QLabel(_AUDIO_LOADING_TEXT)
        self._mic_status_label.setStyleSheet(Theme.secondary_text_style())
        group_layout.addWidget(self._mic_status_label)

        # Подключение сигналов
        self._button_group.buttonClicked.connect(self._on_button_clicked)
        self._mic_combo.currentIndexChanged.connect(
            self._on_mic_device_changed
        )

        self._apply_accessibility_metadata()
        self._refresh_audio_devices()
        layout.addWidget(group)

    def _apply_accessibility_metadata(self) -> None:
        """Назначение accessibility metadata для controls аудио."""
        apply_accessible_metadata(
            self._no_audio_radio,
            "Без аудио",
            "Отключает запись аудио.",
        )
        apply_accessible_metadata(
            self._mic_radio,
            "Только микрофон",
            "Включает запись только микрофона.",
        )
        apply_accessible_metadata(
            self._system_audio_radio,
            "Только системное аудио",
            "Включает запись только системного аудио.",
        )
        apply_accessible_metadata(
            self._both_audio_radio,
            "Микрофон и системное аудио",
            "Включает одновременную запись микрофона и системного аудио.",
        )
        apply_accessible_metadata(
            self._mic_combo,
            "Список микрофонов",
            "Позволяет выбрать входное аудиоустройство.",
            "Выберите микрофон из списка.",
        )
        apply_accessible_metadata(
            self._refresh_mic_btn,
            "Обновить список микрофонов",
            "Перечитывает доступные устройства ввода.",
            "Обновляет список микрофонов.",
        )
        apply_accessible_metadata(
            self._mic_status_label,
            "Статус загрузки микрофонов",
            "Показывает загрузку, ошибки и доступность входных устройств.",
        )

    def _refresh_audio_devices(self) -> None:
        """Обновление списка аудиоустройств."""
        self._device_request_id += 1
        request_id = self._device_request_id
        self._set_devices_loading_state()
        threading.Thread(
            target=self._load_audio_devices_worker,
            args=(request_id,),
            daemon=True,
        ).start()

    def _load_audio_devices_worker(self, request_id: int) -> None:
        """Загрузить список аудиоустройств в фоне."""
        try:
            devices = self._audio_devices_provider()
            self.devices_load_completed.emit(request_id, devices, None)
        except Exception as error:
            self.devices_load_completed.emit(request_id, None, str(error))

    def _on_devices_load_completed(
        self,
        request_id: int,
        devices: object,
        error: object,
    ) -> None:
        """Применить результат фоновой загрузки аудиоустройств."""
        if request_id != self._device_request_id:
            return

        if error is not None:
            self._set_devices_error_state(str(error))
            return

        device_map = devices if isinstance(devices, dict) else {}
        input_devices = device_map.get("input", [])
        selected_index = self.get_mic_device_index()
        selected_name = self.get_mic_device_name()

        self._mic_combo.clear()
        for dev in input_devices:
            if isinstance(dev, dict):
                self._mic_combo.addItem(dev["name"], dev["id"])

        if not input_devices:
            self._set_devices_empty_state()
            return

        self._set_devices_ready_state(len(input_devices))
        restored = self._restore_mic_selection(
            selected_index,
            selected_name,
        )
        if not restored:
            self._mic_combo.setCurrentIndex(0)

    def _restore_mic_selection(
        self,
        device_index: int | None,
        device_name: str,
    ) -> bool:
        """Восстановить выбранный микрофон после refresh."""
        if device_index is not None:
            for combo_index in range(self._mic_combo.count()):
                if self._mic_combo.itemData(combo_index) == device_index:
                    self._mic_combo.setCurrentIndex(combo_index)
                    self._pending_mic_device_index = None
                    self._pending_mic_device_name = ""
                    return True

        target_name = device_name or self._pending_mic_device_name
        if target_name:
            index = self._mic_combo.findText(target_name)
            if index >= 0:
                self._mic_combo.setCurrentIndex(index)
                self._pending_mic_device_index = None
                self._pending_mic_device_name = ""
                return True

        return False

    def _set_devices_loading_state(self) -> None:
        """Показать состояние загрузки аудиоустройств."""
        self._mic_status_label.setText(_AUDIO_LOADING_TEXT)
        self._mic_status_label.setStyleSheet(Theme.secondary_text_style())
        self._mic_combo.setEnabled(False)

    def _set_devices_ready_state(self, count: int) -> None:
        """Показать успешную загрузку списка микрофонов."""
        self._mic_status_label.setText(f"Доступно микрофонов: {count}")
        self._mic_status_label.setStyleSheet(Theme.secondary_text_style())
        self._mic_combo.setEnabled(True)

    def _set_devices_empty_state(self) -> None:
        """Показать отсутствие микрофонов."""
        self._mic_status_label.setText(_AUDIO_EMPTY_TEXT)
        self._mic_status_label.setStyleSheet(
            f"color: {Theme.COLORS['warning']};"
        )
        self._mic_combo.setEnabled(False)

    def _set_devices_error_state(self, message: str) -> None:
        """Показать ошибку загрузки микрофонов."""
        logger.error("Не удалось загрузить аудиоустройства: %s", message)
        self._mic_status_label.setText(
            f"Не удалось загрузить устройства: {message}"
        )
        self._mic_status_label.setStyleSheet(
            f"color: {Theme.COLORS['danger']};"
        )
        self._mic_combo.setEnabled(False)

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
            return self._pending_mic_device_index
        try:
            return int(data)
        except (TypeError, ValueError):
            logger.warning(f"Некорректный индекс устройства: {data}")
            return self._pending_mic_device_index

    def get_mic_device_name(self) -> str:
        """
        Получить имя выбранного устройства микрофона.

        Returns:
            Имя устройства
        """
        current_name = self._mic_combo.currentText()
        if current_name:
            return str(current_name)
        return str(self._pending_mic_device_name)

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
        self._pending_mic_device_index = index
        for i in range(self._mic_combo.count()):
            if self._mic_combo.itemData(i) == index:
                self._mic_combo.setCurrentIndex(i)
                self._pending_mic_device_index = None
                break

    def set_mic_device_name(self, name: str) -> None:
        """
        Установить устройство микрофона по имени.

        Args:
            name: Имя устройства
        """
        self._pending_mic_device_name = name
        index = self._mic_combo.findText(name)
        if index >= 0:
            self._mic_combo.setCurrentIndex(index)
            self._pending_mic_device_name = ""
