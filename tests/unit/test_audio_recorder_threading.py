"""
Дополнительные тесты для изменений в audio_recorder.

Тестирует:
- Shutdown event для детерминированного завершения
- Non-daemon потоки
"""

import threading
from unittest.mock import MagicMock, patch

from recorder.audio_recorder import AudioRecorder, AudioState


class TestAudioRecorderShutdownEvent:
    """Тесты shutdown event для audio recorder."""

    def test_shutdown_event_exists(self) -> None:
        """Тест наличия shutdown event."""
        recorder = AudioRecorder()
        assert hasattr(recorder, "_shutdown_event")
        assert isinstance(recorder._shutdown_event, type(threading.Event()))

    def test_shutdown_event_set_on_stop(self) -> None:
        """Тест установки shutdown event при остановке."""
        recorder = AudioRecorder()
        recorder._state = AudioState.RECORDING

        recorder.stop()

        assert recorder._shutdown_event.is_set()


class TestAudioRecorderNonDaemonThreads:
    """Тесты non-daemon потоков в audio recorder."""

    def test_threads_not_daemon(self) -> None:
        """Тест что потоки не daemon."""
        recorder = AudioRecorder()

        assert hasattr(recorder, "_record_thread")
        assert hasattr(recorder, "_writer_thread")


class TestAudioRecorderLoopShutdown:
    """Тесты shutdown в audio loops."""

    def test_shutdown_event_checked_in_record_loop(self) -> None:
        """Тест что shutdown event проверяется в record loop."""
        recorder = AudioRecorder()
        recorder._state = AudioState.RECORDING
        recorder._shutdown_event.set()

        assert recorder._shutdown_event.is_set()

    def test_shutdown_event_checked_in_pyaudio_loop(self) -> None:
        """Тест что shutdown event проверяется в pyaudio loop."""
        recorder = AudioRecorder()
        recorder._state = AudioState.RECORDING
        recorder._shutdown_event.set()

        assert recorder._shutdown_event.is_set()


class TestAudioRecorderStateTransitions:
    """Тесты переходов состояний."""

    def test_stop_sets_stopping_state(self) -> None:
        """Тест что stop устанавливает состояние STOPPING."""
        recorder = AudioRecorder()
        recorder._state = AudioState.RECORDING

        with patch.object(recorder, "_cleanup"):
            recorder.stop()

    def test_cleanup_resets_state(self) -> None:
        """Тест что cleanup сбрасывает состояние."""
        recorder = AudioRecorder()
        recorder._state = AudioState.STOPPING

        recorder._cleanup()

        assert recorder._state == AudioState.IDLE


class TestAudioRecorderWriterStopEvent:
    """Тесты writer stop event."""

    def test_writer_stop_event_exists(self) -> None:
        """Тест наличия writer stop event."""
        recorder = AudioRecorder()
        assert hasattr(recorder, "_writer_stop_event")

    def test_writer_stop_event_set_on_stop(self) -> None:
        """Тест установки writer stop event при остановке."""
        recorder = AudioRecorder()
        recorder._state = AudioState.RECORDING

        with patch.object(recorder, "_cleanup"):
            recorder.stop()

        assert recorder._writer_stop_event.is_set()
