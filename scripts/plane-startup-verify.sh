#!/usr/bin/env bash
# plane-startup-verify.sh — Verify Plane Docker stack startup health
# Checks: containers up, migrations complete, HTTP 200, API responsive
#
# Usage:
#   ./scripts/plane-startup-verify.sh [compose-project-name]
#   COMPOSE_PROJECT=devops-7e40de40 ./scripts/plane-startup-verify.sh

set -euo pipefail

COMPOSE_PROJECT="${COMPOSE_PROJECT:-devops-7e40de40}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.plane.yaml}"
ENV_FILE="${ENV_FILE:-plane.env}"
PLANE_URL="${PLANE_URL:-http://localhost:8080}"
TIMEOUT="${TIMEOUT:-120}"

PASS=0; FAIL=0; ERRORS=()

check() {
    local label="$1" expect="$2" actual="$3"
    if echo "$actual" | grep -qF "$expect"; then
        echo "  ✅ $label"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $label (got: ${actual:0:80})"
        FAIL=$((FAIL + 1))
        ERRORS+=("$label")
    fi
}

log() { echo "[plane-verify] $*"; }

log "Compose project: $COMPOSE_PROJECT"
log "Plane URL:       $PLANE_URL"
echo ""

# ── 1. Required containers running ────────────────────────────────────────────
log "=== 1. Container Health ==="
REQUIRED=(proxy web admin api worker beat-worker plane-db plane-redis plane-mq plane-minio)
for svc in "${REQUIRED[@]}"; do
    CTR="${COMPOSE_PROJECT}-${svc}-1"
    STATUS=$(docker inspect "$CTR" --format '{{.State.Status}}' 2>/dev/null || echo "missing")
    check "Container: $svc" "running" "$STATUS"
done

# Migrator should have exited 0
MIGRATOR_STATUS=$(docker inspect "${COMPOSE_PROJECT}-migrator-1" --format '{{.State.Status}} exit:{{.State.ExitCode}}' 2>/dev/null || echo "missing")
check "Migrator exited cleanly" "exit:0" "$MIGRATOR_STATUS"

# ── 2. Migrations complete ─────────────────────────────────────────────────────
log "=== 2. Migrations ==="
MIGRATOR_EXIT=$(docker inspect "${COMPOSE_PROJECT}-migrator-1" --format '{{.State.ExitCode}}' 2>/dev/null || echo "1")
check "DB migrations complete (exit 0)" "0" "$MIGRATOR_EXIT"

# ── 3. HTTP reachable ─────────────────────────────────────────────────────────
log "=== 3. HTTP ==="
HTTP_CODE=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 "$PLANE_URL/" 2>/dev/null || echo "000")
check "Plane web (HTTP 200)" "200" "$HTTP_CODE"

ADMIN_CODE=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 "$PLANE_URL/god-mode/" 2>/dev/null || echo "000")
check "Admin panel reachable" "200" "$ADMIN_CODE"

# ── 4. API responsive ────────────────────────────────────────────────────────
log "=== 4. API ==="
API_RESP=$(curl -sS --max-time 10 \
    "$PLANE_URL/api/v1/workspaces/fleet/members/" \
    -H "X-Api-Key: ${PLANE_API_TOKEN:-}" 2>/dev/null || echo "error")
# 401 is fine here (means API is up) — we just need a JSON response
if echo "$API_RESP" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
    echo "  ✅ API returns JSON"
    PASS=$((PASS + 1))
else
    echo "  ❌ API not returning JSON (got: ${API_RESP:0:80})"
    FAIL=$((FAIL + 1))
    ERRORS+=("API returns JSON")
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "══════════════════════════════════════"
if [ $FAIL -eq 0 ]; then
    echo "✅ ALL $PASS checks passed — Plane is healthy"
    echo ""
    echo "  Web UI:  $PLANE_URL"
    echo "  Admin:   $PLANE_URL/god-mode/"
    echo "  API:     $PLANE_URL/api/v1/"
else
    echo "❌ $FAIL/$((PASS + FAIL)) checks FAILED:"
    for e in "${ERRORS[@]}"; do echo "  - $e"; done
    exit 1
fi
echo "══════════════════════════════════════"
