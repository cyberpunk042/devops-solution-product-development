"""Fleet Plane CLI — manage Plane projects and issues, run bidirectional sync.

Usage:
  python -m fleet plane list-projects [--workspace SLUG]
  python -m fleet plane list-issues   --project PROJECT_ID [--workspace SLUG] [--state STATE_ID] [--priority PRIO]
  python -m fleet plane create-issue  --project PROJECT_ID --title TITLE [--workspace SLUG]
                                      [--description DESC] [--priority PRIO] [--state STATE_ID]
                                      [--assignee USER_ID] [--cycle CYCLE_ID]
  python -m fleet plane list-cycles   --project PROJECT_ID [--workspace SLUG]
  python -m fleet plane list-states   --project PROJECT_ID [--workspace SLUG]
  python -m fleet plane sync          [--workspace SLUG] [--project PROJECT_ID]
                                      [--done-state STATE_ID] [--direction in|out|both]

Environment / .env:
  PLANE_URL      — Plane base URL (e.g. http://localhost:8080)
  PLANE_API_KEY  — Plane personal API token
  PLANE_WORKSPACE — Default workspace slug (optional convenience)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from fleet.core.plane_sync import PlaneSyncer
from fleet.infra.config_loader import ConfigLoader
from fleet.infra.mc_client import MCClient
from fleet.infra.plane_client import PlaneClient

# ─── ANSI colours ────────────────────────────────────────────────────────────

BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
DIM = "\033[2m"
NC = "\033[0m"

# ─── Priority colours ────────────────────────────────────────────────────────

_PRIO_COLOR = {
    "urgent": RED,
    "high": YELLOW,
    "medium": CYAN,
    "low": DIM,
    "none": DIM,
}


def _prio(p: str) -> str:
    return f"{_PRIO_COLOR.get(p, NC)}{p}{NC}"


# ─── Client bootstrap ────────────────────────────────────────────────────────


def _load_plane_client(env: dict) -> PlaneClient:
    """Construct a PlaneClient from .env / os.environ."""
    url = env.get("PLANE_URL") or os.environ.get("PLANE_URL", "")
    key = env.get("PLANE_API_KEY") or os.environ.get("PLANE_API_KEY", "")
    if not url:
        print(f"{RED}ERROR{NC}: PLANE_URL not set (add to .env or environment)")
        sys.exit(1)
    if not key:
        print(f"{RED}ERROR{NC}: PLANE_API_KEY not set (add to .env or environment)")
        sys.exit(1)
    return PlaneClient(base_url=url, api_key=key)


def _load_workspace(env: dict, args: argparse.Namespace) -> str:
    """Resolve workspace slug from --workspace arg or PLANE_WORKSPACE env."""
    ws = getattr(args, "workspace", None)
    if ws:
        return ws
    ws = env.get("PLANE_WORKSPACE") or os.environ.get("PLANE_WORKSPACE", "")
    if not ws:
        print(f"{RED}ERROR{NC}: --workspace not specified and PLANE_WORKSPACE not set")
        sys.exit(1)
    return ws


# ─── Subcommand handlers ─────────────────────────────────────────────────────


async def _list_projects(plane: PlaneClient, workspace: str) -> int:
    """List all Plane projects in a workspace."""
    projects = await plane.list_projects(workspace)
    if not projects:
        print(f"  {DIM}No projects found in workspace '{workspace}'{NC}")
        return 0

    print(f"{BOLD}Projects — {workspace}{NC}")
    for p in projects:
        member = f" {GREEN}(member){NC}" if p.is_member else ""
        print(f"  {CYAN}{p.identifier:10s}{NC} {p.name} {DIM}[{p.id}]{NC}{member}")
        if p.description:
            print(f"             {DIM}{p.description[:70]}{NC}")
    print(f"\n  {DIM}{len(projects)} project(s){NC}")
    return 0


async def _list_issues(
    plane: PlaneClient,
    workspace: str,
    project_id: str,
    *,
    state_id: str | None = None,
    priority: str | None = None,
) -> int:
    """List issues in a Plane project."""
    issues = await plane.list_issues(
        workspace, project_id, state_id=state_id, priority=priority
    )
    if not issues:
        print(f"  {DIM}No issues found{NC}")
        return 0

    print(f"{BOLD}Issues — project {project_id}{NC}")
    for i in issues:
        assignees = f" {DIM}@{','.join(i.assignees[:2])}{NC}" if i.assignees else ""
        cycle = f" {MAGENTA}[cycle]{NC}" if i.cycle_id else ""
        pts = f" {DIM}{i.estimate_point}pt{NC}" if i.estimate_point else ""
        print(
            f"  #{i.sequence_id:4d}  {_prio(i.priority):20s} {i.title[:55]}"
            f"{assignees}{cycle}{pts}"
        )
        print(f"          {DIM}{i.id}{NC}")
    print(f"\n  {DIM}{len(issues)} issue(s){NC}")
    return 0


async def _create_issue(
    plane: PlaneClient,
    workspace: str,
    project_id: str,
    *,
    title: str,
    description: str = "",
    priority: str = "none",
    state_id: str | None = None,
    assignees: list[str] | None = None,
    cycle_id: str | None = None,
) -> int:
    """Create a Plane issue."""
    issue = await plane.create_issue(
        workspace,
        project_id,
        title=title,
        description_html=f"<p>{description}</p>" if description else "",
        priority=priority,
        state_id=state_id,
        assignees=assignees,
        cycle_id=cycle_id,
    )
    print(f"{GREEN}Created{NC} issue #{issue.sequence_id}: {issue.title}")
    print(f"  ID:       {issue.id}")
    print(f"  Priority: {_prio(issue.priority)}")
    if issue.cycle_id:
        print(f"  Cycle:    {issue.cycle_id}")
    return 0


async def _list_cycles(plane: PlaneClient, workspace: str, project_id: str) -> int:
    """List cycles (sprints) in a project."""
    cycles = await plane.list_cycles(workspace, project_id)
    if not cycles:
        print(f"  {DIM}No cycles found{NC}")
        return 0

    _STATUS_COLOR = {"current": GREEN, "upcoming": CYAN, "completed": DIM}
    print(f"{BOLD}Cycles — project {project_id}{NC}")
    for c in cycles:
        color = _STATUS_COLOR.get(c.status, NC)
        dates = ""
        if c.start_date and c.end_date:
            dates = f" {DIM}({c.start_date} → {c.end_date}){NC}"
        print(f"  {color}{c.status:12s}{NC} {c.name}{dates}")
        print(f"               {DIM}{c.id}{NC}")
    print(f"\n  {DIM}{len(cycles)} cycle(s){NC}")
    return 0


async def _list_states(plane: PlaneClient, workspace: str, project_id: str) -> int:
    """List workflow states in a project."""
    states = await plane.list_states(workspace, project_id)
    if not states:
        print(f"  {DIM}No states found{NC}")
        return 0

    _GROUP_COLOR = {
        "backlog": DIM,
        "unstarted": NC,
        "started": CYAN,
        "completed": GREEN,
        "cancelled": RED,
    }
    print(f"{BOLD}States — project {project_id}{NC}")
    for s in states:
        color = _GROUP_COLOR.get(s.group, NC)
        default = f" {YELLOW}(default){NC}" if s.is_default else ""
        print(
            f"  {color}{s.group:12s}{NC} {s.name:20s} "
            f"{DIM}{s.color}{NC}  {DIM}[{s.id}]{NC}{default}"
        )
    print(f"\n  {DIM}{len(states)} state(s){NC}")
    return 0


async def _sync(
    plane: PlaneClient,
    mc: MCClient,
    workspace: str,
    board_id: str,
    *,
    project_ids: list[str],
    done_state_id: str | None,
    direction: str,
) -> int:
    """Run bidirectional Plane ↔ OCMC sync."""
    syncer = PlaneSyncer(
        mc=mc,
        plane=plane,
        board_id=board_id,
        workspace_slug=workspace,
        project_ids=project_ids,
        done_state_id=done_state_id,
    )

    exit_code = 0

    # ── Plane → OCMC ────────────────────────────────────────────────────
    if direction in ("in", "both"):
        print(f"{BOLD}Plane → OCMC{NC}")
        ingest_result = await syncer.ingest_from_plane()
        if ingest_result.created:
            for t in ingest_result.created:
                print(f"  {GREEN}+ Created{NC}  {t.title[:55]}  {DIM}[{t.id[:8]}]{NC}")
        if ingest_result.skipped:
            print(f"  {DIM}  Skipped {ingest_result.skipped_count} already-mapped issue(s){NC}")
        if ingest_result.errors:
            for e in ingest_result.errors:
                print(f"  {RED}  ERROR: {e}{NC}")
            exit_code = 1
        if not ingest_result.created and not ingest_result.errors:
            print(f"  {DIM}Nothing new to ingest{NC}")

    # ── OCMC → Plane ────────────────────────────────────────────────────
    if direction in ("out", "both"):
        if not done_state_id:
            print(f"\n{YELLOW}⚠ Skipping OCMC → Plane push:{NC} --done-state not set")
        else:
            print(f"\n{BOLD}OCMC → Plane{NC}")
            push = await syncer.push_completions_to_plane()
            if push.updated:
                for issue_id in push.updated:
                    print(f"  {GREEN}✓ Updated{NC}  Plane issue {issue_id}")
            if push.skipped:
                print(f"  {DIM}  Skipped {len(push.skipped)} task(s) with no Plane mapping{NC}")
            if push.errors:
                for e in push.errors:
                    print(f"  {RED}  ERROR: {e}{NC}")
                exit_code = 1
            if not push.updated and not push.errors:
                print(f"  {DIM}Nothing to push{NC}")

    return exit_code


# ─── Top-level runner ────────────────────────────────────────────────────────


async def _run_plane(argv: list[str]) -> int:
    """Dispatch plane subcommands."""
    parser = argparse.ArgumentParser(
        prog="fleet plane",
        description="Manage Plane projects and issues; run Plane ↔ OCMC sync",
    )
    subparsers = parser.add_subparsers(dest="action", metavar="ACTION")

    # Shared workspace flag
    _WS = dict(metavar="SLUG", default=None)
    _PROJ = dict(metavar="PROJECT_ID", default=None)

    # list-projects
    p_lp = subparsers.add_parser("list-projects", help="List projects in a workspace")
    p_lp.add_argument("--workspace", **_WS)

    # list-issues
    p_li = subparsers.add_parser("list-issues", help="List issues in a project")
    p_li.add_argument("--workspace", **_WS)
    p_li.add_argument("--project", required=True, **_PROJ)
    p_li.add_argument("--state", metavar="STATE_ID", default=None)
    p_li.add_argument("--priority", choices=["urgent", "high", "medium", "low", "none"], default=None)

    # create-issue
    p_ci = subparsers.add_parser("create-issue", help="Create a Plane issue")
    p_ci.add_argument("--workspace", **_WS)
    p_ci.add_argument("--project", required=True, **_PROJ)
    p_ci.add_argument("--title", required=True)
    p_ci.add_argument("--description", default="")
    p_ci.add_argument("--priority", choices=["urgent", "high", "medium", "low", "none"], default="none")
    p_ci.add_argument("--state", metavar="STATE_ID", default=None)
    p_ci.add_argument("--assignee", metavar="USER_ID", action="append", dest="assignees", default=None)
    p_ci.add_argument("--cycle", metavar="CYCLE_ID", default=None)

    # list-cycles
    p_lc = subparsers.add_parser("list-cycles", help="List cycles (sprints) in a project")
    p_lc.add_argument("--workspace", **_WS)
    p_lc.add_argument("--project", required=True, **_PROJ)

    # list-states
    p_ls = subparsers.add_parser("list-states", help="List workflow states in a project")
    p_ls.add_argument("--workspace", **_WS)
    p_ls.add_argument("--project", required=True, **_PROJ)

    # sync
    p_sy = subparsers.add_parser("sync", help="Bidirectional Plane ↔ OCMC sync")
    p_sy.add_argument("--workspace", **_WS)
    p_sy.add_argument("--project", action="append", dest="projects", default=None, metavar="PROJECT_ID",
                      help="Plane project ID to sync (repeatable; default: all)")
    p_sy.add_argument("--done-state", metavar="STATE_ID", default=None,
                      help="Plane state ID to set when OCMC task reaches done")
    p_sy.add_argument("--direction", choices=["in", "out", "both"], default="both",
                      help="Sync direction: in=Plane→OCMC, out=OCMC→Plane, both (default)")

    args = parser.parse_args(argv)

    if not args.action:
        parser.print_help()
        return 1

    # Bootstrap clients
    loader = ConfigLoader()
    env = loader.load_env()
    plane = _load_plane_client(env)
    workspace = _load_workspace(env, args)

    try:
        if args.action == "list-projects":
            return await _list_projects(plane, workspace)

        if args.action == "list-issues":
            return await _list_issues(
                plane, workspace, args.project,
                state_id=args.state, priority=args.priority,
            )

        if args.action == "create-issue":
            return await _create_issue(
                plane, workspace, args.project,
                title=args.title,
                description=args.description,
                priority=args.priority,
                state_id=args.state,
                assignees=args.assignees,
                cycle_id=args.cycle,
            )

        if args.action == "list-cycles":
            return await _list_cycles(plane, workspace, args.project)

        if args.action == "list-states":
            return await _list_states(plane, workspace, args.project)

        if args.action == "sync":
            token = env.get("LOCAL_AUTH_TOKEN", "")
            if not token:
                print(f"{RED}ERROR{NC}: LOCAL_AUTH_TOKEN not set")
                return 1
            mc = MCClient(token=token)
            board_id = await mc.get_board_id()
            if not board_id:
                print(f"{RED}ERROR{NC}: No OCMC board found")
                await mc.close()
                return 1
            result = await _sync(
                plane, mc, workspace, board_id,
                project_ids=args.projects or [],
                done_state_id=args.done_state,
                direction=args.direction,
            )
            await mc.close()
            return result

    finally:
        await plane.close()

    return 0  # unreachable but satisfies type checkers


def run_plane(args: list[str] | None = None) -> int:
    """Entry point for fleet plane."""
    argv = args if args is not None else sys.argv[2:]
    return asyncio.run(_run_plane(argv))


if __name__ == "__main__":
    sys.exit(run_plane())
