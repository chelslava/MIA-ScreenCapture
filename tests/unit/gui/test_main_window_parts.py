"""Тесты связующего слоя MainWindow и сборщика UI после #164.

Закрывает покрытие вынесенных миксинов: сборка окна/вкладок
(``main_ui_builder``) и маршрутизация в ``main_window``
(connect_signals, close, toast, ffmpeg-события, readiness,
настройки, профили).
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.event_bus import RecordingEvent, RecordingEventType
from gui.main_window import MainWindow
from tests.unit.gui.test_main_window import _build_window


class _FakeGeom:
    """Геометрия экрана/окна с целочисленными размерами и позицией."""

    def __init__(
        self, width: int, height: int, x: int = 0, y: int = 0
    ) -> None:
        self._width = width
        self._height = height
        self._x = x
        self._y = y

    def x(self) -> int:
        return self._x

    def y(self) -> int:
        return self._y

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height


class _FakeScreen:
    """Экран по умолчанию для QGuiApplication."""

    def geometry(self) -> _FakeGeom:
        return _FakeGeom(1920, 1080)

    def availableGeometry(self) -> _FakeGeom:
        return _FakeGeom(1920, 1080)


class _FakeGuiApp:
    """QGuiApplication-подобная заглушка с экраном."""

    @staticmethod
    def primaryScreen() -> _FakeScreen:
        return _FakeScreen()


class _FakeNoScreenGuiApp:
    """QGuiApplication без экранов (headless-окружение)."""

    @staticmethod
    def primaryScreen() -> None:
        return None


class TestUiBuilderSetupWindow:
    """Позиционирование и размер главного окна."""

    @staticmethod
    def _make_window() -> MainWindow:
        """Окно без __init__ с заглушками геометрии и контроллера."""
        window = MainWindow.__new__(MainWindow)
        window.setMinimumSize = MagicMock()
        window.resize = MagicMock()
        window.move = MagicMock()
        window.geometry = lambda: _FakeGeom(1000, 750)
        window._settings_controller = MagicMock()
        window._settings_controller.get_window_geometry.return_value = None
        return window

    def test_setup_window_sizes_and_centers(self, monkeypatch) -> None:
        window = self._make_window()

        import gui.views.main_ui_builder as builder_module

        monkeypatch.setattr(builder_module, "QGuiApplication", _FakeGuiApp)

        MainWindow._setup_window(window)

        window.setMinimumSize.assert_called_once_with(900, 650)
        window.resize.assert_called_once_with(1000, 750)
        # Центрирование в available: (1920-1000)//2, (1080-750)//2
        window.move.assert_called_once_with(460, 165)

    def test_setup_window_without_screen_uses_default_geometry(
        self, monkeypatch
    ) -> None:
        window = self._make_window()

        import gui.views.main_ui_builder as builder_module

        monkeypatch.setattr(
            builder_module, "QGuiApplication", _FakeNoScreenGuiApp
        )
        monkeypatch.setattr(
            MainWindow,
            "_get_default_geometry",
            lambda self: _FakeGeom(800, 600),
        )

        MainWindow._setup_window(window)

        # (800-1000)//2 = -100 → окно прижато влево, но без падения
        window.move.assert_called_once_with(-100, -75)

    def test_setup_window_restores_saved_geometry(self, monkeypatch) -> None:
        """Сохранённая геометрия восстанавливается вместо центрирования."""
        window = self._make_window()
        window.setGeometry = MagicMock()
        window._settings_controller.get_window_geometry.return_value = [
            120,
            80,
            1100,
            700,
        ]

        import gui.views.main_ui_builder as builder_module

        monkeypatch.setattr(builder_module, "QGuiApplication", _FakeGuiApp)

        MainWindow._setup_window(window)

        window.setGeometry.assert_called_once_with(120, 80, 1100, 700)
        window.move.assert_not_called()

    def test_setup_window_ignores_offscreen_geometry(
        self, monkeypatch
    ) -> None:
        """Геометрия вне экрана отбрасывается — окно центрируется."""
        window = self._make_window()
        window.setGeometry = MagicMock()
        # Прямоугольник целиком правее и ниже доступной области
        window._settings_controller.get_window_geometry.return_value = [
            5000,
            5000,
            1100,
            700,
        ]

        import gui.views.main_ui_builder as builder_module

        monkeypatch.setattr(builder_module, "QGuiApplication", _FakeGuiApp)

        MainWindow._setup_window(window)

        window.setGeometry.assert_not_called()
        window.move.assert_called_once_with(460, 165)


class TestUiBuilderGetDefaultGeometry:
    """Фолбэк-геометрия при отсутствии экрана."""

    def test_returns_1920x1080_rect(self) -> None:
        window = MainWindow.__new__(MainWindow)

        rect = MainWindow._get_default_geometry(window)

        assert rect is not None


class TestUiBuilderSetupUi:
    """Полная сборка каркаса окна (сайдбар + 6 страниц + статус-бар)."""

    _PATCHED_WIDGETS = (
        "QSplitter",
        "QListWidget",
        "QListWidgetItem",
        "QPushButton",
        "QWidget",
        "QVBoxLayout",
        "QHBoxLayout",
        # QStackedWidget патчится обязательно: без этого общий auto-mock
        # из conftest копит addWidget-вызовы от других тестов сессии
        "QStackedWidget",
        "QLineEdit",
        "QLabel",
        "QComboBox",
        "QStatusBar",
        "QSize",
    )

    _PATCHED_VIEWS = (
        "CaptureView",
        "AudioView",
        "VideoView",
        "OutputView",
        "AppearanceView",
        "PostProcessingView",
        "RecordingTunablesView",
        "ReadinessCenterView",
        "RecordingsListWidget",
        "SettingsPage",
    )

    def test_setup_ui_builds_six_pages(self) -> None:
        window = MainWindow.__new__(MainWindow)
        window.setCentralWidget = MagicMock()
        window.setStatusBar = MagicMock()

        with (
            patch("gui.scheduler.scheduler_tab.SchedulerTab", MagicMock()),
            patch("gui.views.diagnostics_view.DiagnosticsView", MagicMock()),
            patch("gui.views.api_settings_view.ApiSettingsView", MagicMock()),
        ):
            self._run_setup_ui(window)

        assert window._sidebar.addItem.call_count == 6
        assert window._content_stack.addWidget.call_count == 6
        window._sidebar.setCurrentRow.assert_called_once_with(0)
        window._content_stack.setCurrentIndex.assert_called_once_with(0)
        window.setCentralWidget.assert_called_once_with(
            window._sidebar_splitter
        )
        # tabs связан с content_stack (совместимость с тестами)
        assert window.tabs is window._content_stack
        # Статус-бар собран с тремя постоянными виджетами
        assert window.status_bar.addPermanentWidget.call_count == 3

    def _run_setup_ui(self, window: MainWindow) -> None:
        from contextlib import ExitStack

        with ExitStack() as stack:
            for name in self._PATCHED_WIDGETS:
                stack.enter_context(
                    patch(f"gui.views.main_ui_builder.{name}", MagicMock())
                )
            for name in self._PATCHED_VIEWS:
                stack.enter_context(
                    patch(f"gui.views.main_ui_builder.{name}", MagicMock())
                )
            MainWindow._setup_ui(window)

    def test_tabs_property_defaults_and_setter(self) -> None:
        window = MainWindow.__new__(MainWindow)

        # До _setup_ui свойства ещё нет
        assert window.tabs is None

        stack = MagicMock()
        window.tabs = stack
        assert window._content_stack is stack


class TestMainWindowConnectSignals:
    """Маршрутизация сигналов представлений в обработчики окна."""

    def test_connect_signals_wires_views_and_ws(self) -> None:
        window = _build_window()

        with patch("gui.main_window.WebSocketClientController") as ws_cls:
            MainWindow._connect_signals(window)

        assert window._capture_view.capture_type_changed.connect.called
        assert window._capture_view.window_selected.connect.called
        assert window._capture_view.rect_selected.connect.called
        assert window._audio_view.audio_type_changed.connect.called
        assert window._audio_view.mic_device_changed.connect.called
        assert window._video_view.settings_changed.connect.called
        assert window._output_view.output_path_changed.connect.called
        assert window._appearance_view.theme_changed.connect.called
        assert window._appearance_view.language_changed.connect.called
        assert window._appearance_view.hotkeys_requested.connect.called
        assert window._appearance_view.minimize_to_tray_changed.connect.called
        assert window._appearance_view.ui_animations_changed.connect.called
        assert window._appearance_view.win11_backdrop_changed.connect.called
        assert window._api_settings_view.apply_requested.connect.called
        assert window._api_settings_view.start_requested.connect.called
        assert window._api_settings_view.stop_requested.connect.called
        assert window._api_settings_view.restart_requested.connect.called
        assert window._readiness_center_view.refresh_requested.connect.called
        assert window._readiness_center_view.details_requested.connect.called
        assert window._readiness_center_view.action_requested.connect.called
        assert window.stop_operation_finished.connect.called
        assert window.dependency_check_completed.connect.called
        assert window.readiness_refresh_completed.connect.called
        ws_cls.assert_called_once()

    def test_connect_signals_wires_ws_status_and_toasts(self) -> None:
        window = _build_window()

        with patch("gui.main_window.WebSocketClientController") as ws_cls:
            MainWindow._connect_signals(window)

        ws_controller = ws_cls.return_value
        ws_controller.status_changed.connect.assert_called_once_with(
            window._update_ws_status
        )
        ws_controller.connected.connect.assert_called_once()
        ws_controller.disconnected.connect.assert_called_once()
        ws_controller.error_occurred.connect.assert_called_once()


class TestMainWindowCloseEvent:
    """Закрытие окна: выбор действия при активной записи (#94/#90)."""

    def test_close_without_recording_saves_and_accepts(self) -> None:
        window = _build_window()
        window.close_requested = MagicMock()
        window._thread_tracker = MagicMock()
        event = MagicMock()
        event.isAccepted.return_value = True

        MainWindow.closeEvent(window, event)

        window.close_requested.emit.assert_called_once_with(event)
        window._settings_controller.save_settings.assert_called_once()
        window._update_timer.stop.assert_called_once()
        window._thread_tracker.join_all.assert_called_once()
        event.accept.assert_called_once()

    def test_close_while_recording_cancel_ignores_event(self) -> None:
        window = _build_window()
        window._state.start_recording(__import__("pathlib").Path("D:/a.mp4"))
        window._ask_close_action_while_recording = MagicMock(
            return_value="cancel"
        )
        window.close_requested = MagicMock()
        event = MagicMock()

        MainWindow.closeEvent(window, event)

        event.ignore.assert_called_once()
        window.close_requested.emit.assert_not_called()

    def test_close_while_recording_tray_forces_minimize(self) -> None:
        window = _build_window()
        window._state.start_recording(__import__("pathlib").Path("D:/a.mp4"))
        window._ask_close_action_while_recording = MagicMock(
            return_value="tray"
        )
        window.close_requested = MagicMock()
        event = MagicMock()

        MainWindow.closeEvent(window, event)

        window.close_requested.emit.assert_called_once_with(
            {"event": event, "force_minimize_to_tray": True}
        )
        event.accept.assert_not_called()

    def test_close_while_recording_stop_and_exit_continues(self) -> None:
        window = _build_window()
        window._state.start_recording(__import__("pathlib").Path("D:/a.mp4"))
        window._ask_close_action_while_recording = MagicMock(
            return_value="stop_and_exit"
        )
        window._stop_recording = MagicMock()
        window.close_requested = MagicMock()
        window._thread_tracker = MagicMock()
        event = MagicMock()
        event.isAccepted.return_value = True

        MainWindow.closeEvent(window, event)

        window._stop_recording.assert_called_once()
        window._settings_controller.save_settings.assert_called_once()
        event.accept.assert_called_once()

    def test_close_ignored_by_external_handler(self) -> None:
        window = _build_window()
        window.close_requested = MagicMock()
        event = MagicMock()
        event.isAccepted.return_value = False

        MainWindow.closeEvent(window, event)

        window._settings_controller.save_settings.assert_not_called()
        event.accept.assert_not_called()

    def test_ask_close_dialog_returns_cancel_by_default(self) -> None:
        window = _build_window()
        box = MagicMock()
        tray_button, exit_button, cancel_button = (
            MagicMock(),
            MagicMock(),
            MagicMock(),
        )
        box.addButton.side_effect = [tray_button, exit_button, cancel_button]
        box.clickedButton.return_value = MagicMock()  # не одна из кнопок

        with patch("gui.main_window.QMessageBox", MagicMock(return_value=box)):
            choice = MainWindow._ask_close_action_while_recording(window)

        assert choice == "cancel"

    @pytest.mark.parametrize(
        "clicked,expected",
        [
            ("tray_button", "tray"),
            ("exit_button", "stop_and_exit"),
            ("cancel_button", "cancel"),
        ],
    )
    def test_ask_close_dialog_button_mapping(
        self, clicked: str, expected: str
    ) -> None:
        window = _build_window()
        box = MagicMock()
        buttons = {
            "tray_button": MagicMock(),
            "exit_button": MagicMock(),
            "cancel_button": MagicMock(),
        }
        box.addButton.side_effect = list(buttons.values())
        box.clickedButton.return_value = buttons[clicked]

        with patch("gui.main_window.QMessageBox", MagicMock(return_value=box)):
            choice = MainWindow._ask_close_action_while_recording(window)

        assert choice == expected


class TestMainWindowToasts:
    """Всплывающие уведомления в статус-баре."""

    def test_show_toast_inserts_label_and_starts_timer(self) -> None:
        window = _build_window()
        window._toast_timer = MagicMock()
        window._toast_timer.isActive.return_value = True

        with patch("gui.main_window.QLabel") as label_cls:
            MainWindow._show_toast(window, "Проверка", 5000)

        label_cls.assert_called_once_with("Проверка")
        window.status_bar.insertWidget.assert_called_once()
        window._toast_timer.stop.assert_called_once()
        window._toast_timer.setSingleShot.assert_called_once_with(True)
        window._toast_timer.start.assert_called_once_with(5000)

    def test_hide_toast_clears_message(self) -> None:
        window = _build_window()

        MainWindow._hide_toast(window)

        window.status_bar.clearMessage.assert_called_once()


class _FakeBus:
    """EventBus-подобная заглушка, сохраняющая подписки."""

    def __init__(self) -> None:
        self.subscribers: dict[RecordingEventType, list] = {}

    def subscribe(self, event_type, handler) -> None:
        self.subscribers.setdefault(event_type, []).append(handler)

    def dispatch(self, event: RecordingEvent) -> None:
        for handler in self.subscribers.get(event.event_type, []):
            handler(event)


class TestMainWindowFfmpegEvents:
    """Подписка на события FFmpeg через шину (#114)."""

    @staticmethod
    def _make_window() -> MainWindow:
        window = _build_window()
        window._show_toast = MagicMock()
        window._show_non_modal_error = MagicMock()
        return window

    def test_recovery_event_shows_short_toast(self) -> None:
        window = self._make_window()
        bus = _FakeBus()
        MainWindow._subscribe_to_ffmpeg_events(window, bus)

        bus.dispatch(
            RecordingEvent(
                event_type=RecordingEventType.WARNING,
                payload={"type": "ffmpeg_recovery", "message": "Восстановлен"},
            )
        )

        window._show_toast.assert_called_once_with(
            "Восстановлен", duration_ms=3000
        )
        window._show_non_modal_error.assert_not_called()

    def test_crash_event_shows_toast_and_error(self) -> None:
        window = self._make_window()
        bus = _FakeBus()
        MainWindow._subscribe_to_ffmpeg_events(window, bus)

        bus.dispatch(
            RecordingEvent(
                event_type=RecordingEventType.WARNING,
                payload={"type": "ffmpeg_crash", "message": "Падение"},
            )
        )

        window._show_toast.assert_called_once_with("Падение", duration_ms=5000)
        window._show_non_modal_error.assert_called_once_with("Падение")

    def test_disk_space_critical_shows_toast_and_error(self) -> None:
        window = self._make_window()
        bus = _FakeBus()
        MainWindow._subscribe_to_ffmpeg_events(window, bus)

        bus.dispatch(
            RecordingEvent(
                event_type=RecordingEventType.WARNING,
                payload={"type": "disk_space_critical"},
            )
        )

        window._show_toast.assert_called_once_with(
            "Критическая нехватка места на диске", duration_ms=5000
        )
        window._show_non_modal_error.assert_called_once_with(
            "Критическая нехватка места на диске"
        )

    def test_generic_error_event_uses_payload_message(self) -> None:
        window = self._make_window()
        bus = _FakeBus()
        MainWindow._subscribe_to_ffmpeg_events(window, bus)

        bus.dispatch(
            RecordingEvent(
                event_type=RecordingEventType.ERROR,
                payload={"message": "Сбой кодировщика"},
            )
        )

        window._show_toast.assert_called_once_with(
            "Сбой кодировщика", duration_ms=5000
        )
        window._show_non_modal_error.assert_called_once_with(
            "Сбой кодировщика"
        )

    def test_generic_error_event_fallback_text(self) -> None:
        window = self._make_window()
        bus = _FakeBus()
        MainWindow._subscribe_to_ffmpeg_events(window, bus)

        bus.dispatch(
            RecordingEvent(event_type=RecordingEventType.ERROR, payload={})
        )

        window._show_non_modal_error.assert_called_once_with(
            "Произошла ошибка записи"
        )

    def test_info_events_are_ignored(self) -> None:
        window = self._make_window()
        bus = _FakeBus()
        MainWindow._subscribe_to_ffmpeg_events(window, bus)

        bus.dispatch(
            RecordingEvent(
                event_type=RecordingEventType.STARTED,
                payload={"type": "ffmpeg_recovery"},
            )
        )

        window._show_toast.assert_not_called()


class TestMainWindowReadinessRouting:
    """Readiness-центр: summary и one-click действия."""

    def test_refresh_summary_error_state_without_capture(self) -> None:
        window = _build_window()
        window._build_capture_settings_from_views = MagicMock(
            return_value=None
        )

        MainWindow._refresh_readiness_summary(window)

        window._readiness_center_view.set_error_state.assert_called_once()

    def test_refresh_summary_dispatches_request(self) -> None:
        window = _build_window()
        from core.readiness import ReadinessSnapshot

        window._build_capture_settings_from_views = MagicMock(
            return_value=MagicMock()
        )
        window._readiness_service.evaluate.return_value = ReadinessSnapshot()

        MainWindow._refresh_readiness_summary(window)

        window._readiness_center_view.set_loading_state.assert_called_once()
        assert window._readiness_request_id >= 1

    def test_show_readiness_details_switches_tab_and_runs_diagnostics(
        self,
    ) -> None:
        window = _build_window()
        window._diagnostics_view = MagicMock()
        window._run_diagnostics = MagicMock()

        MainWindow._show_readiness_details(window)

        window._sidebar.setCurrentRow.assert_called_once_with(4)
        window._run_diagnostics.assert_called_once()

    def test_diagnostics_fix_routes_to_readiness_action(self) -> None:
        window = _build_window()
        window._handle_readiness_action = MagicMock()

        MainWindow._on_diagnostics_fix(window, "refresh_windows")

        window._handle_readiness_action.assert_called_once_with(
            "refresh_windows"
        )

    @pytest.mark.parametrize(
        "action_key",
        [
            "refresh_windows",
            "focus_capture_window",
            "refresh_audio_devices",
            "focus_microphone_selection",
            "API сервер",
        ],
    )
    def test_handle_readiness_action_routes(self, action_key: str) -> None:
        window = _build_window()

        MainWindow._handle_readiness_action(window, action_key)

    def test_handle_readiness_action_choose_output_path(self) -> None:
        window = _build_window()
        config_mock = MagicMock()

        widgets_module = sys.modules["PyQt6.QtWidgets"]
        monkeypatched = patch.object(
            widgets_module.QFileDialog,
            "getExistingDirectory",
            create=True,
            return_value="D:/recordings",
        )
        with (
            monkeypatched,
            patch("gui.main_window.get_config", return_value=config_mock),
        ):
            MainWindow._handle_readiness_action(window, "choose_output_path")

        assert config_mock.settings.output.default_path == "D:/recordings"
        config_mock.save.assert_called_once()

    def test_apply_readiness_snapshot_blocked_stops_start(self) -> None:
        window = _build_window()
        snapshot = MagicMock()
        snapshot.is_ready = False
        snapshot.summary_text.return_value = "нет места на диске"

        result = MainWindow._apply_readiness_snapshot(window, snapshot)

        assert result is False
        window.status_label.setText.assert_called_once_with(
            "Не готово к записи"
        )
        window._run_diagnostics.assert_called_once()

    def test_apply_readiness_snapshot_ready_with_warning(self) -> None:
        window = _build_window()
        from core.readiness import ReadinessSnapshot

        snapshot = ReadinessSnapshot()

        result = MainWindow._apply_readiness_snapshot(window, snapshot)

        assert result is True


class TestMainWindowSettingsHandlers:
    """Обработчики изменений настроек из AppearanceView."""

    def test_theme_changed_without_app(self) -> None:
        window = _build_window()

        widgets_module = sys.modules["PyQt6.QtWidgets"]
        monkeypatched = patch.object(
            widgets_module.QApplication,
            "instance",
            create=True,
            return_value=None,
        )
        with monkeypatched:
            MainWindow._on_theme_changed(window, "dark")

        window._settings_controller.set_theme_mode.assert_called_once_with(
            "dark"
        )

    def test_language_changed(self) -> None:
        window = _build_window()

        MainWindow._on_language_changed(window, "en")

        window._settings_controller.set_language.assert_called_once_with("en")

    @pytest.mark.parametrize(
        "status,expected_label",
        [
            ("connected", "● Connected"),
            ("connecting", "● Connecting..."),
            ("disconnected", "● Disconnected"),
            ("reconnecting", "◌ Reconnecting..."),
            ("error", "● Error"),
            ("unknown", "● Disconnected"),
        ],
    )
    def test_update_ws_status_labels(
        self, status: str, expected_label: str
    ) -> None:
        window = _build_window()

        MainWindow._update_ws_status(window, status)

        window._ws_status_label.setText.assert_called_once_with(expected_label)

    def test_post_processing_changed_saves_config(self) -> None:
        window = _build_window()
        window._post_processing_view = MagicMock()
        new_settings = SimpleNamespace(format="mp4")
        window._post_processing_view.get_settings.return_value = new_settings
        config_mock = MagicMock()

        with patch("gui.main_window.get_config", return_value=config_mock):
            MainWindow._on_post_processing_changed(window)

        assert config_mock.settings.post_processing is new_settings
        config_mock.save.assert_called_once()

    def test_recording_tunables_changed_saves_config(self) -> None:
        window = _build_window()
        window._recording_tunables_view = MagicMock()
        new_tunables = SimpleNamespace(enable_frame_skip=False)
        window._recording_tunables_view.get_settings.return_value = (
            new_tunables
        )
        config_mock = MagicMock()

        with patch("gui.main_window.get_config", return_value=config_mock):
            MainWindow._on_recording_tunables_changed(window)

        assert config_mock.settings.recording_tunables is new_tunables
        config_mock.save.assert_called_once()

    def test_minimize_to_tray_changed(self) -> None:
        window = _build_window()

        MainWindow._on_minimize_to_tray_changed(window, True)

        window._settings_controller.set_minimize_to_tray.assert_called_once_with(
            True
        )

    def test_capture_type_changed_updates_state_and_readiness(self) -> None:
        window = _build_window()
        window._refresh_readiness_summary = MagicMock()

        MainWindow._on_capture_type_changed(window, "full")

        window._settings_controller.update_capture_settings.assert_called_once_with(
            capture_type="full"
        )
        window._refresh_readiness_summary.assert_called_once_with()

    def test_window_selected_updates_state_and_readiness(self) -> None:
        window = _build_window()
        window._refresh_readiness_summary = MagicMock()

        MainWindow._on_window_selected(window, "Блокнот")

        window._settings_controller.update_capture_settings.assert_called_once_with(
            window_title="Блокнот"
        )
        window._refresh_readiness_summary.assert_called_once_with()

    def test_rect_selected_updates_state_and_readiness(self) -> None:
        window = _build_window()
        window._refresh_readiness_summary = MagicMock()

        MainWindow._on_rect_selected(window, (1, 2, 3, 4))

        window._settings_controller.update_capture_settings.assert_called_once_with(
            rect_coords=(1, 2, 3, 4)
        )
        window._refresh_readiness_summary.assert_called_once_with()

    def test_audio_type_changed_updates_state_and_readiness(self) -> None:
        window = _build_window()
        window._refresh_readiness_summary = MagicMock()

        MainWindow._on_audio_type_changed(window, "mic")

        window._settings_controller.update_audio_settings.assert_called_once_with(
            audio_type="mic"
        )
        window._refresh_readiness_summary.assert_called_once_with()

    def test_mic_device_changed_updates_state_and_readiness(self) -> None:
        window = _build_window()
        window._refresh_readiness_summary = MagicMock()

        MainWindow._on_mic_device_changed(window, 2)

        window._settings_controller.update_audio_settings.assert_called_once_with(
            mic_device_index=2
        )
        window._refresh_readiness_summary.assert_called_once_with()

    def test_output_path_changed_updates_state_and_readiness(self) -> None:
        window = _build_window()
        window._refresh_readiness_summary = MagicMock()

        MainWindow._on_output_path_changed(window, "D:/out")

        window._settings_controller.update_output_settings.assert_called_once_with(
            output_path="D:/out"
        )
        window._refresh_readiness_summary.assert_called_once_with()

    def test_video_settings_changed_updates_state_and_format(self) -> None:
        window = _build_window()
        settings = SimpleNamespace(
            fps=60, codec="h264", bitrate="8M", format="mp4"
        )

        MainWindow._on_video_settings_changed(window, settings)

        window._settings_controller.update_video_settings.assert_called_once_with(
            fps=60, codec="h264", bitrate="8M", format="mp4"
        )
        window._output_view.set_default_format.assert_called_once_with("mp4")


class TestMainWindowProfiles:
    """Инициализация и применение профилей записи."""

    def test_bind_application_facade(self) -> None:
        window = _build_window()
        facade = MagicMock()

        MainWindow.bind_application_facade(window, facade)

        assert window._application_facade is facade

    def test_init_profiles_without_combo_is_noop(self) -> None:
        # _build_window создаёт окно через __new__ без _profile_combo
        window = _build_window()

        MainWindow._init_profiles(window)  # не должно упасть

    def test_init_profiles_with_combo(self) -> None:
        window = _build_window()
        window._profile_combo = MagicMock()
        window._profile_gui_controller = MagicMock()

        MainWindow._init_profiles(window)

        window._profile_gui_controller.init_profiles.assert_called_once_with(
            window._profile_combo
        )

    def test_profile_combo_changed_out_of_range_is_noop(self) -> None:
        window = _build_window()
        window._profile_combo = MagicMock()
        window._profile_gui_controller = MagicMock()

        MainWindow._on_profile_combo_changed(window, -1)

        window._profile_gui_controller.on_profile_combo_changed.assert_not_called()

    def test_profile_combo_changed_dispatches(self) -> None:
        window = _build_window()
        window._profile_combo = MagicMock()
        window._profile_gui_controller = MagicMock()

        MainWindow._on_profile_combo_changed(window, 1)

        window._profile_gui_controller.on_profile_combo_changed.assert_called_once_with(
            1, window._profile_combo, window.apply_profile_settings
        )

    def test_open_profile_dialog_dispatches(self) -> None:
        window = _build_window()
        window._profile_combo = MagicMock()
        window._profile_gui_controller = MagicMock()

        MainWindow._open_profile_dialog(window)

        window._profile_gui_controller.open_profile_dialog.assert_called_once_with(
            window, window._profile_combo, window.apply_profile_settings
        )

    def test_apply_profile_settings_passes_views(self) -> None:
        window = _build_window()
        window._profile_gui_controller = MagicMock()
        profile = MagicMock()

        MainWindow.apply_profile_settings(window, profile)

        window._profile_gui_controller.apply_profile_settings.assert_called_once_with(
            profile,
            video_view=window._video_view,
            audio_view=window._audio_view,
            capture_view=window._capture_view,
            state=window._state,
            combo=None,
            status_bar=window.status_bar,
        )
