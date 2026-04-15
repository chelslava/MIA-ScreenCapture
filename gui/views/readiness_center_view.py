"""Компактный readiness center перед стартом записи."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.readiness import (
    ReadinessCheck,
    summarize_readiness_checks,
)
from gui.accessibility import apply_accessible_metadata
from gui.styles.theme import Theme


class ReadinessCenterView(QWidget):
    """Показывает inline checklist готовности перед стартом записи."""

    refresh_requested = pyqtSignal()
    details_requested = pyqtSignal()
    action_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._row_widgets: dict[str, dict[str, QWidget]] = {}
        self._row_actions: dict[str, str | None] = {}
        self._setup_ui()
        self.set_loading_state()

    def _setup_ui(self) -> None:
        """Настроить компактный readiness center."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("Готовность к записи")
        group_layout = QVBoxLayout(group)

        self._summary_label = QLabel()
        self._summary_label.setStyleSheet(Theme.status_style("muted"))
        group_layout.addWidget(self._summary_label)

        self._summary_hint_label = QLabel()
        self._summary_hint_label.setStyleSheet(Theme.secondary_text_style())
        group_layout.addWidget(self._summary_hint_label)

        for key, title in (
            ("ffmpeg", "FFmpeg"),
            ("output", "Путь вывода"),
            ("capture", "Окно захвата"),
            ("audio", "Микрофон"),
        ):
            row_widgets = self._create_check_row(title, key)
            self._row_widgets[key] = row_widgets
            group_layout.addWidget(row_widgets["container"])

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        self._refresh_btn = QPushButton("Проверить снова")
        self._refresh_btn.clicked.connect(
            lambda _checked=False: self.refresh_requested.emit()
        )
        buttons_layout.addWidget(self._refresh_btn)

        self._details_btn = QPushButton("Открыть диагностику")
        self._details_btn.clicked.connect(
            lambda _checked=False: self.details_requested.emit()
        )
        buttons_layout.addWidget(self._details_btn)

        group_layout.addLayout(buttons_layout)

        self._apply_accessibility_metadata()
        layout.addWidget(group)

    def _create_check_row(
        self,
        title: str,
        row_key: str,
    ) -> dict[str, QWidget]:
        """Создать строку checklist для одного readiness-check."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 4, 0, 4)

        header_layout = QHBoxLayout()
        title_label = QLabel(title)
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        status_label = QLabel("Проверяем…")
        status_label.setStyleSheet(Theme.status_style("muted"))
        header_layout.addWidget(status_label)
        layout.addLayout(header_layout)

        footer_layout = QHBoxLayout()
        message_label = QLabel("Собираем данные preflight-checklist.")
        message_label.setStyleSheet(Theme.secondary_text_style())
        footer_layout.addWidget(message_label)
        footer_layout.addStretch()

        action_btn = QPushButton("Исправить")
        action_btn.setVisible(False)
        action_btn.clicked.connect(
            lambda _checked=False: self._emit_row_action(row_key)
        )
        footer_layout.addWidget(action_btn)
        layout.addLayout(footer_layout)

        return {
            "container": container,
            "title_label": title_label,
            "status_label": status_label,
            "message_label": message_label,
            "action_btn": action_btn,
        }

    def _apply_accessibility_metadata(self) -> None:
        """Назначить accessibility metadata readiness controls."""
        apply_accessible_metadata(
            self._summary_label,
            "Сводка готовности к записи",
            "Показывает общий preflight-статус перед запуском записи.",
        )
        apply_accessible_metadata(
            self._refresh_btn,
            "Повторить readiness-проверку",
            "Запускает повторную preflight-проверку окружения.",
            "Обновляет checklist готовности.",
        )
        apply_accessible_metadata(
            self._details_btn,
            "Открыть полную диагностику",
            "Переходит на вкладку диагностики с подробным checklist.",
            "Открывает вкладку диагностики.",
        )

    def set_loading_state(self) -> None:
        """Показать пользователю, что readiness-checklist обновляется."""
        self._summary_label.setText("Проверяем готовность к записи…")
        self._summary_label.setStyleSheet(Theme.status_style("muted"))
        self._summary_hint_label.setText(
            "Собираем preflight-checklist для FFmpeg, вывода и устройств."
        )

        for row_widgets in self._row_widgets.values():
            status_label = row_widgets["status_label"]
            assert isinstance(status_label, QLabel)
            status_label.setText("Проверяем…")
            status_label.setStyleSheet(Theme.status_style("muted"))

            message_label = row_widgets["message_label"]
            assert isinstance(message_label, QLabel)
            message_label.setText("Ожидаем актуальные данные окружения.")
            message_label.setStyleSheet(Theme.secondary_text_style())

            action_btn = row_widgets["action_btn"]
            assert isinstance(action_btn, QPushButton)
            action_btn.setVisible(False)

    def set_error_state(self, message: str) -> None:
        """Показать ошибку обновления readiness center."""
        self._summary_label.setText("Не удалось обновить readiness-checklist")
        self._summary_label.setStyleSheet(Theme.status_style("danger"))
        self._summary_hint_label.setText(message)
        self._summary_hint_label.setStyleSheet(
            f"color: {Theme.COLORS['danger']};"
        )

    def apply_checks(self, checks: tuple[ReadinessCheck, ...]) -> None:
        """Применить готовый readiness checklist к компактному view."""
        overall_status, summary_text = summarize_readiness_checks(checks)
        tone = {
            "blocking": "danger",
            "warning": "warning",
            "ready": "success",
            "not_required": "muted",
        }.get(overall_status, "muted")

        self._summary_label.setText(summary_text)
        self._summary_label.setStyleSheet(Theme.status_style(tone))
        self._summary_hint_label.setText(self._build_hint_text(checks))
        self._summary_hint_label.setStyleSheet(Theme.secondary_text_style())

        for check in checks:
            self._apply_check_row(check)

    def _build_hint_text(self, checks: tuple[ReadinessCheck, ...]) -> str:
        """Собрать поясняющий текст под общей readiness summary."""
        actionable_checks = [
            check
            for check in checks
            if check.status in ("blocking", "warning")
        ]
        if not actionable_checks:
            return "Можно запускать запись из GUI, tray и hotkey-сценариев."

        first_check = actionable_checks[0]
        if first_check.next_step:
            return first_check.next_step
        return first_check.message

    def _apply_check_row(self, check: ReadinessCheck) -> None:
        """Обновить одну строку readiness checklist."""
        row_widgets = self._row_widgets.get(check.key)
        if row_widgets is None:
            return

        tone = {
            "ready": "success",
            "warning": "warning",
            "blocking": "danger",
            "not_required": "muted",
        }.get(check.status, "muted")
        status_text = {
            "ready": "Готово",
            "warning": "Предупреждение",
            "blocking": "Требует внимания",
            "not_required": "Не требуется",
        }.get(check.status, "—")

        status_label = row_widgets["status_label"]
        assert isinstance(status_label, QLabel)
        status_label.setText(status_text)
        status_label.setStyleSheet(Theme.status_style(tone))

        message_label = row_widgets["message_label"]
        assert isinstance(message_label, QLabel)
        message_label.setText(self._compose_check_message(check))
        message_label.setStyleSheet(Theme.secondary_text_style())

        action_btn = row_widgets["action_btn"]
        assert isinstance(action_btn, QPushButton)
        if check.action is None:
            self._row_actions[check.key] = None
            action_btn.setVisible(False)
            return

        self._row_actions[check.key] = check.action.key
        action_btn.setText(check.action.label)
        action_btn.setVisible(True)

    def _compose_check_message(self, check: ReadinessCheck) -> str:
        """Сформировать текст строки readiness-check."""
        if check.next_step:
            return f"{check.message} {check.next_step}"
        return check.message

    def _emit_row_action(self, row_key: str) -> None:
        """Эмитить action выбранной строки readiness-checklist."""
        action_key = self._row_actions.get(row_key)
        if action_key:
            self.action_requested.emit(action_key)
