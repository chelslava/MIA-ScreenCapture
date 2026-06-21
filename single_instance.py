"""
Защита от одновременного запуска нескольких экземпляров приложения
====================================================================

Windows Graphics Capture API поддерживает только один активный сеанс
захвата на приложение. `SingleInstanceGuard` использует именованный
Windows-мьютекс, чтобы второй запущенный экземпляр мог обнаружить первый
и корректно завершиться вместо конфликта на уровне захвата экрана.

Мьютекс (а не Event) выбран намеренно: ОС автоматически освобождает его
даже при аварийном завершении процесса (краш), поэтому приложение не может
"залипнуть" в состоянии "уже запущен" после падения предыдущего экземпляра.
"""

import win32api
import win32con
import win32event
import win32gui
import winerror

from exceptions import AnotherInstanceRunningError
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class SingleInstanceGuard:
    """
    Гарантирует, что одновременно работает только один экземпляр приложения.

    Example:
        guard = SingleInstanceGuard()
        if not guard.acquire():
            print("Уже запущено")
        else:
            try:
                run_app()
            finally:
                guard.release()
    """

    MUTEX_NAME = "MIA-ScreenCapture-SingleInstance-Mutex"

    def __init__(self) -> None:
        self._handle: int | None = None

    def acquire(self) -> bool:
        """
        Пытается захватить именованный мьютекс.

        Returns:
            True, если экземпляр первый (мьютекс захвачен).
            False, если другой экземпляр уже держит мьютекс.
        """
        handle = win32event.CreateMutex(None, False, self.MUTEX_NAME)
        already_running = (
            win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS
        )

        if already_running:
            win32api.CloseHandle(handle)
            return False

        self._handle = handle
        return True

    def release(self) -> None:
        """Освобождает мьютекс. Безопасно вызывать повторно."""
        if self._handle is None:
            return
        try:
            win32event.ReleaseMutex(self._handle)
        except win32api.error as e:
            logger.debug(f"Мьютекс уже освобождён или не удерживался: {e}")
        finally:
            win32api.CloseHandle(self._handle)
            self._handle = None

    def __enter__(self) -> "SingleInstanceGuard":
        if not self.acquire():
            raise AnotherInstanceRunningError(
                "Другой экземпляр MIA-ScreenCapture уже запущен"
            )
        return self

    def __exit__(self, *_args: object) -> None:
        self.release()


def bring_existing_window_to_front(title: str = "MIA-ScreenCapture") -> bool:
    """
    Переключает фокус на окно уже запущенного экземпляра.

    Best-effort: Windows может заблокировать `SetForegroundWindow` из чужого
    процесса (foreground lock) — в этом случае просто возвращаем False,
    без исключения.

    Args:
        title: Заголовок главного окна (см. `gui/main_window.py`).

    Returns:
        True, если окно найдено и фокус успешно переключён.
    """
    hwnd = win32gui.FindWindow(None, title)
    if not hwnd:
        return False

    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        return True
    except win32api.error as e:
        logger.debug(f"Не удалось переключить фокус на окно: {e}")
        return False
