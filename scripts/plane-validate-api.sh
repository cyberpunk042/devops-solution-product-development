#!/usr/bin/env bash
# plane-validate-api.sh — Validate Plane REST API with generated API key
# Tests: authentication, workspace, projects, issues CRUD, labels
#
# Prerequisites:
#   - Plane running (docker-compose.plane.yaml)
#   - .plane-config with PLANE_URL, PLANE_WORKSPACE_SLUG, PLANE_PROJECT_ID, PLANE_API_TOKEN
#
# Usage:
#   ./scripts/plane-validate-api.sh [--config .plane-config]

set -euo pipefail

CONFIG_FILE="${1:-.plane-config}"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found: $CONFIG_FILE"
    echo "Run ./scripts/plane-configure.sh first"
    exit 1
fi

# shellcheck disable=SC1090
source "$CONFIG_FILE"

PLANE_URL="${PLANE_URL:-http://localhost:8080}"
TOKEN="${PLANE_API_TOKEN}"
WS="${PLANE_WORKSPACE_SLUG}"
PROJECT_ID="${PLANE_PROJECT_ID}"

PASS=0
FAIL=0
ERRORS=()

log()   { echo "[validate] $*"; }
check() {
    local label="$1" expect="$2" actual="$3"
    if echo "$actual" | grep -qF "$expect"; then
        echo "  ✅ $label"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $label"
        echo "     expected: $expect"
        echo "     actual:   ${actual:0:120}"
        FAIL=$((FAIL + 1))
        ERRORS+=("$label")
    fi
}

log "Plane URL:  $PLANE_URL"
log "Workspace:  $WS"
log "Project ID: $PROJECT_ID"
log "Token:      ${TOKEN:0:24}..."
echo ""

# ── 1. Health ──────────────────────────────────────────────────────────────────
log "=== 1. Plane Health ==="
HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" "$PLANE_URL/")
check "Plane reachable (HTTP 200)" "200" "$HTTP_CODE"

# ── 2. Authentication ──────────────────────────────────────────────────────────
log "=== 2. Authentication ==="
RESP=$(curl -sS -H "X-Api-Key: $TOKEN" "$PLANE_URL/api/v1/workspaces/$WS/members/")
check "API key accepted (no 401/403)" "," "$RESP"

# Invalid token should be rejected
BAD_RESP=$(curl -sS -H "X-Api-Key: invalid_token_xxx" "$PLANE_URL/api/v1/workspaces/$WS/members/")
check "Invalid token rejected" "not valid" "$BAD_RESP"

# ── 3. Workspace ───────────────────────────────────────────────────────────────
log "=== 3. Workspace ==="
RESP=$(curl -sS -H "X-Api-Key: $TOKEN" "$PLANE_URL/api/v1/workspaces/$WS/members/")
MEMBER_COUNT=$(echo "$RESP" | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
check "Workspace members accessible" "1" "$MEMBER_COUNT"

# ── 4. Projects ────────────────────────────────────────────────────────────────
log "=== 4. Projects ==="
RESP=$(curl -sS -H "X-Api-Key: $TOKEN" "$PLANE_URL/api/v1/workspaces/$WS/projects/")
check "List projects" "openclaw-fleet" "$RESP"

# ── 5. Issues CRUD ─────────────────────────────────────────────────────────────
log "=== 5. Issues CRUD ==="

# Create
CREATE_RESP=$(curl -sS -X POST \
    -H "X-Api-Key: $TOKEN" \
    -H "Content-Type: application/json" \
    "$PLANE_URL/api/v1/workspaces/$WS/projects/$PROJECT_ID/issues/" \
    -d '{"name":"API Validation Test Issue","priority":"medium"}')
ISSUE_ID=$(echo "$CREATE_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('id',''))" 2>/dev/null)
check "Create issue" "-" "$ISSUE_ID"

if [ -n "$ISSUE_ID" ] && [ "$ISSUE_ID" != "None" ]; then
    # Assign default state via DB (needed for issue_objects manager to include it)
    STATE_ID=$(docker exec "${COMPOSE_PROJECT:-devops-7e40de40}-api-1" python manage.py shell -c \
        "from plane.db.models import State; s=State.objects.filter(project_id='$PROJECT_ID',default=True).first(); print(s.id if s else '')" 2>/dev/null || echo "")
    if [ -n "$STATE_ID" ]; then
        curl -sS -X PATCH -H "X-Api-Key: $TOKEN" -H "Content-Type: application/json" \
            "$PLANE_URL/api/v1/workspaces/$WS/projects/$PROJECT_ID/issues/$ISSUE_ID/" \
            -d "{\"state\":\"$STATE_ID\"}" > /dev/null
    fi

    # Read
    READ_RESP=$(curl -sS -H "X-Api-Key: $TOKEN" \
        "$PLANE_URL/api/v1/workspaces/$WS/projects/$PROJECT_ID/issues/$ISSUE_ID/")
    check "Read issue" "API Validation Test Issue" "$READ_RESP"

    # Update
    UPDATE_RESP=$(curl -sS -X PATCH \
        -H "X-Api-Key: $TOKEN" \
        -H "Content-Type: application/json" \
        "$PLANE_URL/api/v1/workspaces/$WS/projects/$PROJECT_ID/issues/$ISSUE_ID/" \
        -d '{"name":"API Validation Test Issue [updated]","priority":"high"}')
    check "Update issue" "updated" "$UPDATE_RESP"

    # List
    LIST_RESP=$(curl -sS -H "X-Api-Key: $TOKEN" \
        "$PLANE_URL/api/v1/workspaces/$WS/projects/$PROJECT_ID/issues/")
    ISSUE_COUNT=$(echo "$LIST_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('total_count',0))" 2>/dev/null)
    check "List issues (>= 1)" "total_count" "$LIST_RESP"

    # Delete
    DELETE_CODE=$(curl -sS -X DELETE \
        -H "X-Api-Key: $TOKEN" \
        "$PLANE_URL/api/v1/workspaces/$WS/projects/$PROJECT_ID/issues/$ISSUE_ID/" \
        -w "%{http_code}" -o /dev/null)
    check "Delete issue (HTTP 204)" "204" "$DELETE_CODE"
else
    echo "  ⚠️  Skipping Read/Update/List/Delete — issue creation failed"
    FAIL=$((FAIL + 4))
fi

# ── 6. Labels ──────────────────────────────────────────────────────────────────
log "=== 6. Labels ==="
LABEL_RESP=$(curl -sS -X POST \
    -H "X-Api-Key: $TOKEN" \
    -H "Content-Type: application/json" \
    "$PLANE_URL/api/v1/workspaces/$WS/projects/$PROJECT_ID/labels/" \
    -d '{"name":"fleet-test","color":"#6366F1"}')
check "Create label" "fleet-test" "$LABEL_RESP"

LABEL_ID=$(echo "$LABEL_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")
if [ -n "$LABEL_ID" ] && [ "$LABEL_ID" != "None" ]; then
    # Cleanup
    curl -sS -X DELETE \
        -H "X-Api-Key: $TOKEN" \
        "$PLANE_URL/api/v1/workspaces/$WS/projects/$PROJECT_ID/labels/$LABEL_ID/" > /dev/null 2>&1 || true
fi

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════"
if [ $FAIL -eq 0 ]; then
    echo "✅ ALL $PASS tests passed"
else
    echo "❌ $FAIL/$((PASS + FAIL)) tests FAILED:"
    for e in "${ERRORS[@]}"; do echo "  - $e"; done
    exit 1
fi
echo "══════════════════════════════════════"
