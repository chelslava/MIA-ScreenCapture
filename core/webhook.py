"""
Подпись и доставка webhook-уведомлений о событиях записи.

Webhook отправляется при завершении записи (`recording.completed`) и при
ошибке (`recording.error`), подписан HMAC-SHA256 с защитой от replay-атак
через timestamp (TTL 5 минут).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

import requests

from core.event_bus import EventBus, RecordingEvent, RecordingEventType
from logger_config import get_module_logger

logger = get_module_logger(__name__)

SIGNATURE_TTL_SECONDS = 300
_WEBHOOK_TIMEOUT_SECONDS = 10.0
_WEBHOOK_MAX_ATTEMPTS = 3
_WEBHOOK_RETRY_DELAY_S = 1.0


def generate_webhook_secret() -> str:
    """Генерирует новый секрет для подписи webhook (256-bit, base64url)."""
    return secrets.token_urlsafe(32)


@dataclass(frozen=True)
class WebhookPayload:
    """Payload для webhook-уведомления."""

    event: str
    timestamp: int
    data: dict[str, Any] = field(default_factory=dict)

    def to_bytes(self) -> bytes:
        """Сериализует payload в канонический JSON для подписи и отправки."""
        return json.dumps(
            {
                "event": self.event,
                "timestamp": self.timestamp,
                "data": self.data,
            },
            sort_keys=True,
            default=str,
        ).encode("utf-8")


class WebhookSigner:
    """
    HMAC-SHA256 подпись webhook-запросов с защитой от replay-атак.

    Проверка подписи на стороне получателя:
        signature = headers["X-MIA-Signature"]
        timestamp = headers["X-MIA-Timestamp"]
        if abs(time.time() - int(timestamp)) > 300:
            reject()  # истёк TTL подписи
        expected = hmac.new(
            secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            reject()
    """

    TIMESTAMP_TOLERANCE_SECONDS = SIGNATURE_TTL_SECONDS

    def sign(self, payload: WebhookPayload, secret: str) -> dict[str, str]:
        """Создаёт заголовки подписи для payload."""
        body = payload.to_bytes()
        signature = self._compute_signature(payload.timestamp, body, secret)
        return {
            "X-MIA-Signature": signature,
            "X-MIA-Timestamp": str(payload.timestamp),
            "X-MIA-Event": payload.event,
        }

    def verify(
        self, body: bytes, headers: dict[str, str], secret: str
    ) -> bool:
        """Проверяет подпись и timestamp входящего webhook-запроса."""
        signature = headers.get("X-MIA-Signature", "")
        timestamp_str = headers.get("X-MIA-Timestamp", "")
        if not signature or not timestamp_str:
            return False

        try:
            timestamp = int(timestamp_str)
        except ValueError:
            return False

        if (
            abs(int(time.time()) - timestamp)
            > self.TIMESTAMP_TOLERANCE_SECONDS
        ):
            return False

        expected = self._compute_signature(timestamp, body, secret)
        return hmac.compare_digest(signature, expected)

    @staticmethod
    def _compute_signature(timestamp: int, body: bytes, secret: str) -> str:
        signature_base = f"{timestamp}.".encode() + body
        return hmac.new(
            secret.encode("utf-8"), signature_base, hashlib.sha256
        ).hexdigest()


class WebhookSender:
    """Отправка подписанных webhook-уведомлений по HTTP с retry."""

    def __init__(
        self,
        signer: WebhookSigner | None = None,
        max_attempts: int = _WEBHOOK_MAX_ATTEMPTS,
        retry_delay_s: float = _WEBHOOK_RETRY_DELAY_S,
    ) -> None:
        self._signer = signer or WebhookSigner()
        self._max_attempts = max_attempts
        self._retry_delay_s = retry_delay_s

    def send(
        self,
        url: str,
        event: str,
        data: dict[str, Any],
        secret: str | None = None,
    ) -> tuple[bool, float]:
        """
        Отправляет webhook-уведомление с retry при неудаче.

        Args:
            url: URL получателя.
            event: Тип события (`recording.completed`, `recording.error`,
                `webhook.test`).
            data: Данные события.
            secret: Секрет для HMAC-подписи. `None` — отправка без подписи.

        Returns:
            Кортеж `(success, response_time_ms)`.
        """
        payload = WebhookPayload(
            event=event, timestamp=int(time.time()), data=data
        )
        body = payload.to_bytes()
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "MIA-ScreenCapture-Webhook/1.0",
        }
        if secret:
            headers.update(self._signer.sign(payload, secret))

        start = time.time()
        last_error: Exception | None = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                response = requests.post(
                    url,
                    data=body,
                    headers=headers,
                    timeout=_WEBHOOK_TIMEOUT_SECONDS,
                )
                if 200 <= response.status_code < 300:
                    return True, (time.time() - start) * 1000
                logger.warning(
                    "Webhook %s вернул %s (попытка %s/%s)",
                    url,
                    response.status_code,
                    attempt,
                    self._max_attempts,
                )
            except requests.RequestException as e:
                last_error = e
                logger.warning(
                    "Ошибка доставки webhook %s (попытка %s/%s): %s",
                    url,
                    attempt,
                    self._max_attempts,
                    e,
                )

            if attempt < self._max_attempts:
                time.sleep(self._retry_delay_s)

        if last_error is not None:
            logger.error(
                "Webhook %s не доставлен после %s попыток: %s",
                url,
                self._max_attempts,
                last_error,
            )
        return False, (time.time() - start) * 1000


class WebhookNotifier:
    """
    EventBus-подписчик, транслирующий завершение/ошибки записи в webhook.

    Настройки (url/secret/enabled) читаются из конфигурации в момент
    события, а не кэшируются при конструировании — изменение через API
    применяется к следующей записи без перезапуска приложения.
    """

    _SUBSCRIBED_EVENTS = (
        RecordingEventType.STOPPED,
        RecordingEventType.ERROR,
    )

    def __init__(self, sender: WebhookSender | None = None) -> None:
        self._sender = sender or WebhookSender()
        self._attached_bus: EventBus | None = None

    def attach_event_bus(self, event_bus: EventBus) -> None:
        """Подключает нотификатор к STOPPED/ERROR событиям записи."""
        if self._attached_bus is event_bus:
            return
        if self._attached_bus is not None:
            self.detach_event_bus()
        for event_type in self._SUBSCRIBED_EVENTS:
            event_bus.subscribe(event_type, self.handle_recording_event)
        self._attached_bus = event_bus

    def detach_event_bus(self) -> None:
        """Отключает нотификатор от event bus."""
        if self._attached_bus is None:
            return
        for event_type in self._SUBSCRIBED_EVENTS:
            self._attached_bus.unsubscribe(
                event_type, self.handle_recording_event
            )
        self._attached_bus = None

    def handle_recording_event(self, event: RecordingEvent) -> None:
        """Обработчик доменного события — отправляет webhook, если включён."""
        from config import get_config

        api_settings = get_config().settings.api
        if not api_settings.webhook_enabled or not api_settings.webhook_url:
            return

        webhook_event = (
            "recording.completed"
            if event.event_type == RecordingEventType.STOPPED
            else "recording.error"
        )
        self._sender.send(
            url=api_settings.webhook_url,
            event=webhook_event,
            data=dict(event.payload),
            secret=api_settings.webhook_secret,
        )
