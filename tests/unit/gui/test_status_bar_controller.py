"""
Тесты StatusBarController
==========================

Тестирует логику обновления кнопок и меток строки состояния.
"""

from unittest.mock import MagicMock

import pytest

from gui.controllers.status_bar_controller import StatusBarController
from gui.models.recording_state import RecordingStatus


def _build_controller():
    """Создать StatusBarController с мок-виджетами."""
    start_btn = MagicMock()
    stop_btn = MagicMock()
    pause_btn = MagicMock()
    status_label = MagicMock()
    time_label = MagicMock()
    ctrl = StatusBarController(
        start_btn=start_btn,
        stop_btn=stop_btn,
        pause_btn=pause_btn,
        status_label=status_label,
        time_label=time_label,
    )
    return ctrl, start_btn, stop_btn, pause_btn, status_label, time_label


class TestStatusBarControllerIdle:
    """Тесты состояния IDLE."""

    def test_idle_enables_start_disables_stop_and_pause(self) -> None:
        ctrl, start_btn, stop_btn, pause_btn, _, _ = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.IDLE)

        start_btn.setEnabled.assert_called_once_with(True)
        stop_btn.setEnabled.assert_called_once_with(False)
        pause_btn.setEnabled.assert_called_once_with(False)

    def test_idle_sets_status_text_to_ready(self) -> None:
        ctrl, _, _, _, status_label, _ = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.IDLE)

        status_label.setText.assert_called_once_with("Готов")

    def test_idle_resets_time_to_zero(self) -> None:
        ctrl, _, _, _, _, time_label = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.IDLE)

        time_label.setText.assert_called_once_with("00:00")

    def test_idle_sets_pause_text_to_pause(self) -> None:
        ctrl, _, _, pause_btn, _, _ = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.IDLE)

        pause_btn.setText.assert_called_once_with("Пауза")

    def test_idle_sets_stop_text_to_stop(self) -> None:
        ctrl, _, stop_btn, _, _, _ = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.IDLE)

        stop_btn.setText.assert_called_once_with("Стоп")


class TestStatusBarControllerRecording:
    """Тесты состояния RECORDING."""

    def test_recording_disables_start_enables_stop_and_pause(self) -> None:
        ctrl, start_btn, stop_btn, pause_btn, _, _ = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.RECORDING)

        start_btn.setEnabled.assert_called_once_with(False)
        stop_btn.setEnabled.assert_called_once_with(True)
        pause_btn.setEnabled.assert_called_once_with(True)

    def test_recording_sets_status_text(self) -> None:
        ctrl, _, _, _, status_label, _ = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.RECORDING)

        status_label.setText.assert_called_once_with("Запись")

    def test_recording_does_not_reset_time_label(self) -> None:
        ctrl, _, _, _, _, time_label = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.RECORDING)

        time_label.setText.assert_not_called()

    def test_recording_sets_pause_text_to_pause(self) -> None:
        ctrl, _, _, pause_btn, _, _ = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.RECORDING)

        pause_btn.setText.assert_called_once_with("Пауза")


class TestStatusBarControllerPaused:
    """Тесты состояния PAUSED."""

    def test_paused_disables_start_enables_stop_and_pause(self) -> None:
        ctrl, start_btn, stop_btn, pause_btn, _, _ = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.PAUSED)

        start_btn.setEnabled.assert_called_once_with(False)
        stop_btn.setEnabled.assert_called_once_with(True)
        pause_btn.setEnabled.assert_called_once_with(True)

    def test_paused_sets_pause_text_to_continue(self) -> None:
        ctrl, _, _, pause_btn, _, _ = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.PAUSED)

        pause_btn.setText.assert_called_once_with("Продолжить")

    def test_paused_sets_status_text(self) -> None:
        ctrl, _, _, _, status_label, _ = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.PAUSED)

        status_label.setText.assert_called_once_with("Пауза")

    def test_paused_does_not_reset_time_label(self) -> None:
        ctrl, _, _, _, _, time_label = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.PAUSED)

        time_label.setText.assert_not_called()


class TestStatusBarControllerStopping:
    """Тесты состояния STOPPING."""

    def test_stopping_disables_start_and_pause_enables_stop(self) -> None:
        ctrl, start_btn, stop_btn, pause_btn, _, _ = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.STOPPING)

        start_btn.setEnabled.assert_called_once_with(False)
        stop_btn.setEnabled.assert_called_once_with(True)
        pause_btn.setEnabled.assert_called_once_with(False)

    def test_stopping_sets_stop_text_to_cancel(self) -> None:
        ctrl, _, stop_btn, _, _, _ = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.STOPPING)

        stop_btn.setText.assert_called_once_with("Отменить остановку")

    def test_stopping_sets_status_text(self) -> None:
        ctrl, _, _, _, status_label, _ = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.STOPPING)

        status_label.setText.assert_called_once_with("Остановка...")

    def test_stopping_does_not_reset_time_label(self) -> None:
        ctrl, _, _, _, _, time_label = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.STOPPING)

        time_label.setText.assert_not_called()


class TestStatusBarControllerUpdateTime:
    """Тесты обновления метки времени."""

    def test_update_time_display_sets_label_text(self) -> None:
        ctrl, _, _, _, _, time_label = _build_controller()

        ctrl.update_time_display("01:23")

        time_label.setText.assert_called_once_with("01:23")

    @pytest.mark.parametrize(
        "time_text",
        ["00:00", "01:30", "59:59", "1:00:00"],
    )
    def test_update_time_display_parametrized(self, time_text: str) -> None:
        ctrl, _, _, _, _, time_label = _build_controller()

        ctrl.update_time_display(time_text)

        time_label.setText.assert_called_once_with(time_text)


class TestStatusBarControllerStatusStyle:
    """Тесты применения стилей статуса."""

    def test_idle_clears_status_style(self) -> None:
        ctrl, _, _, _, status_label, _ = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.IDLE)

        call_args = status_label.setStyleSheet.call_args[0][0]
        assert call_args == ""

    def test_recording_applies_danger_style(self) -> None:
        ctrl, _, _, _, status_label, _ = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.RECORDING)

        call_args = status_label.setStyleSheet.call_args[0][0]
        assert call_args != ""

    def test_paused_applies_warning_style(self) -> None:
        ctrl, _, _, _, status_label, _ = _build_controller()

        ctrl.apply_recording_status(RecordingStatus.PAUSED)

        call_args = status_label.setStyleSheet.call_args[0][0]
        assert call_args != ""
