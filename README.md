# DSPD — DevOps Solution Product Development

Project management surface for the OpenClaw Fleet, built on self-hosted [Plane](https://plane.so).

## Vision

The fleet needs a real project management tool — not just a 4-stage task board.
DSPD provides sprints, epics, analytics, velocity tracking, and cross-project
dependency mapping. The PM agent bridges Plane ↔ OCMC so agents work in their
surface while humans plan in theirs.

## Architecture

```
Human → Plane (sprints, epics, analytics)
  ↓
Project Manager agent → reads Plane, dispatches to OCMC
  ↓
Fleet agents → execute via OCMC + MCP tools
  ↓
Results → PM updates Plane, PRs merged on GitHub
```

## Quick Start

```bash
# First-time install (IaC — generates secrets, starts Plane, seeds mission)
./setup.sh install

# Other commands
./setup.sh start      # Start Plane services
./setup.sh stop       # Stop Plane services
./setup.sh status     # Show service health
./setup.sh validate   # Run API validation (11 checks)
```

## Mission Configuration

The mission is defined in YAML, not hardcoded in scripts:

| Config File | Purpose |
|-------------|---------|
| `config/mission.yaml` | Workspace, 4 projects, modules/epics, labels, estimates |
| `config/aicp-board.yaml` | AICP: LocalAI independence 5 stages, wiki pages, acceptance criteria |
| `config/fleet-board.yaml` | Fleet: operational modules, status pages |
| `config/dspd-board.yaml` | DSPD: self-hosting phases, architecture pages |
| `config/nnrt-board.yaml` | NNRT: NLP pipeline modules, assessment pages |

`setup.sh install` reads these configs and seeds Plane via `scripts/plane-seed-mission.sh`.
The PM agent creates tasks from the epics — not this IaC.

## Projects in Plane

| ID | Project | Description |
|----|---------|-------------|
| AICP | aicp | AI Control Platform — **LocalAI independence is THE primary mission** |
| OF | openclaw-fleet | Fleet operations, MCP tools, orchestrator, agents |
| DSPD | dspd | This project — Plane deployment and integration |
| NNRT | nnrt | Narrative-to-Neutral Report Transformer |

## Status

| Phase | Status |
|-------|--------|
| Phase 0: Foundation | ✅ Complete |
| Phase 1: Self-host Plane | IaC built, needs deploy |
| Phase 2: Fleet CLI | Code done, needs live test |
| Phase 3: MCP + Webhooks | Code done, needs live test |
| Phase 4: Multi-project + Analytics | Not started |

## Documentation

| Document | Description |
|----------|-------------|
| [CLAUDE.md](CLAUDE.md) | Project conventions — **read before touching any file** |
| [docs/architecture.md](docs/architecture.md) | Technical architecture — service graph, ports, data flow |
| [docs/requirements.md](docs/requirements.md) | Phased feature requirements with acceptance criteria |
| [docs/milestones/implementation-plan.md](docs/milestones/implementation-plan.md) | Full scope: what exists, what's missing, build order |
| [docs/milestones/sprint2.md](docs/milestones/sprint2.md) | Sprint 2 plan |
| [docs/retrospectives/sprint1.md](docs/retrospectives/sprint1.md) | Sprint 1 retrospective |
| [CHANGELOG.md](CHANGELOG.md) | All changes by sprint |

## Related Projects

| Project | Repo | Relationship |
|---------|------|-------------|
| Fleet | [openclaw-fleet](https://github.com/cyberpunk042/openclaw-fleet) | Agents work here, PM bridges to Plane |
| AICP | [devops-expert-local-ai](https://github.com/cyberpunk042/devops-expert-local-ai) | LocalAI independence — the primary mission |
| NNRT | [Narrative-to-Neutral-Report-Transformer](https://github.com/cyberpunk042/Narrative-to-Neutral-Report-Transformer) | NLP pipeline project |

## License

AGPLv3 (matching Plane)