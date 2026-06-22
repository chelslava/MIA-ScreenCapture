"""
Тесты `_WindowsCaptureSession` (#62).

`windows-capture` — Windows-only зависимость (`pyproject.toml`,
`sys_platform == 'win32'`), поэтому во всех тестах модуль полностью
подменяется через `sys.modules` — тесты не требуют реальной библиотеки и
работают на любой платформе (skip на non-Windows не нужен).
"""

from collections.abc import Callable
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from recorder.video_recorder import CaptureArea, _WindowsCaptureSession


def _make_mock_windows_capture_module(
    start_free_threaded: Callable[[], object] | None = None,
) -> tuple[MagicMock, dict[str, Callable]]:
    """
    Создаёт мок модуля `windows_capture`.

    Перехватывает функции, зарегистрированные через `@capture.event`,
    в словарь `handlers` по имени — тест может вызвать их напрямую,
    эмулируя событие из реальной библиотеки.
    """
    handlers: dict[str, Callable] = {}

    def event_decorator(func: Callable) -> Callable:
        handlers[func.__name__] = func
        return func

    mock_capture_instance = MagicMock()
    mock_capture_instance.event = event_decorator
    if start_free_threaded is not None:
        mock_capture_instance.start_free_threaded.side_effect = (
            start_free_threaded
        )
    else:
        mock_capture_instance.start_free_threaded.return_value = MagicMock()

    mock_module = MagicMock()
    mock_module.WindowsCapture.return_value = mock_capture_instance
    mock_module.InternalCaptureControl = MagicMock
    return mock_module, handlers


def _fake_frame(buffer: np.ndarray) -> MagicMock:
    """Создаёт мок объекта frame с заданным `frame_buffer`."""
    frame = MagicMock()
    frame.frame_buffer = buffer
    return frame


class TestWindowsCaptureSessionInit:
    """Тесты инициализации сессии (`start()`)."""

    def test_start_succeeds_when_frame_arrives(self) -> None:
        """Успешная инициализация: первый кадр снимает таймаут ожидания."""
        bgr_frame = _fake_frame(np.zeros((64, 64, 3), dtype=np.uint8))

        def fake_start_free_threaded() -> MagicMock:
            handlers["on_frame_arrived"](bgr_frame, MagicMock())
            return MagicMock()

        mock_module, handlers = _make_mock_windows_capture_module(
            fake_start_free_threaded
        )

        session = _WindowsCaptureSession()
        with patch.dict("sys.modules", {"windows_capture": mock_module}):
            session.start(CaptureArea(type="full", width=64, height=64))

        assert session._control is not None
        frame = session.read_frame(timeout=1.0)
        assert frame is not None
        assert frame.shape == (64, 64, 3)

    def test_start_raises_runtime_error_on_init_exception(self) -> None:
        """Ошибка во время `start_free_threaded` оборачивается в RuntimeError."""

        def failing_start_free_threaded() -> None:
            raise PermissionError("access denied")

        mock_module, _ = _make_mock_windows_capture_module(
            failing_start_free_threaded
        )

        session = _WindowsCaptureSession()
        with (
            patch.dict("sys.modules", {"windows_capture": mock_module}),
            pytest.raises(RuntimeError, match="access denied"),
        ):
            session.start(CaptureArea(type="full", width=64, height=64))

    def test_start_raises_timeout_error_when_capture_unavailable(
        self,
    ) -> None:
        """Захват недоступен (зависает) -> TimeoutError по истечении таймаута."""
        mock_module, _ = _make_mock_windows_capture_module(
            lambda: MagicMock()  # никогда не зовёт on_frame_arrived
        )

        session = _WindowsCaptureSession()
        session._INIT_TIMEOUT_SECONDS = 0.2
        with (
            patch.dict("sys.modules", {"windows_capture": mock_module}),
            pytest.raises(TimeoutError),
        ):
            session.start(CaptureArea(type="full", width=64, height=64))

        assert session._closed is True

    def test_start_raises_runtime_error_when_library_not_installed(
        self,
    ) -> None:
        """Невалидный/отсутствующий windows-capture даёт понятную ошибку."""
        session = _WindowsCaptureSession()
        with (
            patch.dict("sys.modules", {"windows_capture": None}),
            pytest.raises(RuntimeError, match="windows-capture"),
        ):
            session.start(CaptureArea(type="full", width=64, height=64))

    def test_start_uses_window_name_for_window_capture(self) -> None:
        """Для типа 'window' в WindowsCapture передаётся window_name."""
        bgr_frame = _fake_frame(np.zeros((32, 32, 3), dtype=np.uint8))

        def fake_start_free_threaded() -> MagicMock:
            handlers["on_frame_arrived"](bgr_frame, MagicMock())
            return MagicMock()

        mock_module, handlers = _make_mock_windows_capture_module(
            fake_start_free_threaded
        )

        session = _WindowsCaptureSession()
        with patch.dict("sys.modules", {"windows_capture": mock_module}):
            session.start(
                CaptureArea(
                    type="window",
                    width=32,
                    height=32,
                    window_title="Notepad",
                )
            )

        _, kwargs = mock_module.WindowsCapture.call_args
        assert kwargs["window_name"] == "Notepad"
        assert kwargs["monitor_index"] is None

    def test_start_uses_1_based_monitor_index_for_full_capture(self) -> None:
        """Для типа 'full' monitor_index конвертируется из 0-based в 1-based."""
        bgr_frame = _fake_frame(np.zeros((32, 32, 3), dtype=np.uint8))

        def fake_start_free_threaded() -> MagicMock:
            handlers["on_frame_arrived"](bgr_frame, MagicMock())
            return MagicMock()

        mock_module, handlers = _make_mock_windows_capture_module(
            fake_start_free_threaded
        )

        session = _WindowsCaptureSession()
        with patch.dict("sys.modules", {"windows_capture": mock_module}):
            session.start(
                CaptureArea(type="full", width=32, height=32, monitor_index=1)
            )

        _, kwargs = mock_module.WindowsCapture.call_args
        assert kwargs["monitor_index"] == 2
        assert kwargs["window_name"] is None


class TestWindowsCaptureSessionFrameHandling:
    """Тесты обработки кадров (`on_frame_arrived`, `read_frame`)."""

    def _start_session(
        self, capture_area: CaptureArea
    ) -> tuple[_WindowsCaptureSession, dict[str, Callable]]:
        """
        Запускает сессию через служебный init-кадр (1x1), затем сбрасывает
        `_last_frame`/`_frame_event` — тест получает "чистую" запущенную
        сессию и сам решает, какой кадр прислать через `handlers`.
        """
        init_frame = _fake_frame(np.zeros((1, 1, 3), dtype=np.uint8))

        def fake_start_free_threaded() -> MagicMock:
            handlers["on_frame_arrived"](init_frame, MagicMock())
            return MagicMock()

        mock_module, handlers = _make_mock_windows_capture_module(
            fake_start_free_threaded
        )
        session = _WindowsCaptureSession()
        with patch.dict("sys.modules", {"windows_capture": mock_module}):
            session.start(capture_area)

        session._last_frame = None
        session._frame_event.clear()
        return session, handlers

    def test_on_frame_arrived_converts_bgra_to_bgr(self) -> None:
        """BGRA-кадр (4 канала) должен конвертироваться в BGR (3 канала)."""
        session, handlers = self._start_session(
            CaptureArea(type="full", width=16, height=16)
        )

        bgra = np.zeros((16, 16, 4), dtype=np.uint8)
        handlers["on_frame_arrived"](_fake_frame(bgra), MagicMock())

        frame = session.read_frame(timeout=1.0)
        assert frame is not None
        assert frame.shape == (16, 16, 3)

    def test_on_frame_arrived_crops_to_rect_area(self) -> None:
        """Для типа 'rect' кадр должен обрезаться до заданной области."""
        session, handlers = self._start_session(
            CaptureArea(type="rect", x=10, y=5, width=20, height=15)
        )

        full_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        handlers["on_frame_arrived"](_fake_frame(full_frame), MagicMock())

        frame = session.read_frame(timeout=1.0)
        assert frame is not None
        assert frame.shape == (15, 20, 3)

    def test_on_frame_arrived_ignored_after_close(self) -> None:
        """После stop() новые кадры не должны обновлять последний кадр."""
        session, handlers = self._start_session(
            CaptureArea(type="full", width=16, height=16)
        )
        session.stop()

        capture_control = MagicMock()
        handlers["on_frame_arrived"](
            _fake_frame(np.ones((16, 16, 3), dtype=np.uint8)), capture_control
        )

        capture_control.stop.assert_called_once()

    def test_on_frame_arrived_ignores_none_frame_buffer(self) -> None:
        """Кадр без frame_buffer (None) не должен ничего записывать."""
        session, handlers = self._start_session(
            CaptureArea(type="full", width=16, height=16)
        )

        handlers["on_frame_arrived"](_fake_frame(None), MagicMock())

        assert session.read_frame(timeout=0.05) is None

    def test_read_frame_returns_none_on_timeout(self) -> None:
        """Без новых кадров read_frame должен вернуть None по таймауту."""
        session, _handlers = self._start_session(
            CaptureArea(type="full", width=16, height=16)
        )

        assert session.read_frame(timeout=0.05) is None

    def test_read_frame_returns_none_when_capture_lost(self) -> None:
        """При потере захвата read_frame должен немедленно вернуть None."""
        session, _handlers = self._start_session(
            CaptureArea(type="full", width=16, height=16)
        )
        session._capture_lost = True

        assert session.read_frame(timeout=1.0) is None

    def test_read_frame_clears_event_after_read(self) -> None:
        """Повторный read_frame без нового кадра не должен отдавать старый."""
        session, handlers = self._start_session(
            CaptureArea(type="full", width=16, height=16)
        )
        handlers["on_frame_arrived"](
            _fake_frame(np.zeros((16, 16, 3), dtype=np.uint8)), MagicMock()
        )

        first = session.read_frame(timeout=1.0)
        second = session.read_frame(timeout=0.05)

        assert first is not None
        assert second is None


class TestWindowsCaptureSessionCaptureLost:
    """Тесты обработки потери захвата (`on_closed`)."""

    def _start_session(
        self, on_closed_callback: Callable[[str], None] | None = None
    ) -> tuple[_WindowsCaptureSession, dict[str, Callable]]:
        """Запускает сессию через служебный init-кадр (см. аналог выше)."""
        init_frame = _fake_frame(np.zeros((1, 1, 3), dtype=np.uint8))

        def fake_start_free_threaded() -> MagicMock:
            handlers["on_frame_arrived"](init_frame, MagicMock())
            return MagicMock()

        mock_module, handlers = _make_mock_windows_capture_module(
            fake_start_free_threaded
        )
        session = _WindowsCaptureSession(on_closed_callback=on_closed_callback)
        with patch.dict("sys.modules", {"windows_capture": mock_module}):
            session.start(CaptureArea(type="full", width=16, height=16))

        session._last_frame = None
        session._frame_event.clear()
        return session, handlers

    def test_on_closed_marks_capture_lost(self) -> None:
        """Закрытие сессии (окно закрыто/процесс завершён) помечает потерю."""
        session, handlers = self._start_session()

        handlers["on_closed"]()

        assert session.is_capture_lost is True
        assert session._closed is True

    def test_on_closed_notifies_callback_with_message(self) -> None:
        """on_closed должен вызвать callback с понятным сообщением."""
        callback = MagicMock()
        session, handlers = self._start_session(on_closed_callback=callback)

        handlers["on_closed"]()

        callback.assert_called_once()
        assert "Захват потерян" in callback.call_args.args[0]

    def test_on_closed_callback_exception_does_not_propagate(self) -> None:
        """Ошибка в callback не должна прерывать обработку on_closed."""
        callback = MagicMock(side_effect=RuntimeError("listener crashed"))
        session, handlers = self._start_session(on_closed_callback=callback)

        handlers["on_closed"]()  # не должно поднять исключение

        assert session.is_capture_lost is True

    def test_read_frame_after_process_terminated_returns_none(self) -> None:
        """После 'завершения процесса' (on_closed) кадры не возвращаются."""
        session, handlers = self._start_session()
        handlers["on_closed"]()

        assert session.read_frame(timeout=1.0) is None


class TestWindowsCaptureSessionStop:
    """Тесты остановки сессии (`stop()`)."""

    def test_stop_calls_control_stop_and_wait(self) -> None:
        """stop() должен вызвать stop()/wait() у control и сбросить ссылки."""
        session = _WindowsCaptureSession()
        control = MagicMock()
        session._control = control
        session._capture = MagicMock()

        session.stop()

        control.stop.assert_called_once()
        control.wait.assert_called_once()
        assert session._control is None
        assert session._capture is None
        assert session._closed is True

    def test_stop_is_safe_without_active_control(self) -> None:
        """stop() без активной сессии не должен падать."""
        session = _WindowsCaptureSession()

        session.stop()

        assert session._closed is True

    def test_stop_logs_warning_on_native_error(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Ошибка остановки нативного control должна логироваться, не падать."""
        session = _WindowsCaptureSession()
        control = MagicMock()
        control.stop.side_effect = RuntimeError("native stop failed")
        session._control = control

        with caplog.at_level("WARNING"):
            session.stop()

        assert "Не удалось корректно остановить capture session" in (
            caplog.text
        )
