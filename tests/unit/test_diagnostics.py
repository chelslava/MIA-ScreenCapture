"""
Тесты для модуля диагностики.
"""

from unittest.mock import MagicMock, patch

import pytest


class TestDiagnosticsView:
    """Тесты DiagnosticsView."""

    def test_recheck_button_emits_signal(self, qapp):
        """Проверка что кнопка 'Проверить снова' испускает сигнал."""
        from gui.views.diagnostics_view import DiagnosticsView

        view = DiagnosticsView()
        signal_received = []

        def on_recheck():
            signal_received.append(True)

        view.recheck_requested.connect(on_recheck)
        view._recheck_btn.click()

        assert signal_received == [True]

    def test_fix_button_emits_signal(self, qapp):
        """Проверка что кнопка 'Исправить' испускает сигнал с именем проверки."""
        from gui.views.diagnostics_view import DiagnosticsView

        view = DiagnosticsView()
        signal_received = []

        def on_fix(check_name):
            signal_received.append(check_name)

        view.fix_requested.connect(on_fix)
        view.run_checks(api_enabled=False, output_path="")

        fix_btn = view._output_group.findChild(
            type(view._recheck_btn), "fix_btn"
        )
        assert fix_btn is not None
        assert fix_btn.isVisible()

        fix_btn.click()

        assert signal_received == ["Папка вывода"]

    def test_run_checks_returns_results(self, qapp):
        """Проверка что run_checks возвращает результаты."""
        from gui.views.diagnostics_view import DiagnosticsView

        view = DiagnosticsView()

        with patch(
            "gui.views.diagnostics_view.check_ffmpeg", return_value=True
        ):
            with patch(
                "gui.views.diagnostics_view.get_audio_devices",
                return_value=["device1"],
            ):
                results = view.run_checks(api_enabled=True, output_path="/tmp")

        assert "ffmpeg" in results
        assert "audio" in results
        assert "api" in results
        assert "output" in results

    def test_output_path_check_with_valid_path(self, qapp, tmp_path):
        """Проверка валидного пути вывода."""
        from gui.views.diagnostics_view import DiagnosticsView

        view = DiagnosticsView()

        valid_path = str(tmp_path / "output")
        result = view._check_output_path(valid_path)

        assert result is True

    def test_output_path_check_with_empty_path(self, qapp):
        """Проверка пустого пути вывода."""
        from gui.views.diagnostics_view import DiagnosticsView

        view = DiagnosticsView()

        result = view._check_output_path("")

        assert result is False

    def test_ffmpeg_check_handles_exception(self, qapp):
        """Проверка обработки исключения при проверке FFmpeg."""
        from gui.views.diagnostics_view import DiagnosticsView

        view = DiagnosticsView()

        with patch(
            "gui.views.diagnostics_view.check_ffmpeg",
            side_effect=Exception("FFmpeg error"),
        ):
            result = view._check_ffmpeg()

        assert result is False

    def test_audio_devices_check_handles_exception(self, qapp):
        """Проверка обработки исключения при проверке аудиоустройств."""
        from gui.views.diagnostics_view import DiagnosticsView

        view = DiagnosticsView()

        with patch(
            "gui.views.diagnostics_view.get_audio_devices",
            side_effect=Exception("Audio error"),
        ):
            ok, count = view._check_audio_devices()

        assert ok is False
        assert count == 0

    def test_fix_button_visible_on_failure(self, qapp):
        """Проверка видимости кнопки 'Исправить' при ошибке."""
        from gui.views.diagnostics_view import DiagnosticsView

        view = DiagnosticsView()

        with patch(
            "gui.views.diagnostics_view.check_ffmpeg", return_value=False
        ):
            view.run_checks(api_enabled=False, output_path="")

        fix_btn = view._ffmpeg_group.findChild(
            type(view._recheck_btn), "fix_btn"
        )
        assert fix_btn is not None
        assert fix_btn.isVisible()

    def test_fix_button_hidden_on_success(self, qapp, tmp_path):
        """Проверка скрытия кнопки 'Исправить' при успехе."""
        from gui.views.diagnostics_view import DiagnosticsView

        view = DiagnosticsView()

        valid_path = str(tmp_path)

        with patch(
            "gui.views.diagnostics_view.check_ffmpeg", return_value=True
        ):
            with patch(
                "gui.views.diagnostics_view.get_audio_devices",
                return_value=["device1"],
            ):
                view.run_checks(api_enabled=True, output_path=valid_path)

        fix_btn = view._output_group.findChild(
            type(view._recheck_btn), "fix_btn"
        )
        assert fix_btn is not None
        assert not fix_btn.isVisible()


class TestDiagnosticsIntegration:
    """Интеграционные тесты диагностики."""

    def test_recheck_triggers_run_checks(self, qapp):
        """Проверка что кнопка 'Проверить снова' вызывает run_checks."""
        from gui.views.diagnostics_view import DiagnosticsView

        view = DiagnosticsView()

        call_count = 0
        original_run_checks = view.run_checks

        def mock_run_checks(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return original_run_checks(*args, **kwargs)

        view.run_checks = mock_run_checks

        with patch(
            "gui.views.diagnostics_view.check_ffmpeg", return_value=True
        ):
            with patch(
                "gui.views.diagnostics_view.get_audio_devices",
                return_value=[],
            ):
                view.run_checks(api_enabled=False, output_path="")

        initial_count = call_count

        view._recheck_btn.click()

        assert call_count > initial_count
