#!/usr/bin/env bash
# plane-setup-labels.sh — Create standard labels across all Plane projects
# Reads labels from config/mission.yaml and applies to every project.
# Idempotent: safe to re-run.
#
# Usage:
#   COMPOSE_PROJECT=dspd-plane ./scripts/plane-setup-labels.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MISSION_FILE="${MISSION_FILE:-${PROJECT_DIR}/config/mission.yaml}"

PLANE_URL="${PLANE_URL:-http://localhost:8080}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-dspd-plane}"
API_CONTAINER="${API_CONTAINER:-${COMPOSE_PROJECT}-api-1}"
PLANE_ADMIN_EMAIL="${PLANE_ADMIN_EMAIL:-admin@fleet.local}"

log() { echo "[plane-setup-labels] $*"; }
die() { echo "[plane-setup-labels] ERROR: $*" >&2; exit 1; }

[ -f "$MISSION_FILE" ] || die "Mission file not found: $MISSION_FILE"

cat "$MISSION_FILE" | docker exec -i "$API_CONTAINER" python manage.py shell -c "
import sys, yaml
from plane.db.models import User, Workspace, Project, Label

config = yaml.safe_load(sys.stdin.read())
user = User.objects.get(email='${PLANE_ADMIN_EMAIL}')
ws = Workspace.objects.get(slug=config['workspace']['slug'])
labels_cfg = config.get('labels', [])

created = 0
skipped = 0

for proj in Project.objects.filter(workspace=ws):
    for lbl_cfg in labels_cfg:
        _, was_created = Label.objects.get_or_create(
            name=lbl_cfg['name'], project=proj,
            defaults={
                'workspace': ws,
                'color': lbl_cfg['color'],
                'description': lbl_cfg.get('description', ''),
                'created_by': user,
                'updated_by': user,
            }
        )
        if was_created:
            created += 1
        else:
            skipped += 1

    count = Label.objects.filter(project=proj).count()
    print(f'  {proj.identifier}: {count} labels')

print(f'\\nLabels: {created} created, {skipped} already existed')
" 2>&1

log "Done"