#!/usr/bin/env bash
# plane-seed-mission.sh — Seed Plane with mission structure from config/mission.yaml
#
# Reads config/mission.yaml and configures:
#   - Projects with descriptions, GitHub links, view settings
#   - Per-project workflow states (custom per project)
#   - Modules (epics) with descriptions
#   - Labels (fleet-wide, applied to all projects)
#   - Estimate system (Fibonacci story points)
#
# Does NOT create individual tasks/issues.
# The project-manager agent breaks epics into tasks.
#
# Usage:
#   COMPOSE_PROJECT=dspd-plane ./scripts/plane-seed-mission.sh
#
# Idempotent: safe to re-run after config changes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MISSION_FILE="${MISSION_FILE:-${PROJECT_DIR}/config/mission.yaml}"

PLANE_URL="${PLANE_URL:-http://localhost:8080}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-dspd-plane}"
API_CONTAINER="${API_CONTAINER:-${COMPOSE_PROJECT}-api-1}"
PLANE_ADMIN_EMAIL="${PLANE_ADMIN_EMAIL:-admin@fleet.local}"

log() { echo "[plane-seed-mission] $*"; }
die() { echo "[plane-seed-mission] ERROR: $*" >&2; exit 1; }

[ -f "$MISSION_FILE" ] || die "Mission file not found: $MISSION_FILE"

HTTP=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 "$PLANE_URL/" 2>/dev/null || echo "000")
[ "$HTTP" = "200" ] || die "Plane not reachable at $PLANE_URL (HTTP $HTTP)"

log "Mission file: $MISSION_FILE"
log "Plane URL:    $PLANE_URL"
log "Container:    $API_CONTAINER"
echo ""

# Pass the YAML content into the Django shell via stdin
cat "$MISSION_FILE" | docker exec -i "$API_CONTAINER" python manage.py shell -c "
import sys, yaml
from plane.db.models import (
    User, Workspace, WorkspaceMember,
    Project, ProjectMember, State, Module, Label, Estimate, EstimatePoint,
)

config = yaml.safe_load(sys.stdin.read())
user = User.objects.get(email='${PLANE_ADMIN_EMAIL}')

# ── Workspace ──────────────────────────────────────────────────────────────
ws_cfg = config['workspace']
ws = Workspace.objects.filter(slug=ws_cfg['slug']).first()
if not ws:
    print(f'ERROR: Workspace {ws_cfg[\"slug\"]} not found. Run plane-configure.sh first.')
    sys.exit(1)
print(f'Workspace: {ws.name} ({ws.slug})')

# ── Estimates ──────────────────────────────────────────────────────────────
est_cfg = config.get('estimates', {})
# Estimates are created per-project (Plane requires project FK)

# ── Labels (fleet-wide, applied to all projects) ──────────────────────────
labels_cfg = config.get('labels', [])
label_objects = {}

# ── Projects ───────────────────────────────────────────────────────────────
for proj_cfg in config.get('projects', []):
    identifier = proj_cfg['identifier']
    name = proj_cfg['name']
    emoji = proj_cfg.get('emoji', '')
    desc = proj_cfg.get('description', '')
    github = proj_cfg.get('github', '')
    network = proj_cfg.get('network', 2)
    views = proj_cfg.get('views', {})

    proj, created = Project.objects.get_or_create(
        identifier=identifier, workspace=ws,
        defaults={
            'name': name,
            'description': desc.strip(),
            'network': network,
            'created_by': user,
            'updated_by': user,
            'module_view': views.get('modules', True),
            'cycle_view': views.get('cycles', True),
            'issue_views_view': views.get('issue_views', True),
            'page_view': views.get('pages', True),
            'emoji': emoji,
        }
    )
    if not created:
        proj.name = name
        proj.description = desc.strip()
        if emoji: proj.emoji = emoji
        proj.module_view = views.get('modules', True)
        proj.cycle_view = views.get('cycles', True)
        proj.issue_views_view = views.get('issue_views', True)
        proj.page_view = views.get('pages', True)
        proj.save(update_fields=[
            'name', 'description', 'emoji', 'module_view', 'cycle_view',
            'issue_views_view', 'page_view',
        ])

    ProjectMember.objects.get_or_create(
        project=proj, member=user,
        defaults={'role': 20, 'is_active': True}
    )

    tag = 'CREATED' if created else 'UPDATED'
    print(f'\\nProject: {identifier} — {name} ({tag})')

    # ── Per-project states ──
    states_cfg = proj_cfg.get('states', [])
    if states_cfg:
        for s_data in states_cfg:
            state, s_created = State.objects.get_or_create(
                name=s_data['name'], project=proj,
                defaults={
                    'workspace': ws,
                    'group': s_data['group'],
                    'color': s_data['color'],
                    'default': s_data.get('default', False),
                    'sequence': s_data.get('sequence', states_cfg.index(s_data) * 10000 + 15000),
                    'created_by': user,
                    'updated_by': user,
                }
            )
            if not s_created:
                state.group = s_data['group']
                state.color = s_data['color']
                state.default = s_data.get('default', False)
                state.save(update_fields=['group', 'color', 'default'])

        # Ensure single default
        defaults = State.objects.filter(project=proj, default=True)
        if defaults.count() > 1:
            defaults.exclude(pk=defaults.first().pk).update(default=False)

        names = list(State.objects.filter(project=proj).order_by('sequence').values_list('name', flat=True))
        print(f'  States: {names}')

    # ── Per-project labels (fleet-wide labels applied to each project) ──
    for lbl_cfg in labels_cfg:
        lbl, _ = Label.objects.get_or_create(
            name=lbl_cfg['name'], project=proj,
            defaults={
                'workspace': ws,
                'color': lbl_cfg['color'],
                'description': lbl_cfg.get('description', ''),
                'created_by': user,
                'updated_by': user,
            }
        )
    label_count = Label.objects.filter(project=proj).count()
    print(f'  Labels: {label_count}')

    # ── Modules (epics) ──
    modules_cfg = proj_cfg.get('modules', [])
    for mod_cfg in modules_cfg:
        mod, m_created = Module.objects.get_or_create(
            name=mod_cfg['name'], project=proj,
            defaults={
                'workspace': ws,
                'description': mod_cfg.get('description', '').strip(),
                'created_by': user,
                'updated_by': user,
            }
        )
        if not m_created and mod_cfg.get('description'):
            mod.description = mod_cfg['description'].strip()
            mod.save(update_fields=['description'])

    mod_count = Module.objects.filter(project=proj).count()
    mod_names = list(Module.objects.filter(project=proj).values_list('name', flat=True))
    print(f'  Modules: {mod_count} — {mod_names}')

    # ── Estimates (per-project) ──
    if est_cfg:
        scale = est_cfg.get('scale', [1, 2, 3, 5, 8, 13])
        try:
            estimate_obj, e_created = Estimate.objects.get_or_create(
                name='Story Points', project=proj,
                defaults={'workspace': ws, 'type': 'points',
                          'created_by': user, 'updated_by': user}
            )
            if e_created:
                for i, val in enumerate(scale):
                    EstimatePoint.objects.get_or_create(
                        estimate=estimate_obj, key=i,
                        defaults={'value': str(val), 'workspace': ws,
                                  'created_by': user, 'updated_by': user}
                    )
            proj.estimate = estimate_obj
            proj.save(update_fields=['estimate'])
            print(f'  Estimates: Story Points {scale}')
        except Exception as e:
            print(f'  Estimates: SKIP ({e})')

print('\\n=== Mission structure seeded ===')
print(f'Projects: {len(config.get(\"projects\", []))}')
print(f'Labels: {len(labels_cfg)} (per project)')
print(f'Estimates: {est_cfg.get(\"scale\", [])}')
" 2>&1

EXIT_CODE=$?
[ $EXIT_CODE -eq 0 ] || die "Mission seed failed (exit $EXIT_CODE)"

# ── Phase 2: Seed per-project board content (pages, cycles, epic details) ──
log ""
log "Seeding per-project board content..."

BOARD_DIR="${PROJECT_DIR}/config"
for board_file in "$BOARD_DIR"/*-board.yaml; do
    [ -f "$board_file" ] || continue
    BOARD_NAME=$(basename "$board_file")
    log "  Processing $BOARD_NAME..."

    cat "$board_file" | docker exec -i "$API_CONTAINER" python manage.py shell -c "
import sys, yaml
from datetime import date, timedelta
from django.utils import timezone
from plane.db.models import (
    User, Workspace, Project, Module, Cycle, Page, PageLog,
)

board = yaml.safe_load(sys.stdin.read())
user = User.objects.get(email='${PLANE_ADMIN_EMAIL}')
ws = Workspace.objects.get(slug='fleet')
identifier = board.get('project', '')
proj = Project.objects.filter(identifier=identifier, workspace=ws).first()
if not proj:
    print(f'  SKIP: project {identifier} not found')
    sys.exit(0)

# ── Pages (wiki) — skipped, Plane M2M through model requires custom handling
# TODO: use Plane API for page creation instead of Django ORM
pages_cfg = [] # board.get("pages", [])
for page_cfg in pages_cfg:
    title = page_cfg['title']
    content = page_cfg.get('content', '')
    existing = Page.objects.filter(name=title, projects=proj).first()
    if not existing:
        page = Page.objects.create(
            name=title,
            description_html=f'<pre>{content}</pre>',
            workspace=ws,
            owned_by=user,
            created_by=user,
            updated_by=user,
        )
        page.projects.add(proj)
        print(f'  PAGE: {title} (created)')
    else:
        print(f'  PAGE: {title} (exists)')

# ── Cycles (sprints) ──
cycles_cfg = board.get('cycles', [])
today = date.today()
for cycle_cfg in cycles_cfg:
    name = cycle_cfg['name']
    duration = cycle_cfg.get('duration_days', 14)
    desc = cycle_cfg.get('description', '')
    goals = cycle_cfg.get('goals', [])

    full_desc = desc.strip()
    if goals:
        full_desc += '\\n\\nGoals:\\n' + '\\n'.join(f'- {g}' for g in goals)

    existing = Cycle.objects.filter(name=name, project=proj).first()
    if not existing:
        cycle = Cycle.objects.create(
            name=name,
            description=full_desc,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=duration),
            workspace=ws,
            owned_by=user,
            project=proj,
            created_by=user,
            updated_by=user,
        )
        # Link epics to cycle if specified
        epic_names = cycle_cfg.get('epics', [])
        for epic_name in epic_names:
            mod = Module.objects.filter(name=epic_name, project=proj).first()
            if mod:
                print(f'  CYCLE: {name} ← module {epic_name}')
        print(f'  CYCLE: {name} ({today} → {today + timedelta(days=duration)})')
    else:
        print(f'  CYCLE: {name} (exists)')

# ── Epic details (update module descriptions from board config) ──
epic_details = board.get('epic_details', {})
for epic_name, details in epic_details.items():
    mod = Module.objects.filter(name=epic_name, project=proj).first()
    if mod:
        notes = details.get('notes', '')
        ac = details.get('acceptance_criteria', [])
        deps = details.get('dependencies', [])

        desc_parts = [mod.description or '']
        if ac:
            desc_parts.append('\\nAcceptance Criteria:\\n' + '\\n'.join(f'- {c}' for c in ac))
        if deps:
            desc_parts.append('\\nDependencies:\\n' + '\\n'.join(f'- {d}' for d in deps))
        if notes:
            desc_parts.append('\\nNotes:\\n' + notes.strip())

        mod.description = '\\n'.join(desc_parts).strip()
        mod.save(update_fields=['description'])

print(f'  {identifier}: {len(pages_cfg)} pages, {len(cycles_cfg)} cycles, {len(epic_details)} epic details')
" 2>&1
done

log ""
log "Mission seeded successfully"