#!/usr/bin/env bash
# plane-configure.sh — IaC script to configure Plane workspace and project
# Creates: fleet workspace, openclaw-fleet project, devops API token
# Requires: running Plane stack (docker-compose.plane.yaml) with migrations complete
#
# Usage:
#   ./scripts/plane-configure.sh
#
# Output:
#   .plane-config (gitignored) — workspace ID, project ID, API token

set -euo pipefail

PLANE_URL="${PLANE_URL:-http://localhost:8080}"
PLANE_ADMIN_EMAIL="${PLANE_ADMIN_EMAIL:-admin@fleet.local}"
PLANE_ADMIN_PASSWORD="${PLANE_ADMIN_PASSWORD:-FleetAdmin2026!}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-dspd-plane}"
API_CONTAINER="${API_CONTAINER:-${COMPOSE_PROJECT}-api-1}"
CONFIG_FILE="${CONFIG_FILE:-.plane-config}"

log() { echo "[plane-configure] $*"; }
die() { echo "[plane-configure] ERROR: $*" >&2; exit 1; }

# ── Pre-flight ─────────────────────────────────────────────────────────────────

log "Checking Plane is running..."
HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" "$PLANE_URL/")
[ "$HTTP_CODE" = "200" ] || die "Plane not reachable at $PLANE_URL (HTTP $HTTP_CODE)"
log "Plane is up (HTTP 200)"

# ── Wait for migrations ─────────────────────────────────────────────────────────

log "Waiting for migrations to complete..."
for i in $(seq 1 30); do
    MIGRATOR_STATUS=$(docker inspect "${COMPOSE_PROJECT}-migrator-1" --format '{{.State.Status}}' 2>/dev/null || echo "not_found")
    if [ "$MIGRATOR_STATUS" = "exited" ]; then
        EXIT_CODE=$(docker inspect "${COMPOSE_PROJECT}-migrator-1" --format '{{.State.ExitCode}}' 2>/dev/null)
        [ "$EXIT_CODE" = "0" ] || die "Migrator exited with code $EXIT_CODE — check logs"
        log "Migrations complete"
        break
    fi
    sleep 5
    [ $i -eq 30 ] && die "Migrations did not complete within 150s"
done

# ── Create superuser (idempotent) ───────────────────────────────────────────────

log "Creating admin user ($PLANE_ADMIN_EMAIL)..."
docker exec "$API_CONTAINER" python manage.py createsuperuser \
    --email "$PLANE_ADMIN_EMAIL" \
    --username admin \
    --noinput 2>/dev/null \
    && log "Superuser created" \
    || log "Superuser already exists"

# Set admin password (createsuperuser --noinput doesn't set one)
docker exec "$API_CONTAINER" python manage.py shell -c "
from plane.db.models import User
u = User.objects.get(email='${PLANE_ADMIN_EMAIL}')
u.set_password('${PLANE_ADMIN_PASSWORD}')
u.save(update_fields=['password'])
print('ok')
" 2>/dev/null && log "Admin password set" || log "WARN: Could not set admin password"

docker exec "$API_CONTAINER" python manage.py create_instance_admin "$PLANE_ADMIN_EMAIL" 2>/dev/null \
    && log "Instance admin set" \
    || log "Instance admin already set"

# ── Configure workspace, project, and API token ─────────────────────────────────

log "Configuring workspace, project, and API token..."

OUTPUT=$(docker exec "$API_CONTAINER" python manage.py shell -c "
import os, json
from plane.db.models import User, Workspace, WorkspaceMember, Project, ProjectMember, APIToken

user = User.objects.get(email='${PLANE_ADMIN_EMAIL}')

# Workspace
ws, _ = Workspace.objects.get_or_create(
    slug='fleet',
    defaults={'name': 'Fleet', 'owner': user, 'organization_size': '2-10'}
)
WorkspaceMember.objects.get_or_create(workspace=ws, member=user, defaults={'role': 20})

# Project
proj, _ = Project.objects.get_or_create(
    identifier='OF',
    workspace=ws,
    defaults={
        'name': 'openclaw-fleet',
        'description': 'OpenClaw fleet project management',
        'network': 2,
        'created_by': user,
        'updated_by': user,
    }
)
ProjectMember.objects.get_or_create(project=proj, member=user, defaults={'role': 20, 'is_active': True})

# API Token
token, _ = APIToken.objects.get_or_create(
    label='fleet-devops-ws',
    user=user,
    workspace=ws,
    defaults={'is_active': True}
)

result = {
    'workspace_slug': ws.slug,
    'workspace_id': str(ws.id),
    'project_id': str(proj.id),
    'project_identifier': proj.identifier,
    'api_token': token.token,
}
print(json.dumps(result))
" 2>/dev/null)

WORKSPACE_SLUG=$(echo "$OUTPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['workspace_slug'])")
WORKSPACE_ID=$(echo "$OUTPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['workspace_id'])")
PROJECT_ID=$(echo "$OUTPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['project_id'])")
PROJECT_IDENTIFIER=$(echo "$OUTPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['project_identifier'])")
API_TOKEN=$(echo "$OUTPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['api_token'])")

# ── Verify API access ──────────────────────────────────────────────────────────

log "Verifying API access..."
MEMBERS=$(curl -sS -H "X-Api-Key: $API_TOKEN" "$PLANE_URL/api/v1/workspaces/$WORKSPACE_SLUG/members/" 2>/dev/null)
MEMBER_COUNT=$(echo "$MEMBERS" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
[ "$MEMBER_COUNT" -gt "0" ] || die "API access verification failed — members endpoint returned 0 results"

PROJECTS=$(curl -sS -H "X-Api-Key: $API_TOKEN" "$PLANE_URL/api/v1/workspaces/$WORKSPACE_SLUG/projects/" 2>/dev/null)
PROJECT_COUNT=$(echo "$PROJECTS" | python3 -c "import json,sys; d=json.load(sys.stdin); items=d.get('results',d); print(len(items))" 2>/dev/null || echo "0")
[ "$PROJECT_COUNT" -gt "0" ] || die "API access verification failed — projects endpoint returned 0 results"
log "API access verified: $MEMBER_COUNT member(s), $PROJECT_COUNT project(s)"

# ── Write config file ──────────────────────────────────────────────────────────

cat > "$CONFIG_FILE" << EOF
# Plane configuration — auto-generated by plane-configure.sh
# WARNING: Contains secrets — gitignored, do not commit
PLANE_URL=$PLANE_URL
PLANE_WORKSPACE_SLUG=$WORKSPACE_SLUG
PLANE_WORKSPACE_ID=$WORKSPACE_ID
PLANE_PROJECT_ID=$PROJECT_ID
PLANE_PROJECT_IDENTIFIER=$PROJECT_IDENTIFIER
PLANE_API_TOKEN=$API_TOKEN
EOF

log "Config written to $CONFIG_FILE"

# ── Configure Plane instance (god-mode) ─────────────────────────────────────

log "Configuring Plane instance settings..."
INSTANCE_NAME="${PLANE_INSTANCE_NAME:-OpenClaw Fleet Management}"
docker exec "$API_CONTAINER" python manage.py shell -c "
from plane.license.models import Instance, InstanceAdmin
from plane.db.models import User
instance = Instance.objects.first()
instance.instance_name = '${INSTANCE_NAME}'
instance.domain = '${PLANE_URL}'
instance.is_setup_done = True
instance.save(update_fields=['instance_name', 'domain', 'is_setup_done'])
user = User.objects.get(email='${PLANE_ADMIN_EMAIL}')
InstanceAdmin.objects.get_or_create(instance=instance, user=user, defaults={'role': 20})
print('ok')
" 2>/dev/null && log "Instance setup complete (name: ${INSTANCE_NAME})" || log "Instance setup skipped"

log ""
log "✅ Plane configured successfully:"
log "   Instance:   ${INSTANCE_NAME}"
log "   Workspace:  $WORKSPACE_SLUG ($WORKSPACE_ID)"
log "   Project:    openclaw-fleet / $PROJECT_IDENTIFIER ($PROJECT_ID)"
log "   API Token:  ${API_TOKEN:0:24}..."
log "   Admin:      ${PLANE_ADMIN_EMAIL} (password in plane.env)"
log "   God-mode:   ${PLANE_URL}/god-mode/"
log "   Plane URL:  $PLANE_URL"
