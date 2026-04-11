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

from core.readiness import ReadinessSnapshot, RecordingReadinessService
from core.recording_state import AudioSettings, CaptureSettings
from core.recording_types import AudioMode, CaptureMode
from gui.accessibility import apply_accessible_metadata
from gui.styles.theme import Theme
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class DiagnosticsView(QWidget):
    """Виджет диагностики системы."""

    recheck_requested = pyqtSignal()
    fix_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._output_path = ""
        self._readiness_service = RecordingReadinessService()
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

        self._capture_group = self._create_check_group(
            "Окно захвата", "Проверка доступности выбранного окна"
        )
        self._checks_layout.addWidget(self._capture_group)

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
        """Открытие папки с логами."""
        from logger_config import open_logs_folder

        logger.info("Открытие папки логов")
        open_logs_folder()

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
        fix_btn.clicked.connect(lambda: self._on_fix_clicked(title))
        status_layout.addWidget(fix_btn)

        group_layout.addLayout(status_layout)
        return group

    def _on_fix_clicked(self, check_name: str) -> None:
        """Обработка нажатия кнопки исправления."""
        self.fix_requested.emit(check_name)

    def run_checks(
        self,
        api_enabled: bool = False,
        output_path: str | Path = "",
        capture: CaptureSettings | None = None,
        audio: AudioSettings | None = None,
    ) -> dict[str, bool]:
        """
        Запуск всех проверок.

        Args:
            api_enabled: Включён ли API сервер
            output_path: Путь к выходному файлу или папке вывода
            capture: Настройки текущего захвата
            audio: Настройки текущего аудио

        Returns:
            Словарь с результатами проверок
        """
        results: dict[str, bool] = {}

        try:
            capture_settings = capture or CaptureSettings()
            audio_settings = audio or AudioSettings()
            resolved_output_path = Path(str(output_path))
            self._output_path = str(resolved_output_path)
            snapshot = self._readiness_service.evaluate(
                capture=capture_settings,
                audio=audio_settings,
                output_path=resolved_output_path,
            )
            results.update(
                self._apply_readiness_snapshot(
                    snapshot,
                    api_enabled=api_enabled,
                    capture=capture_settings,
                    audio=audio_settings,
                )
            )

            # Проверка API
            results["api"] = api_enabled
            self._update_group_status(
                self._api_group,
                api_enabled,
                "Запущен" if api_enabled else "Не запущен",
            )
        except Exception as e:
            logger.error(f"Ошибка при выполнении проверок: {e}")

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

        ffmpeg_issue = snapshot.find_issue("ffmpeg_missing")
        results["ffmpeg"] = ffmpeg_issue is None
        self._update_group_status(
            self._ffmpeg_group,
            ffmpeg_issue is None,
            "Найден" if ffmpeg_issue is None else ffmpeg_issue.title,
        )

        output_issue = snapshot.find_issue(
            "output_path_invalid",
            "disk_space_low",
        )
        results["output"] = output_issue is None
        self._update_group_status(
            self._output_group,
            output_issue is None,
            "Доступна" if output_issue is None else output_issue.title,
        )

        capture_issue = snapshot.find_issue(
            "window_not_selected",
            "window_missing",
        )
        capture_ok = (
            capture.capture_type != CaptureMode.WINDOW or capture_issue is None
        )
        results["capture"] = capture_ok
        capture_message = "Не требуется для текущего режима"
        if capture.capture_type == CaptureMode.WINDOW:
            capture_message = (
                "Окно доступно"
                if capture_issue is None
                else capture_issue.title
            )
        self._update_group_status(
            self._capture_group,
            capture_ok,
            capture_message,
        )

        audio_issue = snapshot.find_issue(
            "microphone_missing",
            "microphone_selected_missing",
            "microphone_name_missing",
            "microphone_default",
        )
        audio_ok = audio_issue is None or audio_issue.severity == "warning"
        results["audio"] = audio_ok
        if audio.audio_type in (AudioMode.NONE, AudioMode.SYSTEM):
            self._update_group_status(
                self._audio_group,
                True,
                "Не требуется для текущего режима",
            )
        elif audio_issue is None:
            self._update_group_status(
                self._audio_group,
                True,
                "Микрофон готов",
            )
        else:
            self._update_group_status(
                self._audio_group,
                audio_ok,
                audio_issue.title,
                warning=audio_issue.severity == "warning",
            )

        return results

    def _update_group_status(
        self,
        group: QGroupBox,
        ok: bool,
        message: str,
        warning: bool = False,
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
            fix_btn.setVisible((not ok) or warning)
