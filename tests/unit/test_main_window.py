"""
Unit тесты для MainWindow
=========================

Тестирует функциональность главного окна с реальной логикой.

Примечание: PyQt6 мокируется в conftest.py для всех тестов.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core.readiness import ReadinessIssue, ReadinessSnapshot
from core.recording_types import AudioMode, CaptureMode
from gui.desktop_actions import DesktopActionId
from gui.models.recording_state import (
    AudioSettings,
    CaptureSettings,
    RecordingState,
    VideoSettings,
)


def _build_window():
    """Создать MainWindow без запуска тяжёлого __init__."""
    from gui.main_window import MainWindow

    window = MainWindow.__new__(MainWindow)
    window._state = RecordingState()
    window._settings_controller = MagicMock()
    window._recording_controller = MagicMock()
    window._readiness_service = MagicMock(
        evaluate=MagicMock(return_value=ReadinessSnapshot())
    )
    window._capture_view = MagicMock()
    window._audio_view = MagicMock()
    window._video_view = MagicMock()
    window._output_view = MagicMock()
    window._api_settings_view = MagicMock()
    window._application_facade = None
    window._ws_controller = None
    window.start_btn = MagicMock()
    window.stop_btn = MagicMock()
    window.pause_btn = MagicMock()
    window._open_latest_btn = MagicMock()
    window._open_folder_btn = MagicMock()
    window._open_file_btn = MagicMock()
    window._clear_list_btn = MagicMock()
    window.status_label = MagicMock()
    window.time_label = MagicMock()
    window.status_bar = MagicMock()
    window._ws_status_label = MagicMock()
    window.tabs = MagicMock()
    window._registered_shortcuts = {}
    window._tab_navigation_order = []
    window.recording_started = MagicMock()
    window.recording_stopped = MagicMock()
    window.recording_paused = MagicMock()
    window.recording_resumed = MagicMock()
    window.error_occurred = MagicMock()
    window.recordings_list = MagicMock()
    window._recordings_filter_input = MagicMock()
    window._diagnostics_view = MagicMock()
    window._recording_indicator = MagicMock()
    window._run_diagnostics = MagicMock()
    window._update_timer = MagicMock()
    window.dependency_check_completed = MagicMock()
    window._stop_operation_in_progress = False
    window._stop_operation_thread = None
    window.stop_operation_finished = MagicMock()
    return window


class TestMainWindowBasics:
    """Базовые тесты MainWindow."""

    def test_main_window_module_exists(self) -> None:
        """Проверка существования модуля."""
        from gui import main_window

        assert main_window is not None

    def test_main_window_class_exists(self) -> None:
        """Проверка существования класса MainWindow."""
        from gui.main_window import MainWindow

        assert MainWindow is not None


class TestMainWindowRecordingState:
    """Тесты модели состояния записи."""

    def test_recording_state_initial_values(self) -> None:
        """Проверка начальных значений состояния."""
        from gui.models.recording_state import RecordingState, RecordingStatus

        state = RecordingState()

        assert state.status == RecordingStatus.IDLE
        assert not state.is_recording()
        assert not state.is_paused()
        assert state.is_idle()

    def test_recording_state_start_recording(self) -> None:
        """Проверка начала записи."""
        from gui.models.recording_state import RecordingState, RecordingStatus

        state = RecordingState()
        state.start_recording(Path("/tmp/test.mp4"))

        assert state.is_recording()
        assert state.status == RecordingStatus.RECORDING
        assert state.current_output == Path("/tmp/test.mp4")

    def test_recording_state_pause_recording(self) -> None:
        """Проверка паузы записи."""
        from gui.models.recording_state import RecordingState, RecordingStatus

        state = RecordingState()
        state.start_recording(Path("/tmp/test.mp4"))
        state.pause_recording()

        assert state.is_paused()
        assert state.status == RecordingStatus.PAUSED

    def test_recording_state_resume_recording(self) -> None:
        """Проверка возобновления записи."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        state.start_recording(Path("/tmp/test.mp4"))
        state.pause_recording()
        state.resume_recording()

        assert state.is_recording()
        assert not state.is_paused()

    def test_recording_state_stop_recording(self) -> None:
        """Проверка остановки записи."""
        from gui.models.recording_state import RecordingState, RecordingStatus

        state = RecordingState()
        state.start_recording(Path("/tmp/test.mp4"))
        state.stop_recording()

        assert state.is_idle()
        assert state.status == RecordingStatus.IDLE

    def test_recording_state_cannot_pause_when_idle(self) -> None:
        """Проверка невозможности паузы без записи."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        state.pause_recording()  # Не должно иметь эффекта

        assert state.is_idle()

    def test_recording_state_cannot_resume_when_not_paused(self) -> None:
        """Проверка невозможности возобновления без паузы."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        state.start_recording(Path("/tmp/test.mp4"))
        state.resume_recording()  # Не должно иметь эффекта

        assert state.is_recording()


class TestMainWindowStateTransitionsParameterized:
    """Параметризованные тесты переходов состояний."""

    @pytest.mark.parametrize(
        "initial_state,action,expected_state",
        [
            ("idle", "start", "recording"),
            ("recording", "stop", "idle"),
            ("recording", "pause", "paused"),
            ("paused", "resume", "recording"),
            ("paused", "stop", "idle"),
        ],
    )
    def test_state_transitions(
        self, initial_state: str, action: str, expected_state: str
    ) -> None:
        """Проверка переходов между состояниями."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()

        # Устанавливаем начальное состояние
        if initial_state == "recording":
            state.start_recording(Path("/tmp/test.mp4"))
        elif initial_state == "paused":
            state.start_recording(Path("/tmp/test.mp4"))
            state.pause_recording()

        # Выполняем действие
        if action == "start":
            state.start_recording(Path("/tmp/test.mp4"))
        elif action == "stop":
            state.stop_recording()
        elif action == "pause":
            state.pause_recording()
        elif action == "resume":
            state.resume_recording()

        # Проверяем ожидаемое состояние
        if expected_state == "idle":
            assert state.is_idle()
        elif expected_state == "recording":
            assert state.is_recording()
            assert not state.is_paused()
        elif expected_state == "paused":
            assert state.is_paused()


class TestMainWindowButtonStates:
    """Тесты состояний кнопок."""

    @pytest.mark.parametrize(
        "is_recording,is_paused,start_enabled,stop_enabled,pause_enabled",
        [
            (False, False, True, False, False),  # idle
            (True, False, False, True, True),  # recording
            (True, True, False, True, True),  # paused
        ],
    )
    def test_button_states_by_recording_state(
        self,
        is_recording: bool,
        is_paused: bool,
        start_enabled: bool,
        stop_enabled: bool,
        pause_enabled: bool,
    ) -> None:
        """Проверка состояний кнопок по состоянию записи."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()

        if is_recording:
            state.start_recording(Path("/tmp/test.mp4"))
            if is_paused:
                state.pause_recording()

        # Логика доступности кнопок
        actual_start_enabled = state.is_idle()
        actual_stop_enabled = state.is_recording() or state.is_paused()
        actual_pause_enabled = state.is_recording() or state.is_paused()

        assert actual_start_enabled == start_enabled
        assert actual_stop_enabled == stop_enabled
        assert actual_pause_enabled == pause_enabled


class TestMainWindowStatusText:
    """Тесты текста статуса."""

    @pytest.mark.parametrize(
        "is_recording,is_paused,expected_text",
        [
            (False, False, "Готов"),
            (True, False, "Запись"),
            (True, True, "Пауза"),
        ],
    )
    def test_status_text_by_state(
        self, is_recording: bool, is_paused: bool, expected_text: str
    ) -> None:
        """Проверка текста статуса по состоянию."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()

        if is_recording:
            state.start_recording(Path("/tmp/test.mp4"))
            if is_paused:
                state.pause_recording()

        # Логика формирования текста статуса
        if state.is_paused():
            status_text = "Пауза"
        elif state.is_recording():
            status_text = "Запись"
        else:
            status_text = "Готов"

        assert status_text == expected_text


class TestMainWindowPauseButtonText:
    """Тесты текста кнопки паузы."""

    @pytest.mark.parametrize(
        "is_paused,expected_text",
        [
            (False, "Пауза"),
            (True, "Продолжить"),
        ],
    )
    def test_pause_button_text(
        self, is_paused: bool, expected_text: str
    ) -> None:
        """Проверка текста кнопки паузы."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        state.start_recording(Path("/tmp/test.mp4"))

        if is_paused:
            state.pause_recording()

        pause_text = "Продолжить" if state.is_paused() else "Пауза"
        assert pause_text == expected_text


class TestMainWindowRecentRecordings:
    """Тесты списка последних записей."""

    def test_add_recent_recording(self) -> None:
        """Проверка добавления недавней записи."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        state.add_recent_recording(Path("/tmp/test1.mp4"), 1024)

        assert len(state.recent_recordings) == 1
        assert state.recent_recordings[0].path == Path("/tmp/test1.mp4")
        assert state.recent_recordings[0].size == 1024

    def test_recent_recordings_limit(self) -> None:
        """Проверка ограничения списка недавних записей."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()

        # Добавляем 25 записей
        for i in range(25):
            state.add_recent_recording(Path(f"/tmp/test{i}.mp4"), 1024)

        # Должно остаться только 20
        assert len(state.recent_recordings) == 20

    def test_recent_recordings_order(self) -> None:
        """Проверка порядка недавних записей (новые в начале)."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        state.add_recent_recording(Path("/tmp/first.mp4"), 1024)
        state.add_recent_recording(Path("/tmp/second.mp4"), 2048)

        assert state.recent_recordings[0].path == Path("/tmp/second.mp4")
        assert state.recent_recordings[1].path == Path("/tmp/first.mp4")


class TestMainWindowRecentRecordingsFilter:
    """Тесты фильтрации списка последних записей."""

    @pytest.mark.parametrize(
        "filename,date_text,filter_text,expected",
        [
            ("capture_2026-03-28.mp4", "2026-03-28", "", True),
            ("capture_2026-03-28.mp4", "2026-03-28", "capture", True),
            ("capture_2026-03-28.mp4", "2026-03-28", "2026-03", True),
            ("capture_2026-03-28.mp4", "2026-03-28", "CAPTURE", True),
            ("capture_2026-03-28.mp4", "2026-03-28", "audio", False),
        ],
    )
    def test_recording_matches_filter(
        self,
        filename: str,
        date_text: str,
        filter_text: str,
        expected: bool,
    ) -> None:
        """Фильтр должен работать без учета регистра."""
        from gui.main_window import MainWindow

        assert (
            MainWindow._recording_matches_filter(
                filename, date_text, filter_text
            )
            is expected
        )


class TestMainWindowOutputPathFromApi:
    """Тесты разрешения output_path, пришедшего из API."""

    def test_resolve_requested_output_path_adds_extension(self) -> None:
        """Путь без расширения должен дополняться форматом видео."""
        from gui.main_window import MainWindow

        fake_window = MainWindow.__new__(MainWindow)
        fake_window._settings_controller = type(
            "_FakeSettingsController",
            (),
            {"get_output_path": staticmethod(lambda: Path("default.mp4"))},
        )()

        result = MainWindow._resolve_requested_output_path(
            fake_window, "D:/Records/custom_name", "mp4"
        )

        assert str(result).endswith("custom_name.mp4")


class TestMainWindowOutputFilename:
    """Тесты генерации имени выходного файла."""

    def test_get_output_filename_format(self) -> None:
        """Проверка формата имени выходного файла."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        filename = state.get_output_filename()

        # Должен содержать timestamp и расширение
        assert filename.startswith("recording_")
        assert filename.endswith(".mp4")

    def test_get_output_filename_with_custom_format(self) -> None:
        """Проверка имени файла с кастомным форматом."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        state.video.format = "avi"
        filename = state.get_output_filename()

        assert filename.endswith(".avi")


class TestMainWindowVideoSettings:
    """Тесты настроек видео."""

    def test_default_video_settings(self) -> None:
        """Проверка настроек видео по умолчанию."""
        from gui.models.recording_state import VideoSettings

        settings = VideoSettings()

        assert settings.fps == 30
        assert settings.codec == "libx264"
        assert settings.bitrate == "2M"
        assert settings.format == "mp4"

    @pytest.mark.parametrize(
        "fps,codec,bitrate,format",
        [
            (60, "libx265", "5M", "mkv"),
            (24, "libvpx-vp9", "1M", "webm"),
            (120, "libx264", "10M", "mp4"),
        ],
    )
    def test_custom_video_settings(
        self, fps: int, codec: str, bitrate: str, format: str
    ) -> None:
        """Проверка кастомных настроек видео."""
        from gui.models.recording_state import VideoSettings

        settings = VideoSettings(
            fps=fps, codec=codec, bitrate=bitrate, format=format
        )

        assert settings.fps == fps
        assert settings.codec == codec
        assert settings.bitrate == bitrate
        assert settings.format == format


class TestMainWindowAudioSettings:
    """Тесты настроек аудио."""

    def test_default_audio_settings(self) -> None:
        """Проверка настроек аудио по умолчанию."""
        from core.recording_types import AudioMode
        from gui.models.recording_state import AudioSettings

        settings = AudioSettings()

        assert settings.audio_type == AudioMode.NONE
        assert settings.mic_device_index is None

    @pytest.mark.parametrize(
        "audio_type",
        ["NONE", "MIC", "SYSTEM", "BOTH"],
    )
    def test_audio_type_enum(self, audio_type: str) -> None:
        """Проверка типов источников аудио."""
        from core.recording_types import AudioMode

        assert hasattr(AudioMode, audio_type)


class TestMainWindowCaptureSettings:
    """Тесты настроек захвата."""

    def test_default_capture_settings(self) -> None:
        """Проверка настроек захвата по умолчанию."""
        from core.recording_types import CaptureMode
        from gui.models.recording_state import CaptureSettings

        settings = CaptureSettings()

        assert settings.capture_type == CaptureMode.FULL
        assert settings.window_title == ""
        assert settings.rect_coords == (0, 0, 1920, 1080)

    def test_window_capture_settings(self) -> None:
        """Проверка настроек захвата окна."""
        from core.recording_types import CaptureMode
        from gui.models.recording_state import CaptureSettings

        settings = CaptureSettings(
            capture_type=CaptureMode.WINDOW,
            window_title="Chrome",
        )

        assert settings.capture_type == CaptureMode.WINDOW
        assert settings.window_title == "Chrome"

    def test_rectangle_capture_settings(self) -> None:
        """Проверка настроек захвата области."""
        from core.recording_types import CaptureMode
        from gui.models.recording_state import CaptureSettings

        settings = CaptureSettings(
            capture_type=CaptureMode.RECT,
            rect_coords=(100, 100, 800, 600),
        )

        assert settings.capture_type == CaptureMode.RECT
        assert settings.rect_coords == (100, 100, 800, 600)


class TestMainWindowElapsedtime:
    """Тесты отслеживания времени."""

    def test_elapsed_time_initial_value(self) -> None:
        """Проверка начального значения времени."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        assert state.elapsed_time == 0.0

    def test_elapsed_time_reset_on_start(self) -> None:
        """Проверка сброса времени при начале записи."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        state.elapsed_time = 100.0
        state.start_recording(Path("/tmp/test.mp4"))

        assert state.elapsed_time == 0.0

    def test_recording_start_time_set(self) -> None:
        """Проверка установки времени начала записи."""
        from datetime import datetime

        from gui.models.recording_state import RecordingState

        state = RecordingState()
        before = datetime.now()
        state.start_recording(Path("/tmp/test.mp4"))
        after = datetime.now()

        assert state.recording_start_time is not None
        assert before <= state.recording_start_time <= after


class TestMainWindowMethods:
    """Тесты методов MainWindow без полного GUI-init."""

    def test_apply_settings_to_views_applies_rect_capture_and_output(
        self,
    ) -> None:
        """Настройки capture/output переносятся в соответствующие view."""
        window = _build_window()
        window._state.capture.capture_type = CaptureMode.RECT
        window._state.capture.window_title = "Editor"
        window._state.capture.rect_coords = (10, 20, 300, 200)
        window._state.output.default_path = "D:/Recordings"
        window._refresh_recent_recordings = MagicMock()

        window._apply_settings_to_views()

        window._capture_view.set_capture_type.assert_called_once_with(
            CaptureMode.RECT
        )
        window._capture_view.set_window_title.assert_called_once_with("Editor")
        window._capture_view.set_rect_coords.assert_called_once_with(
            (10, 20, 300, 200)
        )
        window._video_view.set_settings.assert_called_once_with(
            window._state.video
        )
        window._output_view.set_output_path.assert_called_once_with(
            "D:/Recordings"
        )
        window._refresh_recent_recordings.assert_called_once()

    def test_refresh_recent_recordings_adds_only_existing_matching_items(
        self, tmp_path: Path
    ) -> None:
        """В список попадают только существующие записи, прошедшие фильтр."""
        from core.recording_state import RecentRecording

        window = _build_window()
        existing = tmp_path / "capture.mp4"
        existing.write_bytes(b"data")
        missing = tmp_path / "missing.mp4"
        window._state.recent_recordings = [
            RecentRecording(path=existing, size=42, date="2026-04-03"),
            RecentRecording(path=missing, size=100, date="2026-04-03"),
        ]
        window._recordings_filter_input.text.return_value = "capture"

        class FakeListWidgetItem:
            def __init__(self, text: str) -> None:
                self.text = text
                self.payload = None

            def setData(self, _role, payload: str) -> None:
                self.payload = payload

        added_items: list[FakeListWidgetItem] = []
        window.recordings_list.addItem.side_effect = added_items.append

        with (
            patch("gui.main_window.QListWidgetItem", FakeListWidgetItem),
            patch("gui.main_window.format_filesize", return_value="42 B"),
        ):
            window._refresh_recent_recordings()

        window.recordings_list.clear.assert_called_once()
        assert len(added_items) == 1
        assert added_items[0].text == "capture.mp4 - 42 B - 2026-04-03"
        assert added_items[0].payload == str(existing)

    @pytest.mark.parametrize(
        ("filename", "date_text", "filter_text", "expected"),
        [
            ("capture.mp4", "2026-04-03", "", True),
            ("capture.mp4", "2026-04-03", "CAPTURE", True),
            ("capture.mp4", "2026-04-03", "2026-04", True),
            ("capture.mp4", "2026-04-03", "other", False),
        ],
    )
    def test_recording_matches_filter(
        self,
        filename: str,
        date_text: str,
        filter_text: str,
        expected: bool,
    ) -> None:
        """Фильтр учитывает имя файла и дату без учёта регистра."""
        from gui.main_window import MainWindow

        assert (
            MainWindow._recording_matches_filter(
                filename,
                date_text,
                filter_text,
            )
            is expected
        )

    def test_clear_recordings_filter_resets_field_and_refreshes(self) -> None:
        """Сброс фильтра очищает поле и обновляет список."""
        window = _build_window()
        window._refresh_recent_recordings = MagicMock()

        window._clear_recordings_filter()

        window._recordings_filter_input.setText.assert_called_once_with("")
        window._refresh_recent_recordings.assert_called_once()

    def test_on_view_signal_handlers_forward_to_settings_controller(
        self,
    ) -> None:
        """Сигналы view проксируются в SettingsController."""
        window = _build_window()
        settings = VideoSettings(
            fps=60, codec="libx265", bitrate="5M", format="avi"
        )

        window._on_capture_type_changed(CaptureMode.WINDOW)
        window._on_window_selected("Editor")
        window._on_rect_selected((1, 2, 3, 4))
        window._on_audio_type_changed(AudioMode.SYSTEM)
        window._on_mic_device_changed(7)
        window._on_video_settings_changed(settings)
        window._on_output_path_changed("D:/out.mp4")

        window._settings_controller.update_capture_settings.assert_any_call(
            capture_type=CaptureMode.WINDOW
        )
        window._settings_controller.update_capture_settings.assert_any_call(
            window_title="Editor"
        )
        window._settings_controller.update_capture_settings.assert_any_call(
            rect_coords=(1, 2, 3, 4)
        )
        window._settings_controller.update_audio_settings.assert_any_call(
            audio_type=AudioMode.SYSTEM
        )
        window._settings_controller.update_audio_settings.assert_any_call(
            mic_device_index=7
        )
        window._settings_controller.update_video_settings.assert_called_once_with(
            fps=60,
            codec="libx265",
            bitrate="5M",
            format="avi",
        )
        window._output_view.set_default_format.assert_called_once_with("avi")
        window._settings_controller.update_output_settings.assert_called_once_with(
            output_path="D:/out.mp4"
        )

    def test_start_recording_shows_error_for_rect_without_coords(self) -> None:
        """Для RECT без координат запуск записи блокируется."""
        window = _build_window()
        window._capture_view.get_capture_type.return_value = CaptureMode.RECT
        window._capture_view.get_rect_coords.return_value = None
        window._show_non_modal_error = MagicMock()

        window._start_recording()

        window._show_non_modal_error.assert_called_once()
        window._recording_controller.start_recording.assert_not_called()

    def test_start_recording_uses_fallback_full_screen_rect(self) -> None:
        """Без rect_coords используется fallback на размер экрана."""
        window = _build_window()
        window._capture_view.get_capture_type.return_value = CaptureMode.FULL
        window._capture_view.get_rect_coords.return_value = None
        window._capture_view.get_window_title.return_value = ""
        window._video_view.get_settings.return_value = VideoSettings()
        window._settings_controller.get_output_path.return_value = Path(
            "D:/capture.mp4"
        )
        window._recording_controller.start_recording.return_value = (
            True,
            None,
        )
        window._on_recording_started = MagicMock()

        class FakeGeometry:
            def width(self) -> int:
                return 1600

            def height(self) -> int:
                return 900

        fake_screen = SimpleNamespace(geometry=lambda: FakeGeometry())

        with patch(
            "PyQt6.QtGui.QGuiApplication.primaryScreen",
            return_value=fake_screen,
        ):
            window._start_recording()

        call = window._recording_controller.start_recording.call_args.kwargs
        assert call["capture"].rect_coords == (0, 0, 1600, 900)
        called_output, called_capture = (
            window._on_recording_started.call_args.args
        )
        assert called_output == Path("D:/capture.mp4")
        assert called_capture.capture_type == CaptureMode.FULL

    def test_start_recording_is_blocked_by_readiness_issues(self) -> None:
        """Blocking readiness snapshot должен останавливать start flow."""
        window = _build_window()
        window._show_error = MagicMock()
        window._capture_view.get_capture_type.return_value = CaptureMode.FULL
        window._capture_view.get_rect_coords.return_value = (0, 0, 100, 100)
        window._settings_controller.get_output_path.return_value = Path(
            "D:/capture.mp4"
        )
        window._video_view.get_settings.return_value = VideoSettings()
        window._readiness_service.evaluate.return_value = ReadinessSnapshot(
            issues=(
                ReadinessIssue(
                    code="ffmpeg_missing",
                    severity="blocking",
                    title="FFmpeg недоступен",
                    message="boom",
                ),
            )
        )

        window._start_recording()

        window._recording_controller.start_recording.assert_not_called()
        window.status_bar.showMessage.assert_called()
        window.tabs.setCurrentWidget.assert_called_once_with(
            window._diagnostics_view
        )
        window._run_diagnostics.assert_called_once_with()

    def test_apply_action_metadata_sets_shortcut_and_accessibility(
        self,
    ) -> None:
        """Action metadata должна попадать в shortcut и accessibility поля."""
        from gui.main_window import MainWindow

        window = _build_window()
        window._desktop_actions = MagicMock()
        window._desktop_actions.get.return_value = SimpleNamespace(
            title="Начать запись",
            description="Запускает запись с текущими настройками.",
            shortcut="Ctrl+R",
        )

        MainWindow._apply_action_metadata(
            window,
            window.start_btn,
            DesktopActionId.START_RECORDING,
        )

        assert window.start_btn._accessible_name == "Начать запись"
        assert (
            window.start_btn._accessible_description
            == "Запускает запись с текущими настройками."
        )
        assert window.start_btn._shortcut == "Ctrl+R"
        assert (
            window._registered_shortcuts[DesktopActionId.START_RECORDING.value]
            == "Ctrl+R"
        )

    def test_configure_tab_order_tracks_keyboard_navigation(self) -> None:
        """Tab order должен фиксироваться даже в mock-окружении."""
        from gui.main_window import MainWindow

        window = _build_window()

        MainWindow._configure_tab_order(window)

        assert window._tab_navigation_order[0] is window.start_btn
        assert window._tab_navigation_order[1] is window.pause_btn
        assert window._tab_navigation_order[-1] is window._open_folder_btn

    def test_run_diagnostics_uses_readiness_inputs(self) -> None:
        """Диагностика должна использовать те же входные данные готовности."""
        from gui.main_window import MainWindow

        window = _build_window()
        capture = CaptureSettings(
            capture_type=CaptureMode.WINDOW,
            window_title="Browser",
        )
        audio = AudioSettings(
            audio_type=AudioMode.MIC,
            mic_device_index=3,
        )
        window._build_capture_settings_from_views = MagicMock(
            return_value=capture
        )
        window._build_audio_settings_from_state = MagicMock(
            return_value=audio
        )
        window._settings_controller.get_output_path.return_value = Path(
            "D:/capture.mp4"
        )
        window._application_facade = SimpleNamespace(
            get_api_status=MagicMock(return_value={"running": True})
        )

        MainWindow._run_diagnostics(window)

        window._diagnostics_view.run_checks.assert_called_once_with(
            api_enabled=True,
            output_path=Path("D:/capture.mp4"),
            capture=capture,
            audio=audio,
        )

    def test_diagnostics_fix_refreshes_audio_and_windows(self) -> None:
        """Fix actions на диагностике делегируют refresh соответствующим view."""
        from gui.main_window import MainWindow

        window = _build_window()

        MainWindow._on_diagnostics_fix(window, "Аудиоустройства")
        MainWindow._on_diagnostics_fix(window, "Окно захвата")

        assert window.tabs.setCurrentIndex.call_count == 2
        window._audio_view._refresh_audio_devices.assert_called_once_with()
        window._capture_view._refresh_windows.assert_called_once_with()

    def test_stop_recording_reports_missing_output(self) -> None:
        """Если backend не вернул путь, показывается ошибка."""
        window = _build_window()
        window._state.start_recording(Path("D:/capture.mp4"))
        window._begin_stop_operation = MagicMock()

        window._stop_recording()

        window._begin_stop_operation.assert_called_once()

    def test_stop_recording_requests_cancel_when_operation_in_progress(
        self,
    ) -> None:
        """Повторное нажатие стопа должно просить отмену остановки."""
        window = _build_window()
        window._stop_operation_in_progress = True
        window._cancel_stop_operation = MagicMock()

        window._stop_recording()

        window._cancel_stop_operation.assert_called_once()

    def test_toggle_pause_calls_expected_controller_branch(self) -> None:
        """Переключение паузы вызывает pause или resume ветку."""
        window = _build_window()
        window._on_recording_paused = MagicMock()
        window._on_recording_resumed = MagicMock()

        window._toggle_pause()
        window._recording_controller.pause_recording.assert_called_once()
        window._on_recording_paused.assert_called_once()

        window._state.start_recording(Path("D:/capture.mp4"))
        window._state.pause_recording()
        window._toggle_pause()
        window._recording_controller.resume_recording.assert_called_once()
        window._on_recording_resumed.assert_called_once()

    def test_on_recording_started_and_resumed_update_controls(self) -> None:
        """UI обновляется при старте, паузе и возобновлении записи."""
        window = _build_window()
        output = Path("D:/capture.mp4")
        capture = CaptureSettings(
            capture_type=CaptureMode.RECT,
            rect_coords=(10, 20, 100, 200),
        )

        window._on_recording_started(output, capture)
        window._on_recording_paused()
        window._on_recording_resumed()

        window.start_btn.setEnabled.assert_called_with(False)
        window.stop_btn.setEnabled.assert_called_with(True)
        window.pause_btn.setText.assert_any_call("Пауза")
        window.pause_btn.setText.assert_any_call("Продолжить")
        window.status_label.setText.assert_any_call("Запись")
        window.status_label.setText.assert_any_call("Пауза")
        window._update_timer.start.assert_any_call(100)
        window._update_timer.stop.assert_called()
        window.recording_started.emit.assert_called_once_with(str(output))
        window.recording_paused.emit.assert_called_once()
        window.recording_resumed.emit.assert_called_once()
        window._recording_indicator.show_for_capture.assert_called_once_with(
            capture
        )
        window._recording_indicator.set_paused.assert_any_call(True)
        window._recording_indicator.set_paused.assert_any_call(False)

    def test_on_recording_stopped_adds_recent_recording_for_existing_file(
        self, tmp_path: Path
    ) -> None:
        """Остановка записи добавляет существующий файл в recent recordings."""
        window = _build_window()
        output = tmp_path / "capture.mp4"
        output.write_bytes(b"abc")
        window._refresh_recent_recordings = MagicMock()

        window._on_recording_stopped(output)

        window._settings_controller.add_recent_recording.assert_called_once_with(
            output,
            3,
        )
        window._update_timer.stop.assert_called_once()
        window._refresh_recent_recordings.assert_called_once()
        window.recording_stopped.emit.assert_called_once_with(str(output))
        window._recording_indicator.hide_indicator.assert_called_once()

    def test_begin_stop_operation_updates_ui_and_spawns_thread(self) -> None:
        """Начало stop operation переводит UI в stopping-состояние."""
        window = _build_window()

        class FakeThread:
            def __init__(self, target, daemon):
                self.target = target
                self.daemon = daemon
                self.started = False

            def start(self):
                self.started = True

        with patch("gui.main_window.threading.Thread", FakeThread):
            window._begin_stop_operation()

        assert window._stop_operation_in_progress is True
        window.pause_btn.setEnabled.assert_called_with(False)
        window.stop_btn.setText.assert_called_with("Отменить остановку")
        window.status_label.setText.assert_called_with("Остановка...")

    def test_cancel_stop_operation_requests_controller_cancellation(
        self,
    ) -> None:
        """Отмена долгой остановки делегируется контроллеру."""
        window = _build_window()
        window._stop_operation_in_progress = True
        window._recording_controller.request_stop_cancellation.return_value = (
            True
        )

        window._cancel_stop_operation()

        window._recording_controller.request_stop_cancellation.assert_called_once()
        window.stop_btn.setEnabled.assert_called_with(False)

    def test_on_stop_operation_finished_success_calls_recording_stopped(
        self,
    ) -> None:
        """Успешное завершение stop operation должно завершать lifecycle."""
        window = _build_window()
        window._stop_operation_in_progress = True
        window._on_recording_stopped = MagicMock()
        output = Path("D:/capture.mp4")

        window._on_stop_operation_finished(output, None)

        assert window._stop_operation_in_progress is False
        window._on_recording_stopped.assert_called_once_with(output)

    def test_on_stop_operation_finished_error_restores_idle_ui(self) -> None:
        """Ошибка stop operation должна вернуть UI в idle-состояние."""
        window = _build_window()
        window._stop_operation_in_progress = True

        window._on_stop_operation_finished(None, "Не удалось сохранить запись")

        assert window._stop_operation_in_progress is False
        window.start_btn.setEnabled.assert_called_with(True)
        window.stop_btn.setEnabled.assert_called_with(False)
        window._recording_indicator.hide_indicator.assert_called_once()

    def test_update_status_formats_elapsed_time(self) -> None:
        """Таймер статуса форматирует elapsed time во время записи."""
        window = _build_window()
        window._state.start_recording(Path("D:/capture.mp4"))
        window._recording_controller.elapsed_time = 12.34

        with patch("gui.main_window.format_time", return_value="00:12"):
            window._update_status()

        window.time_label.setText.assert_called_once_with("00:12")

    def test_check_dependencies_runs_in_background(self) -> None:
        """Проверка зависимостей не должна блокировать UI-поток."""
        from gui.main_window import MainWindow

        started: dict[str, bool] = {"value": False}

        class FakeThread:
            def __init__(self, target, daemon):
                self.target = target
                self.daemon = daemon

            def start(self):
                started["value"] = True

        window = _build_window()

        with patch("gui.main_window.threading.Thread", FakeThread):
            MainWindow._check_dependencies(window)

        assert started["value"] is True

    def test_dependency_check_completion_shows_warning_when_ffmpeg_missing(
        self,
    ) -> None:
        """Результат фоновой проверки показывает warning при отсутствии FFmpeg."""
        from gui.main_window import MainWindow

        window = _build_window()

        with patch("gui.main_window.QMessageBox.warning") as warning:
            MainWindow._on_dependency_check_completed(
                window,
                (False, None),
                None,
            )

        warning.assert_called_once()

    def test_hide_and_show_event_toggle_status_timer(self) -> None:
        """Скрытие окна останавливает timer, показ возвращает его при записи."""
        from gui.main_window import MainWindow

        window = _build_window()
        window._state.start_recording(Path("D:/capture.mp4"))

        MainWindow.hideEvent(window, None)
        MainWindow.showEvent(window, None)

        window._update_timer.stop.assert_called_once()
        window._update_timer.start.assert_called_once_with(100)

    def test_invoke_api_control_handles_none_exception_and_plain_value(
        self,
    ) -> None:
        """Вызов API control нормализует ответы и ошибки."""
        window = _build_window()
        window._show_non_modal_error = MagicMock()
        handler_map = {
            "ping": lambda: "pong",
            "boom": lambda: (_ for _ in ()).throw(RuntimeError("fail")),
        }
        window._get_api_control_handler = MagicMock(
            side_effect=lambda name: handler_map.get(name)
        )

        assert window._invoke_api_control("missing") is None
        assert window._invoke_api_control("ping") == {
            "success": True,
            "data": "pong",
        }
        assert window._invoke_api_control("boom") is None
        window._show_non_modal_error.assert_called_once_with("fail")

    def test_bind_application_facade_routes_api_controls(self) -> None:
        """При наличии фасада API-кнопки должны ходить через него."""
        window = _build_window()
        facade = SimpleNamespace(
            get_api_status=MagicMock(return_value={"running": True}),
            apply_api_settings=MagicMock(return_value={"success": True}),
            start_api_server=MagicMock(return_value={"success": True}),
            stop_api_server=MagicMock(return_value={"success": True}),
            restart_api_server=MagicMock(return_value={"success": True}),
            open_api_logs_folder=MagicMock(return_value=None),
        )

        window.bind_application_facade(facade)

        assert window._invoke_api_control("get_status") == {"running": True}
        assert window._invoke_api_control(
            "apply_settings", {"port": 5001}
        ) == {"success": True}
        assert window._invoke_api_control("start") == {"success": True}
        assert window._invoke_api_control("stop") == {"success": True}
        assert window._invoke_api_control("restart") == {"success": True}
        assert window._invoke_api_control("open_logs") == {
            "success": True,
            "data": None,
        }

        facade.apply_api_settings.assert_called_once_with({"port": 5001})
        facade.start_api_server.assert_called_once_with(force=True)
        facade.stop_api_server.assert_called_once_with()
        facade.restart_api_server.assert_called_once_with()
        facade.open_api_logs_folder.assert_called_once_with()

    def test_request_stop_and_pause_use_interactive_flow(self) -> None:
        """Интерактивные методы должны возвращать snapshot после действия."""
        window = _build_window()
        status_snapshot = {
            "is_recording": True,
            "is_paused": False,
            "elapsed_time": 1.0,
            "current_file": "D:/capture.mp4",
        }
        window._stop_recording = MagicMock()
        window._toggle_pause = MagicMock()
        window.get_status = MagicMock(return_value=status_snapshot)

        stop_result = window.request_stop_recording()
        pause_result = window.request_toggle_pause()

        window._stop_recording.assert_called_once_with()
        window._toggle_pause.assert_called_once_with()
        assert stop_result == status_snapshot
        assert pause_result == status_snapshot

    def test_refresh_api_status_uses_result_and_facade_fallback(self) -> None:
        """Статус API берётся из control-а или из фасада."""
        window = _build_window()
        window._invoke_api_control = MagicMock(
            side_effect=[
                {
                    "configured": {"port": 8080, "api_key": "secret"},
                    "running": True,
                    "url": "http://127.0.0.1:8080",
                },
                None,
            ]
        )
        window._application_facade = SimpleNamespace(
            get_api_status=MagicMock(return_value={"running": False})
        )
        window._api_settings_view.is_editing_settings.return_value = False

        window._refresh_api_status()
        window._refresh_api_status()

        window._api_settings_view.set_settings.assert_called_once_with(
            port=8080,
            token="secret",
        )
        window._api_settings_view.set_status.assert_any_call(
            True,
            "Запущен: http://127.0.0.1:8080",
        )
        window._api_settings_view.set_status.assert_any_call(
            False,
            "Сервер остановлен",
        )

    def test_api_button_handlers_route_success_and_failure(self) -> None:
        """Хендлеры API-кнопок обновляют статусбар и ошибки."""
        window = _build_window()
        window._show_non_modal_error = MagicMock()
        window._refresh_api_status = MagicMock()
        window._start_websocket_after_api = MagicMock()
        window.disconnect_websocket = MagicMock()
        window._invoke_api_control = MagicMock(
            side_effect=[
                {"success": True, "restart_required": True},
                {
                    "success": True,
                    "configured": {"api_key": "t"},
                    "url": "http://x",
                },
                {"success": True},
                {"success": False, "error": "restart failed"},
            ]
        )

        window._on_api_settings_apply(9000, "tok")
        window._on_api_start()
        window._on_api_stop()
        window._on_api_restart()

        assert window.status_bar.showMessage.call_count >= 3
        window._start_websocket_after_api.assert_called_once()
        window.disconnect_websocket.assert_called()
        window._show_non_modal_error.assert_called_with("restart failed")

    def test_show_non_modal_error_updates_status_bar_and_signal(self) -> None:
        """Non-modal error должен обновлять status bar и эмитить сигнал."""
        from gui.main_window import MainWindow

        window = _build_window()

        MainWindow._show_non_modal_error(window, "boom", duration_ms=1234)

        window.status_label.setText.assert_called_once_with("Ошибка")
        window.status_bar.showMessage.assert_called_once_with("boom", 1234)
        window.error_occurred.emit.assert_called_once_with("boom")

    @pytest.mark.parametrize(
        ("ui_state", "expected_status", "expected_pause_text"),
        [
            ("idle", "Готов", "Пауза"),
            ("recording", "Запись", "Пауза"),
            ("paused", "Пауза", "Продолжить"),
            ("stopping", "Остановка...", "Пауза"),
        ],
    )
    def test_update_ui_state_centralizes_button_and_status_updates(
        self,
        ui_state: str,
        expected_status: str,
        expected_pause_text: str,
    ) -> None:
        """Центральный helper должен управлять button/status state."""
        from gui.main_window import MainWindow

        window = _build_window()

        MainWindow._update_ui_state(window, ui_state)

        window.status_label.setText.assert_called_with(expected_status)
        window.pause_btn.setText.assert_called_with(expected_pause_text)

    def test_start_websocket_after_api_initializes_only_when_url_and_token(
        self,
    ) -> None:
        """WebSocket стартует только при наличии URL и токена."""
        window = _build_window()
        window.init_websocket_client = MagicMock()
        window.connect_websocket = MagicMock()

        window._start_websocket_after_api(
            {
                "configured": {"api_key": "token"},
                "url": "http://127.0.0.1:5000",
            }
        )
        window._ws_controller = MagicMock()
        window._start_websocket_after_api(
            {
                "configured": {"api_key": "token"},
                "url": "http://127.0.0.1:5000",
            }
        )
        window._start_websocket_after_api({"configured": {}, "url": ""})

        window.init_websocket_client.assert_called_once_with(
            "http://127.0.0.1:5000",
            "token",
        )
        assert window.connect_websocket.call_count == 2

    def test_websocket_helpers_update_status_and_emit_events(self) -> None:
        """WebSocket-хелперы обновляют label и проксируют события."""
        window = _build_window()

        window._on_ws_status_changed("connected")
        window._on_ws_event_received(
            "recording.started", {"output_path": "D:/capture.mp4"}
        )
        window._on_ws_event_received("recording.paused", {})
        window._on_ws_event_received("recording.resumed", {})
        window._on_ws_event_received("recording.error", {"error": "boom"})

        window._ws_status_label.setText.assert_called_with("WS: ●")
        window.recording_started.emit.assert_called_once_with("D:/capture.mp4")
        window.recording_paused.emit.assert_called_once()
        window.recording_resumed.emit.assert_called_once()
        window.error_occurred.emit.assert_called_once_with("boom")

    def test_open_recording_helpers_use_selected_items(self) -> None:
        """Открытие записей использует выбранный и последний элементы."""
        window = _build_window()
        window._open_file = MagicMock()
        fake_item = MagicMock()
        fake_item.data.return_value = "D:/capture.mp4"
        window.recordings_list.currentItem.return_value = fake_item
        window.recordings_list.item.return_value = fake_item

        window._open_recording(fake_item)
        window._open_selected_recording()
        window._open_latest_recording()

        assert window._open_file.call_count == 3

    @pytest.mark.parametrize(
        ("requested", "fmt", "expected"),
        [
            (None, "mp4", Path("D:/default.mp4")),
            ("  ", "mp4", Path("D:/default.mp4")),
            ("relative_video", "mkv", Path("relative_video.mkv")),
            ("relative_video.mp4", "mkv", Path("relative_video.mp4")),
        ],
    )
    def test_resolve_requested_output_path_basic_variants(
        self,
        requested: str | None,
        fmt: str,
        expected: Path,
    ) -> None:
        """output_path из API нормализуется в итоговый путь файла."""
        window = _build_window()
        window._settings_controller.get_output_path.return_value = Path(
            "D:/default.mp4"
        )

        result = window._resolve_requested_output_path(requested, fmt)

        assert result == expected

    def test_resolve_requested_output_path_for_directory_hint(self) -> None:
        """Путь с завершающим слешем трактуется как директория."""
        window = _build_window()

        with patch("gui.main_window.datetime") as mocked_datetime:
            mocked_datetime.now.return_value.strftime.return_value = (
                "20260403_123456"
            )
            result = window._resolve_requested_output_path("D:/out/", "mp4")

        assert result == Path("D:/out/recording_20260403_123456.mp4")

    def test_start_recording_with_params_success_and_invalid_rect(
        self,
    ) -> None:
        """API-старт записи обрабатывает успешный и невалидный rect кейсы."""
        window = _build_window()
        window._video_view.get_settings.return_value = VideoSettings()
        window._recording_controller.start_recording.return_value = (
            True,
            None,
        )
        window._resolve_requested_output_path = MagicMock(
            return_value=Path("D:/capture.mp4")
        )
        window._on_recording_started = MagicMock()

        result = window.start_recording_with_params(
            {
                "area": "rect",
                "rect": [10, 20, 110, 220],
                "audio": "system",
                "fps": 60,
                "codec": "libx265",
                "bitrate": "5M",
            }
        )
        invalid = window.start_recording_with_params(
            {"area": "rect", "rect": [1, 2, 3]}
        )

        assert result == {
            "success": True,
            "output_path": str(Path("D:/capture.mp4")),
        }
        call = window._recording_controller.start_recording.call_args.kwargs
        assert call["capture"].rect_coords == (10, 20, 110, 220)
        assert isinstance(call["audio"], AudioSettings)
        assert invalid["success"] is False
        assert "4 координаты" in invalid["error"]

    def test_start_recording_with_params_respects_readiness_blockers(
        self,
    ) -> None:
        """API-путь старта должен уважать тот же readiness snapshot."""
        window = _build_window()
        window._video_view.get_settings.return_value = VideoSettings()
        window._resolve_requested_output_path = MagicMock(
            return_value=Path("D:/capture.mp4")
        )
        window._readiness_service.evaluate.return_value = ReadinessSnapshot(
            issues=(
                ReadinessIssue(
                    code="window_missing",
                    severity="blocking",
                    title="Окно захвата недоступно",
                    message="Окно не найдено.",
                ),
            )
        )

        result = window.start_recording_with_params(
            {
                "area": "window",
                "window_title": "Browser",
                "audio": "none",
            }
        )

        assert result["success"] is False
        assert "Окно захвата недоступно" in result["error"]
        window._recording_controller.start_recording.assert_not_called()

    def test_stop_recording_toggle_pause_and_get_recordings_api_methods(
        self,
    ) -> None:
        """API-методы stop/pause/read работают с текущим состоянием."""
        window = _build_window()
        window._on_recording_stopped = MagicMock()
        window._on_recording_paused = MagicMock()
        window._recording_controller.stop_recording.return_value = Path(
            "D:/capture.mp4"
        )

        assert window.stop_recording()["success"] is False
        assert window.toggle_pause()["success"] is False

        window._state.start_recording(Path("D:/capture.mp4"))
        stop_result = window.stop_recording()
        pause_result = window.toggle_pause()

        with patch("gui.main_window.get_config") as mocked_get_config:
            mocked_get_config.return_value.settings.recent_recordings = [
                {"path": "D:/capture.mp4"}
            ]
            recordings = window.get_recordings()

        assert stop_result == {
            "success": True,
            "filepath": str(Path("D:/capture.mp4")),
        }
        assert pause_result == {"success": True, "is_paused": True}
        assert recordings == [{"path": "D:/capture.mp4"}]

    def test_recording_start_time_cleared_on_stop(self) -> None:
        """Проверка очистки времени начала при остановке."""
        from gui.models.recording_state import RecordingState

        state = RecordingState()
        state.start_recording(Path("/tmp/test.mp4"))
        state.stop_recording()

        assert state.recording_start_time is None
