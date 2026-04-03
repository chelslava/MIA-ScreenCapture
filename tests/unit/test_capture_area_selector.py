"""
Тесты графического выбора области захвата.
"""

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from config import ConfigManager
from gui.controllers.settings_controller import SettingsController
from gui.models.recording_state import CaptureType, RecordingState
from gui.views.area_selector import (
    describe_rect,
    format_rect_coords,
    move_rect,
    normalize_rect_coords,
    resize_rect,
)
from gui.views.capture_view import CaptureView

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication


class TestAreaSelectorHelpers:
    """Тесты чистых хелперов selector-а."""

    def test_normalize_rect_coords_reorders_points(self) -> None:
        """Координаты нормализуются независимо от направления выделения."""
        result = normalize_rect_coords((500, 400), (100, 200))
        assert result == (100, 200, 500, 400)

    def test_move_rect_stays_inside_bounds(self) -> None:
        """Перемещение не выпускает область за границы экрана."""
        result = move_rect((100, 100, 400, 300), (900, 700), (0, 0, 1000, 800))
        assert result == (700, 600, 1000, 800)

    def test_resize_rect_clamps_to_bounds(self) -> None:
        """Изменение размера ограничивается экраном."""
        result = resize_rect((100, 100), (1400, 900), (0, 0, 1280, 720))
        assert result == (100, 100, 1280, 720)

    def test_describe_rect_includes_size(self) -> None:
        """Сводка содержит позицию и размер области."""
        summary = describe_rect((10, 20, 210, 120))
        assert "10, 20" in summary
        assert "200 × 100" in summary

    def test_format_rect_coords(self) -> None:
        """Координаты форматируются в строку для GUI."""
        assert format_rect_coords((1, 2, 3, 4)) == "1, 2, 3, 4"


class TestCaptureViewGraphicSelection:
    """Тесты интеграции CaptureView с selector-ом."""

    def test_select_rectangle_updates_view_and_emits_signal(
        self, qapp: "QApplication"
    ) -> None:
        """Выбор области обновляет UI и отправляет сигнал."""
        with (
            patch(
                "gui.views.capture_view.get_available_windows", return_value=[]
            ),
            patch(
                "gui.views.capture_view.get_screen_size",
                return_value=(1920, 1080),
            ),
            patch(
                "gui.views.capture_view.AreaSelectorDialog.select_area",
                return_value=(100, 120, 500, 420),
            ),
        ):
            view = CaptureView()
            received: list[tuple[int, int, int, int]] = []
            view.rect_selected.connect(received.append)

            view._select_rectangle()

            assert view.get_capture_type() == CaptureType.RECT
            assert view.get_rect_coords() == (100, 120, 500, 420)
            assert view._rect_edit.text() == "100, 120, 500, 420"
            assert "400 × 300" in view._rect_summary_label.text()
            assert view._rect_preview._rect_coords == (100, 120, 500, 420)
            assert received == [(100, 120, 500, 420)]

    def test_set_rect_coords_updates_preview_state(
        self,
        qapp: "QApplication",
    ) -> None:
        """Программная установка координат синхронизирует preview."""
        with (
            patch(
                "gui.views.capture_view.get_available_windows", return_value=[]
            ),
            patch(
                "gui.views.capture_view.get_screen_size",
                return_value=(2560, 1440),
            ),
        ):
            view = CaptureView()

            view.set_rect_coords((50, 60, 350, 260))

            assert view.get_rect_coords() == (50, 60, 350, 260)
            assert view._rect_edit.text() == "50, 60, 350, 260"
            assert "300 × 200" in view._rect_summary_label.text()
            assert view._rect_preview._rect_coords == (50, 60, 350, 260)

    def test_cancelled_selection_keeps_empty_state(
        self,
        qapp: "QApplication",
    ) -> None:
        """Отмена selector-а не меняет текущие координаты."""
        with (
            patch(
                "gui.views.capture_view.get_available_windows", return_value=[]
            ),
            patch(
                "gui.views.capture_view.get_screen_size",
                return_value=(1920, 1080),
            ),
            patch(
                "gui.views.capture_view.AreaSelectorDialog.select_area",
                return_value=None,
            ),
        ):
            view = CaptureView()

            view._select_rectangle()

            assert view.get_rect_coords() is None
            assert view._rect_edit.text() == ""
            assert view._rect_summary_label.text() == "Область не выбрана"


class TestSettingsControllerCapturePersistence:
    """Тесты загрузки и сохранения capture-настроек."""

    def test_load_capture_settings(self) -> None:
        """Capture-настройки загружаются в модель состояния."""
        config = MagicMock(spec=ConfigManager)
        config.settings.video.fps = 30
        config.settings.video.codec = "libx264"
        config.settings.video.bitrate = "2M"
        config.settings.video.format = "mp4"
        config.settings.capture.area_type = "rect"
        config.settings.capture.window_title = "Editor"
        config.settings.capture.rect_coords = [10, 20, 300, 200]
        config.settings.output.default_path = ""
        config.settings.recent_recordings = []

        state = RecordingState()
        controller = SettingsController(state=state, config=config)

        controller.load_settings()

        assert state.capture.capture_type == CaptureType.RECT
        assert state.capture.window_title == "Editor"
        assert state.capture.rect_coords == (10, 20, 300, 200)

    def test_save_capture_settings(self) -> None:
        """Capture-настройки сохраняются обратно в конфиг."""
        config = MagicMock(spec=ConfigManager)
        config.settings.video.fps = 30
        config.settings.video.codec = "libx264"
        config.settings.video.bitrate = "2M"
        config.settings.video.format = "mp4"
        config.settings.capture.area_type = "full"
        config.settings.capture.window_title = None
        config.settings.capture.rect_coords = None
        config.settings.output.default_path = ""
        config.settings.recent_recordings = []

        state = RecordingState()
        state.capture.capture_type = CaptureType.RECT
        state.capture.window_title = "Browser"
        state.capture.rect_coords = (100, 120, 800, 600)
        controller = SettingsController(state=state, config=config)

        controller.save_settings()

        assert config.settings.capture.area_type == "rect"
        assert config.settings.capture.window_title == "Browser"
        assert config.settings.capture.rect_coords == [100, 120, 800, 600]
