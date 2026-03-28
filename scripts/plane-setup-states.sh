#!/usr/bin/env bash
# plane-setup-states.sh — Configure Plane workflow states to match OCMC lifecycle
#
# State mapping:
#   Backlog     → (unplanned)    gray    #9CA3AF
#   Todo        → inbox          blue    #3B82F6  (default)
#   In Progress → in_progress    yellow  #F59E0B
#   In Review   → review         purple  #A855F7
#   Done        → done           green   #22C55E
#   Cancelled   → (abandoned)    red     #EF4444
#
# Applied to: all projects in the fleet workspace (OF, NNRT, DSPD, AICP)
# Idempotent: safe to re-run.
#
# Usage:
#   COMPOSE_PROJECT=dspd-plane ./scripts/plane-setup-states.sh

set -euo pipefail

PLANE_URL="${PLANE_URL:-http://localhost:8080}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-dspd-plane}"
API_CONTAINER="${API_CONTAINER:-${COMPOSE_PROJECT}-api-1}"
PLANE_ADMIN_EMAIL="${PLANE_ADMIN_EMAIL:-admin@fleet.local}"

log() { echo "[plane-setup-states] $*"; }
die() { echo "[plane-setup-states] ERROR: $*" >&2; exit 1; }

HTTP=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 "$PLANE_URL/")
[ "$HTTP" = "200" ] || die "Plane not reachable (HTTP $HTTP)"

docker exec "$API_CONTAINER" python manage.py shell -c "
from plane.db.models import User, Workspace, Project, State

user = User.objects.get(email='${PLANE_ADMIN_EMAIL}')
ws = Workspace.objects.get(slug='fleet')

target_states = [
    {'name': 'Backlog',     'group': 'backlog',    'color': '#9CA3AF', 'default': False, 'sequence': 15000},
    {'name': 'Todo',        'group': 'unstarted',  'color': '#3B82F6', 'default': True,  'sequence': 25000},
    {'name': 'In Progress', 'group': 'started',    'color': '#F59E0B', 'default': False, 'sequence': 35000},
    {'name': 'In Review',   'group': 'started',    'color': '#A855F7', 'default': False, 'sequence': 40000},
    {'name': 'Done',        'group': 'completed',  'color': '#22C55E', 'default': False, 'sequence': 45000},
    {'name': 'Cancelled',   'group': 'cancelled',  'color': '#EF4444', 'default': False, 'sequence': 55000},
]

for proj in Project.objects.filter(workspace=ws):
    for s_data in target_states:
        state, created = State.objects.get_or_create(
            name=s_data['name'], project=proj,
            defaults={'workspace': ws, 'group': s_data['group'], 'color': s_data['color'],
                      'default': s_data['default'], 'sequence': s_data['sequence'],
                      'created_by': user, 'updated_by': user}
        )
        if not created:
            state.group = s_data['group']
            state.color = s_data['color']
            state.default = s_data['default']
            state.sequence = s_data['sequence']
            state.save(update_fields=['group','color','default','sequence'])

    # Ensure single default
    defaults = State.objects.filter(project=proj, default=True)
    if defaults.count() > 1:
        defaults.exclude(pk=defaults.first().pk).update(default=False)

    names = list(State.objects.filter(project=proj).order_by('sequence').values_list('name', flat=True))
    print(f'  {proj.identifier}: {names}')

print('States configured')
" 2>/dev/null && log "States configured for all projects" || die "State setup failed"

log ""
log "✅ OCMC lifecycle states applied:"
log "   Backlog     → (unplanned)   #9CA3AF gray"
log "   Todo        → inbox         #3B82F6 blue   [default]"
log "   In Progress → in_progress   #F59E0B yellow"
log "   In Review   → review        #A855F7 purple"
log "   Done        → done          #22C55E green"
log "   Cancelled   → (abandoned)   #EF4444 red"
