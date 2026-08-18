"""
Представление настроек постобработки видеозаписей (Post-Recording Flow)
=======================================================================

Включает:
- переключатель активности конвейера постобработки;
- настройки перекодирования (формат, кодек);
- настройки компрессии (CRF);
- настройки обрезки тишины;
- настройки создания GIF-превью;
- выбор папки авто-копирования;
- открытие в проводнике и отправку webhook.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from config import PostProcessingSettings
from gui.accessibility import apply_accessible_metadata
from logger_config import get_module_logger

if TYPE_CHECKING:
    pass

logger = get_module_logger(__name__)


class PostProcessingView(QWidget):
    """Виджет настроек конвейера постобработки видеофайлов."""

    settings_changed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout(container)

        # Главный тумблер
        self._main_enabled_cb = QCheckBox(
            "Включить автоматическую постобработку после записи"
        )
        self._main_enabled_cb.toggled.connect(self._on_main_enabled_toggled)
        self._main_enabled_cb.toggled.connect(self._emit_change)
        layout.addWidget(self._main_enabled_cb)

        # Секция 1: Перекодирование / Конвертация
        self._transcode_group = QGroupBox("1. Перекодирование / Конвертация")
        self._transcode_group.setCheckable(True)
        self._transcode_group.setChecked(False)
        self._transcode_group.toggled.connect(self._emit_change)
        transcode_layout = QFormLayout(self._transcode_group)

        self._transcode_format_combo = QComboBox()
        self._transcode_format_combo.addItems(["webm", "mp4", "mkv"])
        self._transcode_format_combo.currentTextChanged.connect(
            self._emit_change
        )
        transcode_layout.addRow(
            "Целевой формат:", self._transcode_format_combo
        )

        self._transcode_codec_combo = QComboBox()
        self._transcode_codec_combo.addItems(
            ["libvpx-vp9", "libx264", "libx265", "libaom-av1"]
        )
        self._transcode_codec_combo.currentTextChanged.connect(
            self._emit_change
        )
        transcode_layout.addRow("Видеокодек:", self._transcode_codec_combo)
        layout.addWidget(self._transcode_group)

        # Секция 2: Сжатие (Компрессия)
        self._compress_group = QGroupBox("2. Сжатие видео (Компрессия)")
        self._compress_group.setCheckable(True)
        self._compress_group.setChecked(False)
        self._compress_group.toggled.connect(self._emit_change)
        compress_layout = QFormLayout(self._compress_group)

        self._compress_crf_spin = QSpinBox()
        self._compress_crf_spin.setRange(0, 51)
        self._compress_crf_spin.setValue(28)
        self._compress_crf_spin.setToolTip(
            "CRF фактор качества (18-23 высокое качество, 28 умеренное сжатие, >30 сильное сжатие)"
        )
        self._compress_crf_spin.valueChanged.connect(self._emit_change)
        compress_layout.addRow(
            "CRF (качество/размер):", self._compress_crf_spin
        )
        layout.addWidget(self._compress_group)

        # Секция 3: Обрезка тишины
        self._trim_silence_group = QGroupBox("3. Обрезка тишины в аудио")
        self._trim_silence_group.setCheckable(True)
        self._trim_silence_group.setChecked(False)
        self._trim_silence_group.toggled.connect(self._emit_change)
        trim_layout = QFormLayout(self._trim_silence_group)

        self._trim_threshold_spin = QSpinBox()
        self._trim_threshold_spin.setRange(-90, 0)
        self._trim_threshold_spin.setValue(-50)
        self._trim_threshold_spin.setSuffix(" dB")
        self._trim_threshold_spin.valueChanged.connect(self._emit_change)
        trim_layout.addRow("Порог тишины:", self._trim_threshold_spin)
        layout.addWidget(self._trim_silence_group)

        # Секция 4: Генерация GIF-превью
        self._gif_group = QGroupBox("4. Генерация GIF-превью")
        self._gif_group.setCheckable(True)
        self._gif_group.setChecked(False)
        self._gif_group.toggled.connect(self._emit_change)
        gif_layout = QFormLayout(self._gif_group)

        self._gif_duration_spin = QSpinBox()
        self._gif_duration_spin.setRange(1, 30)
        self._gif_duration_spin.setValue(5)
        self._gif_duration_spin.setSuffix(" сек")
        self._gif_duration_spin.valueChanged.connect(self._emit_change)
        gif_layout.addRow("Длительность превью:", self._gif_duration_spin)

        self._gif_fps_spin = QSpinBox()
        self._gif_fps_spin.setRange(1, 30)
        self._gif_fps_spin.setValue(10)
        self._gif_fps_spin.setSuffix(" FPS")
        self._gif_fps_spin.valueChanged.connect(self._emit_change)
        gif_layout.addRow("Частота кадров GIF:", self._gif_fps_spin)
        layout.addWidget(self._gif_group)

        # Секция 5: Копирование в папку
        self._copy_group = QGroupBox("5. Копирование в целевую папку")
        self._copy_group.setCheckable(True)
        self._copy_group.setChecked(False)
        self._copy_group.toggled.connect(self._emit_change)
        copy_layout = QHBoxLayout(self._copy_group)

        self._copy_path_input = QLineEdit()
        self._copy_path_input.setPlaceholderText(
            "Выберите папку для копирования..."
        )
        self._copy_path_input.textChanged.connect(self._emit_change)
        copy_layout.addWidget(self._copy_path_input)

        self._browse_copy_btn = QPushButton("Обзор...")
        self._browse_copy_btn.clicked.connect(self._on_browse_copy_folder)
        copy_layout.addWidget(self._browse_copy_btn)
        layout.addWidget(self._copy_group)

        # Секция 6: Проводник и Webhook
        integration_group = QGroupBox("6. Интеграции и действия")
        int_layout = QVBoxLayout(integration_group)

        self._open_explorer_cb = QCheckBox(
            "Открыть файл в проводнике после записи"
        )
        self._open_explorer_cb.toggled.connect(self._emit_change)
        int_layout.addWidget(self._open_explorer_cb)

        self._webhook_subgroup = QGroupBox("Отправка Webhook уведомления")
        self._webhook_subgroup.setCheckable(True)
        self._webhook_subgroup.setChecked(False)
        self._webhook_subgroup.toggled.connect(self._emit_change)
        wh_layout = QFormLayout(self._webhook_subgroup)

        self._webhook_url_input = QLineEdit()
        self._webhook_url_input.setPlaceholderText(
            "https://example.com/webhook"
        )
        self._webhook_url_input.textChanged.connect(self._emit_change)
        wh_layout.addRow("URL Webhook:", self._webhook_url_input)
        int_layout.addWidget(self._webhook_subgroup)

        layout.addWidget(integration_group)
        layout.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

        # Accessibility
        apply_accessible_metadata(
            self._main_enabled_cb,
            "Включить постобработку",
            "Включает автоматический конвейер постобработки после завершения записи",
        )

    def _on_main_enabled_toggled(self, checked: bool) -> None:
        """Включение/выключение доступности секций."""
        self._transcode_group.setEnabled(checked)
        self._compress_group.setEnabled(checked)
        self._trim_silence_group.setEnabled(checked)
        self._gif_group.setEnabled(checked)
        self._copy_group.setEnabled(checked)
        self._open_explorer_cb.setEnabled(checked)
        self._webhook_subgroup.setEnabled(checked)

    def _on_browse_copy_folder(self) -> None:
        """Диалог выбора папки для копирования."""
        folder = QFileDialog.getExistingDirectory(
            self, "Выберите папку для копирования записей"
        )
        if folder:
            self._copy_path_input.setText(folder)

    def _emit_change(self, *_args: Any) -> None:
        """Оповещение об изменении настроек."""
        self.settings_changed.emit()

    def get_settings(self) -> PostProcessingSettings:
        """Считывание настроек из полей формы."""
        return PostProcessingSettings(
            enabled=self._main_enabled_cb.isChecked(),
            transcode_enabled=self._transcode_group.isChecked(),
            transcode_format=self._transcode_format_combo.currentText(),
            transcode_codec=self._transcode_codec_combo.currentText(),
            compress_enabled=self._compress_group.isChecked(),
            compress_crf=self._compress_crf_spin.value(),
            trim_silence_enabled=self._trim_silence_group.isChecked(),
            trim_silence_threshold_db=self._trim_threshold_spin.value(),
            generate_gif_enabled=self._gif_group.isChecked(),
            gif_duration_seconds=self._gif_duration_spin.value(),
            gif_fps=self._gif_fps_spin.value(),
            copy_enabled=self._copy_group.isChecked(),
            copy_target_folder=self._copy_path_input.text().strip(),
            open_explorer_on_finish=self._open_explorer_cb.isChecked(),
            webhook_enabled=self._webhook_subgroup.isChecked(),
            webhook_url=self._webhook_url_input.text().strip() or None,
        )

    def set_settings(self, settings: PostProcessingSettings) -> None:
        """Заполнение формы переданными настройками."""
        self._main_enabled_cb.setChecked(settings.enabled)
        self._transcode_group.setChecked(settings.transcode_enabled)
        idx_fmt = self._transcode_format_combo.findText(
            settings.transcode_format
        )
        if idx_fmt >= 0:
            self._transcode_format_combo.setCurrentIndex(idx_fmt)
        idx_codec = self._transcode_codec_combo.findText(
            settings.transcode_codec
        )
        if idx_codec >= 0:
            self._transcode_codec_combo.setCurrentIndex(idx_codec)

        self._compress_group.setChecked(settings.compress_enabled)
        self._compress_crf_spin.setValue(settings.compress_crf)

        self._trim_silence_group.setChecked(settings.trim_silence_enabled)
        self._trim_threshold_spin.setValue(settings.trim_silence_threshold_db)

        self._gif_group.setChecked(settings.generate_gif_enabled)
        self._gif_duration_spin.setValue(settings.gif_duration_seconds)
        self._gif_fps_spin.setValue(settings.gif_fps)

        self._copy_group.setChecked(settings.copy_enabled)
        self._copy_path_input.setText(settings.copy_target_folder)

        self._open_explorer_cb.setChecked(settings.open_explorer_on_finish)

        self._webhook_subgroup.setChecked(settings.webhook_enabled)
        self._webhook_url_input.setText(settings.webhook_url or "")

        self._on_main_enabled_toggled(settings.enabled)
