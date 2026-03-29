# Plane IaC Evolution — From Working to Production-Ready

**Date:** 2026-03-29
**Status:** Active — tracks all remaining Plane configuration work

---

## Current State

Plane is deployed and seeded. 4 projects with modules, labels, states, estimates, sprints.
Fleet connected. But the IaC is incomplete — several platform features aren't configured,
the setup wizard still shows on first visit, and the PM agent can't drive sprints yet.

### What Works

| Item | Status |
|------|--------|
| Docker compose (12 services) | ✅ Running |
| Workspace "Fleet" created | ✅ |
| 4 projects with proper names + emojis | ✅ |
| Per-project custom workflow states | ✅ |
| 22 modules/epics with descriptions | ✅ |
| 19 labels per project | ✅ |
| Story point estimates (Fibonacci) | ✅ |
| 4 active sprints (cycles) | ✅ |
| Epic details with acceptance criteria | ✅ |
| API access from fleet CLI | ✅ |
| Admin user with password | ✅ |
| God-mode instance configured | ✅ |
| plane-validate-api.sh (11 checks) | ✅ |
| plane-startup-verify.sh (15 checks) | ✅ |

### What's Missing or Broken

| Item | Status | Priority |
|------|--------|----------|
| Cover images for projects | ❌ Not set | Medium |
| Project icon_prop (Lucide icons) | ❌ Only emoji set | Low |
| logo_props per project | ❌ Not configured | Low |
| Pages (wiki) via IaC | ❌ Skipped — Plane M2M model needs API not ORM | High |
| Workspace member roles | ❌ Only admin exists | Medium |
| GitHub integration | ❌ Not configured | High |
| Webhook registration | ❌ Script exists but untested | Medium |
| Plane MCP server for PM | ❌ Not researched yet | High |
| PM agent Plane access | ❌ No MCP config | High |
| Plane ↔ OCMC sync live test | ❌ Code exists, never tested | High |
| Migration timeout on first run | ✅ Fixed (600s) | — |
| Proxy port mapping | ✅ Fixed (8080:8080) | — |
| API cache after config | ✅ Fixed (restart API) | — |
| God-mode setup wizard | ✅ Fixed (onboarding flags) | — |

---

## Milestones

### M-P01: Pages via Plane REST API ← HIGH PRIORITY

The Django ORM approach for pages failed because the `project_pages` through table
requires `workspace_id` which isn't set by `page.projects.add()`.

**Fix:** Use the Plane REST API (`POST /api/v1/workspaces/{slug}/projects/{id}/pages/`)
instead of the Django ORM. The API handles the through model correctly.

**Content to seed (from config/*-board.yaml):**
- AICP Architecture page (routing diagram, mode definitions)
- LocalAI Independence Strategic Vision page (verbatim user quotes, 5 stages)
- AICP Current State Assessment (template for PM to fill)
- Fleet Architecture page (agent roster, orchestrator, services)
- DSPD Architecture page (three surfaces diagram, rules)
- NNRT Architecture page (pipeline diagram)

**Acceptance:** All pages visible in Plane UI under each project's Pages section.

### M-P02: GitHub Integration

Connect Plane projects to their GitHub repos for:
- PR links in issues
- Commit references
- CI status in issue comments

**Configuration:**
- AICP → `cyberpunk042/devops-expert-local-ai`
- OF → `cyberpunk042/openclaw-fleet`
- DSPD → `cyberpunk042/devops-solution-product-development`
- NNRT → `cyberpunk042/Narrative-to-Neutral-Report-Transformer`

**Requires:** GitHub OAuth app or personal token configured in Plane god-mode.
**Script:** `scripts/plane-setup-github.sh`

### M-P03: Workspace Members and Roles

Currently only the admin user exists. Need:
- Fleet service account (for PM agent API access)
- Member roles defined per project
- Agent identity mapping (which Plane member = which fleet agent)

**Script:** Update `plane-configure.sh` or new `scripts/plane-setup-members.sh`

### M-P04: Plane MCP Server for PM Agent ← HIGH PRIORITY

Research and configure Plane's MCP server so the PM agent can:
- List projects, cycles, modules natively
- Create/update issues via MCP tools
- Read sprint data (velocity, burn-down)
- Manage cycle membership

**Investigation needed:**
1. Does Plane ship with a built-in MCP server?
2. If yes, what tools does it expose?
3. If no, can we build one using the REST API?
4. How to configure it in the PM agent's `.mcp.json`?

**Script:** `scripts/plane-setup-mcp.sh`

### M-P05: Live Sync Testing (Plane ↔ OCMC)

The sync code exists (`fleet/core/plane_sync.py`) but has never been tested
against a live Plane + OCMC setup. Need:

1. Create a test issue in Plane via CLI
2. Run `fleet plan sync --direction in` → verify OCMC task created
3. Complete the OCMC task
4. Run `fleet plan sync --direction out` → verify Plane issue updated to Done
5. Verify bidirectional (`--direction both`) in one call

**Acceptance:** Full round-trip: Plane → OCMC → agent works → OCMC done → Plane done.

### M-P06: Webhook Handler Live Test

The webhook handler (`dspd/webhooks.py`) and registration script
(`scripts/plane-setup-webhooks.sh`) exist but have never been tested live.

1. Register webhook in Plane
2. Start webhook receiver (`uvicorn dspd.webhooks:app --port 8001`)
3. Create an issue in Plane
4. Verify webhook fires with correct HMAC
5. Verify event handler logs the event

**Note:** Plane Community Edition may not support webhooks. Need to verify.

### M-P07: Project Cover Images and Branding

Each project should have a cover image and proper branding:
- Cover image (Plane supports URL or upload)
- Icon prop (Lucide icon name as alternative to emoji)
- Logo props (SVG or image)

**Config:** Add `cover_image`, `icon_prop` fields to `config/mission.yaml`
**Script:** Update `plane-seed-mission.sh` to apply via API PATCH

### M-P08: setup.sh install End-to-End Verification

Run `./setup.sh install` from a completely clean state (no plane.env, no volumes)
and verify:
1. Secrets generated
2. All 12 containers start
3. Migrations complete
4. Admin user created + onboarded
5. 4 projects with names, emojis, states, modules, labels, estimates
6. Pages seeded (after M-P01)
7. Sprints created
8. API validation 11/11
9. Startup verification 15/15
10. Fleet credentials exported
11. No setup wizard on first visit

**Acceptance:** One command, zero manual steps, everything configured.

### M-P09: Plane Backup and Restore

IaC must include disaster recovery:
- `./setup.sh backup` — dump PostgreSQL + volume data
- `./setup.sh restore <backup>` — restore from backup
- Document backup schedule recommendation

### M-P10: Multi-Fleet Plane Sharing

Per the strategic vision:
> "having our full 2 cluster LocalAI peered in the network with one Plane
> and eventually 2 or even 3 fleets"

Plane is the shared surface. Need:
- Workspace design for multi-fleet (one workspace, fleet-specific labels?)
- Or separate workspaces per fleet?
- Cross-fleet project visibility
- PM agent access from multiple fleet instances

**Depends on:** Federation (fleet/core/federation.py) and Stage 4/5 of LocalAI.

---

## Priority Order

1. **M-P01** Pages via API — content is ready in config, just needs API calls
2. **M-P04** Plane MCP for PM — blocks PM agent from driving sprints
3. **M-P05** Live sync test — blocks autonomous flow
4. **M-P02** GitHub integration — needed for PR links in issues
5. **M-P06** Webhook test — needed for event-driven flow
6. **M-P03** Workspace members — needed before PM agent connects
7. **M-P08** End-to-end verification — clean install test
8. **M-P07** Cover images — polish
9. **M-P09** Backup/restore — operational
10. **M-P10** Multi-fleet — future

---

## Dependencies

```
M-P01 (Pages) → no deps, can start now
M-P02 (GitHub) → needs GitHub OAuth in god-mode
M-P03 (Members) → no deps
M-P04 (MCP) → needs research first
M-P05 (Sync test) → needs M-P03 (PM needs Plane access)
M-P06 (Webhooks) → needs M-P01 (verify Plane supports webhooks)
M-P07 (Covers) → no deps, polish
M-P08 (E2E) → needs M-P01 through M-P06
M-P09 (Backup) → no deps
M-P10 (Multi-fleet) → needs everything else + federation
```