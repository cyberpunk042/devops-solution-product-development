# DSPD — DevOps Solution Product Development

Project management surface for the OpenClaw Fleet, built on [Plane](https://plane.so).

## Vision

The fleet needs a real project management tool — not just a 4-stage task board.
DSPD provides sprints, epics, analytics, velocity tracking, and cross-project
dependency mapping through self-hosted Plane.

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

## Status

**Sprint 1 complete** — Plane Docker stack deployed and verified, REST API client and CLI built, bidirectional OCMC sync implemented.  
**Sprint 2 in progress** — quality hardening, credential security, fleet framework verification.

See [CHANGELOG.md](CHANGELOG.md) for full history and [docs/retrospectives/sprint1.md](docs/retrospectives/sprint1.md) for Sprint 1 outcomes.

## Documentation

| Document | Description |
|----------|-------------|
| [docs/architecture.md](docs/architecture.md) | Technical architecture — service graph, ports, data flow, security model |
| [docs/requirements.md](docs/requirements.md) | Phased feature requirements and acceptance criteria |
| [docs/plane-setup.md](docs/plane-setup.md) | **Complete setup guide** — architecture, multi-fleet, config reference, IaC, onboarding, troubleshooting |
| [CLAUDE.md](CLAUDE.md) | Project conventions — read before touching any file |
| [CHANGELOG.md](CHANGELOG.md) | All changes by sprint |
| [docs/retrospectives/sprint1.md](docs/retrospectives/sprint1.md) | Sprint 1 retrospective |
| [docs/milestones/sprint2.md](docs/milestones/sprint2.md) | Sprint 2 plan |

## License

AGPLv3 (matching Plane)
