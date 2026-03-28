# Sprint 2 Plan — DSPD

**Sprint:** 2  
**Theme:** Quality hardening and Plane operational  
**Target date:** TBD (dispatched 2026-03-28)  
**Author:** technical-writer agent (from PM sprint breakdown + Sprint 2 epic task)  
**Status:** Active — tasks dispatched to board

---

## 1. Sprint Goal

Sprint 1 delivered working code but left three gaps that block reliable operations:

1. **Tests were broken** (missing `pytest-asyncio` — partially fixed)
2. **Plane has never been deployed with real credentials** (only tested with defaults)
3. **Fleet framework verification** is outstanding across all 10 agents

Sprint 2 goal: **make everything that Sprint 1 built actually work in a hardened, verifiable way.**

No new features until the foundation is solid.

---

## 2. Sprint 2 Tasks

### 2.1 Quality Hardening

| # | Task | Agent | Points | Acceptance Criteria | Depends On |
|---|------|-------|--------|---------------------|------------|
| S2-Q1 | Fix 43 failing Plane client tests (pytest-asyncio) | software-engineer | 1 | `pytest fleet/tests/infra/test_plane_client.py` → 43 passed, 0 errors | — |
| S2-Q2 | Fix 16 failing Plane sync tests | software-engineer | 1 | `pytest fleet/tests/core/test_plane_sync.py` → 37 passed, 0 errors | S2-Q1 |

> **Note:** `pytest-asyncio` dep was added in [`e598fb7`] (task:c46e6b62). Tests may already pass — verify before starting S2-Q1.

---

### 2.2 Plane Operational

| # | Task | Agent | Points | Acceptance Criteria | Depends On |
|---|------|-------|--------|---------------------|------------|
| S2-O1 | Fix file placement: move docker files to `docker/`, rename per `CLAUDE.md` | devops | 1 | `docker/docker-compose.plane.yml` and `docker/.env.plane.example` exist; root files removed; all scripts updated to new paths | — |
| S2-O2 | Configure Plane workspace, project, and API key | devops | 2 | `scripts/plane-configure.sh` runs successfully against live Plane instance; Fleet workspace + NNRT project created; API key written to `.plane-config`; verified via `scripts/validate-plane-api.sh` | S2-O1 |
| S2-O3 | Security hardening: credentials + network isolation | devops | 2 | `plane.env.example` has `⚠️ CHANGE BEFORE DEPLOY` markers on all credential fields; `docker-compose.plane.yml` uses explicit `plane-net` network; `docker/` not on default bridge | S2-O1 |

---

### 2.3 Documentation

| # | Task | Agent | Points | Acceptance Criteria | Depends On |
|---|------|-------|--------|---------------------|------------|
| S2-D1 | Add `## Security Rules` section to `CLAUDE.md` | technical-writer | 1 | `CLAUDE.md` documents: never commit `plane.env`, credential generation commands, API key env var policy, gitignore requirements | — |
| S2-D2 | Update `docs/architecture.md` — resource requirements + MinIO/S3 trade-off | technical-writer | 1 | Architecture doc includes RAM/CPU minimum for Plane (4 GB RAM, 2 CPU), MinIO vs. external S3 options | S2-O2 |

---

### 2.4 Fleet Framework Verification

| # | Task | Agent | Points | Acceptance Criteria | Depends On |
|---|------|-------|--------|---------------------|------------|
| S2-F1 | Verify fleet framework on all agents — tools, memory, settings | devops/fleet-ops | 2 | All 10 agents have: `MC_WORKFLOW.md` (13 tools), `STANDARDS.md`, `HEARTBEAT.md` with role instructions, `.claude/settings.json` with effort/memory config, `.claude/memory/` initialized | — |

---

### 2.5 Security Review (carry-forward)

| # | Task | Agent | Points | Acceptance Criteria | Depends On |
|---|------|-------|--------|---------------------|------------|
| S2-S1 | Security review: Plane deployment + fleet autonomy code | devsecops-expert | 3 | Review covers: hardened credential defaults, exposed ports, API key handling, fleet autonomy code (orchestrator, behavioral_security, agent_roles). Findings posted as fleet alerts. | S2-O3 |

---

## 3. Summary

| Category | Tasks | Points |
|----------|-------|--------|
| Quality hardening | 2 | 2 |
| Plane operational | 3 | 5 |
| Documentation | 2 | 2 |
| Fleet framework | 1 | 2 |
| Security review | 1 | 3 |
| **Total** | **9** | **14** |

---

## 4. Out of Scope (Sprint 2)

The following Sprint 1 PM breakdown items are **deferred to Sprint 3**, pending Sprint 2 stability:

| Deferred | Reason |
|---------|--------|
| S2-1: Research Plane MCP server tools | Needs live, hardened Plane instance first |
| S2-2: Configure Plane MCP for PM agent | Depends on S2-1 |
| S2-3: PM sprint planning skill | Depends on S2-2 |
| S2-4: Plane → OCMC dispatch skill | Depends on S2-3 |

---

## 5. Sprint 2 Risks

| Risk | Mitigation |
|------|------------|
| `plane-configure.sh` may fail against real Plane (API surface changed) | Verify against live Plane immediately; fix before closing S2-O2 |
| Docker resource limits may cause Plane OOM on dev machine | Run `docker stats` during startup; document minimum in `docs/architecture.md` |
| Fleet framework verification reveals gaps across agents | Create follow-up tasks per gap; do not block sprint on them |
| Security review may uncover additional blockers | Scope: documentation + alert only in Sprint 2; fixes in Sprint 3 if needed |

---

## 6. Definition of Done (Sprint 2)

Sprint 2 is complete when:

- [ ] All `pytest` runs: zero errors, zero failures in `fleet/tests/`
- [ ] Plane is running locally with non-default credentials
- [ ] `scripts/validate-plane-api.sh` passes 11/11 checks against hardened deployment
- [ ] `CLAUDE.md` security rules section exists
- [ ] All 10 fleet agents verified against framework checklist
- [ ] Sprint 2 retrospective written (this doc updated or new file added)

---

## 7. References

- [Sprint 1 Retrospective](../retrospectives/sprint1.md)
- [CHANGELOG.md](../../CHANGELOG.md)
- [Technical Architecture](../architecture.md)
- [Project Requirements](../requirements.md)
- [Original Sprint Breakdown (board memory)](http://localhost:3000/boards/828d80ab-6bda-4d23-9da3-a670f14ea710) — search tag `sprint-planning`
