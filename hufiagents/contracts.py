"""Persisted V1 contracts. UUIDs use canonical strings at repository boundaries."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def uid() -> str:
    return str(uuid4())


def now() -> datetime:
    return datetime.now(UTC)


class State(StrEnum):
    queued = "queued"
    planning = "planning"
    running = "running"
    waiting_approval = "waiting_approval"
    blocked = "blocked"
    review = "review"
    retrying = "retrying"
    failed = "failed"
    completed = "completed"
    cancelled = "cancelled"


class Risk(StrEnum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class Mission(Contract):
    id: str = Field(default_factory=uid)
    outcome: str = Field(min_length=1, max_length=16000)
    constraints: dict[str, Any] = Field(default_factory=dict)
    status: State = State.queued
    risk_ceiling: Risk = Risk.R1
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    completed_at: datetime | None = None
    requested_by: str = "pascal"
    result: str | None = None


class Task(Contract):
    id: str = Field(default_factory=uid)
    mission_id: str
    parent_task_id: str | None = None
    objective: str
    context_refs: list[str] = Field(default_factory=list)
    expected_output: str = "result.md"
    acceptance_criteria: list[dict[str, Any]] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=lambda: ["files"])
    risk_ceiling: Risk = Risk.R1
    preferred_provider: str | None = None
    budget_tokens: int | None = Field(512, ge=1, le=8192)
    budget_seconds: int | None = Field(300, ge=1, le=3600)
    retry_limit: int = Field(2, ge=0, le=5)
    retry_count: int = 0
    dependencies: list[str] = Field(default_factory=list)
    status: State = State.queued
    assigned_agent_id: str | None = None
    project_id: str | None = None
    dry_run: bool = False
    idempotency_key: str = Field(default_factory=uid)
    heartbeat_at: datetime | None = None
    created_at: datetime = Field(default_factory=now)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    selected_provider: str | None = None
    routing_reason: str | None = None
    result: str | None = None


class Agent(Contract):
    id: str
    role: str
    capabilities: dict[str, Any]
    default_risk_ceiling: Risk = Risk.R1
    # `default_risk_ceiling` is retained for V1 tool-policy compatibility.
    # New workforce code uses `risk_ceiling`; spawned agents always set both.
    name: str = ""
    description: str = ""
    parent_agent_id: str | None = None
    project_id: str | None = None
    risk_ceiling: Risk = Risk.R1
    model_preference: str | None = None
    memory_scope: str = "agent"
    workspace_id: str | None = None
    status: Literal["active", "disabled", "archived"] = "active"
    created_by: str = "system"
    created_at: datetime = Field(default_factory=now)
    archived_at: datetime | None = None


class AgentProfileHistory(Contract):
    id: str = Field(default_factory=uid)
    agent_id: str
    version: int = Field(1, ge=1)
    changed_at: datetime = Field(default_factory=now)
    changed_by: str = "system"
    summary: str = Field(default="", max_length=2000)
    changes: dict[str, Any] = Field(default_factory=dict)
    snapshot: dict[str, Any] = Field(default_factory=dict)


class AgentProvisioningRequest(Contract):
    agent_id: str | None = None
    display_name: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    mission: str = Field(default="", max_length=4000)

    team_ids: list[str] = Field(default_factory=list)
    project_ids: list[str] = Field(default_factory=list)
    skill_ids: list[str] = Field(default_factory=list)
    memory_scopes: list[str] = Field(default_factory=list)
    routine_ids: list[str] = Field(default_factory=list)

    capabilities: dict[str, Any] = Field(default_factory=dict)
    risk_ceiling: Risk = Risk.R1

    model_policy: dict[str, Any] = Field(
        default_factory=lambda: {"preferred": "local", "external_fallback": False}
    )
    model_preference: str | None = None
    external_budget: int = Field(0, ge=0)

    reviewer_agent_id: str | None = None
    participation_mode: Literal["ACTIVE", "LISTENING", "SLEEPING"] = "ACTIVE"

    source: str = "pascal"
    idempotency_key: str | None = None


class Channel(Contract):
    id: str = Field(default_factory=uid)
    name: str = Field(min_length=1, max_length=200)
    project_id: str | None = None
    member_agent_ids: list[str] = Field(default_factory=list)
    status: Literal["active", "archived"] = "active"
    created_at: datetime = Field(default_factory=now)


class Delegation(Contract):
    id: str = Field(default_factory=uid)
    parent_agent_id: str
    child_agent_id: str
    mission_id: str | None = None
    task_id: str | None = None
    objective: str = Field(min_length=1, max_length=16000)
    status: Literal["queued", "running", "completed", "failed", "cancelled"] = "queued"
    result: str | None = None
    correlation_id: str = Field(default_factory=uid)
    created_at: datetime = Field(default_factory=now)
    completed_at: datetime | None = None


class AgentMessage(Contract):
    id: str = Field(default_factory=uid)
    from_agent_id: str
    to_agent_id: str | None = None
    channel_id: str | None = None
    mission_id: str | None = None
    task_id: str | None = None
    content: str = Field(min_length=1, max_length=32000)
    created_at: datetime = Field(default_factory=now)
    status: Literal["unread", "handled"] = "unread"
    correlation_id: str | None = None
    delegation_id: str | None = None


class Routine(Contract):
    """Durable product-level recurring mission; ``schedule`` is deliberately not cron."""

    id: str = Field(default_factory=uid)
    owner_agent_id: str
    project_id: str | None = None
    mission_template: dict[str, Any]
    schedule: str = Field(min_length=1, max_length=1000)
    timezone: str = Field(min_length=1, max_length=100)
    enabled: bool = True
    next_run: datetime | None = None
    last_run: datetime | None = None
    retry_policy: dict[str, Any] = Field(default_factory=lambda: {"max_attempts": 2})
    retry_count: int = Field(0, ge=0, le=20)
    notification_state: Literal["none", "pending", "sent", "failed"] = "none"
    status: Literal["active", "paused", "archived"] = "active"
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class AgentWorkspace(Contract):
    """A logical workspace. storage_key is not a host supplied path."""

    id: str = Field(default_factory=uid)
    agent_id: str
    storage_key: str = Field(min_length=1, max_length=200)
    status: Literal["active", "disabled", "archived"] = "active"
    persistence_policy: Literal["restart", "ephemeral"] = "restart"
    quota_bytes: int = Field(104857600, ge=0, le=10737418240)
    created_at: datetime = Field(default_factory=now)
    archived_at: datetime | None = None


class WorkspaceSession(Contract):
    id: str = Field(default_factory=uid)
    agent_id: str
    workspace_id: str
    status: Literal["active", "closed", "expired"] = "active"
    persistence_policy: Literal["restart", "ephemeral"] = "restart"
    created_at: datetime = Field(default_factory=now)
    last_activity: datetime = Field(default_factory=now)


class ComputerSession(Contract):
    id: str = Field(default_factory=uid)
    agent_id: str
    workspace_id: str
    status: Literal["prepared", "active", "closed", "expired"] = "prepared"
    persistence_policy: Literal["restart", "ephemeral"] = "ephemeral"
    created_at: datetime = Field(default_factory=now)
    last_activity: datetime = Field(default_factory=now)


class BrowserSession(Contract):
    id: str = Field(default_factory=uid)
    agent_id: str
    workspace_id: str
    status: Literal["prepared", "active", "closed", "expired"] = "prepared"
    persistence_policy: Literal["restart", "ephemeral"] = "ephemeral"
    max_tabs: int = Field(1, ge=0, le=8)
    memory_limit_mb: int = Field(512, ge=64, le=2048)
    created_at: datetime = Field(default_factory=now)
    last_activity: datetime = Field(default_factory=now)


class ConnectorRegistration(Contract):
    """Metadata only: credentials stay in a configured secret provider."""

    id: str = Field(default_factory=uid)
    name: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=100)
    capabilities: list[str] = Field(default_factory=list)
    modes: list[Literal["read", "write"]] = Field(default_factory=list)
    auth_state: Literal["unconfigured", "configured", "expired", "error"] = "unconfigured"
    permissions: list[str] = Field(default_factory=list)
    risk_mapping: dict[str, str] = Field(default_factory=dict)
    health: Literal["unknown", "healthy", "degraded", "unhealthy"] = "unknown"
    enabled: bool = True
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class AgentConnectorAccess(Contract):
    id: str = Field(default_factory=uid)
    agent_id: str
    connector_id: str
    capabilities: list[str] = Field(default_factory=list)
    modes: list[Literal["read", "write"]] = Field(default_factory=list)
    risk_ceiling: Risk = Risk.R1
    status: Literal["active", "disabled", "revoked"] = "active"
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)


class Handoff(Contract):
    id: str = Field(default_factory=uid)
    from_agent_id: str
    to_agent_id: str
    task_id: str
    summary: str
    artifacts: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now)


class ToolCall(Contract):
    id: str = Field(default_factory=uid)
    task_id: str
    tool: str
    action: str
    target: str
    params: dict[str, Any] = Field(default_factory=dict)
    risk_class: Risk
    policy_decision: Literal["auto_allow", "reviewer_gate", "approval_required", "denied"]
    idempotency_key: str
    requested_at: datetime = Field(default_factory=now)
    executed_at: datetime | None = None
    result_status: Literal["ok", "error", "timeout", "blocked"] = "blocked"
    result_summary: str = "pending"
    exit_code: int | None = None
    execution_started: bool = False


class ToolResult(ToolCall):
    """Same persisted row, enriched after execution (architecture §3.5)."""


class ReviewResult(Contract):
    id: str = Field(default_factory=uid)
    task_id: str
    reviewer_agent_id: str = "reviewer"
    verdict: Literal["approve", "reject", "revise"]
    findings: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now)


class ApprovalRequest(Contract):
    id: str = Field(default_factory=uid)
    task_id: str | None = None
    tool_call_id: str | None = None
    risk_class: Literal[Risk.R3, Risk.R4]
    summary: str
    status: Literal["pending", "approved", "denied", "expired"] = "pending"
    requested_at: datetime = Field(default_factory=now)
    resolved_at: datetime | None = None
    resolved_by: str | None = None
    resolution_note: str | None = None


class AuditEvent(Contract):
    id: str = Field(default_factory=uid)
    ts: datetime = Field(default_factory=now)
    actor: str = "system"
    mission_id: str | None = None
    task_id: str | None = None
    event_type: str
    detail: dict[str, Any] = Field(default_factory=dict)


class WorkEvidence(Contract):
    """Sanitized, user-visible proof of work.

    Evidence is deliberately separate from audit events: it may be shown in
    product views, while the source payload is always passed through the
    structured redaction boundary before persistence.
    """

    id: str = Field(default_factory=uid)
    mission_id: str | None = None
    task_id: str | None = None
    source_type: str = Field(min_length=1, max_length=64)
    evidence_type: str = Field(min_length=1, max_length=64)
    summary: str = Field(default="", max_length=16000)
    content: Any = None
    artifact_ref: str | None = Field(default=None, max_length=2000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now)
    redacted_at: datetime | None = None


class MemoryRecord(Contract):
    id: str = Field(default_factory=uid)
    owner_id: str
    key: str
    value: dict[str, Any]
    created_at: datetime = Field(default_factory=now)


class Team(Contract):
    id: str = Field(default_factory=uid)
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    status: Literal["active", "archived"] = "active"
    created_at: datetime = Field(default_factory=now)
    archived_at: datetime | None = None


class GraphProject(Contract):
    id: str = Field(default_factory=uid)
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    repository_ref: str | None = None
    status: Literal["active", "archived"] = "active"
    created_at: datetime = Field(default_factory=now)
    archived_at: datetime | None = None


class Resource(Contract):
    id: str = Field(default_factory=uid)
    name: str = Field(min_length=1, max_length=200)
    resource_type: str = "other"
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: Literal["active", "archived"] = "active"
    created_at: datetime = Field(default_factory=now)
    archived_at: datetime | None = None


class GraphRelationship(Contract):
    id: str = Field(default_factory=uid)
    relationship_type: Literal[
        "reports_to",
        "member_of_team",
        "works_on_project",
        "responsible_for_resource",
        "may_use_resource",
    ]
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    primary: bool = False
    created_at: datetime = Field(default_factory=now)
    removed_at: datetime | None = None


class ChatRoom(Contract):
    id: str = Field(default_factory=uid)
    room_type: Literal["agent", "team", "project", "company"]
    host_type: str
    host_id: str | None = None
    name: str = Field(min_length=1, max_length=200)
    created_at: datetime = Field(default_factory=now)
    archived_at: datetime | None = None


class RoomMessage(Contract):
    """A persistent, redacted message posted to a team room.

    ``mention_agent_ids`` carries the resolved IDs of any @mentions found in
    the raw content *before* redaction; they are used by the dispatch bridge to
    fan-out tasks to the correct agents.  ``content`` is always stored in its
    redacted form.
    """

    id: str = Field(default_factory=uid)
    room_id: str
    sender_type: Literal["user", "agent", "system"] = "user"
    sender_id: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=32000)
    mention_agent_ids: list[str] = Field(default_factory=list)
    mission_id: str | None = None
    task_id: str | None = None
    parent_message_id: str | None = None
    created_at: datetime = Field(default_factory=now)
    status: Literal["visible", "redacted", "deleted"] = "visible"


class RoomParticipant(Contract):
    """Tracks an agent's membership and participation state in a room.

    Participation states (execution-only; NOT authorization):

    * ``active``    – eligible for normal policy-driven dispatch.
    * ``listening`` – observes the room; executes only if explicitly @mentioned
                      or a policy allows it.
    * ``sleeping``  – not auto-dispatched; must be @mentioned explicitly.
    * ``left``      – no longer a room member; not eligible for dispatch.

    Changing a participation state NEVER raises risk ceilings, capabilities,
    connector scopes, or credential rights.  Those are governed entirely by the
    agent's own policy and the existing Orchestrator/Risk engine.
    """

    id: str = Field(default_factory=uid)
    room_id: str
    agent_id: str
    participation_state: Literal["active", "listening", "sleeping", "left"] = "active"
    joined_at: datetime = Field(default_factory=now)
    left_at: datetime | None = None


class CredentialRef(Contract):
    """Metadata-only credential handle; plaintext values never enter this model."""

    id: str = Field(default_factory=uid)
    connector: str
    label: str
    scopes: list[str] = Field(default_factory=list)
    status: Literal["active", "revoked"] = "active"
    created_at: datetime = Field(default_factory=now)
    rotated_at: datetime | None = None
    revoked_at: datetime | None = None


class Skill(Contract):
    id: str = Field(default_factory=uid)
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    version: str = "1.0"
    scope_type: Literal["global", "agent", "team", "project"] = "global"
    scope_id: str | None = None
    owner_agent_id: str | None = None
    steps: list[dict[str, Any]] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    risk_ceiling: Risk = Risk.R1
    status: Literal["draft", "approved", "archived"] = "draft"
    source: Literal["system", "manual", "learned"] = "manual"
    success_count: int = 0
    failure_count: int = 0
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    last_used_at: datetime | None = None


class ScopedMemory(Contract):
    id: str = Field(default_factory=uid)
    scope_type: Literal["user", "global", "agent", "project", "mission", "shared"]
    scope_id: str | None = None
    category: str = "general"
    summary: str
    content: str
    importance: float = Field(0.5, ge=0, le=1)
    confidence: float = Field(0.5, ge=0, le=1)
    source: str = "manual"
    created_at: datetime = Field(default_factory=now)
    updated_at: datetime = Field(default_factory=now)
    last_used_at: datetime | None = None


class LearningRecord(Contract):
    id: str = Field(default_factory=uid)
    mission_id: str
    outcome: Literal[
        "memory_created", "memory_updated", "skill_proposed", "skill_updated", "skipped"
    ]
    target_id: str | None = None
    reason: str = ""
    created_at: datetime = Field(default_factory=now)
