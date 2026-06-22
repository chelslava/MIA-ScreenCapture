"""
Тесты модуля видеозаписи
=======================

Тестирует классы CaptureArea и VideoRecorder.
"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from recorder.video_recorder import CaptureArea, RecordingState, VideoRecorder


class TestRecordingState:
    """Тесты перечисления состояний записи."""

    def test_state_values(self) -> None:
        """Проверка значений состояний."""
        assert RecordingState.IDLE.value == "idle"
        assert RecordingState.RECORDING.value == "recording"
        assert RecordingState.PAUSED.value == "paused"
        assert RecordingState.STOPPING.value == "stopping"


class TestCaptureArea:
    """Тесты класса CaptureArea."""

    def test_default_values(self) -> None:
        """Проверка значений по умолчанию."""
        area = CaptureArea(type="full")
        assert area.type == "full"
        assert area.x == 0
        assert area.y == 0
        assert area.width == 0
        assert area.height == 0
        assert area.window_title is None

    def test_custom_values(self) -> None:
        """Проверка пользовательских значений."""
        area = CaptureArea(
            type="rect",
            x=100,
            y=200,
            width=800,
            height=600,
            window_title="Test Window",
        )
        assert area.type == "rect"
        assert area.x == 100
        assert area.y == 200
        assert area.width == 800
        assert area.height == 600
        assert area.window_title == "Test Window"

    def test_full_screen(self) -> None:
        """Проверка создания области полного экрана."""
        with patch(
            "recorder.video_recorder.get_available_monitors"
        ) as mock_monitors:
            mock_monitors.return_value = [
                {"index": 0, "width": 1920, "height": 1080, "is_primary": True}
            ]
            area = CaptureArea.full_screen()

        assert area.type == "full"
        assert area.width == 1920
        assert area.height == 1080

    def test_full_screen_with_monitor_index(self) -> None:
        """Проверка создания области полного экрана с индексом монитора."""
        with patch(
            "recorder.video_recorder.get_available_monitors"
        ) as mock_monitors:
            mock_monitors.return_value = [
                {
                    "index": 0,
                    "width": 1920,
                    "height": 1080,
                    "is_primary": True,
                },
                {
                    "index": 1,
                    "width": 2560,
                    "height": 1440,
                    "is_primary": False,
                },
            ]
            area = CaptureArea.full_screen(monitor_index=1)

        assert area.type == "full"
        assert area.width == 2560
        assert area.height == 1440

    def test_from_rect(self) -> None:
        """Проверка создания прямоугольной области."""
        with patch(
            "recorder.video_recorder.validate_rect_coords"
        ) as mock_validate:
            mock_validate.return_value = (100, 200, 900, 800)
            area = CaptureArea.from_rect(100, 200, 900, 800)

        assert area.type == "rect"
        assert area.x == 100
        assert area.y == 200
        assert area.width == 800
        assert area.height == 600

    def test_from_rect_swapped_coords(self) -> None:
        """Проверка создания области с переставленными координатами."""
        with patch(
            "recorder.video_recorder.validate_rect_coords"
        ) as mock_validate:
            # validate_rect_coords должен нормализовать координаты
            mock_validate.return_value = (100, 200, 900, 800)
            area = CaptureArea.from_rect(900, 800, 100, 200)

        assert area.x == 100
        assert area.y == 200

    def test_from_window(self) -> None:
        """Проверка создания области из окна."""
        with patch(
            "recorder.video_recorder.get_available_windows"
        ) as mock_windows:
            mock_windows.return_value = [
                {
                    "title": "Test Window",
                    "x": 50,
                    "y": 100,
                    "width": 800,
                    "height": 600,
                }
            ]
            area = CaptureArea.from_window("Test Window")

        assert area.type == "window"
        assert area.x == 50
        assert area.y == 100
        assert area.width == 800
        assert area.height == 600
        assert area.window_title == "Test Window"

    def test_from_window_partial_match(self) -> None:
        """Проверка создания области с частичным совпадением заголовка."""
        with patch(
            "recorder.video_recorder.get_available_windows"
        ) as mock_windows:
            mock_windows.return_value = [
                {
                    "title": "Test Window - Application",
                    "x": 0,
                    "y": 0,
                    "width": 1024,
                    "height": 768,
                }
            ]
            area = CaptureArea.from_window("Test Window")

        assert area.type == "window"
        assert area.window_title == "Test Window - Application"

    def test_from_window_not_found_fallback(self) -> None:
        """Проверка fallback на полный экран при ненайденном окне."""
        with (
            patch(
                "recorder.video_recorder.get_available_windows"
            ) as mock_windows,
            patch(
                "recorder.video_recorder.get_available_monitors"
            ) as mock_monitors,
        ):
            mock_windows.return_value = []
            mock_monitors.return_value = [
                {"index": 0, "width": 1920, "height": 1080, "is_primary": True}
            ]
            area = CaptureArea.from_window("Nonexistent Window")

        assert area.type == "full"
        assert area.width == 1920
        assert area.height == 1080

    def test_to_capture_dict(self) -> None:
        """Проверка преобразования в формат области захвата."""
        area = CaptureArea(type="rect", x=100, y=200, width=800, height=600)
        capture_dict = area.to_capture_dict()

        assert capture_dict["left"] == 100
        assert capture_dict["top"] == 200
        assert capture_dict["width"] == 800
        assert capture_dict["height"] == 600


class TestVideoRecorder:
    """Тесты класса VideoRecorder."""

    @pytest.fixture
    def recorder(self) -> VideoRecorder:
        """Создаёт рекордер для тестов (без FFmpeg для unit тестов)."""
        return VideoRecorder(use_ffmpeg=False)

    def test_init_default(self) -> None:
        """Проверка инициализации с параметрами по умолчанию."""
        recorder = VideoRecorder()
        assert recorder.fps == 30
        assert recorder.codec == "libx264"
        assert recorder.bitrate == "2M"
        assert recorder.output_format == "mp4"
        assert recorder.state == RecordingState.IDLE

    def test_init_custom_params(self) -> None:
        """Проверка инициализации с пользовательскими параметрами."""
        recorder = VideoRecorder(
            fps=60,
            codec="h264",
            bitrate="5M",
            output_format="avi",
        )
        assert recorder.fps == 60
        assert recorder.codec == "h264"
        assert recorder.bitrate == "5M"
        assert recorder.output_format == "avi"

    def test_state_property(self, recorder: VideoRecorder) -> None:
        """Проверка свойства state."""
        assert recorder.state == RecordingState.IDLE

    def test_is_recording_false_initially(
        self, recorder: VideoRecorder
    ) -> None:
        """Проверка is_recording при инициализации."""
        assert recorder.is_recording is False

    def test_is_paused_false_initially(self, recorder: VideoRecorder) -> None:
        """Проверка is_paused при инициализации."""
        assert recorder.is_paused is False

    def test_elapsed_time_zero_initially(
        self, recorder: VideoRecorder
    ) -> None:
        """Проверка elapsed_time при инициализации."""
        assert recorder.elapsed_time == 0

    def test_output_path_none_initially(self, recorder: VideoRecorder) -> None:
        """Проверка output_path при инициализации."""
        assert recorder.output_path is None

    def test_frame_count_zero_initially(self, recorder: VideoRecorder) -> None:
        """Проверка frame_count при инициализации."""
        assert recorder.frame_count == 0

    def test_additional_segment_paths_empty_initially(
        self, recorder: VideoRecorder
    ) -> None:
        """additional_segment_paths пуст без активного writer."""
        assert recorder.additional_segment_paths == []

    def test_additional_segment_paths_survives_cleanup(
        self, recorder: VideoRecorder
    ) -> None:
        """Сегменты восстановления остаются доступны после _cleanup()."""
        mock_writer = MagicMock()
        mock_writer.is_corrupted = False
        mock_writer.close.return_value = True
        mock_writer.segment_paths = [
            Path("video.mp4"),
            Path("video_part2.mp4"),
        ]
        recorder._ffmpeg_writer = mock_writer

        recorder._cleanup()

        assert recorder._ffmpeg_writer is None
        assert recorder.additional_segment_paths == [
            Path("video.mp4"),
            Path("video_part2.mp4"),
        ]

    def test_set_callbacks(self, recorder: VideoRecorder) -> None:
        """Проверка установки callback'ов."""
        frame_callback = MagicMock()
        error_callback = MagicMock()
        recorder.set_callbacks(
            on_frame_captured=frame_callback,
            on_error=error_callback,
        )
        assert recorder._on_frame_captured is frame_callback
        assert recorder._on_error is error_callback

    def test_codec_map_exists(self, recorder: VideoRecorder) -> None:
        """Проверка наличия карты кодеков."""
        assert hasattr(VideoRecorder, "CODEC_MAP")
        assert "libx264" in VideoRecorder.CODEC_MAP
        assert "h264" in VideoRecorder.CODEC_MAP

    def test_pause_from_recording_state(self, recorder: VideoRecorder) -> None:
        """Проверка паузы из состояния RECORDING."""
        recorder._state = RecordingState.RECORDING
        recorder._start_time = time.time()

        result = recorder.pause()

        assert result is True
        assert recorder.state == RecordingState.PAUSED
        assert recorder._paused_time > 0

    def test_pause_from_idle_returns_false(
        self, recorder: VideoRecorder
    ) -> None:
        """Проверка паузы из состояния IDLE."""
        result = recorder.pause()

        assert result is False
        assert recorder.state == RecordingState.IDLE

    def test_pause_from_paused_returns_false(
        self, recorder: VideoRecorder
    ) -> None:
        """Проверка паузы из состояния PAUSED."""
        recorder._state = RecordingState.PAUSED

        result = recorder.pause()

        assert result is False

    def test_resume_from_paused_state(self, recorder: VideoRecorder) -> None:
        """Проверка возобновления из состояния PAUSED."""
        recorder._state = RecordingState.PAUSED
        recorder._paused_time = time.time() - 1.0  # Пауза длилась 1 секунду
        recorder._start_time = time.time() - 5.0
        recorder._total_paused = 0

        result = recorder.resume()

        assert result is True
        assert recorder.state == RecordingState.RECORDING
        # _total_paused должен увеличиться на время паузы
        assert recorder._total_paused >= 1.0

    def test_resume_from_idle_returns_false(
        self, recorder: VideoRecorder
    ) -> None:
        """Проверка возобновления из состояния IDLE."""
        result = recorder.resume()

        assert result is False

    def test_resume_from_recording_returns_false(
        self, recorder: VideoRecorder
    ) -> None:
        """Проверка возобновления из состояния RECORDING."""
        recorder._state = RecordingState.RECORDING

        result = recorder.resume()

        assert result is False

    def test_stop_from_idle_returns_false(
        self, recorder: VideoRecorder
    ) -> None:
        """Проверка остановки из состояния IDLE."""
        result = recorder.stop()

        assert result is False

    def test_elapsed_time_during_recording(
        self, recorder: VideoRecorder
    ) -> None:
        """Проверка расчёта времени во время записи."""
        recorder._state = RecordingState.RECORDING
        recorder._start_time = time.time() - 5.0
        recorder._total_paused = 0

        elapsed = recorder.elapsed_time

        assert 4.9 < elapsed < 5.1

    def test_elapsed_time_during_pause(self, recorder: VideoRecorder) -> None:
        """Проверка расчёта времени во время паузы."""
        recorder._state = RecordingState.PAUSED
        recorder._start_time = time.time() - 10.0
        recorder._paused_time = time.time() - 3.0
        recorder._total_paused = 0

        elapsed = recorder.elapsed_time

        # Время должно быть около 7 секунд (10 - 3 паузы)
        assert 6.9 < elapsed < 7.1

    def test_elapsed_time_with_total_paused(
        self, recorder: VideoRecorder
    ) -> None:
        """Проверка расчёта времени с учётом total_paused."""
        recorder._state = RecordingState.RECORDING
        recorder._start_time = time.time() - 10.0
        recorder._total_paused = 3.0

        elapsed = recorder.elapsed_time

        # Время должно быть около 7 секунд (10 - 3 паузы)
        assert 6.9 < elapsed < 7.1

    def test_capture_loop_stops_on_ffmpeg_write_failure(self) -> None:
        """Проверка аварийной остановки при ошибке записи кадра FFmpeg."""
        recorder = VideoRecorder(use_ffmpeg=True)
        recorder._state = RecordingState.RECORDING
        recorder._capture_area = CaptureArea(type="full", width=32, height=32)
        recorder._ffmpeg_writer = MagicMock()
        recorder._ffmpeg_writer.write.return_value = False
        recorder._ffmpeg_writer.is_disk_space_critical = False
        recorder._ffmpeg_writer.is_segment_rotation_failed = False

        error_callback = MagicMock()
        recorder.set_callbacks(on_error=error_callback)

        class MockSession:
            """Простейший mock с одним кадром для цикла захвата."""

            def __init__(self) -> None:
                self.is_capture_lost = False
                self._read_count = 0

            def start(self, capture_area: CaptureArea) -> None:
                _ = capture_area

            def read_frame(self, timeout: float):
                _ = timeout
                if self._read_count == 0:
                    self._read_count += 1
                    return np.zeros((32, 32, 3), dtype=np.uint8)
                return None

            def stop(self) -> None:
                return

        mock_session = MockSession()
        with (
            patch(
                "recorder.video_recorder._WindowsCaptureSession",
                return_value=mock_session,
            ),
            patch.object(recorder, "_cleanup") as mock_cleanup,
        ):
            recorder._capture_loop()

        assert recorder.frame_count == 0
        assert recorder.state == RecordingState.STOPPING
        mock_cleanup.assert_called_once()
        error_callback.assert_called_once()
        recorder._ffmpeg_writer.mark_corrupted.assert_called_once()
        assert recorder.stopped_due_to_low_disk_space is False
        assert recorder.stopped_due_to_segment_rotation_failure is False

    def test_capture_loop_stops_gracefully_on_disk_space_critical(
        self,
    ) -> None:
        """
        Критическая нехватка места останавливает запись без mark_corrupted —
        файл должен быть финализирован штатно через _cleanup()/close().
        """
        recorder = VideoRecorder(use_ffmpeg=True)
        recorder._state = RecordingState.RECORDING
        recorder._capture_area = CaptureArea(type="full", width=32, height=32)
        recorder._ffmpeg_writer = MagicMock()
        recorder._ffmpeg_writer.write.return_value = False
        recorder._ffmpeg_writer.is_disk_space_critical = True

        error_callback = MagicMock()
        recorder.set_callbacks(on_error=error_callback)

        class MockSession:
            """Простейший mock с одним кадром для цикла захвата."""

            def __init__(self) -> None:
                self.is_capture_lost = False
                self._read_count = 0

            def start(self, capture_area: CaptureArea) -> None:
                _ = capture_area

            def read_frame(self, timeout: float):
                _ = timeout
                if self._read_count == 0:
                    self._read_count += 1
                    return np.zeros((32, 32, 3), dtype=np.uint8)
                return None

            def stop(self) -> None:
                return

        mock_session = MockSession()
        with (
            patch(
                "recorder.video_recorder._WindowsCaptureSession",
                return_value=mock_session,
            ),
            patch.object(recorder, "_cleanup") as mock_cleanup,
        ):
            recorder._capture_loop()

        assert recorder.frame_count == 0
        assert recorder.state == RecordingState.STOPPING
        mock_cleanup.assert_called_once()
        error_callback.assert_called_once()
        assert "диска" in error_callback.call_args.args[0]
        recorder._ffmpeg_writer.mark_corrupted.assert_not_called()
        assert recorder.stopped_due_to_low_disk_space is True

    def test_capture_loop_stops_gracefully_on_segment_rotation_failure(
        self,
    ) -> None:
        """
        Неудача плановой ротации сегмента (#53) останавливает запись без
        mark_corrupted — предыдущие сегменты уже штатно закрыты и валидны.
        """
        recorder = VideoRecorder(use_ffmpeg=True)
        recorder._state = RecordingState.RECORDING
        recorder._capture_area = CaptureArea(type="full", width=32, height=32)
        recorder._ffmpeg_writer = MagicMock()
        recorder._ffmpeg_writer.write.return_value = False
        recorder._ffmpeg_writer.is_disk_space_critical = False
        recorder._ffmpeg_writer.is_segment_rotation_failed = True

        error_callback = MagicMock()
        recorder.set_callbacks(on_error=error_callback)

        class MockSession:
            """Простейший mock с одним кадром для цикла захвата."""

            def __init__(self) -> None:
                self.is_capture_lost = False
                self._read_count = 0

            def start(self, capture_area: CaptureArea) -> None:
                _ = capture_area

            def read_frame(self, timeout: float):
                _ = timeout
                if self._read_count == 0:
                    self._read_count += 1
                    return np.zeros((32, 32, 3), dtype=np.uint8)
                return None

            def stop(self) -> None:
                return

        mock_session = MockSession()
        with (
            patch(
                "recorder.video_recorder._WindowsCaptureSession",
                return_value=mock_session,
            ),
            patch.object(recorder, "_cleanup") as mock_cleanup,
        ):
            recorder._capture_loop()

        assert recorder.frame_count == 0
        assert recorder.state == RecordingState.STOPPING
        mock_cleanup.assert_called_once()
        error_callback.assert_called_once()
        assert "ротации" in error_callback.call_args.args[0]
        recorder._ffmpeg_writer.mark_corrupted.assert_not_called()
        assert recorder.stopped_due_to_low_disk_space is False
        assert recorder.stopped_due_to_segment_rotation_failure is True

    def test_start_passes_disk_thresholds_to_ffmpeg_writer(
        self, tmp_path: Path
    ) -> None:
        """Пороги диска из конструктора передаются в FFmpegVideoWriter."""
        recorder = VideoRecorder(
            use_ffmpeg=True,
            disk_warning_mb=512.0,
            disk_critical_mb=64.0,
            disk_check_interval_s=5.0,
        )
        capture_area = CaptureArea(type="full", width=1280, height=720)
        mock_writer = MagicMock()
        mock_writer.open.return_value = True
        mock_writer_class = MagicMock(return_value=mock_writer)

        with (
            patch(
                "recorder.video_recorder.get_platform", return_value="windows"
            ),
            patch(
                "recorder.ffmpeg_writer.FFmpegVideoWriter",
                mock_writer_class,
            ),
            patch.object(recorder, "_capture_loop"),
        ):
            result = recorder.start(tmp_path / "video.mp4", capture_area)

        assert result is True
        _, kwargs = mock_writer_class.call_args
        assert kwargs["disk_warning_mb"] == 512.0
        assert kwargs["disk_critical_mb"] == 64.0
        assert kwargs["disk_check_interval_s"] == 5.0

    def test_start_passes_segment_limits_to_ffmpeg_writer(
        self, tmp_path: Path
    ) -> None:
        """Лимиты сегмента из конструктора передаются в FFmpegVideoWriter."""
        recorder = VideoRecorder(
            use_ffmpeg=True,
            max_segment_size_mb=256.0,
            max_segment_duration_s=120.0,
        )
        capture_area = CaptureArea(type="full", width=1280, height=720)
        mock_writer = MagicMock()
        mock_writer.open.return_value = True
        mock_writer_class = MagicMock(return_value=mock_writer)

        with (
            patch(
                "recorder.video_recorder.get_platform", return_value="windows"
            ),
            patch(
                "recorder.ffmpeg_writer.FFmpegVideoWriter",
                mock_writer_class,
            ),
            patch.object(recorder, "_capture_loop"),
        ):
            result = recorder.start(tmp_path / "video.mp4", capture_area)

        assert result is True
        _, kwargs = mock_writer_class.call_args
        assert kwargs["max_segment_size_mb"] == 256.0
        assert kwargs["max_segment_duration_s"] == 120.0


class TestVideoRecorderCaptureSourceSwitch:
    """Тесты горячего переключения источника захвата (#48)."""

    def test_switch_capture_source_rejected_when_not_recording(self) -> None:
        """Переключение недоступно, если запись не активна."""
        recorder = VideoRecorder(use_ffmpeg=True)
        recorder._state = RecordingState.IDLE

        success, error = recorder.switch_capture_source(
            CaptureArea(type="full", width=32, height=32)
        )

        assert success is False
        assert "не активна" in error

    def test_switch_capture_source_rejected_for_non_ffmpeg_mode(self) -> None:
        """Переключение недоступно в legacy-режиме без FFmpeg."""
        recorder = VideoRecorder(use_ffmpeg=False)
        recorder._state = RecordingState.RECORDING

        success, error = recorder.switch_capture_source(
            CaptureArea(type="full", width=32, height=32)
        )

        assert success is False
        assert "FFmpeg" in error

    def test_switch_capture_source_times_out_when_loop_not_running(
        self,
    ) -> None:
        """Без обработки в capture loop переключение завершается таймаутом."""
        recorder = VideoRecorder(use_ffmpeg=True)
        recorder._state = RecordingState.RECORDING
        recorder._ffmpeg_writer = MagicMock()

        success, error = recorder.switch_capture_source(
            CaptureArea(type="full", width=32, height=32), timeout=0.05
        )

        assert success is False
        assert "Таймаут" in error
        assert recorder._pending_switch_area is None

    def test_capture_loop_applies_pending_switch_same_resolution(
        self,
    ) -> None:
        """Переключение на источник того же размера не ротирует сегмент."""
        recorder = VideoRecorder(use_ffmpeg=True)
        recorder._state = RecordingState.RECORDING
        recorder._capture_area = CaptureArea(type="full", width=32, height=32)
        recorder._ffmpeg_writer = MagicMock()
        recorder._ffmpeg_writer.write.return_value = True

        new_area = CaptureArea(
            type="window", width=32, height=32, window_title="Notepad"
        )
        recorder._pending_switch_area = new_area

        class MockSession:
            def __init__(self) -> None:
                self.is_capture_lost = False
                self.started_with: CaptureArea | None = None

            def start(self, capture_area: CaptureArea) -> None:
                self.started_with = capture_area

            def read_frame(self, timeout: float):
                _ = timeout
                recorder._shutdown_event.set()
                return None

            def stop(self) -> None:
                return

        new_session = MockSession()
        with patch(
            "recorder.video_recorder._WindowsCaptureSession",
            side_effect=[MockSession(), new_session],
        ):
            recorder._capture_loop()

        assert recorder._capture_area is new_area
        assert recorder._switch_result == (True, None)
        assert new_session.started_with is new_area
        recorder._ffmpeg_writer.switch_resolution.assert_not_called()

    def test_capture_loop_applies_pending_switch_different_resolution(
        self,
    ) -> None:
        """Переключение на источник другого размера вызывает switch_resolution()."""
        recorder = VideoRecorder(use_ffmpeg=True)
        recorder._state = RecordingState.RECORDING
        recorder._capture_area = CaptureArea(
            type="full", width=1920, height=1080
        )
        recorder._ffmpeg_writer = MagicMock()
        recorder._ffmpeg_writer.switch_resolution.return_value = True

        new_area = CaptureArea(
            type="window", width=800, height=600, window_title="Notepad"
        )
        recorder._pending_switch_area = new_area

        class MockSession:
            def __init__(self) -> None:
                self.is_capture_lost = False

            def start(self, capture_area: CaptureArea) -> None:
                _ = capture_area

            def read_frame(self, timeout: float):
                _ = timeout
                recorder._shutdown_event.set()
                return None

            def stop(self) -> None:
                return

        with patch(
            "recorder.video_recorder._WindowsCaptureSession",
            side_effect=[MockSession(), MockSession()],
        ):
            recorder._capture_loop()

        recorder._ffmpeg_writer.switch_resolution.assert_called_once_with(
            800, 600
        )
        assert recorder._capture_area is new_area
        assert recorder._switch_result == (True, None)

    def test_switch_rolls_back_when_new_session_fails_to_start(
        self,
    ) -> None:
        """Неудача запуска новой сессии не должна прерывать текущую запись."""
        recorder = VideoRecorder(use_ffmpeg=True)
        recorder._state = RecordingState.RECORDING
        original_area = CaptureArea(type="full", width=32, height=32)
        recorder._capture_area = original_area
        recorder._ffmpeg_writer = MagicMock()

        new_area = CaptureArea(
            type="window", width=32, height=32, window_title="Missing"
        )
        recorder._pending_switch_area = new_area

        class OldSession:
            def __init__(self) -> None:
                self.is_capture_lost = False
                self.read_frame_calls = 0

            def start(self, capture_area: CaptureArea) -> None:
                _ = capture_area

            def read_frame(self, timeout: float):
                _ = timeout
                # Доказывает, что после отказа от переключения цикл
                # продолжил работу со старой сессией, а не упал/завис.
                self.read_frame_calls += 1
                recorder._shutdown_event.set()
                return None

            def stop(self) -> None:
                return

        class FailingNewSession:
            def start(self, capture_area: CaptureArea) -> None:
                _ = capture_area
                raise RuntimeError("окно не найдено")

        old_session = OldSession()
        with patch(
            "recorder.video_recorder._WindowsCaptureSession",
            side_effect=[old_session, FailingNewSession()],
        ):
            recorder._capture_loop()

        assert recorder._switch_result == (False, "окно не найдено")
        assert recorder._capture_area is original_area
        assert old_session.read_frame_calls == 1
        recorder._ffmpeg_writer.switch_resolution.assert_not_called()

    def test_switch_rolls_back_when_resolution_switch_fails(self) -> None:
        """Неудача смены разрешения откатывает переключение без прерывания записи."""
        recorder = VideoRecorder(use_ffmpeg=True)
        recorder._state = RecordingState.RECORDING
        original_area = CaptureArea(type="full", width=1920, height=1080)
        recorder._capture_area = original_area
        recorder._ffmpeg_writer = MagicMock()
        recorder._ffmpeg_writer.switch_resolution.return_value = False

        new_area = CaptureArea(
            type="window", width=800, height=600, window_title="Notepad"
        )
        recorder._pending_switch_area = new_area

        class OldSession:
            def __init__(self) -> None:
                self.is_capture_lost = False
                self.read_frame_calls = 0

            def start(self, capture_area: CaptureArea) -> None:
                _ = capture_area

            def read_frame(self, timeout: float):
                _ = timeout
                # Доказывает, что после отказа от переключения цикл
                # продолжил работу со старой сессией, а не упал/завис.
                self.read_frame_calls += 1
                recorder._shutdown_event.set()
                return None

            def stop(self) -> None:
                return

        class NewSession:
            def __init__(self) -> None:
                self.stopped = False

            def start(self, capture_area: CaptureArea) -> None:
                _ = capture_area

            def stop(self) -> None:
                self.stopped = True

        old_session = OldSession()
        new_session = NewSession()
        with patch(
            "recorder.video_recorder._WindowsCaptureSession",
            side_effect=[old_session, new_session],
        ):
            recorder._capture_loop()

        assert recorder._switch_result is not None
        assert recorder._switch_result[0] is False
        assert recorder._capture_area is original_area
        assert new_session.stopped is True
        assert old_session.read_frame_calls == 1


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
class TestVideoRecorderStart:
    """Тесты запуска видеозаписи."""

    @pytest.fixture
    def recorder(self) -> VideoRecorder:
        """Создаёт рекордер для тестов (без FFmpeg)."""
        return VideoRecorder(use_ffmpeg=False)

    def test_start_from_idle_state(
        self, recorder: VideoRecorder, tmp_path: Path
    ) -> None:
        """Проверка запуска записи из состояния IDLE."""
        output_path = tmp_path / "test_video.mp4"
        capture_area = CaptureArea(type="full", width=1920, height=1080)

        with patch("recorder.video_recorder.cv2.VideoWriter"):
            with patch.object(recorder, "_capture_loop"):
                result = recorder.start(output_path, capture_area)

        assert result is True
        assert recorder.state == RecordingState.RECORDING
        assert recorder.output_path == output_path

    def test_start_from_recording_state_returns_false(
        self, recorder: VideoRecorder, tmp_path: Path
    ) -> None:
        """Проверка что запуск из состояния RECORDING возвращает False."""
        recorder._state = RecordingState.RECORDING
        output_path = tmp_path / "test_video.mp4"
        capture_area = CaptureArea(type="full")

        result = recorder.start(output_path, capture_area)

        assert result is False

    def test_start_from_paused_state_returns_false(
        self, recorder: VideoRecorder, tmp_path: Path
    ) -> None:
        """Проверка что запуск из состояния PAUSED возвращает False."""
        recorder._state = RecordingState.PAUSED
        output_path = tmp_path / "test_video.mp4"
        capture_area = CaptureArea(type="full")

        result = recorder.start(output_path, capture_area)

        assert result is False

    def test_start_creates_output_directory(
        self, recorder: VideoRecorder, tmp_path: Path
    ) -> None:
        """Проверка создания директории вывода."""
        output_path = tmp_path / "subdir" / "test_video.mp4"
        capture_area = CaptureArea(type="full", width=1920, height=1080)

        with patch("recorder.video_recorder.cv2.VideoWriter"):
            with patch.object(recorder, "_capture_loop"):
                result = recorder.start(output_path, capture_area)

        assert result is True
        assert output_path.parent.exists()

    def test_start_with_duration(
        self, recorder: VideoRecorder, tmp_path: Path
    ) -> None:
        """Проверка запуска с ограничением длительности."""
        output_path = tmp_path / "test_video.mp4"
        capture_area = CaptureArea(type="full", width=1920, height=1080)

        with patch("recorder.video_recorder.cv2.VideoWriter"):
            with patch.object(recorder, "_capture_loop"):
                result = recorder.start(
                    output_path, capture_area, duration=10.0
                )

        assert result is True
        assert recorder._duration == 10.0


class TestVideoRecorderStop:
    """Тесты остановки видеозаписи."""

    @pytest.fixture
    def recorder(self) -> VideoRecorder:
        """Создаёт рекордер для тестов (без FFmpeg)."""
        return VideoRecorder(use_ffmpeg=False)

    def test_stop_from_recording_state(
        self, recorder: VideoRecorder, tmp_path: Path
    ) -> None:
        """Проверка остановки из состояния RECORDING."""
        recorder._state = RecordingState.RECORDING
        recorder._output_path = tmp_path / "test.mp4"
        recorder._capture_thread = None
        recorder._write_thread = None

        with patch.object(recorder, "_cleanup"):
            result = recorder.stop()

        assert result is True
        assert recorder.state == RecordingState.STOPPING

    def test_stop_from_paused_state(
        self, recorder: VideoRecorder, tmp_path: Path
    ) -> None:
        """Проверка остановки из состояния PAUSED."""
        recorder._state = RecordingState.PAUSED
        recorder._output_path = tmp_path / "test.mp4"
        recorder._capture_thread = None
        recorder._write_thread = None

        with patch.object(recorder, "_cleanup"):
            result = recorder.stop()

        assert result is True

    def test_stop_logs_warning_when_capture_thread_slow(
        self,
        recorder: VideoRecorder,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Таймаут join должен логироваться как warning."""

        class SlowThread:
            """Поток, который завершается только после cleanup."""

            def __init__(self) -> None:
                self._alive_checks = iter([True, True, False, False])

            def is_alive(self) -> bool:
                return next(self._alive_checks)

            @staticmethod
            def join(timeout: float) -> None:
                _ = timeout

        recorder._state = RecordingState.RECORDING
        recorder._output_path = tmp_path / "slow.mp4"
        recorder._capture_thread = SlowThread()  # type: ignore[assignment]

        with (
            patch.object(recorder, "_cleanup", return_value=True),
            caplog.at_level("WARNING"),
        ):
            result = recorder.stop()

        assert result is True
        assert "Поток захвата не завершился за" in caplog.text

    def test_stop_returns_false_when_capture_thread_hangs(
        self, recorder: VideoRecorder, tmp_path: Path
    ) -> None:
        """Если поток не завершился после cleanup, stop возвращает False."""

        class HungThread:
            """Поток, который не завершается даже после cleanup."""

            @staticmethod
            def is_alive() -> bool:
                return True

            @staticmethod
            def join(timeout: float) -> None:
                _ = timeout

        recorder._state = RecordingState.RECORDING
        recorder._output_path = tmp_path / "hung.mp4"
        recorder._capture_thread = HungThread()  # type: ignore[assignment]

        with patch.object(recorder, "_cleanup", return_value=True):
            result = recorder.stop()

        assert result is False


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-only test")
class TestVideoRecorderIntegration:
    """Интеграционные тесты VideoRecorder."""

    def test_full_lifecycle_mocked(self, tmp_path: Path) -> None:
        """Проверка полного жизненного цикла записи (с моками)."""
        recorder = VideoRecorder(use_ffmpeg=False)
        output_path = tmp_path / "lifecycle.mp4"
        capture_area = CaptureArea(type="full", width=1920, height=1080)

        # Мокаем все внешние зависимости
        with patch("recorder.video_recorder.cv2.VideoWriter"):
            with patch.object(recorder, "_capture_loop"):
                # Запуск
                assert recorder.start(output_path, capture_area) is True
                assert recorder.is_recording is True

                # Пауза
                assert recorder.pause() is True
                assert recorder.is_paused is True

                # Возобновление
                assert recorder.resume() is True
                assert recorder.is_recording is True

                # Остановка
                recorder._capture_thread = None
                recorder._write_thread = None
                with patch.object(recorder, "_cleanup"):
                    assert recorder.stop() is True


class TestVideoRecorderErrorHandling:
    """Тесты ошибок и восстановления видеозаписи."""

    @pytest.fixture
    def recorder(self) -> VideoRecorder:
        """Создаёт рекордер для тестов."""
        return VideoRecorder(use_ffmpeg=False)

    def test_start_rejects_non_windows_platform(
        self, recorder: VideoRecorder, tmp_path: Path
    ) -> None:
        """Проверка отказа запуска вне Windows."""
        error_callback = MagicMock()
        recorder.set_callbacks(on_error=error_callback)
        capture_area = CaptureArea(type="full", width=1920, height=1080)

        with patch(
            "recorder.video_recorder.get_platform", return_value="linux"
        ):
            result = recorder.start(tmp_path / "video.mp4", capture_area)

        assert result is False
        assert recorder.state == RecordingState.IDLE
        error_callback.assert_called_once()
        assert "Windows" in error_callback.call_args.args[0]

    def test_start_resets_capture_lost_flag(
        self, recorder: VideoRecorder, tmp_path: Path
    ) -> None:
        """Проверка сброса флага потери захвата при новом старте."""
        recorder._capture_lost = True
        capture_area = CaptureArea(type="full", width=1280, height=720)

        with (
            patch(
                "recorder.video_recorder.get_platform", return_value="windows"
            ),
            patch("recorder.video_recorder.cv2.VideoWriter"),
            patch.object(recorder, "_capture_loop"),
        ):
            result = recorder.start(tmp_path / "video.mp4", capture_area)

        assert result is True
        assert recorder.is_capture_lost is False

    def test_start_cleans_up_when_ffmpeg_writer_fails_to_open(
        self, tmp_path: Path
    ) -> None:
        """Проверка очистки при ошибке открытия FFmpeg writer."""
        recorder = VideoRecorder(use_ffmpeg=True)
        error_callback = MagicMock()
        recorder.set_callbacks(on_error=error_callback)
        capture_area = CaptureArea(type="full", width=1280, height=720)
        mock_writer = MagicMock()
        mock_writer.open.return_value = False

        with (
            patch(
                "recorder.video_recorder.get_platform", return_value="windows"
            ),
            patch(
                "recorder.ffmpeg_writer.FFmpegVideoWriter",
                return_value=mock_writer,
            ),
            patch.object(recorder, "_cleanup") as mock_cleanup,
        ):
            result = recorder.start(tmp_path / "video.mp4", capture_area)

        assert result is False
        mock_cleanup.assert_called_once()
        error_callback.assert_called_once()
        assert (
            "Не удалось открыть FFmpeg видеозапись"
            in (error_callback.call_args.args[0])
        )

    def test_start_passes_max_recovery_attempts_to_ffmpeg_writer(
        self, tmp_path: Path
    ) -> None:
        """max_recovery_attempts из конструктора передаётся в FFmpegVideoWriter."""
        recorder = VideoRecorder(use_ffmpeg=True, max_recovery_attempts=5)
        capture_area = CaptureArea(type="full", width=1280, height=720)
        mock_writer = MagicMock()
        mock_writer.open.return_value = True
        mock_writer_class = MagicMock(return_value=mock_writer)

        with (
            patch(
                "recorder.video_recorder.get_platform", return_value="windows"
            ),
            patch(
                "recorder.ffmpeg_writer.FFmpegVideoWriter",
                mock_writer_class,
            ),
            patch.object(recorder, "_capture_loop"),
        ):
            result = recorder.start(tmp_path / "video.mp4", capture_area)

        assert result is True
        _, kwargs = mock_writer_class.call_args
        assert kwargs["max_recovery_attempts"] == 5

    def test_capture_loop_marks_capture_lost(self) -> None:
        """Проверка фиксации потери захвата в основном цикле."""
        recorder = VideoRecorder(use_ffmpeg=False)
        recorder._state = RecordingState.RECORDING
        recorder._capture_area = CaptureArea(type="full", width=32, height=32)

        class MockSession:
            """Простейшая сессия, сразу сообщающая о потере захвата."""

            is_capture_lost = True

            def start(self, capture_area: CaptureArea) -> None:
                _ = capture_area

            def read_frame(self, timeout: float):
                _ = timeout
                raise AssertionError("read_frame вызываться не должен")

            def stop(self) -> None:
                return

        with patch(
            "recorder.video_recorder._WindowsCaptureSession",
            return_value=MockSession(),
        ):
            recorder._capture_loop()

        assert recorder.is_capture_lost is True
        assert recorder.state == RecordingState.IDLE

    def test_capture_loop_reconnects_window_capture(self) -> None:
        """Потеря window capture должна пытаться восстановиться."""
        recorder = VideoRecorder(use_ffmpeg=False)
        recorder._state = RecordingState.RECORDING
        recorder._capture_area = CaptureArea(
            type="window",
            width=32,
            height=32,
            window_title="Browser",
        )
        recorder._video_writer = MagicMock()

        frame = np.zeros((32, 32, 3), dtype=np.uint8)

        class LostSession:
            """Сессия, которая сразу сообщает о потере захвата."""

            is_capture_lost = True

            def start(self, capture_area: CaptureArea) -> None:
                _ = capture_area

            def read_frame(self, timeout: float):
                _ = timeout
                raise AssertionError("read_frame вызываться не должен")

            def stop(self) -> None:
                return

        class RecoveredSession:
            """Сессия, которая отдаёт кадр после восстановления."""

            def __init__(self) -> None:
                self.is_capture_lost = False

            def start(self, capture_area: CaptureArea) -> None:
                _ = capture_area

            def read_frame(self, timeout: float):
                _ = timeout
                recorder._shutdown_event.set()
                return frame

            def stop(self) -> None:
                return

        with (
            patch(
                "recorder.video_recorder._WindowsCaptureSession",
                side_effect=[LostSession(), RecoveredSession()],
            ),
            patch(
                "recorder.video_recorder.CaptureArea.from_window",
                return_value=CaptureArea(
                    type="window",
                    width=32,
                    height=32,
                    window_title="Browser",
                ),
            ),
        ):
            recorder._capture_loop()

        assert recorder._video_writer.write.call_count == 1
        assert recorder.is_capture_lost is False
        assert recorder.state == RecordingState.IDLE

    def test_capture_loop_reports_error_when_window_reconnect_fails(
        self,
    ) -> None:
        """После неудачного восстановления window capture приходит ошибка."""
        recorder = VideoRecorder(use_ffmpeg=False)
        error_callback = MagicMock()
        recorder.set_callbacks(on_error=error_callback)
        recorder._state = RecordingState.RECORDING
        recorder._capture_area = CaptureArea(
            type="window",
            width=32,
            height=32,
            window_title="Browser",
        )

        class LostSession:
            """Сессия, которая сразу теряет захват."""

            is_capture_lost = True

            def start(self, capture_area: CaptureArea) -> None:
                _ = capture_area

            def read_frame(self, timeout: float):
                _ = timeout
                raise AssertionError("read_frame вызываться не должен")

            def stop(self) -> None:
                return

        with (
            patch(
                "recorder.video_recorder._WindowsCaptureSession",
                return_value=LostSession(),
            ),
            patch(
                "recorder.video_recorder.CaptureArea.from_window",
                side_effect=ValueError("window not found"),
            ),
            patch(
                "recorder.video_recorder._WINDOW_CAPTURE_RECONNECT_TIMEOUT_SECONDS",
                0.01,
            ),
            patch(
                "recorder.video_recorder._WINDOW_CAPTURE_RECONNECT_POLL_SECONDS",
                0.001,
            ),
        ):
            recorder._capture_loop()

        error_callback.assert_called_once()
        assert "Захват потерян" in error_callback.call_args.args[0]
        assert recorder.is_capture_lost is True
        assert recorder.state == RecordingState.IDLE

    def test_capture_loop_writes_last_frame_for_opencv_on_capture_loss(
        self,
    ) -> None:
        """Последний кадр сохраняется и в OpenCV path при потере захвата."""
        recorder = VideoRecorder(use_ffmpeg=False)
        recorder._state = RecordingState.RECORDING
        recorder._capture_area = CaptureArea(type="full", width=16, height=16)
        video_writer = MagicMock()
        recorder._video_writer = video_writer
        frame = np.zeros((16, 16, 3), dtype=np.uint8)

        class LostAfterReadSession:
            """Сессия, теряющая захват сразу после получения кадра."""

            def __init__(self) -> None:
                self.is_capture_lost = False

            def start(self, capture_area: CaptureArea) -> None:
                _ = capture_area

            def read_frame(self, timeout: float):
                _ = timeout
                self.is_capture_lost = True
                return frame

            def stop(self) -> None:
                return

        with patch(
            "recorder.video_recorder._WindowsCaptureSession",
            return_value=LostAfterReadSession(),
        ):
            recorder._capture_loop()

        video_writer.write.assert_called_once_with(frame)
        video_writer.release.assert_called_once()
        assert recorder._video_writer is None
        assert recorder.is_capture_lost is True

    def test_stop_returns_false_when_cleanup_fails(
        self, recorder: VideoRecorder, tmp_path: Path
    ) -> None:
        """Проверка реакции stop на неуспешную очистку."""
        recorder._state = RecordingState.RECORDING
        recorder._output_path = tmp_path / "video.mp4"

        with patch.object(recorder, "_cleanup", return_value=False):
            result = recorder.stop()

        assert result is False
        assert recorder.state == RecordingState.STOPPING

    def test_windows_capture_session_stop_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Ошибка остановки capture session должна логироваться."""
        from recorder.video_recorder import _WindowsCaptureSession

        class BrokenControl:
            """Контроль, имитирующий ошибку остановки native сессии."""

            @staticmethod
            def stop() -> None:
                raise RuntimeError("native stop failed")

        session = _WindowsCaptureSession()
        session._control = BrokenControl()

        with caplog.at_level("WARNING"):
            session.stop()

        assert "Не удалось корректно остановить capture session" in (
            caplog.text
        )

    def test_capture_loop_logs_warning_when_session_stop_fails(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Ветка finally должна логировать ошибку остановки session."""
        recorder = VideoRecorder(use_ffmpeg=False)
        recorder._state = RecordingState.RECORDING
        recorder._capture_area = CaptureArea(type="full", width=64, height=64)

        class BrokenSession:
            """Сессия, которая падает при старте и остановке."""

            is_capture_lost = False

            @staticmethod
            def start(_capture_area: CaptureArea) -> None:
                raise RuntimeError("start failed")

            @staticmethod
            def stop() -> None:
                raise RuntimeError("stop failed")

        with (
            patch(
                "recorder.video_recorder._WindowsCaptureSession",
                return_value=BrokenSession(),
            ),
            caplog.at_level("WARNING"),
        ):
            recorder._capture_loop()

        assert "Ошибка при остановке capture session в finally" in caplog.text
