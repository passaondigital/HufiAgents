"""Integration tests for V1.3A Repository Context Runtime.

Covers:
- Golden Engineering Test: objective-driven repository context assembly, secret exclusion,
  and verification that actual source code reaches provider CompletionRequest context.
- Inline secret embedded in source code is redacted before provider request.
- Runtime handling when no repository exists or workspace is empty.
- Non-engineering task execution through Orchestrator bypasses repo context.
"""

import json

import pytest

from hufiagents.config import Settings
from hufiagents.contracts import Agent, Risk, State
from hufiagents.orchestrator.engine import Orchestrator
from hufiagents.orchestrator.planner import MissionCreate
from hufiagents.persistence.repository import Store
from hufiagents.providers.base import CompletionRequest, CompletionResult, ProviderHealth


class CapturingProvider:
    """Provider stub that captures the CompletionRequest context for assertion."""

    def __init__(self, provider_id: str = "capturing"):
        self.id = provider_id
        self.captured_requests: list[CompletionRequest] = []

    async def health(self) -> ProviderHealth:
        return ProviderHealth(available=True, reason="ok")

    async def complete(self, request: CompletionRequest) -> CompletionResult:
        self.captured_requests.append(request)
        return CompletionResult(
            text="Captured engineering analysis result.", model="capturing-fake"
        )


def make_store(tmp_path):
    store = Store(f"sqlite:///{tmp_path}/state.sqlite3")
    with store.transaction() as tx:
        tx.agents.add(
            Agent(
                id="builder",
                role="builder",
                capabilities={"tools": ["files"], "providers": ["capturing"]},
                risk_ceiling=Risk.R1,
            )
        )
        tx.agents.add(
            Agent(
                id="support",
                role="support",
                capabilities={"tools": ["chat"], "providers": ["capturing"]},
                risk_ceiling=Risk.R1,
            )
        )
    return store


@pytest.mark.asyncio
async def test_golden_engineering_repo_context(tmp_path):
    """
    Golden Engineering Test (Section 13):
    1. Create synthetic repo in workspace: src/auth.py, src/billing.py, tests/test_auth.py, .env
    2. Submit Mission through Orchestrator: 'Investigate the login session recovery problem.'
    3. Verify src/auth.py & tests/test_auth.py are included, billing.py not selected.
    4. Verify captured CompletionRequest context contains AUTH_SESSION_SENTINEL_47391.
    5. Verify captured CompletionRequest context does NOT contain repo_secret_999 from .env.
    """
    store = make_store(tmp_path)
    capturing_provider = CapturingProvider()
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/state.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="capturing",
    )
    engine = Orchestrator(store, settings, {"capturing": capturing_provider})

    # Create Mission
    request = MissionCreate(outcome="Investigate the login session recovery problem.")
    mission = engine.submit(request)

    # Populate synthetic workspace directory (workspace_root / mission.id)
    ws_dir = settings.workspace_root / mission.id
    (ws_dir / "src").mkdir(parents=True, exist_ok=True)
    (ws_dir / "tests").mkdir(parents=True, exist_ok=True)

    (ws_dir / "src" / "auth.py").write_text(
        "def recover_session():\n    AUTH_SESSION_SENTINEL_47391 = True\n    return True\n",
        encoding="utf-8",
    )
    (ws_dir / "src" / "billing.py").write_text(
        "def process_payment():\n    return False\n",
        encoding="utf-8",
    )
    (ws_dir / "tests" / "test_auth.py").write_text(
        "def test_session_recovery():\n    assert True\n",
        encoding="utf-8",
    )
    (ws_dir / ".env").write_text(
        "SUPER_SECRET_TOKEN=repo_secret_999\n",
        encoding="utf-8",
    )

    with store.transaction() as tx:
        tasks = tx.tasks.list(mission_id=mission.id)
        assert len(tasks) == 1
        task_id = tasks[0].id

    await engine.run(task_id)

    with store.transaction() as tx:
        completed_task = tx.tasks.get(task_id)
        assert completed_task.status == State.completed

    assert len(capturing_provider.captured_requests) == 1
    comp_req = capturing_provider.captured_requests[0]

    ctx_data = json.loads(comp_req.context)
    assert "repository_context" in ctx_data

    repo_ctx = ctx_data["repository_context"]
    selected_paths = [f["path"] for f in repo_ctx["selected_files"]]

    assert any("auth.py" in p for p in selected_paths)
    assert any("test_auth.py" in p for p in selected_paths)
    assert not any("billing.py" in p for p in selected_paths)
    assert not any(".env" in p for p in selected_paths)

    context_str = comp_req.context
    assert "AUTH_SESSION_SENTINEL_47391" in context_str
    assert "repo_secret_999" not in context_str

    store.close()


@pytest.mark.asyncio
async def test_embedded_secret_redacted_in_model_request(tmp_path):
    """Verify inline secret embedded in source is redacted before provider request."""
    store = make_store(tmp_path)
    capturing_provider = CapturingProvider()
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/state.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="capturing",
    )
    engine = Orchestrator(store, settings, {"capturing": capturing_provider})

    request = MissionCreate(outcome="Fix login auth token leakage bug")
    mission = engine.submit(request)

    ws_dir = settings.workspace_root / mission.id
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "auth.py").write_text(
        "TOKEN = 'secretval987654'\ndef login(): pass\n", encoding="utf-8"
    )

    with store.transaction() as tx:
        task_id = tx.tasks.list(mission_id=mission.id)[0].id

    await engine.run(task_id)

    assert len(capturing_provider.captured_requests) == 1
    comp_req = capturing_provider.captured_requests[0]
    assert "secretval987654" not in comp_req.context
    assert "[REDACTED]" in comp_req.context

    store.close()


@pytest.mark.asyncio
async def test_non_repository_task_executes_normally(tmp_path):
    """Tasks in empty workspaces run without repository_context."""
    store = make_store(tmp_path)
    capturing_provider = CapturingProvider()
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/state.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="capturing",
    )
    engine = Orchestrator(store, settings, {"capturing": capturing_provider})

    request = MissionCreate(outcome="General non-repo check")
    mission = engine.submit(request)

    with store.transaction() as tx:
        task_id = tx.tasks.list(mission_id=mission.id)[0].id

    await engine.run(task_id)

    assert len(capturing_provider.captured_requests) == 1
    ctx_data = json.loads(capturing_provider.captured_requests[0].context)
    assert "repository_context" not in ctx_data

    store.close()


@pytest.mark.asyncio
async def test_non_engineering_task_executes_normally(tmp_path):
    """Non-engineering tasks (support agent without file tools) skip repo context."""
    store = make_store(tmp_path)
    capturing_provider = CapturingProvider()
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/state.sqlite3",
        workspace_root=tmp_path / "workspaces",
        default_provider="capturing",
    )
    engine = Orchestrator(store, settings, {"capturing": capturing_provider})

    request = MissionCreate(outcome="General support chat response")
    mission = engine.submit(request)

    ws_dir = settings.workspace_root / mission.id
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "auth.py").write_text("def login(): pass\n", encoding="utf-8")

    with store.transaction() as tx:
        task = tx.tasks.list(mission_id=mission.id)[0]
        task.assigned_agent_id = "support"
        task.allowed_tools = ["chat"]
        tx.tasks.save(task)
        task_id = task.id

    await engine.run(task_id)

    assert len(capturing_provider.captured_requests) == 1
    ctx_data = json.loads(capturing_provider.captured_requests[0].context)
    assert "repository_context" not in ctx_data

    store.close()
