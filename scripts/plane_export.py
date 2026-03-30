#!/usr/bin/env python3
"""Export Plane state to .plane-state.json + update mission.yaml."""

import json
import os
import sys
import urllib.request
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml not installed")
    sys.exit(1)


def api_get(url, token, ws, path):
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

    # Read config
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
        print("ERROR: No PLANE_API_TOKEN in .plane-config")
        sys.exit(1)

    # Export state
    projects = api_get(url, token, ws, "/projects/")["results"]
    status = {"exported_at": "", "projects": {}}

    from datetime import datetime
    status["exported_at"] = datetime.utcnow().isoformat() + "Z"

    for proj in projects:
        ident = proj["identifier"]
        pid = proj["id"]
        name = proj.get("name", "?")

        try:
            mods_resp = api_get(url, token, ws, f"/projects/{pid}/modules/")
            mods = mods_resp.get("results", mods_resp) if isinstance(mods_resp, dict) else mods_resp
        except Exception:
            mods = []

        try:
            cycles_resp = api_get(url, token, ws, f"/projects/{pid}/cycles/")
            cycles = cycles_resp.get("results", cycles_resp) if isinstance(cycles_resp, dict) else cycles_resp
        except Exception:
            cycles = []

        try:
            issues_resp = api_get(url, token, ws, f"/projects/{pid}/issues/")
            issue_count = issues_resp.get("total_results", len(issues_resp.get("results", [])))
        except Exception:
            issue_count = 0

        try:
            labels_resp = api_get(url, token, ws, f"/projects/{pid}/labels/")
            labels = labels_resp.get("results", labels_resp) if isinstance(labels_resp, dict) else labels_resp
        except Exception:
            labels = []

        try:
            states_resp = api_get(url, token, ws, f"/projects/{pid}/states/")
            states = states_resp.get("results", states_resp) if isinstance(states_resp, dict) else states_resp
        except Exception:
            states = []

        status["projects"][ident] = {
            "name": name,
            "emoji": proj.get("emoji", ""),
            "description": (proj.get("description") or "")[:200],
            "modules": len(mods),
            "module_details": [
                {
                    "name": m["name"],
                    "status": m.get("status", ""),
                    "total_issues": m.get("total_issues", 0),
                    "completed_issues": m.get("completed_issues", 0),
                }
                for m in mods
            ],
            "cycles": len(cycles),
            "cycle_details": [
                {
                    "name": c["name"],
                    "status": c.get("status", ""),
                    "start_date": c.get("start_date", ""),
                    "end_date": c.get("end_date", ""),
                }
                for c in cycles
            ],
            "issues": issue_count,
            "labels": len(labels),
            "states": [s["name"] for s in states],
        }
        print(f"  {ident}: {name} — {len(mods)} modules, {len(cycles)} cycles, {issue_count} issues")

    # Write state file
    state_file = project_dir / ".plane-state.json"
    with open(state_file, "w") as f:
        json.dump(status, f, indent=2)
    print(f"State exported to .plane-state.json")

    # Update mission.yaml with current module status
    mission_file = project_dir / "config" / "mission.yaml"
    if mission_file.exists():
        with open(mission_file) as f:
            mission = yaml.safe_load(f)

        updated_modules = 0
        for proj_cfg in mission.get("projects", []):
            ident = proj_cfg["identifier"]
            proj_status = status["projects"].get(ident, {})
            mod_details = {m["name"]: m for m in proj_status.get("module_details", [])}

            for mod_cfg in proj_cfg.get("modules", []):
                if mod_cfg["name"] in mod_details:
                    live = mod_details[mod_cfg["name"]]
                    if live.get("status") and live["status"] != mod_cfg.get("status", ""):
                        mod_cfg["status"] = live["status"]
                        updated_modules += 1

        if updated_modules > 0:
            with open(mission_file, "w") as f:
                yaml.dump(mission, f, default_flow_style=False, allow_unicode=True, sort_keys=False, width=120)
            print(f"mission.yaml: {updated_modules} module statuses updated")
        else:
            print("mission.yaml: no changes")


if __name__ == "__main__":
    main()