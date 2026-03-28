# DSPD — Technical Architecture

**Version:** 0.1 (Phase 0 Foundation)  
**Author:** architect agent  
**Date:** 2026-03-28  
**Status:** Draft — approved by task `15554969`

---

## 1. System Overview

DSPD (DevOps Solution Product Development) is a project management surface for the OpenClaw Fleet, built on self-hosted [Plane](https://github.com/makeplane/plane).

The fleet runs three distinct surfaces with different roles:

```
┌──────────────────────────────────────────────────────────────────────┐
│  PLANE (DSPD)                        Project Management Surface       │
│  sprints · cycles · modules · epics · analytics · wiki               │
│  Primary users: human, PM agent                                       │
└─────────────────────────────┬────────────────────────────────────────┘
                              │  PM agent bridges
┌─────────────────────────────▼────────────────────────────────────────┐
│  OCMC (OpenClaw Mission Control)     Agent Operations Surface         │
│  task dispatch · heartbeat · board memory · approvals                 │
│  Primary users: fleet agents                                          │
└─────────────────────────────┬────────────────────────────────────────┘
                              │  all agents
┌─────────────────────────────▼────────────────────────────────────────┐
│  GitHub                               Code Surface                    │
│  PRs · CI · code review · releases                                    │
│  Primary users: human, all agents                                     │
└──────────────────────────────────────────────────────────────────────┘

Supporting: IRC (#fleet, #reviews, #alerts) — real-time event stream
```

---

## 2. Plane Self-Hosting (Docker Compose)

### 2.1 Service Architecture

Plane requires six services:

| Service | Image | Role | Port |
|---------|-------|------|------|
| `plane-web` | makeplane/plane-frontend | React UI | 3001 (internal) |
| `plane-api` | makeplane/plane-backend | Django REST API | 8083 (internal) |
| `plane-worker` | makeplane/plane-backend | Celery async worker | — |
| `plane-beat` | makeplane/plane-backend | Celery beat scheduler | — |
| `plane-db` | postgres:15 | Primary database | 5433 (internal) |
| `plane-redis` | redis:7 | Cache + message broker | 6380 (internal) |
| `plane-proxy` | nginx | Reverse proxy (public) | **8080** (host) |

### 2.2 Port Allocation

Current host port assignments to avoid collisions:

| Service | Host Port | Purpose |
|---------|-----------|---------|
| OCMC API | 8000 | Mission Control REST API |
| OCMC UI | 3000 | Mission Control web interface |
| Plane | **8080** | Plane UI + API (nginx proxy) |
| Plane DB | 5433 | PostgreSQL (internal, not exposed by default) |

### 2.3 Deployment Layout

```
devops-solution-product-development/
└── docker/
    ├── docker-compose.plane.yml   # Plane services
    ├── .env.plane.example         # Environment template
    └── nginx.plane.conf           # Nginx proxy config
```

Plane is deployed in a **separate compose file** from OCMC to maintain isolation. OCMC and Plane do NOT share a PostgreSQL instance — operational coupling risk is too high.

### 2.4 Data Persistence

```
/var/lib/dspd/
├── postgres/     # Plane PostgreSQL data volume
└── redis/        # Redis persistence (optional)
```

### 2.5 Security Considerations

- Plane UI/API exposed on port 8080, accessible only via localhost or Tailscale
- Plane API key stored in `.env` (gitignored), never in code
- Nginx proxy terminates all requests; API is not directly exposed
- Webhooks from Plane are HMAC-SHA256 signed — fleet verifies signature before processing
- Plane DB port NOT exposed to host in production

---

## 3. Fleet CLI Integration

### 3.1 Package Structure

```
fleet/
├── infra/
│   └── plane_client.py      # Plane REST API client
└── cli/
    └── plane.py             # CLI commands: plan create/list/sync
```

### 3.2 `plane_client.py` — API Client

Thin async HTTP wrapper around Plane's REST API. All methods accept and return typed Pydantic models.

```python
class PlaneClient:
    """Authenticated client for Plane REST API."""

    def __init__(self, base_url: str, api_key: str, workspace_slug: str) -> None: ...

    # Work items
    async def create_work_item(self, project_id: str, payload: WorkItemCreate) -> WorkItem: ...
    async def get_work_item(self, project_id: str, issue_id: str) -> WorkItem: ...
    async def update_work_item(self, project_id: str, issue_id: str, patch: WorkItemPatch) -> WorkItem: ...
    async def list_work_items(self, project_id: str, filters: WorkItemFilters | None = None) -> list[WorkItem]: ...

    # Cycles (sprints)
    async def list_cycles(self, project_id: str) -> list[Cycle]: ...
    async def get_current_cycle(self, project_id: str) -> Cycle | None: ...
    async def add_to_cycle(self, project_id: str, cycle_id: str, issue_ids: list[str]) -> None: ...

    # Modules
    async def list_modules(self, project_id: str) -> list[Module]: ...

    # Projects
    async def list_projects(self) -> list[Project]: ...
    async def get_project(self, project_id: str) -> Project: ...
```

**Configuration** is loaded from environment:
```
PLANE_BASE_URL=http://localhost:8080
PLANE_API_KEY=plane_api_<token>
PLANE_WORKSPACE_SLUG=openclaw-fleet
```

### 3.3 CLI Commands (`fleet plan`)

```
fleet plan create "title" [--project <id>] [--priority high] [--cycle current]
fleet plan list   [--project <id>] [--cycle current] [--state active]
fleet plan sync   [--project <id>] [--dry-run]
fleet plan status <work-item-id>
```

| Command | Description |
|---------|-------------|
| `fleet plan create` | Create a Plane work item (optionally add to current cycle) |
| `fleet plan list` | List work items in current sprint for a project |
| `fleet plan sync` | Sync Plane work items → OCMC tasks (one-way, PM agent-driven) |
| `fleet plan status` | Show the current state of a Plane work item |

---

## 4. PM Agent: The Bridge (Plane ↔ OCMC)

### 4.1 Role

The **project-manager agent** is the single actor that understands both surfaces. It is not a passive bridge — it makes decisions about prioritization, sprint composition, and dispatch.

It has access to:
- Plane via MCP server (native tools for work items, cycles, modules)
- OCMC via fleet tools (`fleet_task_accept`, `fleet_task_complete`, etc.)
- IRC for real-time escalation

### 4.2 Data Flow

```
1. PLAN
   Human creates work items in Plane (sprints, epics, stories, tasks)
         │
         ▼
2. DISPATCH
   PM agent reads Plane (via MCP or fleet CLI)
   PM creates corresponding OCMC tasks → assigns to agents
         │
         ▼
3. EXECUTE
   Fleet agents execute in OCMC
   Agents push code, open PRs, post comments
         │
         ▼
4. CLOSE
   PM detects OCMC task completed (heartbeat or webhook)
   PM updates Plane work item: state → done, adds PR link as comment
         │
         ▼
5. REVIEW
   Human sees Plane burn-down updated, PR ready in GitHub
   Human merges PR, closes cycle in Plane
```

### 4.3 Sync Model (Phase 1)

**One-way: Plane → OCMC (PM-initiated)**

The PM agent is the sole writer on the OCMC side for work originating in Plane. Agents do not write back to Plane directly — PM mediates all updates.

Future phase: bidirectional sync (OCMC status changes → Plane state transitions via webhook).

### 4.4 ID Cross-Reference

PM stores a mapping of Plane issue ID ↔ OCMC task ID. This mapping is persisted in:
- OCMC task custom field: `plane_issue_id` (to be added to OCMC board schema)
- Or board memory entry with tags `[plane-sync, project:<name>]`

---

## 5. Plane MCP Integration

Plane ships with a built-in MCP server. The PM agent connects to it to get native tool access:

```json
{
  "mcpServers": {
    "plane": {
      "command": "plane-mcp",
      "args": ["--workspace", "openclaw-fleet"],
      "env": {
        "PLANE_API_KEY": "<token>",
        "PLANE_BASE_URL": "http://localhost:8080"
      }
    }
  }
}
```

MCP tools the PM agent gains:
- `plane_create_issue` — create work items
- `plane_update_issue` — update state, assignee, priority
- `plane_list_issues` — query current sprint
- `plane_create_cycle` — create a sprint
- `plane_list_cycles` — list sprints + burn-down data

The PM agent uses MCP tools during heartbeats to check sprint health and dispatch overdue items.

---

## 6. Webhooks (Plane → Fleet)

Plane emits webhooks for all lifecycle events. The fleet processes these to trigger PM agent actions without polling.

### 6.1 Webhook Endpoint

```
POST http://localhost:8000/api/v1/webhooks/plane
```

Registered in Plane workspace settings. OCMC receives and verifies the HMAC-SHA256 signature, then routes to the PM agent's event queue.

### 6.2 Events of Interest

| Event | Plane payload | Fleet action |
|-------|--------------|-------------|
| `issue.created` | New work item | PM may auto-dispatch to OCMC |
| `issue.updated` | State/priority change | PM updates OCMC task if mapped |
| `issue.deleted` | Work item removed | PM closes mapped OCMC task |
| `cycle.started` | Sprint begins | PM posts sprint plan to IRC #fleet |
| `cycle.completed` | Sprint ends | PM posts velocity report to board memory |
| `comment.created` | Comment on issue | PM notifies relevant agent via OCMC comment |

### 6.3 Signature Verification

```python
import hmac, hashlib

def verify_plane_webhook(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

---

## 7. Service Dependencies

```
Plane API ──────────────────────── depends on ──── Plane DB (PostgreSQL)
Plane API ──────────────────────── depends on ──── Plane Redis
Plane Worker ───────────────────── depends on ──── Plane DB + Redis
Plane Beat ─────────────────────── depends on ──── Plane DB + Redis
Plane Web ──────────────────────── depends on ──── Plane API (at runtime)
Nginx Proxy ────────────────────── depends on ──── Plane API + Plane Web

Fleet CLI (plane_client.py) ──────── calls ──────── Plane API (HTTP)
PM agent (Plane MCP) ─────────────── calls ──────── Plane API (via MCP server)
OCMC webhook receiver ─────────────── receives ───── Plane → OCMC webhooks
```

Startup order:
1. `plane-db`, `plane-redis`
2. `plane-api` (migrations run as entrypoint)
3. `plane-worker`, `plane-beat`
4. `plane-web`
5. `plane-proxy` (nginx)

---

## 8. Network Topology

```
Host machine (WSL2 / Linux)
│
├── localhost:8000  →  OCMC API (existing)
├── localhost:3000  →  OCMC UI (existing)
└── localhost:8080  →  Plane (nginx proxy)
                           ├── /           → plane-web (React)
                           └── /api/       → plane-api (Django REST)

Internal Docker network: dspd_internal
  plane-api, plane-worker, plane-beat, plane-web, plane-db, plane-redis
  (not reachable from OCMC containers directly — by design)
```

Tailscale provides remote access to both OCMC and Plane without exposing them to the public internet.

---

## 9. Open Architecture Questions

| # | Question | Decision |
|---|----------|----------|
| Q1 | Shared or separate Docker Compose? | **Separate** — `docker-compose.plane.yml` — cleaner isolation |
| Q2 | Shared PostgreSQL? | **No** — separate `plane-db` container — operational independence |
| Q3 | Sync direction (v1)? | **One-way: Plane → OCMC** — PM-initiated, no auto-reverse |
| Q4 | Plane MCP vs fleet CLI? | **Both** — MCP for PM agent; CLI for human/scripts |
| Q5 | Existing OCMC task migration? | **Not in scope v1** — fresh start in Plane, OCMC stays for agent ops |
| Q6 | PM agent heartbeat vs event-driven? | **Both** — webhook for real-time; heartbeat for sprint health checks |

---

## 10. References

- [Plane GitHub](https://github.com/makeplane/plane)
- [Plane API Docs](https://developers.plane.so/)
- [Fleet Milestone: dspd-plane-integration.md](../../../openclaw-fleet/docs/milestones/dspd-plane-integration.md)
- [OCMC Mission Control](http://localhost:3000)
