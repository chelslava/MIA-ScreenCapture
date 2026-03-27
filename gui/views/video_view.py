"""
Представление настроек видео
============================

Компонент UI для настройки параметров видео.
"""


from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gui.models.recording_state import VideoSettings
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class VideoView(QWidget):
    """
    Представление для настройки видео.

    Содержит:
    - Выбор FPS
    - Выбор кодека
    - Выбор битрейта
    - Выбор формата
    """

    # Сигналы
    fps_changed = pyqtSignal(int)
    codec_changed = pyqtSignal(str)
    bitrate_changed = pyqtSignal(str)
    format_changed = pyqtSignal(str)
    settings_changed = pyqtSignal(VideoSettings)

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

        group = QGroupBox("Настройки видео")
        group_layout = QGridLayout(group)

        # FPS
        group_layout.addWidget(QLabel("FPS:"), 0, 0)
        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(1, 120)
        self._fps_spin.setValue(30)
        group_layout.addWidget(self._fps_spin, 0, 1)

        # Кодек
        group_layout.addWidget(QLabel("Кодек:"), 0, 2)
        self._codec_combo = QComboBox()
        self._codec_combo.addItems(["libx264", "mp4v", "h264", "xvid"])
        group_layout.addWidget(self._codec_combo, 0, 3)

        # Битрейт
        group_layout.addWidget(QLabel("Битрейт:"), 1, 0)
        self._bitrate_combo = QComboBox()
        self._bitrate_combo.setEditable(True)
        self._bitrate_combo.addItems(["1M", "2M", "4M", "8M", "10M"])
        self._bitrate_combo.setCurrentText("2M")
        group_layout.addWidget(self._bitrate_combo, 1, 1)

        # Формат
        group_layout.addWidget(QLabel("Формат:"), 1, 2)
        self._format_combo = QComboBox()
        self._format_combo.addItems(["mp4", "avi", "mkv"])
        group_layout.addWidget(self._format_combo, 1, 3)

        # Подключение сигналов
        self._fps_spin.valueChanged.connect(self._on_fps_changed)
        self._codec_combo.currentTextChanged.connect(self._on_codec_changed)
        self._bitrate_combo.currentTextChanged.connect(
            self._on_bitrate_changed
        )
        self._format_combo.currentTextChanged.connect(self._on_format_changed)

        layout.addWidget(group)

    def _on_fps_changed(self, value: int) -> None:
        """Обработка изменения FPS."""
        self.fps_changed.emit(value)
        self._emit_settings()

    def _on_codec_changed(self, value: str) -> None:
        """Обработка изменения кодека."""
        self.codec_changed.emit(value)
        self._emit_settings()

    def _on_bitrate_changed(self, value: str) -> None:
        """Обработка изменения битрейта."""
        self.bitrate_changed.emit(value)
        self._emit_settings()

    def _on_format_changed(self, value: str) -> None:
        """Обработка изменения формата."""
        self.format_changed.emit(value)
        self._emit_settings()

    def _emit_settings(self) -> None:
        """Отправка сигнала с текущими настройками."""
        settings = VideoSettings(
            fps=self._fps_spin.value(),
            codec=self._codec_combo.currentText(),
            bitrate=self._bitrate_combo.currentText(),
            format=self._format_combo.currentText(),
        )
        self.settings_changed.emit(settings)

    def get_fps(self) -> int:
        """
        Получить выбранное значение FPS.

        Returns:
            FPS
        """
        return self._fps_spin.value()

    def get_codec(self) -> str:
        """
        Получить выбранный кодек.

        Returns:
            Название кодека
        """
        return self._codec_combo.currentText()

    def get_bitrate(self) -> str:
        """
        Получить выбранный битрейт.

        Returns:
            Значение битрейта
        """
        return self._bitrate_combo.currentText()

    def get_format(self) -> str:
        """
        Получить выбранный формат.

        Returns:
            Формат файла
        """
        return self._format_combo.currentText()

    def get_settings(self) -> VideoSettings:
        """
        Получить текущие настройки видео.

        Returns:
            Объект VideoSettings
        """
        return VideoSettings(
            fps=self.get_fps(),
            codec=self.get_codec(),
            bitrate=self.get_bitrate(),
            format=self.get_format(),
        )

    def set_fps(self, fps: int) -> None:
        """
        Установить значение FPS.

        Args:
            fps: FPS
        """
        self._fps_spin.setValue(fps)

    def set_codec(self, codec: str) -> None:
        """
        Установить кодек.

        Args:
            codec: Название кодека
        """
        index = self._codec_combo.findText(codec)
        if index >= 0:
            self._codec_combo.setCurrentIndex(index)
        else:
            self._codec_combo.setEditText(codec)

    def set_bitrate(self, bitrate: str) -> None:
        """
        Установить битрейт.

        Args:
            bitrate: Значение битрейта
        """
        index = self._bitrate_combo.findText(bitrate)
        if index >= 0:
            self._bitrate_combo.setCurrentIndex(index)
        else:
            self._bitrate_combo.setEditText(bitrate)

    def set_format(self, format: str) -> None:
        """
        Установить формат.

        Args:
            format: Формат файла
        """
        index = self._format_combo.findText(format)
        if index >= 0:
            self._format_combo.setCurrentIndex(index)

    def set_settings(self, settings: VideoSettings) -> None:
        """
        Установить все настройки видео.

        Args:
            settings: Объект VideoSettings
        """
        self.set_fps(settings.fps)
        self.set_codec(settings.codec)
        self.set_bitrate(settings.bitrate)
        self.set_format(settings.format)
