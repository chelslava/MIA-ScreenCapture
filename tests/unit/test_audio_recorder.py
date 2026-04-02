"""
Тесты модуля аудиозаписи
=======================

Тестирует классы AudioRecorder и SystemAudioRecorder.
"""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from recorder.audio_recorder import (
    AudioConfig,
    AudioRecorder,
    AudioState,
    SystemAudioRecorder,
)


class TestAudioConfig:
    """Тесты конфигурации аудио."""

    def test_default_values(self) -> None:
        """Проверка значений по умолчанию."""
        config = AudioConfig()
        assert config.sample_rate == 44100
        assert config.channels == 2
        assert config.chunk_size == 1024
        assert config.device_index is None

    def test_custom_values(self) -> None:
        """Проверка пользовательских значений."""
        config = AudioConfig(
            sample_rate=48000,
            channels=1,
            chunk_size=2048,
            device_index=1,
        )
        assert config.sample_rate == 48000
        assert config.channels == 1
        assert config.chunk_size == 2048
        assert config.device_index == 1


class TestAudioState:
    """Тесты перечисления состояний аудио."""

    def test_state_values(self) -> None:
        """Проверка значений состояний."""
        assert AudioState.IDLE.value == "idle"
        assert AudioState.RECORDING.value == "recording"
        assert AudioState.PAUSED.value == "paused"
        assert AudioState.STOPPING.value == "stopping"


class TestAudioRecorder:
    """Тесты класса AudioRecorder."""

    @pytest.fixture
    def recorder(self) -> AudioRecorder:
        """Создаёт рекордер для тестов."""
        return AudioRecorder()

    def test_init_default(self) -> None:
        """Проверка инициализации с параметрами по умолчанию."""
        recorder = AudioRecorder()
        assert recorder.config.sample_rate == 44100
        assert recorder.config.channels == 2
        assert recorder.config.chunk_size == 1024
        assert recorder.state == AudioState.IDLE

    def test_init_custom_params(self) -> None:
        """Проверка инициализации с пользовательскими параметрами."""
        recorder = AudioRecorder(
            sample_rate=48000,
            channels=1,
            chunk_size=2048,
        )
        assert recorder.config.sample_rate == 48000
        assert recorder.config.channels == 1
        assert recorder.config.chunk_size == 2048

    def test_state_property(self, recorder: AudioRecorder) -> None:
        """Проверка свойства state."""
        assert recorder.state == AudioState.IDLE

    def test_is_recording_false_initially(
        self, recorder: AudioRecorder
    ) -> None:
        """Проверка is_recording при инициализации."""
        assert recorder.is_recording is False

    def test_is_paused_false_initially(self, recorder: AudioRecorder) -> None:
        """Проверка is_paused при инициализации."""
        assert recorder.is_paused is False

    def test_elapsed_time_zero_initially(
        self, recorder: AudioRecorder
    ) -> None:
        """Проверка elapsed_time при инициализации."""
        assert recorder.elapsed_time == 0

    def test_output_path_none_initially(self, recorder: AudioRecorder) -> None:
        """Проверка output_path при инициализации."""
        assert recorder.output_path is None

    def test_set_callbacks(self, recorder: AudioRecorder) -> None:
        """Проверка установки callback'ов."""
        error_callback = MagicMock()
        recorder.set_callbacks(on_error=error_callback)
        # Callback установлен (проверяем косвенно через атрибут)
        assert recorder._on_error is error_callback

    def test_get_available_devices(self, recorder: AudioRecorder) -> None:
        """Проверка получения списка устройств."""
        with patch(
            "recorder.audio_recorder.get_audio_devices"
        ) as mock_get_devices:
            mock_get_devices.return_value = {
                "input": [{"name": "Mic 1"}, {"name": "Mic 2"}],
                "output": [{"name": "Speaker"}],
            }
            devices = AudioRecorder.get_available_devices()
            assert len(devices) == 2
            assert devices[0]["name"] == "Mic 1"

    def test_start_from_idle_state(
        self, recorder: AudioRecorder, tmp_path: Path
    ) -> None:
        """Проверка запуска записи из состояния IDLE."""
        output_path = tmp_path / "test_audio.wav"

        with patch.object(recorder, "_init_audio"):
            with (
                patch.object(recorder, "_record_loop"),
                patch.object(recorder, "_writer_loop"),
            ):
                result = recorder.start(output_path)

        assert result is True
        assert recorder.state == AudioState.RECORDING
        assert recorder.output_path == output_path

    def test_start_creates_output_directory(
        self, recorder: AudioRecorder, tmp_path: Path
    ) -> None:
        """Проверка создания директории вывода."""
        output_path = tmp_path / "subdir" / "test_audio.wav"

        with patch.object(recorder, "_init_audio"):
            with (
                patch.object(recorder, "_record_loop"),
                patch.object(recorder, "_writer_loop"),
            ):
                result = recorder.start(output_path)

        assert result is True
        assert output_path.parent.exists()

    def test_start_from_recording_state_returns_false(
        self, recorder: AudioRecorder, tmp_path: Path
    ) -> None:
        """Проверка что запуск из состояния RECORDING возвращает False."""
        recorder._state = AudioState.RECORDING
        output_path = tmp_path / "test_audio.wav"

        result = recorder.start(output_path)

        assert result is False

    def test_start_from_paused_state_returns_false(
        self, recorder: AudioRecorder, tmp_path: Path
    ) -> None:
        """Проверка что запуск из состояния PAUSED возвращает False."""
        recorder._state = AudioState.PAUSED
        output_path = tmp_path / "test_audio.wav"

        result = recorder.start(output_path)

        assert result is False

    def test_pause_from_recording_state(self, recorder: AudioRecorder) -> None:
        """Проверка паузы из состояния RECORDING."""
        recorder._state = AudioState.RECORDING
        recorder._start_time = time.time()

        result = recorder.pause()

        assert result is True
        assert recorder.state == AudioState.PAUSED
        assert recorder._paused_time > 0

    def test_pause_from_idle_returns_false(
        self, recorder: AudioRecorder
    ) -> None:
        """Проверка паузы из состояния IDLE."""
        result = recorder.pause()

        assert result is False
        assert recorder.state == AudioState.IDLE

    def test_pause_from_paused_returns_false(
        self, recorder: AudioRecorder
    ) -> None:
        """Проверка паузы из состояния PAUSED."""
        recorder._state = AudioState.PAUSED

        result = recorder.pause()

        assert result is False

    def test_resume_from_paused_state(self, recorder: AudioRecorder) -> None:
        """Проверка возобновления из состояния PAUSED."""
        recorder._state = AudioState.PAUSED
        recorder._paused_time = time.time() - 1.0  # Пауза длилась 1 секунду
        recorder._start_time = time.time() - 5.0
        recorder._total_paused = 0

        result = recorder.resume()

        assert result is True
        assert recorder.state == AudioState.RECORDING
        # _total_paused должен увеличиться на время паузы
        assert recorder._total_paused >= 1.0

    def test_resume_from_idle_returns_false(
        self, recorder: AudioRecorder
    ) -> None:
        """Проверка возобновления из состояния IDLE."""
        result = recorder.resume()

        assert result is False

    def test_resume_from_recording_returns_false(
        self, recorder: AudioRecorder
    ) -> None:
        """Проверка возобновления из состояния RECORDING."""
        recorder._state = AudioState.RECORDING

        result = recorder.resume()

        assert result is False

    def test_stop_from_recording_state(
        self, recorder: AudioRecorder, tmp_path: Path
    ) -> None:
        """Проверка остановки из состояния RECORDING."""
        recorder._state = AudioState.RECORDING
        recorder._output_path = tmp_path / "test.wav"
        recorder._record_thread = None

        with patch.object(recorder, "_cleanup"):
            result = recorder.stop()

        assert result is True
        assert recorder.state == AudioState.STOPPING

    def test_stop_from_paused_state(
        self, recorder: AudioRecorder, tmp_path: Path
    ) -> None:
        """Проверка остановки из состояния PAUSED."""
        recorder._state = AudioState.PAUSED
        recorder._output_path = tmp_path / "test.wav"
        recorder._record_thread = None

        with patch.object(recorder, "_cleanup"):
            result = recorder.stop()

        assert result is True

    def test_stop_from_idle_returns_false(
        self, recorder: AudioRecorder
    ) -> None:
        """Проверка остановки из состояния IDLE."""
        result = recorder.stop()

        assert result is False

    def test_elapsed_time_during_recording(
        self, recorder: AudioRecorder
    ) -> None:
        """Проверка расчёта времени во время записи."""
        recorder._state = AudioState.RECORDING
        recorder._start_time = time.time() - 5.0
        recorder._total_paused = 0

        elapsed = recorder.elapsed_time

        assert 4.9 < elapsed < 5.1

    def test_elapsed_time_during_pause(self, recorder: AudioRecorder) -> None:
        """Проверка расчёта времени во время паузы."""
        recorder._state = AudioState.PAUSED
        recorder._start_time = time.time() - 10.0
        recorder._paused_time = time.time() - 3.0
        recorder._total_paused = 0

        elapsed = recorder.elapsed_time

        # Время должно быть около 7 секунд (10 - 3 паузы)
        assert 6.9 < elapsed < 7.1

    def test_elapsed_time_with_total_paused(
        self, recorder: AudioRecorder
    ) -> None:
        """Проверка расчёта времени с учётом total_paused."""
        recorder._state = AudioState.RECORDING
        recorder._start_time = time.time() - 10.0
        recorder._total_paused = 3.0

        elapsed = recorder.elapsed_time

        # Время должно быть около 7 секунд (10 - 3 паузы)
        assert 6.9 < elapsed < 7.1

    def test_start_with_device_index(
        self, recorder: AudioRecorder, tmp_path: Path
    ) -> None:
        """Проверка запуска с указанием устройства."""
        output_path = tmp_path / "test_audio.wav"

        with patch.object(recorder, "_init_audio"):
            with (
                patch.object(recorder, "_record_loop"),
                patch.object(recorder, "_writer_loop"),
            ):
                result = recorder.start(output_path, device_index=2)

        assert result is True
        assert recorder.config.device_index == 2

    def test_start_with_duration(
        self, recorder: AudioRecorder, tmp_path: Path
    ) -> None:
        """Проверка запуска с ограничением длительности."""
        output_path = tmp_path / "test_audio.wav"

        with patch.object(recorder, "_init_audio"):
            with (
                patch.object(recorder, "_record_loop"),
                patch.object(recorder, "_writer_loop"),
            ):
                result = recorder.start(output_path, duration=10.0)

        assert result is True
        assert recorder._duration == 10.0

    def test_start_handles_exception(
        self, recorder: AudioRecorder, tmp_path: Path
    ) -> None:
        """Проверка обработки исключения при запуске."""
        output_path = tmp_path / "test_audio.wav"
        error_callback = MagicMock()
        recorder.set_callbacks(on_error=error_callback)

        with patch.object(
            recorder, "_init_audio", side_effect=Exception("Audio error")
        ):
            result = recorder.start(output_path)

        assert result is False
        error_callback.assert_called_once_with("Audio error")

    def test_cleanup_resets_state(self, recorder: AudioRecorder) -> None:
        """Проверка что cleanup сбрасывает состояние."""
        recorder._state = AudioState.RECORDING
        recorder._start_time = time.time()

        recorder._cleanup()

        assert recorder.state == AudioState.IDLE


class TestAudioRecorderIntegration:
    """Интеграционные тесты AudioRecorder."""

    def test_full_lifecycle_mocked(self, tmp_path: Path) -> None:
        """Проверка полного жизненного цикла записи (с моками)."""
        recorder = AudioRecorder()
        output_path = tmp_path / "lifecycle.wav"

        # Мокаем все внешние зависимости
        with patch.object(recorder, "_init_audio"):
            with (
                patch.object(recorder, "_record_loop"),
                patch.object(recorder, "_writer_loop"),
            ):
                # Запуск
                assert recorder.start(output_path) is True
                assert recorder.is_recording is True

                # Пауза
                assert recorder.pause() is True
                assert recorder.is_paused is True

                # Возобновление
                assert recorder.resume() is True
                assert recorder.is_recording is True

                # Остановка
                recorder._record_thread = None
                with patch.object(recorder, "_cleanup"):
                    assert recorder.stop() is True


class TestAudioRecorderInitAudio:
    """Тесты инициализации аудио."""

    @pytest.fixture
    def recorder(self) -> AudioRecorder:
        """Создаёт рекордер для тестов."""
        return AudioRecorder()

    def test_init_audio_with_sounddevice(
        self, recorder: AudioRecorder
    ) -> None:
        """Проверка инициализации через sounddevice."""
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = {
            "name": "Test Microphone",
            "max_input_channels": 2,
        }

        with patch.dict("sys.modules", {"sounddevice": mock_sd}):
            recorder._init_audio()

        mock_sd.query_devices.assert_called_once()

    def test_init_audio_with_device_index(
        self, recorder: AudioRecorder
    ) -> None:
        """Проверка инициализации с указанным устройством."""
        recorder.config.device_index = 1
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = {
            "name": "Test Microphone",
            "max_input_channels": 2,
        }

        with patch.dict("sys.modules", {"sounddevice": mock_sd}):
            recorder._init_audio()

        mock_sd.query_devices.assert_called_once_with(1)

    def test_init_audio_adjusts_channels(
        self, recorder: AudioRecorder
    ) -> None:
        """Проверка корректировки каналов."""
        recorder.config.channels = 4  # Больше чем доступно
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = {
            "name": "Test Microphone",
            "max_input_channels": 2,
        }

        with patch.dict("sys.modules", {"sounddevice": mock_sd}):
            recorder._init_audio()

        assert recorder.config.channels == 2

    def test_init_audio_fallback_to_pyaudio(
        self, recorder: AudioRecorder
    ) -> None:
        """Проверка отката к PyAudio при отсутствии sounddevice."""
        mock_pyaudio = MagicMock()
        mock_audio = MagicMock()
        mock_stream = MagicMock()
        mock_pyaudio.PyAudio.return_value = mock_audio
        mock_audio.open.return_value = mock_stream

        with patch.dict(
            "sys.modules",
            {"sounddevice": None, "pyaudio": mock_pyaudio},
        ):
            recorder._init_audio()

        mock_audio.open.assert_called_once()


class TestAudioRecorderCleanup:
    """Тесты очистки ресурсов."""

    @pytest.fixture
    def recorder(self) -> AudioRecorder:
        """Создаёт рекордер для тестов."""
        return AudioRecorder()

    def test_cleanup_closes_wave_file(self, recorder: AudioRecorder) -> None:
        """Проверка закрытия WAV файла."""
        mock_wave = MagicMock()
        recorder._wave_file = mock_wave

        recorder._cleanup()

        mock_wave.close.assert_called_once()
        assert recorder._wave_file is None

    def test_cleanup_closes_pyaudio_stream(
        self, recorder: AudioRecorder
    ) -> None:
        """Проверка закрытия потока PyAudio."""
        mock_stream = MagicMock()
        mock_interface = MagicMock()
        recorder._audio_stream = mock_stream
        recorder._audio_interface = mock_interface

        recorder._cleanup()

        mock_stream.stop_stream.assert_called_once()
        mock_stream.close.assert_called_once()
        mock_interface.terminate.assert_called_once()
        assert recorder._audio_stream is None
        assert recorder._audio_interface is None

    def test_cleanup_handles_exception(self, recorder: AudioRecorder) -> None:
        """Проверка обработки исключения при очистке."""
        mock_wave = MagicMock()
        mock_wave.close.side_effect = Exception("Close error")
        recorder._wave_file = mock_wave

        # Не должно вызывать исключение
        recorder._cleanup()

        assert recorder.state == AudioState.IDLE


class TestAudioRecorderGetDevices:
    """Тесты получения списка устройств."""

    def test_get_available_devices_success(self) -> None:
        """Проверка получения списка устройств ввода."""
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = [
            {
                "name": "Microphone 1",
                "max_input_channels": 2,
                "max_output_channels": 0,
                "default_samplerate": 44100,
            },
            {
                "name": "Speakers",
                "max_input_channels": 0,
                "max_output_channels": 2,
                "default_samplerate": 44100,
            },
        ]

        with patch.dict("sys.modules", {"sounddevice": mock_sd}):
            devices = AudioRecorder.get_available_devices()

        # get_available_devices возвращает список устройств ввода
        assert isinstance(devices, list)
        assert len(devices) == 1  # Только Microphone 1 (устройство ввода)
        assert devices[0]["name"] == "Microphone 1"
        assert devices[0]["channels"] == 2
        assert devices[0]["sample_rate"] == 44100


class TestAudioRecorderBackendFallback:
    """Тесты выбора backend'ов аудиозаписи."""

    @pytest.fixture
    def recorder(self) -> AudioRecorder:
        """Создаёт рекордер для тестов."""
        return AudioRecorder()

    def test_init_audio_raises_when_backends_missing(
        self, recorder: AudioRecorder
    ) -> None:
        """Проверка ошибки при отсутствии sounddevice и pyaudio."""
        with patch.dict(
            "sys.modules",
            {"sounddevice": None, "pyaudio": None},
        ):
            with pytest.raises(
                RuntimeError, match="Ни sounddevice, ни pyaudio недоступны"
            ):
                recorder._init_audio()


class TestSystemAudioRecorderSelection:
    """Тесты выбора системного аудиоустройства."""

    def test_windows_system_audio_selects_loopback_device(self) -> None:
        """Проверка выбора loopback-устройства на Windows."""
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = [
            {
                "name": "Speakers",
                "max_input_channels": 0,
                "max_output_channels": 2,
                "default_samplerate": 44100,
            },
            {
                "name": "Stereo Mix",
                "max_input_channels": 2,
                "max_output_channels": 0,
                "default_samplerate": 44100,
            },
        ]

        with (
            patch(
                "recorder.audio_recorder.get_platform", return_value="windows"
            ),
            patch.dict("sys.modules", {"sounddevice": mock_sd}),
        ):
            recorder = SystemAudioRecorder()
            recorder._init_audio()

        assert recorder.config.device_index == 1

    def test_windows_system_audio_falls_back_to_default_input(self) -> None:
        """Проверка fallback на обычный вход, если loopback не найден."""
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = [
            {
                "name": "Speakers",
                "max_input_channels": 0,
                "max_output_channels": 2,
                "default_samplerate": 44100,
            }
        ]

        with (
            patch(
                "recorder.audio_recorder.get_platform", return_value="windows"
            ),
            patch.dict("sys.modules", {"sounddevice": mock_sd}),
        ):
            recorder = SystemAudioRecorder()
            with patch.object(AudioRecorder, "_init_audio") as mock_base_init:
                recorder._init_audio()

        mock_base_init.assert_called_once()
        assert recorder.config.device_index is None

    def test_linux_system_audio_selects_monitor_device(self) -> None:
        """Проверка выбора monitor-устройства на Linux."""
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = [
            {
                "name": "Output",
                "max_input_channels": 0,
                "max_output_channels": 2,
                "default_samplerate": 44100,
            },
            {
                "name": "PulseAudio Monitor",
                "max_input_channels": 2,
                "max_output_channels": 0,
                "default_samplerate": 44100,
            },
        ]

        with (
            patch(
                "recorder.audio_recorder.get_platform", return_value="linux"
            ),
            patch.dict("sys.modules", {"sounddevice": mock_sd}),
        ):
            recorder = SystemAudioRecorder()
            recorder._init_audio()

        assert recorder.config.device_index == 1

    def test_macos_system_audio_requires_virtual_device(self) -> None:
        """Проверка ошибки при отсутствии виртуального устройства на macOS."""
        mock_sd = MagicMock()
        mock_sd.query_devices.return_value = [
            {
                "name": "Built-in Output",
                "max_input_channels": 0,
                "max_output_channels": 2,
                "default_samplerate": 44100,
            }
        ]

        with (
            patch(
                "recorder.audio_recorder.get_platform", return_value="darwin"
            ),
            patch.dict("sys.modules", {"sounddevice": mock_sd}),
        ):
            recorder = SystemAudioRecorder()
            with pytest.raises(
                RuntimeError, match="Виртуальное аудиоустройство"
            ):
                recorder._init_audio()
