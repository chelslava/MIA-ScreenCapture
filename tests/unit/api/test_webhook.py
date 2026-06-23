"""Тесты подписи и доставки webhook-уведомлений (#52)."""

import time
from unittest.mock import MagicMock, patch

import requests

from core.event_bus import InMemoryEventBus, RecordingEvent, RecordingEventType
from core.webhook import (
    WebhookNotifier,
    WebhookPayload,
    WebhookSender,
    WebhookSigner,
    generate_webhook_secret,
)


class TestWebhookSigner:
    """Тесты HMAC-подписи и проверки webhook."""

    def test_sign_and_verify_round_trip(self) -> None:
        """Корректно подписанный запрос должен проходить проверку."""
        signer = WebhookSigner()
        payload = WebhookPayload(
            event="recording.completed",
            timestamp=int(time.time()),
            data={"file_path": "video.mp4"},
        )
        secret = "test-secret"

        headers = signer.sign(payload, secret)

        assert signer.verify(payload.to_bytes(), headers, secret) is True

    def test_verify_fails_on_tampered_body(self) -> None:
        """Изменённое тело запроса должно проваливать проверку подписи."""
        signer = WebhookSigner()
        payload = WebhookPayload(
            event="recording.completed",
            timestamp=int(time.time()),
            data={"file_path": "video.mp4"},
        )
        secret = "test-secret"
        headers = signer.sign(payload, secret)

        tampered_body = b'{"event": "recording.completed", "tampered": true}'

        assert signer.verify(tampered_body, headers, secret) is False

    def test_verify_fails_on_wrong_secret(self) -> None:
        """Проверка с неверным секретом должна провалиться."""
        signer = WebhookSigner()
        payload = WebhookPayload(
            event="recording.completed", timestamp=int(time.time()), data={}
        )
        headers = signer.sign(payload, "correct-secret")

        assert (
            signer.verify(payload.to_bytes(), headers, "wrong-secret") is False
        )

    def test_verify_fails_on_expired_timestamp(self) -> None:
        """Просроченный (за пределами TTL) timestamp должен отвергаться."""
        signer = WebhookSigner()
        old_timestamp = int(time.time())
        payload = WebhookPayload(
            event="recording.completed", timestamp=old_timestamp, data={}
        )
        secret = "test-secret"
        headers = signer.sign(payload, secret)

        with patch(
            "core.webhook.time.time",
            return_value=old_timestamp
            + signer.TIMESTAMP_TOLERANCE_SECONDS
            + 1,
        ):
            assert signer.verify(payload.to_bytes(), headers, secret) is False

    def test_verify_fails_on_missing_headers(self) -> None:
        """Отсутствие заголовков подписи должно отвергаться."""
        signer = WebhookSigner()
        assert signer.verify(b"{}", {}, "secret") is False

    def test_verify_fails_on_non_numeric_timestamp(self) -> None:
        """Нечисловой timestamp не должен вызывать исключение."""
        signer = WebhookSigner()
        headers = {
            "X-MIA-Signature": "deadbeef",
            "X-MIA-Timestamp": "not-a-number",
        }
        assert signer.verify(b"{}", headers, "secret") is False


class TestGenerateWebhookSecret:
    """Тесты генерации секрета."""

    def test_generate_webhook_secret_is_url_safe_and_long_enough(
        self,
    ) -> None:
        """Секрет должен быть достаточно длинным (256-bit) и url-safe."""
        secret = generate_webhook_secret()
        assert len(secret) >= 32
        assert all(c.isalnum() or c in "-_" for c in secret)

    def test_generate_webhook_secret_is_unique(self) -> None:
        """Повторные вызовы должны давать разные секреты."""
        assert generate_webhook_secret() != generate_webhook_secret()


class TestWebhookSender:
    """Тесты отправки webhook с retry."""

    def test_send_success_on_first_attempt(self) -> None:
        """Успешный ответ 2xx должен сразу возвращать success=True."""
        response = MagicMock(status_code=200)
        with patch(
            "core.webhook.requests.post", return_value=response
        ) as post:
            sender = WebhookSender()
            success, response_time_ms = sender.send(
                url="https://example.com/webhook",
                event="recording.completed",
                data={"file_path": "video.mp4"},
            )

        assert success is True
        assert response_time_ms >= 0
        post.assert_called_once()

    def test_send_includes_signature_headers_when_secret_given(self) -> None:
        """При наличии секрета запрос должен содержать заголовки подписи."""
        response = MagicMock(status_code=200)
        with patch(
            "core.webhook.requests.post", return_value=response
        ) as post:
            sender = WebhookSender()
            sender.send(
                url="https://example.com/webhook",
                event="recording.completed",
                data={},
                secret="my-secret",
            )

        _, kwargs = post.call_args
        assert "X-MIA-Signature" in kwargs["headers"]
        assert "X-MIA-Timestamp" in kwargs["headers"]

    def test_send_omits_signature_headers_without_secret(self) -> None:
        """Без секрета заголовки подписи не должны добавляться."""
        response = MagicMock(status_code=200)
        with patch(
            "core.webhook.requests.post", return_value=response
        ) as post:
            sender = WebhookSender()
            sender.send(
                url="https://example.com/webhook",
                event="recording.completed",
                data={},
            )

        _, kwargs = post.call_args
        assert "X-MIA-Signature" not in kwargs["headers"]

    def test_send_retries_on_failure_then_succeeds(self) -> None:
        """Временная ошибка не должна приводить к итоговому провалу."""
        failing_response = MagicMock(status_code=500)
        ok_response = MagicMock(status_code=200)
        with (
            patch(
                "core.webhook.requests.post",
                side_effect=[failing_response, ok_response],
            ) as post,
            patch("core.webhook.time.sleep"),
        ):
            sender = WebhookSender(max_attempts=3)
            success, _ = sender.send(
                url="https://example.com/webhook",
                event="recording.completed",
                data={},
            )

        assert success is True
        assert post.call_count == 2

    def test_send_exhausts_retries_and_fails(self) -> None:
        """После исчерпания всех попыток должен возвращаться success=False."""
        with (
            patch(
                "core.webhook.requests.post",
                side_effect=requests.ConnectionError("connection refused"),
            ) as post,
            patch("core.webhook.time.sleep"),
        ):
            sender = WebhookSender(max_attempts=2)
            success, _ = sender.send(
                url="https://example.com/webhook",
                event="recording.error",
                data={},
            )

        assert success is False
        assert post.call_count == 2


class TestWebhookNotifier:
    """Тесты EventBus-подписчика, транслирующего события в webhook."""

    def _config_with_webhook(
        self,
        url: str | None = "https://example.com/webhook",
        enabled: bool = True,
        secret: str | None = "secret-value",
    ) -> MagicMock:
        config = MagicMock()
        config.settings.api.webhook_url = url
        config.settings.api.webhook_enabled = enabled
        config.settings.api.webhook_secret = secret
        return config

    def test_notifier_sends_on_stopped_event(self) -> None:
        """STOPPED событие должно отправлять webhook recording.completed."""
        sender = MagicMock(spec=WebhookSender)
        sender.send.return_value = (True, 12.5)
        notifier = WebhookNotifier(sender=sender)
        bus = InMemoryEventBus()
        notifier.attach_event_bus(bus)

        with patch(
            "config.get_config",
            return_value=self._config_with_webhook(),
        ):
            bus.publish(
                RecordingEvent(
                    event_type=RecordingEventType.STOPPED,
                    payload={"filepath": "video.mp4"},
                )
            )

        sender.send.assert_called_once()
        _, kwargs = sender.send.call_args
        assert kwargs["event"] == "recording.completed"
        assert kwargs["url"] == "https://example.com/webhook"
        assert kwargs["secret"] == "secret-value"

    def test_notifier_sends_on_error_event(self) -> None:
        """ERROR событие должно отправлять webhook recording.error."""
        sender = MagicMock(spec=WebhookSender)
        sender.send.return_value = (True, 5.0)
        notifier = WebhookNotifier(sender=sender)
        bus = InMemoryEventBus()
        notifier.attach_event_bus(bus)

        with patch(
            "config.get_config",
            return_value=self._config_with_webhook(),
        ):
            bus.publish(
                RecordingEvent(
                    event_type=RecordingEventType.ERROR,
                    payload={"error": "disk full"},
                )
            )

        _, kwargs = sender.send.call_args
        assert kwargs["event"] == "recording.error"

    def test_notifier_ignores_unsubscribed_event_types(self) -> None:
        """STARTED/PROGRESS не должны вызывать отправку webhook."""
        sender = MagicMock(spec=WebhookSender)
        notifier = WebhookNotifier(sender=sender)
        bus = InMemoryEventBus()
        notifier.attach_event_bus(bus)

        with patch(
            "config.get_config",
            return_value=self._config_with_webhook(),
        ):
            bus.publish(
                RecordingEvent(
                    event_type=RecordingEventType.STARTED, payload={}
                )
            )
            bus.publish(
                RecordingEvent(
                    event_type=RecordingEventType.PROGRESS, payload={}
                )
            )

        sender.send.assert_not_called()

    def test_notifier_does_nothing_when_disabled(self) -> None:
        """Webhook выключен -> отправка не должна происходить."""
        sender = MagicMock(spec=WebhookSender)
        notifier = WebhookNotifier(sender=sender)
        bus = InMemoryEventBus()
        notifier.attach_event_bus(bus)

        with patch(
            "config.get_config",
            return_value=self._config_with_webhook(enabled=False),
        ):
            bus.publish(
                RecordingEvent(
                    event_type=RecordingEventType.STOPPED, payload={}
                )
            )

        sender.send.assert_not_called()

    def test_notifier_does_nothing_without_url(self) -> None:
        """Webhook включён, но URL не настроен -> отправка не должна происходить."""
        sender = MagicMock(spec=WebhookSender)
        notifier = WebhookNotifier(sender=sender)
        bus = InMemoryEventBus()
        notifier.attach_event_bus(bus)

        with patch(
            "config.get_config",
            return_value=self._config_with_webhook(url=None),
        ):
            bus.publish(
                RecordingEvent(
                    event_type=RecordingEventType.STOPPED, payload={}
                )
            )

        sender.send.assert_not_called()

    def test_detach_event_bus_stops_notifications(self) -> None:
        """После detach события не должны больше вызывать отправку."""
        sender = MagicMock(spec=WebhookSender)
        notifier = WebhookNotifier(sender=sender)
        bus = InMemoryEventBus()
        notifier.attach_event_bus(bus)
        notifier.detach_event_bus()

        with patch(
            "config.get_config",
            return_value=self._config_with_webhook(),
        ):
            bus.publish(
                RecordingEvent(
                    event_type=RecordingEventType.STOPPED, payload={}
                )
            )

        sender.send.assert_not_called()
