#!/usr/bin/env bash
# plane-restore.sh — Restore Plane from backup
#
# Restores the PostgreSQL database from a SQL dump.
# Then restarts all services so caches rebuild.
#
# Usage:
#   ./scripts/plane-restore.sh                              # From latest
#   ./scripts/plane-restore.sh backups/plane-20260329.sql   # Specific backup
#   ./setup.sh restore                                      # Via setup.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${PROJECT_DIR}/backups"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-dspd-plane}"
DB_CONTAINER="${COMPOSE_PROJECT}-plane-db-1"
COMPOSE_FILE="${PROJECT_DIR}/docker-compose.plane.yaml"
ENV_FILE="${PROJECT_DIR}/plane.env"

BACKUP_FILE="${1:-${BACKUP_DIR}/plane-latest.sql}"

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "ERROR: Backup not found: $BACKUP_FILE"
    echo "Available:"
    ls -lh "${BACKUP_DIR}"/plane-*.sql 2>/dev/null || echo "  (none)"
    exit 1
fi

SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[restore] Backup: $BACKUP_FILE ($SIZE)"
echo ""
echo "WARNING: This REPLACES all current Plane data."
read -rp "Type 'restore' to confirm: " CONFIRM
[[ "$CONFIRM" == "restore" ]] || { echo "Aborted."; exit 1; }

# Stop app services (keep DB + Redis running)
echo "[restore] Stopping Plane app services..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" \
    --project-name "$COMPOSE_PROJECT" \
    stop api worker beat-worker web space admin live proxy migrator 2>/dev/null || true

# Restore database
echo "[restore] Restoring database..."
docker exec -i "$DB_CONTAINER" psql -U plane -d plane --quiet < "$BACKUP_FILE" 2>/dev/null

# Restart ALL services (so Redis cache, API memory, etc. rebuild from DB)
echo "[restore] Restarting all services..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" \
    --project-name "$COMPOSE_PROJECT" \
    up -d 2>/dev/null

# Wait for Plane
echo "[restore] Waiting for Plane..."
for i in $(seq 1 30); do
    curl -sf http://localhost:8080/ >/dev/null 2>&1 && break
    sleep 3
done

echo "[restore] Done. Verify: http://localhost:8080"
echo "[restore] All data including stickies, comments, preferences restored."