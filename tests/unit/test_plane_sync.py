"""Tests for PlaneSyncer — bidirectional Plane ↔ OCMC sync logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from fleet.core.models import Task, TaskCustomFields, TaskStatus
from fleet.core.plane_sync import (
    CF_PLANE_ISSUE_ID,
    CF_PLANE_PROJECT_ID,
    CF_PLANE_WORKSPACE,
    IngestResult,
    PlaneSyncer,
    PushResult,
    _html_to_plain,
    _map_priority,
)
from fleet.infra.plane_client import PlaneIssue, PlaneProject


# ─── Fixtures / helpers ──────────────────────────────────────────────────────


def _make_task(
    task_id: str = "task-1",
    status: str = "inbox",
    plane_issue_id: Optional[str] = None,
    plane_project_id: Optional[str] = None,
    plane_workspace: Optional[str] = None,
    title: str = "A task",
) -> Task:
    return Task(
        id=task_id,
        board_id="board-1",
        title=title,
        status=TaskStatus(status),
        custom_fields=TaskCustomFields(
            plane_issue_id=plane_issue_id,
            plane_project_id=plane_project_id,
            plane_workspace=plane_workspace,
        ),
    )


def _make_plane_issue(
    issue_id: str = "issue-1",
    title: str = "Plane issue",
    priority: str = "medium",
    description_html: str = "",
    sequence_id: int = 1,
) -> PlaneIssue:
    return PlaneIssue(
        {
            "id": issue_id,
            "name": title,
            "priority": priority,
            "description_html": description_html,
            "sequence_id": sequence_id,
            "state": "state-1",
            "project": "proj-1",
            "assignees": [],
            "label_ids": [],
            "cycle": None,
        }
    )


def _make_syncer(
    project_ids: Optional[list[str]] = None,
    done_state_id: Optional[str] = None,
    assigned_agent_id: Optional[str] = None,
) -> tuple[PlaneSyncer, MagicMock, MagicMock]:
    mc = MagicMock()
    plane = MagicMock()
    # Use ["proj-1"] as default only when project_ids is not supplied at all (None)
    resolved = ["proj-1"] if project_ids is None else project_ids
    syncer = PlaneSyncer(
        mc=mc,
        plane=plane,
        board_id="board-1",
        workspace_slug="my-ws",
        project_ids=resolved,
        done_state_id=done_state_id,
        assigned_agent_id=assigned_agent_id,
    )
    return syncer, mc, plane


# ─── _html_to_plain ──────────────────────────────────────────────────────────


def test_html_to_plain_empty():
    assert _html_to_plain("") == ""


def test_html_to_plain_none_like():
    assert _html_to_plain(None) == ""  # type: ignore[arg-type]


def test_html_to_plain_simple_paragraph():
    assert _html_to_plain("<p>Hello world</p>") == "Hello world"


def test_html_to_plain_br_becomes_newline():
    result = _html_to_plain("Line one<br/>Line two")
    assert "Line one" in result
    assert "Line two" in result
    assert "\n" in result


def test_html_to_plain_list_items():
    html = "<ul><li>Alpha</li><li>Beta</li></ul>"
    result = _html_to_plain(html)
    assert "Alpha" in result
    assert "Beta" in result
    assert "•" in result


def test_html_to_plain_strips_tags():
    result = _html_to_plain("<strong>Bold</strong> and <em>italic</em>")
    assert "<" not in result
    assert "Bold" in result
    assert "italic" in result


def test_html_to_plain_no_triple_newlines():
    html = "<p>A</p><p></p><p></p><p>B</p>"
    result = _html_to_plain(html)
    assert "\n\n\n" not in result


# ─── _map_priority ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("plane,ocmc", [
    ("urgent", "urgent"),
    ("high", "high"),
    ("medium", "medium"),
    ("low", "low"),
    ("none", "medium"),
    ("unknown_value", "medium"),
])
def test_map_priority(plane, ocmc):
    assert _map_priority(plane) == ocmc


# ─── IngestResult / PushResult ───────────────────────────────────────────────


def test_ingest_result_counts():
    r = IngestResult(created=[_make_task()], skipped=["x", "y"])
    assert r.created_count == 1
    assert r.skipped_count == 2


def test_push_result_counts():
    r = PushResult(updated=["i1", "i2"])
    assert r.updated_count == 2


# ─── PlaneSyncer._get_cf ─────────────────────────────────────────────────────


def test_get_cf_returns_plane_issue_id():
    task = _make_task(plane_issue_id="issue-42")
    assert PlaneSyncer._get_cf(task, CF_PLANE_ISSUE_ID) == "issue-42"


def test_get_cf_returns_none_when_missing():
    task = _make_task()
    assert PlaneSyncer._get_cf(task, CF_PLANE_ISSUE_ID) is None


def test_get_cf_plane_project_id():
    task = _make_task(plane_project_id="proj-99")
    assert PlaneSyncer._get_cf(task, CF_PLANE_PROJECT_ID) == "proj-99"


def test_get_cf_plane_workspace():
    task = _make_task(plane_workspace="acme")
    assert PlaneSyncer._get_cf(task, CF_PLANE_WORKSPACE) == "acme"


# ─── ingest_from_plane ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ingest_creates_task_for_new_issue():
    syncer, mc, plane = _make_syncer(project_ids=["proj-1"])

    plane.list_issues = AsyncMock(return_value=[_make_plane_issue("issue-1")])
    mc.list_tasks = AsyncMock(return_value=[])  # no existing tasks
    created_task = _make_task("ocmc-new", plane_issue_id="issue-1")
    mc.create_task = AsyncMock(return_value=created_task)

    result = await syncer.ingest_from_plane()

    assert result.created_count == 1
    assert result.skipped_count == 0
    assert result.errors == []
    mc.create_task.assert_called_once()
    call_kwargs = mc.create_task.call_args[1]
    assert call_kwargs["custom_fields"][CF_PLANE_ISSUE_ID] == "issue-1"
    assert call_kwargs["custom_fields"][CF_PLANE_PROJECT_ID] == "proj-1"
    assert call_kwargs["custom_fields"][CF_PLANE_WORKSPACE] == "my-ws"
    assert call_kwargs["auto_created"] is True


@pytest.mark.asyncio
async def test_ingest_skips_already_mapped_issue():
    syncer, mc, plane = _make_syncer(project_ids=["proj-1"])

    existing_task = _make_task("existing", plane_issue_id="issue-1")
    mc.list_tasks = AsyncMock(return_value=[existing_task])
    plane.list_issues = AsyncMock(return_value=[_make_plane_issue("issue-1")])
    mc.create_task = AsyncMock()

    result = await syncer.ingest_from_plane()

    assert result.created_count == 0
    assert result.skipped_count == 1
    assert "issue-1" in result.skipped
    mc.create_task.assert_not_called()


@pytest.mark.asyncio
async def test_ingest_creates_new_and_skips_existing():
    syncer, mc, plane = _make_syncer(project_ids=["proj-1"])

    existing = _make_task("existing", plane_issue_id="issue-1")
    mc.list_tasks = AsyncMock(return_value=[existing])
    plane.list_issues = AsyncMock(
        return_value=[
            _make_plane_issue("issue-1"),  # already mapped
            _make_plane_issue("issue-2"),  # new
        ]
    )
    new_task = _make_task("new-ocmc", plane_issue_id="issue-2")
    mc.create_task = AsyncMock(return_value=new_task)

    result = await syncer.ingest_from_plane()

    assert result.created_count == 1
    assert result.skipped_count == 1
    mc.create_task.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_maps_priority():
    syncer, mc, plane = _make_syncer(project_ids=["proj-1"])

    mc.list_tasks = AsyncMock(return_value=[])
    plane.list_issues = AsyncMock(
        return_value=[_make_plane_issue("issue-1", priority="urgent")]
    )
    mc.create_task = AsyncMock(return_value=_make_task())

    await syncer.ingest_from_plane()

    call_kwargs = mc.create_task.call_args[1]
    assert call_kwargs["priority"] == "urgent"


@pytest.mark.asyncio
async def test_ingest_maps_none_priority_to_medium():
    syncer, mc, plane = _make_syncer(project_ids=["proj-1"])

    mc.list_tasks = AsyncMock(return_value=[])
    plane.list_issues = AsyncMock(
        return_value=[_make_plane_issue("issue-1", priority="none")]
    )
    mc.create_task = AsyncMock(return_value=_make_task())

    await syncer.ingest_from_plane()

    call_kwargs = mc.create_task.call_args[1]
    assert call_kwargs["priority"] == "medium"


@pytest.mark.asyncio
async def test_ingest_includes_description_with_sequence_id():
    syncer, mc, plane = _make_syncer(project_ids=["proj-1"])

    mc.list_tasks = AsyncMock(return_value=[])
    plane.list_issues = AsyncMock(
        return_value=[_make_plane_issue("issue-1", description_html="<p>Details</p>", sequence_id=42)]
    )
    mc.create_task = AsyncMock(return_value=_make_task())

    await syncer.ingest_from_plane()

    call_kwargs = mc.create_task.call_args[1]
    assert "Details" in call_kwargs["description"]
    assert "42" in call_kwargs["description"]


@pytest.mark.asyncio
async def test_ingest_assigns_agent_when_configured():
    syncer, mc, plane = _make_syncer(
        project_ids=["proj-1"], assigned_agent_id="agent-uuid"
    )

    mc.list_tasks = AsyncMock(return_value=[])
    plane.list_issues = AsyncMock(return_value=[_make_plane_issue("issue-1")])
    mc.create_task = AsyncMock(return_value=_make_task())

    await syncer.ingest_from_plane()

    call_kwargs = mc.create_task.call_args[1]
    assert call_kwargs["assigned_agent_id"] == "agent-uuid"


@pytest.mark.asyncio
async def test_ingest_resolves_projects_dynamically_when_none_given():
    syncer, mc, plane = _make_syncer(project_ids=[])  # empty → auto-discover

    proj = PlaneProject({"id": "proj-auto", "name": "Auto"})
    plane.list_projects = AsyncMock(return_value=[proj])
    plane.list_issues = AsyncMock(return_value=[])
    mc.list_tasks = AsyncMock(return_value=[])

    result = await syncer.ingest_from_plane()

    plane.list_projects.assert_called_once_with("my-ws")
    plane.list_issues.assert_called_once_with("my-ws", "proj-auto")
    assert result.created_count == 0


@pytest.mark.asyncio
async def test_ingest_records_error_when_list_issues_fails():
    syncer, mc, plane = _make_syncer(project_ids=["proj-1"])

    mc.list_tasks = AsyncMock(return_value=[])
    plane.list_issues = AsyncMock(side_effect=Exception("Plane API down"))

    result = await syncer.ingest_from_plane()

    assert result.created_count == 0
    assert len(result.errors) == 1
    assert "Plane API down" in result.errors[0]


@pytest.mark.asyncio
async def test_ingest_records_error_when_create_task_fails():
    syncer, mc, plane = _make_syncer(project_ids=["proj-1"])

    mc.list_tasks = AsyncMock(return_value=[])
    plane.list_issues = AsyncMock(return_value=[_make_plane_issue("issue-1")])
    mc.create_task = AsyncMock(side_effect=Exception("OCMC 500"))

    result = await syncer.ingest_from_plane()

    assert result.created_count == 0
    assert len(result.errors) == 1
    assert "OCMC 500" in result.errors[0]


@pytest.mark.asyncio
async def test_ingest_no_projects_returns_empty():
    syncer, mc, plane = _make_syncer(project_ids=[])

    plane.list_projects = AsyncMock(return_value=[])
    mc.list_tasks = AsyncMock(return_value=[])

    result = await syncer.ingest_from_plane()

    assert result.created_count == 0
    assert result.errors == []


# ─── push_completions_to_plane ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_push_updates_plane_issue_for_done_task():
    syncer, mc, plane = _make_syncer(done_state_id="state-done")

    done_task = _make_task(
        "task-1", status="done",
        plane_issue_id="issue-1",
        plane_project_id="proj-1",
        plane_workspace="my-ws",
    )
    mc.list_tasks = AsyncMock(return_value=[done_task])
    plane.update_issue = AsyncMock(return_value=MagicMock())

    result = await syncer.push_completions_to_plane()

    assert result.updated_count == 1
    assert "issue-1" in result.updated
    plane.update_issue.assert_called_once_with(
        "my-ws", "proj-1", "issue-1", state_id="state-done"
    )


@pytest.mark.asyncio
async def test_push_skips_task_without_plane_mapping():
    syncer, mc, plane = _make_syncer(done_state_id="state-done")

    done_task = _make_task("task-1", status="done")  # no plane fields
    mc.list_tasks = AsyncMock(return_value=[done_task])
    plane.update_issue = AsyncMock()

    result = await syncer.push_completions_to_plane()

    assert result.updated_count == 0
    assert "task-1" in result.skipped
    plane.update_issue.assert_not_called()


@pytest.mark.asyncio
async def test_push_no_op_when_done_state_not_configured():
    syncer, mc, plane = _make_syncer(done_state_id=None)

    mc.list_tasks = AsyncMock()
    plane.update_issue = AsyncMock()

    result = await syncer.push_completions_to_plane()

    assert result.updated_count == 0
    mc.list_tasks.assert_not_called()
    plane.update_issue.assert_not_called()


@pytest.mark.asyncio
async def test_push_records_error_when_update_fails():
    syncer, mc, plane = _make_syncer(done_state_id="state-done")

    done_task = _make_task(
        "task-1", status="done",
        plane_issue_id="issue-1",
        plane_project_id="proj-1",
    )
    mc.list_tasks = AsyncMock(return_value=[done_task])
    plane.update_issue = AsyncMock(side_effect=Exception("Plane 503"))

    result = await syncer.push_completions_to_plane()

    assert result.updated_count == 0
    assert len(result.errors) == 1
    assert "Plane 503" in result.errors[0]


@pytest.mark.asyncio
async def test_push_handles_multiple_done_tasks():
    syncer, mc, plane = _make_syncer(done_state_id="state-done")

    task_a = _make_task("t-a", status="done", plane_issue_id="i-a", plane_project_id="proj-1")
    task_b = _make_task("t-b", status="done", plane_issue_id="i-b", plane_project_id="proj-1")
    task_c = _make_task("t-c", status="done")  # no mapping → skip
    mc.list_tasks = AsyncMock(return_value=[task_a, task_b, task_c])
    plane.update_issue = AsyncMock(return_value=MagicMock())

    result = await syncer.push_completions_to_plane()

    assert result.updated_count == 2
    assert result.skipped == ["t-c"]
    assert plane.update_issue.call_count == 2


# ─── TaskCustomFields plane fields ───────────────────────────────────────────


def test_task_custom_fields_plane_defaults():
    cf = TaskCustomFields()
    assert cf.plane_issue_id is None
    assert cf.plane_project_id is None
    assert cf.plane_workspace is None


def test_task_custom_fields_plane_values():
    cf = TaskCustomFields(
        plane_issue_id="i-1",
        plane_project_id="p-1",
        plane_workspace="acme",
    )
    assert cf.plane_issue_id == "i-1"
    assert cf.plane_project_id == "p-1"
    assert cf.plane_workspace == "acme"
