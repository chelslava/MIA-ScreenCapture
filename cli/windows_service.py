"""
Модуль Windows Service для MIA-ScreenCapture (Issue #122).
=========================================================

Позволяет запускать MIA-ScreenCapture как системную службу Windows
для автозапуска, работы в фоне без входа пользователя и удалённого API.
"""

from __future__ import annotations

import sys
import threading
from typing import Any

from logger_config import get_module_logger

logger = get_module_logger(__name__)

SERVICE_NAME = "MIAScreenCapture"
SERVICE_DISPLAY_NAME = "MIA Screen Capture Service"
SERVICE_DESCRIPTION = "MIA Screen Capture REST API & Scheduler Service"

try:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil

    HAS_PYWIN32 = True
except ImportError:
    HAS_PYWIN32 = False
    win32serviceutil = object


if HAS_PYWIN32:

    class MIAService(win32serviceutil.ServiceFramework):
        """Системная служба Windows для headless-режима MIA-ScreenCapture."""

        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = SERVICE_DISPLAY_NAME
        _svc_description_ = SERVICE_DESCRIPTION

        def __init__(self, args: list[str]) -> None:
            super().__init__(args)
            self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
            self._is_running = True
            self._app_thread: threading.Thread | None = None
            self._app_instance: Any = None

        def SvcStop(self) -> None:
            """Остановка службы при запросе от Windows Service Control Manager."""
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            logger.info(
                "Получен сигнал остановки службы Windows %s", SERVICE_NAME
            )
            self._is_running = False
            if self._app_instance and hasattr(self._app_instance, "shutdown"):
                try:
                    self._app_instance.shutdown()
                except Exception as e:
                    logger.error("Ошибка при завершении приложения: %s", e)
            win32event.SetEvent(self.hWaitStop)

        def SvcDoRun(self) -> None:
            """Главный рабочий цикл службы."""
            try:
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    servicemanager.PYS_SERVICE_STARTED,
                    (self._svc_name_, ""),
                )
                logger.info(
                    "Служба %s запущена в headless-режиме", SERVICE_NAME
                )
                self._run_application()
                win32event.WaitForSingleObject(
                    self.hWaitStop, win32event.INFINITE
                )
                logger.info("Служба %s остановлена", SERVICE_NAME)
                servicemanager.LogMsg(
                    servicemanager.EVENTLOG_INFORMATION_TYPE,
                    servicemanager.PYS_SERVICE_STOPPED,
                    (self._svc_name_, ""),
                )
            except Exception as e:
                logger.exception(
                    "Критическая ошибка выполнения службы Windows: %s", e
                )
                self.SvcStop()

        def _run_application(self) -> None:
            """Запуск headless-приложения в отдельном потоке."""

            def _runner() -> None:
                try:
                    from main import VideoRecorderApp

                    self._app_instance = VideoRecorderApp({"mode": "headless"})
                    self._app_instance.run()
                except Exception as ex:
                    logger.exception(
                        "Ошибка в рабочем потоке приложения службы: %s", ex
                    )

            self._app_thread = threading.Thread(
                target=_runner, name="MIAServiceAppThread", daemon=True
            )
            self._app_thread.start()
else:

    class MIAService:  # type: ignore[no-redef]
        """Заглушка для сред без pywin32."""

        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = SERVICE_DISPLAY_NAME
        _svc_description_ = SERVICE_DESCRIPTION


def install_service(startup: str = "auto") -> bool:
    """Установка службы Windows."""
    if not HAS_PYWIN32:
        logger.error("pywin32 не установлен в системе")
        return False
    try:
        start_type = (
            win32service.SERVICE_AUTO_START
            if startup == "auto"
            else win32service.SERVICE_DEMAND_START
        )
        win32serviceutil.InstallService(
            None,
            SERVICE_NAME,
            SERVICE_DISPLAY_NAME,
            startType=start_type,
            description=SERVICE_DESCRIPTION,
            exeName=sys.executable,
        )
        logger.info(
            "Служба %s успешно установлена (старт: %s)", SERVICE_NAME, startup
        )
        return True
    except Exception as e:
        logger.error("Ошибка при установке службы: %s", e)
        return False


def start_service() -> bool:
    """Запуск службы Windows."""
    if not HAS_PYWIN32:
        logger.error("pywin32 не установлен в системе")
        return False
    try:
        win32serviceutil.StartService(SERVICE_NAME)
        logger.info("Служба %s успешно запущена", SERVICE_NAME)
        return True
    except Exception as e:
        logger.error("Ошибка при запуске службы: %s", e)
        return False


def stop_service() -> bool:
    """Остановка службы Windows."""
    if not HAS_PYWIN32:
        logger.error("pywin32 не установлен в системе")
        return False
    try:
        win32serviceutil.StopService(SERVICE_NAME)
        logger.info("Служба %s успешно остановлена", SERVICE_NAME)
        return True
    except Exception as e:
        logger.error("Ошибка при остановке службы: %s", e)
        return False


def restart_service() -> bool:
    """Перезапуск службы Windows."""
    if not HAS_PYWIN32:
        logger.error("pywin32 не установлен в системе")
        return False
    try:
        win32serviceutil.RestartService(SERVICE_NAME)
        logger.info("Служба %s успешно перезапущена", SERVICE_NAME)
        return True
    except Exception as e:
        logger.error("Ошибка при перезапуске службы: %s", e)
        return False


def uninstall_service() -> bool:
    """Удаление службы Windows."""
    if not HAS_PYWIN32:
        logger.error("pywin32 не установлен в системе")
        return False
    try:
        win32serviceutil.RemoveService(SERVICE_NAME)
        logger.info("Служба %s успешно удалена", SERVICE_NAME)
        return True
    except Exception as e:
        logger.error("Ошибка при удалении службы: %s", e)
        return False


def get_service_status() -> str:
    """Получение текущего статуса службы Windows."""
    if not HAS_PYWIN32:
        return "pywin32_not_installed"
    try:
        status = win32serviceutil.QueryServiceStatus(SERVICE_NAME)
        state = status[1]
        state_map = {
            win32service.SERVICE_STOPPED: "stopped",
            win32service.SERVICE_START_PENDING: "start_pending",
            win32service.SERVICE_STOP_PENDING: "stop_pending",
            win32service.SERVICE_RUNNING: "running",
            win32service.SERVICE_CONTINUE_PENDING: "continue_pending",
            win32service.SERVICE_PAUSE_PENDING: "pause_pending",
            win32service.SERVICE_PAUSED: "paused",
        }
        return state_map.get(state, f"unknown_{state}")
    except Exception as e:
        return f"not_installed ({e})"


def handle_service_command(action: str, startup: str = "auto") -> int:
    """Обработчик CLI-команд управления службой."""
    action = action.lower()
    if action == "install":
        ok = install_service(startup=startup)
        print(
            f"Установка службы '{SERVICE_NAME}': {'Успешно' if ok else 'Ошибка'}"
        )
        return 0 if ok else 1
    elif action == "start":
        ok = start_service()
        print(
            f"Запуск службы '{SERVICE_NAME}': {'Успешно' if ok else 'Ошибка'}"
        )
        return 0 if ok else 1
    elif action == "stop":
        ok = stop_service()
        print(
            f"Остановка службы '{SERVICE_NAME}': {'Успешно' if ok else 'Ошибка'}"
        )
        return 0 if ok else 1
    elif action == "restart":
        ok = restart_service()
        print(
            f"Перезапуск службы '{SERVICE_NAME}': {'Успешно' if ok else 'Ошибка'}"
        )
        return 0 if ok else 1
    elif action in ("uninstall", "remove"):
        ok = uninstall_service()
        print(
            f"Удаление службы '{SERVICE_NAME}': {'Успешно' if ok else 'Ошибка'}"
        )
        return 0 if ok else 1
    elif action == "status":
        st = get_service_status()
        print(f"Статус службы '{SERVICE_NAME}': {st}")
        return 0
    else:
        print(f"Неизвестное действие службы: {action}")
        return 2


if __name__ == "__main__":
    if len(sys.argv) > 1 and HAS_PYWIN32:
        win32serviceutil.HandleCommandLine(MIAService)
    elif HAS_PYWIN32:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(MIAService)
        servicemanager.StartServiceCtrlDispatcher()
