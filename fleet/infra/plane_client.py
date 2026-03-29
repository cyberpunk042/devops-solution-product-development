"""Fleet Plane API client.

Wraps the Plane REST API for issue tracking integration.
Mirrors the MCClient pattern: async httpx, clean typed methods,
credentials from environment (.env: PLANE_URL, PLANE_API_KEY).
"""

from __future__ import annotations

from typing import Any, Optional

import httpx


class PlaneProject:
    """Minimal model for a Plane project."""

    def __init__(self, data: dict) -> None:
        self.id: str = str(data.get("id", ""))
        self.name: str = data.get("name", "")
        self.identifier: str = data.get("identifier", "")
        self.description: str = data.get("description", "") or ""
        self.network: int = data.get("network", 0)
        self.is_member: bool = bool(data.get("is_member", False))

    def __repr__(self) -> str:  # pragma: no cover
        return f"PlaneProject(id={self.id!r}, name={self.name!r})"


class PlaneState:
    """Minimal model for a Plane workflow state."""

    def __init__(self, data: dict) -> None:
        self.id: str = str(data.get("id", ""))
        self.name: str = data.get("name", "")
        self.color: str = data.get("color", "")
        self.group: str = data.get("group", "")  # backlog|unstarted|started|completed|cancelled
        self.project_id: str = str(data.get("project", ""))
        self.is_default: bool = bool(data.get("default", False))

    def __repr__(self) -> str:  # pragma: no cover
        return f"PlaneState(id={self.id!r}, name={self.name!r}, group={self.group!r})"


class PlaneCycle:
    """Minimal model for a Plane cycle (sprint)."""

    def __init__(self, data: dict) -> None:
        self.id: str = str(data.get("id", ""))
        self.name: str = data.get("name", "")
        self.description: str = data.get("description", "") or ""
        self.project_id: str = str(data.get("project", ""))
        self.start_date: Optional[str] = data.get("start_date")
        self.end_date: Optional[str] = data.get("end_date")
        self.status: str = data.get("status", "")  # current|upcoming|completed

    def __repr__(self) -> str:  # pragma: no cover
        return f"PlaneCycle(id={self.id!r}, name={self.name!r}, status={self.status!r})"


class PlaneIssue:
    """Minimal model for a Plane issue."""

    def __init__(self, data: dict) -> None:
        self.id: str = str(data.get("id", ""))
        self.sequence_id: int = int(data.get("sequence_id", 0))
        self.title: str = data.get("name", "")
        self.description_html: str = data.get("description_html", "") or ""
        self.state_id: str = str(data.get("state", ""))
        self.project_id: str = str(data.get("project", ""))
        self.priority: str = data.get("priority", "none")  # urgent|high|medium|low|none
        self.assignees: list[str] = [str(a) for a in (data.get("assignees") or [])]
        self.labels: list[str] = [str(lbl) for lbl in (data.get("label_ids") or [])]
        self.estimate_point: Optional[int] = data.get("estimate_point")
        self.cycle_id: Optional[str] = str(data["cycle"]) if data.get("cycle") else None
        self.created_at: Optional[str] = data.get("created_at")
        self.updated_at: Optional[str] = data.get("updated_at")

    def __repr__(self) -> str:  # pragma: no cover
        return f"PlaneIssue(id={self.id!r}, title={self.title!r}, priority={self.priority!r})"


class PlaneClient:
    """Plane REST API async client.

    Mirrors MCClient's structure: httpx AsyncClient, typed return models,
    credentials via constructor or environment.

    Environment variables (read from .env or os.environ):
        PLANE_URL     — Base URL of the Plane instance (e.g. http://localhost:8080)
        PLANE_API_KEY — Personal API token from Plane Settings → API Tokens

    Usage::

        client = PlaneClient(base_url="http://localhost:8080", api_key="...")
        async with client:
            projects = await client.list_projects("my-workspace")
    """

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
    ) -> None:
        import os

        self._base_url = (base_url or os.environ.get("PLANE_URL", "")).rstrip("/")
        self._api_key = api_key or os.environ.get("PLANE_API_KEY", "")

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._build_headers(),
            timeout=15.0,
        )

    def _build_headers(self) -> dict[str, str]:
        """Build Plane API auth headers.

        Plane uses 'X-API-Key' for personal API tokens.
        """
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        return headers

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "PlaneClient":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # ─── Projects ───────────────────────────────────────────────────────

    async def list_projects(self, workspace_slug: str) -> list[PlaneProject]:
        """List all projects the API token can access in a workspace.

        Args:
            workspace_slug: The Plane workspace slug (e.g. ``"my-org"``).

        Returns:
            List of :class:`PlaneProject` objects.

        Raises:
            httpx.HTTPStatusError: on non-2xx response.
        """
        resp = await self._client.get(
            f"/api/v1/workspaces/{workspace_slug}/projects/"
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("results", data) if isinstance(data, dict) else data
        return [PlaneProject(item) for item in items]

    # ─── States ─────────────────────────────────────────────────────────

    async def list_states(
        self, workspace_slug: str, project_id: str
    ) -> list[PlaneState]:
        """List workflow states for a project.

        Args:
            workspace_slug: The Plane workspace slug.
            project_id: The Plane project UUID.

        Returns:
            List of :class:`PlaneState` objects.
        """
        resp = await self._client.get(
            f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/states/"
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("results", data) if isinstance(data, dict) else data
        return [PlaneState(item) for item in items]

    # ─── Cycles ─────────────────────────────────────────────────────────

    async def list_cycles(
        self, workspace_slug: str, project_id: str
    ) -> list[PlaneCycle]:
        """List cycles (sprints) for a project.

        Args:
            workspace_slug: The Plane workspace slug.
            project_id: The Plane project UUID.

        Returns:
            List of :class:`PlaneCycle` objects.
        """
        resp = await self._client.get(
            f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/cycles/"
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("results", data) if isinstance(data, dict) else data
        return [PlaneCycle(item) for item in items]

    # ─── Issues ─────────────────────────────────────────────────────────

    async def list_issues(
        self,
        workspace_slug: str,
        project_id: str,
        *,
        state_id: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 100,
    ) -> list[PlaneIssue]:
        """List issues in a project with optional filters.

        Args:
            workspace_slug: The Plane workspace slug.
            project_id: The Plane project UUID.
            state_id: Filter by state UUID (optional).
            priority: Filter by priority ``urgent|high|medium|low|none`` (optional).
            limit: Maximum number of issues to return (default 100).

        Returns:
            List of :class:`PlaneIssue` objects.
        """
        params: dict[str, Any] = {"per_page": limit}
        if state_id:
            params["state"] = state_id
        if priority:
            params["priority"] = priority

        resp = await self._client.get(
            f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/",
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("results", data) if isinstance(data, dict) else data
        return [PlaneIssue(item) for item in items]

    async def create_issue(
        self,
        workspace_slug: str,
        project_id: str,
        *,
        title: str,
        description_html: str = "",
        state_id: Optional[str] = None,
        priority: str = "none",
        assignees: Optional[list[str]] = None,
        label_ids: Optional[list[str]] = None,
        estimate_point: Optional[int] = None,
        cycle_id: Optional[str] = None,
    ) -> PlaneIssue:
        """Create a new issue in a project.

        Args:
            workspace_slug: The Plane workspace slug.
            project_id: The Plane project UUID.
            title: Issue title (required).
            description_html: HTML description (optional).
            state_id: UUID of the target workflow state (optional).
            priority: ``urgent|high|medium|low|none`` (default ``"none"``).
            assignees: List of member UUIDs to assign (optional).
            label_ids: List of label UUIDs (optional).
            estimate_point: Story point estimate (optional).
            cycle_id: UUID of the cycle to add the issue to (optional).

        Returns:
            Created :class:`PlaneIssue`.

        Raises:
            httpx.HTTPStatusError: on non-2xx response.
        """
        payload: dict[str, Any] = {
            "name": title,
            "priority": priority,
        }
        if description_html:
            payload["description_html"] = description_html
        if state_id:
            payload["state"] = state_id
        if assignees:
            payload["assignees"] = assignees
        if label_ids:
            payload["label_ids"] = label_ids
        if estimate_point is not None:
            payload["estimate_point"] = estimate_point

        resp = await self._client.post(
            f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/",
            json=payload,
        )
        resp.raise_for_status()
        issue = PlaneIssue(resp.json())

        # Optionally add to a cycle immediately
        if cycle_id and issue.id:
            await self._add_issue_to_cycle(
                workspace_slug, project_id, cycle_id, issue.id
            )
            issue.cycle_id = cycle_id

        return issue

    async def update_issue(
        self,
        workspace_slug: str,
        project_id: str,
        issue_id: str,
        *,
        title: Optional[str] = None,
        description_html: Optional[str] = None,
        state_id: Optional[str] = None,
        priority: Optional[str] = None,
        assignees: Optional[list[str]] = None,
        label_ids: Optional[list[str]] = None,
        estimate_point: Optional[int] = None,
    ) -> PlaneIssue:
        """Partially update an existing issue.

        Only fields explicitly passed are included in the PATCH body.
        Use ``None`` to leave a field unchanged.

        Args:
            workspace_slug: The Plane workspace slug.
            project_id: The Plane project UUID.
            issue_id: The issue UUID to update.
            title: New title (optional).
            description_html: New HTML description (optional).
            state_id: New state UUID (optional).
            priority: New priority (optional).
            assignees: Replacement list of member UUIDs (optional).
            label_ids: Replacement list of label UUIDs (optional).
            estimate_point: New story point estimate (optional).

        Returns:
            Updated :class:`PlaneIssue`.

        Raises:
            httpx.HTTPStatusError: on non-2xx response.
        """
        payload: dict[str, Any] = {}
        if title is not None:
            payload["name"] = title
        if description_html is not None:
            payload["description_html"] = description_html
        if state_id is not None:
            payload["state"] = state_id
        if priority is not None:
            payload["priority"] = priority
        if assignees is not None:
            payload["assignees"] = assignees
        if label_ids is not None:
            payload["label_ids"] = label_ids
        if estimate_point is not None:
            payload["estimate_point"] = estimate_point

        resp = await self._client.patch(
            f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/{issue_id}/",
            json=payload,
        )
        resp.raise_for_status()
        return PlaneIssue(resp.json())

    # ─── Cycle membership ───────────────────────────────────────────────

    async def _add_issue_to_cycle(
        self,
        workspace_slug: str,
        project_id: str,
        cycle_id: str,
        issue_id: str,
    ) -> None:
        """Add an issue to a cycle (internal helper).

        Args:
            workspace_slug: The Plane workspace slug.
            project_id: The Plane project UUID.
            cycle_id: The cycle UUID.
            issue_id: The issue UUID to add.
        """
        resp = await self._client.post(
            f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}"
            f"/cycles/{cycle_id}/cycle-issues/",
            json={"issues": [issue_id]},
        )
        resp.raise_for_status()
