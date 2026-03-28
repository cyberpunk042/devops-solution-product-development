# Changelog

All notable changes to DSPD are documented here.
Follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Commit SHAs reference the `cyberpunk042/devops-solution-product-development` repo and the `cyberpunk042/openclaw-fleet` repo where indicated.

---

## [Unreleased]

_Sprint 2 work in progress — see [docs/milestones/sprint2.md](docs/milestones/sprint2.md)._

---

## [Sprint 1] — 2026-03-28

**Theme:** Plane self-hosting and fleet CLI integration  
**Tasks:** S1-1 through S1-8 | **Story points delivered:** ~21  
**See:** [docs/retrospectives/sprint1.md](docs/retrospectives/sprint1.md)

### Added

#### Phase 0 — Project Foundation

- **`docs/architecture.md`** — full technical architecture: Plane service graph (13 containers), port allocation (8080, avoids OCMC 8000/3000), Docker Compose design, service responsibilities, security posture, phase roadmap ([`96af189`] task:15554969)
- **`docs/requirements.md`** — phased feature requirements: Plane entities (projects, cycles, modules, issues), custom state workflows per project, sprint acceptance criteria, MCP integration requirements ([`96af189`] task:15554969)
- **`CLAUDE.md`** — project conventions for all agents: non-negotiable architecture rules, code standards, anti-patterns, project layout spec ([`96af189`] task:15554969)
- **`pyproject.toml`** — Python package configuration with test deps, ruff formatting, pytest config ([`96af189`] task:15554969)
- **`README.md`** — project vision, architecture diagram, and status ([`9f51310`])

#### S1-1 — Plane Docker Research

- **`docker-compose.plane.yaml`** — 13-service Plane Community Edition stack: proxy (nginx), web (Next.js), space, admin, live, api (Django), worker (Celery), beat (Celery scheduler), migrator, plane-db (PostgreSQL 15), plane-redis (Valkey 7.2), plane-mq (RabbitMQ 3.13), plane-minio (MinIO) — port 8080, isolated from OCMC ([`738c66c`] task:78ade8d5, merged PR #1)
- **`plane.env.example`** — environment template with all required vars grouped by concern: networking, security, PostgreSQL, Redis, RabbitMQ, MinIO, performance — includes `SECRET_KEY` generation instructions ([`738c66c`] task:78ade8d5)

#### S1-2 — Plane Docker Deployment

- Plane stack deployed and verified: all 13 services start cleanly, Plane web UI reachable at `localhost:8080`, migrations complete (15/15 startup checks pass) (task:4d79e4cc, merged PR #2, PR #5)
- **`scripts/verify-plane-startup.sh`** — 15-check startup verification script: service health, UI reachability, API endpoint, migration status ([`325c6d8`] task:4d79e4cc)

#### S1-3 — Plane Workspace Configuration

- **`scripts/plane-configure.sh`** — idempotent IaC configuration script: creates admin superuser, configures Fleet workspace and NNRT project, generates API key, writes output to `.plane-config` ([`bc6f11d`] task:7e40de40, PR #3)
- `.gitignore` — added `plane.env` and `.plane-config` to prevent credential commits ([`bc6f11d`] task:7e40de40)

#### S1-4 — Plane API Validation

- **`scripts/validate-plane-api.sh`** — 11-check API validation script: workspace CRUD, project CRUD, issue create/read/update/delete, cycle listing, label management, API key auth confirmation (task:be565540, merged PR #4)

#### S1-5 — Plane REST API Client (fleet workspace)

- **`fleet/infra/plane_client.py`** — async Plane REST API wrapper (httpx): `PlaneClient` class with `list_projects`, `list_states`, `create_issue`, `update_issue`, `list_issues`, `list_cycles`, `add_issue_to_cycle`; typed model classes `PlaneProject`, `PlaneState`, `PlaneCycle`, `PlaneIssue`; credentials from `PLANE_URL`/`PLANE_API_KEY` env vars ([`a1c28c9`] fleet repo, task:2304dc81)
- **`fleet/tests/infra/test_plane_client.py`** — 43 unit tests with httpx mocking

#### S1-6 — Fleet Plane CLI (fleet workspace)

- **`fleet/cli/plane.py`** — CLI commands via Typer: `fleet plane list [--project] [--sprint]`, `fleet plane create <title> [--project] [--priority]`, `fleet plane sync [--project] [--dry-run]` ([`65fe2e8`] fleet repo, task:48647626)

#### S1-7 — Plane ↔ OCMC Bidirectional Sync (fleet workspace)

- **`fleet/core/plane_sync.py`** — `PlaneSyncer` class: `ingest_from_plane()` polls Plane projects → creates OCMC tasks with `plane_issue_id`/`plane_project_id`/`plane_workspace` custom fields; `push_completions_to_plane()` reflects OCMC done tasks back to Plane issue state; idempotent (skips already-mapped issues); priority mapping (Plane `none` → OCMC `medium`) ([`4194a68`] fleet repo, task:49993215)
- **`fleet/tests/core/test_plane_sync.py`** — 37 unit tests (all passing)

#### S1-8 — Security Review

- Security audit completed: three findings documented in board memory (see [Known Issues](#known-issues)) (task:3b3e2e7a)

### Fixed

- `fix(deps)` — added `pytest-asyncio` and `pytest-httpx` to dev dependencies; added `fleet/tests` to pytest testpaths ([`e598fb7`] fleet repo, task:c46e6b62)

### Known Issues (Sprint 1 Exit)

| ID | Severity | Issue | Status |
|----|----------|-------|--------|
| SEC-1 | 🔴 HIGH | Weak credential defaults in `plane.env.example` (`POSTGRES_PASSWORD=plane`, `SECRET_KEY=changeme-...`) | Deployment-blocking; must replace before `docker compose up` |
| SEC-2 | ⚠️ MEDIUM | `plane.env` not in `.gitignore` (added in S1-3 PR but not on all branches) | Partially fixed |
| SEC-3 | ⚠️ MEDIUM | All 13 Plane containers on default Docker bridge — no network segmentation from OCMC | Deferred to Sprint 2 |
| STRUCT-1 | ⚠️ LOW | `docker-compose.plane.yaml` and `plane.env.example` are in repo root, not `docker/` as `CLAUDE.md` specifies | Deferred to Sprint 2 |
| TEST-1 | ⚠️ MEDIUM | 43 PlaneClient tests and 16 PlaneSyncer tests were failing (missing `pytest-asyncio`) | Fixed in task:c46e6b62 |

---

## [Phase 0] — 2026-03-28 (pre-Sprint 1)

**Theme:** Project foundation  
**Outcome:** Architecture designed, requirements documented, project scaffolded.

### Added

- Initial project scaffold: `docs/architecture.md`, `docs/requirements.md`, `CLAUDE.md`, `pyproject.toml`, `README.md`
- Registered DSPD as an official fleet project in `fleet/config/` ([`45266dd`] fleet repo)
- DSPD milestone plan posted to board memory: 4-sprint roadmap, 21 tasks, 68 story points ([`9c69567`] fleet repo)
- Sprint breakdown documented (PM agent): all 4 sprints, task-level acceptance criteria, dependency graph, risk register

---

## Links

- [Sprint 1 Retrospective](docs/retrospectives/sprint1.md)
- [Sprint 2 Plan](docs/milestones/sprint2.md)
- [Technical Architecture](docs/architecture.md)
- [Project Requirements](docs/requirements.md)
- [GitHub Repository](https://github.com/cyberpunk042/devops-solution-product-development)
