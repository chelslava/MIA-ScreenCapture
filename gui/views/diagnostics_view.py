"""
Модуль диагностики системы
==========================

Вкладка для проверки состояния системы и устранения неполадок.
"""

from pathlib import Path

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

from core.readiness import (
    ReadinessCheck,
    ReadinessSnapshot,
    RecordingReadinessService,
    build_readiness_checks,
)
from core.recording_state import AudioSettings, CaptureSettings
from gui.accessibility import apply_accessible_metadata
from gui.styles.theme import Theme
from gui.views.loading_overlay import LoadingOverlay
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class DiagnosticsView(QWidget):
    """Виджет диагностики системы."""

    recheck_requested = pyqtSignal()
    fix_requested = pyqtSignal(str)
    logs_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._output_path = ""
        self._readiness_service = RecordingReadinessService()
        self._loading = LoadingOverlay(self)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Заголовок
        title = QLabel("Диагностика системы")
        title.setStyleSheet(Theme.title_style())
        layout.addWidget(title)

        # Scroll area для проверок
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self._checks_widget = QWidget()
        self._checks_layout = QVBoxLayout(self._checks_widget)
        self._checks_layout.setSpacing(Theme.SPACING)

        # Группы проверок
        self._ffmpeg_group = self._create_check_group(
            "FFmpeg", "Проверка наличия FFmpeg в PATH"
        )
        self._checks_layout.addWidget(self._ffmpeg_group)

        self._audio_group = self._create_check_group(
            "Аудиоустройства", "Проверка доступных устройств записи"
        )
        self._checks_layout.addWidget(self._audio_group)

        self._capture_group = self._create_check_group(
            "Окно захвата", "Проверка доступности выбранного окна"
        )
        self._checks_layout.addWidget(self._capture_group)

        self._api_group = self._create_check_group(
            "API сервер", "Проверка готовности API сервера"
        )
        self._checks_layout.addWidget(self._api_group)

        self._recovery_group = self._create_check_group(
            "Восстановление FFmpeg",
            "Количество успешных восстановлений после сбоев",
        )
        self._checks_layout.addWidget(self._recovery_group)

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
        self._recheck_btn.clicked.connect(self._on_recheck_clicked)
        buttons_layout.addWidget(self._recheck_btn)

        self._logs_btn = QPushButton("Открыть логи")
        self._logs_btn.clicked.connect(self._on_open_logs)
        buttons_layout.addWidget(self._logs_btn)

        layout.addLayout(buttons_layout)
        self._apply_accessibility_metadata()

    def _apply_accessibility_metadata(self) -> None:
        """Назначение accessibility metadata для controls диагностики."""
        apply_accessible_metadata(
            self._recheck_btn,
            "Повторить диагностику",
            "Перезапускает проверку готовности среды и зависимостей.",
            "Повторно запускает диагностику.",
        )
        apply_accessible_metadata(
            self._logs_btn,
            "Открыть логи приложения",
            "Открывает директорию с логами приложения.",
            "Открывает логи приложения.",
        )

    def _on_recheck_clicked(self) -> None:
        """Обработка нажатия кнопки проверки."""
        logger.info("Кнопка 'Проверить снова' нажата")
        self.recheck_requested.emit()

    def _on_open_logs(self) -> None:
        """Запросить открытие папки с логами у host-окна."""
        logger.info("Запрос на открытие папки логов")
        self.logs_requested.emit()

    def _create_check_group(self, title: str, description: str) -> QGroupBox:
        group = QGroupBox(title)
        group_layout = QVBoxLayout(group)

        desc_label = QLabel(description)
        desc_label.setStyleSheet(Theme.secondary_hint_style())
        group_layout.addWidget(desc_label)

        status_layout = QHBoxLayout()
        status_label = QLabel("Не проверено")
        status_label.setStyleSheet(Theme.status_style("muted"))
        status_label.setObjectName("status_label")
        status_layout.addWidget(status_label)
        status_layout.addStretch()

        fix_btn = QPushButton("Исправить")
        fix_btn.setVisible(False)
        fix_btn.setObjectName("fix_btn")
        fix_btn._fallback_action = title  # type: ignore[attr-defined]
        fix_btn.clicked.connect(
            lambda _checked=False: self._on_fix_clicked(fix_btn)
        )
        status_layout.addWidget(fix_btn)

        group_layout.addLayout(status_layout)
        return group

    def _on_fix_clicked(self, button: QPushButton) -> None:
        """Обработка нажатия кнопки исправления."""
        action = getattr(button, "_readiness_action", None)
        fallback_action = getattr(button, "_fallback_action", "")
        self.fix_requested.emit(str(action or fallback_action))

    def run_checks(
        self,
        api_enabled: bool = False,
        output_path: str | Path = "",
        capture: CaptureSettings | None = None,
        audio: AudioSettings | None = None,
        snapshot: ReadinessSnapshot | None = None,
        recovery_count: int = 0,
    ) -> dict[str, bool]:
        """
        Запуск всех проверок.

        Args:
            api_enabled: Включён ли API сервер
            output_path: Путь к выходному файлу или папке вывода
            capture: Настройки текущего захвата
            audio: Настройки текущего аудио
            snapshot: Готовый readiness snapshot, если он уже был собран.

        Returns:
            Словарь с результатами проверок
        """
        self._loading.show()
        try:
            capture_settings = capture or CaptureSettings()
            audio_settings = audio or AudioSettings()
            resolved_output_path = Path(str(output_path))
            self._output_path = str(resolved_output_path)
            current_snapshot = snapshot or self._readiness_service.evaluate(
                capture=capture_settings,
                audio=audio_settings,
                output_path=resolved_output_path,
            )
            results = self._apply_readiness_snapshot(
                current_snapshot,
                api_enabled=api_enabled,
                capture=capture_settings,
                audio=audio_settings,
            )

            # Проверка API
            results["api"] = api_enabled
            self._update_group_status(
                self._api_group,
                api_enabled,
                "Запущен" if api_enabled else "Не запущен",
            )

            # Статистика восстановления FFmpeg
            if recovery_count > 0:
                self._update_group_status(
                    self._recovery_group,
                    ok=True,
                    message=f"Восстановлено {recovery_count} раз",
                    warning=recovery_count >= 2,
                )
            else:
                self._update_group_status(
                    self._recovery_group,
                    ok=True,
                    message="Нет восстановлений",
                )
        except Exception as e:
            logger.error(f"Ошибка при выполнении проверок: {e}")
        finally:
            self._loading.hide()

        return results

    def _apply_readiness_snapshot(
        self,
        snapshot: ReadinessSnapshot,
        api_enabled: bool,
        capture: CaptureSettings,
        audio: AudioSettings,
    ) -> dict[str, bool]:
        """Применить readiness snapshot к группам диагностики."""
        results: dict[str, bool] = {}
        checks = {
            check.key: check
            for check in build_readiness_checks(snapshot, capture, audio)
        }

        ffmpeg_check = checks["ffmpeg"]
        results["ffmpeg"] = ffmpeg_check.status == "ready"
        self._apply_check_to_group(self._ffmpeg_group, ffmpeg_check)

        output_check = checks["output"]
        results["output"] = output_check.status == "ready"
        self._apply_check_to_group(self._output_group, output_check)

        capture_check = checks["capture"]
        results["capture"] = capture_check.status != "blocking"
        self._apply_check_to_group(self._capture_group, capture_check)

        audio_check = checks["audio"]
        results["audio"] = audio_check.status != "blocking"
        self._apply_check_to_group(self._audio_group, audio_check)

        return results

    def _apply_check_to_group(
        self,
        group: QGroupBox,
        check: ReadinessCheck,
    ) -> None:
        """Применить общий readiness-check к группе диагностики."""
        ok = check.status in ("ready", "not_required", "warning")
        warning = check.status == "warning"
        if check.status == "ready":
            message = "Готово"
        elif check.status == "not_required":
            message = "Не требуется для текущего режима"
        else:
            message = check.message

        action_label = check.action.label if check.action is not None else None
        action_key = check.action.key if check.action is not None else None
        self._update_group_status(
            group,
            ok,
            message,
            warning=warning,
            action_label=action_label,
            action_key=action_key,
        )

    def _update_group_status(
        self,
        group: QGroupBox,
        ok: bool,
        message: str,
        warning: bool = False,
        action_label: str | None = None,
        action_key: str | None = None,
    ) -> None:
        """Обновление статуса группы."""
        status_label = group.findChild(QLabel, "")
        for child in group.findChildren(QLabel):
            if child.text() not in ("", group.title()):
                if Theme.COLORS["muted"] not in child.styleSheet():
                    status_label = child
                    break

        if status_label:
            status_label.setText(message)
            tone = "warning" if warning else ("success" if ok else "danger")
            status_label.setStyleSheet(Theme.status_style(tone))

        # Показать кнопку исправления если есть проблема
        fix_btn = group.findChild(QPushButton)
        if fix_btn:
            if action_label:
                fix_btn.setText(action_label)
            else:
                fix_btn.setText("Исправить")
            fix_btn._readiness_action = action_key  # type: ignore[attr-defined]
            fix_btn.setVisible((not ok) or warning)
