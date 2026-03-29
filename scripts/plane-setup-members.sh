#!/usr/bin/env bash
# plane-setup-members.sh — Create agent bot accounts, issue types, and saved views
#
# Reads config/fleet-members.yaml and creates:
#   - Bot user accounts for each agent (is_bot=True)
#   - Fleet service account for sync
#   - Workspace + project memberships
#   - Issue types (Epic/Story/Task/Bug/Spike/Chore)
#   - Saved views per project
#
# Idempotent: checks before creating.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MEMBERS_FILE="${PROJECT_DIR}/config/fleet-members.yaml"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-dspd-plane}"
API_CONTAINER="${API_CONTAINER:-${COMPOSE_PROJECT}-api-1}"
PLANE_ADMIN_EMAIL="${PLANE_ADMIN_EMAIL:-admin@fleet.local}"

log() { echo "[setup-members] $*"; }
die() { echo "[setup-members] ERROR: $*" >&2; exit 1; }

[ -f "$MEMBERS_FILE" ] || die "Config not found: $MEMBERS_FILE"

log "Config: $MEMBERS_FILE"

cat "$MEMBERS_FILE" | docker exec -i "$API_CONTAINER" python manage.py shell -c "
import sys, yaml, json
from plane.db.models import (
    User, Workspace, WorkspaceMember, Project, ProjectMember,
    IssueView,
)
from plane.db.models.issue_type import IssueType, ProjectIssueType

config = yaml.safe_load(sys.stdin.read())
admin = User.objects.get(email='${PLANE_ADMIN_EMAIL}')
ws = Workspace.objects.get(slug='fleet')
prefix = config.get('fleet_prefix', '0000')

def create_bot_user(email, display_name, workspace_role, project_roles):
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            'username': email.split('@')[0],
            'first_name': display_name.split('[')[0].strip(),
            'last_name': f'[{prefix}]',
            'display_name': display_name,
            'is_bot': True,
            'is_active': True,
            'is_password_autoset': True,
        }
    )
    if not created:
        user.display_name = display_name
        user.is_bot = True
        user.save(update_fields=['display_name', 'is_bot'])

    # Workspace membership
    WorkspaceMember.objects.get_or_create(
        workspace=ws, member=user,
        defaults={'role': workspace_role}
    )

    # Project memberships
    for ident, role in project_roles.items():
        proj = Project.objects.filter(identifier=ident, workspace=ws).first()
        if proj:
            ProjectMember.objects.get_or_create(
                project=proj, member=user,
                defaults={'role': role, 'is_active': True}
            )

    tag = 'CREATED' if created else 'EXISTS'
    return user, tag

# ── Service account ──
svc = config.get('service_account', {})
if svc:
    user, tag = create_bot_user(
        svc['email'],
        svc['display_name'],
        svc.get('workspace_role', 20),
        {},
    )
    print(f'Service: {svc[\"display_name\"]} ({tag})')

# ── Agent accounts ──
agents_created = 0
agents_existing = 0
for agent in config.get('agents', []):
    display = agent['display_name_template'].replace('{prefix}', prefix)
    user, tag = create_bot_user(
        agent['email'],
        display,
        agent.get('workspace_role', 10),
        agent.get('project_roles', {}),
    )
    if tag == 'CREATED':
        agents_created += 1
    else:
        agents_existing += 1
    print(f'  Agent: {display} ({tag})')

print(f'\\nAgents: {agents_created} created, {agents_existing} existing')

# ── Issue Types ──
print('\\n=== Issue Types ===')
types_created = 0
for it_cfg in config.get('issue_types', []):
    it, created = IssueType.objects.get_or_create(
        name=it_cfg['name'], workspace=ws,
        defaults={
            'description': it_cfg.get('description', ''),
            'is_epic': it_cfg.get('is_epic', False),
            'is_default': it_cfg.get('is_default', False),
            'is_active': True,
            'level': it_cfg.get('level', 2),
            'logo_props': it_cfg.get('logo_props', {}),
            'created_by': admin,
            'updated_by': admin,
        }
    )
    if not created:
        it.description = it_cfg.get('description', it.description)
        it.is_epic = it_cfg.get('is_epic', it.is_epic)
        it.level = it_cfg.get('level', it.level)
        it.logo_props = it_cfg.get('logo_props', it.logo_props)
        it.save(update_fields=['description', 'is_epic', 'level', 'logo_props'])
    tag = 'created' if created else 'exists'
    print(f'  {it_cfg[\"name\"]} (level={it_cfg.get(\"level\",2)}, epic={it_cfg.get(\"is_epic\",False)}) [{tag}]')
    types_created += 1 if created else 0

    # Enable on all projects
    for proj in Project.objects.filter(workspace=ws):
        ProjectIssueType.objects.get_or_create(
            project=proj, issue_type=it,
            defaults={'workspace': ws, 'level': it_cfg.get('level', 2),
                      'created_by': admin, 'updated_by': admin}
        )

# Enable issue types on all projects
for proj in Project.objects.filter(workspace=ws):
    if not proj.is_issue_type_enabled:
        proj.is_issue_type_enabled = True
        proj.save(update_fields=['is_issue_type_enabled'])

print(f'Issue types: {types_created} created, enabled on {Project.objects.filter(workspace=ws).count()} projects')

# ── Saved Views ──
print('\\n=== Saved Views ===')
views_created = 0
for proj in Project.objects.filter(workspace=ws):
    for view_cfg in config.get('views', []):
        existing = IssueView.objects.filter(
            name=view_cfg['name'], project=proj
        ).exists()
        if not existing:
            filters = view_cfg.get('filters', {})
            group_by = view_cfg.get('group_by', '')
            query_data = {}
            if filters:
                query_data['filters'] = filters
            if group_by:
                query_data['group_by'] = group_by

            IssueView.objects.create(
                name=view_cfg['name'],
                description=view_cfg.get('description', ''),
                project=proj,
                workspace=ws,
                filters=filters,
                owned_by=admin,
                created_by=admin,
                updated_by=admin,
            )
            views_created += 1
    print(f'  {proj.identifier}: views configured')

print(f'Views: {views_created} created')
print('\\nDone')
" 2>&1

log "Done"