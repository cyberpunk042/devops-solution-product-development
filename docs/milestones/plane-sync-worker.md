# Plane Sync Worker — Real-Time Cross-Platform Bridge

**Date:** 2026-03-29
**Status:** Architecture plan — ready for execution
**Scope:** The worker daemon that keeps Plane, OCMC, GitHub, and IRC in sync

---

## User Requirements (Verbatim)

> "there is going to be a worker that listen to everything like it does for
> the PR and PR messages and any inter-platform sync needed sync and event
> generation for the agents follow-up and sync achieval or conflict resolution
> or assistance or follow-up and impediments and so on.. do not forget a
> single thing. we will need a bullet proof system"

> "important to remember the plane place and yet how oc agent still work on
> ocmc, that's why we need smart tools, chains that will trigger multiple
> things for one call or one event and that will keep listening to all side
> and keep in sync for if I do a manual change or adding or task or information
> and such that everything is kept track of and triggering the right event that
> will wake the right agent or will influence it for its next heartbeat."

> "We will also need to make it so that we can keep the IaC definition in sync
> as the plane evolve as the agent works, so that if we restart it will pick up
> where we left approximately or even perfectly."

> "we need to really make this strong."

---

## What This Worker Does

A daemon that runs alongside the orchestrator, listening to ALL surfaces
and keeping them in sync. Like the existing `remote_watcher.py` that
monitors GitHub PR comments, but expanded to cover the full ecosystem.

### Surfaces It Watches

| Surface | What It Watches | How |
|---------|----------------|-----|
| **Plane** | New issues, state changes, comments, cycle changes, module updates | Webhook receiver + polling |
| **OCMC** | Task status changes, approvals, board memory, agent activity | MC API polling (existing sync daemon) |
| **GitHub** | PR comments, review status, CI results, merge events | GitHub API polling (existing remote_watcher) |
| **IRC** | Agent messages, @mentions, alerts | IRC client (existing) |

### What It Does With Events

| Event | Action |
|-------|--------|
| **Plane: new issue created by human** | Tag for PM's next heartbeat. If "auto-dispatch" label, create OCMC task immediately. |
| **Plane: issue state changed** | Sync to OCMC if mapped task exists. If moved to "Done" in Plane, mark OCMC task done. |
| **Plane: comment added** | Route @mentions to agents via OCMC chat or IRC. Track for agent heartbeat context. |
| **Plane: cycle started** | Post sprint kickoff to IRC #sprint. Update PM heartbeat context. |
| **Plane: cycle completed** | Generate velocity report. Post to IRC #fleet. Update board memory. |
| **Plane: module updated** | If description/status changed, flag for relevant agent's heartbeat. |
| **OCMC: task completed** | Sync to Plane issue (state → "Done"). Update Plane cycle progress. |
| **OCMC: task created by agent** | Create corresponding Plane issue if cross-project. Tag with agent + fleet ID. |
| **OCMC: approval processed** | If approved, fire completion chain. If rejected, create fix task. Notify Plane. |
| **OCMC: agent goes offline** | Alert IRC #alerts. Flag in Plane project status page. |
| **GitHub: PR merged** | Update OCMC task to done. Update Plane issue. Close IRC review thread. |
| **GitHub: PR comment** | Route to assigned agent via OCMC. Track for agent heartbeat. (Existing in remote_watcher) |
| **GitHub: CI failed** | Alert assigned agent. Post to IRC #builds. Flag task as blocked. |
| **GitHub: review requested** | Notify fleet-ops via OCMC. Post to IRC #reviews. |
| **IRC: @mention** | Route to mentioned agent's heartbeat context. |
| **Conflict detected** | When Plane and OCMC disagree on state, flag for PM resolution. |

### Conflict Resolution

When the sync worker detects conflicting state:
- **Plane says "Done", OCMC says "In Progress"**: Trust OCMC (closer to the work). Flag for PM.
- **OCMC says "Done", Plane says "In Progress"**: Update Plane (OCMC is authoritative for agent work).
- **Both updated simultaneously**: Last-write-wins with audit trail. Flag for PM review.
- **Plane issue deleted, OCMC task exists**: Archive OCMC task. Don't delete — archive with reason.
- **OCMC task deleted, Plane issue exists**: Flag in Plane as "OCMC task removed". PM decides.

### Impediment Detection

The worker detects impediments and assists:
- Task assigned but agent offline for >2 heartbeats → flag impediment
- Task in progress >24h with no commits → flag stalled
- PR open >48h with no reviews → escalate to fleet-ops
- Blocked task with resolved dependency → auto-unblock, notify agent
- Sprint at >80% time with <50% completion → velocity alert to PM

---

## Architecture

### Worker Process

```
fleet/cli/sync_worker.py (NEW)
    │
    ├── PlaneWatcher
    │   ├── Webhook receiver (dspd/webhooks.py — already built)
    │   └── Polling fallback (when webhooks unavailable)
    │
    ├── OCMCWatcher
    │   ├── Task status changes (poll MC API)
    │   ├── Approval events (poll approvals endpoint)
    │   └── Agent activity (poll agent last_seen)
    │
    ├── GitHubWatcher
    │   ├── PR comments (existing remote_watcher.py)
    │   ├── CI status (GitHub API)
    │   └── Merge events (GitHub API)
    │
    ├── SyncEngine
    │   ├── Bidirectional state sync (Plane ↔ OCMC)
    │   ├── Conflict detection + resolution
    │   ├── Impediment detection
    │   └── Event chain emission
    │
    └── EventEmitter
        ├── Chain builder (builds EventChain per detected event)
        ├── Chain runner (executes across all surfaces)
        └── Audit logger (tracks all sync actions)
```

### Integration with Existing Daemons

The sync worker runs as a new daemon in `fleet/cli/daemon.py`:

```python
async def _run_all():
    await asyncio.gather(
        _run_sync_daemon(60),       # existing: board sync
        _run_auth_daemon(120),       # existing: token refresh
        _run_monitor_daemon(300),    # existing: health + self-healing
        run_orchestrator_daemon(30), # existing: the brain
        run_sync_worker(15),         # NEW: cross-platform sync
    )
```

The sync worker runs every 15 seconds — faster than the orchestrator
because it needs to detect changes quickly for responsive sync.

### State Tracking

The worker maintains sync state to know what's changed:

```python
@dataclass
class SyncState:
    """Tracks last-known state for change detection."""

    # Plane state
    plane_issues: dict[str, str]        # issue_id → last_updated_at
    plane_cycles: dict[str, str]        # cycle_id → last_updated_at

    # OCMC state
    ocmc_tasks: dict[str, str]          # task_id → last_updated_at
    ocmc_approvals: dict[str, str]      # approval_id → status

    # GitHub state
    github_prs: dict[str, str]          # pr_url → last_updated_at

    # Mapping
    plane_to_ocmc: dict[str, str]       # plane_issue_id → ocmc_task_id
    ocmc_to_plane: dict[str, str]       # ocmc_task_id → plane_issue_id
```

Persisted to `.fleet-sync-state.json` — survives daemon restarts.
On clean install, starts empty and builds up as items are synced.

---

## IaC State Persistence

> "We will also need to make it so that we can keep the IaC definition in sync
> as the plane evolve as the agent works, so that if we restart it will pick up
> where we left approximately or even perfectly."

### Export Script: `scripts/plane-export-state.sh`

Dumps current Plane state to config files:

```bash
./setup.sh export
```

**What it exports:**
- Projects (names, descriptions, emojis, settings) → updates `config/mission.yaml`
- Modules (names, descriptions, status, leads) → updates `config/mission.yaml`
- Labels → updates `config/mission.yaml`
- States → updates `config/mission.yaml`
- Members → updates `config/fleet-members.yaml`
- Cycles (active/upcoming) → updates `config/*-board.yaml`
- Pages (content) → updates `config/*-board.yaml`
- Issues (open ones) → exports to `config/plane-issues-export.yaml`
- Sync state → `.fleet-sync-state.json`

**What it does NOT export:**
- Closed/archived issues (historical)
- Activity logs
- Webhook logs
- User sessions

### Rebuild Recovery

```
1. ./setup.sh export           # Save current state
2. ./setup.sh uninstall        # Remove everything
3. ./setup.sh install           # Rebuild from configs
4. Result: Plane has all projects, modules, labels, states,
   members, cycles, pages, and open issues restored
```

The sync state file (`.fleet-sync-state.json`) tracks Plane↔OCMC mappings.
After rebuild, the sync worker re-establishes mappings on first cycle.

---

## Milestones

### M-SW01: Sync State Model

**File:** `fleet/core/sync_state.py` (NEW)

Define the `SyncState` dataclass. Persistence to JSON.
Load/save from `.fleet-sync-state.json`.
State includes: issue mappings, last-seen timestamps, conflict log.

### M-SW02: Plane Watcher

**File:** `fleet/core/plane_watcher.py` (NEW)

Polls Plane API for changes since last check:
- New issues
- State changes on existing issues
- New comments
- Cycle status changes
- Module updates

Uses the PlaneClient. Compares against SyncState to detect deltas.

### M-SW03: OCMC Watcher Enhancement

**File:** Update `fleet/cli/sync.py`

Enhance existing sync to emit deltas:
- Task status changes (with previous state)
- New approvals
- Agent online/offline transitions

Currently sync daemon just polls — needs to track state and detect changes.

### M-SW04: GitHub Watcher Enhancement

**File:** Update `fleet/core/remote_watcher.py`

Extend existing PR comment watcher to also detect:
- CI status changes (pass → fail, fail → pass)
- Merge events
- Review requests
- New PR labels

### M-SW05: Sync Engine — Bidirectional State Sync

**File:** `fleet/core/sync_engine.py` (NEW)

The core logic:
- Compare Plane state vs OCMC state
- Detect: new items, state changes, conflicts
- Apply sync rules (OCMC authoritative for agent work, Plane for project management)
- Emit events for each sync action

### M-SW06: Conflict Resolution

**File:** Part of `sync_engine.py`

Handle disagreements:
- State conflicts (Plane says X, OCMC says Y)
- Deletion conflicts (one side deleted, other still has it)
- Concurrent modifications (both updated within same sync window)
- Resolution: rules-based for common cases, flag PM for ambiguous ones

### M-SW07: Impediment Detection

**File:** `fleet/core/impediment_detector.py` (NEW)

Detect and flag:
- Offline agent with assigned work
- Stalled tasks (no progress for X hours)
- Aging PRs (no review for X hours)
- Resolved dependencies (auto-unblock)
- Sprint velocity alerts (behind schedule)

Emits alerts via event chains (IRC #alerts, ntfy urgent, PM heartbeat).

### M-SW08: Worker Daemon Integration

**File:** Update `fleet/cli/daemon.py`

Add `run_sync_worker(interval=15)` to the daemon gather.
Uses: PlaneWatcher, SyncEngine, ImpedimentDetector.
Emits: EventChains via ChainRunner.

### M-SW09: Plane State Export

**File:** `scripts/plane-export-state.sh` (NEW)

Export current Plane state → update config YAMLs.
Add `export` command to `setup.sh`.
Deterministic output (sorted, normalized) for clean git diffs.

### M-SW10: Audit Trail

**File:** Part of sync_engine.py

Every sync action logged:
- What changed, on which surface
- What action was taken
- Whether conflict was detected
- Resolution applied

Stored in `.fleet-sync-audit.jsonl` (append-only, rotated).
Queryable by the PM for sync health reports.

---

## Dependencies

```
M-SW01 (State model) → no deps
M-SW02 (Plane watcher) → M-SW01
M-SW03 (OCMC watcher) → M-SW01
M-SW04 (GitHub watcher) → M-SW01
M-SW05 (Sync engine) → M-SW01 + M-SW02 + M-SW03
M-SW06 (Conflict resolution) → M-SW05
M-SW07 (Impediment detection) → M-SW05
M-SW08 (Worker daemon) → M-SW05 + chain runner (M-SC02)
M-SW09 (State export) → M-SW01
M-SW10 (Audit trail) → M-SW05
```

### Depends on Other Milestones

- **M-SC02** (Chain runner) — worker emits chains, needs runner
- **M-SC04** (Plane MCP tools) — worker uses PlaneClient
- **M-PF08** (Webhooks) — Plane watcher can use webhooks when available

---

## Priority Order

1. **M-SW01** — State model (foundation for everything)
2. **M-SW02** — Plane watcher (detect Plane changes)
3. **M-SW05** — Sync engine (the core logic)
4. **M-SW08** — Worker daemon (wire into fleet)
5. **M-SW03** — OCMC watcher enhancement
6. **M-SW07** — Impediment detection
7. **M-SW06** — Conflict resolution
8. **M-SW09** — State export (IaC persistence)
9. **M-SW04** — GitHub watcher enhancement
10. **M-SW10** — Audit trail

---

## Total Milestone Count

All Plane-related milestones across all documents:

| Document | Prefix | Count | Focus |
|----------|--------|-------|-------|
| plane-full-configuration.md | M-PF | 9 | Basic setup (mostly done) |
| plane-skills-and-chains.md | M-SC | 8 | Chain runner, MCP tools, skills |
| plane-iac-evolution.md | M-P | 10 | Infrastructure evolution |
| plane-platform-maturity.md | M-PM | 10 | Rich content, personalization |
| plane-sync-worker.md | M-SW | 10 | Real-time cross-platform sync |
| plane-fleet-integration-architecture.md | — | 0 | Architecture reference (no milestones) |
| **Total** | | **47** | |

These 47 milestones represent the complete Plane integration from deployment
to production-grade, multi-fleet, bulletproof cross-platform synchronization.