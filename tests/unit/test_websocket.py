"""
Unit тесты для api.websocket.
"""

from api.websocket import WebSocketManager
from core.event_bus import InMemoryEventBus, RecordingEvent, RecordingEventType


class TestWebSocketManager:
    def test_publish_and_read_recent_events(self) -> None:
        manager = WebSocketManager(max_events=3)
        manager.publish({"type": "started", "data": {"x": 1}})
        manager.publish({"type": "paused", "data": {"x": 2}})

        events = manager.get_recent_events(limit=10)
        assert len(events) == 2
        assert events[0]["type"] == "started"
        assert events[1]["type"] == "paused"

    def test_event_buffer_limit(self) -> None:
        manager = WebSocketManager(max_events=2)
        manager.publish({"type": "e1"})
        manager.publish({"type": "e2"})
        manager.publish({"type": "e3"})

        events = manager.get_recent_events(limit=10)
        assert len(events) == 2
        assert events[0]["type"] == "e2"
        assert events[1]["type"] == "e3"

    def test_attach_and_receive_from_event_bus(self) -> None:
        bus = InMemoryEventBus()
        manager = WebSocketManager()
        manager.attach_event_bus(bus)

        bus.publish(
            RecordingEvent(
                event_type=RecordingEventType.STARTED,
                payload={"output_path": "demo.mp4"},
            )
        )

        events = manager.get_recent_events(limit=1)
        assert len(events) == 1
        assert events[0]["type"] == "started"
        assert events[0]["data"]["output_path"] == "demo.mp4"

    def test_detach_event_bus(self) -> None:
        bus = InMemoryEventBus()
        manager = WebSocketManager()
        manager.attach_event_bus(bus)
        manager.detach_event_bus()

        bus.publish(
            RecordingEvent(
                event_type=RecordingEventType.ERROR,
                payload={"error": "boom"},
            )
        )

        events = manager.get_recent_events(limit=10)
        assert events == []
