"""
Unit-тесты для представления настроек постобработки PostProcessingView (Issue #118)
==================================================================================
"""

from __future__ import annotations

from unittest.mock import MagicMock

from config import PostProcessingSettings
from gui.views.post_processing_view import PostProcessingView


class TestPostProcessingView:
    """Тестирование виджета PostProcessingView."""

    def test_get_and_set_settings(self) -> None:
        view = PostProcessingView()
        settings = PostProcessingSettings(
            enabled=True,
            transcode_enabled=True,
            transcode_format="webm",
            transcode_codec="libvpx-vp9",
            compress_enabled=True,
            compress_crf=22,
            trim_silence_enabled=True,
            trim_silence_threshold_db=-40,
            generate_gif_enabled=True,
            gif_duration_seconds=7,
            gif_fps=15,
            copy_enabled=True,
            copy_target_folder="D:/Recordings",
            open_explorer_on_finish=True,
            webhook_enabled=True,
            webhook_url="https://example.com/hook",
        )

        view.set_settings(settings)
        result = view.get_settings()

        assert result.enabled is True
        assert result.transcode_enabled is True
        assert result.transcode_format == "webm"
        assert result.compress_enabled is True
        assert result.compress_crf == 22
        assert result.trim_silence_enabled is True
        assert result.trim_silence_threshold_db == -40
        assert result.generate_gif_enabled is True
        assert result.gif_duration_seconds == 7
        assert result.gif_fps == 15
        assert result.copy_enabled is True
        assert result.copy_target_folder == "D:/Recordings"
        assert result.open_explorer_on_finish is True
        assert result.webhook_enabled is True
        assert result.webhook_url == "https://example.com/hook"

    def test_settings_changed_signal_emitted(self) -> None:
        view = PostProcessingView()
        mock_handler = MagicMock()
        view.settings_changed.connect(mock_handler)

        view._main_enabled_cb.toggled.emit(True)
        assert mock_handler.called
