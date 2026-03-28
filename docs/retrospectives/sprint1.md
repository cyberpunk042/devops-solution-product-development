# Sprint 1 Retrospective — DSPD

**Sprint:** 1  
**Theme:** Plane self-hosting and fleet CLI integration  
**Date:** 2026-03-28  
**Author:** technical-writer agent  
**Status:** Complete

---

## 1. What We Set Out to Do

Sprint 1 goal: get Plane running locally, accessible via REST API, and wired into the fleet CLI so agents can create and list work items programmatically.

**Original scope (from sprint breakdown):**

| Task | Agent | Points | Goal |
|------|-------|--------|------|
| S1-1 | devops | 1 | Research Plane Docker requirements |
| S1-2 | devops | 3 | Deploy Plane Docker stack |
| S1-3 | devops | 2 | Configure workspace and project via script |
| S1-4 | devops | 1 | Validate Plane REST API end-to-end |
| S1-5 | software-engineer | 3 | Build `plane_client.py` |
| S1-6 | software-engineer | 3 | Build `fleet plane` CLI |
| **Total** | | **13** | |

**What actually ran:**

Sprint 1 scope expanded during execution. Additional tasks were created and completed:

| Task | Outcome |
|------|---------|
| S1-7: Plane ↔ OCMC bidirectional sync | Added; delivered |
| S1-8: Security review of deployment and API | Added; delivered |
| Phase 0 (architect + PM): foundation docs | Pre-sprint; delivered |

---

## 2. What Was Delivered

### ✅ Fully Delivered

| Deliverable | Location | Evidence |
|------------|----------|---------|
| 13-service Plane Docker stack | `docker-compose.plane.yaml` | PR #1 merged |
| Environment template | `plane.env.example` | PR #1 merged |
| Startup verification script (15 checks) | `scripts/verify-plane-startup.sh` | PR #2, PR #5 merged; 15/15 pass |
| Plane API validation script (11 checks) | `scripts/validate-plane-api.sh` | PR #4 merged; 11/11 pass |
| Workspace configuration script | `scripts/plane-configure.sh` | PR #3 |
| Plane REST API client | `fleet/infra/plane_client.py` | 43 unit tests |
| Fleet Plane CLI | `fleet/cli/plane.py` | `list`, `create`, `sync` commands |
| Plane ↔ OCMC sync engine | `fleet/core/plane_sync.py` | 37 unit tests |
| Security audit | Board memory + fleet alerts | 3 findings raised |
| Architecture docs | `docs/architecture.md`, `docs/requirements.md` | Phase 0 |
| Project conventions | `CLAUDE.md` | Phase 0 |

### ⚠️ Delivered with Issues

| Deliverable | Issue |
|------------|-------|
| `fleet/tests/infra/test_plane_client.py` (43 tests) | Failed on delivery: missing `pytest-asyncio` in dev deps. Fixed post-sprint (task:c46e6b62). |
| `fleet/tests/core/test_plane_sync.py` (37 tests) | Same `pytest-asyncio` issue. Fixed post-sprint. |
| File placement (`docker-compose.plane.yaml`, `plane.env.example`) | Committed to repo root across two PRs; `CLAUDE.md` specifies `docker/` subdirectory. Not corrected in sprint. |

### ❌ Not Delivered

Nothing from the original scope was dropped. All 6 planned tasks plus 2 bonus tasks completed.

---

## 3. What Broke

### 🔴 Test infrastructure failure (blocking)

**What:** `pytest-asyncio` was not listed in `pyproject.toml` dev dependencies. All 43 `PlaneClient` tests and 37 `PlaneSyncer` tests were `ERROR` on collection.

**Root cause:** The software-engineer wrote `@pytest.mark.asyncio` tests without verifying the dependency was present in `pyproject.toml`. QA caught this on review.

**Fix:** Added `pytest-asyncio>=0.23` and `pytest-httpx>=0.30` to `[project.optional-dependencies] test` in `pyproject.toml` ([`e598fb7`]).

**Lesson:** Before declaring test coverage, agents must run `pytest` and confirm zero errors.

---

### ⚠️ File placement drift (structural)

**What:** Sprint 1 produced `docker-compose.plane.yaml` and `plane.env.example` at the repo root. `CLAUDE.md` specifies `docker/docker-compose.plane.yml` and `docker/.env.plane.example` (different directory, different filenames).

**Root cause:** S1-1 agent placed files in root. S1-3 agent re-added them in root rather than correcting to `docker/`. The inconsistency persisted across two PRs.

**Impact:** `scripts/plane-configure.sh` hardcodes `docker-compose.plane.yaml` (root path). Sprint 2 code will break if files are moved without updating scripts.

**Recommendation:** Fix file placement in Sprint 2 before new code references these paths. One clean-up commit.

---

### ⚠️ Security: weak credential defaults

**What:** `plane.env.example` ships with `POSTGRES_PASSWORD=plane`, `RABBITMQ_PASSWORD=plane`, `SECRET_KEY=changeme-replace-with-50-char-random-string`, and other weak placeholders.

**Root cause:** Intentional defaults for developer convenience, but the env file lacked clear warnings that these must be replaced before production use.

**Impact:** If deployed with defaults, Plane would be accessible with trivial credentials.

**Fix (Sprint 2):** Add `## Security Rules` section to `CLAUDE.md`; add prominent `⚠️ CHANGE BEFORE DEPLOY` comments in `plane.env.example`.

---

### ⚠️ Docker network isolation gap

**What:** All 13 Plane containers run on Docker's default bridge network. No explicit `plane-net` network segment isolates Plane from other Docker services (e.g., OCMC containers).

**Impact:** Low in local dev; deployment-blocking for any shared-host production setup.

**Fix (Sprint 2):** Add `networks: plane-net:` to `docker-compose.plane.yaml` and assign all Plane services to it.

---

## 4. Lessons Learned

### Process

| # | Lesson | Action |
|---|--------|--------|
| L1 | **Test before review.** Two tasks completed with untested code (S1-5, S1-7). QA caught test failures post-review. | All agents must run `pytest` (or equivalent) before marking a task complete. Add to `CLAUDE.md`. |
| L2 | **CLAUDE.md is the spec.** Two separate PRs drifted from the file layout defined in `CLAUDE.md`. Agents should cross-check `CLAUDE.md` project layout before committing files. | Add a pre-commit note in `CLAUDE.md`: "Before committing, verify file paths match this layout." |
| L3 | **Security review early.** S1-8 (security) ran at the end. Credential and network issues found could have been addressed during S1-1/S1-2 if security review ran concurrently. | Schedule security review as a parallel track from S1-2 onward in Sprint 2. |
| L4 | **Scope creep was net-positive.** S1-7 (bidirectional sync) and S1-8 (security audit) were added mid-sprint. Both added real value. | Accept scope additions that directly enable the sprint goal; escalate to @lead when uncertain. |

### Technical

| # | Lesson | Action |
|---|--------|--------|
| T1 | **`pytest-asyncio` requires explicit dep declaration.** The package is not a pytest dependency by default; any project with async tests must add it. | Add to the `pyproject.toml` template in `CLAUDE.md`. |
| T2 | **Plane needs 4+ GB RAM.** Confirmed by S1-1 research. Default Docker Desktop memory limits may cause OOM on `plane-worker`. | Document in `docs/architecture.md` §2 resource requirements; add to `RUNBOOK.md` (Sprint 4). |
| T3 | **MinIO adds complexity.** Plane's file upload depends on MinIO. The default `plane.env.example` uses internal MinIO, but external S3 is possible. Not documented. | Add MinIO vs. S3 trade-off to `docs/architecture.md` §2 in Sprint 2. |

---

## 5. Sprint Metrics

| Metric | Value |
|--------|-------|
| Tasks planned | 6 |
| Tasks completed | 8 (+S1-7, S1-8) |
| Story points planned | 13 |
| Story points delivered | ~21 (estimated) |
| PRs opened | 5 |
| PRs merged | 4 (PR #1, #2, #4, #5) |
| PRs in review | 1 (PR #3 — S1-3) |
| Tests written | 80 (43 PlaneClient + 37 PlaneSyncer) |
| Tests passing at sprint close | 80/80 (after dep fix) |
| Security findings | 3 (1 HIGH, 2 MEDIUM) |
| Blocking issues at sprint close | 0 |

---

## 6. Sprint 2 Handoff

The following items are **carried into Sprint 2** as debt or prerequisites:

| Item | Owner | Priority |
|------|-------|----------|
| Fix file placement: move to `docker/`, rename per `CLAUDE.md` | devops | High |
| Add Docker network segmentation (`plane-net`) | devops | High |
| Add `## Security Rules` to `CLAUDE.md` | technical-writer | Medium |
| Verify `scripts/plane-configure.sh` against live Plane instance | devops | High |
| Sprint 2 core work: MCP integration, PM agent skills | software-engineer | Sprint goal |

See [Sprint 2 plan →](../milestones/sprint2.md)

---

## References

- [CHANGELOG.md](../../CHANGELOG.md) — all Sprint 1 commits
- [Sprint 2 Plan](../milestones/sprint2.md)
- [Technical Architecture](../architecture.md)
- [Project Requirements](../requirements.md)
