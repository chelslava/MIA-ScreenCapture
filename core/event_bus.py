"""
Транспорт-независимый event bus для событий домена записи.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import Lock
from typing import Any, Callable, Dict, List, Protocol

from logger_config import get_module_logger

logger = get_module_logger(__name__)


class RecordingEventType(str, Enum):
    """Типы доменных событий записи."""

    STARTED = "started"
    STOPPED = "stopped"
    PAUSED = "paused"
    RESUMED = "resumed"
    PROGRESS = "progress"
    ERROR = "error"
    STATUS = "status"


@dataclass(frozen=True)
class RecordingEvent:
    """Событие домена записи."""

    event_type: RecordingEventType
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


EventHandler = Callable[[RecordingEvent], None]


class EventBus(Protocol):
    """Контракт event bus для транспортного слоя (WebSocket/лог/метрики)."""

    def subscribe(
        self, event_type: RecordingEventType, handler: EventHandler
    ) -> None:
        """Подписывает обработчик на тип события."""

    def unsubscribe(
        self, event_type: RecordingEventType, handler: EventHandler
    ) -> None:
        """Отписывает обработчик от типа события."""

    def publish(self, event: RecordingEvent) -> None:
        """Публикует событие в bus."""


class InMemoryEventBus:
    """
    In-memory реализация event bus.

    Не привязана к транспорту и подходит как базовый адаптер для будущего
    WebSocket моста.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[RecordingEventType, List[EventHandler]] = {
            event_type: [] for event_type in RecordingEventType
        }
        self._lock = Lock()

    def subscribe(
        self, event_type: RecordingEventType, handler: EventHandler
    ) -> None:
        with self._lock:
            handlers = self._subscribers[event_type]
            if handler not in handlers:
                handlers.append(handler)

    def unsubscribe(
        self, event_type: RecordingEventType, handler: EventHandler
    ) -> None:
        with self._lock:
            handlers = self._subscribers[event_type]
            if handler in handlers:
                handlers.remove(handler)

    def publish(self, event: RecordingEvent) -> None:
        with self._lock:
            handlers = list(self._subscribers.get(event.event_type, []))
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.warning(
                    f"Ошибка обработчика события {event.event_type}: {e}"
                )
