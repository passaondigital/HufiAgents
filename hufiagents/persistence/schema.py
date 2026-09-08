"""SQLAlchemy Core columns mirror every public contract; migration 001 owns creation."""

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, MetaData, String, Table

from hufiagents.contracts import (
    Agent,
    AgentConnectorAccess,
    AgentMessage,
    AgentWorkspace,
    ApprovalRequest,
    AuditEvent,
    ChatRoom,
    CredentialRef,
    GraphProject,
    GraphRelationship,
    BrowserSession,
    Channel,
    ComputerSession,
    ConnectorRegistration,
    Delegation,
    Handoff,
    LearningRecord,
    MemoryRecord,
    Mission,
    Resource,
    ReviewResult,
    ScopedMemory,
    Skill,
    Routine,
    Task,
    Team,
    ToolCall,
    WorkEvidence,
    WorkspaceSession,
)

metadata = MetaData()
MODELS = {
    "missions": Mission,
    "tasks": Task,
    "agents": Agent,
    "routines": Routine,
    "agent_workspaces": AgentWorkspace,
    "workspace_sessions": WorkspaceSession,
    "computer_sessions": ComputerSession,
    "browser_sessions": BrowserSession,
    "connectors": ConnectorRegistration,
    "agent_connector_access": AgentConnectorAccess,
    "agent_messages": AgentMessage,
    "delegations": Delegation,
    "channels": Channel,
    "handoffs": Handoff,
    "tool_calls": ToolCall,
    "reviews": ReviewResult,
    "approvals": ApprovalRequest,
    "audit_log": AuditEvent,
    "task_context": MemoryRecord,
    "project_knowledge": MemoryRecord,
    "agent_memory": MemoryRecord,
    "work_evidence": WorkEvidence,
    "teams": Team,
    "graph_projects": GraphProject,
    "resources": Resource,
    "relationships": GraphRelationship,
    "chat_rooms": ChatRoom,
    "credential_refs": CredentialRef,
    "skills": Skill,
    "scoped_memories": ScopedMemory,
    "learning_records": LearningRecord,
}
JSON_FIELDS = {
    "constraints",
    "context_refs",
    "acceptance_criteria",
    "allowed_tools",
    "dependencies",
    "capabilities",
    "artifacts",
    "params",
    "findings",
    "detail",
    "value",
    "content",
    "metadata",
    "scopes",
    "steps",
    "required_capabilities",
    "input_schema",
    "output_schema",
    "member_agent_ids",
    "mission_template",
    "retry_policy",
    "modes",
    "permissions",
    "risk_mapping",
}
INTEGER_FIELDS = {
    "budget_tokens",
    "budget_seconds",
    "retry_limit",
    "retry_count",
    "exit_code",
    "quota_bytes",
    "max_tabs",
    "memory_limit_mb",
}
FK = {
    "mission_id": "missions.id",
    "task_id": "tasks.id",
    "parent_task_id": "tasks.id",
    "tool_call_id": "tool_calls.id",
    "delegation_id": "delegations.id",
    "owner_agent_id": "agents.id",
    "agent_id": "agents.id",
    "workspace_id": "agent_workspaces.id",
    "connector_id": "connectors.id",
}
TABLES = {}
for name, model in MODELS.items():
    columns = []
    for field in model.model_fields:
        kind = (
            JSON
            if field in JSON_FIELDS
            else Integer
            if field in INTEGER_FIELDS
            else Boolean
            if field in {"execution_started", "dry_run"}
            else String
        )
        args = [ForeignKey(FK[field])] if field in FK else []
        columns.append(
            Column(
                field,
                kind,
                *args,
                primary_key=field == "id",
                unique=name == "tool_calls" and field == "idempotency_key",
            )
        )
    TABLES[name] = Table(name, metadata, *columns)
Table("schema_migrations", metadata, Column("version", Integer, primary_key=True))
