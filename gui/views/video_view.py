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
from gui.models.video_codecs import (
    codec_id_from_display_name,
    display_name_from_codec_id,
    get_available_codec_display_names,
)
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
    - Выбор preset (скорость кодирования)
    """

    # Сигналы
    fps_changed = pyqtSignal(int)
    codec_changed = pyqtSignal(str)
    bitrate_changed = pyqtSignal(str)
    format_changed = pyqtSignal(str)
    preset_changed = pyqtSignal(str)
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
        self._codec_combo.addItems(get_available_codec_display_names())
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

        # Preset (скорость кодирования)
        group_layout.addWidget(QLabel("Скорость кодирования:"), 2, 0)
        self._preset_combo = QComboBox()
        self._preset_combo.addItems(
            [
                "ultrafast (максимальная скорость)",
                "superfast",
                "veryfast",
                "faster",
                "fast",
                "medium (по умолчанию)",
                "slow",
                "slower",
                "veryslow (максимальное качество)",
            ]
        )
        self._preset_combo.setCurrentIndex(5)  # medium
        group_layout.addWidget(self._preset_combo, 2, 1, 1, 3)

        # Подключение сигналов
        self._fps_spin.valueChanged.connect(self._on_fps_changed)
        self._codec_combo.currentTextChanged.connect(self._on_codec_changed)
        self._bitrate_combo.currentTextChanged.connect(
            self._on_bitrate_changed
        )
        self._format_combo.currentTextChanged.connect(self._on_format_changed)
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)

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

    def _on_preset_changed(self, index: int) -> None:
        """Обработка изменения preset."""
        preset = self._get_preset_value()
        self.preset_changed.emit(preset)
        self._emit_settings()

    def _get_preset_value(self) -> str:
        """Получение значения preset из выпадающего списка."""
        presets = [
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
        ]
        index = self._preset_combo.currentIndex()
        return presets[index] if 0 <= index < len(presets) else "medium"

    def _emit_settings(self) -> None:
        """Отправка сигнала с текущими настройками."""
        settings = VideoSettings(
            fps=self._fps_spin.value(),
            codec=self.get_codec(),
            bitrate=self._bitrate_combo.currentText(),
            format=self._format_combo.currentText(),
            preset=self._get_preset_value(),
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
        Получить идентификатор выбранного кодека.

        Returns:
            Идентификатор кодека FFmpeg
        """
        current_text: str = self._codec_combo.currentText()
        codec_id: str = codec_id_from_display_name(current_text)
        return codec_id

    def get_bitrate(self) -> str:
        """
        Получить выбранный битрейт.

        Returns:
            Значение битрейта
        """
        bitrate: str = self._bitrate_combo.currentText()
        return bitrate

    def get_format(self) -> str:
        """
        Получить выбранный формат.

        Returns:
            Формат файла
        """
        video_format: str = self._format_combo.currentText()
        return video_format

    def get_preset(self) -> str:
        """
        Получить выбранный preset.

        Returns:
            Значение preset
        """
        return self._get_preset_value()

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
            preset=self.get_preset(),
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
        Установить кодек по его идентификатору.

        Args:
            codec: Идентификатор кодека FFmpeg
        """
        text: str = display_name_from_codec_id(codec)
        index = self._codec_combo.findText(text)
        if index >= 0:
            self._codec_combo.setCurrentIndex(index)

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

    def set_preset(self, preset: str) -> None:
        """
        Установить preset.

        Args:
            preset: Значение preset
        """
        presets = [
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
        ]
        if preset in presets:
            self._preset_combo.setCurrentIndex(presets.index(preset))

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
        if hasattr(settings, "preset"):
            self.set_preset(settings.preset)
