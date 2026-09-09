"""Integration tests — V1.3 Memory + Skills Runtime Reuse.

Golden Second-Mission test:
- Agent HM-SENTINEL, Project release-project
- Skill RELEASE_SKILL_SENTINEL_51172 injected into Mission 2 provider request
- Memory SECURITY_SENTINEL_84217 injected into Mission 2 provider request
- Unapproved, wrong-project, and raw secrets (memory-secret-999) are absent

All tests are self-contained: no external services, no LLM calls.
"""

from __future__ import annotations

import pytest

from hufiagents.config import Settings
from hufiagents.contracts import Agent, Risk, ScopedMemory, Skill
from hufiagents.knowledge import KnowledgeService
from hufiagents.orchestrator.engine import Orchestrator
from hufiagents.orchestrator.planner import MissionCreate
from hufiagents.persistence.repository import Store
from hufiagents.providers.base import CompletionRequest, CompletionResult, ProviderHealth


class CapturingProvider:
    """Provider stub that captures CompletionRequests without network calls."""

    def __init__(self, provider_id: str = "capturing"):
        self.id = provider_id
        self.captured_requests: list[CompletionRequest] = []

    async def health(self) -> ProviderHealth:
        return ProviderHealth(available=True, reason="ok")

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        self.captured_requests.append(request)
        return CompletionResult(
            text="Mission completed with approved knowledge context.", model="capturing-fake"
        )


def make_store_with_sentinel_agent(tmp_path, agent_id="HM-SENTINEL", project_id="release-project"):
    """Create a Store with the HM-SENTINEL agent provisioned."""
    store = Store(f"sqlite:///{tmp_path}/state.sqlite3")
    with store.transaction() as tx:
        tx.agents.add(
            Agent(
                id=agent_id,
                name="HM-SENTINEL Agent",
                role="builder",
                capabilities={
                    "providers": ["capturing"],
                    "tools": ["files"],
                    "skills": ["RELEASE_SKILL_SENTINEL_51172"],
                },
                risk_ceiling=Risk.R1,
                project_id=project_id,
                status="active",
            )
        )
        # Add builder fallback agent
        tx.agents.add(
            Agent(
                id="builder",
                role="builder",
                capabilities={"tools": ["files"], "providers": ["capturing"]},
                risk_ceiling=Risk.R1,
            )
        )
    return store


@pytest.mark.asyncio
async def test_golden_second_mission_reuse(tmp_path):
    """
    Golden Second-Mission Test:
    1. Seed knowledge: RELEASE_SKILL_SENTINEL_51172 (approved) +
       SECURITY_SENTINEL_84217 (approved, project=release-project).
    2. Seed negative fixtures: unapproved draft skill, wrong-project memory, raw secret memory.
    3. Submit Mission 2 as HM-SENTINEL agent on project release-project.
    4. Verify provider CompletionRequest context contains RELEASE_SKILL_SENTINEL_51172.
    5. Verify provider context contains SECURITY_SENTINEL_84217.
    6. Verify unapproved, wrong-project, and raw secret sentinels are absent.
    """
    store = make_store_with_sentinel_agent(tmp_path)
    knowledge = KnowledgeService(store)

    # Approved skill assigned to the agent
    knowledge.create_skill(
        Skill(
            name="RELEASE_SKILL_SENTINEL_51172",
            description="Production release security checks",
            steps=[{"action": "verify_build"}, {"action": "check_security_gates"}],
            status="approved",
        )
    )

    # Approved project memory — should appear in Mission 2
    knowledge.create_memory(
        ScopedMemory(
            scope_type="project",
            scope_id="release-project",
            category="fact",
            summary="Security Sentinel Policy",
            content="SECURITY_SENTINEL_84217: enforce TLS 1.3 in all release builds",
            status="approved",
        )
    )

    # NEGATIVE: Draft skill (should NOT appear)
    knowledge.create_skill(
        Skill(
            name="DRAFT_SKILL_SENTINEL_99999",
            description="Unverified draft skill",
            steps=[{"action": "unverified"}],
            status="draft",
        )
    )

    # NEGATIVE: Wrong-project approved memory (should NOT appear)
    knowledge.create_memory(
        ScopedMemory(
            scope_type="project",
            scope_id="wrong-project-xyz",
            category="fact",
            summary="Wrong Project Memory",
            content="WRONG_PROJECT_SENTINEL_11111: irrelevant rule",
            status="approved",
        )
    )

    # NEGATIVE: Raw secret memory — redacted upon storage
    knowledge.create_memory(
        ScopedMemory(
            scope_type="project",
            scope_id="release-project",
            category="fact",
            summary="Secret Config",
            content="DB_PASSWORD=memory-secret-999",
            status="approved",
        )
    )

    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/state.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="capturing",
    )
    capturing_provider = CapturingProvider()
    engine = Orchestrator(store, settings, {"capturing": capturing_provider})

    # Submit Mission 2 with project context
    request = MissionCreate(
        outcome="Perform release security review for release-project",
    )
    mission = engine.submit(request)

    with store.transaction() as tx:
        tasks = tx.tasks.list(mission_id=mission.id)
        assert len(tasks) >= 1
        task = tasks[0]
        # Override the agent assignment to HM-SENTINEL
        task.assigned_agent_id = "HM-SENTINEL"
        task.project_id = "release-project"
        tx.tasks.save(task)
        task_id = task.id

    await engine.run(task_id)

    assert len(capturing_provider.captured_requests) >= 1
    comp_req = capturing_provider.captured_requests[0]

    ctx_str = comp_req.context

    # POSITIVE: Approved skill and memory must be present
    assert "RELEASE_SKILL_SENTINEL_51172" in ctx_str, (
        "Expected RELEASE_SKILL_SENTINEL_51172 in context"
    )
    assert "SECURITY_SENTINEL_84217" in ctx_str, "Expected SECURITY_SENTINEL_84217 in context"

    # NEGATIVE: Draft skill must NOT appear
    assert "DRAFT_SKILL_SENTINEL_99999" not in ctx_str, "Draft skill must not appear in context"

    # NEGATIVE: Wrong-project memory must NOT appear
    assert "WRONG_PROJECT_SENTINEL_11111" not in ctx_str, (
        "Wrong-project memory must not appear in context"
    )

    # NEGATIVE: Raw secret must NOT appear
    assert "memory-secret-999" not in ctx_str, "Raw secret must not appear in context"

    store.close()


@pytest.mark.asyncio
async def test_knowledge_context_audit_event_logged(tmp_path):
    """knowledge_context_prepared audit event is logged when approved memories/skills are found."""
    store = make_store_with_sentinel_agent(tmp_path)
    knowledge = KnowledgeService(store)

    knowledge.create_memory(
        ScopedMemory(
            scope_type="project",
            scope_id="release-project",
            category="fact",
            summary="Release fact",
            content="AUDIT_SENTINEL_55555: record this fact",
            status="approved",
        )
    )

    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/state.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="capturing",
    )
    capturing_provider = CapturingProvider()
    engine = Orchestrator(store, settings, {"capturing": capturing_provider})

    request = MissionCreate(
        outcome="AUDIT_SENTINEL_55555 release fact review",
    )
    mission = engine.submit(request)

    with store.transaction() as tx:
        tasks = tx.tasks.list(mission_id=mission.id)
        task = tasks[0]
        task.assigned_agent_id = "HM-SENTINEL"
        task.project_id = "release-project"
        tx.tasks.save(task)
        task_id = task.id

    await engine.run(task_id)

    with store.transaction() as tx:
        audit_events = tx.audit.list(event_type="knowledge_context_prepared")
        assert len(audit_events) >= 1
        evt = audit_events[0]
        assert evt.detail.get("memory_count", 0) >= 1

    store.close()


@pytest.mark.asyncio
async def test_truthful_work_evidence_generated(tmp_path):
    """WorkEvidence REUSED record is generated for knowledge_context_prepared event."""
    store = make_store_with_sentinel_agent(tmp_path)
    knowledge = KnowledgeService(store)

    knowledge.create_memory(
        ScopedMemory(
            scope_type="project",
            scope_id="release-project",
            category="fact",
            summary="Evidence Sentinel",
            content="EVIDENCE_SENTINEL_66666: truthful evidence",
            status="approved",
        )
    )

    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/state.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="capturing",
    )
    capturing_provider = CapturingProvider()
    engine = Orchestrator(store, settings, {"capturing": capturing_provider})

    request = MissionCreate(
        outcome="EVIDENCE_SENTINEL_66666 release review",
    )
    mission = engine.submit(request)

    with store.transaction() as tx:
        tasks = tx.tasks.list(mission_id=mission.id)
        task = tasks[0]
        task.assigned_agent_id = "HM-SENTINEL"
        task.project_id = "release-project"
        tx.tasks.save(task)
        task_id = task.id

    await engine.run(task_id)

    with store.transaction() as tx:
        evidence_list = tx.work_evidence.list(mission_id=mission.id, limit=100)
        reused_evidence = [e for e in evidence_list if e.evidence_type == "REUSED"]
        assert len(reused_evidence) >= 1
        ev = reused_evidence[0]
        assert ev.source_type == "KNOWLEDGE"
        s = ev.summary.lower()
        assert "wiederverwendet" in s or "skill" in s or "wissen" in s

    store.close()


@pytest.mark.asyncio
async def test_repo_context_and_memory_compose_without_clobbering(tmp_path):
    """Repository context and approved memory can coexist in a single model context."""
    store = make_store_with_sentinel_agent(tmp_path)
    knowledge = KnowledgeService(store)

    knowledge.create_memory(
        ScopedMemory(
            scope_type="project",
            scope_id="release-project",
            category="fact",
            summary="Composition Sentinel",
            content="COMPOSITION_SENTINEL_77777: coexist with repo",
            status="approved",
        )
    )

    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/state.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="capturing",
    )
    capturing_provider = CapturingProvider()
    engine = Orchestrator(store, settings, {"capturing": capturing_provider})

    request = MissionCreate(
        outcome="COMPOSITION_SENTINEL_77777 release file analysis",
    )
    mission = engine.submit(request)

    # Create a minimal repo file in workspace
    ws_dir = settings.workspace_root / mission.id
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "release_check.py").write_text(
        "def check_release():\n    COMPOSITION_SENTINEL_77777 = True\n    return True\n",
        encoding="utf-8",
    )

    with store.transaction() as tx:
        tasks = tx.tasks.list(mission_id=mission.id)
        task = tasks[0]
        task.assigned_agent_id = "HM-SENTINEL"
        task.project_id = "release-project"
        tx.tasks.save(task)
        task_id = task.id

    await engine.run(task_id)

    assert len(capturing_provider.captured_requests) >= 1
    ctx_str = capturing_provider.captured_requests[0].context

    # Both memory and (optionally) repo context contribute to the context
    assert "COMPOSITION_SENTINEL_77777" in ctx_str

    store.close()


@pytest.mark.asyncio
async def test_no_memory_for_different_project(tmp_path):
    """Agent on project-A cannot access memory scoped to project-B."""
    store = Store(f"sqlite:///{tmp_path}/state.sqlite3")
    knowledge = KnowledgeService(store)

    # Setup agents
    with store.transaction() as tx:
        tx.agents.add(
            Agent(
                id="agent-project-a",
                role="builder",
                capabilities={"tools": ["files"], "providers": ["capturing"]},
                risk_ceiling=Risk.R1,
                project_id="project-a",
                status="active",
            )
        )
        tx.agents.add(
            Agent(
                id="builder",
                role="builder",
                capabilities={"tools": ["files"], "providers": ["capturing"]},
                risk_ceiling=Risk.R1,
            )
        )

    # Memory scoped to project-B only
    knowledge.create_memory(
        ScopedMemory(
            scope_type="project",
            scope_id="project-b",
            category="fact",
            summary="Project B Secret",
            content="PROJECT_B_SENTINEL_88888: only for B",
            status="approved",
        )
    )

    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/state.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="capturing",
    )
    capturing_provider = CapturingProvider()
    engine = Orchestrator(store, settings, {"capturing": capturing_provider})

    request = MissionCreate(
        outcome="PROJECT_B_SENTINEL_88888 analysis for project-a",
    )
    mission = engine.submit(request)

    with store.transaction() as tx:
        tasks = tx.tasks.list(mission_id=mission.id)
        task = tasks[0]
        task.assigned_agent_id = "agent-project-a"
        task.project_id = "project-a"
        tx.tasks.save(task)
        task_id = task.id

    await engine.run(task_id)

    assert len(capturing_provider.captured_requests) >= 1
    ctx_str = capturing_provider.captured_requests[0].context
    # Memory from project-B must NOT leak into project-A mission
    assert "PROJECT_B_SENTINEL_88888: only for B" not in ctx_str

    store.close()
