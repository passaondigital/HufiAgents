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
    status: Literal["active", "disabled"] = "active"


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


class MemoryRecord(Contract):
    id: str = Field(default_factory=uid)
    owner_id: str
    key: str
    value: dict[str, Any]
    created_at: datetime = Field(default_factory=now)
