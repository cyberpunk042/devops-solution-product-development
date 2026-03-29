"""Fleet core interfaces — abstract contracts for infrastructure adapters.

These interfaces define WHAT the fleet needs from external systems.
The infra/ layer implements HOW.

This module has NO external dependencies.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from fleet.core.models import (
    Agent,
    Approval,
    BoardMemoryEntry,
    FleetContext,
    Project,
    PullRequest,
    Task,
    TaskCustomFields,
)


class TaskClient(ABC):
    """Interface for Mission Control task operations."""

    @abstractmethod
    async def get_task(self, board_id: str, task_id: str) -> Task:
        """Fetch a task by ID."""

    @abstractmethod
    async def list_tasks(
        self, board_id: str, status: Optional[str] = None, limit: int = 100
    ) -> list[Task]:
        """List tasks on a board, optionally filtered by status."""

    @abstractmethod
    async def update_task(
        self,
        board_id: str,
        task_id: str,
        *,
        status: Optional[str] = None,
        comment: Optional[str] = None,
        custom_fields: Optional[dict] = None,
        tag_ids: Optional[list[str]] = None,
    ) -> Task:
        """Update task status, comment, custom fields, or tags."""

    @abstractmethod
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
    ) -> Task:
        """Create a new task."""

    @abstractmethod
    async def post_comment(
        self, board_id: str, task_id: str, message: str
    ) -> dict:
        """Post a comment on a task."""


class MemoryClient(ABC):
    """Interface for Mission Control board memory operations."""

    @abstractmethod
    async def post_memory(
        self,
        board_id: str,
        content: str,
        tags: list[str],
        source: str,
    ) -> BoardMemoryEntry:
        """Post an entry to board memory."""

    @abstractmethod
    async def list_memory(
        self, board_id: str, limit: int = 20, tags: Optional[list[str]] = None
    ) -> list[BoardMemoryEntry]:
        """List board memory entries, optionally filtered by tags."""


class ApprovalClient(ABC):
    """Interface for Mission Control approval operations."""

    @abstractmethod
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

    @abstractmethod
    async def approve_approval(
        self,
        board_id: str,
        approval_id: str,
        *,
        status: str = "approved",
        comment: str = "",
    ) -> Approval:
        """Approve or reject a pending approval."""

    @abstractmethod
    async def list_approvals(
        self, board_id: str, status: str = ""
    ) -> list[Approval]:
        """List approvals on a board."""


class AgentClient(ABC):
    """Interface for agent discovery and health."""

    @abstractmethod
    async def list_agents(self) -> list[Agent]:
        """List all fleet agents."""

    @abstractmethod
    async def get_board_id(self) -> Optional[str]:
        """Get the fleet board ID."""


class NotificationClient(ABC):
    """Interface for sending notifications to IRC channels."""

    @abstractmethod
    async def notify(
        self, channel: str, message: str
    ) -> bool:
        """Send a message to an IRC channel. Returns True on success."""


class GitClient(ABC):
    """Interface for git operations in worktrees."""

    @abstractmethod
    async def push_branch(self, worktree: str, branch: str) -> bool:
        """Push a branch to remote. Returns True on success."""

    @abstractmethod
    async def create_pr(
        self,
        worktree: str,
        *,
        title: str,
        body: str,
    ) -> PullRequest:
        """Create a pull request. Returns the PR with URL and number."""

    @abstractmethod
    async def get_pr_state(self, pr_url: str) -> Optional[str]:
        """Check PR state: OPEN, CLOSED, or MERGED."""

    @abstractmethod
    async def merge_pr(self, pr_url: str) -> bool:
        """Merge a PR. Returns True on success."""

    @abstractmethod
    async def get_branch_commits(
        self, worktree: str, base: str = "origin/main"
    ) -> list[dict]:
        """Get commits on branch since base. Returns list of {sha, message}."""

    @abstractmethod
    async def get_diff_stat(
        self, worktree: str, base: str = "origin/main"
    ) -> list[dict]:
        """Get diff stat. Returns list of {path, added, removed}."""


class ConfigLoader(ABC):
    """Interface for loading fleet configuration."""

    @abstractmethod
    def load_projects(self) -> dict[str, Project]:
        """Load project registry from config/projects.yaml."""

    @abstractmethod
    def load_url_templates(self) -> dict:
        """Load URL templates from config/url-templates.yaml."""

    @abstractmethod
    def load_tools_md(self, workspace: str) -> dict:
        """Load credentials from a TOOLS.md file."""