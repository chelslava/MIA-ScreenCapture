"""Unit-тесты для контракта ApplicationFacade."""

from typing import Protocol

from core.application_facade import ApplicationFacade


def test_application_facade_protocol_definition() -> None:
    """Проверка, что ApplicationFacade является валидным Protocol."""
    assert issubclass(ApplicationFacade, Protocol)
    assert hasattr(ApplicationFacade, "start_recording")
    assert hasattr(ApplicationFacade, "stop_recording")
    assert hasattr(ApplicationFacade, "get_status")
    assert hasattr(ApplicationFacade, "get_recording_metrics")
    assert hasattr(ApplicationFacade, "get_profiles")
