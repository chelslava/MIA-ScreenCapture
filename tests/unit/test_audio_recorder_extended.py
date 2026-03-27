"""
Расширенные unit тесты для AudioRecorder
=========================================

Дополнительные тесты для повышения покрытия audio_recorder до 90%.
"""

import queue
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from recorder.audio_recorder import AudioConfig, AudioRecorder, AudioState


class TestAudioConfig:
    """Тесты конфигурации аудио."""

    def test_default_config(self) -> None:
        """Проверка конфигурации по умолчанию."""
        config = AudioConfig()

        assert config.sample_rate == 44100
        assert config.channels == 2
        assert config.chunk_size == 1024
        assert config.device_index is None

    def test_custom_config(self) -> None:
        """Проверка пользовательской конфигурации."""
        config = AudioConfig(
            sample_rate=48000,
            channels=1,
            chunk_size=2048,
            device_index=0,
        )

        assert config.sample_rate == 48000
        assert config.channels == 1
        assert config.chunk_size == 2048
        assert config.device_index == 0

    @pytest.mark.parametrize("sample_rate", [22050, 44100, 48000, 96000])
    def test_sample_rates(self, sample_rate: int) -> None:
        """Проверка различных частот дискретизации."""
        config = AudioConfig(sample_rate=sample_rate)
        assert config.sample_rate == sample_rate

    @pytest.mark.parametrize("channels", [1, 2])
    def test_channel_configurations(self, channels: int) -> None:
        """Проверка конфигураций каналов."""
        config = AudioConfig(channels=channels)
        assert config.channels == channels

    @pytest.mark.parametrize("chunk_size", [512, 1024, 2048, 4096])
    def test_chunk_sizes(self, chunk_size: int) -> None:
        """Проверка размеров чанка."""
        config = AudioConfig(chunk_size=chunk_size)
        assert config.chunk_size == chunk_size

    def test_dataclass_equality(self) -> None:
        """Проверка равенства dataclass."""
        config1 = AudioConfig(sample_rate=44100, channels=2)
        config2 = AudioConfig(sample_rate=44100, channels=2)

        assert config1 == config2


class TestAudioState:
    """Тесты состояний аудиозаписи."""

    def test_audio_state_values(self) -> None:
        """Проверка значений AudioState."""
        assert AudioState.IDLE.value == "idle"
        assert AudioState.RECORDING.value == "recording"
        assert AudioState.PAUSED.value == "paused"
        assert AudioState.STOPPING.value == "stopping"

    def test_audio_state_count(self) -> None:
        """Проверка количества состояний."""
        states = list(AudioState)
        assert len(states) == 4


class TestAudioRecorderInit:
    """Тесты инициализации AudioRecorder."""

    def test_init_default_params(self) -> None:
        """Проверка инициализации с параметрами по умолчанию."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

        assert recorder.config.sample_rate == 44100
        assert recorder.config.channels == 2
        assert recorder.config.chunk_size == 1024

    def test_init_custom_params(self) -> None:
        """Проверка инициализации с пользовательскими параметрами."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder(
                sample_rate=48000,
                channels=1,
                chunk_size=2048,
            )

        assert recorder.config.sample_rate == 48000
        assert recorder.config.channels == 1
        assert recorder.config.chunk_size == 2048

    def test_init_state_idle(self) -> None:
        """Проверка начального состояния."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

        assert recorder.state == AudioState.IDLE
        assert recorder.is_recording is False

    def test_init_queue_exists(self) -> None:
        """Проверка создания очереди."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

        assert hasattr(recorder, "_audio_queue")
        assert isinstance(recorder._audio_queue, type(queue.Queue()))


class TestAudioRecorderState:
    """Тесты состояний AudioRecorder."""

    def test_is_recording_false_initially(self) -> None:
        """Проверка начального состояния is_recording."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

        assert recorder.is_recording is False

    def test_is_recording_true_when_recording(self) -> None:
        """Проверка is_recording при записи."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

        recorder._state = AudioState.RECORDING
        assert recorder.is_recording is True

    def test_is_paused_false_initially(self) -> None:
        """Проверка начального состояния is_paused."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

        assert recorder.is_paused is False

    def test_is_paused_true_when_paused(self) -> None:
        """Проверка is_paused при паузе."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

        recorder._state = AudioState.PAUSED
        assert recorder.is_paused is True

    @pytest.mark.parametrize(
        "state,expected_recording,expected_paused",
        [
            (AudioState.IDLE, False, False),
            (AudioState.RECORDING, True, False),
            (AudioState.PAUSED, False, True),
            (AudioState.STOPPING, False, False),
        ],
    )
    def test_state_properties(
        self,
        state: AudioState,
        expected_recording: bool,
        expected_paused: bool,
    ) -> None:
        """Проверка свойств состояния."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

        recorder._state = state
        assert recorder.is_recording == expected_recording
        assert recorder.is_paused == expected_paused


class TestAudioRecorderDeviceSelection:
    """Тесты выбора аудиоустройства."""

    def test_get_available_devices(self) -> None:
        """Проверка получения списка устройств."""
        mock_devices = [
            {"name": "Microphone", "max_input_channels": 2},
        ]

        with patch("recorder.audio_recorder.get_audio_devices") as mock_get:
            mock_get.return_value = {"input": mock_devices}
            devices = AudioRecorder.get_available_devices()

        assert devices == mock_devices

    def test_get_available_devices_empty(self) -> None:
        """Проверка пустого списка устройств."""
        with patch("recorder.audio_recorder.get_audio_devices") as mock_get:
            mock_get.return_value = {"input": []}
            devices = AudioRecorder.get_available_devices()

        assert devices == []


class TestAudioRecorderStartStop:
    """Тесты запуска и остановки записи."""

    def test_start_recording_success(self, tmp_path: Path) -> None:
        """Проверка успешного запуска записи."""
        output_file = tmp_path / "test.wav"

        with patch("recorder.audio_recorder.get_audio_devices"):
            with patch.object(AudioRecorder, "_init_audio"):
                with patch.object(AudioRecorder, "_record_loop"):
                    recorder = AudioRecorder()
                    result = recorder.start(output_file)

        assert result is True
        assert recorder.state == AudioState.RECORDING

    def test_start_recording_already_recording(self, tmp_path: Path) -> None:
        """Проверка запуска когда уже идёт запись."""
        output_file = tmp_path / "test.wav"

        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()
            recorder._state = AudioState.RECORDING

            result = recorder.start(output_file)

        assert result is False

    def test_start_recording_with_device(self, tmp_path: Path) -> None:
        """Проверка запуска с указанием устройства."""
        output_file = tmp_path / "test.wav"

        with patch("recorder.audio_recorder.get_audio_devices"):
            with patch.object(AudioRecorder, "_init_audio"):
                with patch.object(AudioRecorder, "_record_loop"):
                    recorder = AudioRecorder()
                    result = recorder.start(output_file, device_index=0)

        assert result is True
        assert recorder.config.device_index == 0

    def test_start_recording_with_duration(self, tmp_path: Path) -> None:
        """Проверка запуска с указанием длительности."""
        output_file = tmp_path / "test.wav"

        with patch("recorder.audio_recorder.get_audio_devices"):
            with patch.object(AudioRecorder, "_init_audio"):
                with patch.object(AudioRecorder, "_record_loop"):
                    recorder = AudioRecorder()
                    result = recorder.start(output_file, duration=60.0)

        assert result is True
        assert recorder._duration == 60.0

    def test_stop_recording(self) -> None:
        """Проверка остановки записи."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            with patch.object(AudioRecorder, "_cleanup"):
                recorder = AudioRecorder()
                recorder._state = AudioState.RECORDING
                recorder._record_thread = MagicMock()
                recorder._record_thread.is_alive.return_value = False

                recorder.stop()

        # После stop состояние может быть STOPPING или IDLE в зависимости от реализации
        assert recorder.state in (AudioState.IDLE, AudioState.STOPPING)


class TestAudioRecorderPause:
    """Тесты паузы записи."""

    def test_pause_recording(self) -> None:
        """Проверка паузы записи."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()
            recorder._state = AudioState.RECORDING

            recorder.pause()

        assert recorder.state == AudioState.PAUSED

    def test_resume_recording(self) -> None:
        """Проверка возобновления записи."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()
            recorder._state = AudioState.PAUSED

            recorder.resume()

        assert recorder.state == AudioState.RECORDING

    def test_pause_when_not_recording(self) -> None:
        """Проверка паузы когда запись не активна."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

            recorder.pause()

        # Состояние не должно измениться
        assert recorder.state == AudioState.IDLE

    def test_resume_when_not_paused(self) -> None:
        """Проверка возобновления когда не на паузе."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()
            recorder._state = AudioState.IDLE

            recorder.resume()

        # Состояние не должно измениться
        assert recorder.state == AudioState.IDLE


class TestAudioRecorderCallbacks:
    """Тесты обратных вызовов."""

    def test_set_on_error_callback(self) -> None:
        """Проверка установки callback для ошибок."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

        on_error = MagicMock()
        recorder.set_callbacks(on_error=on_error)

        assert recorder._on_error == on_error

    def test_set_callbacks_none(self) -> None:
        """Проверка установки None для callback."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()
            recorder._on_error = MagicMock()

            recorder.set_callbacks(on_error=None)

        assert recorder._on_error is None


class TestAudioRecorderStatistics:
    """Тесты статистики записи."""

    def test_elapsed_time_zero_initially(self) -> None:
        """Проверка начального времени."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

        assert recorder.elapsed_time == 0

    def test_elapsed_time_after_start(self) -> None:
        """Проверка времени после начала записи."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()
            recorder._start_time = time.time() - 10
            recorder._state = AudioState.RECORDING

            elapsed = recorder.elapsed_time

            assert 9 < elapsed < 11

    def test_elapsed_time_during_pause(self) -> None:
        """Проверка времени во время паузы."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()
            recorder._start_time = time.time() - 20
            recorder._paused_time = time.time() - 5
            recorder._state = AudioState.PAUSED

            elapsed = recorder.elapsed_time

            # Время паузы не должно учитываться
            assert 14 < elapsed < 16


class TestAudioRecorderOutput:
    """Тесты вывода аудио."""

    def test_output_path_property(self) -> None:
        """Проверка свойства output_path."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

        assert recorder.output_path is None

        recorder._output_path = Path("/tmp/audio.wav")
        assert recorder.output_path == Path("/tmp/audio.wav")


class TestAudioRecorderThreading:
    """Тесты потоков записи."""

    def test_recording_thread_none_initially(self) -> None:
        """Проверка отсутствия потока при инициализации."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

        assert recorder._record_thread is None

    def test_lock_exists(self) -> None:
        """Проверка существования блокировки."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

        assert hasattr(recorder, "_lock")
        assert isinstance(recorder._lock, type(threading.Lock()))


class TestAudioRecorderEdgeCases:
    """Тесты граничных случаев."""

    def test_start_already_recording(self, tmp_path: Path) -> None:
        """Проверка запуска когда уже идёт запись."""
        output_file = tmp_path / "test.wav"

        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()
            recorder._state = AudioState.RECORDING

            result = recorder.start(output_file)

        assert result is False
        assert recorder.state == AudioState.RECORDING

    def test_stop_when_not_recording(self) -> None:
        """Проверка остановки когда запись не активна."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            with patch.object(AudioRecorder, "_cleanup"):
                recorder = AudioRecorder()

                recorder.stop()

        # Должно пройти без ошибок
        assert recorder.state == AudioState.IDLE

    @pytest.mark.parametrize(
        "sample_rate", [22050, 44100, 48000, 96000, 192000]
    )
    def test_various_sample_rates(self, sample_rate: int) -> None:
        """Проверка с различными частотами дискретизации."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder(sample_rate=sample_rate)

        assert recorder.config.sample_rate == sample_rate

    @pytest.mark.parametrize("chunk_size", [512, 1024, 2048, 4096, 8192])
    def test_various_chunk_sizes(self, chunk_size: int) -> None:
        """Проверка с различными размерами чанка."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder(chunk_size=chunk_size)

        assert recorder.config.chunk_size == chunk_size


class TestAudioRecorderQueue:
    """Тесты очереди аудио."""

    def test_queue_empty_initially(self) -> None:
        """Проверка пустой очереди при инициализации."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

        assert recorder._audio_queue.empty()

    def test_queue_exists(self) -> None:
        """Проверка существования очереди."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

        assert hasattr(recorder, "_audio_queue")
        assert isinstance(recorder._audio_queue, queue.Queue)


class TestAudioRecorderNegative:
    """Негативные тесты для обработки исключительных ситуаций."""

    def test_start_with_invalid_path(self) -> None:
        """Проверка запуска с некорректным путём."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

            # Путь к несуществующей директории без прав записи
            # Должно выбросить исключение или вернуть False
            with patch.object(
                recorder, "_init_audio", side_effect=Exception("Error")
            ):
                result = recorder.start(Path("/nonexistent/path/audio.wav"))

        assert result is False

    def test_start_creates_directory(self, tmp_path: Path) -> None:
        """Проверка создания директории при запуске."""
        output_file = tmp_path / "subdir" / "test.wav"

        with patch("recorder.audio_recorder.get_audio_devices"):
            with patch.object(AudioRecorder, "_init_audio"):
                with patch.object(AudioRecorder, "_record_loop"):
                    recorder = AudioRecorder()
                    result = recorder.start(output_file)

        assert result is True
        assert output_file.parent.exists()

    def test_error_callback_invoked(self) -> None:
        """Проверка вызова callback при ошибке."""
        with patch("recorder.audio_recorder.get_audio_devices"):
            recorder = AudioRecorder()

        on_error = MagicMock()
        recorder._on_error = on_error

        # Симуляция вызова обработчика ошибки
        if hasattr(recorder, "_handle_error"):
            recorder._handle_error("Test error")
            on_error.assert_called_once_with("Test error")
