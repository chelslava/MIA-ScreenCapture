"""
Расширенные unit тесты для VideoRecorder
=========================================

Дополнительные тесты для повышения покрытия video_recorder до 90%.
"""

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from recorder.video_recorder import CaptureArea, RecordingState, VideoRecorder


class TestCaptureAreaExtended:
    """Расширенные тесты для CaptureArea."""

    def test_capture_area_full_screen(self) -> None:
        """Проверка создания области полного экрана."""
        with patch(
            "recorder.video_recorder.get_available_monitors",
            return_value=[
                {"index": 0, "width": 1920, "height": 1080, "is_primary": True}
            ],
        ):
            area = CaptureArea.full_screen()

        assert area.type == "full"
        assert area.width == 1920
        assert area.height == 1080
        assert area.x == 0
        assert area.y == 0

    def test_capture_area_from_rect(self) -> None:
        """Проверка создания прямоугольной области."""
        with patch(
            "recorder.video_recorder.validate_rect_coords",
            return_value=(100, 100, 800, 600),
        ):
            area = CaptureArea.from_rect(100, 100, 800, 600)

        assert area.type == "rect"
        assert area.x == 100
        assert area.y == 100
        assert area.width == 700
        assert area.height == 500

    def test_capture_area_from_rect_swapped_coords(self) -> None:
        """Проверка создания области с переставленными координатами."""
        with patch(
            "recorder.video_recorder.validate_rect_coords",
            return_value=(100, 100, 800, 600),
        ):
            area = CaptureArea.from_rect(800, 600, 100, 100)

        # Координаты должны быть нормализованы
        assert area.x == 100
        assert area.y == 100

    def test_capture_area_from_window_found(self) -> None:
        """Проверка создания области из найденного окна."""
        mock_windows = [
            {
                "title": "Browser",
                "x": 0,
                "y": 0,
                "width": 1920,
                "height": 1080,
            },
            {
                "title": "Editor",
                "x": 100,
                "y": 100,
                "width": 800,
                "height": 600,
            },
        ]

        with patch(
            "recorder.video_recorder.get_available_windows",
            return_value=mock_windows,
        ):
            area = CaptureArea.from_window("Browser")

        assert area.type == "window"
        assert area.window_title == "Browser"
        assert area.width == 1920

    def test_capture_area_from_window_partial_match(self) -> None:
        """Проверка создания области при частичном совпадении заголовка."""
        mock_windows = [
            {
                "title": "Google Chrome - Page",
                "x": 0,
                "y": 0,
                "width": 1920,
                "height": 1080,
            },
        ]

        with patch(
            "recorder.video_recorder.get_available_windows",
            return_value=mock_windows,
        ):
            area = CaptureArea.from_window("Chrome")

        assert area.type == "window"
        assert "Chrome" in area.window_title

    def test_capture_area_from_window_not_found(self) -> None:
        """Проверка создания области когда окно не найдено."""
        mock_windows = []

        with (
            patch(
                "recorder.video_recorder.get_available_windows",
                return_value=mock_windows,
            ),
            patch(
                "recorder.video_recorder.get_available_monitors",
                return_value=[
                    {
                        "index": 0,
                        "width": 1920,
                        "height": 1080,
                        "is_primary": True,
                    }
                ],
            ),
        ):
            area = CaptureArea.from_window("NonExistent")

        # Должен вернуться полный экран
        assert area.type == "full"

    def test_capture_area_to_capture_dict(self) -> None:
        """Проверка преобразования в формат области захвата."""
        area = CaptureArea(type="rect", x=100, y=200, width=800, height=600)

        capture_dict = area.to_capture_dict()

        assert capture_dict["left"] == 100
        assert capture_dict["top"] == 200
        assert capture_dict["width"] == 800
        assert capture_dict["height"] == 600

    def test_capture_area_dataclass_equality(self) -> None:
        """Проверка равенства dataclass."""
        area1 = CaptureArea(type="rect", x=100, y=100, width=800, height=600)
        area2 = CaptureArea(type="rect", x=100, y=100, width=800, height=600)

        assert area1 == area2


class TestVideoRecorderInit:
    """Тесты инициализации VideoRecorder."""

    def test_init_default_params(self) -> None:
        """Проверка параметров по умолчанию."""
        recorder = VideoRecorder()

        assert recorder.fps == 30
        assert recorder.codec == "libx264"
        assert recorder.bitrate == "2M"
        assert recorder.output_format == "mp4"

    def test_init_custom_params(self) -> None:
        """Проверка пользовательских параметров."""
        recorder = VideoRecorder(
            fps=60, codec="h264", bitrate="5M", output_format="avi"
        )

        assert recorder.fps == 60
        assert recorder.codec == "h264"
        assert recorder.bitrate == "5M"
        assert recorder.output_format == "avi"

    def test_init_state_idle(self) -> None:
        """Проверка начального состояния."""
        recorder = VideoRecorder()

        assert recorder.state == RecordingState.IDLE
        assert recorder.is_recording is False
        assert recorder.is_paused is False

    def test_init_elapsed_time_zero(self) -> None:
        """Проверка начального времени."""
        recorder = VideoRecorder()

        assert recorder.elapsed_time == 0

    def test_init_frame_count_zero(self) -> None:
        """Проверка начального количества кадров."""
        recorder = VideoRecorder()

        assert recorder.frame_count == 0

    def test_init_output_path_none(self) -> None:
        """Проверка начального пути вывода."""
        recorder = VideoRecorder()

        assert recorder.output_path is None

    def test_codec_map_exists(self) -> None:
        """Проверка карты кодеков."""
        assert hasattr(VideoRecorder, "CODEC_MAP")
        assert "libx264" in VideoRecorder.CODEC_MAP
        assert "h264" in VideoRecorder.CODEC_MAP


class TestVideoRecorderState:
    """Тесты состояний VideoRecorder."""

    def test_state_property(self) -> None:
        """Проверка свойства state."""
        recorder = VideoRecorder()

        assert recorder.state == RecordingState.IDLE

        recorder._state = RecordingState.RECORDING
        assert recorder.state == RecordingState.RECORDING

    def test_is_recording_property(self) -> None:
        """Проверка свойства is_recording."""
        recorder = VideoRecorder()

        assert recorder.is_recording is False

        recorder._state = RecordingState.RECORDING
        assert recorder.is_recording is True

        recorder._state = RecordingState.PAUSED
        assert recorder.is_recording is False

    def test_is_paused_property(self) -> None:
        """Проверка свойства is_paused."""
        recorder = VideoRecorder()

        assert recorder.is_paused is False

        recorder._state = RecordingState.PAUSED
        assert recorder.is_paused is True


class TestVideoRecorderElapsed:
    """Тесты расчёта времени записи."""

    def test_elapsed_time_not_started(self) -> None:
        """Проверка времени до начала записи."""
        recorder = VideoRecorder()

        assert recorder.elapsed_time == 0

    def test_elapsed_time_after_start(self) -> None:
        """Проверка времени после начала записи."""
        recorder = VideoRecorder()
        recorder._start_time = time.time() - 10  # 10 секунд назад
        recorder._state = RecordingState.RECORDING

        elapsed = recorder.elapsed_time

        assert 9 < elapsed < 11  # Примерно 10 секунд

    def test_elapsed_time_during_pause(self) -> None:
        """Проверка времени во время паузы."""
        recorder = VideoRecorder()
        recorder._start_time = time.time() - 20
        recorder._paused_time = time.time() - 5  # Пауза 5 секунд назад
        recorder._state = RecordingState.PAUSED

        elapsed = recorder.elapsed_time

        # Время паузы не должно учитываться
        assert 14 < elapsed < 16

    def test_elapsed_time_with_total_paused(self) -> None:
        """Проверка времени с учётом общей паузы."""
        recorder = VideoRecorder()
        recorder._start_time = time.time() - 30
        recorder._total_paused = 10  # 10 секунд общей паузы
        recorder._state = RecordingState.RECORDING

        elapsed = recorder.elapsed_time

        assert 19 < elapsed < 21


class TestVideoRecorderCallbacks:
    """Тесты обратных вызовов."""

    def test_set_callbacks(self) -> None:
        """Проверка установки callbacks."""
        recorder = VideoRecorder()

        on_frame = MagicMock()
        on_error = MagicMock()

        recorder.set_callbacks(on_frame_captured=on_frame, on_error=on_error)

        assert recorder._on_frame_captured == on_frame
        assert recorder._on_error == on_error

    def test_set_callbacks_none(self) -> None:
        """Проверка установки None callbacks."""
        recorder = VideoRecorder()

        recorder.set_callbacks(on_frame_captured=None, on_error=None)

        assert recorder._on_frame_captured is None
        assert recorder._on_error is None

    def test_set_callbacks_partial(self) -> None:
        """Проверка частичной установки callbacks."""
        recorder = VideoRecorder()

        on_frame = MagicMock()

        recorder.set_callbacks(on_frame_captured=on_frame)

        assert recorder._on_frame_captured == on_frame
        assert recorder._on_error is None


class TestVideoRecorderCodecSelection:
    """Тесты выбора кодека."""

    def test_get_opencv_codec_libx264(self) -> None:
        """Проверка получения OpenCV кодека для libx264."""
        VideoRecorder(codec="libx264")

        # libx264 -> mp4v в карте кодеков
        assert VideoRecorder.CODEC_MAP["libx264"] == "mp4v"

    def test_get_opencv_codec_h264(self) -> None:
        """Проверка получения OpenCV кодека для h264."""
        VideoRecorder(codec="h264")

        assert VideoRecorder.CODEC_MAP["h264"] == "mp4v"

    def test_get_opencv_codec_xvid(self) -> None:
        """Проверка получения OpenCV кодека для xvid."""
        VideoRecorder(codec="xvid")

        assert VideoRecorder.CODEC_MAP["xvid"] == "XVID"

    def test_get_opencv_codec_avc1(self) -> None:
        """Проверка получения OpenCV кодека для avc1."""
        VideoRecorder(codec="avc1")

        assert VideoRecorder.CODEC_MAP["avc1"] == "H264"


class TestVideoRecorderFrameStorage:
    """Тесты хранения последнего захваченного кадра."""

    def test_last_captured_frame_exists(self) -> None:
        """Проверка наличия буфера последнего кадра."""
        recorder = VideoRecorder()

        assert hasattr(recorder, "_last_captured_frame")
        assert recorder._last_captured_frame is None


class TestVideoRecorderThreading:
    """Тесты потоков записи."""

    def test_capture_thread_none_initially(self) -> None:
        """Проверка отсутствия потока захвата при инициализации."""
        recorder = VideoRecorder()

        assert recorder._capture_thread is None

    def test_lock_exists(self) -> None:
        """Проверка существования блокировки."""
        recorder = VideoRecorder()

        assert hasattr(recorder, "_lock")
        assert isinstance(recorder._lock, type(threading.Lock()))


class TestVideoRecorderStatistics:
    """Тесты статистики записи."""

    def test_frame_count_property(self) -> None:
        """Проверка свойства frame_count."""
        recorder = VideoRecorder()

        assert recorder.frame_count == 0

        recorder._frame_count = 100
        assert recorder.frame_count == 100

    def test_output_path_property(self) -> None:
        """Проверка свойства output_path."""
        recorder = VideoRecorder()

        assert recorder.output_path is None

        recorder._output_path = Path("/tmp/test.mp4")
        assert recorder.output_path == Path("/tmp/test.mp4")


class TestVideoRecorderEdgeCases:
    """Тесты граничных случаев."""

    def test_zero_fps(self) -> None:
        """Проверка с нулевым FPS."""
        # FPS = 0 может вызвать деление на ноль
        recorder = VideoRecorder(fps=0)

        assert recorder.fps == 0

    def test_very_high_fps(self) -> None:
        """Проверка с очень высоким FPS."""
        recorder = VideoRecorder(fps=120)

        assert recorder.fps == 120

    def test_empty_bitrate(self) -> None:
        """Проверка с пустым битрейтом."""
        recorder = VideoRecorder(bitrate="")

        assert recorder.bitrate == ""

    def test_unusual_output_format(self) -> None:
        """Проверка с необычным форматом вывода."""
        recorder = VideoRecorder(output_format="mkv")

        assert recorder.output_format == "mkv"

    def test_unknown_codec(self) -> None:
        """Проверка с неизвестным кодеком."""
        recorder = VideoRecorder(codec="unknown_codec")

        assert recorder.codec == "unknown_codec"


class TestRecordingStateEnum:
    """Тесты перечисления RecordingState."""

    def test_idle_value(self) -> None:
        """Проверка значения IDLE."""
        assert RecordingState.IDLE.value == "idle"

    def test_recording_value(self) -> None:
        """Проверка значения RECORDING."""
        assert RecordingState.RECORDING.value == "recording"

    def test_paused_value(self) -> None:
        """Проверка значения PAUSED."""
        assert RecordingState.PAUSED.value == "paused"

    def test_stopping_value(self) -> None:
        """Проверка значения STOPPING."""
        assert RecordingState.STOPPING.value == "stopping"

    def test_all_states_exist(self) -> None:
        """Проверка наличия всех состояний."""
        states = list(RecordingState)

        assert len(states) == 4
        assert RecordingState.IDLE in states
        assert RecordingState.RECORDING in states
        assert RecordingState.PAUSED in states
        assert RecordingState.STOPPING in states


class TestCaptureAreaEdgeCases:
    """Тесты граничных случаев для CaptureArea."""

    def test_zero_dimensions(self) -> None:
        """Проверка с нулевыми размерами."""
        area = CaptureArea(type="rect", x=0, y=0, width=0, height=0)

        assert area.width == 0
        assert area.height == 0

    def test_negative_coordinates(self) -> None:
        """Проверка с отрицательными координатами."""
        area = CaptureArea(type="rect", x=-100, y=-100, width=800, height=600)

        assert area.x == -100
        assert area.y == -100

    def test_very_large_dimensions(self) -> None:
        """Проверка с очень большими размерами."""
        area = CaptureArea(type="rect", x=0, y=0, width=10000, height=10000)

        assert area.width == 10000
        assert area.height == 10000

    def test_window_title_none(self) -> None:
        """Проверка с None в заголовке окна."""
        area = CaptureArea(type="full", window_title=None)

        assert area.window_title is None

    def test_window_title_with_special_chars(self) -> None:
        """Проверка с спецсимволами в заголовке окна."""
        area = CaptureArea(
            type="window", window_title="Window - Test (1) [HD]"
        )

        assert area.window_title == "Window - Test (1) [HD]"

    def test_type_values(self) -> None:
        """Проверка различных значений type."""
        for type_val in ["full", "window", "rect"]:
            area = CaptureArea(type=type_val)
            assert area.type == type_val
