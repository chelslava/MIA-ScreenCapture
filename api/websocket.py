"""
Модуль подготовки WebSocket/SSE уведомлений.

Содержит транспорт-независимый менеджер событий, который получает события
из core.event_bus и хранит недавнюю историю для последующей публикации
через WebSocket/SSE транспорт.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict
from threading import Lock
from typing import Any, Deque, Dict, List, Optional

from core.event_bus import EventBus, RecordingEvent, RecordingEventType


class WebSocketManager:
    """
    Менеджер доменных событий для real-time транспорта.

    Текущая реализация хранит историю событий и счётчики.
    Это позволяет уже сейчас потреблять события через REST endpoint,
    а позже подключить WebSocket/SSE транспорт без изменения ядра.
    """

    def __init__(self, max_events: int = 500) -> None:
        self._events: Deque[Dict[str, Any]] = deque(maxlen=max_events)
        self._lock = Lock()
        self._events_published = 0
        self._attached_bus: Optional[EventBus] = None

    def attach_event_bus(self, event_bus: EventBus) -> None:
        """Подключает менеджер ко всем доменным событиям event bus."""
        if self._attached_bus is event_bus:
            return

        if self._attached_bus is not None:
            self.detach_event_bus()

        for event_type in RecordingEventType:
            event_bus.subscribe(event_type, self.handle_recording_event)
        self._attached_bus = event_bus

    def detach_event_bus(self) -> None:
        """Отключает менеджер от ранее подключённого event bus."""
        if self._attached_bus is None:
            return
        for event_type in RecordingEventType:
            self._attached_bus.unsubscribe(
                event_type, self.handle_recording_event
            )
        self._attached_bus = None

    def handle_recording_event(self, event: RecordingEvent) -> None:
        """Обработчик события записи из event bus."""
        payload = self._event_to_payload(event)
        self.publish(payload)

    def publish(self, payload: Dict[str, Any]) -> None:
        """Публикация события в очередь уведомлений."""
        with self._lock:
            self._events.append(dict(payload))
            self._events_published += 1

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Возвращает последние события (по умолчанию до 50)."""
        safe_limit = max(1, min(limit, 500))
        with self._lock:
            return list(self._events)[-safe_limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Возвращает статистику менеджера уведомлений."""
        with self._lock:
            buffered = len(self._events)
            published = self._events_published
        return {
            "buffered_events": buffered,
            "events_published_total": published,
            "transport_ready": True,
            "attached_to_event_bus": self._attached_bus is not None,
        }

    @staticmethod
    def _event_to_payload(event: RecordingEvent) -> Dict[str, Any]:
        raw = asdict(event)
        timestamp = raw["timestamp"]
        return {
            "type": event.event_type.value,
            "timestamp": timestamp.isoformat(),
            "data": dict(event.payload),
        }
