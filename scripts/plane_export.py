#!/usr/bin/env python3
"""Export Plane state to config files — the IaC sync-back mechanism.

Reads live Plane data and updates:
  - .plane-state.json (full state snapshot)
  - config/mission.yaml (project names, descriptions, module status)
  - config/*-board.yaml (cycle dates/status, epic detail updates)

This runs as part of the monitor daemon (300s) via config_sync.py.
Changes to config files get auto-committed by config_sync.

> "We will also need to make it so that we can keep the IaC definition
> in sync as the plane evolve as the agent works, so that if we restart
> it will pick up where we left approximately or even perfectly."
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
import urllib.request

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed")
    sys.exit(1)


def api_get(url: str, token: str, ws: str, path: str) -> Any:
    req = urllib.request.Request(
        f"{url}/api/v1/workspaces/{ws}{path}",
        headers={"X-Api-Key": token},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def main():
    project_dir = Path(os.environ.get("PROJECT_DIR", "."))
    config_file = project_dir / ".plane-config"

    if not config_file.exists():
        print("ERROR: .plane-config not found")
        sys.exit(1)

    env = {}
    with open(config_file) as f:
        for line in f:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                key, val = line.split("=", 1)
                env[key] = val

    url = env.get("PLANE_URL", "http://localhost:8080")
    token = env.get("PLANE_API_TOKEN", "")
    ws = env.get("PLANE_WORKSPACE_SLUG", "fleet")

    if not token:
        print("ERROR: No PLANE_API_TOKEN")
        sys.exit(1)

    try:
        projects = api_get(url, token, ws, "/projects/")["results"]
    except Exception as e:
        print(f"ERROR: Cannot reach Plane: {e}")
        sys.exit(1)

    state = {"exported_at": datetime.utcnow().isoformat() + "Z", "projects": {}}
    changes = 0

    for proj in projects:
        ident = proj["identifier"]
        pid = proj["id"]
        name = proj.get("name", "?")

        # Get live data
        try:
            mods = api_get(url, token, ws, f"/projects/{pid}/modules/")
            mods = mods.get("results", mods) if isinstance(mods, dict) else mods
        except Exception:
            mods = []

        try:
            cycles = api_get(url, token, ws, f"/projects/{pid}/cycles/")
            cycles = cycles.get("results", cycles) if isinstance(cycles, dict) else cycles
        except Exception:
            cycles = []

        try:
            issues = api_get(url, token, ws, f"/projects/{pid}/issues/")
            issue_list = issues.get("results", [])
            issue_count = issues.get("total_results", len(issue_list))
        except Exception:
            issue_list = []
            issue_count = 0

        try:
            labels = api_get(url, token, ws, f"/projects/{pid}/labels/")
            labels = labels.get("results", labels) if isinstance(labels, dict) else labels
        except Exception:
            labels = []

        try:
            states = api_get(url, token, ws, f"/projects/{pid}/states/")
            states = states.get("results", states) if isinstance(states, dict) else states
        except Exception:
            states = []

        state["projects"][ident] = {
            "name": name,
            "emoji": proj.get("emoji", ""),
            "description": (proj.get("description") or "")[:500],
            "modules": [
                {
                    "name": m["name"],
                    "description": (m.get("description") or "")[:200],
                    "status": m.get("status", ""),
                    "total_issues": m.get("total_issues", 0),
                    "completed_issues": m.get("completed_issues", 0),
                }
                for m in mods
            ],
            "cycles": [
                {
                    "name": c["name"],
                    "status": c.get("status", ""),
                    "start_date": c.get("start_date", ""),
                    "end_date": c.get("end_date", ""),
                }
                for c in cycles
            ],
            "issues": [
                {
                    "title": i.get("name", ""),
                    "priority": i.get("priority", ""),
                    "state": i.get("state_detail", {}).get("name", "") if isinstance(i.get("state_detail"), dict) else "",
                    "assignees": [a.get("display_name", "") for a in i.get("assignee_detail", [])] if isinstance(i.get("assignee_detail"), list) else [],
                }
                for i in issue_list[:50]
            ],
            "issue_count": issue_count,
            "label_count": len(labels),
            "state_names": [s["name"] for s in states],
        }

        print(f"  {ident}: {name} — {len(mods)} modules, {len(cycles)} cycles, {issue_count} issues")

    # Write state file
    state_file = project_dir / ".plane-state.json"
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)
    print("State exported to .plane-state.json")

    # ── Update mission.yaml ──
    mission_file = project_dir / "config" / "mission.yaml"
    if mission_file.exists():
        with open(mission_file) as f:
            mission = yaml.safe_load(f)

        mission_changes = 0
        for proj_cfg in mission.get("projects", []):
            ident = proj_cfg["identifier"]
            live = state["projects"].get(ident, {})

            # Sync project name and description
            live_name = live.get("name", "")
            if live_name and live_name != proj_cfg.get("name", ""):
                proj_cfg["name"] = live_name
                mission_changes += 1

            live_desc = live.get("description", "")
            if live_desc and len(live_desc) > 50 and live_desc != proj_cfg.get("description", ""):
                proj_cfg["description"] = live_desc
                mission_changes += 1

            # Sync module status
            live_mods = {m["name"]: m for m in live.get("modules", [])}
            for mod_cfg in proj_cfg.get("modules", []):
                live_mod = live_mods.get(mod_cfg["name"], {})
                if live_mod.get("status") and live_mod["status"] != mod_cfg.get("status", ""):
                    mod_cfg["status"] = live_mod["status"]
                    mission_changes += 1
                # Sync module description if changed significantly
                live_mod_desc = live_mod.get("description", "")
                if live_mod_desc and len(live_mod_desc) > 30:
                    current_desc = mod_cfg.get("description", "")
                    if live_mod_desc != current_desc[:200]:
                        # Only update if live is longer or different
                        if len(live_mod_desc) > len(current_desc) or live_mod_desc[:100] != current_desc[:100]:
                            pass  # Don't overwrite rich descriptions with truncated API responses

        if mission_changes > 0:
            with open(mission_file, "w") as f:
                yaml.dump(mission, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)
            print(f"mission.yaml: {mission_changes} changes synced")
            changes += mission_changes
        else:
            print("mission.yaml: no changes")

    # ── Update board configs with cycle status ──
    for ident_lower, ident_upper in [("aicp", "AICP"), ("fleet", "OF"), ("dspd", "DSPD"), ("nnrt", "NNRT")]:
        board_file = project_dir / "config" / f"{ident_lower}-board.yaml"
        if not board_file.exists():
            continue

        live = state["projects"].get(ident_upper, {})
        if not live:
            continue

        with open(board_file) as f:
            board = yaml.safe_load(f)

        board_changes = 0

        # Update cycle status
        live_cycles = {c["name"]: c for c in live.get("cycles", [])}
        for cycle_cfg in board.get("cycles", []):
            live_cycle = live_cycles.get(cycle_cfg["name"], {})
            if live_cycle.get("status") and live_cycle["status"] != cycle_cfg.get("status", ""):
                cycle_cfg["status"] = live_cycle["status"]
                board_changes += 1

        if board_changes > 0:
            with open(board_file, "w") as f:
                yaml.dump(board, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)
            print(f"{ident_lower}-board.yaml: {board_changes} changes synced")
            changes += board_changes

    if changes > 0:
        print(f"\nTotal: {changes} changes synced to config files")
    else:
        print("\nNo config changes detected")


if __name__ == "__main__":
    main()