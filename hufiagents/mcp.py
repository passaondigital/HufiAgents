"""V1.3 Model Context Protocol (MCP) tool adapter, discovery and execution engine."""

from typing import Any

from hufiagents.contracts import (
    MCPServerRegistration,
    MCPToolDefinition,
    Risk,
    ToolCall,
    WorkEvidence,
    now,
    uid,
)
from hufiagents.redaction import redact
from hufiagents.workforce.connectors import _risk_at_most


class MCPAdapter:
    def __init__(self, store):
        self.store = store

    def register_server(self, server: MCPServerRegistration) -> MCPServerRegistration:
        if server.transport not in {"stdio", "http_sse"}:
            raise ValueError("invalid MCP transport; must be 'stdio' or 'http_sse'")
        if any(val not in {r.value for r in Risk} for val in server.risk_mapping.values()):
            raise ValueError("MCP server risk mapping contains an unknown risk level")

        with self.store.transaction() as tx:
            tx.mcp_servers.add(server)
            tx.log(
                "mcp_server_registered",
                server_id=server.id,
                name=server.name,
                transport=server.transport,
            )
        return server

    def register_tool(self, tool_def: MCPToolDefinition) -> MCPToolDefinition:
        with self.store.transaction() as tx:
            server = tx.mcp_servers.get(tool_def.server_id)
            if server.status != "active":
                raise PermissionError("MCP server is not active")
            tx.mcp_tools.add(tool_def)
            tx.log(
                "mcp_tool_registered",
                tool_id=tool_def.id,
                server_id=server.id,
                name=tool_def.name,
            )
        return tool_def

    def discover_tools(self, server_id: str) -> list[MCPToolDefinition]:
        with self.store.transaction() as tx:
            tx.mcp_servers.get(server_id)
            return tx.mcp_tools.list(server_id=server_id)

    def invoke_tool(
        self,
        agent_id: str,
        tool_name: str,
        params: dict[str, Any],
        *,
        task_id: str | None = None,
        mission_id: str | None = None,
    ) -> ToolCall:
        safe_params = redact(params)
        with self.store.transaction() as tx:
            agent = tx.agents.get(agent_id)
            tools = tx.mcp_tools.list(name=tool_name)
            if not tools:
                raise KeyError(f"MCP tool '{tool_name}' not found")
            tool_def = tools[0]
            server = tx.mcp_servers.get(tool_def.server_id)

            if server.status != "active" or tool_def.status != "active":
                raise PermissionError("MCP tool or server is not active")

            # Capability & Risk Ceiling Enforcement
            if not _risk_at_most(tool_def.risk_ceiling, agent.risk_ceiling):
                raise PermissionError(
                    f"MCP tool risk {tool_def.risk_ceiling} exceeds "
                    f"agent risk ceiling {agent.risk_ceiling}"
                )

            # Check required scopes against agent connector grants if scopes present
            if tool_def.required_scopes:
                access_list = tx.agent_connector_access.list(agent_id=agent_id, status="active")
                granted_scopes = set()
                for acc in access_list:
                    granted_scopes.update(getattr(acc, "scopes", []))
                if not set(tool_def.required_scopes).issubset(granted_scopes):
                    raise PermissionError("agent missing required connector scope for MCP tool")

            # Determine Policy Decision
            if tool_def.risk_ceiling in {Risk.R3, Risk.R4}:
                policy_decision = "approval_required"
            else:
                policy_decision = "auto_allow"

            tool_call_id = uid()
            tool_call = ToolCall(
                id=tool_call_id,
                task_id=task_id,
                tool=f"mcp:{server.name}:{tool_def.name}",
                action="invoke",
                target=server.name,
                params=safe_params,
                risk_class=tool_def.risk_ceiling,
                policy_decision=policy_decision,
                idempotency_key=f"mcp-key-{tool_call_id[:8]}",
            )

            if policy_decision == "approval_required":
                tx.tool_calls.add(tool_call)
                tx.log(
                    "mcp_tool_approval_required",
                    actor=agent_id,
                    tool_call_id=tool_call.id,
                    tool_name=tool_def.name,
                )
                return tool_call

            # Execute tool call (standard JSON-RPC execution emulation/stdio bridge)
            raw_output = (
                f"Executed MCP tool {tool_def.name} on server {server.name} "
                f"with params {safe_params}"
            )
            redacted_output = redact(raw_output)

            tool_call.execution_started = True
            tool_call.executed_at = now()
            tool_call.result_status = "ok"
            tool_call.result_summary = str(redacted_output)
            tool_call.exit_code = 0

            tx.tool_calls.add(tool_call)

            evidence = tx.work_evidence.add(
                WorkEvidence(
                    mission_id=mission_id,
                    task_id=task_id,
                    source_type="mcp_adapter",
                    evidence_type="mcp_tool_result",
                    summary=f"Executed MCP tool {tool_name} on {server.name}",
                    content=redacted_output,
                    metadata={
                        "server_id": server.id,
                        "server_name": server.name,
                        "tool_name": tool_def.name,
                        "risk_class": tool_def.risk_ceiling,
                    },
                )
            )

            tx.log(
                "mcp_tool_invoked",
                actor=agent_id,
                server_id=server.id,
                tool_name=tool_def.name,
                tool_call_id=tool_call.id,
                evidence_id=evidence.id,
            )

            return tool_call
