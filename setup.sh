#!/usr/bin/env bash
# setup.sh — DSPD infrastructure setup
# Deploys and configures Plane for the OpenClaw fleet.
#
# Usage:
#   ./setup.sh [command]
#
# Commands:
#   install   — First-time setup: generate secrets, start services, configure workspace
#   start     — Start Plane services
#   stop      — Stop Plane services
#   restart   — Restart Plane services
#   status    — Show service health
#   validate  — Run API validation suite
#   upgrade   — Pull latest images and restart
#   uninstall — Stop and remove all containers and volumes
#
# Environment:
#   PLANE_PORT      — HTTP port (default: 8080)
#   PLANE_URL       — Base URL (default: http://localhost:8080)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.plane.yaml"
ENV_FILE="${SCRIPT_DIR}/plane.env"
CONFIG_FILE="${SCRIPT_DIR}/.plane-config"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-dspd-plane}"

PLANE_PORT="${PLANE_PORT:-8080}"
PLANE_URL="${PLANE_URL:-http://localhost:${PLANE_PORT}}"

CMD="${1:-help}"

log()  { echo "[setup] $*"; }
die()  { echo "[setup] ERROR: $*" >&2; exit 1; }
bold() { echo ""; echo "══════════════════════════════════════════"; echo "  $*"; echo "══════════════════════════════════════════"; }

# ── Helpers ────────────────────────────────────────────────────────────────────

compose_cmd() {
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" --project-name "$COMPOSE_PROJECT" "$@"
}

wait_for_http() {
    local url="$1" timeout="${2:-120}" i=0
    log "Waiting for $url ..."
    while [ $i -lt $timeout ]; do
        if curl -sS -o /dev/null -w "%{http_code}" "$url" 2>/dev/null | grep -q "200"; then
            return 0
        fi
        sleep 3; i=$((i + 3))
    done
    die "Timeout waiting for $url"
}

wait_for_migrations() {
    local timeout=180 i=0
    log "Waiting for database migrations..."
    while [ $i -lt $timeout ]; do
        STATUS=$(docker inspect "${COMPOSE_PROJECT}-migrator-1" --format '{{.State.Status}}' 2>/dev/null || echo "not_found")
        EXIT=$(docker inspect "${COMPOSE_PROJECT}-migrator-1" --format '{{.State.ExitCode}}' 2>/dev/null || echo "1")
        if [ "$STATUS" = "exited" ] && [ "$EXIT" = "0" ]; then
            log "Migrations complete"
            return 0
        fi
        if [ "$STATUS" = "exited" ] && [ "$EXIT" != "0" ]; then
            die "Migrations failed (exit $EXIT) — run: docker logs ${COMPOSE_PROJECT}-migrator-1"
        fi
        sleep 5; i=$((i + 5))
    done
    die "Migrations timed out after ${timeout}s"
}

# ── Commands ───────────────────────────────────────────────────────────────────

cmd_install() {
    bold "Installing Plane"

    # Generate plane.env if not present
    if [ ! -f "$ENV_FILE" ]; then
        log "Generating plane.env from template..."
        cp "${SCRIPT_DIR}/plane.env.example" "$ENV_FILE"
        SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
        LIVE_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
        sed -i "s/changeme-replace-with-50-char-random-string/${SECRET_KEY}/" "$ENV_FILE"
        sed -i "s/changeme-live-secret/${LIVE_SECRET}/" "$ENV_FILE"
        # Set port
        sed -i "s/LISTEN_HTTP_PORT=8080/LISTEN_HTTP_PORT=${PLANE_PORT}/" "$ENV_FILE"
        sed -i "s|WEB_URL=http://localhost:8080|WEB_URL=${PLANE_URL}|" "$ENV_FILE"
        sed -i "s|CORS_ALLOWED_ORIGINS=http://localhost:8080|CORS_ALLOWED_ORIGINS=${PLANE_URL}|" "$ENV_FILE"
        log "plane.env generated with fresh secrets"
    else
        log "plane.env already exists — skipping generation"
    fi

    cmd_start

    log "Configuring workspace and project..."
    COMPOSE_PROJECT="$COMPOSE_PROJECT" API_CONTAINER="${COMPOSE_PROJECT}-api-1" \
        "${SCRIPT_DIR}/scripts/plane-configure.sh"

    bold "Plane installed successfully"
    log "  Web UI:  ${PLANE_URL}"
    log "  Admin:   ${PLANE_URL}/god-mode/"
    log "  API:     ${PLANE_URL}/api/v1/"
    log ""
    log "Next: source .plane-config to use PLANE_API_TOKEN, PLANE_WORKSPACE_SLUG, etc."
}

cmd_start() {
    bold "Starting Plane"
    [ -f "$ENV_FILE" ] || die "plane.env not found — run: ./setup.sh install"

    log "Pulling images..."
    compose_cmd pull --quiet

    log "Starting services..."
    compose_cmd up -d

    wait_for_migrations
    wait_for_http "${PLANE_URL}/"

    log "All services up — Plane is running on ${PLANE_URL}"
    cmd_status
}

cmd_stop() {
    bold "Stopping Plane"
    compose_cmd down
    log "Plane stopped"
}

cmd_restart() {
    bold "Restarting Plane"
    compose_cmd restart
    wait_for_http "${PLANE_URL}/"
    log "Plane restarted"
}

cmd_status() {
    bold "Plane Status"
    compose_cmd ps --format "table {{.Name}}\t{{.Status}}"
    echo ""
    HTTP=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 5 "${PLANE_URL}/" 2>/dev/null || echo "000")
    if [ "$HTTP" = "200" ]; then
        log "✅ Web UI reachable: ${PLANE_URL} (HTTP 200)"
    else
        log "❌ Web UI not reachable (HTTP $HTTP)"
    fi
}

cmd_validate() {
    bold "Validating Plane API"
    [ -f "$CONFIG_FILE" ] || die ".plane-config not found — run: ./setup.sh install"
    COMPOSE_PROJECT="$COMPOSE_PROJECT" "${SCRIPT_DIR}/scripts/plane-validate-api.sh" "$CONFIG_FILE"
}

cmd_upgrade() {
    bold "Upgrading Plane"
    log "Pulling latest images..."
    compose_cmd pull
    log "Restarting services..."
    compose_cmd up -d
    wait_for_migrations
    log "Upgrade complete"
}

cmd_uninstall() {
    bold "Uninstalling Plane"
    read -rp "This will DELETE all Plane data. Type 'yes' to confirm: " CONFIRM
    [ "$CONFIRM" = "yes" ] || die "Aborted"
    compose_cmd down -v
    log "Plane uninstalled — all volumes removed"
}

cmd_help() {
    echo "Usage: ./setup.sh [command]"
    echo ""
    echo "Commands:"
    echo "  install    First-time setup (generate secrets, start, configure)"
    echo "  start      Start Plane services"
    echo "  stop       Stop Plane services"
    echo "  restart    Restart Plane services"
    echo "  status     Show service health"
    echo "  validate   Run API validation (requires .plane-config)"
    echo "  upgrade    Pull latest images and restart"
    echo "  uninstall  Remove all containers and volumes"
}

# ── Dispatch ───────────────────────────────────────────────────────────────────

case "$CMD" in
    install)   cmd_install ;;
    start)     cmd_start ;;
    stop)      cmd_stop ;;
    restart)   cmd_restart ;;
    status)    cmd_status ;;
    validate)  cmd_validate ;;
    upgrade)   cmd_upgrade ;;
    uninstall) cmd_uninstall ;;
    help|--help|-h) cmd_help ;;
    *) die "Unknown command: $CMD — run ./setup.sh help" ;;
esac
