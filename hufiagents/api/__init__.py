import fcntl
import hmac
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from hufiagents import auth
from hufiagents.api.org import router_for as org_router_for
from hufiagents.api.rooms import router_for as rooms_router_for
from hufiagents.browser import BrowserAutomationService
from hufiagents.config import Settings
from hufiagents.contracts import (
    Agent,
    AgentConnectorAccess,
    AgentMessage,
    AgentProvisioningRequest,
    MCPServerRegistration,
    MCPToolDefinition,
    Routine,
    ScopedMemory,
    Skill,
    WorkEvidence,
)
from hufiagents.evidence import get_agent_activity, get_mission_execution_feed
from hufiagents.knowledge import KnowledgeService
from hufiagents.mcp import MCPAdapter
from hufiagents.orchestrator.engine import Orchestrator
from hufiagents.orchestrator.planner import MissionCreate
from hufiagents.persistence.repository import Store
from hufiagents.projects import ProjectRegistry
from hufiagents.room_runtime import RoomMessageService
from hufiagents.routine_runtime import RoutineScheduler
from hufiagents.workforce.builder import WorkforceBuilder
from hufiagents.workforce.connectors import ConnectorRegistry
from hufiagents.workforce.routines import RoutineService
from hufiagents.workforce.sessions import SessionService
from hufiagents.workforce.team import HufManagerTeamMission

PUBLIC_PATHS = {"/health", "/login"}


class Resolution(BaseModel):
    note: str = Field("", max_length=2000)


class BrowserNavigateRequest(BaseModel):
    agent_id: str
    session_id: str
    url: str
    task_id: str | None = None
    mission_id: str | None = None


class BrowserScreenshotRequest(BaseModel):
    agent_id: str
    session_id: str
    label: str = "screenshot"
    task_id: str | None = None
    mission_id: str | None = None


class BrowserInteractRequest(BaseModel):
    agent_id: str
    session_id: str
    action: str
    selector: str = ""
    value: str = ""
    task_id: str | None = None
    mission_id: str | None = None


class SessionHandoffRequest(BaseModel):
    agent_id: str
    target_agent_id: str
    session_id: str
    task_id: str | None = None
    summary: str = "session handoff"


class MCPInvokeRequest(BaseModel):
    agent_id: str
    tool_name: str
    params: dict = Field(default_factory=dict)
    task_id: str | None = None
    mission_id: str | None = None


class ConnectorCheckRequest(BaseModel):
    agent_id: str
    connector_id: str
    capability: str
    mode: str = "read"
    required_scope: str | None = None


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=200)


class ContextRequest(BaseModel):
    intent: str = Field(min_length=1, max_length=16000)
    scopes: list[tuple[str, str | None]] = []
    max_memory_items: int = Field(10, ge=0, le=100)
    max_skill_items: int = Field(5, ge=0, le=100)
    max_context_chars: int = Field(12000, ge=100, le=100000)
    max_context_tokens_estimate: int = Field(3000, ge=50, le=25000)


class AgentCreate(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    name: str = Field("", max_length=200)
    role: str = Field(min_length=1, max_length=1000)
    description: str = Field("", max_length=8000)
    capabilities: dict = Field(default_factory=dict)
    parent_agent_id: str | None = None
    project_id: str | None = None
    risk_ceiling: str = "R1"
    model_preference: str | None = Field(None, max_length=200)
    memory_scope: str = Field("agent", max_length=200)
    workspace_id: str | None = Field(None, max_length=200)
    delegator_id: str | None = Field(None, max_length=200)


class AgentUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    role: str | None = Field(None, min_length=1, max_length=1000)
    description: str | None = Field(None, max_length=8000)
    project_id: str | None = Field(None, max_length=200)
    model_preference: str | None = Field(None, max_length=200)
    memory_scope: str | None = Field(None, max_length=200)
    workspace_id: str | None = Field(None, max_length=200)
    status: str | None = None


class MessageCreate(BaseModel):
    from_agent_id: str
    to_agent_id: str | None = None
    channel_id: str | None = None
    mission_id: str | None = None
    task_id: str | None = None
    content: str = Field(min_length=1, max_length=32000)
    correlation_id: str | None = None
    delegation_id: str | None = None


class DelegationCreate(BaseModel):
    parent_agent_id: str
    child_agent_id: str
    objective: str = Field(min_length=1, max_length=16000)
    mission_id: str | None = None
    task_id: str | None = None


class DelegationResult(BaseModel):
    agent_id: str
    result: str = Field(min_length=1, max_length=32000)
    failed: bool = False


class RoutineCreate(BaseModel):
    owner_agent_id: str
    project_id: str | None = None
    mission_template: dict
    schedule: str = Field(min_length=1, max_length=1000)
    timezone: str = Field(min_length=1, max_length=100)
    retry_policy: dict = Field(default_factory=lambda: {"max_attempts": 2})


class RoutineUpdate(BaseModel):
    mission_template: dict | None = None
    schedule: str | None = None
    timezone: str | None = None
    retry_policy: dict | None = None


def create_app(settings=None, providers=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        lock = None
        store = None
        engine = None
        try:
            if settings.database_url.startswith(
                "sqlite:///"
            ) and not settings.database_url.endswith(":memory:"):
                db = Path(settings.database_url.removeprefix("sqlite:///"))
                db.parent.mkdir(parents=True, exist_ok=True)
                lock = Path(str(db) + ".lock").open("a")
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            store = Store(settings.database_url)
            engine = Orchestrator(store, settings, providers)
            app.state.store, app.state.engine = store, engine
            room_svc = RoomMessageService(store, engine)
            app.state.room_message_service = room_svc
            engine.room_service = room_svc
            routine_svc = RoutineService(store, engine.submit)
            app.state.routine_service = routine_svc
            routine_scheduler = RoutineScheduler(
                routine_svc, settings.routine_poll_interval_seconds
            )
            app.state.routine_scheduler = routine_scheduler
            await engine.start()
            await routine_scheduler.start()
            yield
        finally:
            if "routine_scheduler" in locals() and routine_scheduler:
                await routine_scheduler.stop()
            if engine:
                await engine.stop()
            if store:
                store.close()
            if lock:
                lock.close()

    app = FastAPI(title="HufiAgents Core V1", lifespan=lifespan)
    app.state.store = Store(settings.database_url)
    app.include_router(org_router_for(app))
    app.include_router(rooms_router_for(app))
    allowed_hosts = ["127.0.0.1", "localhost", "testserver"]
    if settings.public_hostname:
        allowed_hosts.append(settings.public_hostname)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
    app.mount(
        "/static",
        StaticFiles(directory=Path(__file__).with_name("static")),
        name="static",
    )

    @app.middleware("http")
    async def request_boundary(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            origin = request.headers.get("origin")
            # A same-origin fetch()/XHR write also carries an Origin header in
            # modern browsers -- only a *mismatching* Origin is a real
            # cross-origin write attempt. Comparing hosts (not full origin
            # strings) tolerates the proxy terminating TLS: the browser's
            # Origin is https://<host>, this app only ever sees the plain
            # Host header nginx forwards.
            if origin and urlsplit(origin).netloc != request.headers.get("host", ""):
                return JSONResponse(
                    {"detail": "browser cross-origin writes are disabled"}, status_code=403
                )
            if (
                request.headers.get("content-length", "").isdigit()
                and int(request.headers["content-length"]) > 128000
            ):
                return JSONResponse({"detail": "request too large"}, status_code=413)
        return await call_next(request)

    # V1 login gate (hufiagents/auth.py, docs/DECISIONS.md ADR-015). A no-op
    # when auth isn't configured (settings.auth_enabled is False), which is
    # true for every existing test and for `fake`-provider local dev --
    # nothing about this middleware can regress a deployment that never opts
    # into it. /health always stays public so a load balancer/monitor never
    # needs credentials.
    @app.middleware("http")
    async def auth_gate(request: Request, call_next):
        if settings.auth_enabled and request.url.path not in PUBLIC_PATHS:
            session_cookie = request.cookies.get(auth.COOKIE_NAME)
            username = (
                auth.verify_session(session_cookie, settings.session_secret.get_secret_value())
                if session_cookie
                else None
            )
            if not username:
                if request.method == "GET" and "text/html" in request.headers.get("accept", ""):
                    return RedirectResponse("/login", status_code=303)
                return JSONResponse({"detail": "authentication required"}, status_code=401)
            request.state.username = username
        return await call_next(request)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": "resource not found"}, status_code=404)

    @app.exception_handler(ValueError)
    async def conflict(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(OverflowError)
    async def capacity(request, exc):
        return JSONResponse({"detail": "queue at capacity"}, status_code=429)

    @app.exception_handler(PermissionError)
    async def forbidden(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=403)

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "provider": settings.default_provider,
            "max_concurrent_tasks": settings.max_concurrent_tasks,
            "auth_enabled": settings.auth_enabled,
        }

    @app.get("/login", response_class=HTMLResponse)
    async def login_page():
        if not settings.auth_enabled:
            return RedirectResponse("/")
        return Path(__file__).with_name("login.html").read_text()

    @app.post("/login")
    async def login(body: LoginRequest, response: Response):
        if not settings.auth_enabled:
            raise HTTPException(404, "authentication not configured")
        valid = hmac.compare_digest(
            body.username, settings.admin_username
        ) and auth.verify_password(body.password, settings.admin_password_hash.get_secret_value())
        if not valid:
            raise HTTPException(401, "invalid credentials")
        token = auth.issue_session(
            settings.admin_username, settings.session_secret.get_secret_value()
        )
        response.set_cookie(
            auth.COOKIE_NAME,
            token,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="lax",
            max_age=auth.SESSION_TTL_SECONDS,
            path="/",
        )
        return {"status": "ok"}

    @app.post("/logout")
    async def logout(response: Response):
        response.delete_cookie(auth.COOKIE_NAME, path="/")
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    async def status():
        return Path(__file__).with_name("static").joinpath("index.html").read_text()

    @app.get("/legacy", response_class=HTMLResponse)
    async def legacy_status():
        # V1.0.1 admin-dashboard UI, kept reachable for expert/system fallback
        # during the V1.1 product-experience rollout (docs/HUFIAGENTS-PRODUCT-VISION.md).
        return Path(__file__).with_name("status.html").read_text()

    @app.post("/missions", status_code=202)
    async def create_mission(body: MissionCreate):
        return app.state.engine.submit(body)

    @app.post("/missions/hufmanager/team", status_code=202)
    async def hufmanager_team_mission():
        """Start the bounded, read-only HufManager sales-readiness benchmark."""
        return await HufManagerTeamMission(app.state.engine).run()

    @app.get("/missions")
    async def missions(limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0)):
        with app.state.store.transaction() as tx:
            return tx.missions.list(limit=limit, offset=offset)

    @app.get("/missions/{identifier}")
    async def mission(identifier: str):
        with app.state.store.transaction() as tx:
            return tx.missions.get(identifier)

    @app.get("/tasks")
    async def tasks(
        mission_id: str, limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0)
    ):
        with app.state.store.transaction() as tx:
            return tx.tasks.list(mission_id=mission_id, limit=limit, offset=offset)

    @app.get("/tasks/{identifier}")
    async def task(identifier: str):
        with app.state.store.transaction() as tx:
            return tx.tasks.get(identifier)

    @app.post("/tasks/{identifier}/cancel")
    async def cancel(identifier: str):
        await app.state.engine.cancel(identifier)
        return {"status": "cancelled"}

    @app.get("/agents")
    async def agents(status: str | None = None):
        return app.state.engine.workforce.list_agents(**({"status": status} if status else {}))

    @app.post("/agents", status_code=201)
    async def create_agent(body: AgentCreate, request: Request):
        data = body.model_dump(exclude={"delegator_id"})
        return app.state.engine.workforce.create_agent(
            Agent(**data, created_by=getattr(request.state, "username", "pascal")),
            delegator_id=body.delegator_id,
        )

    @app.get("/agents/{identifier}")
    async def agent(identifier: str):
        return app.state.engine.workforce.get_agent(identifier)

    @app.patch("/agents/{identifier}")
    async def update_agent(identifier: str, body: AgentUpdate, request: Request):
        return app.state.engine.workforce.update_agent(
            identifier,
            body.model_dump(exclude_none=True),
            actor=getattr(request.state, "username", "pascal"),
        )

    @app.post("/agents/{identifier}/archive")
    async def archive_agent(identifier: str, request: Request):
        return app.state.engine.workforce.archive_agent(
            identifier, actor=getattr(request.state, "username", "pascal")
        )

    @app.post("/agent-messages", status_code=201)
    async def send_agent_message(body: MessageCreate):
        return app.state.engine.workforce.send_message(AgentMessage(**body.model_dump()))

    @app.post("/agents/{identifier}/messages/receive")
    async def receive_agent_messages(identifier: str):
        return app.state.engine.workforce.receive_messages(identifier)

    @app.post("/delegations", status_code=201)
    async def delegate_task(body: DelegationCreate):
        return app.state.engine.workforce.delegate_task(**body.model_dump())

    @app.post("/delegations/{identifier}/result")
    async def receive_agent_result(identifier: str, body: DelegationResult):
        return app.state.engine.workforce.receive_agent_result(identifier, **body.model_dump())

    def routines_service():
        return getattr(
            app.state,
            "routine_service",
            RoutineService(app.state.store, app.state.engine.submit),
        )

    @app.get("/routines")
    async def routines(owner_agent_id: str | None = None):
        with app.state.store.transaction() as tx:
            return tx.routines.list(
                **({"owner_agent_id": owner_agent_id} if owner_agent_id else {})
            )

    @app.post("/routines", status_code=201)
    async def create_routine(body: RoutineCreate):
        return routines_service().create(Routine(**body.model_dump()))

    @app.post("/routines/runtime/tick")
    async def routines_runtime_tick():
        dispatched = routines_service().tick()
        return {"dispatched": dispatched, "count": len(dispatched)}

    @app.get("/routines/runtime/status")
    async def routines_runtime_status():
        scheduler = getattr(app.state, "routine_scheduler", None)
        if scheduler:
            return scheduler.status
        return {"running": False, "status": "no_scheduler"}

    @app.patch("/routines/{identifier}")
    async def update_routine(identifier: str, body: RoutineUpdate):
        return routines_service().update(identifier, **body.model_dump(exclude_none=True))

    @app.post("/routines/{identifier}/pause")
    async def pause_routine(identifier: str):
        return routines_service().pause(identifier)

    @app.post("/routines/{identifier}/resume")
    async def resume_routine(identifier: str):
        return routines_service().resume(identifier)

    @app.post("/routines/{identifier}/archive")
    async def archive_routine(identifier: str):
        return routines_service().archive(identifier)

    @app.get("/projects")
    async def projects():
        registry = ProjectRegistry(settings.projects_path)
        return [
            {
                "id": project.id,
                "repo_url": project.repo_url,
                "github_repo": project.github_repo,
                "default_branch": project.default_branch,
                "allowed": project.allowed,
                "has_test": bool(project.test_command),
                "has_build": bool(project.build_command),
                "has_lint": bool(project.lint_command),
            }
            for project in registry.projects.values()
        ]

    @app.get("/models")
    async def models():
        provider_health = []
        for provider_id, provider in app.state.engine.providers.items():
            health = await provider.health()
            provider_health.append(
                {
                    "provider": provider_id,
                    "selected": provider_id == settings.default_provider,
                    "healthy": health.available,
                    "reason": health.reason,
                    "model": getattr(provider, "model", None),
                }
            )
        router = None
        default = app.state.engine.providers.get(settings.default_provider)
        base_url = getattr(default, "base_url", None)
        if base_url:
            try:
                async with httpx.AsyncClient(trust_env=False, timeout=5) as client:
                    models_response = await client.get(base_url + "/models")
                    models_response.raise_for_status()
                    status_response = await client.get(
                        base_url.removesuffix("/v1") + "/router/status"
                    )
                    status_response.raise_for_status()
                    router = {
                        "base_url": base_url,
                        "models": [m["id"] for m in models_response.json().get("data", [])],
                        "status": status_response.json(),
                    }
            except (httpx.HTTPError, ValueError):
                router = {"base_url": base_url, "error": "router unreachable"}
        return {
            "default_provider": settings.default_provider,
            "providers": provider_health,
            "router": router,
        }

    @app.get("/approvals")
    async def approvals(limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0)):
        with app.state.store.transaction() as tx:
            return tx.approvals.list(limit=limit, offset=offset)

    def resolve(request, identifier, body, authorization, status):
        # A logged-in session (docs/DECISIONS.md ADR-015) already proves this
        # is Pascal, via the browser UI -- it satisfies the same owner-only
        # bar the separate Bearer approval_token exists for, without making
        # the UI hold a second secret. approval_token remains the only path
        # when web auth isn't configured (existing tests, script/API use).
        if settings.auth_enabled and getattr(request.state, "username", None):
            app.state.engine.resolve(identifier, status, body.note)
            return {"status": status}
        token = settings.approval_token.get_secret_value()
        if not token:
            raise HTTPException(503, "approval resolution disabled; configure owner token")
        if not hmac.compare_digest(authorization or "", f"Bearer {token}"):
            raise HTTPException(401, "owner approval token required")
        app.state.engine.resolve(identifier, status, body.note)
        return {"status": status}

    @app.post("/approvals/{identifier}/approve")
    async def approve(
        request: Request,
        identifier: str,
        body: Resolution,
        authorization: str | None = Header(None),
    ):
        return resolve(request, identifier, body, authorization, "approved")

    @app.post("/approvals/{identifier}/deny")
    async def deny(
        request: Request,
        identifier: str,
        body: Resolution,
        authorization: str | None = Header(None),
    ):
        return resolve(request, identifier, body, authorization, "denied")

    @app.get("/audit")
    async def audit(
        mission_id: str, limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0)
    ):
        with app.state.store.transaction() as tx:
            return tx.audit.list(mission_id=mission_id, limit=limit, offset=offset)

    @app.post("/work-evidence", status_code=201)
    async def create_work_evidence(body: WorkEvidence):
        """Persist sanitized, typed proof of work and its audit marker."""
        with app.state.store.transaction() as tx:
            if body.mission_id:
                tx.missions.get(body.mission_id)
            if body.task_id:
                task = tx.tasks.get(body.task_id)
                if body.mission_id and task.mission_id != body.mission_id:
                    raise ValueError("task does not belong to mission")
            evidence = tx.work_evidence.add(body)
            tx.log(
                "work_evidence_created",
                mission_id=evidence.mission_id,
                task_id=evidence.task_id,
                evidence_id=evidence.id,
                source_type=evidence.source_type,
                evidence_type=evidence.evidence_type,
            )
            tx.log(
                "work_evidence_redacted",
                mission_id=evidence.mission_id,
                task_id=evidence.task_id,
                evidence_id=evidence.id,
            )
            return evidence

    @app.get("/work-evidence")
    async def work_evidence(
        mission_id: str | None = None,
        task_id: str | None = None,
        source_type: str | None = None,
        limit: int = Query(100, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        filters = {
            key: value
            for key, value in {
                "mission_id": mission_id,
                "task_id": task_id,
                "source_type": source_type,
            }.items()
            if value is not None
        }
        with app.state.store.transaction() as tx:
            return tx.work_evidence.list(limit=limit, offset=offset, **filters)

    @app.get("/work-evidence/{identifier}")
    async def work_evidence_item(identifier: str):
        with app.state.store.transaction() as tx:
            return tx.work_evidence.get(identifier)

    @app.get("/missions/{mission_id}/execution")
    async def mission_execution_feed(
        request: Request,
        mission_id: str,
        mode: Literal["simple", "transparent", "live"] = "transparent",
        limit: int = Query(50, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        with request.app.state.store.transaction() as tx:
            return get_mission_execution_feed(tx, mission_id, mode=mode, limit=limit, offset=offset)

    @app.get("/agents/{agent_id}/activity")
    async def agent_activity_feed(
        request: Request,
        agent_id: str,
        limit: int = Query(20, ge=1, le=100),
    ):
        with request.app.state.store.transaction() as tx:
            return get_agent_activity(tx, agent_id, limit=limit)

    @app.get("/reviews")
    async def reviews(task_id: str):
        with app.state.store.transaction() as tx:
            return tx.reviews.list(task_id=task_id)

    @app.get("/tool-calls")
    async def tool_calls(task_id: str):
        with app.state.store.transaction() as tx:
            return tx.tool_calls.list(task_id=task_id)

    @app.get("/skills")
    async def skills(status: str | None = None, limit: int = Query(100, ge=1, le=500)):
        with app.state.store.transaction() as tx:
            return (
                tx.skills.list(status=status, limit=limit)
                if status
                else tx.skills.list(limit=limit)
            )

    @app.post("/skills", status_code=201)
    async def create_skill(body: Skill):
        return KnowledgeService(app.state.store).create_skill(body, actor="pascal")

    @app.get("/memories")
    async def memories(
        scope_type: str | None = None,
        scope_id: str | None = None,
        limit: int = Query(100, ge=1, le=500),
    ):
        with app.state.store.transaction() as tx:
            filters = {
                k: v
                for k, v in {"scope_type": scope_type, "scope_id": scope_id}.items()
                if v is not None
            }
            return tx.scoped_memories.list(limit=limit, **filters)

    @app.post("/memories", status_code=201)
    async def create_memory(body: ScopedMemory):
        return KnowledgeService(app.state.store).create_memory(body, actor="pascal")

    @app.post("/context/assemble")
    async def assemble_context(body: ContextRequest):
        return KnowledgeService(app.state.store).assemble_context(
            body.intent,
            scopes=body.scopes,
            max_memory_items=body.max_memory_items,
            max_skill_items=body.max_skill_items,
            max_context_chars=body.max_context_chars,
            max_context_tokens_estimate=body.max_context_tokens_estimate,
        )

    @app.get("/work-summary")
    async def work_summary(
        project_id: str | None = None,
        team_id: str | None = None,
        agent_id: str | None = None,
        limit: int = Query(100, ge=1, le=1000),
    ):
        """Bounded summary assembled only from persisted records; no ROI estimates."""
        with app.state.store.transaction() as tx:
            tasks = tx.tasks.list(limit=limit)
            if project_id:
                tasks = [task for task in tasks if task.project_id == project_id]
            if agent_id:
                tasks = [task for task in tasks if task.assigned_agent_id == agent_id]
            mission_ids = {task.mission_id for task in tasks}
            evidence = tx.work_evidence.list(limit=limit)
            evidence = [item for item in evidence if item.mission_id in mission_ids]
            reviews = tx.reviews.list(limit=limit)
            task_ids = {task.id for task in tasks}
            reviews = [review for review in reviews if review.task_id in task_ids]
            return {
                "completed_tasks": [task for task in tasks if str(task.status) == "completed"],
                "active_or_blocking_tasks": [
                    task
                    for task in tasks
                    if str(task.status) in {"running", "blocked", "waiting_approval"}
                ],
                "generated_artifacts": [
                    artifact
                    for task in tasks
                    for artifact in (task.result or "").splitlines()
                    if artifact
                ],
                "work_evidence_count": len(evidence),
                "reviews": reviews,
                "affected_projects": sorted({task.project_id for task in tasks if task.project_id}),
                "team_filter": team_id,
                "source": "persisted_records",
            }

    # -----------------------------------------------------------------------
    # Workforce Builder endpoints
    # -----------------------------------------------------------------------

    class ProfileUpdate(BaseModel):
        changes: dict = Field(default_factory=dict)
        actor: str = Field("system", max_length=200)
        summary: str = Field("", max_length=2000)

    @app.post("/workforce/provision", status_code=201)
    async def provision_agent(
        request: AgentProvisioningRequest,
        x_caller_agent_id: str = Header(default="system"),
    ):
        """Provision a new digital employee from a structured request.

        Enforces privilege isolation: provisioned agent capabilities and risk
        ceiling cannot exceed the caller's own ceiling.  Raw secret values are
        rejected at the boundary.
        """
        store = app.state.store

        # Resolve caller capabilities / ceiling from existing agent record, or
        # fall back to an empty / R0 context so callers cannot self-escalate.
        caller_caps: dict = {}
        from hufiagents.contracts import Risk

        caller_ceiling: Risk = Risk.R1
        try:
            with store.transaction() as tx:
                caller = tx.agents.get(x_caller_agent_id)
                caller_caps = caller.capabilities
                caller_ceiling = caller.risk_ceiling
        except KeyError:
            pass  # Unknown caller → empty caps, R1 default

        builder = WorkforceBuilder(store)
        try:
            agent = builder.provision(
                request,
                caller_capabilities=caller_caps,
                caller_risk_ceiling=caller_ceiling,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        return agent

    @app.patch("/workforce/agents/{agent_id}/profile")
    async def update_agent_profile(agent_id: str, body: ProfileUpdate):
        """Apply profile changes to an existing agent (immutable fields are protected)."""
        store = app.state.store
        builder = WorkforceBuilder(store)
        try:
            agent = builder.update_profile(
                agent_id,
                body.changes,
                actor=body.actor,
                summary=body.summary,
            )
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found.") from None
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        return agent

    @app.get("/workforce/agents/{agent_id}/profile-history")
    async def get_agent_profile_history(agent_id: str):
        """Return the full profile version history for an agent."""
        store = app.state.store
        builder = WorkforceBuilder(store)
        try:
            history = builder.get_profile_history(agent_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found.") from None
        return {"agent_id": agent_id, "history": history, "count": len(history)}

    def sessions_svc():
        return SessionService(app.state.store, settings.workspace_root)

    def browser_svc():
        return BrowserAutomationService(app.state.store, sessions_svc())

    def mcp_svc():
        return MCPAdapter(app.state.store)

    def connectors_svc():
        return ConnectorRegistry(app.state.store)

    @app.post("/sessions/computer/{identifier}/activate")
    async def activate_computer(identifier: str, agent_id: str):
        return sessions_svc().activate_computer(agent_id, identifier)

    @app.post("/sessions/computer/{identifier}/snapshot")
    async def snapshot_computer(identifier: str, agent_id: str, snapshot_name: str | None = None):
        return sessions_svc().snapshot_computer(agent_id, identifier, snapshot_name)

    @app.post("/sessions/computer/{identifier}/reset")
    async def reset_computer(identifier: str, agent_id: str, snapshot_name: str | None = None):
        return sessions_svc().reset_computer(agent_id, identifier, snapshot_name)

    @app.post("/sessions/computer/{identifier}/recover")
    async def recover_computer(identifier: str, agent_id: str):
        return sessions_svc().recover_computer(agent_id, identifier)

    @app.post("/sessions/computer/{identifier}/handoff")
    async def handoff_computer(identifier: str, body: SessionHandoffRequest):
        return sessions_svc().handoff_computer(
            body.agent_id,
            body.target_agent_id,
            identifier,
            task_id=body.task_id,
            summary=body.summary,
        )

    @app.post("/sessions/browser/{identifier}/activate")
    async def activate_browser(identifier: str, agent_id: str):
        return sessions_svc().activate_browser(agent_id, identifier)

    @app.post("/sessions/browser/{identifier}/snapshot")
    async def snapshot_browser(identifier: str, agent_id: str, snapshot_name: str | None = None):
        return sessions_svc().snapshot_browser(agent_id, identifier, snapshot_name)

    @app.post("/sessions/browser/{identifier}/reset")
    async def reset_browser(identifier: str, agent_id: str, snapshot_name: str | None = None):
        return sessions_svc().reset_browser(agent_id, identifier, snapshot_name)

    @app.post("/sessions/browser/{identifier}/recover")
    async def recover_browser(identifier: str, agent_id: str):
        return sessions_svc().recover_browser(agent_id, identifier)

    @app.post("/sessions/browser/{identifier}/handoff")
    async def handoff_browser(identifier: str, body: SessionHandoffRequest):
        return sessions_svc().handoff_browser(
            body.agent_id,
            body.target_agent_id,
            identifier,
            task_id=body.task_id,
            summary=body.summary,
        )

    @app.post("/browser/navigate", status_code=201)
    async def browser_navigate(body: BrowserNavigateRequest):
        return browser_svc().navigate(
            body.agent_id,
            body.session_id,
            body.url,
            task_id=body.task_id,
            mission_id=body.mission_id,
        )

    @app.post("/browser/screenshot", status_code=201)
    async def browser_screenshot(body: BrowserScreenshotRequest):
        return browser_svc().take_screenshot(
            body.agent_id,
            body.session_id,
            body.label,
            task_id=body.task_id,
            mission_id=body.mission_id,
        )

    @app.post("/browser/interact", status_code=201)
    async def browser_interact(body: BrowserInteractRequest):
        return browser_svc().interact(
            body.agent_id,
            body.session_id,
            body.action,
            body.selector,
            body.value,
            task_id=body.task_id,
            mission_id=body.mission_id,
        )

    @app.post("/mcp/servers", status_code=201)
    async def register_mcp_server(body: MCPServerRegistration):
        return mcp_svc().register_server(body)

    @app.get("/mcp/servers")
    async def list_mcp_servers():
        with app.state.store.transaction() as tx:
            return tx.mcp_servers.list()

    @app.post("/mcp/tools", status_code=201)
    async def register_mcp_tool(body: MCPToolDefinition):
        return mcp_svc().register_tool(body)

    @app.get("/mcp/tools")
    async def list_mcp_tools(server_id: str | None = None):
        with app.state.store.transaction() as tx:
            return tx.mcp_tools.list(**({"server_id": server_id} if server_id else {}))

    @app.post("/mcp/invoke", status_code=201)
    async def invoke_mcp_tool(body: MCPInvokeRequest):
        return mcp_svc().invoke_tool(
            body.agent_id,
            body.tool_name,
            body.params,
            task_id=body.task_id,
            mission_id=body.mission_id,
        )

    @app.post("/connectors/grant", status_code=201)
    async def grant_connector_access(body: AgentConnectorAccess):
        return connectors_svc().grant(body)

    @app.post("/connectors/check")
    async def check_connector_access(body: ConnectorCheckRequest):
        allowed = connectors_svc().check_access(
            body.agent_id,
            body.connector_id,
            body.capability,
            mode=body.mode,
            required_scope=body.required_scope,
        )
        return {"status": "ok", "allowed": allowed}

    return app
