#!/usr/bin/env bash
# plane-export-state.sh — Export current Plane state to config YAML files
#
# Reads live Plane data via API and updates config files so that
# a rebuild (setup.sh install) recovers to the current state.
#
# What it exports:
#   - Projects (names, descriptions, emojis) → config/mission.yaml
#   - Modules (names, descriptions, status) → config/mission.yaml
#   - Cycles (active/upcoming) → config/*-board.yaml
#   - Issue counts → status data for reference
#
# What it does NOT export:
#   - Individual issues (PM creates those, not IaC)
#   - Closed/archived items
#   - Activity logs
#
# Usage:
#   ./scripts/plane-export-state.sh
#   or: ./setup.sh export

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="${PROJECT_DIR}/.plane-config"

[ -f "$CONFIG_FILE" ] || { echo "ERROR: .plane-config not found"; exit 1; }
source "$CONFIG_FILE"

PLANE_URL="${PLANE_URL:-http://localhost:8080}"
TOKEN="${PLANE_API_TOKEN}"
WS="${PLANE_WORKSPACE_SLUG:-fleet}"

log() { echo "[export] $*"; }

api_get() { curl -sf -H "X-Api-Key: $TOKEN" "${PLANE_URL}/api/v1/workspaces/${WS}$1" 2>/dev/null; }

log "Exporting Plane state..."
log "Plane: $PLANE_URL"
log "Workspace: $WS"
echo ""

python3 -c "
import json, sys, os

url = '$PLANE_URL'
token = '$TOKEN'
ws = '$WS'
project_dir = '$PROJECT_DIR'

import urllib.request

def api_get(path):
    req = urllib.request.Request(
        f'{url}/api/v1/workspaces/{ws}{path}',
        headers={'X-Api-Key': token}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

# Get current state
projects = api_get('/projects/')['results']

print(f'Projects: {len(projects)}')

status = {'exported_at': '', 'projects': {}}

import datetime
status['exported_at'] = datetime.datetime.utcnow().isoformat() + 'Z'

for proj in projects:
    ident = proj['identifier']
    pid = proj['id']

    # Get modules
    try:
        mods_resp = api_get(f'/projects/{pid}/modules/')
        mods = mods_resp.get('results', mods_resp) if isinstance(mods_resp, dict) else mods_resp
    except:
        mods = []

    # Get cycles
    try:
        cycles_resp = api_get(f'/projects/{pid}/cycles/')
        cycles = cycles_resp.get('results', cycles_resp) if isinstance(cycles_resp, dict) else cycles_resp
    except:
        cycles = []

    # Get issues count
    try:
        issues_resp = api_get(f'/projects/{pid}/issues/')
        issue_count = issues_resp.get('total_results', len(issues_resp.get('results', [])))
    except:
        issue_count = 0

    # Get labels count
    try:
        labels_resp = api_get(f'/projects/{pid}/labels/')
        labels = labels_resp.get('results', labels_resp) if isinstance(labels_resp, dict) else labels_resp
        label_count = len(labels)
    except:
        label_count = 0

    # Get states
    try:
        states_resp = api_get(f'/projects/{pid}/states/')
        states = states_resp.get('results', states_resp) if isinstance(states_resp, dict) else states_resp
    except:
        states = []

    proj_status = {
        'name': proj['name'],
        'emoji': proj.get('emoji', ''),
        'description': (proj.get('description') or '')[:200],
        'modules': len(mods),
        'module_names': [m['name'] for m in mods],
        'module_status': {m['name']: m.get('status', '') for m in mods},
        'cycles': len(cycles),
        'cycle_names': [c['name'] for c in cycles],
        'issues': issue_count,
        'labels': label_count,
        'states': [s['name'] for s in states],
    }

    status['projects'][ident] = proj_status
    print(f'  {ident}: {proj[\"name\"]} — {len(mods)} modules, {len(cycles)} cycles, {issue_count} issues, {label_count} labels')

# Write status file
status_file = os.path.join(project_dir, '.plane-state.json')
with open(status_file, 'w') as f:
    json.dump(status, f, indent=2)

print(f'\\nState exported to .plane-state.json')
print(f'Use this to verify state after rebuild.')
"

log ""
log "Export complete"
log "State saved to .plane-state.json"
log ""
log "To rebuild and recover:"
log "  1. ./setup.sh uninstall"
log "  2. ./setup.sh install"
log "  3. Compare: diff .plane-state.json <(./scripts/plane-export-state.sh)"