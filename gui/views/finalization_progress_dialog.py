"""
Диалог прогресса финализации записи
====================================

Отображает текущий этап и процент выполнения при объединении/кодировании
видео после остановки записи (issue #96). Получает обновления от
``FinalizationProgressTracker`` единым источником через polling/ticker.
"""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from logger_config import get_module_logger
from recorder.encoder import FinalizationProgressTracker

logger = get_module_logger(__name__)


class FinalizationProgressDialog(QDialog):
    """Немодальный диалог прогресса финализации записи (#96).

    Поведение:
    - раз в 250 мс опрашивает ``tracker.snapshot()`` и обновляет
      прогресс-бар и метку этапа;
    - кнопка «Отмена» эмитирует ``cancel_requested`` — обработка на
      вызывающей стороне (``RecordingController.request_stop_cancellation``);
    - блокирует собственную закрывающую кнопку во время активной
      финализации, чтобы не нарушать итоговую сборку файла.
    """

    cancel_requested = pyqtSignal()

    def __init__(
        self,
        tracker: FinalizationProgressTracker,
        parent: QWidget | None = None,
        poll_interval_ms: int = 250,
    ) -> None:
        """Инициализация диалога.

        Args:
            tracker: Общий трекер прогресса, читается через ``snapshot()``.
            parent: Родительский виджет (для центрирования).
            poll_interval_ms: Период опроса трекера в миллисекундах.
        """
        super().__init__(parent)
        self._tracker = tracker
        self._poll_interval_ms = int(poll_interval_ms)
        self._cancel_in_progress = False

        self.setWindowTitle("Финализация записи")
        self.setModal(True)
        self.setMinimumWidth(360)
        # Запрещаем стандартное закрытие — обработка через _on_cancel.
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)

        self._stage_label = QLabel("Инициализация…")
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)

        self._cancel_btn = QPushButton("Отмена")
        self._cancel_btn.setAccessibleName("Отмена финализации записи")
        self._cancel_btn.clicked.connect(self._on_cancel_clicked)

        layout = QVBoxLayout(self)
        layout.addWidget(self._stage_label)
        layout.addWidget(self._progress)
        layout.addWidget(self._cancel_btn)

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._on_poll_tick)

    def start(self) -> None:
        """Показать диалог и начать polling прогресса."""
        self._cancel_in_progress = False
        self._cancel_btn.setEnabled(True)
        self._progress.setValue(0)
        self._stage_label.setText("Инициализация…")
        self._poll_timer.start(self._poll_interval_ms)
        self.show()
        self.raise_()
        logger.info("Диалог финализации открыт")

    def stop(self) -> None:
        """Остановить polling и скрыть диалог."""
        self._poll_timer.stop()
        self.hide()

    def _on_poll_tick(self) -> None:
        """Периодический опрос трекера и обновление UI."""
        snapshot = self._tracker.snapshot()
        percent = float(snapshot.get("percent", 0.0) or 0.0)
        stage = str(snapshot.get("stage", ""))
        active = bool(snapshot.get("active", False))

        self._progress.setValue(int(round(percent)))
        if stage:
            self._stage_label.setText(stage)

        if not active and percent >= 100.0:
            # Финализация завершена — закрываем диалог и уведомляем
            # вызывающую сторону (она подключена к finished-обработчику).
            self.stop()
            self.accept()

    def _on_cancel_clicked(self) -> None:
        """Запрос отмены от пользователя."""
        if self._cancel_in_progress:
            return
        logger.info("Пользователь запросил отмену финализации")
        self._cancel_in_progress = True
        self._cancel_btn.setEnabled(False)
        self._stage_label.setText("Отмена финализации…")
        self.cancel_requested.emit()

    def closeEvent(self, event: Any) -> None:
        """Игнорируем закрытие по Alt+F4/крестику во время финализации."""
        event.ignore()
