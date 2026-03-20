"""
Тесты модуля видеозаписи
========================

Тестирует классы CaptureArea и VideoRecorder.
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        with patch("recorder.video_recorder.get_screen_size") as mock_size:
            mock_size.return_value = (1920, 1080)
            area = CaptureArea.full_screen()

        assert area.type == "full"
        assert area.width == 1920
        assert area.height == 1080

    def test_full_screen_with_monitor_index(self) -> None:
        """Проверка создания области полного экрана с индексом монитора."""
        with patch("recorder.video_recorder.get_screen_size") as mock_size:
            mock_size.return_value = (2560, 1440)
            area = CaptureArea.full_screen(monitor_index=2)

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
            patch("recorder.video_recorder.get_screen_size") as mock_size,
        ):
            mock_windows.return_value = []
            mock_size.return_value = (1920, 1080)
            area = CaptureArea.from_window("Nonexistent Window")

        assert area.type == "full"
        assert area.width == 1920
        assert area.height == 1080

    def test_to_mss_dict(self) -> None:
        """Проверка преобразования в формат MSS."""
        area = CaptureArea(type="rect", x=100, y=200, width=800, height=600)
        mss_dict = area.to_mss_dict()

        assert mss_dict["left"] == 100
        assert mss_dict["top"] == 200
        assert mss_dict["width"] == 800
        assert mss_dict["height"] == 600


class TestVideoRecorder:
    """Тесты класса VideoRecorder."""

    @pytest.fixture
    def recorder(self) -> VideoRecorder:
        """Создаёт рекордер для тестов."""
        return VideoRecorder()

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


class TestVideoRecorderStart:
    """Тесты запуска видеозаписи."""

    @pytest.fixture
    def recorder(self) -> VideoRecorder:
        """Создаёт рекордер для тестов."""
        return VideoRecorder()

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
        """Создаёт рекордер для тестов."""
        return VideoRecorder()

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


class TestVideoRecorderIntegration:
    """Интеграционные тесты VideoRecorder."""

    def test_full_lifecycle_mocked(self, tmp_path: Path) -> None:
        """Проверка полного жизненного цикла записи (с моками)."""
        recorder = VideoRecorder()
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
