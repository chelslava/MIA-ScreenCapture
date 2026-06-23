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

    def test_handler_exception_does_not_break_chain(self) -> None:
        bus = InMemoryEventBus()
        called = {"ok": 0}

        def broken_handler(event: RecordingEvent) -> None:
            raise RuntimeError("handler failed")

        def ok_handler(event: RecordingEvent) -> None:
            called["ok"] += 1

        bus.subscribe(RecordingEventType.ERROR, broken_handler)
        bus.subscribe(RecordingEventType.ERROR, ok_handler)

        bus.publish(
            RecordingEvent(
                event_type=RecordingEventType.ERROR,
                payload={"error": "boom"},
            )
        )

        assert called["ok"] == 1
