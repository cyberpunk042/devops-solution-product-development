#!/usr/bin/env bash
# plane-setup-projects.sh — Create Plane projects with modules and settings
# Creates: FLEET (OF), NNRT, DSPD, AICP — each with states, modules, views enabled
#
# Usage:
#   COMPOSE_PROJECT=dspd-plane ./scripts/plane-setup-projects.sh
#
# Idempotent: safe to re-run.

set -euo pipefail

PLANE_URL="${PLANE_URL:-http://localhost:8080}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-dspd-plane}"
API_CONTAINER="${API_CONTAINER:-${COMPOSE_PROJECT}-api-1}"
PLANE_ADMIN_EMAIL="${PLANE_ADMIN_EMAIL:-admin@fleet.local}"

log() { echo "[plane-setup-projects] $*"; }
die() { echo "[plane-setup-projects] ERROR: $*" >&2; exit 1; }

log "Plane URL: $PLANE_URL"
log "API container: $API_CONTAINER"

# Pre-flight
HTTP=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 "$PLANE_URL/")
[ "$HTTP" = "200" ] || die "Plane not reachable (HTTP $HTTP)"

docker exec "$API_CONTAINER" python manage.py shell -c "
from plane.db.models import User, Workspace, Project, ProjectMember, State, Module

user = User.objects.get(email='${PLANE_ADMIN_EMAIL}')
ws = Workspace.objects.get(slug='fleet')

default_states = [
    {'name': 'Backlog',     'group': 'backlog',    'color': '#A3A3A3', 'default': False, 'sequence': 15000},
    {'name': 'Todo',        'group': 'unstarted',  'color': '#3A3A3A', 'default': True,  'sequence': 25000},
    {'name': 'In Progress', 'group': 'started',    'color': '#F59E0B', 'default': False, 'sequence': 35000},
    {'name': 'Done',        'group': 'completed',  'color': '#22C55E', 'default': False, 'sequence': 45000},
    {'name': 'Cancelled',   'group': 'cancelled',  'color': '#EF4444', 'default': False, 'sequence': 55000},
]

projects_config = {
    'OF':   ('openclaw-fleet', 'Fleet operations, MCP tools, orchestrator, agents. GitHub: cyberpunk042/openclaw-fleet',
             ['Core', 'Infrastructure', 'MCP', 'CLI', 'Agents', 'Tests']),
    'NNRT': ('nnrt', 'Narrative-to-Neutral Report Transformer. GitHub: cyberpunk042/Narrative-to-Neutral-Report-Transformer',
             ['Intake', 'Structuring', 'Mapping', 'Pressure', 'Persistence']),
    'DSPD': ('dspd', 'DevOps Solution Product Development. GitHub: cyberpunk042/devops-solution-product-development',
             ['Setup', 'Integration', 'Sync', 'Customization']),
    'AICP': ('aicp', 'AI Control Platform. Personal AI control workspace. GitHub: cyberpunk042/devops-expert-local-ai',
             ['Core', 'Integrations', 'Plugins']),
}

for identifier, (name, desc, modules) in projects_config.items():
    proj, created = Project.objects.get_or_create(
        identifier=identifier, workspace=ws,
        defaults={
            'name': name, 'description': desc, 'network': 2,
            'created_by': user, 'updated_by': user,
            'module_view': True, 'cycle_view': True, 'issue_views_view': True, 'page_view': True,
        }
    )
    if not created:
        proj.description = desc
        proj.module_view = True; proj.cycle_view = True; proj.page_view = True
        proj.save(update_fields=['description','module_view','cycle_view','page_view'])

    ProjectMember.objects.get_or_create(project=proj, member=user, defaults={'role': 20, 'is_active': True})

    for s_data in default_states:
        State.objects.get_or_create(
            name=s_data['name'], project=proj,
            defaults={'workspace': ws, 'group': s_data['group'], 'color': s_data['color'],
                      'default': s_data['default'], 'sequence': s_data['sequence'],
                      'created_by': user, 'updated_by': user}
        )

    for mod_name in modules:
        Module.objects.get_or_create(
            name=mod_name, project=proj,
            defaults={'workspace': ws, 'created_by': user, 'updated_by': user}
        )

    mod_count = Module.objects.filter(project=proj).count()
    print(f'  {identifier}: {proj.name} — {mod_count} modules, views enabled (created={created})')

print('Done')
" 2>/dev/null && log "Projects configured" || die "Project setup failed"

log ""
log "✅ Projects configured:"
log "   OF   — openclaw-fleet (modules: Core, Infrastructure, MCP, CLI, Agents, Tests)"
log "   NNRT — nnrt (modules: Intake, Structuring, Mapping, Pressure, Persistence)"
log "   DSPD — dspd (modules: Setup, Integration, Sync, Customization)"
log "   AICP — aicp (modules: Core, Integrations, Plugins)"
