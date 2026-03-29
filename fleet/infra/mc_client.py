"""Fleet Mission Control API client.

Implements core interfaces: TaskClient, MemoryClient, ApprovalClient, AgentClient.
Uses httpx for async HTTP. Supports caching via core.cache.Cache.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx

from fleet.core.cache import Cache
from fleet.core.interfaces import (
    AgentClient,
    ApprovalClient,
    MemoryClient,
    TaskClient,
)
from fleet.core.models import (
    Agent,
    AgentRole,
    Approval,
    BoardMemoryEntry,
    Task,
    TaskCustomFields,
    TaskStatus,
)


def _parse_datetime(value) -> Optional[datetime]:
    """Parse an ISO datetime string from MC API."""
    if not value:
        return None
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


class MCClient(TaskClient, MemoryClient, ApprovalClient, AgentClient):
    """Mission Control REST API client.

    Single client implements all MC-related interfaces.
    Credentials from TOOLS.md (agent token) or .env (admin token).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        token: str = "",
        cache: Optional[Cache] = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._cache = cache
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=self._build_headers(),
            timeout=15.0,
        )

    def _build_headers(self) -> dict:
        """Build auth headers. Supports both admin and agent tokens."""
        headers = {"Content-Type": "application/json"}
        if self._token:
            # Agent tokens use X-Agent-Token, admin tokens use Authorization
            if len(self._token) > 80:
                headers["Authorization"] = f"Bearer {self._token}"
            else:
                headers["X-Agent-Token"] = self._token
        return headers

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    # ─── TaskClient ─────────────────────────────────────────────────────

    async def get_task(self, board_id: str, task_id: str) -> Task:
        """Fetch a task by ID."""
        tasks = await self.list_tasks(board_id)
        for t in tasks:
            if t.id == task_id:
                return t
        raise ValueError(f"Task {task_id} not found")

    async def list_tasks(
        self, board_id: str, status: Optional[str] = None, limit: int = 100
    ) -> list[Task]:
        """List tasks on a board."""
        cache_key = f"tasks:{board_id}:{status}:{limit}"
        if self._cache:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return cached

        params: dict = {"limit": limit}
        if status:
            params["status"] = status

        resp = await self._client.get(
            f"/api/v1/boards/{board_id}/tasks", params=params
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", data) if isinstance(data, dict) else data

        tasks = [self._parse_task(item) for item in items]

        if self._cache:
            await self._cache.set(cache_key, tasks, ttl_seconds=30)

        return tasks

    async def update_task(
        self,
        board_id: str,
        task_id: str,
        *,
        status: Optional[str] = None,
        comment: Optional[str] = None,
        custom_fields: Optional[dict] = None,
        tag_ids: Optional[list[str]] = None,
        depends_on: Optional[list[str]] = None,
    ) -> Task:
        """Update a task."""
        payload: dict = {}
        if status:
            payload["status"] = status
        if comment:
            payload["comment"] = comment
        if custom_fields:
            payload["custom_field_values"] = custom_fields
        if tag_ids:
            payload["tag_ids"] = tag_ids
        if depends_on is not None:
            payload["depends_on_task_ids"] = depends_on

        resp = await self._client.patch(
            f"/api/v1/boards/{board_id}/tasks/{task_id}",
            json=payload,
        )
        resp.raise_for_status()

        # Invalidate cache
        if self._cache:
            await self._cache.clear(prefix=f"tasks:{board_id}")

        return self._parse_task(resp.json())

    async def create_task(
        self,
        board_id: str,
        *,
        title: str,
        description: str = "",
        priority: str = "medium",
        assigned_agent_id: Optional[str] = None,
        custom_fields: Optional[dict] = None,
        tag_ids: Optional[list[str]] = None,
        depends_on: Optional[list[str]] = None,
        auto_created: bool = False,
        auto_reason: str = "",
        due_at: Optional[str] = None,
    ) -> Task:
        """Create a new task."""
        payload: dict = {
            "title": title,
            "status": "inbox",
            "priority": priority,
        }
        if description:
            payload["description"] = description
        if assigned_agent_id:
            payload["assigned_agent_id"] = assigned_agent_id
        if custom_fields:
            payload["custom_field_values"] = custom_fields
        if tag_ids:
            payload["tag_ids"] = tag_ids
        if depends_on:
            payload["depends_on_task_ids"] = depends_on
        if auto_created:
            payload["auto_created"] = True
            if auto_reason:
                payload["auto_reason"] = auto_reason
        if due_at:
            payload["due_at"] = due_at

        resp = await self._client.post(
            f"/api/v1/boards/{board_id}/tasks", json=payload
        )
        resp.raise_for_status()

        if self._cache:
            await self._cache.clear(prefix=f"tasks:{board_id}")

        return self._parse_task(resp.json())

    async def post_comment(
        self, board_id: str, task_id: str, message: str
    ) -> dict:
        """Post a comment on a task."""
        resp = await self._client.post(
            f"/api/v1/boards/{board_id}/tasks/{task_id}/comments",
            json={"message": message},
        )
        resp.raise_for_status()
        return resp.json()

    # ─── MemoryClient ───────────────────────────────────────────────────

    async def post_memory(
        self,
        board_id: str,
        content: str,
        tags: list[str],
        source: str,
    ) -> BoardMemoryEntry:
        """Post to board memory."""
        resp = await self._client.post(
            f"/api/v1/boards/{board_id}/memory",
            json={"content": content, "tags": tags, "source": source},
        )
        resp.raise_for_status()
        data = resp.json()
        return BoardMemoryEntry(
            id=str(data.get("id", "")),
            board_id=board_id,
            content=content,
            tags=tags,
            source=source,
        )

    async def list_memory(
        self, board_id: str, limit: int = 20, tags: Optional[list[str]] = None
    ) -> list[BoardMemoryEntry]:
        """List board memory entries."""
        params: dict = {"limit": limit}
        resp = await self._client.get(
            f"/api/v1/boards/{board_id}/memory", params=params
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        return [
            BoardMemoryEntry(
                id=str(item.get("id", "")),
                board_id=board_id,
                content=item.get("content", ""),
                tags=item.get("tags") or [],
                source=item.get("source", ""),
            )
            for item in items
        ]

    # ─── ApprovalClient ─────────────────────────────────────────────────

    async def create_approval(
        self,
        board_id: str,
        *,
        task_ids: list[str],
        action_type: str,
        confidence: float,
        rubric_scores: dict[str, int],
        reason: str,
        agent_id: Optional[str] = None,
    ) -> Approval:
        """Create an approval request."""
        payload: dict = {
            "action_type": action_type,
            "task_ids": task_ids,
            "confidence": confidence,
            "rubric_scores": rubric_scores,
            "payload": {"reason": reason},
        }
        if agent_id:
            payload["agent_id"] = agent_id

        resp = await self._client.post(
            f"/api/v1/boards/{board_id}/approvals", json=payload
        )
        resp.raise_for_status()
        data = resp.json()
        return Approval(
            id=str(data.get("id", "")),
            board_id=board_id,
            task_id=task_ids[0] if task_ids else "",
            action_type=action_type,
            confidence=confidence,
            rubric_scores=rubric_scores,
            reason=reason,
            status=data.get("status", "pending"),
            agent_id=agent_id,
        )

    async def list_approvals(
        self, board_id: str, status: str = ""
    ) -> list[Approval]:
        """List approvals on a board, optionally filtered by status."""
        params: dict = {"limit": 50}
        if status:
            params["status"] = status
        resp = await self._client.get(
            f"/api/v1/boards/{board_id}/approvals", params=params
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", data) if isinstance(data, dict) else data
        return [
            Approval(
                id=str(item.get("id", "")),
                board_id=board_id,
                task_id=str(item.get("task_id", "") or ""),
                action_type=item.get("action_type", ""),
                confidence=item.get("confidence", 0),
                rubric_scores=item.get("rubric_scores") or {},
                reason=str((item.get("payload") or {}).get("reason", "")),
                status=item.get("status", "pending"),
            )
            for item in items
        ]

    async def approve_approval(
        self,
        board_id: str,
        approval_id: str,
        *,
        status: str = "approved",
        comment: str = "",
    ) -> Approval:
        """Approve or reject a pending approval."""
        payload: dict = {"status": status}
        if comment:
            payload["comment"] = comment

        resp = await self._client.patch(
            f"/api/v1/boards/{board_id}/approvals/{approval_id}",
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return Approval(
            id=str(data.get("id", "")),
            board_id=board_id,
            task_id=str(data.get("task_id", "") or ""),
            action_type=data.get("action_type", ""),
            confidence=data.get("confidence", 0),
            rubric_scores=data.get("rubric_scores") or {},
            reason=str((data.get("payload") or {}).get("reason", "")),
            status=data.get("status", ""),
        )

    async def task_has_approved_approval(
        self, board_id: str, task_id: str
    ) -> bool:
        """Check if a task has at least one approved approval."""
        approvals = await self.list_approvals(board_id, status="approved")
        for a in approvals:
            if a.task_id == task_id:
                return True
        return False

    # ─── AgentClient ────────────────────────────────────────────────────

    async def list_agents(self) -> list[Agent]:
        """List all fleet agents."""
        cache_key = "agents:list"
        if self._cache:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return cached

        resp = await self._client.get("/api/v1/agents")
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", data) if isinstance(data, dict) else data

        agents = [
            Agent(
                id=str(item.get("id", "")),
                name=item.get("name", ""),
                status=item.get("status", "offline"),
                board_id=str(item.get("board_id", "")) if item.get("board_id") else None,
                session_key=item.get("openclaw_session_id"),
            )
            for item in items
        ]

        if self._cache:
            await self._cache.set(cache_key, agents, ttl_seconds=60)

        return agents

    async def get_board_id(self) -> Optional[str]:
        """Get the fleet board ID from agent list."""
        agents = await self.list_agents()
        for a in agents:
            if a.board_id:
                return a.board_id
        return None

    # ─── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _parse_task(data: dict) -> Task:
        """Parse a task from MC API response."""
        custom = data.get("custom_field_values") or {}
        return Task(
            id=str(data.get("id", "")),
            board_id=str(data.get("board_id", "")),
            title=data.get("title", ""),
            status=TaskStatus(data.get("status", "inbox")),
            description=data.get("description", ""),
            priority=data.get("priority", "medium"),
            assigned_agent_id=str(data["assigned_agent_id"]) if data.get("assigned_agent_id") else None,
            custom_fields=TaskCustomFields(
                project=custom.get("project"),
                branch=custom.get("branch"),
                pr_url=custom.get("pr_url"),
                worktree=custom.get("worktree"),
                agent_name=custom.get("agent_name"),
                story_points=custom.get("story_points"),
                sprint=custom.get("sprint"),
                complexity=custom.get("complexity"),
                model=custom.get("model"),
                parent_task=custom.get("parent_task"),
                task_type=custom.get("task_type"),
                plan_id=custom.get("plan_id"),
                review_gates=custom.get("review_gates"),
                plane_issue_id=custom.get("plane_issue_id"),
                plane_project_id=custom.get("plane_project_id"),
                plane_workspace=custom.get("plane_workspace"),
            ),
            tags=[str(t.get("name", t)) if isinstance(t, dict) else str(t) for t in (data.get("tags") or [])],
            depends_on=[str(d) for d in (data.get("depends_on_task_ids") or [])],
            is_blocked=bool(data.get("is_blocked", False)),
            blocked_by_task_ids=[str(b) for b in (data.get("blocked_by_task_ids") or [])],
            auto_created=bool(data.get("auto_created", False)),
            due_at=_parse_datetime(data.get("due_at")),
            created_at=_parse_datetime(data.get("created_at")),
            updated_at=_parse_datetime(data.get("updated_at")),
        )