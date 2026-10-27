"""Тесты индикации потери аудио-чанков в DiagnosticsView (#154)."""

from __future__ import annotations

from unittest.mock import MagicMock

from core.readiness import ReadinessSnapshot
from core.recording_state import AudioSettings, CaptureSettings
from gui.views.diagnostics_view import DiagnosticsView


def _make_check_group(title: str) -> tuple[MagicMock, MagicMock]:
    """Фейковая check-группа с управляемым статус-лейблом."""
    group = MagicMock()
    status_label = MagicMock()
    status_label.text.return_value = "Не проверено"
    status_label.styleSheet.return_value = ""
    group.title.return_value = title
    group.findChildren.return_value = [status_label]
    group.findChild.return_value = None
    return group, status_label


def _build_diagnostics_view() -> tuple[DiagnosticsView, MagicMock]:
    """DiagnosticsView без _setup_ui с фейковыми check-группами."""
    view = DiagnosticsView.__new__(DiagnosticsView)
    view._loading = MagicMock()
    view._ffmpeg_group = _make_check_group("FFmpeg")[0]
    view._output_group = _make_check_group("Папка вывода")[0]
    view._capture_group = _make_check_group("Захват")[0]
    view._audio_group = _make_check_group("Аудио")[0]
    view._api_group = _make_check_group("API сервер")[0]
    view._recovery_group = _make_check_group("Восстановление FFmpeg")[0]
    audio_drop_group, audio_drop_label = _make_check_group("Потеря аудио")
    view._audio_drop_group = audio_drop_group
    view._readiness_service = MagicMock()
    return view, audio_drop_label


class TestAudioDropIndication:
    """Группа «Потеря аудио» в диагностике (#154)."""

    def test_zero_drops_shows_ok_message(self) -> None:
        """Без потерь показывается нейтральный статус."""
        view, audio_drop_label = _build_diagnostics_view()

        view.run_checks(
            capture=CaptureSettings(),
            audio=AudioSettings(),
            snapshot=ReadinessSnapshot(),
            dropped_audio_chunks=0,
        )

        audio_drop_label.setText.assert_called_with("Потерь нет")

    def test_drops_shows_warning_message(self) -> None:
        """Потери показывают счётчик и предупреждение."""
        view, audio_drop_label = _build_diagnostics_view()

        view.run_checks(
            capture=CaptureSettings(),
            audio=AudioSettings(),
            snapshot=ReadinessSnapshot(),
            dropped_audio_chunks=7,
        )

        audio_drop_label.setText.assert_called_with("Потеряно 7 аудио-чанков")

    def test_drop_status_style_differs_from_ok(self) -> None:
        """Стиль при потерях отличается от нейтрального (warning/danger)."""
        view_ok, label_ok = _build_diagnostics_view()
        view_drop, label_drop = _build_diagnostics_view()

        view_ok.run_checks(
            capture=CaptureSettings(),
            audio=AudioSettings(),
            snapshot=ReadinessSnapshot(),
            dropped_audio_chunks=0,
        )
        view_drop.run_checks(
            capture=CaptureSettings(),
            audio=AudioSettings(),
            snapshot=ReadinessSnapshot(),
            dropped_audio_chunks=1,
        )

        ok_style = label_ok.setStyleSheet.call_args.args[0]
        drop_style = label_drop.setStyleSheet.call_args.args[0]
        assert ok_style != drop_style
