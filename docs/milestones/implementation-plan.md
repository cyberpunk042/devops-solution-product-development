# DSPD Implementation Plan — From 15% to 100%

**Date:** 2026-03-29
**Status:** Plan — requires review before execution
**Author:** Claude (from requirements.md, architecture.md, CLAUDE.md, Sprint 2 plan)

---

## Current State Assessment

### What Exists (the 15%)

| Item | Location | Status |
|------|----------|--------|
| Architecture doc | `docs/architecture.md` | Written |
| Requirements doc | `docs/requirements.md` | Written, Phase 0-4 defined |
| CLAUDE.md | root | Written, defines conventions |
| pyproject.toml | root | Written |
| README.md | root | Written |
| docker-compose | `docker-compose.plane.yaml` (root — wrong path) | Written, 12 services defined |
| plane.env.example | root (wrong path — should be `docker/`) | Written, has ⚠️ markers |
| setup.sh | root | Written, has install/start/stop/status/validate/upgrade/uninstall |
| plane-configure.sh | `scripts/` | Written, creates superuser + workspace + project + API token + god-mode |
| plane-setup-projects.sh | `scripts/` | Written, creates 4 projects (OF, NNRT, DSPD, AICP) with modules |
| plane-setup-states.sh | `scripts/` | Written, applies OCMC lifecycle states to all projects |
| plane-validate-api.sh | `scripts/` | Written, 11-point API CRUD test |
| plane-startup-verify.sh | `scripts/` | Written, 15-point container health check |
| Sprint 1 retrospective | `docs/retrospectives/sprint1.md` | Written |
| Sprint 2 plan | `docs/milestones/sprint2.md` | Written |
| CHANGELOG.md | root | Written |
| .gitignore | root | Written |

### What's Missing (the 85%)

#### Project Structure (CLAUDE.md says it should exist)

| Item | Expected Path | Status |
|------|---------------|--------|
| Docker compose | `docker/docker-compose.plane.yml` | EXISTS at wrong path (root) |
| Env template | `docker/.env.plane.example` | EXISTS at wrong path (root) |
| Nginx config | `docker/nginx.plane.conf` | **MISSING** |
| Setup script | `scripts/setup-plane.sh` | EXISTS as `setup.sh` at root (fine) |
| Plane client | `fleet/infra/plane_client.py` | **EMPTY** (code in openclaw-fleet only) |
| Plane CLI | `fleet/cli/plane.py` | **EMPTY** (code in openclaw-fleet only) |
| Plane sync | `fleet/core/plane_sync.py` | **MISSING** (code in openclaw-fleet only) |
| Config module | `dspd/config.py` | **MISSING** |
| Unit tests | `tests/unit/` | **MISSING** |
| Integration tests | `tests/integration/` | **MISSING** |
| `__init__.py` files | fleet/*, dspd/*, tests/* | **MISSING** |

#### Phase 0 — Foundation (2 unchecked)

| Deliverable | Status | What's Needed |
|-------------|--------|---------------|
| `docker/docker-compose.plane.yml` skeleton | File exists at wrong path | Move to `docker/` |
| `.env.plane.example` | File exists at wrong path | Move to `docker/` |

#### Phase 1 — Self-Host Plane (7 unchecked)

| Deliverable | Status | What's Needed |
|-------------|--------|---------------|
| `docker/docker-compose.plane.yml` — working stack | Exists, untested on clean machine | Move file, verify works |
| `docker/nginx.plane.conf` — proxy config | **MISSING** | Build: upstream blocks for api/web/space/admin/live/minio, WebSocket upgrade, catch-all |
| `scripts/setup-plane.sh` — first-run script | Exists as `setup.sh` | Wire in project setup, state setup, labels, webhooks, validate, verify, fleet export |
| Plane workspace `openclaw-fleet` created | Script exists | Never verified on live |
| Plane projects: `fleet`, `nnrt` | Script creates 4 projects | Never verified on live |
| API key generated and stored | Script exists | Never verified on live |
| API returns projects | Validate script exists | Never verified on live |

**Done when:** `fleet plan list` returns sprint items from a live Plane instance.

#### Phase 2 — Fleet CLI (4 unchecked)

| Deliverable | Status | What's Needed |
|-------------|--------|---------------|
| `fleet/infra/plane_client.py` | Code exists in openclaw-fleet | Copy to DSPD repo, add `__init__.py` files |
| `fleet/cli/plane.py` | Code exists in openclaw-fleet | Copy to DSPD repo |
| `fleet plan sync` dispatches Plane → OCMC | Code exists in openclaw-fleet | Copy plane_sync.py, verify imports work |
| PM done → Plane state updated | Logic in plane_sync.py | Never tested end-to-end |

**Done when:** End-to-end flow tested: Plane item → OCMC task → agent completes → Plane state updated.

#### Phase 3 — MCP Integration (3 unchecked)

| Deliverable | Status | What's Needed |
|-------------|--------|---------------|
| Plane MCP server configured for PM | **NOT STARTED** | Research Plane MCP packaging, write `scripts/plane-setup-mcp.sh` |
| PM uses MCP tools for sprint planning | **NOT STARTED** | Configure .mcp.json for PM agent workspace |
| Webhook handler operational (HMAC) | **NOT STARTED** | Build `dspd/webhooks.py` with HMAC-SHA256 verification, event handlers, ASGI receiver; `scripts/plane-setup-webhooks.sh` for registration |

**Done when:** PM agent can read sprint, dispatch items, and update Plane from a single heartbeat loop.

#### Phase 4 — Full DSPD (5 unchecked)

| Deliverable | Status | What's Needed |
|-------------|--------|---------------|
| Multi-project (fleet, nnrt, aicp, dspd) | Script creates 4 projects | Verify on live, add per-project custom states per requirements §1.3 |
| Cross-project dependency mapping | **NOT STARTED** | Needs Plane Timeline view + issue relations API |
| Velocity + burn-down tracking | **NOT STARTED** | Needs cycles created per project, PM agent populates estimates |
| Analytics dashboard | **NOT STARTED** | Plane built-in analytics, needs populated data |
| DSPD v1.0 milestone cut | **NOT STARTED** | Everything above working |

**Done when:** All active fleet projects visible in Plane with live sprint tracking.

#### Missing Scripts

| Script | Purpose | Status |
|--------|---------|--------|
| `scripts/plane-setup-labels.sh` | Create standard labels per requirements §1.4 across all projects | **MISSING** |
| `scripts/plane-setup-webhooks.sh` | Register webhook in Plane, store HMAC secret | **MISSING** |
| `scripts/plane-setup-mcp.sh` | Configure Plane MCP server for PM agent | **MISSING** |

#### Missing Code

| File | Purpose | Status |
|------|---------|--------|
| `dspd/__init__.py` | Package init | **MISSING** |
| `dspd/config.py` | Config constants from env (no hardcoded URLs/ports) | **MISSING** |
| `dspd/webhooks.py` | Webhook handler: HMAC verification, event dispatch | **MISSING** |
| `fleet/infra/plane_client.py` | Typed async Plane API client | **EMPTY** (exists in openclaw-fleet) |
| `fleet/cli/plane.py` | CLI: create/list/sync/status commands | **EMPTY** (exists in openclaw-fleet) |
| `fleet/core/plane_sync.py` | Bidirectional Plane ↔ OCMC sync | **MISSING** (exists in openclaw-fleet) |
| `fleet/__init__.py` | Package init | **MISSING** |
| `fleet/infra/__init__.py` | Package init | **MISSING** |
| `fleet/cli/__init__.py` | Package init | **MISSING** |
| `fleet/core/__init__.py` | Package init | **MISSING** |

#### Missing Tests

| File | Purpose | Status |
|------|---------|--------|
| `tests/__init__.py` | Package init | **MISSING** |
| `tests/conftest.py` | Shared fixtures | **MISSING** |
| `tests/unit/__init__.py` | Package init | **MISSING** |
| `tests/unit/test_config.py` | Test config loading | **MISSING** |
| `tests/unit/test_plane_client.py` | Test PlaneClient with mocked httpx | **MISSING** (43 tests exist in openclaw-fleet) |
| `tests/unit/test_plane_sync.py` | Test PlaneSyncer with mocks | **MISSING** (37 tests exist in openclaw-fleet) |
| `tests/unit/test_webhooks.py` | Test HMAC verification, event routing | **MISSING** |
| `tests/integration/__init__.py` | Package init | **MISSING** |
| `tests/integration/test_plane_api.py` | Live Plane API CRUD test | **MISSING** |

#### Per-Project Custom States (requirements §1.3)

Currently `plane-setup-states.sh` applies the same 6 states to all projects. Requirements specify:

**Fleet project** needs: backlog, todo, dispatched, in-review, done, cancelled
**NNRT project** needs: backlog, spec-required, spec-ready, in-progress, review, done, cancelled
**DSPD/AICP** can use generic OCMC lifecycle: backlog, todo, in-progress, in-review, done, cancelled

#### setup.sh install — Missing Steps

Current install flow:
1. ✅ Generate plane.env with secrets
2. ✅ Source plane.env
3. ✅ Start services + wait for migrations + HTTP health
4. ✅ plane-configure.sh (superuser, workspace, project, API token, god-mode)
5. ✅ plane-setup-projects.sh (4 projects + modules)
6. ✅ plane-setup-states.sh (OCMC lifecycle states)
7. ✅ plane-validate-api.sh (11-point check)
8. ✅ plane-startup-verify.sh (15-point health)
9. ✅ Export credentials to fleet .env

Missing from install flow:
10. ❌ `plane-setup-labels.sh` — standard labels across all projects
11. ❌ `plane-setup-webhooks.sh` — webhook registration with HMAC
12. ❌ `plane-setup-mcp.sh` — PM agent MCP configuration
13. ❌ Per-project custom states (currently all generic)
14. ❌ Create initial cycles (sprints) for each project
15. ❌ Verify fleet CLI can talk to Plane (`fleet plan list-projects`)

---

## Build Order

### Block 1: Project Structure (Phase 0 completion)

1. Move `docker-compose.plane.yaml` → `docker/docker-compose.plane.yml`
2. Move `plane.env.example` → `docker/.env.plane.example`
3. Create `docker/nginx.plane.conf`
4. Create all `__init__.py` files (dspd/, fleet/*, tests/*)
5. Create `dspd/config.py`
6. Create `tests/conftest.py`
7. Update `setup.sh` to reference `docker/` paths
8. Update all scripts for new paths
9. Update `CLAUDE.md` phase marker
10. Update `requirements.md` Phase 0 checkboxes

### Block 2: Python Code (Phase 2 foundation)

11. Copy `plane_client.py` from openclaw-fleet → `fleet/infra/`
12. Copy `plane.py` CLI from openclaw-fleet → `fleet/cli/`
13. Copy `plane_sync.py` from openclaw-fleet → `fleet/core/`
14. Adapt imports for DSPD context
15. Copy unit tests from openclaw-fleet (43 + 37 tests)
16. Create `tests/unit/test_config.py`
17. Verify `pytest tests/unit/` passes

### Block 3: Missing Scripts (Phase 1 + 3)

18. Create `scripts/plane-setup-labels.sh` — 9 labels × 4 projects
19. Update `scripts/plane-setup-states.sh` — per-project custom states
20. Create `scripts/plane-setup-webhooks.sh` — register + HMAC secret
21. Create `scripts/plane-setup-mcp.sh` — PM agent MCP config
22. Wire all into `setup.sh install`

### Block 4: Webhook Handler (Phase 3)

23. Create `dspd/webhooks.py` — HMAC verification + event handlers
24. Create `tests/unit/test_webhooks.py`
25. Create integration test: `tests/integration/test_plane_api.py`

### Block 5: Verification (Phase 1 completion)

26. Run `./setup.sh install` on clean state
27. Run `./setup.sh validate`
28. Run `fleet plan list-projects` against live Plane
29. Run `pytest tests/unit/` — all pass
30. Update `requirements.md` Phase 1 checkboxes

### Block 6: End-to-End Flow (Phase 2 completion)

31. Create Plane issue via CLI → verify in Plane UI
32. Run `fleet plan sync` → verify OCMC task created
33. Complete OCMC task → verify Plane state updated
34. Run `pytest tests/integration/` against live Plane
35. Update `requirements.md` Phase 2 checkboxes

### Block 7: PM Agent Integration (Phase 3 completion)

36. Configure Plane MCP for PM agent
37. Test PM heartbeat reads Plane sprint
38. Test PM dispatches Plane items → OCMC
39. Test webhook fires on Plane events
40. Update `requirements.md` Phase 3 checkboxes

### Block 8: Multi-Project + Analytics (Phase 4)

41. Verify all 4 projects in Plane with custom states
42. Create cycles (sprints) in each project
43. Add cross-project issue relations
44. Populate estimates for velocity tracking
45. Verify analytics dashboard shows data
46. DSPD v1.0 milestone cut
47. Update `requirements.md` Phase 4 checkboxes

---

## Total Scope

| Category | Items |
|----------|-------|
| Files to move | 2 |
| Files to create | ~25 |
| Files to update | ~8 |
| Scripts to create | 3 |
| Scripts to update | 3 |
| Unit tests to create | ~4 files (~100+ test cases) |
| Integration tests | 1 file |
| End-to-end verifications | 6 |
| Phase checklists to complete | Phase 0 (2), Phase 1 (7), Phase 2 (4), Phase 3 (3), Phase 4 (5) = 21 items |

---

## Dependencies

- Block 1 has no dependencies
- Block 2 depends on Block 1 (paths must be correct)
- Block 3 depends on Block 1 (setup.sh paths)
- Block 4 depends on Block 3 (webhook registration)
- Block 5 depends on Blocks 1-3 + running Docker
- Block 6 depends on Block 5 + running fleet
- Block 7 depends on Block 6 + PM agent operational
- Block 8 depends on Block 7

---

## Risks

| Risk | Mitigation |
|------|------------|
| Plane Docker images pull takes forever on slow connection | setup.sh already has `pull --quiet` |
| 8GB RAM may be tight with fleet + Plane | Monitor with `docker stats`, Plane uses GUNICORN_WORKERS=1 |
| Plane MCP server may not exist or may be immature | Research first in Block 7, fallback to API-only |
| openclaw-fleet plane_client.py may have fleet-specific imports | Audit imports when copying in Block 2 |
| Per-project states may conflict with Plane defaults | plane-setup-states.sh updates existing states, doesn't just create |