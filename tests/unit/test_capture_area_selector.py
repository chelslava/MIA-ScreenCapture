"""
Тесты графического выбора области захвата.
"""

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from config import ConfigManager
from gui.controllers.settings_controller import SettingsController
from gui.models.recording_state import CaptureType, RecordingState
from gui.views.area_selector import (
    AreaSelectorDialog,
    describe_rect,
    format_rect_coords,
    is_valid_selection,
    move_rect,
    normalize_rect_coords,
    point_in_rect,
    point_in_resize_handle,
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

    def test_point_in_rect(self) -> None:
        """Точка внутри области определяется корректно."""
        assert point_in_rect((50, 60), (10, 20, 100, 120))

    def test_point_in_resize_handle(self) -> None:
        """Правый нижний маркер resize распознаётся по координатам."""
        assert point_in_resize_handle((100, 120), (10, 20, 100, 120))

    def test_is_valid_selection(self) -> None:
        """Слишком маленькая область считается невалидной."""
        assert not is_valid_selection((0, 0, 3, 3))
        assert is_valid_selection((0, 0, 10, 10))


class _FakeMouseEvent:
    """Упрощённое mouse event для тестов selector-а."""

    def __init__(
        self,
        x: int,
        y: int,
        button: object,
        use_position: bool = False,
    ) -> None:
        self._x = x
        self._y = y
        self._button = button
        if use_position:
            self.position = lambda: SimpleNamespace(  # noqa: B023
                x=lambda: self._x,
                y=lambda: self._y,
            )

    def button(self) -> object:
        """Вернуть кнопку мыши."""
        return self._button

    def pos(self) -> SimpleNamespace:
        """Вернуть координаты через совместимый pos()."""
        return SimpleNamespace(x=lambda: self._x, y=lambda: self._y)


class _FakeKeyEvent:
    """Упрощённое key event для тестов selector-а."""

    def __init__(self, key: object) -> None:
        self._key = key

    def key(self) -> object:
        """Вернуть код клавиши."""
        return self._key


class TestAreaSelectorDialog:
    """Тесты поведения диалога выбора области."""

    def _create_dialog(self) -> AreaSelectorDialog:
        """Создать selector с безопасно замоканным окном."""
        with (
            patch.object(
                AreaSelectorDialog,
                "_get_screen_bounds",
                return_value=(0, 0, 1920, 1080),
            ),
            patch.object(AreaSelectorDialog, "_setup_window"),
        ):
            dialog = AreaSelectorDialog()
        dialog.update = MagicMock()
        dialog.accept = MagicMock()
        dialog.reject = MagicMock()
        dialog.selection_completed = MagicMock()
        return dialog

    def test_select_area_returns_selection_for_accepted_dialog(self) -> None:
        """select_area возвращает выбранный rect после успешного confirm."""

        def fake_init(
            self,
            initial_rect=None,
            parent=None,
        ) -> None:
            self._selection = initial_rect

        with (
            patch.object(AreaSelectorDialog, "__init__", fake_init),
            patch.object(
                AreaSelectorDialog, "exec", return_value=1, create=True
            ),
            patch.object(
                AreaSelectorDialog,
                "get_selected_rect",
                return_value=(10, 20, 100, 200),
            ),
        ):
            assert AreaSelectorDialog.select_area(
                initial_rect=(1, 2, 3, 4)
            ) == (10, 20, 100, 200)

    def test_get_selected_rect_returns_none_for_too_small_rect(self) -> None:
        """Невалидная область не должна считаться выбранной."""
        dialog = self._create_dialog()
        dialog._selection = (1, 1, 4, 4)
        assert dialog.get_selected_rect() is None

    def test_event_point_supports_position_api(self) -> None:
        """Selector читает координаты из position() в стиле Qt6."""
        dialog = self._create_dialog()
        event = _FakeMouseEvent(30, 40, button=1, use_position=True)
        assert dialog._event_point(event) == (30, 40)

    def test_mouse_press_move_and_release_create_selection(self) -> None:
        """Последовательность drag создаёт и фиксирует область."""
        dialog = self._create_dialog()
        left_button = object()
        qt_patch = SimpleNamespace(
            MouseButton=SimpleNamespace(LeftButton=left_button)
        )

        with patch("gui.views.area_selector.Qt", qt_patch):
            dialog.mousePressEvent(_FakeMouseEvent(10, 20, left_button))
            dialog.mouseMoveEvent(_FakeMouseEvent(110, 220, left_button))
            dialog.mouseReleaseEvent(_FakeMouseEvent(110, 220, left_button))

        assert dialog.get_selected_rect() == (10, 20, 110, 220)
        assert dialog.update.called

    def test_mouse_press_inside_selection_switches_to_move_mode(self) -> None:
        """Клик внутри рамки включает режим перемещения."""
        dialog = self._create_dialog()
        dialog._selection = (10, 20, 110, 220)
        left_button = object()
        qt_patch = SimpleNamespace(
            MouseButton=SimpleNamespace(LeftButton=left_button)
        )

        with patch("gui.views.area_selector.Qt", qt_patch):
            dialog.mousePressEvent(_FakeMouseEvent(30, 50, left_button))

        assert dialog._drag_mode == "move"
        assert dialog._move_offset == (20, 30)

    def test_mouse_double_click_accepts_when_inside_selection(self) -> None:
        """Двойной клик внутри области подтверждает выбор."""
        dialog = self._create_dialog()
        dialog._selection = (10, 20, 110, 220)

        dialog.mouseDoubleClickEvent(_FakeMouseEvent(50, 70, button=1))

        dialog.selection_completed.emit.assert_called_once_with(
            (10, 20, 110, 220)
        )
        dialog.accept.assert_called_once()

    def test_key_press_handles_escape_and_enter(self) -> None:
        """Escape отменяет, Enter подтверждает выбранную область."""
        dialog = self._create_dialog()
        dialog._selection = (10, 20, 110, 220)
        qt_patch = SimpleNamespace(
            Key=SimpleNamespace(
                Key_Escape="esc", Key_Return="ret", Key_Enter="ent"
            )
        )

        with patch("gui.views.area_selector.Qt", qt_patch):
            dialog.keyPressEvent(_FakeKeyEvent("esc"))
            dialog.keyPressEvent(_FakeKeyEvent("ret"))

        dialog.reject.assert_called_once()
        dialog.selection_completed.emit.assert_called_once_with(
            (10, 20, 110, 220)
        )
        dialog.accept.assert_called_once()


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
