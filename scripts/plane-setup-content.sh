#!/usr/bin/env bash
# plane-setup-content.sh — Create module links, welcome issues, module leads
#
# Reads config files and creates:
#   - Module links (GitHub repos, docs cross-references)
#   - Module lead assignments
#   - Welcome issues (one per project, not empty)
#
# Requires: plane-setup-members.sh ran first (agent users must exist)
# Idempotent: checks before creating.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-dspd-plane}"
API_CONTAINER="${API_CONTAINER:-${COMPOSE_PROJECT}-api-1}"
PLANE_ADMIN_EMAIL="${PLANE_ADMIN_EMAIL:-admin@fleet.local}"
PLANE_URL="${PLANE_URL:-http://localhost:8080}"

log() { echo "[setup-content] $*"; }

# Read .plane-config for API token
CONFIG_FILE="${PROJECT_DIR}/.plane-config"
[ -f "$CONFIG_FILE" ] && source "$CONFIG_FILE"
TOKEN="${PLANE_API_TOKEN:-}"
WS="${PLANE_WORKSPACE_SLUG:-fleet}"

timeout 120 docker exec "$API_CONTAINER" python manage.py shell -c "
import json
from plane.db.models import (
    User, Workspace, Project, Module, ModuleLink, ModuleMember,
    Issue, State, Label, IssueLabel, IssueLink,
)

admin = User.objects.get(email='${PLANE_ADMIN_EMAIL}')
ws = Workspace.objects.get(slug='fleet')

def get_user(email):
    return User.objects.filter(email=email).first()

def get_project(ident):
    return Project.objects.filter(identifier=ident, workspace=ws).first()

def get_module(proj, name):
    return Module.objects.filter(project=proj, name=name).first()

def add_module_link(mod, title, url):
    if not ModuleLink.objects.filter(module=mod, url=url).exists():
        ModuleLink.objects.create(
            module=mod, project=mod.project, workspace=ws,
            title=title, url=url,
            created_by=admin, updated_by=admin,
        )
        return True
    return False

def set_module_lead(mod, agent_email):
    user = get_user(agent_email)
    if not user:
        return False
    mem, created = ModuleMember.objects.get_or_create(
        module=mod, member=user,
        defaults={'project': mod.project, 'workspace': ws,
                  'created_by': admin, 'updated_by': admin}
    )
    if created:
        mod.lead = user
        mod.save(update_fields=['lead'])
    return created

# ═══════════════════════════════════════════════════════════════════════════
# Module Links
# ═══════════════════════════════════════════════════════════════════════════

print('=== Module Links ===')
links_created = 0

# AICP
aicp = get_project('AICP')
if aicp:
    github = 'https://github.com/cyberpunk042/devops-expert-local-ai'
    vision = 'https://github.com/cyberpunk042/openclaw-fleet/blob/main/docs/milestones/active/strategic-vision-localai-independence.md'

    for stage_num in range(1, 6):
        mod = get_module(aicp, f'Stage {stage_num}:' + Module.objects.filter(project=aicp, name__startswith=f'Stage {stage_num}:').values_list('name', flat=True).first().split(':',1)[1] if Module.objects.filter(project=aicp, name__startswith=f'Stage {stage_num}:').exists() else '')
    # Simpler approach
    for mod in Module.objects.filter(project=aicp):
        if mod.name.startswith('Stage'):
            if add_module_link(mod, 'Strategic Vision', vision):
                links_created += 1
            if add_module_link(mod, 'GitHub: AICP', github):
                links_created += 1
        elif mod.name == 'Core Platform':
            if add_module_link(mod, 'GitHub: aicp/core/', f'{github}/tree/main/aicp/core'):
                links_created += 1
        elif mod.name == 'Integrations':
            if add_module_link(mod, 'GitHub: aicp/backends/', f'{github}/tree/main/aicp/backends'):
                links_created += 1
    print(f'  AICP: {links_created} links')

# OF
of = get_project('OF')
if of:
    github = 'https://github.com/cyberpunk042/openclaw-fleet'
    for mod in Module.objects.filter(project=of):
        paths = {
            'Core': 'fleet/cli/orchestrator.py',
            'MCP': 'fleet/mcp/tools.py',
            'Agents': 'agents/',
            'Infrastructure': 'scripts/',
            'Autonomy': 'docs/milestones/active/fleet-autonomy-milestones.md',
            'Tests': 'fleet/tests/',
        }
        if mod.name in paths:
            if add_module_link(mod, f'GitHub: {paths[mod.name]}', f'{github}/tree/main/{paths[mod.name]}'):
                links_created += 1
    print(f'  OF: links added')

# DSPD
dspd = get_project('DSPD')
if dspd:
    github = 'https://github.com/cyberpunk042/devops-solution-product-development'
    for mod in Module.objects.filter(project=dspd):
        if mod.name == 'Setup':
            add_module_link(mod, 'GitHub: setup.sh', f'{github}/blob/main/setup.sh')
        elif mod.name == 'Integration':
            add_module_link(mod, 'GitHub: fleet/cli/plane.py', f'{github}/blob/main/fleet/cli/plane.py')
        elif mod.name == 'Sync':
            add_module_link(mod, 'GitHub: plane_sync.py', f'{github}/blob/main/fleet/core/plane_sync.py')
    print(f'  DSPD: links added')

# NNRT
nnrt = get_project('NNRT')
if nnrt:
    github = 'https://github.com/cyberpunk042/Narrative-to-Neutral-Report-Transformer'
    for mod in Module.objects.filter(project=nnrt):
        add_module_link(mod, 'GitHub: NNRT', github)
    print(f'  NNRT: links added')

print(f'Total links: {links_created}+')

# ═══════════════════════════════════════════════════════════════════════════
# Module Leads
# ═══════════════════════════════════════════════════════════════════════════

print('\\n=== Module Leads ===')

leads = {
    'AICP': {
        'Stage 1': 'architect@fleet.local',
        'Stage 2': 'architect@fleet.local',
        'Stage 3': 'software-engineer@fleet.local',
        'Stage 4': 'devops@fleet.local',
        'Stage 5': 'architect@fleet.local',
        'Core Platform': 'architect@fleet.local',
        'Integrations': 'software-engineer@fleet.local',
    },
    'OF': {
        'Core': 'fleet-ops@fleet.local',
        'MCP': 'software-engineer@fleet.local',
        'Agents': 'fleet-ops@fleet.local',
        'Infrastructure': 'devops@fleet.local',
        'Autonomy': 'architect@fleet.local',
        'Tests': 'qa-engineer@fleet.local',
    },
    'DSPD': {
        'Setup': 'devops@fleet.local',
        'Integration': 'project-manager@fleet.local',
        'Sync': 'software-engineer@fleet.local',
        'Customization': 'software-engineer@fleet.local',
    },
    'NNRT': {
        'Intake': 'accountability-generator@fleet.local',
        'Structuring': 'accountability-generator@fleet.local',
        'Mapping': 'accountability-generator@fleet.local',
        'Pressure': 'accountability-generator@fleet.local',
        'Persistence': 'accountability-generator@fleet.local',
    },
}

for ident, module_leads in leads.items():
    proj = get_project(ident)
    if not proj:
        continue
    for mod_name_prefix, email in module_leads.items():
        for mod in Module.objects.filter(project=proj, name__startswith=mod_name_prefix):
            set_module_lead(mod, email)
    print(f'  {ident}: leads assigned')

# ═══════════════════════════════════════════════════════════════════════════
# Welcome Issues
# ═══════════════════════════════════════════════════════════════════════════

print('\\n=== Welcome Issues ===')

welcome = {
    'AICP': {
        'title': 'Welcome to AI Control Platform — LocalAI Independence Mission',
        'description': (
            '<h2>Mission</h2>'
            '<p>Progressive LocalAI independence. Route work through LocalAI for everything '
            'that does not require Claude reasoning. Target: 80%+ Claude token reduction.</p>'
            '<h2>Current State (2026-03-29)</h2>'
            '<ul>'
            '<li>LocalAI running: 9 models, hermes-3b benchmarked (1.2s warm)</li>'
            '<li>OpenAI-compatible API verified</li>'
            '<li>AICP package: 46 modules, 67 tests</li>'
            '</ul>'
            '<h2>Next Steps</h2>'
            '<ul>'
            '<li>Complete Stage 1: cluster verification + full benchmarks</li>'
            '<li>See Modules tab for the 5 stages + Core Platform + Integrations</li>'
            '<li>See Pages for architecture and strategic vision docs</li>'
            '</ul>'
        ),
        'priority': 'none',
        'labels': ['strategic'],
        'assignee': 'project-manager@fleet.local',
    },
    'OF': {
        'title': 'Welcome to OpenClaw Fleet — Operational Validation',
        'description': (
            '<h2>Fleet Status</h2>'
            '<p>10 agents online. Gateway running with self-healing. Daemons cycling. '
            'Communication verified (8/8 checks). 341 tests passing.</p>'
            '<h2>Known Gaps</h2>'
            '<ul>'
            '<li>Chain runner not built (MCP tools bypass chains)</li>'
            '<li>No Plane MCP tools (PM cannot access Plane from sessions)</li>'
            '<li>29 autonomy milestones NOT STARTED</li>'
            '<li>No agent has completed a real task yet</li>'
            '</ul>'
            '<h2>Next Steps</h2>'
            '<ul>'
            '<li>Validate one real task through the full review chain</li>'
            '<li>See Modules for Core, MCP, Agents, Infrastructure, Autonomy, Tests</li>'
            '</ul>'
        ),
        'priority': 'none',
        'labels': ['infra'],
        'assignee': 'fleet-ops@fleet.local',
    },
    'DSPD': {
        'title': 'Welcome to DSPD — Plane Platform Configuration',
        'description': (
            '<h2>Status</h2>'
            '<p>Plane deployed (12 containers). 4 projects seeded with modules, labels, states, '
            'sprints. Mission content from config/mission.yaml.</p>'
            '<h2>Remaining</h2>'
            '<ul>'
            '<li>Plane MCP tools for PM agent</li>'
            '<li>Chain runner integration with Plane surface</li>'
            '<li>Live sync test (Plane ↔ OCMC)</li>'
            '<li>Webhook registration</li>'
            '</ul>'
            '<h2>Milestones</h2>'
            '<ul>'
            '<li>M-SC01-08: Skills and chains</li>'
            '<li>M-PF01-09: Full Plane configuration</li>'
            '<li>M-P01-10: IaC evolution</li>'
            '</ul>'
        ),
        'priority': 'none',
        'labels': ['iac'],
        'assignee': 'project-manager@fleet.local',
    },
    'NNRT': {
        'title': 'Welcome to NNRT — Pipeline Assessment',
        'description': (
            '<h2>Project</h2>'
            '<p>Narrative-to-Neutral Report Transformer. Python NLP pipeline. '
            'The project exists as a GitHub repo — assessment needed first.</p>'
            '<h2>Pipeline</h2>'
            '<p>Intake → Structuring → Mapping → Pressure Detection → Persistence</p>'
            '<h2>Next Steps</h2>'
            '<ul>'
            '<li>Clone and assess current codebase</li>'
            '<li>Run existing tests</li>'
            '<li>Document what works, what is scaffolding</li>'
            '<li>Create Sprint 2 plan with task breakdown</li>'
            '</ul>'
        ),
        'priority': 'none',
        'labels': ['docs'],
        'assignee': 'accountability-generator@fleet.local',
    },
}

for ident, issue_cfg in welcome.items():
    proj = get_project(ident)
    if not proj:
        continue

    # Check if already exists
    if Issue.objects.filter(project=proj, name=issue_cfg['title']).exists():
        print(f'  {ident}: welcome issue exists')
        continue

    # Get default state (backlog)
    state = State.objects.filter(project=proj, group='backlog').first()
    if not state:
        state = State.objects.filter(project=proj, default=True).first()

    # Get assignee
    assignee = get_user(issue_cfg.get('assignee', ''))

    issue = Issue.objects.create(
        name=issue_cfg['title'],
        description_html=issue_cfg['description'],
        project=proj,
        workspace=ws,
        state=state,
        priority=issue_cfg.get('priority', 'none'),
        created_by=admin,
        updated_by=admin,
    )

    # Assign
    if assignee:
        from plane.db.models import IssueAssignee
        IssueAssignee.objects.create(
            issue=issue, assignee=assignee,
            project=proj, workspace=ws,
            created_by=admin, updated_by=admin,
        )

    # Labels
    for label_name in issue_cfg.get('labels', []):
        label = Label.objects.filter(project=proj, name=label_name).first()
        if label:
            IssueLabel.objects.create(
                issue=issue, label=label,
                project=proj, workspace=ws,
                created_by=admin, updated_by=admin,
            )

    # Add link to GitHub
    github_urls = {
        'AICP': 'https://github.com/cyberpunk042/devops-expert-local-ai',
        'OF': 'https://github.com/cyberpunk042/openclaw-fleet',
        'DSPD': 'https://github.com/cyberpunk042/devops-solution-product-development',
        'NNRT': 'https://github.com/cyberpunk042/Narrative-to-Neutral-Report-Transformer',
    }
    if ident in github_urls:
        IssueLink.objects.create(
            issue=issue, project=proj, workspace=ws,
            title='GitHub Repository',
            url=github_urls[ident],
            created_by=admin, updated_by=admin,
        )

    print(f'  {ident}: \"{issue_cfg[\"title\"][:50]}...\" (created)')

print('\\nDone')
" 2>&1

log "Done"

# ── Pages (from board config) ──────────────────────────────────

log "Creating pages from board configs..."

for board_file in "$PROJECT_DIR"/config/*-board.yaml; do
    [ -f "$board_file" ] || continue

    timeout 60 docker exec -i "$API_CONTAINER" python manage.py shell -c "
import sys, yaml
from plane.db.models import Project, Workspace, User
try:
    from plane.db.models import Page, ProjectPage
except ImportError:
    from plane.db.models.page import Page, ProjectPage

ws = Workspace.objects.get(slug='fleet')
admin = User.objects.get(email='${PLANE_ADMIN_EMAIL}')
board = yaml.safe_load(sys.stdin.read())
proj = Project.objects.filter(identifier=board['project'], workspace=ws).first()
if not proj:
    sys.exit(0)

for page_cfg in board.get('pages', []):
    title = page_cfg['title']
    html = page_cfg.get('content_html', '')
    if not html:
        content = page_cfg.get('content', '')
        html = f'<pre>{content}</pre>' if content else ''
    if not html:
        continue

    exists = ProjectPage.objects.filter(project=proj, page__name=title).exists()
    if exists:
        pp = ProjectPage.objects.get(project=proj, page__name=title)
        pp.page.description_html = html
        pp.page.save(update_fields=['description_html'])
    else:
        page = Page.objects.create(
            name=title,
            description_html=html,
            workspace=ws,
            owned_by=admin,
            created_by=admin,
            updated_by=admin,
        )
        ProjectPage.objects.create(
            page=page, project=proj, workspace=ws,
            created_by=admin, updated_by=admin,
        )
        print(f'  {board[\"project\"]}: {title}')
" < "$board_file" 2>&1 || log "WARN: Pages failed for $(basename "$board_file")"
done

log "Pages created"

# ── Starter Issues (from board config) ──────────────────────────────────

log "Creating starter issues from board configs..."

for board_file in "$PROJECT_DIR"/config/*-board.yaml; do
    [ -f "$board_file" ] || continue
    
    timeout 60 docker exec -i "$API_CONTAINER" python manage.py shell -c "
import sys, yaml
from plane.db.models import (
    User, Workspace, Project, Issue, State, Label,
    IssueAssignee, IssueLabel, IssueLink,
)
from plane.db.models.issue_type import IssueType

ws = Workspace.objects.get(slug='fleet')
admin = User.objects.get(email='${PLANE_ADMIN_EMAIL}')
board = yaml.safe_load(sys.stdin.read())
proj = Project.objects.filter(identifier=board['project'], workspace=ws).first()
if not proj:
    sys.exit(0)

for issue_cfg in board.get('starter_issues', []):
    title = issue_cfg['title']
    if Issue.objects.filter(project=proj, name=title).exists():
        continue

    state = State.objects.filter(project=proj, group='backlog').first()
    issue_type = IssueType.objects.filter(name=issue_cfg.get('type', 'Task'), workspace=ws).first()

    kwargs = {
        'name': title,
        'description_html': f'<p>{issue_cfg.get(\"description\", \"\")}</p>',
        'project': proj,
        'workspace': ws,
        'state': state,
        'priority': issue_cfg.get('priority', 'medium'),
        'created_by': admin,
        'updated_by': admin,
    }
    if issue_type:
        kwargs['type'] = issue_type

    issue = Issue.objects.create(**kwargs)

    assignee_email = issue_cfg.get('assignee', '')
    if assignee_email:
        assignee = User.objects.filter(email=assignee_email).first()
        if assignee:
            IssueAssignee.objects.create(
                issue=issue, assignee=assignee,
                project=proj, workspace=ws,
                created_by=admin, updated_by=admin,
            )

    for label_name in issue_cfg.get('labels', []):
        label = Label.objects.filter(project=proj, name=label_name).first()
        if label:
            IssueLabel.objects.create(
                issue=issue, label=label,
                project=proj, workspace=ws,
                created_by=admin, updated_by=admin,
            )

    print(f'  {board[\"project\"]}: {title[:50]}')
" < "$board_file" 2>&1 || log "WARN: Starter issues failed for $(basename "$board_file")"
done

log "Starter issues created"
