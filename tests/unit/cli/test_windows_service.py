"""
Unit-тесты для Windows Service модуля (cli/windows_service.py, Issue #122).
==========================================================================
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from cli.parser import create_parser, parse_args
from cli.windows_service import (
    SERVICE_NAME,
    MIAService,
    get_service_status,
    handle_service_command,
    install_service,
    restart_service,
    start_service,
    stop_service,
    uninstall_service,
)


def test_parser_service_arguments() -> None:
    """Проверка разбора CLI-аргументов для Windows Service."""
    parser = create_parser()
    args = parser.parse_args(
        ["--service", "install", "--service-startup", "manual"]
    )
    assert args.service == "install"
    assert args.service_startup == "manual"

    with patch("sys.argv", ["main.py", "--service", "status"]):
        cfg = parse_args()
        assert cfg["mode"] == "service"
        assert cfg["service_action"] == "status"


def test_install_service_success() -> None:
    """Тест успешной установки службы Windows."""
    with (
        patch("cli.windows_service.HAS_PYWIN32", True),
        patch(
            "cli.windows_service.win32serviceutil.InstallService"
        ) as mock_install,
    ):
        ok = install_service(startup="auto")
        assert ok is True
        mock_install.assert_called_once()


def test_start_service_success() -> None:
    """Тест успешного запуска службы Windows."""
    with (
        patch("cli.windows_service.HAS_PYWIN32", True),
        patch(
            "cli.windows_service.win32serviceutil.StartService"
        ) as mock_start,
    ):
        ok = start_service()
        assert ok is True
        mock_start.assert_called_once_with(SERVICE_NAME)


def test_stop_service_success() -> None:
    """Тест успешной остановки службы Windows."""
    with (
        patch("cli.windows_service.HAS_PYWIN32", True),
        patch("cli.windows_service.win32serviceutil.StopService") as mock_stop,
    ):
        ok = stop_service()
        assert ok is True
        mock_stop.assert_called_once_with(SERVICE_NAME)


def test_restart_service_success() -> None:
    """Тест перезапуска службы Windows."""
    with (
        patch("cli.windows_service.HAS_PYWIN32", True),
        patch(
            "cli.windows_service.win32serviceutil.RestartService"
        ) as mock_restart,
    ):
        ok = restart_service()
        assert ok is True
        mock_restart.assert_called_once_with(SERVICE_NAME)


def test_uninstall_service_success() -> None:
    """Тест удаления службы Windows."""
    with (
        patch("cli.windows_service.HAS_PYWIN32", True),
        patch(
            "cli.windows_service.win32serviceutil.RemoveService"
        ) as mock_remove,
    ):
        ok = uninstall_service()
        assert ok is True
        mock_remove.assert_called_once_with(SERVICE_NAME)


def test_get_service_status_query() -> None:
    """Тест запроса статуса службы."""
    with (
        patch("cli.windows_service.HAS_PYWIN32", True),
        patch(
            "cli.windows_service.win32serviceutil.QueryServiceStatus"
        ) as mock_query,
    ):
        # 4 = SERVICE_RUNNING
        mock_query.return_value = [0, 4, 0, 0, 0, 0, 0]
        status = get_service_status()
        assert status == "running"


def test_handle_service_command_dispatch() -> None:
    """Тест диспетчеризации команд через handle_service_command."""
    with patch("cli.windows_service.install_service", return_value=True):
        code = handle_service_command("install", startup="auto")
        assert code == 0

    with patch("cli.windows_service.start_service", return_value=False):
        code = handle_service_command("start")
        assert code == 1

    code_unknown = handle_service_command("unknown_action")
    assert code_unknown == 2


def test_mia_service_stop() -> None:
    """Тест обработки сигнала остановки службы SvcStop."""
    with (
        patch("cli.windows_service.HAS_PYWIN32", True),
        patch("cli.windows_service.win32event.CreateEvent", return_value=1234),
        patch("cli.windows_service.win32event.SetEvent") as mock_set_event,
        patch(
            "cli.windows_service.win32serviceutil.ServiceFramework.__init__",
            return_value=None,
        ),
    ):
        svc = MIAService([])
        svc.ReportServiceStatus = MagicMock()
        mock_app = MagicMock()
        svc._app_instance = mock_app

        svc.SvcStop()

        assert svc._is_running is False
        mock_app.shutdown.assert_called_once()
        mock_set_event.assert_called_once()
