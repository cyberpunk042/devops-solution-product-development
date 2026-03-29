#!/usr/bin/env bash
# plane-seed-mission.sh — Seed Plane via REST API from config/mission.yaml
#
# Uses the Plane v1 REST API exclusively (no Django ORM, no docker exec).
# This ensures the UI sees all changes immediately — no cache issues.
#
# Reads:
#   - config/mission.yaml — workspace, projects, modules, labels, states
#   - config/*-board.yaml — per-project cycles, epic details
#   - .plane-config — API credentials (from plane-configure.sh)
#
# Does NOT create individual tasks/issues.
# The project-manager agent breaks epics into tasks.
#
# Idempotent: checks before creating, updates existing.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MISSION_FILE="${MISSION_FILE:-${PROJECT_DIR}/config/mission.yaml}"
CONFIG_FILE="${PROJECT_DIR}/.plane-config"

[ -f "$CONFIG_FILE" ] || { echo "ERROR: .plane-config not found. Run plane-configure.sh first."; exit 1; }
[ -f "$MISSION_FILE" ] || { echo "ERROR: config/mission.yaml not found."; exit 1; }

source "$CONFIG_FILE"

PLANE_URL="${PLANE_URL:-http://localhost:8080}"
TOKEN="${PLANE_API_TOKEN}"
WS="${PLANE_WORKSPACE_SLUG:-fleet}"

log() { echo "[seed] $*"; }
die() { echo "[seed] ERROR: $*" >&2; exit 1; }

# ── API helper ──
api_get() { curl -sf -H "X-Api-Key: $TOKEN" "${PLANE_URL}/api/v1/workspaces/${WS}$1" 2>/dev/null; }
api_post() { curl -sf -X POST -H "X-Api-Key: $TOKEN" -H "Content-Type: application/json" "${PLANE_URL}/api/v1/workspaces/${WS}$1" -d "$2" 2>/dev/null; }
api_patch() { curl -sf -X PATCH -H "X-Api-Key: $TOKEN" -H "Content-Type: application/json" "${PLANE_URL}/api/v1/workspaces/${WS}$1" -d "$2" 2>/dev/null; }

# ── Pre-flight ──
HTTP=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 "$PLANE_URL/" 2>/dev/null || echo "000")
[ "$HTTP" = "200" ] || die "Plane not reachable (HTTP $HTTP)"

log "Plane: $PLANE_URL"
log "Workspace: $WS"
log "Mission: $MISSION_FILE"
echo ""

# ── Parse config ──
PARSED=$(python3 -c "
import yaml, json
with open('$MISSION_FILE') as f:
    config = yaml.safe_load(f)
json.dump(config, __import__('sys').stdout)
")

# ── Get existing projects ──
PROJECTS_RAW=$(api_get "/projects/")

# ── Process each project ──
echo "$PARSED" | python3 -c "
import json, sys, subprocess, os

config = json.load(sys.stdin)
ws = '$WS'
url = '$PLANE_URL'
token = '$TOKEN'
project_dir = '$PROJECT_DIR'

def api_get(path):
    import urllib.request
    req = urllib.request.Request(
        f'{url}/api/v1/workspaces/{ws}{path}',
        headers={'X-Api-Key': token}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return None

def api_post(path, data):
    import urllib.request
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f'{url}/api/v1/workspaces/{ws}{path}',
        data=body,
        headers={'X-Api-Key': token, 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {'error': str(e)}

def api_patch(path, data):
    import urllib.request
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f'{url}/api/v1/workspaces/{ws}{path}',
        data=body,
        headers={'X-Api-Key': token, 'Content-Type': 'application/json'},
        method='PATCH',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {'error': str(e)}

# Get existing projects
projects_resp = api_get('/projects/')
if not projects_resp:
    print('ERROR: Cannot list projects')
    sys.exit(1)

existing = {p['identifier']: p for p in projects_resp.get('results', [])}

for proj_cfg in config.get('projects', []):
    ident = proj_cfg['identifier']
    name = proj_cfg['name']
    emoji = proj_cfg.get('emoji', '')
    desc = proj_cfg.get('description', '').strip()

    if ident not in existing:
        # Create project via REST API (triggers internal init hooks)
        import time
        create_data = {
            'name': name,
            'identifier': ident,
            'description': desc,
            'network': proj_cfg.get('network', 2),
        }
        if emoji:
            create_data['emoji'] = emoji
        views = proj_cfg.get('views', {})
        create_data['module_view'] = views.get('modules', True)
        create_data['cycle_view'] = views.get('cycles', True)
        create_data['issue_views_view'] = views.get('issue_views', True)
        create_data['page_view'] = views.get('pages', True)

        result = api_post('/projects/', create_data)
        if result and 'id' in result:
            pid = result['id']
            existing[ident] = result
            print(f'=== {ident} — {name} (CREATED via API) ===')
            time.sleep(1)  # Rate limit protection
        else:
            print(f'  ERROR creating {ident}: {result}')
            continue
    else:
        pid = existing[ident]['id']
    print(f'=== {ident} — {name} ===')

    # ── Update project ──
    patch = {'name': name, 'description': desc}
    if emoji:
        patch['emoji'] = emoji
    cover = proj_cfg.get('cover_image', '')
    if cover:
        patch['cover_image'] = cover
    logo = proj_cfg.get('logo_props', {})
    if logo:
        patch['logo_props'] = logo
    views = proj_cfg.get('views', {})
    patch['module_view'] = views.get('modules', True)
    patch['cycle_view'] = views.get('cycles', True)
    patch['issue_views_view'] = views.get('issue_views', True)
    patch['page_view'] = views.get('pages', True)

    result = api_patch(f'/projects/{pid}/', patch)
    if result and 'error' not in result:
        print(f'  Project: {result.get(\"name\",\"?\")} {result.get(\"emoji\",\"\")}')
    else:
        print(f'  Project: PATCH failed — {result}')

    # ── States ──
    states_cfg = proj_cfg.get('states', [])
    if states_cfg:
        existing_states = api_get(f'/projects/{pid}/states/')
        state_names = set()
        if existing_states:
            items = existing_states.get('results', existing_states) if isinstance(existing_states, dict) else existing_states
            state_names = {s['name'] for s in items}

        for s_data in states_cfg:
            if s_data['name'] not in state_names:
                payload = {
                    'name': s_data['name'],
                    'group': s_data['group'],
                    'color': s_data['color'],
                }
                if s_data.get('default'):
                    payload['default'] = True
                api_post(f'/projects/{pid}/states/', payload)
        print(f'  States: {len(states_cfg)} configured')

    # ── Labels ──
    labels_cfg = config.get('labels', [])
    existing_labels = api_get(f'/projects/{pid}/labels/')
    label_names = set()
    if existing_labels:
        items = existing_labels.get('results', existing_labels) if isinstance(existing_labels, dict) else existing_labels
        label_names = {l['name'] for l in items}

    created_labels = 0
    for lbl in labels_cfg:
        if lbl['name'] not in label_names:
            api_post(f'/projects/{pid}/labels/', {
                'name': lbl['name'],
                'color': lbl['color'],
            })
            created_labels += 1
    print(f'  Labels: {created_labels} created, {len(label_names)} existing')

    # ── Modules (epics) ──
    modules_cfg = proj_cfg.get('modules', [])
    existing_mods = api_get(f'/projects/{pid}/modules/')
    mod_names = {}
    if existing_mods:
        items = existing_mods.get('results', existing_mods) if isinstance(existing_mods, dict) else existing_mods
        mod_names = {m['name']: m['id'] for m in items}

    for mod_cfg in modules_cfg:
        mod_name = mod_cfg['name']
        mod_desc = mod_cfg.get('description', '').strip()
        mod_status = mod_cfg.get('status', '')

        if mod_name in mod_names:
            # Update description and status
            patch_data = {}
            if mod_desc:
                patch_data['description'] = mod_desc
            if mod_status:
                patch_data['status'] = mod_status
            if patch_data:
                api_patch(f'/projects/{pid}/modules/{mod_names[mod_name]}/', patch_data)
            print(f'  Module: {mod_name} (updated)')
        else:
            payload = {'name': mod_name}
            if mod_desc:
                payload['description'] = mod_desc
            if mod_status:
                payload['status'] = mod_status
            result = api_post(f'/projects/{pid}/modules/', payload)
            if result and 'id' in result:
                mod_names[mod_name] = result['id']
            print(f'  Module: {mod_name} (created)')

    # ── Cycles (from board config) ──
    board_file = os.path.join(project_dir, 'config', f'{ident.lower()}-board.yaml')
    if os.path.exists(board_file):
        import yaml
        with open(board_file) as f:
            board = yaml.safe_load(f)

        existing_cycles = api_get(f'/projects/{pid}/cycles/')
        cycle_names = set()
        if existing_cycles:
            items = existing_cycles.get('results', existing_cycles) if isinstance(existing_cycles, dict) else existing_cycles
            cycle_names = {c['name'] for c in items}

        from datetime import date, timedelta
        today = date.today()

        for cyc_cfg in board.get('cycles', []):
            cyc_name = cyc_cfg['name']
            if cyc_name in cycle_names:
                print(f'  Cycle: {cyc_name} (exists)')
            else:
                duration = cyc_cfg.get('duration_days', 14)
                cyc_desc = cyc_cfg.get('description', '').strip()[:500]
                goals = cyc_cfg.get('goals', [])
                if goals:
                    cyc_desc += '\\n\\nGoals:\\n' + '\\n'.join(f'- {g}' for g in goals)

                start = today.isoformat()
                end = (today + timedelta(days=duration)).isoformat()

                result = api_post(f'/projects/{pid}/cycles/', {
                    'name': cyc_name,
                    'description': cyc_desc,
                    'start_date': start,
                    'end_date': end,
                    'project_id': pid,
                })
                if result and 'id' in result:
                    print(f'  Cycle: {cyc_name} ({start} → {end})')
                else:
                    print(f'  Cycle: {cyc_name} FAILED — {result}')

        # ── Epic details (update module descriptions with acceptance criteria) ──
        for epic_name, details in board.get('epic_details', {}).items():
            if epic_name in mod_names:
                mid = mod_names[epic_name]
                notes = details.get('notes', '').strip()
                ac = details.get('acceptance_criteria', [])
                deps = details.get('dependencies', [])

                # Build rich description
                existing_mod = api_get(f'/projects/{pid}/modules/{mid}/')
                base_desc = ''
                if existing_mod:
                    base_desc = existing_mod.get('description', '') or ''

                parts = [base_desc] if base_desc and 'Acceptance Criteria' not in base_desc else []
                if not parts:
                    # Use the module description from mission.yaml
                    for mc in modules_cfg:
                        if mc['name'] == epic_name:
                            parts = [mc.get('description', '').strip()]
                            break
                if ac:
                    parts.append('\\nAcceptance Criteria:\\n' + '\\n'.join(f'- {c}' for c in ac))
                if deps:
                    parts.append('\\nDependencies:\\n' + '\\n'.join(f'- {d}' for d in deps))
                if notes:
                    parts.append('\\nNotes:\\n' + notes)

                full_desc = '\\n'.join(parts).strip()
                api_patch(f'/projects/{pid}/modules/{mid}/', {'description': full_desc})

    print()

print('=== Mission seeded via REST API ===')
"

log ""
log "Done"