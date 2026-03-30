#!/usr/bin/env bash
# plane-backup.sh — Full Plane backup (DB dump + YAML export)
#
# Creates:
#   1. backups/plane-latest.sql — PostgreSQL dump (complete, git-diffable)
#   2. .plane-state.json — YAML-friendly state export (via plane_export.py)
#
# The SQL dump captures EVERYTHING (stickies, comments, preferences, activity).
# The YAML export captures structural data for IaC seeding.
# Both together = complete disaster recovery.
#
# Usage:
#   ./scripts/plane-backup.sh           # Creates backup
#   ./setup.sh backup                   # Same, via setup.sh
#
# Restore:
#   ./scripts/plane-restore.sh          # Restore from latest

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="${PROJECT_DIR}/backups"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-dspd-plane}"
DB_CONTAINER="${COMPOSE_PROJECT}-plane-db-1"

mkdir -p "$BACKUP_DIR"

echo "[backup] Starting Plane backup..."

# 1. PostgreSQL dump — plain SQL, git-diffable
DUMP_FILE="${BACKUP_DIR}/plane-latest.sql"
echo "[backup] Dumping PostgreSQL..."
docker exec -e PGPASSWORD=plane "$DB_CONTAINER" pg_dump -U plane -d plane \
    --clean --if-exists --no-owner --no-acl \
    --format=plain > "$DUMP_FILE"
SIZE=$(du -h "$DUMP_FILE" | cut -f1)
echo "[backup] Database: $DUMP_FILE ($SIZE)"

# 2. YAML export — structural data
echo "[backup] Exporting state..."
export PROJECT_DIR
export COMPOSE_PROJECT
python3 "$SCRIPT_DIR/plane_export.py" 2>&1 | sed 's/^/[backup] /'

# 3. Timestamped copy for history
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
cp "$DUMP_FILE" "${BACKUP_DIR}/plane-${TIMESTAMP}.sql"

# Retention: keep last 5 timestamped backups
cd "$BACKUP_DIR"
ls -t plane-20*.sql 2>/dev/null | tail -n +6 | xargs -r rm -f

echo "[backup] Done."
echo "[backup] Files:"
echo "  ${DUMP_FILE} (complete DB)"
echo "  ${PROJECT_DIR}/.plane-state.json (state export)"
echo "  ${BACKUP_DIR}/plane-${TIMESTAMP}.sql (timestamped copy)"