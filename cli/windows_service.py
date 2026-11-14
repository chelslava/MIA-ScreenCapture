"""
Модуль Windows Service для MIA-ScreenCapture (Issue #122).
=========================================================

Позволяет запускать MIA-ScreenCapture как системную службу Windows
для автозапуска, работы в фоне без входа пользователя и удалённого API.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from typing import Any

from logger_config import get_module_logger

logger = get_module_logger(__name__)

SERVICE_NAME = "MIAScreenCapture"
SERVICE_DISPLAY_NAME = "MIA Screen Capture Service"
SERVICE_DESCRIPTION = "MIA Screen Capture REST API & Scheduler Service"

# Watchdog службы (#192): интервал контроля живости рабочего потока
WATCHDOG_POLL_SECONDS = 5
# Recovery-действия SCM (#192): перезапуск через 1мин, 1мин, 5мин;
# счётчик сбоев сбрасывается раз в сутки — попытки перезапуска ограничены
RECOVERY_RESET_SECONDS = 86400
RECOVERY_ACTIONS = "restart/60000/restart/60000/restart/300000"

try:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil

    HAS_PYWIN32 = True
except ImportError:
    HAS_PYWIN32 = False
    win32serviceutil = object


def build_recovery_command(service_name: str) -> list[str]:
    """Команда `sc.exe failure` для настройки авто-перезапуска службы.

    Returns:
        Аргументы для subprocess: перезапуск через 1мин/1мин/5мин,
        счётчик сбоев сбрасывается раз в сутки (RECOVERY_*).
    """
    return [
        "sc.exe",
        "failure",
        service_name,
        "reset=",
        str(RECOVERY_RESET_SECONDS),
        "actions=",
        RECOVERY_ACTIONS,
    ]


def configure_service_recovery(service_name: str) -> bool:
    """Настроить автоматический перезапуск службы после сбоя (#192).

    Watchdog-механика уровня SCM: при аварийном завершении процесса
    службы Windows перезапускает её с лимитом попыток (два рестарта
    через минуту, затем через пять, счётчик сбрасывается раз в сутки).

    Args:
        service_name: Имя установленной службы.

    Returns:
        True, если recovery-действия заданы.
    """
    if sys.platform != "win32":
        return False
    try:
        result = subprocess.run(
            build_recovery_command(service_name),
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as e:
        logger.error("Не удалось запустить sc.exe failure: %s", e)
        return False
    if result.returncode != 0:
        logger.error(
            "Recovery-действия не заданы: %s",
            (result.stderr or result.stdout).strip(),
        )
        return False
    logger.info("Recovery-действия службы заданы: %s", RECOVERY_ACTIONS)
    return True


def watchdog_should_fail(
    app_thread_alive: bool,
    app_exit_ok: bool,
    is_running: bool,
) -> bool:
    """Решение watchdog: умер ли рабочий поток без штатной остановки.

    Аварийное завершение рабочего потока при активной службе — это
    сбой процесса: SCM выполнит recovery-действия и перезапустит
    службу (см. `configure_service_recovery`).

    Args:
        app_thread_alive: Жив ли рабочий поток приложения.
        app_exit_ok: Завершился ли поток штатно (`run()` вернулся).
        is_running: Запрошена ли остановка службы.

    Returns:
        True — процесс службы должен завершиться аварийно (os._exit).
    """
    return not app_thread_alive and not app_exit_ok and is_running


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
            self._app_exit_ok = False

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
                # Watchdog (#192): пока служба не остановлена, контролируем
                # живость рабочего потока. Аварийная смерть потока — сбой
                # процесса: SCM выполнит recovery-действия и перезапустит.
                while self._is_running:
                    signaled = win32event.WaitForSingleObject(
                        self.hWaitStop, WATCHDOG_POLL_SECONDS * 1000
                    )
                    if signaled == win32event.WAIT_OBJECT_0:
                        break
                    if watchdog_should_fail(
                        (
                            self._app_thread is not None
                            and self._app_thread.is_alive()
                        ),
                        self._app_exit_ok,
                        self._is_running,
                    ):
                        logger.error(
                            "Рабочий поток приложения завершился аварийно — "
                            "служба падает для перезапуска через recovery"
                        )
                        # Осознанно без ReportServiceStatus(SERVICE_STOPPED):
                        # только аварийное завершение процесса считает
                        # сбоем и запускает recovery-действия SCM
                        os._exit(1)
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
                    # Штатный выход: watchdog не считает поток умершим
                    self._app_exit_ok = True
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
        # Watchdog-перезапуск (#192): неудача не отменяет установку
        configure_service_recovery(SERVICE_NAME)
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
