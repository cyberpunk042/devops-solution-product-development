"""Fleet config loader — reads YAML configs and TOOLS.md credentials.

Implements core.interfaces.ConfigLoader.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

import yaml

from fleet.core.interfaces import ConfigLoader as ConfigLoaderInterface
from fleet.core.models import Project


class ConfigLoader(ConfigLoaderInterface):
    """Load fleet configuration from YAML files and TOOLS.md."""

    def __init__(self, fleet_dir: Optional[str] = None):
        if fleet_dir:
            self._fleet_dir = Path(fleet_dir)
        elif os.environ.get("FLEET_DIR"):
            self._fleet_dir = Path(os.environ["FLEET_DIR"])
        else:
            # Resolve from package location: fleet/ is inside the fleet dir
            self._fleet_dir = Path(__file__).resolve().parent.parent.parent

    @property
    def fleet_dir(self) -> Path:
        return self._fleet_dir

    def load_projects(self) -> dict[str, Project]:
        """Load project registry from config/projects.yaml."""
        path = self._fleet_dir / "config" / "projects.yaml"
        if not path.exists():
            return {}

        with open(path) as f:
            cfg = yaml.safe_load(f) or {}

        projects = {}
        for name, info in cfg.get("projects", {}).items():
            if info.get("local"):
                # Local projects don't have GitHub coords in the projects.yaml
                # but may have them in url-templates.yaml
                projects[name] = Project(
                    name=name,
                    owner="",
                    repo="",
                    description=info.get("description", ""),
                    local=True,
                )
            else:
                projects[name] = Project(
                    name=name,
                    owner="",  # Filled from url-templates.yaml
                    repo=info.get("repo", "").split("/")[-1] if info.get("repo") else "",
                    description=info.get("description", ""),
                )

        # Enrich with GitHub owner/repo from url-templates.yaml
        url_templates = self.load_url_templates()
        for name, mapping in url_templates.get("projects", {}).items():
            if name in projects:
                projects[name].owner = mapping.get("owner", "")
                projects[name].repo = mapping.get("repo", "")

        return projects

    def load_url_templates(self) -> dict:
        """Load URL templates from config/url-templates.yaml."""
        path = self._fleet_dir / "config" / "url-templates.yaml"
        if not path.exists():
            return {}

        with open(path) as f:
            return yaml.safe_load(f) or {}

    def load_tools_md(self, workspace: str) -> dict:
        """Load credentials from a TOOLS.md file.

        Parses lines like: - `KEY=value`
        Returns dict of key→value.
        """
        tools_path = Path(workspace) / "TOOLS.md"
        if not tools_path.exists():
            return {}

        result = {}
        pattern = re.compile(r"^-\s*`(\w+)=(.+)`\s*$")

        with open(tools_path) as f:
            for line in f:
                match = pattern.match(line.strip())
                if match:
                    result[match.group(1)] = match.group(2)

        return result

    def load_env(self) -> dict:
        """Load fleet .env file."""
        env_path = self._fleet_dir / ".env"
        if not env_path.exists():
            return {}

        result = {}
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    result[key.strip()] = value.strip()

        return result