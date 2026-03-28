# CLAUDE.md — DSPD Project Conventions

**Read this before touching any DSPD file.**

This project integrates self-hosted [Plane](https://github.com/makeplane/plane) with the OpenClaw Fleet.
Your work here connects two live surfaces — Plane (project management) and OCMC (agent operations).

---

## Project Layout

```
devops-solution-product-development/
├── docs/
│   ├── architecture.md      # Technical architecture — READ FIRST
│   └── requirements.md      # Feature requirements per phase
├── fleet/
│   ├── infra/
│   │   └── plane_client.py  # Plane REST API client (async, typed)
│   └── cli/
│       └── plane.py         # CLI commands: fleet plan create/list/sync
├── docker/
│   ├── docker-compose.plane.yml   # Plane self-hosted stack
│   ├── nginx.plane.conf           # Nginx reverse proxy
│   └── .env.plane.example         # Environment template
├── scripts/
│   └── setup-plane.sh             # First-run setup
├── tests/
│   ├── unit/                      # Fast, no network
│   └── integration/               # Requires live Plane instance
├── pyproject.toml
├── CLAUDE.md   ← you are here
└── README.md
```

---

## Architecture Rules (Non-Negotiable)

1. **PM agent is the sole writer to Plane.** No other agent writes to Plane directly.
2. **plane_client.py is the only Plane API caller.** No inline `httpx.get()` calls outside this module.
3. **OCMC and Plane are NOT the same thing.** OCMC is for agent ops; Plane is for project management. Do not conflate them.
4. **Separate Docker Compose.** Plane runs in `docker-compose.plane.yml`, not with OCMC.
5. **No shared PostgreSQL.** Plane has its own `plane-db` container. Do not attach it to OCMC's database.
6. **Webhook HMAC verification is mandatory.** Never process a Plane webhook without verifying its signature.

---

## Code Standards

### Python

- **Type hints on all public functions** (no `Any` unless unavoidable)
- **Docstrings on all public classes and non-obvious functions**
- **Formatting:** ruff (line-length 100, target py311)
- **Imports:** stdlib → third-party → local, sorted
- **No hardcoded credentials** — use `python-dotenv` + `.env` (gitignored)
- **No hardcoded URLs or ports** — use config constants from `dspd/config.py`

### Bash / Shell

- Shebang: `#!/usr/bin/env bash`
- Strict mode: `set -euo pipefail`
- Quote all variables: `"$VAR"`
- No hardcoded paths; use `$HOME`, env vars, or function arguments

### Tests

- Unit tests: no network, no Docker, mock `httpx` with `pytest-httpx`
- Integration tests: require live Plane on `localhost:8080`; mark `@pytest.mark.integration`
- Run unit tests before committing: `pytest -m unit`

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `PLANE_BASE_URL` | Plane instance URL | Yes |
| `PLANE_API_KEY` | Personal access token | Yes |
| `PLANE_WORKSPACE_SLUG` | Workspace slug | Yes |
| `PLANE_DEFAULT_PROJECT` | Default project slug for CLI | No |
| `PLANE_WEBHOOK_SECRET` | HMAC secret for webhook verification | Yes (Phase 3) |
| `OCMC_BASE_URL` | Mission Control API URL | Yes (PM agent only) |
| `OCMC_AUTH_TOKEN` | OCMC agent token | Yes (PM agent only) |

Copy `.env.plane.example` to `.env` and fill in values. **Never commit `.env`.**

---

## Git & Commit Standards

Follow fleet-wide conventions:

```
type(scope): description [task:<task-id>]
```

Examples:
```
feat(plane_client): add async work item creation
fix(docker): correct plane-db port binding
docs(architecture): add webhook sequence diagram
chore(pyproject): add missing pytest-httpx dependency
```

Scopes: `plane_client`, `cli`, `docker`, `scripts`, `tests`, `docs`, `pyproject`

---

## Port Allocation

| Service | Host Port | Do Not Change |
|---------|-----------|---------------|
| OCMC API | 8000 | ✅ taken |
| OCMC UI | 3000 | ✅ taken |
| **Plane** | **8080** | DSPD reserved |
| Plane DB | 5433 | internal only |

---

## Fleet Workflow

When working on DSPD tasks:

1. `fleet_read_context(task_id=..., project="dspd")` — always first
2. `fleet_task_accept(plan="...")` — before starting work
3. Work in the assigned worktree (check `custom_field_values.worktree`)
4. Commit early and often: `fleet_commit(files=[...], message="...")`
5. `fleet_task_complete(summary="...")` — one call handles PR, IRC, MC

---

## Common Mistakes to Avoid

| ❌ Wrong | ✅ Right |
|----------|----------|
| Calling `httpx` directly in CLI code | Use `PlaneClient` methods |
| Using `plane.so` cloud API | Use `PLANE_BASE_URL` env var (self-hosted) |
| Writing to Plane from a non-PM agent | Route via PM agent |
| Hardcoding port 8080 | Use `settings.PLANE_BASE_URL` |
| Skipping HMAC verification | Always verify before processing webhooks |
| One big commit at the end | Commit each logical change separately |

---

## Phase Boundaries

Check `docs/requirements.md` §5 before implementing. Do not build Phase 2 features while Phase 1 is incomplete. The phases are:

- **Phase 0:** Foundation docs + project structure ← you are here
- **Phase 1:** Self-host Plane (Docker Compose, working instance)
- **Phase 2:** Fleet CLI (`fleet plan create/list/sync`)
- **Phase 3:** MCP + webhooks (PM agent native Plane access)
- **Phase 4:** Multi-project + analytics

---

## Where to Get Help

- Architecture questions → post comment on current task, tag `@architect`
- Plane API questions → [developers.plane.so](https://developers.plane.so/)
- Fleet tool questions → read `AGENTS.md` in workspace root
- Blocked → `fleet_pause(reason="...", needed="...")` and stop
