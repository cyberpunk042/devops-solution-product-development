# Plane Skills, MCP Tools, and Chain Integration

**Date:** 2026-03-29
**Status:** Investigation complete — plan ready for execution
**Scope:** How agents interact with Plane, how chains bridge OCMC↔Plane, what skills are needed

---

## Investigation Findings

### What Exists

| Component | File | Status |
|-----------|------|--------|
| Event chain model | `fleet/core/event_chain.py` | Built — EventChain, Event, EventSurface, chain builders |
| Smart chains | `fleet/core/smart_chains.py` | Built — DispatchContext pre-compute |
| Heartbeat context | `fleet/core/heartbeat_context.py` | Built — HeartbeatBundle pre-compute |
| Notification router | `fleet/core/notification_router.py` | Built — classify + route events |
| Task routing | `fleet/core/routing.py` | Built — capability-based agent matching |
| Skill enforcement | `fleet/core/skill_enforcement.py` | Built — required tools per task type |
| Driver model | `fleet/core/driver.py` | Built — PM owns DSPD, AG owns NNRT |
| Plane REST client | `fleet/infra/plane_client.py` | Built — 387 lines, typed async |
| Plane CLI | `fleet/cli/plane.py` | Built — create/list/sync/status |
| Plane sync | `fleet/core/plane_sync.py` | Built — bidirectional OCMC↔Plane |
| Webhook handler | `dspd/webhooks.py` | Built — HMAC-SHA256, event dispatch |
| Fleet MCP tools | `fleet/mcp/tools.py` | Built — 13 tools |
| Claude Code skills | `.claude/skills/` | Built — 6 skills (communicate, plan, review, security, sprint, test) |

### What's Missing

| Component | Why It Matters |
|-----------|---------------|
| **Chain runner** (M154) | Chain builders exist but NOTHING EXECUTES them. MCP tools do individual API calls instead of emitting chains. |
| **Operation→chain mapping** (M155) | fleet_task_complete does 5 separate calls. Should emit ONE chain that publishes to all surfaces. |
| **Plane surface in chains** | EventSurface has INTERNAL/PUBLIC/CHANNEL/NOTIFY/META but NO PLANE surface. Chains can't sync to Plane. |
| **Plane MCP tools** | Agents have NO way to interact with Plane from inside a session. No plane_list_projects, plane_create_issue, etc. |
| **Plane skills** | No Claude Code skill for Plane operations. PM can't plan sprints in Plane from a heartbeat. |
| **Plane in heartbeat context** | HeartbeatBundle doesn't include Plane sprint data. PM wakes up blind to Plane state. |
| **Plane↔OCMC sync in chains** | When task completes in OCMC, chain should auto-sync to Plane. Not wired. |
| **Chain integration tests** (M156) | No end-to-end test that verifies events propagate across all surfaces. |

---

## User Vision

> "important to remember the plane place and yet how oc agent still work on ocmc,
> that's why we need smart tools, chains that will trigger multiple things for one
> call or one event and that will keep listening to all side and keep in sync for
> if I do a manual change or adding or task or information and such that everything
> is kept track of and triggering the right event that will wake the right agent or
> will influence it for its next heartbeat."

> "it should only call claude when needed otherwise do mcp / tool calls and whatever"

> "Where ever we can take this pattern to improve the work and the flow and
> the logic we will. Its very important that the AI focus on what it needs
> and doesn't waste time with needless tools call that can be pre-embedded."

> "we need to really make this strong."

---

## Architecture: How It Should Work

### Current Flow (Broken)

```
Agent calls fleet_task_complete()
  → 5 separate API calls inside the tool handler
  → MC task update
  → MC comment
  → GitHub PR (maybe)
  → IRC notification (maybe)
  → ntfy notification (maybe)
  → Plane: NOTHING (not synced)
```

### Target Flow (Chain-Based)

```
Agent calls fleet_task_complete()
  → Tool handler builds EventChain
  → Chain runner executes ALL events:
      INTERNAL: MC task→review, approval created, board memory
      PUBLIC: branch pushed, PR created
      CHANNEL: #fleet + #reviews IRC messages
      NOTIFY: ntfy notification
      PLANE: Plane issue updated to "In Review", comment posted
      META: metrics updated, sync tracked
  → One call, all surfaces, tolerant of partial failure
```

### Target Flow (PM Heartbeat with Plane)

```
PM agent heartbeat fires
  → HeartbeatBundle includes:
      - Assigned OCMC tasks
      - Chat messages mentioning PM
      - Plane sprint status (velocity, burn-down, blocked items)
      - Plane inbox (new items human created)
  → PM reads bundle, decides:
      - "3 new Plane items need OCMC tasks" → fleet_task_create × 3
      - "Sprint at 60%, 3 days left" → post velocity alert
      - "OCMC task done, update Plane" → chain handles it
```

### Target Flow (Human Creates Plane Issue)

```
Human creates issue in Plane UI
  → Plane webhook fires
  → dspd/webhooks.py receives, verifies HMAC
  → Event handler:
      - If label "auto-dispatch": PM's next heartbeat includes it
      - If priority "urgent": IRC #fleet alert
      - Always: tracked for next Plane→OCMC sync
```

---

## Milestones

### M-SC01: Add PLANE Surface to Event Chains

**File:** `fleet/core/event_chain.py`

Add `EventSurface.PLANE` to the enum. Update chain builders:
- `build_task_complete_chain`: add PLANE event (update Plane issue state)
- `build_alert_chain`: add PLANE event (post comment on related Plane issue)
- `build_sprint_complete_chain`: add PLANE event (update cycle, post velocity)

**Acceptance:** Chain builders produce PLANE events. No runner yet — just the model.

### M-SC02: Build Chain Runner

**File:** `fleet/core/chain_runner.py` (NEW)

Engine that takes an EventChain and executes each event:
- INTERNAL → MCClient calls
- PUBLIC → GHClient calls
- CHANNEL → IRCClient calls
- NOTIFY → NtfyClient calls
- PLANE → PlaneClient calls
- META → metrics/logging

Failure handling: if one surface fails, others still execute.
Logging: every event execution logged with success/failure.

**Acceptance:** `await run_chain(chain)` executes all events, returns ChainResult.

### M-SC03: Wire MCP Tools to Emit Chains

**File:** `fleet/mcp/tools.py`

Replace individual API calls in tool handlers with chain emission:
- `fleet_task_complete` → `build_task_complete_chain()` → `run_chain()`
- `fleet_alert` → `build_alert_chain()` → `run_chain()`
- `fleet_escalate` → build escalation chain → `run_chain()`

**Acceptance:** MCP tools emit chains instead of individual calls. All surfaces notified.

### M-SC04: Plane MCP Tools for Agents

**File:** `fleet/mcp/tools.py` (add to existing)

New MCP tools agents can call:
- `fleet_plane_list_projects()` — list Plane projects
- `fleet_plane_list_sprint(project)` — current sprint with velocity
- `fleet_plane_list_modules(project)` — list epics/modules
- `fleet_plane_sync()` — trigger Plane↔OCMC sync
- `fleet_plane_update_issue(issue_id, state, comment)` — update Plane issue

All use PlaneClient internally. Only PM should write (enforce via agent_roles.py).

**Acceptance:** PM agent can read Plane sprint and update issues from a heartbeat session.

### M-SC05: Plane Skill for PM Agent

**File:** `.claude/skills/fleet-plane/SKILL.md` (NEW)

Claude Code skill that teaches the PM how to:
1. Read current sprint status from Plane
2. Break down epics into tasks (create in OCMC, not Plane)
3. Update Plane issues when OCMC tasks complete
4. Post sprint reports with velocity data
5. Manage cycle lifecycle (start/close sprints)

References the Plane MCP tools from M-SC04.

**Acceptance:** PM agent has fleet-plane skill installed and can use it in heartbeats.

### M-SC06: Plane in Heartbeat Context

**File:** `fleet/core/heartbeat_context.py`

Add Plane data to HeartbeatBundle for PM agent:
- Current sprint name, progress (done/total), velocity
- New Plane items since last heartbeat (human-created)
- Blocked Plane items
- Sprint end date + days remaining

Only for PM (and maybe fleet-ops). Other agents don't need Plane context.

**Acceptance:** PM heartbeat bundle includes Plane sprint data. No extra tool calls needed.

### M-SC07: Plane↔OCMC Sync in Orchestrator

**File:** `fleet/cli/orchestrator.py`

Add a new step to the orchestrator cycle:
- After DISPATCH step: run Plane→OCMC sync (new Plane items → OCMC tasks)
- After EVALUATE PARENTS step: run OCMC→Plane sync (done tasks → Plane updated)

Uses existing `plane_sync.py` logic. Configurable interval (not every cycle — maybe every 5 cycles).

**Acceptance:** Orchestrator keeps Plane and OCMC in sync automatically.

### M-SC08: Chain Integration Test

**File:** `fleet/tests/core/test_chain_runner.py` (NEW)

End-to-end test:
1. Build a task_complete chain
2. Execute with mock clients
3. Verify ALL surfaces received correct events (INTERNAL + PUBLIC + CHANNEL + NOTIFY + PLANE + META)
4. Verify partial failure handling (one surface fails, others succeed)

**Acceptance:** Test passes. Chain runner verified across all surfaces.

---

## Dependencies

```
M-SC01 (PLANE surface) → no deps
M-SC02 (Chain runner) → M-SC01
M-SC03 (Wire MCP tools) → M-SC02
M-SC04 (Plane MCP tools) → no deps (can parallel with M-SC01-03)
M-SC05 (Plane skill) → M-SC04
M-SC06 (Plane in heartbeat) → M-SC04
M-SC07 (Sync in orchestrator) → M-SC04
M-SC08 (Integration test) → M-SC02 + M-SC03
```

### Parallel Tracks

**Track A (Chains):** M-SC01 → M-SC02 → M-SC03 → M-SC08
**Track B (Plane access):** M-SC04 → M-SC05 + M-SC06 + M-SC07

Both tracks can run in parallel. They converge when MCP tools emit chains that include PLANE events.

---

## Priority Order

1. **M-SC04** — Plane MCP tools (unblocks PM agent immediately)
2. **M-SC06** — Plane in heartbeat context (PM gets sprint data without tool calls)
3. **M-SC05** — Plane skill for PM (teaches PM how to use the tools)
4. **M-SC01** — PLANE surface in chains (model extension)
5. **M-SC02** — Chain runner (the engine)
6. **M-SC03** — Wire MCP tools to chains (the integration)
7. **M-SC07** — Sync in orchestrator (automatic flow)
8. **M-SC08** — Integration test (verification)

Rationale: PM agent access to Plane is the immediate blocker. Chains are important but the PM can function with direct Plane tool calls while the chain infrastructure is built.

---

## Impact on AICP Epics

The AICP epic descriptions need to reference this chain architecture:
- Stage 2 (routing) needs to understand that some operations are CHAINS, not single calls
- Stage 3 (offload) needs to know which chain events can go to LocalAI
- The inference router needs to work WITH the chain runner, not replace it

The PM agent reading the AICP epics needs to know:
- The chain system exists (models built, runner missing)
- Skills exist for fleet operations (6 skills) but not for Plane
- The smart chain pattern (pre-compute, bundle, no wasted calls) applies to Plane too
- The routing table (what goes to LocalAI vs Claude) applies to chain events too