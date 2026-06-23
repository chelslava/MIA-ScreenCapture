"""Тесты concrete application facade."""

from unittest.mock import MagicMock

from core.application_service import ApplicationService


def test_application_service_delegates_recording_and_api_calls() -> None:
    """Сервис должен делегировать команды backend-фасаду."""
    backend = MagicMock()
    backend.request_start_recording.return_value = {"success": True}
    backend.start_recording.return_value = {"success": True, "mode": "api"}
    backend.get_api_status.return_value = {"running": True}
    backend.stop_api_server.return_value = {"success": True}

    service = ApplicationService(backend)

    assert service.request_start_recording() == {"success": True}
    assert service.start_recording({"area": "full"}) == {
        "success": True,
        "mode": "api",
    }
    assert service.get_api_status() == {"running": True}
    assert service.stop_api_server() == {"success": True}

    backend.request_start_recording.assert_called_once_with()
    backend.start_recording.assert_called_once_with({"area": "full"})
    backend.get_api_status.assert_called_once_with()
    backend.stop_api_server.assert_called_once_with()
