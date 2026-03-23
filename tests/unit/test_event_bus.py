"""
Unit тесты для core.event_bus.
"""

from core.event_bus import (
    InMemoryEventBus,
    RecordingEvent,
    RecordingEventType,
)


class TestInMemoryEventBus:
    def test_publish_to_subscriber(self) -> None:
        bus = InMemoryEventBus()
        received = []

        def handler(event: RecordingEvent) -> None:
            received.append(event)

        bus.subscribe(RecordingEventType.STARTED, handler)
        bus.publish(
            RecordingEvent(
                event_type=RecordingEventType.STARTED,
                payload={"output_path": "demo.mp4"},
            )
        )

        assert len(received) == 1
        assert received[0].event_type == RecordingEventType.STARTED
        assert received[0].payload["output_path"] == "demo.mp4"

    def test_unsubscribe(self) -> None:
        bus = InMemoryEventBus()
        called = {"count": 0}

        def handler(event: RecordingEvent) -> None:
            called["count"] += 1

        bus.subscribe(RecordingEventType.STOPPED, handler)
        bus.unsubscribe(RecordingEventType.STOPPED, handler)
        bus.publish(
            RecordingEvent(
                event_type=RecordingEventType.STOPPED,
                payload={"filepath": "demo.mp4"},
            )
        )

        assert called["count"] == 0
