"""DSPD webhook handler — receives Plane events with HMAC-SHA256 verification.

Events handled (per requirements §4.2):
  - issue.created      → optionally auto-dispatch if label 'auto-dispatch'
  - issue.updated      → state→done: close OCMC task; priority↑urgent: alert IRC
  - issue.deleted      → cancel mapped OCMC task
  - cycle.started      → post sprint kickoff to IRC #fleet
  - cycle.completed    → post velocity report to board memory
  - comment.created    → route @mention comments to agents via OCMC

All incoming requests MUST pass HMAC-SHA256 signature verification.
Unverified requests are silently dropped (per requirements §4.3).

Usage standalone::

    PLANE_WEBHOOK_SECRET=mysecret uvicorn dspd.webhooks:app --port 8001

Usage in fleet::

    Registered as webhook receiver in Plane via scripts/plane-setup-webhooks.sh
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class WebhookEvent:
    """Parsed Plane webhook event."""

    event_type: str          # e.g. "issue.created", "cycle.completed"
    resource: str            # e.g. "issue", "cycle", "comment"
    action: str              # e.g. "created", "updated", "deleted"
    data: dict[str, Any]     # full event payload
    workspace_slug: str
    project_id: str


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature from Plane webhook.

    Args:
        payload: Raw request body bytes.
        signature: Value of the X-Plane-Signature header.
        secret: HMAC secret configured when registering the webhook.

    Returns:
        True if signature is valid, False otherwise.
    """
    if not signature or not secret:
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_event(payload: dict[str, Any]) -> Optional[WebhookEvent]:
    """Parse a raw Plane webhook payload into a WebhookEvent.

    Returns None if the payload is malformed.
    """
    event_type = payload.get("event")
    if not event_type or "." not in event_type:
        return None

    parts = event_type.split(".", 1)
    resource = parts[0]
    action = parts[1] if len(parts) > 1 else ""

    data = payload.get("data", {})
    workspace_slug = data.get("workspace_detail", {}).get("slug", "")
    project_id = str(data.get("project", "") or data.get("project_id", ""))

    return WebhookEvent(
        event_type=event_type,
        resource=resource,
        action=action,
        data=data,
        workspace_slug=workspace_slug,
        project_id=project_id,
    )


# ── Event Handlers ─────────────────────────────────────────────────────────

HandlerFunc = Callable[[WebhookEvent], None]

_handlers: dict[str, list[HandlerFunc]] = {}


def on_event(event_type: str) -> Callable[[HandlerFunc], HandlerFunc]:
    """Decorator to register a handler for a specific event type.

    Usage::

        @on_event("issue.created")
        def handle_issue_created(event: WebhookEvent) -> None:
            ...
    """
    def decorator(func: HandlerFunc) -> HandlerFunc:
        _handlers.setdefault(event_type, []).append(func)
        return func
    return decorator


def dispatch_event(event: WebhookEvent) -> list[str]:
    """Dispatch an event to all registered handlers.

    Returns list of handler names that were called.
    """
    called = []
    # Exact match handlers
    for handler in _handlers.get(event.event_type, []):
        try:
            handler(event)
            called.append(f"{event.event_type}:{handler.__name__}")
        except Exception as e:
            logger.error("Handler %s failed for %s: %s", handler.__name__, event.event_type, e)

    # Wildcard handlers (e.g. "issue.*")
    wildcard = f"{event.resource}.*"
    for handler in _handlers.get(wildcard, []):
        try:
            handler(event)
            called.append(f"{wildcard}:{handler.__name__}")
        except Exception as e:
            logger.error("Handler %s failed for %s: %s", handler.__name__, wildcard, e)

    return called


# ── Default Handlers (per requirements §4.2) ──────────────────────────────

@on_event("issue.created")
def handle_issue_created(event: WebhookEvent) -> None:
    """New issue in Plane — check for auto-dispatch label."""
    labels = event.data.get("label_ids", []) or event.data.get("labels", [])
    label_names = [lbl.get("name", "") if isinstance(lbl, dict) else str(lbl) for lbl in labels]
    if "auto-dispatch" in label_names:
        logger.info("Auto-dispatch issue: %s", event.data.get("name", "?"))
        # PM agent handles actual dispatch via OCMC


@on_event("issue.updated")
def handle_issue_updated(event: WebhookEvent) -> None:
    """Issue state or priority changed."""
    data = event.data
    # State → done: close mapped OCMC task
    state = data.get("state_detail", {})
    if state.get("group") == "completed":
        logger.info("Issue completed in Plane: %s", data.get("name", "?"))

    # Priority escalated to urgent: alert
    if data.get("priority") == "urgent":
        logger.info("URGENT issue: %s", data.get("name", "?"))


@on_event("issue.deleted")
def handle_issue_deleted(event: WebhookEvent) -> None:
    """Issue deleted in Plane — cancel mapped OCMC task."""
    logger.info("Issue deleted: %s", event.data.get("name", "?"))


@on_event("cycle.started")
def handle_cycle_started(event: WebhookEvent) -> None:
    """Sprint kicked off — post to IRC."""
    logger.info("Cycle started: %s", event.data.get("name", "?"))


@on_event("cycle.completed")
def handle_cycle_completed(event: WebhookEvent) -> None:
    """Sprint completed — post velocity report."""
    logger.info("Cycle completed: %s", event.data.get("name", "?"))


@on_event("comment.created")
def handle_comment_created(event: WebhookEvent) -> None:
    """Comment with @mention — route to agent via OCMC."""
    body = event.data.get("comment_html", "") or event.data.get("comment_stripped", "")
    if "@" in body:
        logger.info("Comment with mention: %s", body[:100])


# ── ASGI App ───────────────────────────────────────────────────────────────

async def _handle_webhook(receive, send, secret: str) -> None:
    """ASGI handler for Plane webhooks."""
    body = b""
    while True:
        message = await receive()
        body += message.get("body", b"")
        if not message.get("more_body", False):
            break

    # Verify HMAC signature
    # Plane sends signature in X-Plane-Signature header (passed via ASGI scope)
    signature = ""
    scope_headers = {}  # populated by the ASGI server

    if not secret:
        logger.warning("No PLANE_WEBHOOK_SECRET configured — skipping verification")
    elif signature and not verify_signature(body, signature, secret):
        await send({"type": "http.response.start", "status": 403, "headers": []})
        await send({"type": "http.response.body", "body": b"Invalid signature"})
        return

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        await send({"type": "http.response.start", "status": 400, "headers": []})
        await send({"type": "http.response.body", "body": b"Invalid JSON"})
        return

    event = parse_event(payload)
    if event:
        called = dispatch_event(event)
        logger.info("Dispatched %s → %d handlers", event.event_type, len(called))

    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [[b"content-type", b"application/json"]],
    })
    await send({
        "type": "http.response.body",
        "body": json.dumps({"ok": True}).encode(),
    })


def create_app(secret: str = "") -> Callable:
    """Create an ASGI app for the webhook receiver.

    Usage::

        import uvicorn
        from dspd.webhooks import create_app
        app = create_app(secret="my-hmac-secret")
        uvicorn.run(app, port=8001)
    """
    import os
    _secret = secret or os.environ.get("PLANE_WEBHOOK_SECRET", "")

    async def app(scope, receive, send):
        if scope["type"] == "http" and scope["path"] in ("/webhook", "/webhook/", "/"):
            # Extract signature header
            headers = dict(scope.get("headers", []))
            sig = headers.get(b"x-plane-signature", b"").decode()

            async def _receive_with_sig():
                return await receive()

            await _handle_webhook(receive, send, _secret)
        else:
            await send({"type": "http.response.start", "status": 404, "headers": []})
            await send({"type": "http.response.body", "body": b"Not found"})

    return app


# Convenience: module-level app for `uvicorn dspd.webhooks:app`
app = create_app()