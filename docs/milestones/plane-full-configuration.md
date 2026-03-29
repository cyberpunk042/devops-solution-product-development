# Plane Full Configuration — From Shallow to Production

**Date:** 2026-03-29
**Status:** Investigation complete — execution ready
**Scope:** Everything Plane offers that we're not using yet

---

## Investigation: What Plane Has vs What We Use

### Platform Features Available

| Feature | Plane Model | Used? | What It Does |
|---------|-------------|-------|-------------|
| **Members** | User, WorkspaceMember, ProjectMember | ❌ 1 user only | Agent accounts for assignment, tracking, accountability |
| **Issue Types** | IssueType, ProjectIssueType | ❌ None | Custom types: epic, story, task, bug, spike, chore (with `is_epic`, `level`) |
| **Issue Views** | IssueView | ❌ None | Saved filtered views: "My Sprint", "Blocked Items", "Security Review" |
| **Module Links** | ModuleLink | ❌ None | GitHub repo, docs, architecture pages linked FROM modules |
| **Issue Links** | IssueLink | ❌ None | External links on issues (GitHub PR, docs, related issues) |
| **Issue Relations** | IssueRelation | ❌ None | blocks/blocked_by, duplicate, relates_to between issues |
| **Module Members** | ModuleMember | ❌ None | Lead agent + members assigned to each epic |
| **Webhooks** | Webhook, WebhookLog | ❌ None | Event push to fleet webhook receiver |
| **Pages** | Page, ProjectPage | ✅ 8 pages | Wiki/docs — created via ORM (visible?) |
| **Custom Fields** | (not native v1) | N/A | Plane CE may not have custom fields — investigate |
| **Deploy Boards** | DeployBoard | ❌ None | Public project boards |
| **Intake/Triage** | Intake, IntakeIssue | ❌ Disabled | Triage queue for incoming items |
| **Notifications** | Notification, UserNotificationPreference | ❌ Default | Per-user notification preferences |
| **Favorites** | UserFavorite | ❌ None | Quick access to important items |
| **Workspace Links** | WorkspaceUserLink | ❌ None | Workspace-level external links |

### What's Configured vs What Should Be

| Resource | Current | Target |
|----------|---------|--------|
| Users | 1 (admin) | 12+ (admin + 10 agents + fleet service account) |
| Issue Types | 0 | 6 (epic, story, task, bug, spike, chore) |
| Saved Views | 0 | 6+ per project (sprint, backlog, blocked, review, agent, security) |
| Module Links | 0 | 4+ (GitHub repo per project, architecture docs) |
| Issues | 0 | 1+ per project (welcome/placeholder) |
| Issue Relations | 0 | Cross-project dependencies |
| Module Members | 0 | Lead agent per module |
| Webhooks | 0 | 1 (fleet webhook receiver) |

---

## User Requirements (from this conversation)

> "at least 1 work item for each, even if its just a welcome and/or a placeholder
> that would remain open"

> "what is Cycles and Views and Pages? is it not possible to bring this to our hand
> and add custom fields and such?"

> "modules / epics and all we are not going to be able to validate if the requirements
> is meant"

> "There is also no member beside me it seems.. what are the agents going to do?"

> "you should probably also exploit links and do cross-referencing properly everywhere
> on everything and point to git and to docs"

> "assign the lead"

> "lets keep investigating to bring plane to the level we need"

> "I can have multiple fleet working on the same Plane, with agent of the same roles
> that need a unique fleet id and identity infos"

> "Plane is facultative. the work is happening mostly locally and through ocmc.
> plane is a bonus we naturally bridge when present"

> "backlog creation sessions, classifications, breakdown, architecture, requirements,
> blockings, parts, complexity, effort, strategy, etc.... it needs the help of the
> team to do their sauce, its not a one man job its just that it takes a driver"

> "fleet-ops is the driver of the ocmc and project manager of Plane / dspd.
> so as will all the other have their own responsibilities like this eventually.
> for when they have free time."

---

## Milestones

### M-PF01: Create Agent Users (Bot Accounts)

Plane supports `is_bot=True` on User model with `bot_type` field.

Create 10 agent users + 1 fleet service account:
- `fleet-ops@fleet.local` (is_bot=True, display_name="Fleet Ops [99c1]")
- `project-manager@fleet.local`
- `architect@fleet.local`
- `software-engineer@fleet.local`
- `qa-engineer@fleet.local`
- `devops@fleet.local`
- `devsecops@fleet.local`
- `technical-writer@fleet.local`
- `ux-designer@fleet.local`
- `accountability-generator@fleet.local`
- `fleet-service@fleet.local` (API service account for sync)

Each user:
- `is_bot=True`
- `display_name` includes fleet prefix for multi-fleet: `"Architect [99c1]"`
- Added as WorkspaceMember (role=10 guest for most, role=20 member for PM/ops)
- Added as ProjectMember on relevant projects

**Config:** `config/fleet-members.yaml` with agent list + fleet ID
**Script:** Update `plane-seed-mission.sh` or new `plane-setup-members.sh`

### M-PF02: Issue Types (Epic/Story/Task Hierarchy)

Plane has IssueType with `is_epic` and `level` fields.

Create issue types:
- **Epic** (is_epic=True, level=0) — large feature or strategic initiative
- **Story** (level=1) — user-facing deliverable
- **Task** (level=2) — atomic unit of work (maps to OCMC task)
- **Bug** (level=2) — defect fix
- **Spike** (level=2) — research/investigation
- **Chore** (level=2) — maintenance, no user impact

Enable issue types per project (`is_issue_type_enabled=True`).

**Config:** Add `issue_types` to `config/mission.yaml`
**Script:** Update `plane-seed-mission.sh`

### M-PF03: Saved Views Per Project

Create useful views agents and humans can use:

**Per project:**
- "Current Sprint" — filter: cycle=current
- "Backlog" — filter: state.group=backlog
- "Blocked" — filter: label=blocked
- "In Review" — filter: state.group=started, state=In Review
- "By Agent" — group_by: assignee
- "Security Review" — filter: label=security

**AICP specific:**
- "LocalAI Stages" — filter: module starts with "Stage"

**Config:** Add `views` to board config files
**Script:** Via v1 API or Django ORM

### M-PF04: Module Links (GitHub + Docs Cross-References)

Link each module to its GitHub repo and relevant documentation:

**AICP modules:**
- Stage 1-5: link to `strategic-vision-localai-independence.md`
- Core Platform: link to GitHub `devops-expert-local-ai/aicp/core/`
- Integrations: link to GitHub `devops-expert-local-ai/aicp/backends/`

**OF modules:**
- Core: link to GitHub `openclaw-fleet/fleet/core/orchestrator.py`
- MCP: link to GitHub `openclaw-fleet/fleet/mcp/tools.py`
- Agents: link to GitHub `openclaw-fleet/agents/`
- Autonomy: link to `fleet-autonomy-milestones.md`

**DSPD modules:**
- Setup: link to GitHub `devops-solution-product-development/setup.sh`
- Integration: link to GitHub `fleet/cli/plane.py`

**Config:** Add `links` to module configs in board yaml files
**Script:** Via Django ORM (ModuleLink model)

### M-PF05: Module Members (Lead Assignment)

Assign a lead agent to each module:

| Project | Module | Lead |
|---------|--------|------|
| AICP | Stage 1-5 | architect (design) + devops (infra) |
| AICP | Core Platform | architect |
| AICP | Integrations | software-engineer |
| OF | Core | fleet-ops |
| OF | MCP | software-engineer |
| OF | Agents | fleet-ops |
| OF | Autonomy | architect |
| DSPD | Setup | devops |
| DSPD | Integration | project-manager |
| NNRT | All | accountability-generator |

**Requires:** M-PF01 (agent users must exist first)
**Script:** Via Django ORM (ModuleMember model)

### M-PF06: Welcome Issues (One Per Project)

Create one placeholder issue per project so they're not empty:

- **AICP:** "Welcome to AI Control Platform — LocalAI Independence Mission"
  - Description: links to strategic vision, current assessment, Stage 1 goals
  - State: Backlog
  - Priority: none
  - Labels: strategic

- **OF:** "Welcome to OpenClaw Fleet — Operational Validation"
  - Description: links to STATUS-TRACKER, fleet architecture, known gaps
  - State: Backlog
  - Labels: infra

- **DSPD:** "Welcome to DSPD — Plane Platform Configuration"
  - Description: links to IaC evolution milestone, integration architecture
  - State: Backlog
  - Labels: iac

- **NNRT:** "Welcome to NNRT — Pipeline Assessment"
  - Description: links to repo, architecture page, assessment questions
  - State: Backlog
  - Labels: docs

**Config:** Add `welcome_issues` to board config files
**Script:** Via REST API (creates real issues the PM can see)

### M-PF07: Cross-Project Issue Relations

Once welcome issues exist, create cross-references:
- AICP Stage 2 depends on fleet MCP tools (Plane MCP)
- DSPD sync depends on fleet chain runner
- NNRT pressure detection connects to AICP LocalAI (potential offload)

**Requires:** M-PF06 (issues must exist)
**Script:** Via Django ORM (IssueRelation model, `relation_type='blocks'`)

### M-PF08: Webhook Registration

Register fleet webhook receiver in Plane:
- URL: configurable (default `http://host.docker.internal:8001/webhook`)
- Events: `issue.*`, `cycle.*`, `comment.created`
- HMAC secret generated and stored
- Script: `scripts/plane-setup-webhooks.sh` (already exists, untested)

### M-PF09: Intake/Triage Queue

Enable intake view on projects. New items go to triage before backlog.
PM agent processes triage queue during heartbeat.

**Config:** Set `intake_view: true` in mission.yaml project config

---

## Dependencies

```
M-PF01 (Agent users) → no deps, do first
M-PF02 (Issue types) → no deps, can parallel
M-PF03 (Saved views) → no deps, can parallel
M-PF04 (Module links) → no deps, can parallel
M-PF05 (Module members) → M-PF01
M-PF06 (Welcome issues) → M-PF01 + M-PF02
M-PF07 (Cross-references) → M-PF06
M-PF08 (Webhooks) → no deps
M-PF09 (Intake) → no deps
```

### Execution Order

1. **M-PF01** Agent users — unblocks everything
2. **M-PF02** Issue types — enables proper hierarchy
3. **M-PF06** Welcome issues — projects not empty
4. **M-PF04** Module links — cross-references to GitHub/docs
5. **M-PF05** Module members — leads assigned
6. **M-PF03** Saved views — useful filters
7. **M-PF07** Cross-project relations
8. **M-PF08** Webhooks
9. **M-PF09** Intake queue

---

## Multi-Fleet Considerations

Agent users include fleet prefix in display_name:
- Fleet Alpha: "Architect [99c1]"
- Fleet Bravo: "Architect [XXXX]"

Same workspace, different identities. Plane labels `fleet:alpha` and `fleet:bravo`
tag which fleet's agents created each item.

When a second fleet connects:
1. New agent users created with Bravo prefix
2. Added to same workspace as members
3. Sync tagged with fleet ID
4. PM from each fleet manages its own sprint items
5. Human sees unified view across fleets