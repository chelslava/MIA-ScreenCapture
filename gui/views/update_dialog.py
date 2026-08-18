"""
Диалоговое окно уведомления о доступном обновлении и установки (#128).
====================================================================
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from core.updater.types import DownloadProgress, ReleaseInfo
from logger_config import get_module_logger
from version import get_version

if TYPE_CHECKING:
    from core.updater.updater import AppUpdater

logger = get_module_logger(__name__)


class UpdateDialog(QDialog):
    """Диалог с информацией о доступном обновлении и процессом скачивания."""

    download_requested = pyqtSignal(object)  # ReleaseInfo
    install_requested = pyqtSignal()
    ignore_requested = pyqtSignal(str)  # version

    def __init__(
        self,
        release_info: ReleaseInfo,
        updater: AppUpdater | None = None,
        parent: Any = None,
    ) -> None:
        super().__init__(parent)
        self.release_info = release_info
        self._updater = updater

        self.setWindowTitle("Доступно обновление MIA-ScreenCapture")
        self.setMinimumSize(520, 380)
        self.resize(560, 420)

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Заголовок
        cur_v = get_version()
        header_text = (
            f"<h2>Доступна новая версия: {self.release_info.name or self.release_info.version}</h2>"
            f"<p style='color: #888;'>Текущая версия: <b>{cur_v}</b> | Новая версия: <b>{self.release_info.version}</b></p>"
        )
        self._header_label = QLabel(header_text)
        self._header_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self._header_label)

        # Release Notes
        notes_label = QLabel("Что нового:")
        notes_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(notes_label)

        self._notes_browser = QTextBrowser()
        self._notes_browser.setOpenExternalLinks(True)
        if self.release_info.release_notes:
            self._notes_browser.setMarkdown(self.release_info.release_notes)
        else:
            self._notes_browser.setPlainText("Описание релиза отсутствует.")
        layout.addWidget(self._notes_browser, 1)

        # Размер и тип
        size_mb = self.release_info.size_bytes / (1024 * 1024)
        info_text = f"Размер загрузки: {size_mb:.1f} МБ"
        if self.release_info.is_delta:
            info_text += " (дельта-патч)"
        self._info_label = QLabel(info_text)
        self._info_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self._info_label)

        # Прогресс-бар
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #007acc; font-weight: bold;")
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)

        # Кнопки действий
        btn_layout = QHBoxLayout()

        self._ignore_btn = QPushButton("Пропустить эту версию")
        self._ignore_btn.clicked.connect(self._on_ignore_clicked)
        btn_layout.addWidget(self._ignore_btn)

        btn_layout.addStretch(1)

        self._later_btn = QPushButton("Напомнить позже")
        self._later_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._later_btn)

        self._action_btn = QPushButton("Скачать и установить")
        self._action_btn.setStyleSheet(
            "background-color: #007acc; color: white; font-weight: bold; padding: 6px 14px;"
        )
        self._action_btn.clicked.connect(self._on_action_clicked)
        btn_layout.addWidget(self._action_btn)

        layout.addLayout(btn_layout)

    def set_progress(self, progress: DownloadProgress) -> None:
        """Обновляет статус скачивания в UI."""
        self._progress_bar.setVisible(True)
        self._status_label.setVisible(True)
        self._progress_bar.setValue(int(progress.percent))
        speed_kb = progress.speed_bytes_per_sec / 1024
        self._status_label.setText(
            f"Скачивание... {progress.percent:.1f}% ({speed_kb:.0f} КБ/с)"
        )

    def set_download_completed(self) -> None:
        """Переводит диалог в состояние готовности к установке."""
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(100)
        self._status_label.setVisible(True)
        self._status_label.setText("Обновление готово к установке!")
        self._action_btn.setEnabled(True)
        self._action_btn.setText("Перезапустить и обновить")

    def _on_action_clicked(self) -> None:
        if self._action_btn.text() == "Перезапустить и обновить":
            self.install_requested.emit()
            if self._updater:
                self._updater.apply_update()
            self.accept()
        else:
            self._action_btn.setEnabled(False)
            self._ignore_btn.setEnabled(False)
            self._progress_bar.setVisible(True)
            self._status_label.setVisible(True)
            self._status_label.setText("Подготовка к скачиванию...")
            self.download_requested.emit(self.release_info)
            if self._updater:
                self._updater.download_update_async(
                    release=self.release_info,
                    callback=lambda success: (
                        self.set_download_completed() if success else None
                    ),
                )

    def _on_ignore_clicked(self) -> None:
        version = self.release_info.version
        self.ignore_requested.emit(version)
        if self._updater:
            self._updater.ignore_version(version)
        self.reject()
