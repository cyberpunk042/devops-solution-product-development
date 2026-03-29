"""Tests for PlaneClient — model parsing and request construction."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from fleet.infra.plane_client import (
    PlaneCycle,
    PlaneIssue,
    PlaneProject,
    PlaneState,
    PlaneClient,
)


# ─── Model parsing ──────────────────────────────────────────────────────────


def test_plane_project_parse():
    data = {
        "id": "proj-1",
        "name": "NNRT",
        "identifier": "NNRT",
        "description": "Narrative transformer",
        "network": 2,
        "is_member": True,
    }
    project = PlaneProject(data)
    assert project.id == "proj-1"
    assert project.name == "NNRT"
    assert project.identifier == "NNRT"
    assert project.description == "Narrative transformer"
    assert project.network == 2
    assert project.is_member is True


def test_plane_project_parse_minimal():
    project = PlaneProject({})
    assert project.id == ""
    assert project.name == ""
    assert project.description == ""
    assert project.is_member is False


def test_plane_state_parse():
    data = {
        "id": "state-1",
        "name": "In Progress",
        "color": "#f97316",
        "group": "started",
        "project": "proj-1",
        "default": False,
    }
    state = PlaneState(data)
    assert state.id == "state-1"
    assert state.name == "In Progress"
    assert state.color == "#f97316"
    assert state.group == "started"
    assert state.project_id == "proj-1"
    assert state.is_default is False


def test_plane_state_parse_minimal():
    state = PlaneState({})
    assert state.id == ""
    assert state.group == ""
    assert state.is_default is False


def test_plane_cycle_parse():
    data = {
        "id": "cycle-1",
        "name": "Sprint 1",
        "description": "First sprint",
        "project": "proj-1",
        "start_date": "2026-03-01",
        "end_date": "2026-03-14",
        "status": "current",
    }
    cycle = PlaneCycle(data)
    assert cycle.id == "cycle-1"
    assert cycle.name == "Sprint 1"
    assert cycle.description == "First sprint"
    assert cycle.project_id == "proj-1"
    assert cycle.start_date == "2026-03-01"
    assert cycle.end_date == "2026-03-14"
    assert cycle.status == "current"


def test_plane_cycle_parse_minimal():
    cycle = PlaneCycle({})
    assert cycle.id == ""
    assert cycle.start_date is None
    assert cycle.end_date is None
    assert cycle.status == ""


def test_plane_issue_parse():
    data = {
        "id": "issue-1",
        "sequence_id": 42,
        "name": "Fix the bug",
        "description_html": "<p>Details</p>",
        "state": "state-1",
        "project": "proj-1",
        "priority": "high",
        "assignees": ["user-a", "user-b"],
        "label_ids": ["lbl-1"],
        "estimate_point": 3,
        "cycle": "cycle-1",
        "created_at": "2026-03-20T10:00:00Z",
        "updated_at": "2026-03-21T08:00:00Z",
    }
    issue = PlaneIssue(data)
    assert issue.id == "issue-1"
    assert issue.sequence_id == 42
    assert issue.title == "Fix the bug"
    assert issue.description_html == "<p>Details</p>"
    assert issue.state_id == "state-1"
    assert issue.project_id == "proj-1"
    assert issue.priority == "high"
    assert issue.assignees == ["user-a", "user-b"]
    assert issue.labels == ["lbl-1"]
    assert issue.estimate_point == 3
    assert issue.cycle_id == "cycle-1"


def test_plane_issue_parse_no_cycle():
    data = {
        "id": "issue-2",
        "name": "Another issue",
        "state": "state-1",
        "project": "proj-1",
        "priority": "none",
        "cycle": None,
    }
    issue = PlaneIssue(data)
    assert issue.cycle_id is None
    assert issue.assignees == []
    assert issue.labels == []


def test_plane_issue_parse_minimal():
    issue = PlaneIssue({})
    assert issue.id == ""
    assert issue.sequence_id == 0
    assert issue.title == ""
    assert issue.priority == "none"
    assert issue.cycle_id is None


# ─── Client construction ────────────────────────────────────────────────────


def test_plane_client_headers_with_key():
    client = PlaneClient(base_url="http://localhost:8080", api_key="test-key")
    headers = client._build_headers()
    assert headers["X-API-Key"] == "test-key"
    assert headers["Content-Type"] == "application/json"


def test_plane_client_headers_no_key():
    client = PlaneClient(base_url="http://localhost:8080", api_key="")
    headers = client._build_headers()
    assert "X-API-Key" not in headers


def test_plane_client_env_fallback(monkeypatch):
    monkeypatch.setenv("PLANE_URL", "http://plane.example.com")
    monkeypatch.setenv("PLANE_API_KEY", "env-key")
    client = PlaneClient()
    assert client._base_url == "http://plane.example.com"
    assert client._api_key == "env-key"


def test_plane_client_strips_trailing_slash():
    client = PlaneClient(base_url="http://localhost:8080/", api_key="k")
    assert client._base_url == "http://localhost:8080"


# ─── Async method tests (mocked httpx) ──────────────────────────────────────


def _make_response(data: dict | list, status_code: int = 200) -> MagicMock:
    """Build a mock httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = data
    resp.raise_for_status = MagicMock()
    return resp


@pytest.mark.asyncio
async def test_list_projects():
    client = PlaneClient(base_url="http://localhost:8080", api_key="k")
    mock_resp = _make_response(
        {"results": [{"id": "p1", "name": "Alpha", "identifier": "ALP"}]}
    )
    client._client.get = AsyncMock(return_value=mock_resp)

    projects = await client.list_projects("my-ws")

    client._client.get.assert_called_once_with(
        "/api/v1/workspaces/my-ws/projects/"
    )
    assert len(projects) == 1
    assert projects[0].id == "p1"
    assert projects[0].name == "Alpha"


@pytest.mark.asyncio
async def test_list_states():
    client = PlaneClient(base_url="http://localhost:8080", api_key="k")
    mock_resp = _make_response(
        {"results": [{"id": "s1", "name": "Todo", "group": "unstarted"}]}
    )
    client._client.get = AsyncMock(return_value=mock_resp)

    states = await client.list_states("my-ws", "proj-1")

    client._client.get.assert_called_once_with(
        "/api/v1/workspaces/my-ws/projects/proj-1/states/"
    )
    assert len(states) == 1
    assert states[0].group == "unstarted"


@pytest.mark.asyncio
async def test_list_cycles():
    client = PlaneClient(base_url="http://localhost:8080", api_key="k")
    mock_resp = _make_response(
        {"results": [{"id": "c1", "name": "Sprint 1", "status": "current"}]}
    )
    client._client.get = AsyncMock(return_value=mock_resp)

    cycles = await client.list_cycles("my-ws", "proj-1")

    client._client.get.assert_called_once_with(
        "/api/v1/workspaces/my-ws/projects/proj-1/cycles/"
    )
    assert len(cycles) == 1
    assert cycles[0].status == "current"


@pytest.mark.asyncio
async def test_create_issue_minimal():
    client = PlaneClient(base_url="http://localhost:8080", api_key="k")
    mock_resp = _make_response(
        {"id": "i1", "name": "New issue", "state": "s1", "project": "p1", "priority": "none"}
    )
    client._client.post = AsyncMock(return_value=mock_resp)

    issue = await client.create_issue("my-ws", "proj-1", title="New issue")

    client._client.post.assert_called_once()
    call_kwargs = client._client.post.call_args
    assert call_kwargs[0][0] == "/api/v1/workspaces/my-ws/projects/proj-1/issues/"
    payload = call_kwargs[1]["json"]
    assert payload["name"] == "New issue"
    assert payload["priority"] == "none"
    assert "description_html" not in payload
    assert issue.id == "i1"
    assert issue.title == "New issue"


@pytest.mark.asyncio
async def test_create_issue_full():
    client = PlaneClient(base_url="http://localhost:8080", api_key="k")
    issue_data = {
        "id": "i2", "name": "Full issue", "state": "s1",
        "project": "p1", "priority": "high",
        "assignees": ["u1"], "label_ids": ["lbl1"], "estimate_point": 5,
        "cycle": None,
    }
    client._client.post = AsyncMock(return_value=_make_response(issue_data))

    issue = await client.create_issue(
        "my-ws",
        "proj-1",
        title="Full issue",
        description_html="<p>Details</p>",
        state_id="s1",
        priority="high",
        assignees=["u1"],
        label_ids=["lbl1"],
        estimate_point=5,
    )

    payload = client._client.post.call_args[1]["json"]
    assert payload["description_html"] == "<p>Details</p>"
    assert payload["state"] == "s1"
    assert payload["priority"] == "high"
    assert payload["assignees"] == ["u1"]
    assert payload["label_ids"] == ["lbl1"]
    assert payload["estimate_point"] == 5
    assert issue.estimate_point == 5


@pytest.mark.asyncio
async def test_create_issue_with_cycle_adds_to_cycle():
    """create_issue should POST to cycle-issues endpoint when cycle_id given."""
    client = PlaneClient(base_url="http://localhost:8080", api_key="k")
    issue_data = {"id": "i3", "name": "Sprint issue", "state": "s1", "project": "p1", "priority": "none", "cycle": None}
    post_resp = _make_response(issue_data)
    cycle_resp = _make_response({})
    client._client.post = AsyncMock(side_effect=[post_resp, cycle_resp])

    issue = await client.create_issue("ws", "proj-1", title="Sprint issue", cycle_id="c1")

    assert client._client.post.call_count == 2
    cycle_call = client._client.post.call_args_list[1]
    assert "cycle-issues" in cycle_call[0][0]
    assert issue.cycle_id == "c1"


@pytest.mark.asyncio
async def test_update_issue_partial():
    client = PlaneClient(base_url="http://localhost:8080", api_key="k")
    updated_data = {
        "id": "i1", "name": "Updated title", "state": "s2",
        "project": "p1", "priority": "medium", "cycle": None,
    }
    client._client.patch = AsyncMock(return_value=_make_response(updated_data))

    issue = await client.update_issue(
        "my-ws", "proj-1", "i1",
        title="Updated title",
        state_id="s2",
    )

    call_kwargs = client._client.patch.call_args
    assert "i1" in call_kwargs[0][0]
    payload = call_kwargs[1]["json"]
    assert payload["name"] == "Updated title"
    assert payload["state"] == "s2"
    assert "priority" not in payload   # not passed → not in patch body
    assert issue.title == "Updated title"


@pytest.mark.asyncio
async def test_update_issue_empty_patch():
    """Calling update_issue with no fields sends an empty patch."""
    client = PlaneClient(base_url="http://localhost:8080", api_key="k")
    client._client.patch = AsyncMock(
        return_value=_make_response({"id": "i1", "name": "Same", "state": "s1", "project": "p1", "priority": "none", "cycle": None})
    )

    await client.update_issue("ws", "proj-1", "i1")

    payload = client._client.patch.call_args[1]["json"]
    assert payload == {}


@pytest.mark.asyncio
async def test_list_issues_with_filters():
    client = PlaneClient(base_url="http://localhost:8080", api_key="k")
    mock_resp = _make_response({"results": []})
    client._client.get = AsyncMock(return_value=mock_resp)

    await client.list_issues("ws", "proj-1", state_id="s1", priority="high", limit=50)

    call_params = client._client.get.call_args[1]["params"]
    assert call_params["state"] == "s1"
    assert call_params["priority"] == "high"
    assert call_params["per_page"] == 50


@pytest.mark.asyncio
async def test_context_manager():
    """PlaneClient should work as an async context manager."""
    client = PlaneClient(base_url="http://localhost:8080", api_key="k")
    client._client.aclose = AsyncMock()

    async with client as c:
        assert c is client

    client._client.aclose.assert_called_once()
