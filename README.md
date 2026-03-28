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

**Phase 0: Foundation** — initial project structure and requirements.

## License

AGPLv3 (matching Plane)
