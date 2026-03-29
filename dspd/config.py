"""DSPD configuration — all settings from environment, no hardcoded values.

Usage::

    from dspd.config import settings
    print(settings.PLANE_URL)
    print(settings.PLANE_API_KEY)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _project_root() -> Path:
    """Return the DSPD project root (parent of dspd/ package)."""
    return Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Load .env files if python-dotenv is available."""
    try:
        from dotenv import load_dotenv

        root = _project_root()
        # plane.env has Plane-specific config
        plane_env = root / "plane.env"
        if plane_env.exists():
            load_dotenv(plane_env)
        # .env has general config (OCMC tokens, etc.)
        dotenv = root / ".env"
        if dotenv.exists():
            load_dotenv(dotenv)
    except ImportError:
        pass


@dataclass(frozen=True)
class DspdSettings:
    """Immutable settings loaded from environment.

    All values come from env vars or plane.env / .env files.
    No hardcoded URLs, ports, or credentials.
    """

    # ── Plane ──────────────────────────────────────────────────────────
    PLANE_URL: str = ""
    PLANE_API_KEY: str = ""
    PLANE_WORKSPACE_SLUG: str = ""
    PLANE_PROJECT_ID: str = ""
    PLANE_WEBHOOK_SECRET: str = ""
    PLANE_ADMIN_EMAIL: str = ""

    # ── OCMC (Mission Control) ─────────────────────────────────────────
    OCMC_BASE_URL: str = ""
    OCMC_AUTH_TOKEN: str = ""

    # ── Fleet ──────────────────────────────────────────────────────────
    FLEET_DIR: str = ""

    # ── Docker ─────────────────────────────────────────────────────────
    COMPOSE_PROJECT: str = "dspd-plane"

    # ── Paths ──────────────────────────────────────────────────────────
    PROJECT_ROOT: str = ""
    MISSION_FILE: str = ""

    @classmethod
    def from_env(cls) -> DspdSettings:
        """Load settings from environment variables."""
        _load_dotenv()
        root = str(_project_root())
        return cls(
            PLANE_URL=os.environ.get("PLANE_URL", "http://localhost:8080"),
            PLANE_API_KEY=os.environ.get("PLANE_API_KEY", ""),
            PLANE_WORKSPACE_SLUG=os.environ.get("PLANE_WORKSPACE_SLUG",
                                                 os.environ.get("PLANE_WORKSPACE", "fleet")),
            PLANE_PROJECT_ID=os.environ.get("PLANE_PROJECT_ID", ""),
            PLANE_WEBHOOK_SECRET=os.environ.get("PLANE_WEBHOOK_SECRET", ""),
            PLANE_ADMIN_EMAIL=os.environ.get("PLANE_ADMIN_EMAIL", "admin@fleet.local"),
            OCMC_BASE_URL=os.environ.get("OCMC_BASE_URL",
                                         os.environ.get("BASE_URL", "http://localhost:8000")),
            OCMC_AUTH_TOKEN=os.environ.get("OCMC_AUTH_TOKEN",
                                           os.environ.get("LOCAL_AUTH_TOKEN", "")),
            FLEET_DIR=os.environ.get("FLEET_DIR", ""),
            COMPOSE_PROJECT=os.environ.get("COMPOSE_PROJECT", "dspd-plane"),
            PROJECT_ROOT=root,
            MISSION_FILE=os.environ.get("MISSION_FILE",
                                        os.path.join(root, "config", "mission.yaml")),
        )


# Module-level singleton — import and use directly
settings = DspdSettings.from_env()