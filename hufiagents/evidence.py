"""V1.3A Evidence Collector & Execution Feed Service.

Transforms real, persisted runtime audit events and state transitions into
sanitised, human-readable WorkEvidence records and truthful execution feeds.
No fake live activity, simulated percentages, or fabricated step counts.
"""

from typing import Any, Literal

from hufiagents.contracts import RoomMessage, WorkEvidence, now
from hufiagents.redaction import redact

# Event types ignored to prevent circular logging
IGNORED_EVENT_TYPES = {
    "work_evidence_created",
    "work_evidence_redacted",
    "audit_logged",
}

# Major milestones to notify Room chat if mission belongs to a room
MAJOR_MILESTONES = {
    "mission_created",
    "mission_completed",
    "handoff",
    "approval_requested",
    "artifact_created",
    "task_failed",
}


class EvidenceCollector:
    """Central collector converting audit events to WorkEvidence records."""

    @classmethod
    def process_event(
        cls,
        tx,
        event_type: str,
        *,
        task=None,
        mission_id: str | None = None,
        actor: str = "system",
        detail: dict[str, Any] | None = None,
    ) -> WorkEvidence | None:
        if event_type in IGNORED_EVENT_TYPES:
            return None

        detail = detail or {}
        m_id = task.mission_id if task else mission_id
        t_id = task.id if task else None
        agent_id = (task.assigned_agent_id if task else None) or actor or "system"

        source_type = "SYSTEM"
        evidence_type = "INFO"
        summary = ""
        content = None
        artifact_ref = None
        metadata = {
            "event_type": event_type,
            "actor": actor,
            "agent_id": agent_id,
        }

        # 1. Mission Created
        if event_type == "mission_created":
            source_type = "MISSION"
            evidence_type = "STARTED"
            outcome = ""
            if m_id:
                try:
                    m = tx.missions.get(m_id)
                    outcome = m.outcome
                except KeyError:
                    outcome = ""
            summary = f"Mission gestartet: {outcome}".strip() if outcome else "Mission gestartet"
            metadata["outcome"] = outcome

        # 2. Mission Completed
        elif event_type == "mission_completed":
            source_type = "MISSION"
            evidence_type = "COMPLETED"
            summary = "Mission erfolgreich abgeschlossen"
            content = detail.get("result")

        # 3. Task State Transitions
        elif event_type == "state_transition":
            target = detail.get("target")
            source = detail.get("source")
            reason = detail.get("reason", "")

            if target == "running" and source != "running":
                source_type = "TASK"
                evidence_type = "STARTED"
                obj = task.objective if task else "Aufgabe"
                summary = f"Aufgabe gestartet: {obj}"
                metadata["objective"] = obj

            elif target == "review":
                source_type = "REVIEW"
                evidence_type = "STARTED"
                summary = "Review gestartet"

            elif target == "retrying":
                source_type = "TASK"
                evidence_type = "RETRY"
                summary = f"Aufgabe wird erneut versucht: {reason}".strip(": ")

            elif target == "failed":
                source_type = "ERROR"
                evidence_type = "FAILED"
                summary = f"Aufgabe fehlgeschlagen: {reason}".strip(": ")
                metadata["reason"] = reason

            else:
                return None

        # 4. Repo Context Prepared
        elif event_type == "repo_context_prepared":
            source_type = "REPO_CONTEXT"
            evidence_type = "PREPARED"
            count = detail.get("selected_count", 0)
            truncated = detail.get("truncated", False)
            if truncated:
                summary = "Repository-Kontext begrenzt"
            else:
                summary = f"Repository-Kontext vorbereitet: {count} relevante Dateien"
            metadata["selected_count"] = count
            metadata["truncated"] = truncated

        # 4b. Knowledge Context Prepared
        elif event_type == "knowledge_context_prepared":
            source_type = "KNOWLEDGE"
            evidence_type = "REUSED"
            mem_count = detail.get("memory_count", 0)
            skill_count = detail.get("skill_count", 0)
            skill_names = detail.get("skill_names", [])

            parts = []
            if mem_count == 1:
                parts.append("1 freigegebene Projekterfahrung wiederverwendet")
            elif mem_count > 1:
                parts.append(f"{mem_count} freigegebene Erfahrungen wiederverwendet")

            if skill_names:
                parts.append(f"Skill {skill_names[0]} angewendet")
            elif skill_count > 0:
                parts.append(f"{skill_count} Skill(s) angewendet")

            summary = " & ".join(parts) if parts else "Freigegebenes Wissen wiederverwendet"
            metadata["memory_count"] = mem_count
            metadata["skill_count"] = skill_count
            metadata["skill_names"] = skill_names

        # 5. Tool Results
        elif event_type == "tool_result":
            tool_call_id = detail.get("tool_call_id")
            tool_call = None
            if tool_call_id:
                try:
                    tool_call = tx.tool_calls.get(tool_call_id)
                except KeyError:
                    tool_call = None

            tool_name = (tool_call.tool if tool_call else detail.get("tool")) or "tool"
            action = (tool_call.action if tool_call else detail.get("action")) or "execute"
            target = (tool_call.target if tool_call else detail.get("target")) or ""
            exit_code = (
                detail.get("exit_code")
                if detail.get("exit_code") is not None
                else (tool_call.exit_code if tool_call else 0)
            )
            status = detail.get("status") or (tool_call.result_status if tool_call else "ok")

            raw_out = redact(
                detail.get("raw_output") or detail.get("output") or detail.get("error") or ""
            )
            if raw_out:
                metadata["raw_output"] = raw_out

            if tool_name == "files" and action in {"write", "write_file", "create_file"}:
                source_type = "ARTIFACT"
                evidence_type = "CREATED"
                summary = (
                    f"Bericht erstellt: {target}"
                    if target.endswith(".md")
                    else f"Artefakt erstellt: {target}"
                )
                artifact_ref = target

            elif (
                tool_name in {"shell", "terminal"}
                or "test" in target.lower()
                or "pytest" in target.lower()
                or "test" in str(detail).lower()
            ):
                source_type = "TEST"
                is_ok = (exit_code == 0 or exit_code is None) and status == "ok"
                evidence_type = "PASSED" if is_ok else "FAILED"
                summary = (
                    "Tests erfolgreich abgeschlossen"
                    if is_ok
                    else f"Testlauf fehlgeschlagen (Exit Code {exit_code})"
                )
                metadata["target"] = target
                metadata["exit_code"] = exit_code

            elif tool_name == "git":
                source_type = "GIT"
                evidence_type = "COMMIT" if action == "commit" else "STATUS"
                summary = (
                    "Änderung als Commit gespeichert"
                    if action == "commit"
                    else "Git-Änderungen geprüft"
                )
                metadata["action"] = action

            else:
                source_type = "TOOL"
                evidence_type = "EXECUTED"
                summary = f"Werkzeug ausgeführt: {tool_name}"
                metadata["tool"] = tool_name
                metadata["action"] = action

        # 6. Review Verdict
        elif event_type == "review":
            source_type = "REVIEW"
            verdict = detail.get("verdict")
            if verdict == "approve":
                evidence_type = "APPROVED"
                summary = "Review erfolgreich abgeschlossen"
            elif verdict == "revise":
                evidence_type = "REVISE"
                summary = "Überarbeitung durch Reviewer angefordert"
            else:
                evidence_type = "REJECTED"
                summary = "Review abgelehnt"
            metadata["verdict"] = verdict

        # 7. Approvals
        elif event_type == "approval_requested":
            source_type = "APPROVAL"
            evidence_type = "REQUESTED"
            risk = detail.get("risk_ceiling", "R2")
            summary = f"Freigabe erforderlich (Stufe {risk})"
            metadata["risk_ceiling"] = risk

        elif event_type == "approval_granted":
            source_type = "APPROVAL"
            evidence_type = "GRANTED"
            summary = "Freigabe erteilt"

        elif event_type == "approval_rejected":
            source_type = "APPROVAL"
            evidence_type = "REJECTED"
            summary = "Freigabe abgelehnt"

        # 8. Handoff
        elif event_type == "handoff":
            source_type = "HANDOFF"
            evidence_type = "DELEGATED"
            from_agent = detail.get("from_agent", agent_id)
            to_agent = detail.get("to_agent", "reviewer")
            summary = f"{from_agent} übergibt an {to_agent}"
            metadata["from_agent"] = from_agent
            metadata["to_agent"] = to_agent

        # 9. Routine
        elif event_type in {"routine_created", "routine_execution"}:
            source_type = "ROUTINE"
            evidence_type = "EXECUTED"
            name = detail.get("routine_name") or detail.get("name") or "Routine"
            summary = f"Routine gestartet: {name}"
            metadata["routine_id"] = detail.get("routine_id")

        # 10. Workforce provisioning
        elif event_type == "agent_created":
            source_type = "WORKFORCE"
            evidence_type = "PROVISIONED"
            display_name = detail.get("display_name") or detail.get("role") or agent_id
            role = detail.get("role", "")
            summary = f"Agent bereitgestellt: {display_name}" + (f" ({role})" if role else "")
            metadata["role"] = role

        elif event_type == "provisioning_completed":
            source_type = "WORKFORCE"
            evidence_type = "COMPLETED"
            summary = f"Provisioning abgeschlossen: Agent {detail.get('agent_id', agent_id)}"
            metadata["idempotency_key"] = detail.get("idempotency_key")

        elif event_type == "agent_updated":
            source_type = "WORKFORCE"
            evidence_type = "UPDATED"
            fields = detail.get("fields", [])
            summary = f"Agent-Profil aktualisiert: {', '.join(fields) if fields else 'Felder'}"
            metadata["fields"] = fields

        elif event_type == "agent_archived":
            source_type = "WORKFORCE"
            evidence_type = "ARCHIVED"
            summary = f"Agent archiviert: {detail.get('agent_id', agent_id)}"

        # 11. Browser automation
        elif event_type == "browser_navigated":
            source_type = "BROWSER"
            evidence_type = "NAVIGATED"
            url = detail.get("url", "")
            summary = f"Seite geöffnet: {url}"
            metadata["url"] = url
            metadata["session_id"] = detail.get("session_id")

        elif event_type == "browser_action_executed" or event_type == "browser_action_completed":
            source_type = "BROWSER"
            evidence_type = "INTERACTED"
            action = detail.get("action", "")
            selector = detail.get("selector", "")
            summary = f"Browser-Aktion ausgeführt: {action}" + (
                f" ({selector})" if selector else ""
            )
            metadata["action"] = action
            metadata["session_id"] = detail.get("session_id")

        elif event_type == "browser_screenshot_captured":
            source_type = "BROWSER"
            evidence_type = "SCREENSHOT"
            artifact_ref = detail.get("artifact_ref")
            summary = "Screenshot erstellt"
            metadata["session_id"] = detail.get("session_id")
            metadata["artifact_ref"] = artifact_ref

        else:
            return None

        # Redact fields before database insertion
        summary = redact(summary)
        if content:
            content = redact(content)
        if artifact_ref:
            artifact_ref = redact(artifact_ref)
        metadata = redact(metadata)

        # Deduplication check
        if m_id:
            existing = tx.work_evidence.list(mission_id=m_id, limit=20)
            for e in existing:
                if (
                    e.summary == summary
                    and e.evidence_type == evidence_type
                    and (not t_id or e.task_id == t_id)
                ):
                    return None

        record = WorkEvidence(
            mission_id=m_id,
            task_id=t_id,
            source_type=source_type,
            evidence_type=evidence_type,
            summary=summary,
            content=content,
            artifact_ref=artifact_ref,
            metadata=metadata,
        )

        saved = tx.work_evidence.add(record)

        # Major milestone notification to Room chat
        if m_id and (
            event_type in MAJOR_MILESTONES
            or evidence_type in {"COMPLETED", "FAILED", "DELEGATED", "REQUESTED", "CREATED"}
        ):
            cls._notify_room_milestone(tx, m_id, agent_id, summary)

        return saved

    @classmethod
    def _notify_room_milestone(cls, tx, mission_id: str, agent_id: str, summary: str):
        """Post a concise milestone message to Room chat if mission originated from a room."""
        m = tx.missions.get(mission_id)
        room_id = m.constraints.get("room_id") if m.constraints else None
        if room_id:
            recent = tx.room_messages.list(room_id=room_id, limit=5)
            m_text = f"📌 {summary}"
            if not any(msg.content == m_text for msg in recent):
                tx.room_messages.add(
                    RoomMessage(
                        room_id=room_id,
                        sender_type="agent" if agent_id != "system" else "system",
                        sender_id=agent_id,
                        content=m_text,
                    )
                )


def get_mission_execution_feed(
    tx,
    mission_id: str,
    *,
    mode: Literal["simple", "transparent", "live"] = "transparent",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Build truthful execution feed derived strictly from persisted state/evidence."""
    mission = tx.missions.get(mission_id)
    tasks = tx.tasks.list(mission_id=mission_id, limit=100)
    evidence_list = tx.work_evidence.list(mission_id=mission_id, limit=limit, offset=offset)
    workforce_events = tx.workforce_events.list(
        mission_id=mission_id, limit=limit, offset=offset, descending=True
    )
    persisted_artifacts = tx.work_artifacts.list(mission_id=mission_id, limit=100)

    completed_tasks = [t for t in tasks if t.status == "completed"]
    blocked_tasks = [t for t in tasks if t.status in {"blocked", "waiting_approval"}]

    total_steps = len(tasks) if tasks else None
    completed_steps = len(completed_tasks)

    last_activity_at = mission.updated_at
    if evidence_list:
        last_activity_at = evidence_list[-1].created_at

    current_activity = "Aufgabe läuft"
    if mission.status == "completed":
        current_activity = "Mission erfolgreich abgeschlossen"
    elif mission.status == "failed":
        current_activity = "Mission fehlgeschlagen"
    elif blocked_tasks:
        current_activity = "Freigabe erforderlich"
    elif evidence_list:
        latest_e = evidence_list[-1]
        if latest_e.summary:
            current_activity = latest_e.summary

    agents_map = {}
    for t in tasks:
        ag_id = t.assigned_agent_id or "builder"
        if ag_id not in agents_map:
            ag_role = ag_id
            try:
                ag_obj = tx.agents.get(ag_id)
                ag_role = ag_obj.role
            except KeyError:
                ag_role = ag_id
            agent_events = [event for event in workforce_events if event.agent_id == ag_id]
            latest_event = agent_events[0] if agent_events else None
            agents_map[ag_id] = {
                "agent_id": ag_id,
                "role": ag_role,
                "status": t.status,
                "current_activity": latest_event.safe_summary
                if latest_event
                else f"Aufgabe {t.status}",
                "last_activity_at": latest_event.timestamp
                if latest_event
                else t.heartbeat_at or t.created_at or last_activity_at,
                "unread_event_count": sum(1 for event in agent_events if event.read_at is None),
                "active_task_count": sum(
                    1
                    for candidate in tasks
                    if candidate.assigned_agent_id == ag_id
                    and str(candidate.status)
                    in {
                        "queued",
                        "planning",
                        "running",
                        "review",
                        "retrying",
                        "blocked",
                        "waiting_approval",
                    }
                ),
            }

    artifacts = [artifact for artifact in persisted_artifacts]

    recent_evidence = [
        {
            "id": e.id,
            "mission_id": e.mission_id,
            "task_id": e.task_id,
            "source_type": e.source_type,
            "evidence_type": e.evidence_type,
            "summary": e.summary,
            "content": e.content,
            "artifact_ref": e.artifact_ref,
            "metadata": e.metadata,
            "created_at": e.created_at,
        }
        for e in evidence_list
    ]

    if mode == "simple":
        recent_evidence = recent_evidence[-5:]

    return {
        "mission_id": mission.id,
        "status": mission.status,
        "outcome": mission.outcome,
        "created_at": mission.created_at,
        "completed_at": mission.completed_at,
        "current_activity": current_activity,
        "last_activity_at": last_activity_at,
        "step_summary": {
            "completed_steps": completed_steps,
            "total_steps": total_steps,
        },
        "agents": list(agents_map.values()),
        "recent_evidence": recent_evidence,
        "events": workforce_events,
        "artifacts": artifacts,
        "blockers": [t.id for t in blocked_tasks],
        "approvals": [t.id for t in blocked_tasks if t.status == "waiting_approval"],
        "result_summary": mission.result,
        "mode": mode,
    }


def get_agent_activity(tx, agent_id: str, limit: int = 20) -> dict[str, Any]:
    """Return a real persisted digital work room for one agent."""
    events = tx.workforce_events.list(agent_id=agent_id, limit=limit, descending=True)
    tasks = tx.tasks.list(assigned_agent_id=agent_id, limit=200, descending=True)
    task_ids = {task.id for task in tasks}
    evidence = [item for item in tx.work_evidence.list(limit=500) if item.task_id in task_ids]
    artifacts = [item for item in tx.work_artifacts.list(limit=500) if item.task_id in task_ids]
    messages = [
        item
        for item in tx.agent_messages.list(limit=500)
        if item.from_agent_id == agent_id or item.to_agent_id == agent_id
    ]

    role = agent_id
    status = "active"
    try:
        ag = tx.agents.get(agent_id)
        role = ag.role
        status = ag.status
    except KeyError:
        role = agent_id

    active_states = {
        "queued",
        "planning",
        "running",
        "waiting_approval",
        "blocked",
        "review",
        "retrying",
    }
    active_tasks = [task for task in tasks if str(task.status) in active_states]
    live_status = "AVAILABLE" if status == "active" else status.upper()
    status_order = (
        ("BLOCKED", {"blocked"}),
        ("WAITING", {"waiting_approval"}),
        ("REVIEWING", {"review"}),
        ("WORKING", {"running", "retrying"}),
        ("PLANNING", {"planning", "queued"}),
    )
    for candidate, states in status_order:
        if any(str(task.status) in states for task in active_tasks):
            live_status = candidate
            break
    last_act = events[0].timestamp if events else (tasks[0].created_at if tasks else None)
    curr_act = events[0].safe_summary if events else "Verfügbar"

    return {
        "agent_id": agent_id,
        "role": role,
        "status": live_status,
        "current_activity": curr_act,
        "last_activity_at": last_act,
        "unread_event_count": sum(1 for event in events if event.read_at is None),
        "active_task_count": len(active_tasks),
        "tasks": tasks[:limit],
        "events": events[:limit],
        "artifacts": artifacts[-limit:],
        "messages": messages[-limit:],
        "recent_evidence": [
            {
                "id": e.id,
                "mission_id": e.mission_id,
                "task_id": e.task_id,
                "source_type": e.source_type,
                "evidence_type": e.evidence_type,
                "summary": e.summary,
                "artifact_ref": e.artifact_ref,
                "created_at": e.created_at,
            }
            for e in evidence[-limit:]
        ],
    }


def get_company_live_feed(tx, *, limit=50, offset=0, mission_id=None, unit_id=None):
    filters = {
        key: value
        for key, value in {"mission_id": mission_id, "unit_id": unit_id}.items()
        if value is not None
    }
    events = tx.workforce_events.list(limit=limit, offset=offset, descending=True, **filters)
    return {"events": events, "limit": limit, "offset": offset, "source": "persisted_runtime"}


def get_company_pulse(tx):
    tasks = tx.tasks.list(limit=1000)
    active = [
        task
        for task in tasks
        if str(task.status)
        in {"queued", "planning", "running", "waiting_approval", "blocked", "review", "retrying"}
    ]
    mission_ids = {task.mission_id for task in active}
    missions = tx.missions.list(limit=1000)
    approvals = tx.approvals.list(status="pending", limit=1000)
    events = tx.workforce_events.list(limit=1000)
    model_calls = [event for event in tx.audit.list(limit=1000) if event.event_type == "model_call"]
    local_providers = {"fake", "hufi-local-router", "ollama"}
    paid_calls = [
        event for event in model_calls if event.detail.get("provider") not in local_providers
    ]
    active_unit_ids = {
        event.unit_id for event in events if event.mission_id in mission_ids and event.unit_id
    }
    today = now().date()
    return {
        "active_areas": len(active_unit_ids),
        "completed_today": sum(
            1
            for mission in missions
            if str(mission.status) == "completed"
            and mission.completed_at
            and mission.completed_at.date() == today
        ),
        "blocked": sum(1 for task in active if str(task.status) == "blocked"),
        "needs_owner_decision": len(approvals),
        "p0_count": sum(1 for event in events if event.severity == "P0"),
        "external_model_cost": sum(float(event.detail.get("cost") or 0) for event in paid_calls),
        "paid_model_calls": len(paid_calls),
        "owner_instructions": len(missions),
        "owner_interventions": len(approvals),
        "tasks": len(tasks),
        "artifacts": len(tx.work_artifacts.list(limit=1000)),
        "evidence": len(tx.work_evidence.list(limit=1000)),
        "source": "persisted_records",
    }


def get_company_workforce(tx, limit=200):
    """Build the bounded sidebar/company state without per-agent queries."""
    agents = {agent.id: agent for agent in tx.agents.list(status="active", limit=limit)}
    tasks = tx.tasks.list(limit=1000, descending=True)
    events = tx.workforce_events.list(limit=1000, descending=True)
    relationships = tx.relationships.list(relationship_type="member_of_unit", limit=5000)
    units = {unit.id: unit for unit in tx.organization_units.list(status="active", limit=1000)}
    active_values = {
        "queued",
        "planning",
        "running",
        "waiting_approval",
        "blocked",
        "review",
        "retrying",
    }
    active_tasks = [task for task in tasks if str(task.status) in active_values]
    latest_by_agent = {}
    for event in events:
        if event.agent_id and event.agent_id not in latest_by_agent:
            latest_by_agent[event.agent_id] = event
    tasks_by_agent = {}
    for task in active_tasks:
        tasks_by_agent.setdefault(task.assigned_agent_id, []).append(task)
    unit_by_agent = {}
    for relationship in relationships:
        unit_by_agent.setdefault(relationship.source_id, []).append(relationship.target_id)

    workers = []
    for agent_id, agent in agents.items():
        own_tasks = tasks_by_agent.get(agent_id, [])
        states = {str(task.status) for task in own_tasks}
        live_state = "AVAILABLE"
        for candidate, matching in (
            ("BLOCKED", {"blocked"}),
            ("WAITING", {"waiting_approval"}),
            ("REVIEWING", {"review"}),
            ("WORKING", {"running", "retrying"}),
            ("PLANNING", {"planning", "queued"}),
        ):
            if states & matching:
                live_state = candidate
                break
        latest = latest_by_agent.get(agent_id)
        workers.append(
            {
                "agent_id": agent_id,
                "name": agent.name or agent_id,
                "role": agent.role,
                "live_state": live_state,
                "current_activity": latest.safe_summary if latest else "Verfügbar",
                "last_activity_at": latest.timestamp if latest else None,
                "unread_event_count": sum(
                    1 for event in events if event.agent_id == agent_id and event.read_at is None
                ),
                "active_task_count": len(own_tasks),
                "unit_ids": unit_by_agent.get(agent_id, []),
            }
        )

    areas = []
    for unit_id, unit in units.items():
        members = [worker for worker in workers if unit_id in worker["unit_ids"]]
        active_members = [worker for worker in members if worker["active_task_count"]]
        if members or unit.unit_type in {"BUSINESS_UNIT", "SHARED_SERVICE"}:
            areas.append(
                {
                    "unit_id": unit_id,
                    "name": unit.name,
                    "stable_key": unit.stable_key,
                    "status": "WORKING" if active_members else "AVAILABLE",
                    "active_agent_count": len(active_members),
                    "unread_event_count": sum(item["unread_event_count"] for item in members),
                }
            )
    return {"areas": areas, "workers": workers, "source": "persisted_runtime"}
