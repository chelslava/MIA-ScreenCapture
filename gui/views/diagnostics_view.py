"""
Модуль диагностики системы
==========================

Вкладка для проверки состояния системы и устранения неполадок.
"""

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from logger_config import get_module_logger
from recorder.utils import check_ffmpeg, get_audio_devices

logger = get_module_logger(__name__)


class DiagnosticsView(QWidget):
    """Виджет диагностики системы."""

    recheck_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Заголовок
        title = QLabel("Диагностика системы")
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title)

        # Scroll area для проверок
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self._checks_widget = QWidget()
        self._checks_layout = QVBoxLayout(self._checks_widget)
        self._checks_layout.setSpacing(10)

        # Группы проверок
        self._ffmpeg_group = self._create_check_group(
            "FFmpeg", "Проверка наличия FFmpeg в PATH"
        )
        self._checks_layout.addWidget(self._ffmpeg_group)

        self._audio_group = self._create_check_group(
            "Аудиоустройства", "Проверка доступных устройств записи"
        )
        self._checks_layout.addWidget(self._audio_group)

        self._api_group = self._create_check_group(
            "API сервер", "Проверка готовности API сервера"
        )
        self._checks_layout.addWidget(self._api_group)

        self._output_group = self._create_check_group(
            "Папка вывода", "Проверка прав на запись в папку вывода"
        )
        self._checks_layout.addWidget(self._output_group)

        self._checks_layout.addStretch()
        scroll.setWidget(self._checks_widget)
        layout.addWidget(scroll)

        # Кнопки
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        self._recheck_btn = QPushButton("Проверить снова")
        self._recheck_btn.clicked.connect(self.recheck_requested)
        buttons_layout.addWidget(self._recheck_btn)

        layout.addLayout(buttons_layout)

    def _create_check_group(self, title: str, description: str) -> QGroupBox:
        group = QGroupBox(title)
        group_layout = QVBoxLayout(group)

        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: gray; font-size: 11px;")
        group_layout.addWidget(desc_label)

        status_layout = QHBoxLayout()
        self._status_label = QLabel("Не проверено")
        self._status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(self._status_label)
        status_layout.addStretch()

        self._fix_btn = QPushButton("Исправить")
        self._fix_btn.setVisible(False)
        status_layout.addWidget(self._fix_btn)

        group_layout.addLayout(status_layout)
        return group

    def run_checks(
        self,
        api_enabled: bool = False,
        output_path: str = "",
    ) -> dict[str, bool]:
        """
        Запуск всех проверок.

        Args:
            api_enabled: Включён ли API сервер
            output_path: Путь к папке вывода

        Returns:
            Словарь с результатами проверок
        """
        results: dict[str, bool] = {}

        # Проверка FFmpeg
        ffmpeg_ok = self._check_ffmpeg()
        results["ffmpeg"] = ffmpeg_ok
        self._update_group_status(
            self._ffmpeg_group,
            ffmpeg_ok,
            "Найден" if ffmpeg_ok else "Не найден",
        )

        # Проверка аудиоустройств
        audio_ok, audio_count = self._check_audio_devices()
        results["audio"] = audio_ok
        self._update_group_status(
            self._audio_group,
            audio_ok,
            f"Найдено устройств: {audio_count}"
            if audio_ok
            else "Нет устройств",
        )

        # Проверка API
        results["api"] = api_enabled
        self._update_group_status(
            self._api_group,
            api_enabled,
            "Запущен" if api_enabled else "Не запущен",
        )

        # Проверка папки вывода
        output_ok = self._check_output_path(output_path)
        results["output"] = output_ok
        self._update_group_status(
            self._output_group,
            output_ok,
            "Доступна" if output_ok else "Недоступна или не указана",
        )

        return results

    def _check_ffmpeg(self) -> bool:
        """Проверка наличия FFmpeg."""
        try:
            return check_ffmpeg()
        except Exception as e:
            logger.error(f"Ошибка проверки FFmpeg: {e}")
            return False

    def _check_audio_devices(self) -> tuple[bool, int]:
        """Проверка аудиоустройств."""
        try:
            devices = get_audio_devices()
            count = len(devices) if devices else 0
            return count > 0, count
        except Exception as e:
            logger.error(f"Ошибка проверки аудиоустройств: {e}")
            return False, 0

    def _check_output_path(self, path: str) -> bool:
        """Проверка папки вывода."""
        if not path:
            return False
        try:
            from pathlib import Path

            p = Path(path)
            if not p.exists():
                p.mkdir(parents=True, exist_ok=True)
            return p.is_dir() and os.access(path, os.W_OK)
        except Exception as e:
            logger.error(f"Ошибка проверки папки вывода: {e}")
            return False

    def _update_group_status(
        self, group: QGroupBox, ok: bool, message: str
    ) -> None:
        """Обновление статуса группы."""
        status_label = group.findChild(QLabel, "")
        for child in group.findChildren(QLabel):
            if child.text() not in ("", group.title()):
                if "color: gray" not in child.styleSheet():
                    status_label = child
                    break

        if status_label:
            status_label.setText(message)
            color = "green" if ok else "red"
            status_label.setStyleSheet(f"font-weight: bold; color: {color};")

        # Показать кнопку исправления если есть проблема
        fix_btn = group.findChild(QPushButton)
        if fix_btn:
            fix_btn.setVisible(not ok)
