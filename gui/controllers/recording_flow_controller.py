"""
UI-реакции на жизненный цикл записи (#164)
==========================================

Миксин ``RecordingFlowControllerMixin`` вынесен из
``gui/main_window.py``: фоновая операция остановки, диалог прогресса
финализации, обработчики старта/остановки/паузы, плавающий виджет
метрик (#158) и таймер обновления статуса. ``MainWindow`` наследует
миксин — методы доступны как раньше.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PyQt6.QtGui import QIcon

from gui.controllers.status_bar_controller import StatusBarController
from gui.models.recording_state import RecordingStatus
from gui.views.finalization_progress_dialog import FinalizationProgressDialog
from gui.views.floating_widget import (
    STATE_FINALIZING,
    STATE_PAUSED,
    STATE_RECORDING,
    FloatingRecordingWidget,
)
from gui.views.recording_indicator import RecordingIndicatorOverlay
from logger_config import get_module_logger
from recorder.utils import format_time

if TYPE_CHECKING:
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QLabel, QMainWindow, QPushButton, QStatusBar

    from gui.controllers.recording_controller import RecordingController
    from gui.controllers.recordings_controller import RecordingsController
    from gui.controllers.settings_controller import SettingsController
    from gui.main_window import _ThreadTracker
    from gui.models.recording_state import CaptureSettings, RecordingState

logger = get_module_logger(__name__)

_STATUS_UPDATE_INTERVAL_MS = 100


if TYPE_CHECKING:
    _QWindowBase = QMainWindow
else:
    # В рантайме миксин — обычный класс (без metaclass-конфликтов
    # с PyQt); QMainWindow приходит от MainWindow напрямую.
    _QWindowBase = object


class RecordingFlowControllerMixin(_QWindowBase):
    """Фоновая остановка записи и обновление UI при её жизненном цикле."""

    if TYPE_CHECKING:
        # Общие атрибуты окна
        _stop_operation_in_progress: bool
        _stop_operation_thread: threading.Thread | None
        _thread_tracker: _ThreadTracker
        _recording_controller: RecordingController
        _recordings_controller: RecordingsController
        _recording_indicator: RecordingIndicatorOverlay
        _finalization_dialog: FinalizationProgressDialog | None
        _floating_widget: FloatingRecordingWidget | None
        _audio_drop_warning_shown: bool
        _settings_controller: SettingsController
        _status_bar_controller: StatusBarController
        _state: RecordingState
        _update_timer: QTimer
        stop_btn: QPushButton
        status_bar: QStatusBar
        status_label: QLabel

        # Сигналы MainWindow (после создания класса — bound signal)
        stop_operation_finished: Any
        recording_started: Any
        recording_stopped: Any
        recording_paused: Any
        recording_resumed: Any

        # Методы MainWindow
        _show_toast: Callable[..., None]
        _refresh_recent_recordings: Callable[[], None]

    def _get_finalization_dialog(self) -> FinalizationProgressDialog:
        """Получить диалог прогресса финализации (создать при необходимости)."""
        if self._finalization_dialog is None:
            dialog = FinalizationProgressDialog(
                tracker=self._recording_controller.progress_tracker,
                parent=self,
            )
            dialog.cancel_requested.connect(self._cancel_stop_operation)
            self._finalization_dialog = dialog
        return self._finalization_dialog

    def _show_finalization_progress_dialog(self) -> None:
        """Показать диалог прогресса финализации записи."""
        try:
            dialog = self._get_finalization_dialog()
        except Exception as e:
            # Без GUI (например, в тестах) пропускаем диалог
            logger.debug(f"Не удалось создать диалог финализации: {e}")
            return
        # Центрируем на главном окне: иначе диалог появляется в позиции
        # ОС и может перекрыть плавающий виджет или важные области.
        # Защищённо: в mocked-тестах геометрии может не быть.
        parent_geometry = getattr(self, "geometry", None)
        dialog_geometry = getattr(dialog, "frameGeometry", None)
        if callable(parent_geometry) and callable(dialog_geometry):
            window = parent_geometry()
            box = dialog_geometry()
            dialog.move(
                window.x() + (window.width() - box.width()) // 2,
                window.y() + (window.height() - box.height()) // 2,
            )
        dialog.start()

    def _hide_finalization_progress_dialog(self) -> None:
        """Скрыть диалог прогресса финализации записи."""
        dialog = self._finalization_dialog
        if dialog is None:
            return
        try:
            dialog.stop()
        except Exception as e:
            logger.debug(f"Не удалось остановить диалог финализации: {e}")

    def _begin_stop_operation(self) -> None:
        """Запустить остановку записи в фоне."""
        self._stop_operation_in_progress = True
        self._update_ui_state(RecordingStatus.STOPPING)
        self._set_floating_widget_state(STATE_FINALIZING)
        self.status_bar.showMessage("Финализация записи...", 0)
        self._show_finalization_progress_dialog()
        self._stop_operation_thread = threading.Thread(
            target=self._stop_recording_worker,
            daemon=True,
        )
        self._thread_tracker.track(self._stop_operation_thread)
        self._stop_operation_thread.start()

    def _stop_recording_worker(self) -> None:
        """Фоновый worker остановки записи."""
        output_path = self._recording_controller.stop_recording()
        error_message = (
            None if output_path is not None else "Не удалось сохранить запись"
        )
        self.stop_operation_finished.emit(output_path, error_message)

    def _cancel_stop_operation(self) -> None:
        """Запросить отмену долгой остановки записи."""
        if not self._stop_operation_in_progress:
            return

        if self._recording_controller.request_stop_cancellation():
            self.status_label.setText("Отмена остановки...")
            self.status_bar.showMessage(
                "Запрошена отмена остановки записи",
                5000,
            )
            self.stop_btn.setEnabled(False)
            return

        self.status_bar.showMessage(
            "Остановка ещё не дошла до стадии, которую можно отменить",
            5000,
        )

    def _on_stop_operation_finished(
        self,
        output_path: Path | None,
        error_message: str | None,
    ) -> None:
        """Завершить UI-часть операции остановки записи."""
        self._stop_operation_in_progress = False
        self._stop_operation_thread = None
        self.stop_btn.setText("Стоп")
        self._hide_finalization_progress_dialog()
        self._hide_floating_widget()

        if output_path is not None:
            self._on_recording_stopped(output_path)
            return

        self._update_ui_state(RecordingStatus.IDLE)
        self._recording_indicator.hide_indicator()
        self.status_bar.showMessage(
            error_message or "Остановка записи не завершена",
            5000,
        )

    # === Обработчики событий записи ===

    def _on_recording_started(
        self,
        output_path: Path,
        capture: CaptureSettings | None = None,
    ) -> None:
        """Обработка запуска записи."""
        self._set_status_updates_enabled(True)
        self._update_ui_state(RecordingStatus.RECORDING)
        self._audio_drop_warning_shown = False
        if capture is not None:
            self._recording_indicator.show_for_capture(capture)

        self._show_floating_widget()
        self.recording_started.emit(str(output_path))
        logger.info(f"Запись запущена: {output_path}")

    def _on_audio_chunks_dropped_warning(self, total: int) -> None:
        """Тост о первом переполнении аудио-очереди за запись (#154)."""
        if self._audio_drop_warning_shown:
            return
        self._audio_drop_warning_shown = True
        self._show_toast(
            f"Потеряно {total} аудио-чанков — переполнение очереди",
            duration_ms=5000,
        )

    def _on_recording_stopped(self, output_path: Path) -> None:
        """Обработка остановки записи."""
        # Режим рисования привязан к записи: закрыть оверлей (#159)
        draw_overlay = getattr(self, "_draw_overlay", None)
        if (
            draw_overlay is not None
            and getattr(draw_overlay, "isVisible", lambda: False)()
        ):
            draw_overlay.close_overlay()
        # Эффекты курсора привязаны к записи: скрыть оверлей (#166)
        hide_cursor_effects = getattr(self, "_hide_cursor_effects", None)
        if callable(hide_cursor_effects):
            hide_cursor_effects()
        self._set_status_updates_enabled(False)
        self._update_ui_state(RecordingStatus.IDLE)
        self._recording_indicator.hide_indicator()

        # Добавление в список последних записей
        if output_path.exists():
            size = output_path.stat().st_size
            self._settings_controller.add_recent_recording(output_path, size)
            # Запустить генерацию миниатюры в фоновом потоке
            self._generate_thumbnail_for_recording(output_path)
        self._refresh_recent_recordings()

        self.recording_stopped.emit(str(output_path))
        logger.info(f"Запись остановлена: {output_path}")

    def _generate_thumbnail_for_recording(self, output_path: Path) -> None:
        """Генерировать миниатюру для новой записи в фоновом потоке."""
        self._recordings_controller.generate_thumbnail_for_recording(
            output_path
        )

    def _get_recorded_video_icon(self) -> QIcon:
        """Получить placeholder иконку для записи без миниатюры."""
        return self._recordings_controller.get_recorded_video_icon()

    def _on_recording_paused(self) -> None:
        """Обработка приостановки записи."""
        self._set_status_updates_enabled(False)
        self._update_ui_state(RecordingStatus.PAUSED)
        self._recording_indicator.set_paused(True)
        self._set_floating_widget_state(STATE_PAUSED)

        self.recording_paused.emit()

    def _on_recording_resumed(self) -> None:
        """Обработка возобновления записи."""
        self._set_status_updates_enabled(True)
        self._update_ui_state(RecordingStatus.RECORDING)
        self._recording_indicator.set_paused(False)
        self._set_floating_widget_state(STATE_RECORDING)

        self.recording_resumed.emit()

    # === Плавающий виджет записи (#158) ===

    def _get_floating_widget(self) -> FloatingRecordingWidget | None:
        """Лениво создать плавающий виджет записи (#158)."""
        if self._floating_widget is None:
            try:
                self._floating_widget = FloatingRecordingWidget()
            except Exception as e:
                logger.warning(
                    "Не удалось создать плавающий виджет записи: %s", e
                )
                return None
        return self._floating_widget

    def _show_floating_widget(self) -> None:
        """Показать плавающий виджет в состоянии записи (#158)."""
        widget = self._get_floating_widget()
        if widget is None:
            return
        widget.set_state(STATE_RECORDING)
        try:
            from recorder.utils import get_screen_size

            widget.restore_position(get_screen_size())
        except Exception as e:
            logger.debug("Позиция плавающего виджета не восстановлена: %s", e)
        if hasattr(widget, "show"):
            widget.show()
        widget.start_updates(self._on_floating_widget_tick)

    def _hide_floating_widget(self) -> None:
        """Скрыть плавающий виджет и сохранить позицию (#158)."""
        widget = self._floating_widget
        if widget is None:
            return
        widget.stop_updates()
        widget.save_position()
        if hasattr(widget, "hide"):
            widget.hide()
        widget.set_state("idle")

    def _set_floating_widget_state(self, state: str) -> None:
        """Переключить состояние плавающего виджета, если он виден (#158)."""
        widget = self._floating_widget
        if widget is not None:
            widget.set_state(state)

    def _on_floating_widget_tick(self) -> None:
        """Тик плавающего виджета: обновить метрики (#158)."""
        widget = self._floating_widget
        if widget is None or self._floating_widget is None:
            return
        self._update_floating_widget_metrics()

    def _update_floating_widget_metrics(self) -> None:
        """Передать в плавающий виджет таймер/FPS/размер файла (#158)."""
        widget = self._floating_widget
        if widget is None or not hasattr(widget, "isVisible"):
            return
        if not widget.isVisible():
            return
        elapsed = self._recording_controller.elapsed_time
        metrics = self._recording_controller.frame_metrics
        actual_fps = float(metrics.get("actual_fps", 0.0))
        size = self._recording_controller.temp_video_size
        widget.update_metrics(elapsed, actual_fps, size)

    # === Таймер статуса ===

    def _update_ui_state(self, status: RecordingStatus) -> None:
        """
        Централизованно обновить состояние recording UI controls.

        Args:
            status: Статус записи из `RecordingStatus`.
        """
        self._status_bar_controller.apply_recording_status(status)

    def _update_status(self) -> None:
        """Обновление отображения статуса."""
        if self._state.is_recording():
            elapsed = self._recording_controller.elapsed_time
            formatted_time = format_time(elapsed)
            metrics = self._recording_controller.frame_metrics
            actual_fps = float(metrics.get("actual_fps", 0.0))
            jitter_ms = float(metrics.get("jitter_ms", 0.0))
            if actual_fps > 0:
                display_text = f"{formatted_time} (FPS: {actual_fps:.1f} | Jitter: {jitter_ms:.1f}ms)"
            else:
                display_text = formatted_time
            self._status_bar_controller.update_time_display(display_text)
            self._update_floating_widget_metrics()

    def _set_status_updates_enabled(self, enabled: bool) -> None:
        """
        Включить или выключить обновление времени записи.

        Args:
            enabled: Нужно ли держать timer активным.
        """
        if enabled:
            self._update_timer.start(_STATUS_UPDATE_INTERVAL_MS)
            return

        self._update_timer.stop()
