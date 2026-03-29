"""Fleet domain models — pure data structures.

No business logic. No external dependencies. Just typed data.
Business rules live in lifecycle.py and quality.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ─── Enums ──────────────────────────────────────────────────────────────────


class TaskStatus(str, Enum):
    """Task lifecycle states."""

    INBOX = "inbox"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"


class AlertSeverity(str, Enum):
    """Alert severity levels — drives routing."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertCategory(str, Enum):
    """Alert categories."""

    SECURITY = "security"
    QUALITY = "quality"
    ARCHITECTURE = "architecture"
    WORKFLOW = "workflow"
    TOOLING = "tooling"


class AgentRole(str, Enum):
    """Agent types — worker or driver."""

    WORKER = "worker"
    DRIVER = "driver"


class TaskType(str, Enum):
    """Hierarchical task types."""

    EPIC = "epic"
    STORY = "story"
    TASK = "task"
    SUBTASK = "subtask"
    BLOCKER = "blocker"
    REQUEST = "request"
    CONCERN = "concern"


class CommitType(str, Enum):
    """Conventional commit types."""

    FEAT = "feat"
    FIX = "fix"
    DOCS = "docs"
    REFACTOR = "refactor"
    TEST = "test"
    CHORE = "chore"
    CI = "ci"
    STYLE = "style"
    PERF = "perf"


# ─── Domain Models ──────────────────────────────────────────────────────────


@dataclass
class Project:
    """A project the fleet works on."""

    name: str
    owner: str  # GitHub owner
    repo: str  # GitHub repo name
    description: str = ""
    local: bool = False  # True if it's the fleet repo itself

    @property
    def github_url(self) -> str:
        return f"https://github.com/{self.owner}/{self.repo}"


@dataclass
class TaskCustomFields:
    """Custom field values on a task."""

    project: Optional[str] = None
    branch: Optional[str] = None
    pr_url: Optional[str] = None
    worktree: Optional[str] = None
    agent_name: Optional[str] = None
    story_points: Optional[int] = None
    sprint: Optional[str] = None
    complexity: Optional[str] = None
    model: Optional[str] = None
    parent_task: Optional[str] = None
    task_type: Optional[str] = None
    plan_id: Optional[str] = None
    # Review gates — populated by fleet_task_complete, read by fleet-ops (board lead)
    review_gates: Optional[list] = None
    # Plane integration fields — set when a task is synced from a Plane issue
    plane_issue_id: Optional[str] = None
    plane_project_id: Optional[str] = None
    plane_workspace: Optional[str] = None


@dataclass
class Task:
    """A Mission Control task."""

    id: str
    board_id: str
    title: str
    status: TaskStatus
    description: str = ""
    priority: str = "medium"
    assigned_agent_id: Optional[str] = None
    custom_fields: TaskCustomFields = field(default_factory=TaskCustomFields)
    tags: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    is_blocked: bool = False
    blocked_by_task_ids: list[str] = field(default_factory=list)
    auto_created: bool = False
    due_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @property
    def short_id(self) -> str:
        """First 8 chars of task ID — used in branches and references."""
        return self.id[:8]


@dataclass
class Agent:
    """A fleet agent."""

    id: str
    name: str
    role: AgentRole = AgentRole.WORKER
    status: str = "offline"
    board_id: Optional[str] = None
    session_key: Optional[str] = None
    capabilities: list[str] = field(default_factory=list)
    model: str = "sonnet"
    last_seen: Optional[datetime] = None


@dataclass
class Approval:
    """A task approval with confidence and rubric scoring."""

    id: str
    board_id: str
    task_id: str
    action_type: str
    confidence: float  # 0-100
    rubric_scores: dict[str, int] = field(default_factory=dict)
    reason: str = ""
    status: str = "pending"  # pending, approved, rejected
    agent_id: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


@dataclass
class BoardMemoryEntry:
    """A board memory entry."""

    id: str
    board_id: str
    content: str
    tags: list[str] = field(default_factory=list)
    source: str = ""
    created_at: Optional[datetime] = None


@dataclass
class Commit:
    """A git commit."""

    sha: str
    message: str
    commit_type: Optional[CommitType] = None
    scope: Optional[str] = None
    description: str = ""
    task_ref: Optional[str] = None

    @property
    def short_sha(self) -> str:
        return self.sha[:7]


@dataclass
class PullRequest:
    """A GitHub pull request."""

    url: str
    number: int
    title: str
    branch: str
    state: str = "open"  # open, closed, merged
    commits: list[Commit] = field(default_factory=list)
    files_changed: list[str] = field(default_factory=list)


@dataclass
class FleetContext:
    """Full context for an agent starting a task.

    Loaded by fleet_read_context MCP tool.
    Gives the agent everything it needs to start informed.
    """

    task: Task
    project: Project
    agent: Agent
    urls: dict[str, str] = field(default_factory=dict)
    recent_memory: list[BoardMemoryEntry] = field(default_factory=list)
    recent_decisions: list[BoardMemoryEntry] = field(default_factory=list)
    active_blockers: list[BoardMemoryEntry] = field(default_factory=list)
    team_activity: list[dict] = field(default_factory=list)


@dataclass
class EventChainResult:
    """Result of executing an event chain."""

    ok: bool
    internal_results: list[dict] = field(default_factory=list)
    public_results: list[dict] = field(default_factory=list)
    channel_results: list[dict] = field(default_factory=list)
    meta_results: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)