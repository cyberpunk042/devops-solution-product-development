"""Tests for dspd.webhooks module."""

import json

import pytest

from dspd.webhooks import (
    WebhookEvent,
    dispatch_event,
    on_event,
    parse_event,
    verify_signature,
)


class TestVerifySignature:
    """HMAC-SHA256 signature verification."""

    def test_valid_signature(self):
        payload = b'{"event": "issue.created", "data": {}}'
        secret = "test-secret-key"
        import hashlib, hmac as _hmac
        sig = _hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert verify_signature(payload, sig, secret) is True

    def test_invalid_signature(self):
        payload = b'{"event": "issue.created"}'
        assert verify_signature(payload, "bad-sig", "secret") is False

    def test_empty_signature(self):
        assert verify_signature(b"data", "", "secret") is False

    def test_empty_secret(self):
        assert verify_signature(b"data", "sig", "") is False

    def test_tampered_payload(self):
        secret = "key"
        original = b'{"amount": 100}'
        import hashlib, hmac as _hmac
        sig = _hmac.new(secret.encode(), original, hashlib.sha256).hexdigest()
        tampered = b'{"amount": 999}'
        assert verify_signature(tampered, sig, secret) is False


class TestParseEvent:
    """Webhook event parsing."""

    def test_parse_issue_created(self):
        payload = {
            "event": "issue.created",
            "data": {
                "name": "Test issue",
                "project": "abc-123",
                "workspace_detail": {"slug": "fleet"},
            },
        }
        event = parse_event(payload)
        assert event is not None
        assert event.event_type == "issue.created"
        assert event.resource == "issue"
        assert event.action == "created"
        assert event.workspace_slug == "fleet"
        assert event.project_id == "abc-123"

    def test_parse_cycle_completed(self):
        payload = {
            "event": "cycle.completed",
            "data": {"name": "Sprint 1", "project_id": "xyz"},
        }
        event = parse_event(payload)
        assert event.resource == "cycle"
        assert event.action == "completed"

    def test_parse_malformed_no_event(self):
        assert parse_event({"data": {}}) is None

    def test_parse_malformed_no_dot(self):
        assert parse_event({"event": "nodot"}) is None

    def test_parse_empty_data(self):
        event = parse_event({"event": "issue.updated", "data": {}})
        assert event is not None
        assert event.data == {}
        assert event.workspace_slug == ""


class TestDispatchEvent:
    """Event dispatch to handlers."""

    def test_dispatch_calls_handler(self):
        called = []

        @on_event("test.custom_event")
        def handler(event):
            called.append(event.event_type)

        event = WebhookEvent(
            event_type="test.custom_event",
            resource="test",
            action="custom_event",
            data={},
            workspace_slug="fleet",
            project_id="",
        )
        result = dispatch_event(event)
        assert len(called) == 1
        assert "test.custom_event:handler" in result

    def test_dispatch_no_handler(self):
        event = WebhookEvent(
            event_type="unknown.event_type",
            resource="unknown",
            action="event_type",
            data={},
            workspace_slug="",
            project_id="",
        )
        result = dispatch_event(event)
        assert result == []

    def test_handler_exception_doesnt_crash(self):
        @on_event("test.error_event")
        def bad_handler(event):
            raise ValueError("boom")

        event = WebhookEvent(
            event_type="test.error_event",
            resource="test",
            action="error_event",
            data={},
            workspace_slug="",
            project_id="",
        )
        result = dispatch_event(event)
        assert len(result) == 0  # handler failed, not counted as called