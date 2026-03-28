# Plane Setup Guide

**Version:** 1.0  
**Date:** 2026-03-28  
**Author:** technical-writer agent  
**Task:** 263bf5e4

This document covers the complete Plane setup for the OpenClaw Fleet: architecture, multi-fleet model, configuration reference, IaC guide, new fleet onboarding, state mapping, and troubleshooting.

---

## Table of Contents

1. [Architecture: Plane + OCMC + Fleet](#1-architecture-plane--ocmc--fleet)
2. [Multi-Fleet Model](#2-multi-fleet-model)
3. [Configuration Reference](#3-configuration-reference)
4. [IaC Guide: plane-configure.sh](#4-iac-guide-plane-configuresh)
5. [New Fleet Onboarding](#5-new-fleet-onboarding)
6. [State Mapping Reference](#6-state-mapping-reference)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Architecture: Plane + OCMC + Fleet

### 1.1 Three Surfaces, Three Roles

The OpenClaw Fleet operates across three distinct surfaces. Each surface has a defined role — do not conflate them.

```
┌──────────────────────────────────────────────────────────────────────┐
│  PLANE (DSPD)                        Project Management Surface       │
│  sprints · cycles · modules · epics · analytics · wiki               │
│  Primary users: human, PM agent                                       │
│  Port: 8080                                                           │
└─────────────────────────────┬────────────────────────────────────────┘
                              │  PM agent is the sole bridge
┌─────────────────────────────▼────────────────────────────────────────┐
│  OCMC (OpenClaw Mission Control)     Agent Operations Surface         │
│  task dispatch · heartbeat · board memory · approvals                 │
│  Primary users: fleet agents                                          │
│  Port: 8000 (API), 3000 (UI)                                         │
└─────────────────────────────┬────────────────────────────────────────┘
                              │  all agents
┌─────────────────────────────▼────────────────────────────────────────┐
│  GitHub                               Code Surface                    │
│  PRs · CI · code review · releases                                    │
│  Primary users: human, all agents                                     │
└──────────────────────────────────────────────────────────────────────┘

Supporting: IRC (#fleet, #reviews, #alerts) — real-time event stream
```

### 1.2 How They Connect

```
Human
  │  creates work items in Plane (sprints, epics, stories)
  ▼
Plane ──[Plane MCP / fleet CLI]──► PM agent
                                        │  reads Plane sprint
                                        │  creates OCMC tasks
                                        ▼
                                    OCMC board
                                        │  dispatches to agents
                                        ▼
                                    Fleet agents
                                        │  execute, open PRs
                                        ▼
                                    PM agent
                                        │  detects completion
                                        │  updates Plane issue state
                                        ▼
                                    Plane (issue → Done)
                                        │
                                        ▼
                                    Human reviews burn-down, merges PRs
```

### 1.3 The PM Agent as Bridge

The **project-manager agent** is the sole actor that speaks to both Plane and OCMC. No other agent writes to Plane directly.

| PM Agent Action | Trigger | What it does |
|-----------------|---------|--------------|
| Sprint dispatch | Heartbeat / sprint start | Reads Plane cycle → creates OCMC tasks |
| Progress update | OCMC task heartbeat | Marks Plane issue `in-progress` |
| Completion sync | OCMC task done | Updates Plane issue state → `Done`, adds PR link |
| Sprint report | Cycle end / cron | Posts velocity report to #fleet, board memory |

### 1.4 Docker Service Architecture

Plane requires 13 services, all in a dedicated compose file:

| Service | Image | Role | Internal Port |
|---------|-------|------|---------------|
| `plane-proxy` | nginx | Reverse proxy — sole external entry point | **8080 (host)** |
| `plane-web` | makeplane/plane-frontend | React UI | 3001 |
| `plane-space` | makeplane/plane-space | Public spaces app | 3002 |
| `plane-admin` | makeplane/plane-admin | Admin panel | 3003 |
| `plane-live` | makeplane/plane-live | Real-time collab server | 3004 |
| `plane-api` | makeplane/plane-backend | Django REST API | 8000 |
| `plane-worker` | makeplane/plane-backend | Celery async worker | — |
| `plane-beat` | makeplane/plane-backend | Celery scheduler | — |
| `plane-migrator` | makeplane/plane-backend | DB migrations (init only) | — |
| `plane-db` | postgres:15 | PostgreSQL database | 5432 (internal) |
| `plane-redis` | valkey:7.2 | Cache + message queue | 6379 (internal) |
| `plane-mq` | rabbitmq:3.13 | Task queue (Celery) | 5672 (internal) |
| `plane-minio` | minio/minio | Object storage (file uploads) | 9000 (internal) |

**Key design decisions:**
- Plane runs in `docker-compose.plane.yaml` — completely separate from OCMC's compose file
- No shared PostgreSQL between Plane and OCMC — each has its own database container
- Only `plane-proxy` (nginx) is exposed on the host (port 8080)
- Internal services communicate on Docker network `plane-net` — isolated from OCMC containers

### 1.5 Port Allocation (Host)

| Service | Host Port | Reserved By |
|---------|-----------|-------------|
| OCMC API | 8000 | OCMC |
| OCMC UI | 3000 | OCMC |
| **Plane** | **8080** | DSPD |

Do not change these ports without updating `CLAUDE.md` and all scripts.

---

## 2. Multi-Fleet Model

### 2.1 One Plane, Multiple Fleets

A single Plane instance can serve multiple independent fleets. Each fleet gets its own **Workspace** in Plane, providing full isolation of work items, members, and settings.

```
Plane instance (localhost:8080)
│
├── Workspace: openclaw-fleet          ← Fleet 1 (main fleet)
│   ├── Project: fleet
│   ├── Project: nnrt
│   ├── Project: dspd
│   └── Project: aicp
│
└── Workspace: second-fleet            ← Fleet 2 (future)
    ├── Project: some-project
    └── Project: another-project
```

### 2.2 Workspace Isolation

Workspaces in Plane are fully isolated:
- Members of one workspace cannot see another's work items
- Each workspace has its own API keys, states, labels, and cycles
- The PM agent for Fleet 1 uses Fleet 1's API key (scoped to `openclaw-fleet` workspace)
- The PM agent for Fleet 2 uses a separate API key (scoped to `second-fleet` workspace)

### 2.3 Shared Infrastructure

Both fleets share:
- The same Plane Docker stack (`docker-compose.plane.yaml`)
- The same PostgreSQL instance (`plane-db` container, different schemas per workspace)
- The same nginx proxy on port 8080

Neither fleet shares:
- API keys
- OCMC boards (each fleet has its own OCMC board)
- Agent workspaces

### 2.4 Multi-Fleet Configuration

Each fleet's PM agent needs its own environment variables:

**Fleet 1 (`~/.env` for openclaw-fleet PM agent):**
```bash
PLANE_BASE_URL=http://localhost:8080
PLANE_API_KEY=plane_api_<fleet1-token>
PLANE_WORKSPACE_SLUG=openclaw-fleet
```

**Fleet 2 (`~/.env` for second-fleet PM agent):**
```bash
PLANE_BASE_URL=http://localhost:8080
PLANE_API_KEY=plane_api_<fleet2-token>
PLANE_WORKSPACE_SLUG=second-fleet
```

Both PM agents call the same Plane URL; their API keys scope them to their respective workspaces.

### 2.5 Admin Separation

The Plane superuser (`admin@fleet.local`) is a shared admin account for infrastructure management. Each fleet's API key belongs to a per-workspace user, not the superuser. This limits blast radius if a fleet's key is compromised.

---

## 3. Configuration Reference

### 3.1 Workspace Settings

Created by `scripts/plane-configure.sh`. Verify at `http://localhost:8080/settings/`.

| Setting | Value | Notes |
|---------|-------|-------|
| Workspace name | `Fleet` | Display name |
| Workspace slug | `openclaw-fleet` | URL-safe identifier used in all API calls |
| Organization size | `2-10` | Configuration only |
| Owner | `admin@fleet.local` | Superuser account |

### 3.2 Project Configuration

Each project has independent states, labels, and estimates.

**Standard projects:**

| Project | Identifier | Purpose |
|---------|------------|---------|
| `fleet` | `FL` | Fleet infrastructure and tooling |
| `nnrt` | `NN` | NNRT AI pipeline |
| `dspd` | `DS` | DSPD Plane integration project |
| `aicp` | `AI` | AICP (future) |

### 3.3 Custom State Workflows

States are created per project. The following are the fleet standard states.

**Fleet project (`fleet`):**

| State | Type | Color | Meaning |
|-------|------|-------|---------|
| `backlog` | backlog | grey | Not yet scheduled |
| `todo` | unstarted | blue | In current sprint, not started |
| `dispatched` | started | yellow | OCMC task created, agent working |
| `in-review` | started | orange | PR open, awaiting merge |
| `done` | completed | green | Merged, deployed |
| `cancelled` | cancelled | red | Dropped |

**NNRT project (`nnrt`):**

| State | Type | Meaning |
|-------|------|---------|
| `backlog` | backlog | Not scheduled |
| `spec-required` | unstarted | Pass needs spec before implementation |
| `spec-ready` | unstarted | Spec written, ready for implementation |
| `in-progress` | started | Agent implementing |
| `review` | started | PR open |
| `done` | completed | Merged |
| `cancelled` | cancelled | Dropped |

**DSPD project (`dspd`):**

| State | Type | Meaning |
|-------|------|---------|
| `backlog` | backlog | Not yet scheduled |
| `sprint-ready` | unstarted | Accepted into sprint |
| `in-progress` | started | Agent working |
| `in-review` | started | PR open |
| `done` | completed | Merged |
| `cancelled` | cancelled | Dropped |

### 3.4 Labels (Fleet-Wide)

Apply these labels consistently across all projects:

| Label | Color | Meaning |
|-------|-------|---------|
| `agent:architect` | blue | Assigned to / owned by architect |
| `agent:software-engineer` | purple | Assigned to software-engineer |
| `agent:devops` | orange | Assigned to devops |
| `agent:qa-engineer` | teal | Assigned to QA |
| `agent:pm` | yellow | PM owns this item |
| `agent:technical-writer` | green | Technical writer |
| `spec-required` | red | Must have spec doc before code |
| `blocked` | red | Externally blocked |
| `infra` | grey | Infrastructure change |
| `docs` | blue | Documentation only |
| `test` | teal | Test-only change |

### 3.5 Estimates (Story Points)

Use Fibonacci sequence: **1, 2, 3, 5, 8, 13**

| Points | Complexity | Description |
|--------|------------|-------------|
| 1 | XS | < 1 hour; trivial change, 1 file |
| 2 | S | 1-2 hours; clear scope, few files |
| 3 | S+ | 2-4 hours; well-defined, moderate scope |
| 5 | M | 4-8 hours; significant but bounded |
| 8 | L | 1-2 days; complex, multiple components |
| 13 | XL | 3+ days; consider splitting |

### 3.6 Cycle (Sprint) Configuration

| Setting | Value |
|---------|-------|
| Duration | 2 weeks |
| Naming | `Sprint N — YYYY-MM-DD` |
| Start day | Monday |
| Auto-close | No (PM agent closes manually after review) |

---

## 4. IaC Guide: plane-configure.sh

### 4.1 What It Does

`scripts/plane-configure.sh` is the authoritative IaC script for Plane workspace setup. It is **idempotent** — run it as many times as needed without duplicating data.

**What it creates:**
1. Plane admin superuser (email: `admin@fleet.local`)
2. Workspace: `openclaw-fleet` (slug: `fleet`)
3. Project: `openclaw-fleet` (identifier: `OF`)
4. API token: `fleet-devops-ws`
5. Config file: `.plane-config` (gitignored)

### 4.2 Prerequisites

Before running the script:

```bash
# 1. Plane must be running
docker compose -f docker-compose.plane.yaml --env-file plane.env up -d

# 2. Migrations must be complete (check with):
docker inspect devops-7e40de40-migrator-1 --format '{{.State.Status}}'
# Expected: "exited"
docker inspect devops-7e40de40-migrator-1 --format '{{.State.ExitCode}}'
# Expected: "0"

# 3. Web UI must be reachable:
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8080/
# Expected: 200
```

### 4.3 Running the Script

```bash
# Default run (uses localhost:8080, default credentials):
./scripts/plane-configure.sh

# Custom Plane URL or admin email:
PLANE_URL=http://my-server:8080 \
PLANE_ADMIN_EMAIL=admin@myorg.com \
PLANE_ADMIN_PASSWORD=MySecurePass \
./scripts/plane-configure.sh
```

### 4.4 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PLANE_URL` | `http://localhost:8080` | Plane instance URL |
| `PLANE_ADMIN_EMAIL` | `admin@fleet.local` | Admin user email |
| `PLANE_ADMIN_PASSWORD` | `FleetAdmin2026!` | Admin user password — **change this** |
| `COMPOSE_PROJECT` | `devops-7e40de40` | Docker Compose project name |
| `API_CONTAINER` | `${COMPOSE_PROJECT}-api-1` | Django API container name |
| `CONFIG_FILE` | `.plane-config` | Output config file path |

### 4.5 Output: .plane-config

After a successful run, `.plane-config` contains:

```bash
# Plane configuration — auto-generated by plane-configure.sh
# WARNING: Contains secrets — gitignored, do not commit
PLANE_URL=http://localhost:8080
PLANE_WORKSPACE_SLUG=fleet
PLANE_WORKSPACE_ID=<uuid>
PLANE_PROJECT_ID=<uuid>
PLANE_PROJECT_IDENTIFIER=OF
PLANE_API_TOKEN=plane_api_<token>
```

Source this file to configure the fleet CLI and PM agent:

```bash
source .plane-config
export PLANE_BASE_URL="$PLANE_URL"
export PLANE_API_KEY="$PLANE_API_TOKEN"
```

### 4.6 Script Internals

The script uses `docker exec` to run Django management commands inside the `plane-api` container — this is the supported method for Plane setup operations. It does not use the REST API for setup (the API requires a logged-in user, not just an API key, for admin operations).

Key steps in order:
1. Pre-flight: verify Plane is reachable at `$PLANE_URL/`
2. Wait for migrations: poll `plane-migrator` container status
3. Create superuser: `manage.py createsuperuser` (idempotent)
4. Set instance admin: `manage.py create_instance_admin`
5. Django shell script: create workspace, project, project member, API token
6. Verify API access: call `/api/v1/workspaces/<slug>/members/` with generated token
7. Write `.plane-config`

### 4.7 Validating Setup

After running `plane-configure.sh`, validate the full API surface:

```bash
./scripts/validate-plane-api.sh
```

This runs 11 checks: workspace access, project CRUD, issue CRUD, cycle listing, label management, and API key auth confirmation. All 11 should pass.

---

## 5. New Fleet Onboarding

Follow these steps to connect a new fleet to the existing Plane instance.

### 5.1 Prerequisites

- Plane is running and accessible (`http://localhost:8080` returns HTTP 200)
- You have the Plane admin credentials (`admin@fleet.local`)
- The new fleet has an OCMC board provisioned

### 5.2 Step-by-Step

**Step 1: Create a Plane workspace for the new fleet**

```bash
PLANE_ADMIN_EMAIL=admin@fleet.local \
PLANE_ADMIN_PASSWORD=<your-admin-password> \
PLANE_WORKSPACE_SLUG=new-fleet-slug \
./scripts/plane-configure.sh
```

This creates a new workspace with the provided slug. The output `.plane-config` contains the new fleet's API token.

**Step 2: Configure the new fleet's PM agent**

Copy the generated credentials into the new PM agent's workspace:

```bash
# In the new PM agent's workspace:
cat >> .env << 'EOF'
PLANE_BASE_URL=http://localhost:8080
PLANE_API_KEY=plane_api_<token-from-plane-config>
PLANE_WORKSPACE_SLUG=new-fleet-slug
OCMC_BASE_URL=http://localhost:8000
OCMC_AUTH_TOKEN=<ocmc-agent-token>
EOF
```

**Step 3: Create projects in Plane for the new fleet**

Using the fleet CLI or Plane UI, create one project per fleet initiative:

```bash
# Via fleet CLI:
fleet plan create-project "My Project" --slug my-project --workspace new-fleet-slug

# Or via Plane UI at http://localhost:8080
```

**Step 4: Configure state workflows**

For each project, add the fleet-standard states listed in [§3.3](#33-custom-state-workflows). This is currently a manual step in the Plane UI (`Project Settings → States`).

**Step 5: Create fleet-standard labels**

Add the labels from [§3.4](#34-labels-fleet-wide) to the workspace (`Workspace Settings → Labels`).

**Step 6: Validate API access**

```bash
source .plane-config
curl -sS -H "X-Api-Key: $PLANE_API_TOKEN" \
  "$PLANE_URL/api/v1/workspaces/$PLANE_WORKSPACE_SLUG/projects/" | python3 -m json.tool
```

Expected: JSON response listing your configured projects.

**Step 7: Register the PM agent with OCMC**

Ensure the new fleet's PM agent is provisioned and its heartbeat is running. The PM agent will begin polling Plane on its next heartbeat cycle.

### 5.3 Verification Checklist

- [ ] Plane workspace accessible at `http://localhost:8080/<new-fleet-slug>/`
- [ ] API key returns projects at `/api/v1/workspaces/<slug>/projects/`
- [ ] State workflows configured for each project
- [ ] Labels created
- [ ] PM agent `.env` contains `PLANE_WORKSPACE_SLUG=<new-fleet-slug>`
- [ ] PM agent heartbeat running and posting to OCMC board memory

---

## 6. State Mapping Reference

This section documents the canonical mapping between Plane issue states and OCMC task statuses. Used by `fleet/core/plane_sync.py` and any future sync code.

### 6.1 Plane → OCMC Mapping

When syncing a Plane issue to OCMC, map state as follows:

| Plane State Group | Plane State Name | OCMC Status | Notes |
|-------------------|-----------------|-------------|-------|
| `backlog` | `backlog` | `inbox` | Not yet dispatched |
| `unstarted` | `todo` | `inbox` | Ready for dispatch |
| `unstarted` | `sprint-ready` | `inbox` | Sprint-accepted, awaiting dispatch |
| `unstarted` | `spec-required` | `inbox` | Cannot dispatch until spec exists |
| `unstarted` | `spec-ready` | `inbox` | Ready after spec approval |
| `started` | `dispatched` | `in_progress` | Agent assigned |
| `started` | `in-progress` | `in_progress` | Agent working |
| `started` | `in-review` | `review` | PR open |
| `started` | `review` | `review` | PR open (NNRT naming) |
| `completed` | `done` | `done` | Work complete |
| `cancelled` | `cancelled` | `done` | Closed (mark with note) |

### 6.2 OCMC → Plane Mapping

When reflecting OCMC task completion back to Plane:

| OCMC Status | Plane State | Condition |
|-------------|-------------|-----------|
| `in_progress` | `dispatched` | On first agent heartbeat |
| `review` | `in-review` | When PR is opened |
| `done` | `done` | When OCMC task approved and closed |

### 6.3 Custom Field Cross-Reference

The sync engine stores the Plane ↔ OCMC mapping in OCMC task custom fields:

| OCMC Custom Field | Type | Contents |
|-------------------|------|---------|
| `plane_issue_id` | UUID string | Plane issue UUID |
| `plane_project_id` | UUID string | Plane project UUID |
| `plane_workspace` | string | Plane workspace slug (e.g., `openclaw-fleet`) |

Query all OCMC tasks mapped to Plane:
```python
# In PlaneSyncer.ingest_from_plane():
# Already-mapped issues are detected by scanning plane_issue_id custom fields
tasks = await mc.list_tasks(board_id=board_id)
mapped_ids = {
    t.custom_field_values.get("plane_issue_id")
    for t in tasks
    if t.custom_field_values.get("plane_issue_id")
}
```

### 6.4 Priority Mapping

| Plane Priority | OCMC Priority |
|---------------|---------------|
| `urgent` | `urgent` |
| `high` | `high` |
| `medium` | `medium` |
| `low` | `low` |
| `none` | `medium` (default) |

### 6.5 Sync Boundaries (v1)

Current sync scope (Phase 1 — one-way, PM-initiated):

| In scope | Out of scope |
|----------|-------------|
| Plane issues → OCMC tasks | OCMC tasks → Plane (future Phase 3) |
| PM-initiated dispatch | Automatic webhook-triggered sync |
| State: backlog/todo/sprint-ready | Plane module/epic hierarchy |
| Priority mapping | Plane estimate ↔ OCMC story_points |
| Custom field cross-reference | Plane comments ↔ OCMC comments |

---

## 7. Troubleshooting

### 7.1 Docker Issues

**Problem: `docker compose up` fails with port conflict**

```
Error: port 8080 already in use
```

Check what is using port 8080:
```bash
lsof -i :8080
# or
ss -tlnp | grep 8080
```

If another service is on 8080, either stop it or change `LISTEN_HTTP_PORT` in `plane.env` and update `plane-proxy` service port binding in `docker-compose.plane.yaml`.

---

**Problem: Plane services start but `plane-api` keeps restarting**

```bash
docker logs devops-7e40de40-api-1 --tail 50
```

Common causes:
- `SECRET_KEY` is still the default placeholder — replace it with a 50-char random string
- `DATABASE_URL` credentials don't match `POSTGRES_USER`/`POSTGRES_PASSWORD`
- `plane-db` hasn't finished initializing yet — wait 30s and retry

Generate a valid `SECRET_KEY`:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

---

**Problem: Migrations fail (migrator exits with non-zero code)**

```bash
docker logs devops-7e40de40-migrator-1
```

Common cause: `plane-db` was not ready when migrator started. Restart migrator:
```bash
docker compose -f docker-compose.plane.yaml restart migrator
```

---

**Problem: MinIO fails to start**

Check MinIO root credentials:
```bash
docker logs devops-7e40de40-plane-minio-1 --tail 20
```

Ensure `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `plane.env` are at least 3 characters (MinIO minimum). The defaults `access-key` and `secret-key` are valid but **must be changed before production use**.

---

**Problem: Plane web UI loads but shows blank page**

The frontend may be trying to reach the API via `WEB_URL` but the URL is wrong. Check:
```bash
grep WEB_URL plane.env
# Should be: WEB_URL=http://localhost:8080  (or your actual hostname)
```

If deploying on a remote machine, `WEB_URL` must be the externally reachable URL, not `localhost`.

---

### 7.2 API Access Issues

**Problem: `configure-plane.sh` fails at "API access verification"**

The script calls `/api/v1/workspaces/<slug>/members/` and gets 0 results or an error.

Debug manually:
```bash
source .plane-config
curl -sS -H "X-Api-Key: $PLANE_API_TOKEN" \
  "$PLANE_URL/api/v1/workspaces/$PLANE_WORKSPACE_SLUG/members/" | python3 -m json.tool
```

Common causes:
- API token was generated for a different workspace slug
- Workspace slug in the URL doesn't match the workspace created (check: `PLANE_WORKSPACE_SLUG`)
- `plane-api` container is still starting up — wait 30s

---

**Problem: `fleet plane list` returns "Unauthorized"**

```bash
fleet plane list --project fleet
# Error: 401 Unauthorized
```

Check your environment:
```bash
echo $PLANE_BASE_URL   # Should be http://localhost:8080
echo $PLANE_API_KEY    # Should start with "plane_api_"
echo $PLANE_WORKSPACE_SLUG  # Should match your workspace slug
```

Re-source your config:
```bash
source .plane-config
export PLANE_BASE_URL="$PLANE_URL"
export PLANE_API_KEY="$PLANE_API_TOKEN"
```

---

**Problem: API returns 404 for workspace endpoints**

Plane workspace slugs are case-sensitive and URL-encoded. Verify the slug:
```bash
curl -sS -H "X-Api-Key: $PLANE_API_TOKEN" \
  "http://localhost:8080/api/v1/workspaces/" | python3 -m json.tool
# Lists all workspaces the token has access to
```

---

**Problem: `validate-plane-api.sh` fails on issue CRUD tests**

Ensure the default project exists. The validate script creates/reads/updates/deletes a test issue in the `OF` project. If the project was deleted or the identifier changed:

```bash
# Re-run configure to recreate:
./scripts/plane-configure.sh
```

---

### 7.3 Authentication Issues

**Problem: Admin login fails at `http://localhost:8080`**

Default credentials:
- Email: `admin@fleet.local`
- Password: `FleetAdmin2026!` (or whatever was set in `PLANE_ADMIN_PASSWORD`)

If you've lost the admin password, reset via Django:
```bash
docker exec -it devops-7e40de40-api-1 python manage.py changepassword admin
```

---

**Problem: API token expired or revoked**

Plane API tokens do not expire by default, but can be revoked. To regenerate:

```bash
# Re-run configure (idempotent — creates new token if old one is gone):
./scripts/plane-configure.sh
```

Or via Plane UI: `Profile → API Tokens → Create token`.

---

**Problem: PM agent can't authenticate (OCMC token expired)**

OCMC tokens are separate from Plane tokens. Check `OCMC_AUTH_TOKEN` in the PM agent's `.env`. Provision a new token via OCMC admin or re-run the agent provisioning script.

---

### 7.4 Sync Issues

**Problem: `fleet plane sync` creates duplicate OCMC tasks**

The sync engine is supposed to be idempotent (skips issues that already have an OCMC mapping via `plane_issue_id`). If duplicates appear:

1. Check that the original OCMC task has `plane_issue_id` in its custom fields
2. If the original task was deleted from OCMC, the mapping is lost — the sync will recreate it

To find OCMC tasks missing `plane_issue_id`:
```python
from fleet.infra.mc_client import MCClient
mc = MCClient(...)
tasks = await mc.list_tasks(board_id=board_id)
unmapped = [t for t in tasks if not t.custom_field_values.get("plane_issue_id")]
```

---

**Problem: Completed OCMC tasks not reflecting in Plane**

`push_completions_to_plane()` requires the OCMC task to have both `plane_issue_id` and `status == "done"`. Check:

```bash
# Verify the OCMC task has plane_issue_id:
curl -fsS -H "Authorization: Bearer $OCMC_AUTH_TOKEN" \
  "$OCMC_BASE_URL/api/v1/agent/boards/$BOARD_ID/tasks?status=done" | \
  python3 -c "
import sys,json; d=json.load(sys.stdin)
for t in d['items']:
    pid = t.get('custom_field_values',{}).get('plane_issue_id')
    print(t['title'][:40], '— plane_id:', pid or 'MISSING')
"
```

---

## References

- [Technical Architecture](architecture.md) — full service design and data flow
- [Project Requirements](requirements.md) — phased feature requirements
- [CHANGELOG.md](../CHANGELOG.md) — Sprint 1 commit history
- [Sprint 2 Plan](milestones/sprint2.md) — current sprint
- [Plane GitHub](https://github.com/makeplane/plane) — upstream project
- [Plane API Docs](https://developers.plane.so/) — REST API reference
- [CLAUDE.md](../CLAUDE.md) — project conventions (read before touching any file)
