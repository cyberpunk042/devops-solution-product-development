#!/usr/bin/env bash
# plane-configure.sh — IaC script to configure Plane workspace and projects
# Creates: fleet workspace, projects (openclaw-fleet, nnrt, dspd), API token
# Requires: running Plane stack with migrations complete
#
# Usage:
#   ./scripts/plane-configure.sh [config-file]
#   COMPOSE_PROJECT=dspd-plane ./scripts/plane-configure.sh
#
# Output:
#   .plane-config (gitignored) — workspace ID, project IDs, API token

set -euo pipefail

PLANE_URL="${PLANE_URL:-http://localhost:8080}"
PLANE_ADMIN_EMAIL="${PLANE_ADMIN_EMAIL:-admin@fleet.local}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-dspd-plane}"
API_CONTAINER="${API_CONTAINER:-${COMPOSE_PROJECT}-api-1}"
CONFIG_FILE="${CONFIG_FILE:-.plane-config}"

log() { echo "[plane-configure] $*"; }
die() { echo "[plane-configure] ERROR: $*" >&2; exit 1; }

# ── Pre-flight ──────────────────────────────────────────────────────────────

log "Checking Plane is running..."
HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 "$PLANE_URL/")
[ "$HTTP_CODE" = "200" ] || die "Plane not reachable at $PLANE_URL (HTTP $HTTP_CODE)"
log "Plane is up (HTTP 200)"

# ── Wait for migrations ─────────────────────────────────────────────────────

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

# ── Create superuser (idempotent) ───────────────────────────────────────────

PLANE_ADMIN_PASSWORD="${PLANE_ADMIN_PASSWORD:-FleetAdmin2026!}"
log "Creating admin user ($PLANE_ADMIN_EMAIL)..."
docker exec -e DJANGO_SUPERUSER_PASSWORD="$PLANE_ADMIN_PASSWORD" "$API_CONTAINER" \
    python manage.py createsuperuser --email "$PLANE_ADMIN_EMAIL" --username admin --noinput 2>/dev/null \
    && log "Superuser created" || log "Superuser already exists"

docker exec "$API_CONTAINER" python manage.py create_instance_admin "$PLANE_ADMIN_EMAIL" 2>/dev/null \
    && log "Instance admin set" || log "Instance admin already set"

# ── Configure workspace, projects, and API token ────────────────────────────

log "Configuring workspace, projects, and API token..."

OUTPUT=$(docker exec "$API_CONTAINER" python manage.py shell -c "
import json
from plane.db.models import User, Workspace, WorkspaceMember, Project, ProjectMember, APIToken, State

user = User.objects.get(email='${PLANE_ADMIN_EMAIL}')

# Workspace
ws, _ = Workspace.objects.get_or_create(
    slug='fleet',
    defaults={'name': 'Fleet', 'owner': user, 'organization_size': '2-10'}
)
WorkspaceMember.objects.get_or_create(workspace=ws, member=user, defaults={'role': 20})

# Default states template
default_states = [
    {'name': 'Backlog',     'group': 'backlog',    'color': '#A3A3A3', 'default': False, 'sequence': 15000},
    {'name': 'Todo',        'group': 'unstarted',  'color': '#3A3A3A', 'default': True,  'sequence': 25000},
    {'name': 'In Progress', 'group': 'started',    'color': '#F59E0B', 'default': False, 'sequence': 35000},
    {'name': 'Done',        'group': 'completed',  'color': '#22C55E', 'default': False, 'sequence': 45000},
    {'name': 'Cancelled',   'group': 'cancelled',  'color': '#EF4444', 'default': False, 'sequence': 55000},
]

def ensure_project(identifier, name, description):
    proj, created = Project.objects.get_or_create(
        identifier=identifier, workspace=ws,
        defaults={'name': name, 'description': description, 'network': 2,
                  'created_by': user, 'updated_by': user}
    )
    ProjectMember.objects.get_or_create(project=proj, member=user, defaults={'role': 20, 'is_active': True})
    for s_data in default_states:
        State.objects.get_or_create(
            name=s_data['name'], project=proj,
            defaults={'workspace': ws, 'group': s_data['group'], 'color': s_data['color'],
                      'default': s_data['default'], 'sequence': s_data['sequence'],
                      'created_by': user, 'updated_by': user}
        )
    return proj

# Projects
of_proj  = ensure_project('OF',   'openclaw-fleet', 'OpenClaw fleet project management')
nnrt_proj = ensure_project('NNRT', 'nnrt',           'Narrative-to-Neutral Report Transformer')
dspd_proj = ensure_project('DSPD', 'dspd',           'DevOps Solution Product Development via Plane')

# API Token (workspace-scoped)
token, _ = APIToken.objects.get_or_create(
    label='fleet-devops-ws', user=user, workspace=ws,
    defaults={'is_active': True}
)

result = {
    'workspace_slug': ws.slug,
    'workspace_id': str(ws.id),
    'project_openclaw_fleet_id': str(of_proj.id),
    'project_nnrt_id': str(nnrt_proj.id),
    'project_dspd_id': str(dspd_proj.id),
    'api_token': token.token,
}
print(json.dumps(result))
" 2>/dev/null)

WS_SLUG=$(echo "$OUTPUT"      | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['workspace_slug'])")
WS_ID=$(echo "$OUTPUT"        | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['workspace_id'])")
PROJ_OF=$(echo "$OUTPUT"      | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['project_openclaw_fleet_id'])")
PROJ_NNRT=$(echo "$OUTPUT"    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['project_nnrt_id'])")
PROJ_DSPD=$(echo "$OUTPUT"    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['project_dspd_id'])")
API_TOKEN=$(echo "$OUTPUT"    | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['api_token'])")

# ── Verify API access ────────────────────────────────────────────────────────

log "Verifying API access..."
PROJECTS=$(curl -sS -H "X-Api-Key: $API_TOKEN" "$PLANE_URL/api/v1/workspaces/$WS_SLUG/projects/" 2>/dev/null)
PROJECT_COUNT=$(echo "$PROJECTS" | python3 -c "import json,sys; d=json.load(sys.stdin); items=d.get('results',d); print(len(items))" 2>/dev/null || echo "0")
[ "$PROJECT_COUNT" -ge "3" ] || die "API verification failed — expected 3 projects, got $PROJECT_COUNT"
log "API verified: $PROJECT_COUNT projects accessible"

# ── Write config file ────────────────────────────────────────────────────────

cat > "$CONFIG_FILE" << EOF
# Plane configuration — auto-generated by plane-configure.sh
# WARNING: Contains secrets — gitignored, do not commit
PLANE_URL=$PLANE_URL
PLANE_WORKSPACE_SLUG=$WS_SLUG
PLANE_WORKSPACE_ID=$WS_ID
PLANE_PROJECT_OPENCLAW_FLEET_ID=$PROJ_OF
PLANE_PROJECT_NNRT_ID=$PROJ_NNRT
PLANE_PROJECT_DSPD_ID=$PROJ_DSPD
PLANE_API_TOKEN=$API_TOKEN
EOF

log "Config written to $CONFIG_FILE"
log ""
log "✅ Plane configured successfully:"
log "   Workspace:       $WS_SLUG ($WS_ID)"
log "   Project OF:      openclaw-fleet ($PROJ_OF)"
log "   Project NNRT:    nnrt ($PROJ_NNRT)"
log "   Project DSPD:    dspd ($PROJ_DSPD)"
log "   API Token:       ${API_TOKEN:0:24}..."
log "   Plane URL:       $PLANE_URL"
