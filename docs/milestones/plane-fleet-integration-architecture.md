# Plane ↔ Fleet Integration Architecture

**Date:** 2026-03-29
**Status:** Investigation + architectural plan
**Scope:** How Plane fits into the fleet ecosystem, multi-fleet, agent roles, sync model

---

## Core Principle: Plane is Optional

Plane is a bonus surface. The fleet works WITHOUT Plane — agents operate on OCMC,
heartbeats fire, tasks dispatch, reviews happen, PRs get created. All locally.

When Plane IS present, it provides:
- Sprint/cycle management (burn-down, velocity)
- Cross-project visibility (OF, AICP, DSPD, NNRT in one dashboard)
- Backlog management (classification, prioritization, story points)
- Wiki/pages (architecture docs, specs, playbooks)
- Analytics (agent productivity, cycle time)
- Human interface (the user works in Plane, agents work in OCMC)

**The bridge is natural, not forced.** If Plane is down, the fleet continues.
If Plane is up, data syncs both ways through the PM agent and orchestrator.

> "important to remember the plane place and yet how oc agent still work on ocmc,
> that's why we need smart tools, chains that will trigger multiple things for one
> call or one event and that will keep listening to all side and keep in sync for
> if I do a manual change or adding or task or information and such that everything
> is kept track of and triggering the right event that will wake the right agent or
> will influence it for its next heartbeat."

---

## Multi-Fleet Architecture

> "having our full 2 cluster LocalAI peered in the network with one Plane
> and eventually 2 or even 3 fleets"

### One Plane, Multiple Fleets

```
                    ┌─────────────────────────┐
                    │  PLANE (shared)          │
                    │  4 projects (OF,AICP,    │
                    │  DSPD,NNRT)              │
                    │  sprints, epics, wiki    │
                    └────────┬────────┬────────┘
                             │        │
              ┌──────────────┘        └──────────────┐
              ▼                                      ▼
   ┌─────────────────────┐              ┌─────────────────────┐
   │ Fleet Alpha          │              │ Fleet Bravo          │
   │ fleet-99c1272b       │              │ fleet-XXXXXXXX       │
   │                      │              │                      │
   │ OCMC + Gateway       │              │ OCMC + Gateway       │
   │ 10 agents (99c1-*)   │              │ 10 agents (XXXX-*)   │
   │ LocalAI Cluster 1    │              │ LocalAI Cluster 2    │
   │ Daemons (orch/sync)  │              │ Daemons (orch/sync)  │
   └──────────────────────┘              └──────────────────────┘
```

### Agent Identity in Multi-Fleet

Each fleet has a unique identity (from `fleet/core/federation.py`):
- `fleet_id`: `fleet-99c1272b` (unique per machine)
- `agent_prefix`: `99c1` (4-char prefix for namespacing)
- `machine_id`: hostname

Agents from different fleets have the same ROLES but different IDENTITIES:
- Fleet Alpha: `99c1-project-manager`, `99c1-architect`, `99c1-software-engineer`...
- Fleet Bravo: `XXXX-project-manager`, `XXXX-architect`, `XXXX-software-engineer`...

In Plane, these map to workspace members with fleet-prefixed display names.
The PM from Fleet Alpha and PM from Fleet Bravo can both contribute to the
same Plane project — their work is tagged with their fleet identity.

### Plane Sync Per Fleet

Each fleet's orchestrator runs its own Plane sync:
- Fleet Alpha syncs its OCMC tasks → Plane (tagged `fleet:alpha`)
- Fleet Bravo syncs its OCMC tasks → Plane (tagged `fleet:bravo`)
- Human sees unified view in Plane across all fleets
- PM agent from each fleet reads the same Plane sprint but creates OCMC tasks in its OWN MC

The sync is tagged — each fleet only touches its own tasks in the sync.
Cross-fleet visibility is through Plane labels and filters.

---

## Agent Roles and Plane Responsibilities

### fleet-ops: Driver of OCMC

fleet-ops is the board lead of OCMC. Responsibilities:
- Reviews ALL agent work (approval gate)
- Monitors board health (stale tasks, offline agents)
- Posts operational digests
- Enforces quality standards
- Drives fleet improvements when idle

fleet-ops does NOT write to Plane directly. It works exclusively in OCMC.
Plane updates come through the sync, not through fleet-ops.

### project-manager: Driver of Plane/DSPD

The PM is the sole writer to Plane. Responsibilities:
- Reads Plane sprint status on heartbeat
- Breaks down epics into OCMC tasks (dispatches to agents)
- Updates Plane when OCMC tasks complete
- Runs backlog creation sessions:
  - Classification (type, priority, complexity)
  - Breakdown (epic → stories → tasks)
  - Architecture requirements identification
  - Blocking/dependency mapping
  - Effort estimation (story points)
  - Strategy alignment (does this serve the mission?)
- Sprint management:
  - Sprint planning (what goes in this cycle)
  - Velocity tracking (story points delivered)
  - Burn-down monitoring
  - Sprint retrospective at cycle end
- Cross-project coordination via Plane modules

> The PM needs help from the team. Backlog creation is not a one-person job —
> the PM drives it but the architect provides complexity assessment, the
> QA engineer identifies test requirements, the devsecops expert flags security
> concerns, the technical writer identifies documentation needs.

### Other Agents: Secondary Responsibilities

When agents have free time (no assigned tasks, no human work), they
contribute to their secondary responsibilities:

| Agent | Primary | Secondary (when free) |
|-------|---------|----------------------|
| fleet-ops | OCMC board lead, reviews | Quality improvement, gap detection |
| project-manager | Plane/DSPD, sprint management | Cross-project dependency analysis |
| architect | System design | Complexity assessment for PM, architecture review |
| software-engineer | Implementation | Code quality suggestions, refactoring proposals |
| qa-engineer | Testing | Test coverage analysis, regression risk assessment |
| devops | Infrastructure | CI/CD improvements, monitoring enhancements |
| devsecops-expert | Security | Dependency audit, credential rotation |
| technical-writer | Documentation | Doc gap detection, onboarding improvements |
| ux-designer | UI/UX | Accessibility audit, design system updates |
| accountability-generator | NNRT, governance | Evidence chain validation, compliance checks |

These secondary responsibilities feed INTO the PM's backlog. When the architect
identifies a complexity issue, the PM creates a Plane item. When the QA engineer
flags a coverage gap, the PM classifies and schedules it.

---

## Sync Model

### Direction: Bidirectional with PM as Bridge

```
Human creates Plane issue
  → Plane webhook / next sync cycle
  → PM's heartbeat context includes new Plane items
  → PM evaluates: classify, estimate, assign
  → PM creates OCMC task via fleet_task_create
  → Agent gets dispatched, works, completes
  → Completion chain fires
  → Chain includes PLANE surface event
  → Plane issue updated to "Done"
```

```
Agent discovers work during task execution
  → Agent creates subtask via fleet_task_create (OCMC)
  → Orchestrator evaluates parents
  → Next sync cycle: OCMC→Plane
  → Plane shows new items created by agents
  → Human sees full picture in Plane
```

### What Syncs

| OCMC → Plane | Plane → OCMC |
|-------------|-------------|
| Task completion (state change) | New issues (human-created) |
| PR URLs (from fleet_task_complete) | Priority changes |
| Story point actuals | Sprint/cycle changes |
| Agent assignments | Deleted/cancelled items |
| Sprint velocity data | Comments/mentions |

### What Does NOT Sync

- OCMC board memory → NOT synced (operational, not project management)
- Agent heartbeat data → NOT synced (internal)
- IRC messages → NOT synced (ephemeral)
- Plane pages/wiki → NOT synced (lives in Plane only)
- OCMC approvals → NOT synced (internal review process)

### Graceful Degradation

If Plane is unreachable:
- Chain runner marks PLANE events as failed, continues others
- Orchestrator Plane sync step skips with warning
- PM heartbeat context shows "Plane: OFFLINE" instead of sprint data
- Fleet continues operating on OCMC normally
- When Plane comes back, next sync catches up

---

## Backlog Management Standards

The PM agent follows high standards for every piece of project work:

### Backlog Creation Session

When the PM has a new epic or set of work items:

1. **Classification** — What type? (feature, bug, infra, docs, security, test)
2. **Priority** — How urgent? (urgent/high/medium/low)
3. **Complexity** — How hard? (trivial/simple/moderate/complex/very complex)
4. **Effort** — How much work? (story points: 1/2/3/5/8/13)
5. **Architecture** — What's the technical approach? (PM asks architect if complex)
6. **Requirements** — What must it do? (acceptance criteria)
7. **Blocking** — What does it depend on? What does it block?
8. **Parts** — How does it break down? (epic → stories → tasks)
9. **Strategy** — Does this serve the mission? (LocalAI independence, fleet autonomy)
10. **Assignment** — Which agent is best suited? (routing by capability)

### Sprint Planning

When starting a new cycle:

1. Review backlog — what's ready? (spec complete, dependencies met)
2. Capacity check — which agents are available? (workload, status)
3. Priority sort — what's most important? (urgent first, then mission-aligned)
4. Load balance — distribute across agents (no one overloaded)
5. Dependency chain — order tasks so blockers resolve first
6. Sprint goal — one sentence: what does this sprint achieve?
7. Communicate — post sprint kickoff to IRC #sprint, update Plane cycle

### Quality Gate (every task)

Before moving to "Done":
1. Tests pass (fleet_task_complete runs pytest)
2. PR created and linked
3. Review by fleet-ops (approval with reasoning)
4. Acceptance criteria met
5. Documentation updated (if applicable)
6. No security regressions (devsecops review for sensitive changes)

---

## Impact on Config Files

### mission.yaml Changes Needed

The module descriptions for AICP need to reference:
- The chain architecture (one call → multi-surface publish)
- The routing table (what stays on Claude, what goes to LocalAI)
- That Plane is optional but naturally bridged when present
- The multi-fleet identity system
- That the PM drives breakdown, not the IaC

### aicp-board.yaml Changes Needed

Epic details need to include:
- Verbatim user vision quotes (already partially done)
- References to the chain/skill milestones (M-SC01 through M-SC08)
- How each stage connects to the Plane integration
- That Stage 2 routing works WITH the chain runner
- That Stage 3 offload applies to chain events too

### fleet-board.yaml Changes Needed

Module descriptions should reference:
- fleet-ops as OCMC driver
- PM as Plane driver
- Secondary responsibilities for idle agents
- The chain system (Core module)
- The sync model (how OCMC↔Plane stays in sync)

### New Config: fleet-roles.yaml

Define agent responsibilities in a way the PM can read:
- Primary role
- Secondary role (when free)
- Plane access level (PM=write, fleet-ops=read, others=none)
- Products owned (from driver.py)
- Skills available

---

## Next Steps

1. Update `config/mission.yaml` module descriptions with full context
2. Update `config/aicp-board.yaml` epic details with vision quotes + chain refs
3. Update `config/fleet-board.yaml` with agent role descriptions
4. Create `config/fleet-roles.yaml` for agent responsibility matrix
5. Re-run `plane-seed-mission.sh` to push updated content
6. Begin M-SC04 (Plane MCP tools) — the immediate unblock for PM agent