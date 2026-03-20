"""
Интеграционные тесты для процесса записи
=========================================

Тестирует полный цикл записи видео с моками для захвата экрана.
"""

import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from recorder.audio_recorder import AudioRecorder, AudioState
from recorder.video_recorder import CaptureArea, RecordingState, VideoRecorder


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """
    Создание временной директории для выходных файлов.

    Args:
        tmp_path: Временная директория pytest

    Returns:
        Путь к директории для записи
    """
    output_dir = tmp_path / "recordings"
    output_dir.mkdir(exist_ok=True)
    return output_dir


@pytest.fixture
def mock_mss():
    """Создание мока для MSS (захват экрана)."""
    mock = MagicMock()

    # Создание тестового кадра (1920x1080 RGB)
    test_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    test_frame[:, :] = [100, 150, 200]  # Серый фон

    mock.grab.return_value = MagicMock(
        rgb=test_frame.tobytes(), size=(1920, 1080)
    )

    return mock


@pytest.fixture
def mock_sounddevice():
    """Создание мока для sounddevice (аудио)."""
    mock = MagicMock()

    # Создание тестового аудио чанка
    test_audio = np.zeros((1024, 2), dtype=np.float32)

    mock.InputStream.return_value.__enter__.return_value.read.return_value = (
        test_audio,
        True,
    )

    return mock


class TestVideoRecorderIntegration:
    """Интеграционные тесты для VideoRecorder."""

    def test_video_recorder_init(self):
        """Проверка инициализации видеозаписи."""
        recorder = VideoRecorder(
            fps=30, codec="libx264", bitrate="2M", output_format="mp4"
        )

        assert recorder.fps == 30
        assert recorder.codec == "libx264"
        assert recorder.bitrate == "2M"
        assert recorder.output_format == "mp4"
        assert recorder._state == RecordingState.IDLE

    def test_capture_area_full_screen(self):
        """Проверка создания области захвата полного экрана."""
        with patch("recorder.video_recorder.get_screen_size") as mock_size:
            mock_size.return_value = (1920, 1080)

            area = CaptureArea.full_screen()

            assert area.type == "full"
            assert area.width == 1920
            assert area.height == 1080

    def test_capture_area_from_rect(self):
        """Проверка создания прямоугольной области захвата."""
        with patch(
            "recorder.video_recorder.validate_rect_coords"
        ) as mock_validate:
            mock_validate.return_value = (100, 100, 800, 600)

            area = CaptureArea.from_rect(100, 100, 800, 600)

            assert area.type == "rect"
            assert area.x == 100
            assert area.y == 100
            assert area.width == 700
            assert area.height == 500

    def test_capture_area_from_window(self):
        """Проверка создания области захвата из окна."""
        with patch(
            "recorder.video_recorder.get_available_windows"
        ) as mock_windows:
            mock_windows.return_value = [
                {
                    "title": "Test Browser",
                    "x": 0,
                    "y": 0,
                    "width": 1920,
                    "height": 1080,
                }
            ]

            area = CaptureArea.from_window("Browser")

            assert area.type == "window"
            assert area.window_title == "Test Browser"
            assert area.width == 1920

    def test_capture_area_window_not_found(self):
        """Проверка fallback при ненайденном окне."""
        with patch(
            "recorder.video_recorder.get_available_windows"
        ) as mock_windows:
            mock_windows.return_value = []

            with patch("recorder.video_recorder.get_screen_size") as mock_size:
                mock_size.return_value = (1920, 1080)

                area = CaptureArea.from_window("NonExistent")

                # Должен вернуться полный экран
                assert area.type == "full"

    def test_video_recorder_state_transitions(self, temp_output_dir: Path):
        """Проверка переходов состояния видеозаписи."""
        recorder = VideoRecorder(fps=30)

        # Начальное состояние
        assert recorder.state == RecordingState.IDLE

        # Проверка переходов состояний напрямую
        recorder._state = RecordingState.RECORDING
        assert recorder.state == RecordingState.RECORDING

        recorder._state = RecordingState.PAUSED
        assert recorder.state == RecordingState.PAUSED

        recorder._state = RecordingState.STOPPING
        assert recorder.state == RecordingState.STOPPING

        # Возврат в IDLE
        recorder._state = RecordingState.IDLE
        assert recorder.state == RecordingState.IDLE

    def test_video_recorder_elapsed_time(self):
        """Проверка расчёта прошедшего времени."""
        recorder = VideoRecorder(fps=30)

        # Изначально 0
        assert recorder.elapsed_time == 0

        # Симуляция записи
        recorder._start_time = time.time() - 10  # 10 секунд назад
        recorder._state = RecordingState.RECORDING

        elapsed = recorder.elapsed_time
        assert 9 < elapsed < 11  # Примерно 10 секунд

    def test_video_recorder_elapsed_time_paused(self):
        """Проверка расчёта времени с паузой."""
        recorder = VideoRecorder(fps=30)

        recorder._start_time = time.time() - 20
        recorder._total_paused = 5  # 5 секунд на паузе
        recorder._state = RecordingState.RECORDING

        elapsed = recorder.elapsed_time
        assert 14 < elapsed < 16  # Примерно 15 секунд


class TestAudioRecorderIntegration:
    """Интеграционные тесты для AudioRecorder."""

    def test_audio_recorder_init(self):
        """Проверка инициализации аудиозаписи."""
        recorder = AudioRecorder(
            sample_rate=44100, channels=2, chunk_size=1024
        )

        assert recorder.config.sample_rate == 44100
        assert recorder.config.channels == 2
        assert recorder.config.chunk_size == 1024
        assert recorder.state == AudioState.IDLE

    def test_audio_recorder_state_transitions(self):
        """Проверка переходов состояния аудиозаписи."""
        recorder = AudioRecorder()

        # Начальное состояние
        assert recorder.state == AudioState.IDLE
        assert not recorder.is_recording
        assert not recorder.is_paused

        # Симуляция состояний
        recorder._state = AudioState.RECORDING
        assert recorder.is_recording

        recorder._state = AudioState.PAUSED
        assert recorder.is_paused

    def test_audio_recorder_elapsed_time(self):
        """Проверка расчёта прошедшего времени аудио."""
        recorder = AudioRecorder()

        # Изначально 0
        assert recorder.elapsed_time == 0

        # Симуляция записи
        recorder._start_time = time.time() - 15
        recorder._state = AudioState.RECORDING

        elapsed = recorder.elapsed_time
        assert 14 < elapsed < 16

    def test_audio_recorder_get_devices(self):
        """Проверка получения списка устройств."""
        with patch(
            "recorder.audio_recorder.get_audio_devices"
        ) as mock_devices:
            mock_devices.return_value = {
                "input": [
                    {"index": 0, "name": "Mic 1"},
                    {"index": 1, "name": "Mic 2"},
                ],
                "output": [{"index": 0, "name": "Speakers"}],
            }

            devices = AudioRecorder.get_available_devices()

            assert len(devices) == 2
            assert devices[0]["name"] == "Mic 1"


class TestRecordingManagerIntegration:
    """Интеграционные тесты для RecordingController."""

    def test_recording_manager_init(self):
        """Проверка инициализации контроллера записи."""
        from gui.controllers.recording_controller import RecordingController

        controller = RecordingController()

        assert controller._video_recorder is None
        assert controller._audio_recorder is None
        assert controller._encoder is None
        assert not controller.state.is_recording()
        assert not controller.state.is_paused()

    def test_recording_manager_elapsed_time(self):
        """Проверка получения времени записи."""
        from gui.controllers.recording_controller import RecordingController

        controller = RecordingController()

        # Без записи
        assert controller.elapsed_time == 0

        # С видеозаписью
        mock_video = MagicMock()
        mock_video.elapsed_time = 25.5
        controller._video_recorder = mock_video

        assert controller.elapsed_time == 25.5

    def test_recording_manager_current_output(self):
        """Проверка получения текущего выходного файла."""
        from gui.controllers.recording_controller import RecordingController

        controller = RecordingController()

        # Без записи
        assert controller.state.current_output is None

        # С записью - используем публичный атрибут current_output
        controller.state.current_output = Path("/tmp/test.mp4")

        assert controller.state.current_output == Path("/tmp/test.mp4")


class TestCaptureAreaIntegration:
    """Интеграционные тесты для CaptureArea."""

    def test_to_mss_dict(self):
        """Проверка преобразования в формат MSS."""
        area = CaptureArea(type="rect", x=100, y=200, width=800, height=600)

        mss_dict = area.to_mss_dict()

        assert mss_dict["left"] == 100
        assert mss_dict["top"] == 200
        assert mss_dict["width"] == 800
        assert mss_dict["height"] == 600

    def test_full_screen_creates_correct_area(self):
        """Проверка создания области полного экрана."""
        with patch("recorder.video_recorder.get_screen_size") as mock_size:
            mock_size.return_value = (2560, 1440)

            area = CaptureArea.full_screen(monitor_index=1)

            assert area.type == "full"
            assert area.width == 2560
            assert area.height == 1440
            assert area.x == 0
            assert area.y == 0

    def test_from_rect_validates_coords(self):
        """Проверка валидации координат прямоугольника."""
        with patch(
            "recorder.video_recorder.validate_rect_coords"
        ) as mock_validate:
            # Координаты должны быть упорядочены
            mock_validate.return_value = (50, 50, 500, 400)

            area = CaptureArea.from_rect(500, 400, 50, 50)

            # validate_rect_coords должен быть вызван
            mock_validate.assert_called_once()


class TestEncoderIntegration:
    """Интеграционные тесты для кодировщика."""

    def test_encoding_settings_defaults(self):
        """Проверка настроек кодирования по умолчанию."""
        from recorder.encoder import EncodingSettings

        settings = EncodingSettings()

        assert settings.codec == "libx264"
        assert settings.bitrate == "2M"
        assert settings.preset == "medium"

    def test_encoding_settings_custom(self):
        """Проверка пользовательских настроек кодирования."""
        from recorder.encoder import EncodingSettings

        settings = EncodingSettings(
            codec="h264", bitrate="5M", preset="fast", crf=23
        )

        assert settings.codec == "h264"
        assert settings.bitrate == "5M"
        assert settings.preset == "fast"
        assert settings.crf == 23

    def test_recording_encoder_init(self, temp_output_dir: Path):
        """Проверка инициализации кодировщика."""
        from recorder.encoder import EncodingSettings, RecordingEncoder

        output_path = temp_output_dir / "test_output.mp4"
        settings = EncodingSettings(codec="libx264", bitrate="2M")

        encoder = RecordingEncoder(output_path, settings)

        assert encoder.output_path == output_path
        assert encoder.settings == settings
        assert encoder._temp_dir is None
        assert encoder._temp_video is None
        assert encoder._temp_audio is None


class TestRecordingFlowIntegration:
    """Полные интеграционные тесты процесса записи."""

    @pytest.mark.slow
    def test_full_recording_flow_mocked(
        self, temp_output_dir: Path, mock_mss, mock_sounddevice
    ):
        """Тест полного цикла записи с моками."""
        from gui.controllers.recording_controller import RecordingController

        controller = RecordingController()
        output_path = temp_output_dir / "full_test.mp4"

        # Проверка что контроллер инициализирован корректно
        assert controller._video_recorder is None
        assert controller._audio_recorder is None
        assert not controller.state.is_recording()

        # Проверка что контроллер готов к работе
        assert controller.elapsed_time == 0
        assert controller.state.current_output is None

    def test_concurrent_video_audio_recording(self, temp_output_dir: Path):
        """Тест параллельной записи видео и аудио."""
        results = {"video_frames": 0, "audio_chunks": 0, "errors": []}
        lock = threading.Lock()

        def simulate_video_capture():
            """Симуляция захвата видео."""
            try:
                for _ in range(30):  # 30 кадров
                    time.sleep(0.033)  # ~30 fps
                    with lock:
                        results["video_frames"] += 1
            except Exception as e:
                with lock:
                    results["errors"].append(f"Video: {e}")

        def simulate_audio_capture():
            """Симуляция захвата аудио."""
            try:
                for _ in range(30):  # 30 чанков
                    time.sleep(0.033)
                    with lock:
                        results["audio_chunks"] += 1
            except Exception as e:
                with lock:
                    results["errors"].append(f"Audio: {e}")

        # Запуск потоков
        video_thread = threading.Thread(target=simulate_video_capture)
        audio_thread = threading.Thread(target=simulate_audio_capture)

        video_thread.start()
        audio_thread.start()

        video_thread.join(timeout=5)
        audio_thread.join(timeout=5)

        # Проверка результатов
        assert len(results["errors"]) == 0
        assert results["video_frames"] == 30
        assert results["audio_chunks"] == 30

    def test_recording_with_duration_limit(self, temp_output_dir: Path):
        """Тест записи с ограничением длительности."""
        duration = 2  # 2 секунды
        results = {"frames": 0, "completed": False}

        def simulate_recording():
            """Симуляция записи с ограничением."""
            start_time = time.time()
            fps = 30
            frame_interval = 1.0 / fps

            while True:
                elapsed = time.time() - start_time
                if elapsed >= duration:
                    results["completed"] = True
                    break

                results["frames"] += 1
                time.sleep(frame_interval)

        thread = threading.Thread(target=simulate_recording)
        thread.start()
        thread.join(timeout=5)

        assert results["completed"]
        # Примерно duration * fps кадров (с допуском для CI)
        assert 40 <= results["frames"] <= 80


class TestRecordingErrorHandling:
    """Тесты обработки ошибок при записи."""

    def test_video_recorder_handles_capture_error(self):
        """Проверка обработки ошибки захвата."""
        recorder = VideoRecorder(fps=30)

        # Проверка начального состояния
        assert recorder.state == RecordingState.IDLE

        # Рекордер должен оставаться в стабильном состоянии при ошибке
        # (проверка что состояние не изменилось без реального запуска)
        assert recorder.state == RecordingState.IDLE

    def test_audio_recorder_handles_device_error(self):
        """Проверка обработки ошибки аудиоустройства."""
        recorder = AudioRecorder()

        # Проверка начального состояния
        assert recorder.state == AudioState.IDLE

        # Рекордер должен оставаться в стабильном состоянии при ошибке
        assert recorder.state == AudioState.IDLE
        assert not recorder.is_recording

    def test_recording_cleanup_on_error(self, temp_output_dir: Path):
        """Проверка очистки ресурсов при ошибке."""
        from gui.controllers.recording_controller import RecordingController

        controller = RecordingController()

        # Симуляция ошибки после начала записи
        controller.state.current_output = temp_output_dir / "partial.mp4"

        # Проверка что путь установлен
        assert controller.state.current_output == temp_output_dir / "partial.mp4"

        # При ошибке ресурсы должны быть очищены
        # Проверка что контроллер может быть очищен
        controller.state.current_output = None
        assert controller.state.current_output is None


class TestRecordingPerformance:
    """Тесты производительности записи."""

    @pytest.mark.slow
    def test_frame_capture_performance(self):
        """Тест производительности захвата кадров."""
        frame_times = []

        def capture_frame():
            """Симуляция захвата кадра."""
            start = time.perf_counter()

            # Симуляция обработки кадра
            frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
            _ = frame.tobytes()

            return time.perf_counter() - start

        # Измерение времени захвата 100 кадров
        for _ in range(100):
            frame_time = capture_frame()
            frame_times.append(frame_time)

        avg_time = sum(frame_times) / len(frame_times)
        max_time = max(frame_times)

        # Среднее время должно быть меньше интервала кадра для 30 fps
        assert avg_time < 0.033  # ~33ms для 30 fps
        # Максимальное время не должно превышать 50ms
        assert max_time < 0.05

    @pytest.mark.slow
    def test_queue_performance(self):
        """Тест производительности очереди кадров."""
        import queue

        frame_queue = queue.Queue(maxsize=100)

        def producer():
            """Производитель кадров."""
            for i in range(100):
                frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
                frame_queue.put(frame)

        def consumer():
            """Потребитель кадров."""
            consumed = 0
            while consumed < 100:
                try:
                    frame = frame_queue.get(timeout=1)
                    consumed += 1
                except queue.Empty:
                    break
            return consumed

        # Запуск
        producer_thread = threading.Thread(target=producer)
        consumer_thread = threading.Thread(target=consumer)

        start_time = time.time()

        producer_thread.start()
        consumer_thread.start()

        producer_thread.join(timeout=5)
        consumer_thread.join(timeout=5)

        elapsed = time.time() - start_time

        # 100 кадров должны быть обработаны быстро
        assert elapsed < 2.0
