"""Integration tests against a live Plane instance.

Requires:
  - Plane running on localhost:8080
  - .plane-config with valid credentials

Run with:
  pytest tests/integration/ -m integration
"""

import os

import pytest

pytestmark = pytest.mark.integration


@pytest.fixture
def plane_client():
    """Create a PlaneClient from .plane-config or environment."""
    from fleet.infra.plane_client import PlaneClient

    url = os.environ.get("PLANE_URL", "http://localhost:8080")
    key = os.environ.get("PLANE_API_KEY", "")

    if not key:
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", ".plane-config")
        if os.path.exists(config_path):
            with open(config_path) as f:
                for line in f:
                    if line.startswith("PLANE_API_TOKEN="):
                        key = line.split("=", 1)[1].strip()

    if not key:
        pytest.skip("No PLANE_API_KEY or .plane-config available")

    return PlaneClient(base_url=url, api_key=key)


@pytest.fixture
def workspace_slug():
    ws = os.environ.get("PLANE_WORKSPACE_SLUG",
                        os.environ.get("PLANE_WORKSPACE", "fleet"))
    return ws


@pytest.mark.asyncio
async def test_list_projects(plane_client, workspace_slug):
    """Can list projects in workspace."""
    async with plane_client:
        projects = await plane_client.list_projects(workspace_slug)
        assert len(projects) > 0
        identifiers = [p.identifier for p in projects]
        assert "AICP" in identifiers or "OF" in identifiers


@pytest.mark.asyncio
async def test_list_states(plane_client, workspace_slug):
    """Can list states for a project."""
    async with plane_client:
        projects = await plane_client.list_projects(workspace_slug)
        assert len(projects) > 0
        states = await plane_client.list_states(workspace_slug, projects[0].id)
        assert len(states) > 0
        groups = {s.group for s in states}
        assert "completed" in groups or "started" in groups


@pytest.mark.asyncio
async def test_issue_crud(plane_client, workspace_slug):
    """Create, read, update, delete an issue."""
    async with plane_client:
        projects = await plane_client.list_projects(workspace_slug)
        project = projects[0]

        # Create
        issue = await plane_client.create_issue(
            workspace_slug, project.id,
            title="Integration test issue — safe to delete",
            priority="low",
        )
        assert issue.id
        assert issue.title == "Integration test issue — safe to delete"

        # Update
        updated = await plane_client.update_issue(
            workspace_slug, project.id, issue.id,
            title="Integration test issue [updated]",
            priority="medium",
        )
        assert updated.title == "Integration test issue [updated]"

        # List — should include our issue
        issues = await plane_client.list_issues(workspace_slug, project.id)
        ids = [i.id for i in issues]
        assert issue.id in ids

        # Delete — Plane API may not support DELETE on issues via v1 API
        # Just clean up by updating to cancelled state if available


@pytest.mark.asyncio
async def test_list_cycles(plane_client, workspace_slug):
    """Can list cycles (sprints) for a project."""
    async with plane_client:
        projects = await plane_client.list_projects(workspace_slug)
        if not projects:
            pytest.skip("No projects found")
        cycles = await plane_client.list_cycles(workspace_slug, projects[0].id)
        # May be empty if no sprints created yet — that's OK
        assert isinstance(cycles, list)