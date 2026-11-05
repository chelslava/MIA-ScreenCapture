"""Мастер первого запуска MIA-ScreenCapture (#172).

Три шага: приветствие → сводка текущих настроек → проверка готовности
(переиспользует `core.readiness`). Показывается однократно (флаг
`onboarding_completed` в конфиге); повторный запуск — из меню «Справка».

Мастер не меняет настройки сам — только показывает сводку и результат
preflight-проверки, снижая порог первого запуска.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtWidgets import (
    QLabel,
    QWizard,
    QWizardPage,
)

from core.readiness import ReadinessSnapshot, build_readiness_checks
from core.recording_state import AudioSettings, CaptureSettings
from logger_config import get_module_logger

logger = get_module_logger(__name__)

_WIZARD_TITLE = "Добро пожаловать в MIA-ScreenCapture"
_WELCOME_TEXT = (
    "Этот мастер поможет подготовиться к первой записи.\n\n"
    "Дальше вы увидите:\n"
    "  1. Сводку текущих настроек захвата и аудио.\n"
    "  2. Результат проверки готовности (FFmpeg, устройства, диск).\n\n"
    "Все настройки можно изменить позже на соответствующих страницах."
)
_COMPLETE_TEXT = (
    "Готово! Запись запускается кнопкой на главной странице "
    "или глобальным хоткеем Ctrl+Alt+T."
)


class OnboardingWizard(QWizard):
    """Мастер первого запуска: сводка настроек + проверка готовности (#172)."""

    def __init__(
        self,
        settings_summary: dict[str, str],
        readiness_snapshot: Any,
        parent: Any = None,
    ) -> None:
        """Инициализировать мастер.

        Args:
            settings_summary: Отображаемые пары «настройка → значение».
            readiness_snapshot: Результат `RecordingReadinessService.evaluate`.
            parent: Родительское окно.
        """
        super().__init__(parent)
        self.setWindowTitle(_WIZARD_TITLE)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage, True)

        self.addPage(self._build_welcome_page())
        self.addPage(self._build_settings_page(settings_summary))
        self.addPage(self._build_readiness_page(readiness_snapshot))
        logger.debug("Мастер первого запуска создан")

    def _build_welcome_page(self) -> QWizardPage:
        """Шаг 1: приветствие."""
        page = QWizardPage()
        page.setTitle("Приветствие")
        from PyQt6.QtWidgets import QVBoxLayout

        vbox = QVBoxLayout(page)
        label = QLabel(_WELCOME_TEXT)
        if hasattr(label, "setWordWrap"):
            label.setWordWrap(True)
        vbox.addWidget(label)
        return page

    def _build_settings_page(
        self, settings_summary: dict[str, str]
    ) -> QWizardPage:
        """Шаг 2: сводка текущих настроек."""
        page = QWizardPage()
        page.setTitle("Ваши текущие настройки")
        from PyQt6.QtWidgets import QVBoxLayout

        vbox = QVBoxLayout(page)
        for name, value in settings_summary.items():
            row = QLabel(f"<b>{name}:</b> {value}")
            if hasattr(row, "setWordWrap"):
                row.setWordWrap(True)
            vbox.addWidget(row)
        vbox.addStretch(1)
        return page

    def _build_readiness_page(self, snapshot: Any) -> QWizardPage:
        """Шаг 3: результат проверки готовности."""
        page = QWizardPage()
        page.setTitle("Проверка готовности")
        from PyQt6.QtWidgets import QVBoxLayout

        vbox = QVBoxLayout(page)

        if isinstance(snapshot, ReadinessSnapshot):
            checks = build_readiness_checks(
                snapshot, CaptureSettings(), AudioSettings()
            )
            for check in checks:
                icon = "✅" if check.status == "ready" else "⚠️"
                vbox.addWidget(
                    QLabel(f"{icon} {check.title}: {check.message}")
                )
            if snapshot.blocking_issues:
                warn = QLabel(
                    "Есть блокирующие проблемы — запустите диагностику "
                    "на главной странице после завершения мастера."
                )
                if hasattr(warn, "setWordWrap"):
                    warn.setWordWrap(True)
                vbox.addWidget(warn)
        else:
            vbox.addWidget(QLabel("Проверка готовности недоступна."))

        done = QLabel(_COMPLETE_TEXT)
        if hasattr(done, "setWordWrap"):
            done.setWordWrap(True)
        vbox.addWidget(done)
        vbox.addStretch(1)
        return page
