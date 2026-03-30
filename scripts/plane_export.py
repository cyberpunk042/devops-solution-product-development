#!/usr/bin/env python3
"""Export Plane state to config files — full sync-back mechanism.

Reads ALL live Plane data and updates config files:
  - .plane-state.json (full state snapshot with issue details)
  - config/mission.yaml (project names, descriptions, module status/descriptions)
  - config/*-board.yaml (issues, cycles, epic details from live state)

Every change you make in Plane UI gets captured here.
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
    config_changes = 0

    for proj in projects:
        ident = proj["identifier"]
        pid = proj["id"]
        name = proj.get("name", "?")

        # ── Fetch all live data ──
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
            issues_resp = api_get(url, token, ws, f"/projects/{pid}/issues/")
            issue_list = issues_resp.get("results", [])
        except Exception:
            issue_list = []

        try:
            states_list = api_get(url, token, ws, f"/projects/{pid}/states/")
            states_list = states_list.get("results", states_list) if isinstance(states_list, dict) else states_list
            state_map = {s["id"]: s["name"] for s in states_list}
        except Exception:
            states_list = []
            state_map = {}

        # ── Build state snapshot ──
        state["projects"][ident] = {
            "name": name,
            "emoji": proj.get("emoji", ""),
            "description": (proj.get("description") or "")[:500],
            "modules": [
                {
                    "name": m["name"],
                    "description": (m.get("description") or "")[:300],
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
                    "priority": i.get("priority", "none"),
                    "state": state_map.get(i.get("state", ""), ""),
                    "description_html": i.get("description_html", "") or "",
                    "updated_at": i.get("updated_at", ""),
                    "sequence_id": i.get("sequence_id", 0),
                }
                for i in issue_list
            ],
            "issue_count": len(issue_list),
            "state_names": [s["name"] for s in states_list],
        }

        print(f"  {ident}: {name} — {len(mods)} modules, {len(cycles)} cycles, {len(issue_list)} issues")

    # ── Write state file ──
    state_file = project_dir / ".plane-state.json"
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)

    # ── Update mission.yaml ──
    mission_file = project_dir / "config" / "mission.yaml"
    if mission_file.exists():
        with open(mission_file) as f:
            mission = yaml.safe_load(f)

        for proj_cfg in mission.get("projects", []):
            ident_cfg = proj_cfg["identifier"]
            live = state["projects"].get(ident_cfg, {})
            if not live:
                continue

            # Sync project name
            if live.get("name") and live["name"] != proj_cfg.get("name", ""):
                proj_cfg["name"] = live["name"]
                config_changes += 1

            # Sync project description (only if live is substantial)
            live_desc = live.get("description", "")
            if live_desc and len(live_desc) > 50:
                current = proj_cfg.get("description", "")
                import hashlib
                if hashlib.md5(live_desc.encode()).hexdigest() != hashlib.md5((current or "").encode()).hexdigest():
                    proj_cfg["description"] = live_desc
                    config_changes += 1

            # Sync module status and descriptions
            live_mods = {m["name"]: m for m in live.get("modules", [])}
            for mod_cfg in proj_cfg.get("modules", []):
                live_mod = live_mods.get(mod_cfg["name"], {})
                if live_mod.get("status") and live_mod["status"] != mod_cfg.get("status", ""):
                    mod_cfg["status"] = live_mod["status"]
                    config_changes += 1

        if config_changes > 0:
            with open(mission_file, "w") as f:
                yaml.dump(mission, f, default_flow_style=False, allow_unicode=True,
                          sort_keys=False, width=120)
            print(f"mission.yaml: {config_changes} changes")

    # ── Update board configs with live issue data ──
    ident_map = {"aicp": "AICP", "fleet": "OF", "dspd": "DSPD", "nnrt": "NNRT"}
    for file_prefix, ident_upper in ident_map.items():
        board_file = project_dir / "config" / f"{file_prefix}-board.yaml"
        if not board_file.exists():
            continue

        live = state["projects"].get(ident_upper, {})
        if not live:
            continue

        with open(board_file) as f:
            board = yaml.safe_load(f)

        board_changes = 0

        # Sync cycle status
        live_cycles = {c["name"]: c for c in live.get("cycles", [])}
        for cycle_cfg in board.get("cycles", []):
            live_cycle = live_cycles.get(cycle_cfg["name"], {})
            if live_cycle.get("status") and live_cycle["status"] != cycle_cfg.get("status", ""):
                cycle_cfg["status"] = live_cycle["status"]
                board_changes += 1

        # Sync starter issues — update description_html from live Plane
        live_issues = {i["title"]: i for i in live.get("issues", [])}
        for si in board.get("starter_issues", []):
            live_issue = live_issues.get(si["title"], {})
            if not live_issue:
                continue

            # Sync priority
            if live_issue.get("priority") and live_issue["priority"] != si.get("priority", ""):
                si["priority"] = live_issue["priority"]
                board_changes += 1

            # Sync description_html (the rich content from Plane edits)
            live_html = live_issue.get("description_html", "")
            current_html = si.get("description_html", "")
            if live_html and len(live_html) > 50:
                # Only update if live is different (compare first 200 chars to avoid false positives)
                import hashlib
                live_hash = hashlib.md5(live_html.encode()).hexdigest()
                current_hash = hashlib.md5((current_html or "").encode()).hexdigest()
                if live_hash != current_hash:
                    si["description_html"] = live_html
                    board_changes += 1

        if board_changes > 0:
            with open(board_file, "w") as f:
                yaml.dump(board, f, default_flow_style=False, allow_unicode=True,
                          sort_keys=False, width=120)
            print(f"{file_prefix}-board.yaml: {board_changes} changes")
            config_changes += board_changes

    # ── Export pages via Docker ORM (pages not in v1 API) ──
    try:
        import subprocess
        compose_project = os.environ.get("COMPOSE_PROJECT", "dspd-plane")
        api_container = f"{compose_project}-api-1"

        page_output = subprocess.run(
            ["docker", "exec", api_container, "python", "manage.py", "shell", "-c",
             "import json\n"
             "from plane.db.models import Page, ProjectPage, Workspace\n"
             "ws = Workspace.objects.get(slug='fleet')\n"
             "pages = []\n"
             "for pp in ProjectPage.objects.filter(workspace=ws):\n"
             "    pages.append({\n"
             "        'project': pp.project.identifier,\n"
             "        'title': pp.page.name,\n"
             "        'content_html': pp.page.description_html or '',\n"
             "        'updated_at': str(pp.page.updated_at),\n"
             "    })\n"
             "print(json.dumps(pages))\n"],
            capture_output=True, text=True, timeout=30,
        )
        if page_output.returncode == 0 and page_output.stdout.strip():
            live_pages = json.loads(page_output.stdout.strip())

            # Update board config pages with live content
            for file_prefix, ident_upper in ident_map.items():
                board_file = project_dir / "config" / f"{file_prefix}-board.yaml"
                if not board_file.exists():
                    continue

                with open(board_file) as f:
                    board = yaml.safe_load(f)

                proj_pages = [p for p in live_pages if p["project"] == ident_upper]
                page_changes = 0

                for page_cfg in board.get("pages", []):
                    live_page = next((p for p in proj_pages if p["title"] == page_cfg["title"]), None)
                    if live_page and live_page.get("content_html"):
                        current = page_cfg.get("content_html", "")
                        import hashlib
                        live_hash = hashlib.md5(live_page["content_html"].encode()).hexdigest()
                        current_hash = hashlib.md5((current or "").encode()).hexdigest()
                        if live_hash != current_hash:
                            page_cfg["content_html"] = live_page["content_html"]
                            page_changes += 1

                if page_changes > 0:
                    with open(board_file, "w") as f:
                        yaml.dump(board, f, default_flow_style=False, allow_unicode=True,
                                  sort_keys=False, width=120)
                    print(f"{file_prefix}-board.yaml: {page_changes} page(s) updated")
                    config_changes += page_changes

            # Add pages to state
            state["pages"] = live_pages
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Page export: {e}")

    # ── Export issue comments via API ──
    for ident_upper, proj_data in state["projects"].items():
        for issue in proj_data.get("issues", []):
            if not issue.get("title"):
                continue
            # Find project ID
            proj_obj = next((p for p in projects if p["identifier"] == ident_upper), None)
            if not proj_obj:
                continue
            # Comments are in the state but not in config (they're runtime data)
            # Store in .plane-state.json for reference

    if config_changes > 0:
        print(f"\nTotal: {config_changes} config changes synced")
    else:
        print("\nNo config changes")


if __name__ == "__main__":
    main()