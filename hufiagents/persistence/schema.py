"""SQLAlchemy Core columns mirror every public contract; migration 001 owns creation."""

from sqlalchemy import JSON, Boolean, Column, ForeignKey, Integer, MetaData, String, Table

from hufiagents.contracts import (
    Agent,
    AgentConnectorAccess,
    AgentMessage,
    AgentProfileHistory,
    AgentWorkspace,
    ApprovalRequest,
    AuditEvent,
    BrowserSession,
    Channel,
    ChatRoom,
    ComputerSession,
    ConnectorRegistration,
    CredentialRef,
    Delegation,
    GraphProject,
    GraphRelationship,
    Handoff,
    LearningRecord,
    MCPServerRegistration,
    MCPToolDefinition,
    MemoryRecord,
    Mission,
    Resource,
    ReviewResult,
    RoomMessage,
    RoomParticipant,
    Routine,
    ScopedMemory,
    Skill,
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
    "agent_profile_history": AgentProfileHistory,
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
    "room_messages": RoomMessage,
    "room_participants": RoomParticipant,
    "credential_refs": CredentialRef,
    "skills": Skill,
    "scoped_memories": ScopedMemory,
    "learning_records": LearningRecord,
    "mcp_servers": MCPServerRegistration,
    "mcp_tools": MCPToolDefinition,
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
    "mention_agent_ids",
    "changes",
    "snapshot",
    "args",
    "env_keys",
    "required_scopes",
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
    "active_tab_count",
}
# Per-table field type overrides: (table_name, field_name) → SQLAlchemy type.
# Used when the same field name carries different Python types across contracts
# (e.g. Skill.version is a semver string, AgentProfileHistory.version is int).
TABLE_FIELD_OVERRIDES: dict[tuple[str, str], type] = {
    ("agent_profile_history", "version"): Integer,
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
    "server_id": "mcp_servers.id",
}
TABLES = {}
for name, model in MODELS.items():
    columns = []
    for field in model.model_fields:
        kind = TABLE_FIELD_OVERRIDES.get(
            (name, field),
            JSON
            if field in JSON_FIELDS
            else Integer
            if field in INTEGER_FIELDS
            else Boolean
            if field in {"execution_started", "dry_run"}
            else String,
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
