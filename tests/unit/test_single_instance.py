"""Тесты `single_instance.py` — защита от множественного запуска."""

from unittest.mock import patch

import pytest
import winerror

from exceptions import AnotherInstanceRunningError
from single_instance import SingleInstanceGuard, bring_existing_window_to_front


class TestSingleInstanceGuard:
    """Проверки захвата/освобождения именованного мьютекса."""

    @patch("single_instance.win32api")
    @patch("single_instance.win32event")
    def test_acquire_succeeds_when_no_other_instance(
        self, mock_win32event, mock_win32api
    ) -> None:
        mock_win32event.CreateMutex.return_value = 123
        mock_win32api.GetLastError.return_value = 0

        guard = SingleInstanceGuard()

        assert guard.acquire() is True
        assert guard._handle == 123

    @patch("single_instance.win32api")
    @patch("single_instance.win32event")
    def test_acquire_fails_when_other_instance_running(
        self, mock_win32event, mock_win32api
    ) -> None:
        mock_win32event.CreateMutex.return_value = 456
        mock_win32api.GetLastError.return_value = winerror.ERROR_ALREADY_EXISTS

        guard = SingleInstanceGuard()

        assert guard.acquire() is False
        assert guard._handle is None
        mock_win32api.CloseHandle.assert_called_once_with(456)

    @patch("single_instance.win32api")
    @patch("single_instance.win32event")
    def test_release_closes_handle_and_resets_state(
        self, mock_win32event, mock_win32api
    ) -> None:
        mock_win32event.CreateMutex.return_value = 789
        mock_win32api.GetLastError.return_value = 0

        guard = SingleInstanceGuard()
        guard.acquire()
        guard.release()

        mock_win32event.ReleaseMutex.assert_called_once_with(789)
        mock_win32api.CloseHandle.assert_called_once_with(789)
        assert guard._handle is None

    @patch("single_instance.win32api")
    @patch("single_instance.win32event")
    def test_release_without_acquire_is_noop(
        self, mock_win32event, mock_win32api
    ) -> None:
        guard = SingleInstanceGuard()
        guard.release()

        mock_win32event.ReleaseMutex.assert_not_called()
        mock_win32api.CloseHandle.assert_not_called()

    @patch("single_instance.win32api")
    @patch("single_instance.win32event")
    def test_release_is_idempotent(
        self, mock_win32event, mock_win32api
    ) -> None:
        mock_win32event.CreateMutex.return_value = 111
        mock_win32api.GetLastError.return_value = 0

        guard = SingleInstanceGuard()
        guard.acquire()
        guard.release()
        guard.release()

        mock_win32event.ReleaseMutex.assert_called_once()
        mock_win32api.CloseHandle.assert_called_once()

    @patch("single_instance.win32api")
    @patch("single_instance.win32event")
    def test_context_manager_raises_when_already_running(
        self, mock_win32event, mock_win32api
    ) -> None:
        mock_win32event.CreateMutex.return_value = 222
        mock_win32api.GetLastError.return_value = winerror.ERROR_ALREADY_EXISTS

        with pytest.raises(AnotherInstanceRunningError):
            with SingleInstanceGuard():
                pass

    @patch("single_instance.win32api")
    @patch("single_instance.win32event")
    def test_context_manager_releases_on_exit(
        self, mock_win32event, mock_win32api
    ) -> None:
        mock_win32event.CreateMutex.return_value = 333
        mock_win32api.GetLastError.return_value = 0

        with SingleInstanceGuard():
            pass

        mock_win32event.ReleaseMutex.assert_called_once_with(333)


class TestBringExistingWindowToFront:
    """Проверки переключения фокуса на окно существующего экземпляра."""

    @patch("single_instance.win32gui")
    def test_returns_false_when_window_not_found(self, mock_win32gui) -> None:
        mock_win32gui.FindWindow.return_value = 0

        assert bring_existing_window_to_front("MIA-ScreenCapture") is False
        mock_win32gui.SetForegroundWindow.assert_not_called()

    @patch("single_instance.win32con")
    @patch("single_instance.win32gui")
    def test_restores_and_focuses_minimized_window(
        self, mock_win32gui, mock_win32con
    ) -> None:
        mock_win32gui.FindWindow.return_value = 42
        mock_win32gui.IsIconic.return_value = True
        mock_win32con.SW_RESTORE = 9

        assert bring_existing_window_to_front("MIA-ScreenCapture") is True
        mock_win32gui.ShowWindow.assert_called_once_with(42, 9)
        mock_win32gui.SetForegroundWindow.assert_called_once_with(42)

    @patch("single_instance.win32gui")
    def test_skips_restore_when_not_minimized(self, mock_win32gui) -> None:
        mock_win32gui.FindWindow.return_value = 42
        mock_win32gui.IsIconic.return_value = False

        assert bring_existing_window_to_front("MIA-ScreenCapture") is True
        mock_win32gui.ShowWindow.assert_not_called()
        mock_win32gui.SetForegroundWindow.assert_called_once_with(42)

    @patch("single_instance.win32api")
    @patch("single_instance.win32gui")
    def test_returns_false_when_foreground_lock_blocks(
        self, mock_win32gui, mock_win32api
    ) -> None:
        mock_win32gui.FindWindow.return_value = 42
        mock_win32gui.IsIconic.return_value = False
        mock_win32api.error = RuntimeError
        mock_win32gui.SetForegroundWindow.side_effect = RuntimeError(
            "foreground lock"
        )

        assert bring_existing_window_to_front("MIA-ScreenCapture") is False
