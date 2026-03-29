# DSPD — Project Requirements

**Version:** 0.1 (Phase 0 Foundation)  
**Author:** architect agent  
**Date:** 2026-03-28  
**Status:** Draft

---

## 1. Plane Features We Use

### 1.1 Core Entities

| Entity | Plane Term | How We Use It |
|--------|-----------|---------------|
| Project | Project | One Plane project per fleet project: `fleet`, `nnrt`, `dspd`, `aicp` |
| Sprint | Cycle | 2-week cycles per project; PM agent manages start/end |
| Epic | Module | Group related stories/tasks across sprints |
| Work item | Issue | Atomic unit of deliverable work; maps 1:1 to OCMC task when dispatched |
| Story points | Estimate | 1/2/3/5/8/13 (Fibonacci); set by PM agent on dispatch |
| Label | Label | `agent:<name>`, `project:<name>`, `blocked`, `spec-required` |
| State | State | Custom per project (see §1.3) |
| Page | Page | Specs, architecture docs, playbooks — Plane's wiki layer |

### 1.2 Plane Features Enabled

| Feature | Used For |
|---------|----------|
| Cycles (Sprints) | 2-week iterations with burn-down |
| Modules | Epics and feature groups |
| Timeline view | Cross-project dependency visualization |
| Analytics | Velocity, burn-down, agent productivity charts |
| Pages | Living docs (specs, architecture, playbooks) |
| Webhooks | Real-time event push → fleet webhook receiver |
| API | fleet CLI + PM agent integration |
| MCP server | PM agent native tool access |

### 1.3 Custom State Workflows

**Fleet project (`fleet`):**

| State | Color | Meaning |
|-------|-------|---------|
| `backlog` | grey | Not yet scheduled |
| `todo` | blue | In current sprint, not started |
| `dispatched` | yellow | OCMC task created, agent working |
| `in-review` | orange | PR open, awaiting merge |
| `done` | green | Merged, deployed |
| `cancelled` | red | Dropped |

**NNRT project (`nnrt`):**

| State | Meaning |
|-------|---------|
| `backlog` | Not scheduled |
| `spec-required` | Pass needs spec before implementation |
| `spec-ready` | Spec written, ready for implementation |
| `in-progress` | Agent implementing |
| `review` | PR open |
| `done` | Merged |
| `cancelled` | Dropped |

### 1.4 Labels

Standard labels applied fleet-wide:

| Label | Meaning |
|-------|---------|
| `agent:architect` | Assigned to / owned by architect |
| `agent:software-engineer` | Assigned to software-engineer |
| `agent:devops` | Assigned to devops |
| `agent:pm` | PM owns this (meta-task) |
| `spec-required` | Must have spec doc before code |
| `blocked` | Externally blocked |
| `infra` | Infrastructure change |
| `docs` | Documentation only |
| `test` | Test-only change |

---

## 2. Fleet CLI Commands

### 2.1 Required Commands (MVP)

| Command | Description |
|---------|-------------|
| `fleet plan create "title" [--project] [--priority] [--cycle current]` | Create Plane work item |
| `fleet plan list [--project] [--cycle current] [--state]` | List sprint items |
| `fleet plan sync [--project] [--dry-run]` | Sync Plane → OCMC (PM-dispatched) |
| `fleet plan status <work-item-id>` | Show Plane work item state |
| `fleet plan close <work-item-id> --pr <url>` | Mark done, attach PR |

### 2.2 Configuration

Commands read from environment:

```
PLANE_BASE_URL=http://localhost:8080
PLANE_API_KEY=plane_api_<token>      # from .env (gitignored)
PLANE_WORKSPACE_SLUG=openclaw-fleet
PLANE_DEFAULT_PROJECT=fleet          # optional default project slug
```

### 2.3 Future Commands (Phase 2+)

| Command | Phase |
|---------|-------|
| `fleet sprint start [--project]` | Phase 2 |
| `fleet sprint close [--project]` | Phase 2 |
| `fleet sprint report [--project]` | Phase 2 |
| `fleet plan import --from ocmc` | Phase 3 |

---

## 3. MCP Integration Requirements

### 3.1 PM Agent Tool Requirements

The project-manager agent MUST have access to these Plane MCP tools:

| Tool | Purpose |
|------|---------|
| `plane_list_projects` | Discover all fleet projects in Plane |
| `plane_list_cycles` | Get current + upcoming sprints |
| `plane_get_cycle` | Get burn-down and velocity for a sprint |
| `plane_list_issues` | Query work items with filters |
| `plane_create_issue` | Create new work item |
| `plane_update_issue` | Update state, assignee, priority, estimate |
| `plane_add_to_cycle` | Add work item to a sprint |
| `plane_create_comment` | Add PR link or agent result as comment |
| `plane_list_modules` | Get epics/modules |

### 3.2 MCP Server Config

The Plane MCP server must be configured in the PM agent's OpenClaw node config before Phase 3 can begin. Configuration method TBD (depends on Plane MCP server packaging).

### 3.3 Tool Use Policy

- PM agent is the **sole agent** that writes to Plane
- Other agents interact with Plane **only through task comments directed at PM**
- PM writes PR links, status updates, and velocity data back to Plane

---

## 4. Webhooks

### 4.1 Webhook Registration

One webhook registered in Plane workspace settings:

```
URL: http://localhost:8000/api/v1/webhooks/plane
Events: issue.*, cycle.*, comment.created
Secret: <HMAC secret stored in .env>
```

### 4.2 Events and Handlers

| Event | Handler | Action |
|-------|---------|--------|
| `issue.created` | `pm_agent` | Optionally auto-dispatch if label `auto-dispatch` present |
| `issue.updated` (state→done) | `pm_agent` | Close mapped OCMC task if exists |
| `issue.updated` (priority↑) | `pm_agent` | Alert IRC #fleet if priority becomes urgent |
| `issue.deleted` | `pm_agent` | Cancel mapped OCMC task |
| `cycle.started` | `pm_agent` | Post sprint kickoff summary to IRC #fleet |
| `cycle.completed` | `pm_agent` | Post velocity report to board memory |
| `comment.created` | `pm_agent` | Route @mention comments to relevant agents via OCMC |

### 4.3 Signature Verification (Required)

All incoming webhook requests MUST be verified via HMAC-SHA256 before processing. Unverified requests are silently dropped.

---

## 5. MVP vs Future Phases

### Phase 0 — Foundation ✅ COMPLETE

Deliverables:
- [x] Architecture document (`docs/architecture.md`)
- [x] Requirements document (`docs/requirements.md`)
- [x] `pyproject.toml` project config
- [x] `CLAUDE.md` agent conventions
- [x] `docker-compose.plane.yaml` (12 services)
- [x] `plane.env.example` (all credentials marked ⚠️ CHANGE)

Done when: All documents written, project structure exists. ✅

### Phase 1 — Self-Host Plane (M184–M187) — IaC BUILT, needs deploy

Deliverables:
- [x] `docker-compose.plane.yaml` — working Plane stack (12 services)
- [x] `docker/nginx.plane.conf` — reverse proxy config
- [x] `setup.sh` — IaC: install/start/stop/status/validate/upgrade/uninstall
- [x] `scripts/plane-configure.sh` — superuser, workspace, API token, god-mode
- [x] `scripts/plane-seed-mission.sh` — reads config/mission.yaml, creates all structure
- [x] `config/mission.yaml` — 4 projects (OF, NNRT, DSPD, AICP), per-project states, modules, labels, estimates
- [x] `config/*-board.yaml` — per-project pages, cycles, epic details with acceptance criteria
- [ ] Plane deployed and running (`./setup.sh install`)
- [ ] Workspace + 4 projects verified in Plane UI
- [ ] API validation passes 11/11 (`plane-validate-api.sh`)
- [ ] Startup verification passes 15/15 (`plane-startup-verify.sh`)

Done when: `fleet plan list-projects` returns 4 projects from a live Plane instance.

### Phase 2 — Fleet CLI (M188–M191) — CODE DONE, needs live test

Deliverables:
- [x] `fleet/infra/plane_client.py` — typed async API client (projects, states, cycles, issues CRUD)
- [x] `fleet/cli/plane.py` — `create / list / sync / status / list-cycles / list-states` commands
- [x] `fleet/core/plane_sync.py` — bidirectional Plane ↔ OCMC sync
- [x] Unit tests: 18 passing (test_plane_client.py, test_plane_sync.py)
- [ ] `fleet plan sync` verified end-to-end against live instances
- [ ] PM agent marks OCMC done → PM updates Plane state (live test)

Done when: End-to-end flow tested: Plane item → OCMC task → agent completes → Plane state updated.

### Phase 3 — MCP + Webhooks (M192–M194) — CODE DONE, needs live test

Deliverables:
- [x] `dspd/webhooks.py` — HMAC-SHA256 verification, event handlers, ASGI receiver
- [x] `scripts/plane-setup-webhooks.sh` — register webhook + HMAC secret in Plane
- [x] Unit tests: test_webhooks.py (signature, parsing, dispatch)
- [ ] Plane MCP server researched and configured for PM agent
- [ ] PM agent uses MCP tools for sprint planning (live)
- [ ] Webhook handler operational against live Plane events

Done when: PM agent can read sprint, dispatch items, and update Plane from a single heartbeat loop.

### Phase 4 — Full DSPD (M195–M199) — NOT STARTED

Deliverables:
- [x] Multi-project: config/mission.yaml defines OF, NNRT, AICP, DSPD with modules
- [ ] Plane deployed with all 4 projects live
- [ ] Cross-project dependency mapping in Timeline view
- [ ] Velocity + burn-down tracking per project
- [ ] Analytics dashboard capturing agent productivity
- [ ] DSPD v1.0 milestone cut

Done when: All active fleet projects visible in Plane with live sprint tracking.

---

## 6. Non-Requirements (Explicitly Out of Scope)

| Item | Reason |
|------|--------|
| Replacing OCMC with Plane | OCMC and Plane have different roles; both stay |
| Agents writing to Plane directly | PM is the sole Plane writer; reduces coupling |
| Public internet exposure | Fleet is internal; Tailscale for remote access |
| Plane Cloud (SaaS) | Self-hosted only for cost and data control |
| Custom Plane fork | Use upstream; contribute upstream if needed |

---

## 7. Acceptance Criteria (Phase 0)

- [ ] `docs/architecture.md` exists and covers all required sections
- [ ] `docs/requirements.md` exists and covers Plane features, CLI, MCP, webhooks, MVP
- [ ] `pyproject.toml` is valid Python project config (3.11+, correct dependencies)
- [ ] `CLAUDE.md` covers project conventions for any agent working on DSPD
- [ ] Follow-up tasks proposed for PM agent to pick up
