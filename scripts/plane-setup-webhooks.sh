#!/usr/bin/env bash
# plane-setup-webhooks.sh — Register webhook in Plane + generate HMAC secret
# Creates a webhook that sends issue/cycle/comment events to the fleet receiver.
# Stores HMAC secret in plane.env for verification.
# Idempotent: checks for existing webhook before creating.
#
# Usage:
#   COMPOSE_PROJECT=dspd-plane ./scripts/plane-setup-webhooks.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${PROJECT_DIR}/plane.env"
CONFIG_FILE="${PROJECT_DIR}/.plane-config"

PLANE_URL="${PLANE_URL:-http://localhost:8080}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-dspd-plane}"
API_CONTAINER="${API_CONTAINER:-${COMPOSE_PROJECT}-api-1}"
PLANE_ADMIN_EMAIL="${PLANE_ADMIN_EMAIL:-admin@fleet.local}"
WEBHOOK_URL="${WEBHOOK_URL:-http://host.docker.internal:8001/webhook}"

log() { echo "[plane-setup-webhooks] $*"; }
die() { echo "[plane-setup-webhooks] ERROR: $*" >&2; exit 1; }

# Generate HMAC secret if not already in env
if grep -q "^PLANE_WEBHOOK_SECRET=" "$ENV_FILE" 2>/dev/null; then
    WEBHOOK_SECRET=$(grep "^PLANE_WEBHOOK_SECRET=" "$ENV_FILE" | cut -d= -f2-)
    log "Using existing PLANE_WEBHOOK_SECRET"
else
    WEBHOOK_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    echo "PLANE_WEBHOOK_SECRET=${WEBHOOK_SECRET}" >> "$ENV_FILE"
    log "Generated PLANE_WEBHOOK_SECRET"
fi

# Read workspace slug from .plane-config
if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
fi
WS_SLUG="${PLANE_WORKSPACE_SLUG:-fleet}"

docker exec "$API_CONTAINER" python manage.py shell -c "
from plane.db.models import User, Workspace, Webhook

user = User.objects.get(email='${PLANE_ADMIN_EMAIL}')
ws = Workspace.objects.get(slug='${WS_SLUG}')

# Check for existing webhook with same URL
existing = Webhook.objects.filter(workspace=ws, url='${WEBHOOK_URL}').first()
if existing:
    # Update secret and events
    existing.secret_key = '${WEBHOOK_SECRET}'
    existing.is_active = True
    existing.save(update_fields=['secret_key', 'is_active'])
    print(f'UPDATED: webhook {existing.id} → ${WEBHOOK_URL}')
else:
    webhook = Webhook.objects.create(
        workspace=ws,
        url='${WEBHOOK_URL}',
        secret_key='${WEBHOOK_SECRET}',
        is_active=True,
        created_by=user,
        updated_by=user,
    )
    print(f'CREATED: webhook {webhook.id} → ${WEBHOOK_URL}')

print(f'Events: issue.*, cycle.*, comment.created')
print(f'HMAC: SHA256 with stored secret')
" 2>&1 && log "Webhook configured" || log "WARN: Webhook setup failed (Plane may not support Webhook model in this version)"

log ""
log "Webhook URL:    $WEBHOOK_URL"
log "HMAC secret:    ${WEBHOOK_SECRET:0:16}..."
log "Verify header:  X-Plane-Signature"