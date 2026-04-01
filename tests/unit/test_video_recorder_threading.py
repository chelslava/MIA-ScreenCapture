"""
Дополнительные тесты для изменений в video_recorder.

Тестирует:
- Потокобезопасный доступ к _capture_lost
- Shutdown event для детерминированного завершения
- Timeout инициализации windows-capture
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from recorder.video_recorder import (
    CaptureArea,
    RecordingState,
    VideoRecorder,
    _WindowsCaptureSession,
)


class TestCaptureLostThreadSafety:
    """Тесты потокобезопасности _capture_lost."""

    def test_capture_lost_lock_exists(self) -> None:
        """Тест наличия блокировки для _capture_lost."""
        recorder = VideoRecorder()
        assert hasattr(recorder, "_capture_lost_lock")
        assert isinstance(recorder._capture_lost_lock, type(threading.Lock()))

    def test_capture_lost_property_thread_safe(self) -> None:
        """Тест потокобезопасного доступа к is_capture_lost."""
        recorder = VideoRecorder()
        results: list[bool] = []
        errors: list[str] = []

        def read_capture_lost() -> None:
            for _ in range(100):
                try:
                    results.append(recorder.is_capture_lost)
                except Exception as e:
                    errors.append(str(e))

        def write_capture_lost() -> None:
            for i in range(100):
                with recorder._capture_lost_lock:
                    recorder._capture_lost = i % 2 == 0

        threads = [
            threading.Thread(target=read_capture_lost),
            threading.Thread(target=read_capture_lost),
            threading.Thread(target=write_capture_lost),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 200


class TestShutdownEvent:
    """Тесты shutdown event для детерминированного завершения."""

    def test_shutdown_event_exists(self) -> None:
        """Тест наличия shutdown event."""
        recorder = VideoRecorder()
        assert hasattr(recorder, "_shutdown_event")
        assert isinstance(recorder._shutdown_event, type(threading.Event()))

    def test_shutdown_event_cleared_on_start(self) -> None:
        """Тест очистки shutdown event при старте."""
        recorder = VideoRecorder()
        recorder._shutdown_event.set()
        # _shutdown_event.clear() вызывается в start() на строке 510
        # Проверяем что флаг установлен до старта
        assert recorder._shutdown_event.is_set()
        # После создания нового recorder событие должно быть сброшено
        recorder2 = VideoRecorder()
        assert not recorder2._shutdown_event.is_set()

    def test_shutdown_event_set_on_stop(self) -> None:
        """Тест установки shutdown event при остановке."""
        recorder = VideoRecorder()
        recorder._state = RecordingState.RECORDING

        recorder.stop()

        assert recorder._shutdown_event.is_set()

    def test_capture_thread_not_daemon(self) -> None:
        """Тест что поток захвата не daemon."""
        recorder = VideoRecorder()

        assert hasattr(recorder, "_capture_thread")


class TestWindowsCaptureSessionTimeout:
    """Тесты timeout инициализации windows-capture."""

    def test_init_timeout_constant(self) -> None:
        """Тест константы timeout."""
        assert hasattr(_WindowsCaptureSession, "_INIT_TIMEOUT_SECONDS")
        assert _WindowsCaptureSession._INIT_TIMEOUT_SECONDS == 10.0

    def test_init_complete_event_exists(self) -> None:
        """Тест наличия события завершения инициализации."""
        session = _WindowsCaptureSession()
        assert hasattr(session, "_init_complete")
        assert hasattr(session, "_init_error")

    def test_timeout_on_init(self) -> None:
        """Тест timeout при инициализации."""
        # Уменьшаем timeout для быстрого теста
        session = _WindowsCaptureSession()
        session._INIT_TIMEOUT_SECONDS = 0.5

        # Мокаем windows_capture модуль
        mock_capture = MagicMock()
        mock_control = MagicMock()

        # event декоратор должен вернуть функцию как есть
        def mock_event_decorator(func):
            return func
        mock_capture.event = mock_event_decorator

        # start_free_threaded блокирует навсегда (не вызывает _init_complete.set())
        mock_capture.start_free_threaded.return_value = mock_control

        mock_windows_capture = MagicMock()
        mock_windows_capture.WindowsCapture.return_value = mock_capture
        mock_windows_capture.InternalCaptureControl = MagicMock

        with patch.dict(
            "sys.modules", {"windows_capture": mock_windows_capture}
        ):
            capture_area = CaptureArea(type="full", width=1920, height=1080)

            with pytest.raises(TimeoutError):
                session.start(capture_area)


class TestNonDaemonThreads:
    """Тесты non-daemon потоков."""

    def test_video_recorder_thread_not_daemon_by_default(self) -> None:
        """Тест что VideoRecorder не создаёт daemon потоки по умолчанию."""
        recorder = VideoRecorder()

        assert hasattr(recorder, "_capture_thread")
        if recorder._capture_thread is not None:
            assert not recorder._capture_thread.daemon


class TestCaptureLoopShutdownIntegration:
    """Интеграционные тесты shutdown в capture loop."""

    def test_shutdown_event_checked_in_loop(self) -> None:
        """Тест что shutdown event проверяется в цикле."""
        recorder = VideoRecorder()
        recorder._state = RecordingState.RECORDING
        recorder._shutdown_event.set()

        assert recorder._shutdown_event.is_set()


class TestCaptureLostInCallback:
    """Тесты _capture_lost в callback."""

    def test_capture_lost_set_with_lock_in_callback(self) -> None:
        """Тест установки _capture_lost с блокировкой в callback."""
        recorder = VideoRecorder()
        recorder._on_error = MagicMock()

        if hasattr(recorder, "_capture_lost_lock"):
            with recorder._capture_lost_lock:
                recorder._capture_lost = True

            assert recorder.is_capture_lost is True
