import fcntl
import hmac
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from hufiagents import auth
from hufiagents.config import Settings
from hufiagents.orchestrator.engine import Orchestrator
from hufiagents.orchestrator.planner import MissionCreate
from hufiagents.persistence.repository import Store
from hufiagents.projects import ProjectRegistry

PUBLIC_PATHS = {"/health", "/login"}


class Resolution(BaseModel):
    note: str = Field("", max_length=2000)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=200)


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
            await engine.start()
            yield
        finally:
            if engine:
                await engine.stop()
            if store:
                store.close()
            if lock:
                lock.close()

    app = FastAPI(title="HufiAgents Core V1", lifespan=lifespan)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @app.middleware("http")
    async def request_boundary(request: Request, call_next):
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if request.headers.get("origin"):
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
        return Path(__file__).with_name("status.html").read_text()

    @app.post("/missions", status_code=202)
    async def create_mission(body: MissionCreate):
        return app.state.engine.submit(body)

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
    async def agents():
        with app.state.store.transaction() as tx:
            return tx.agents.list()

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

    @app.get("/reviews")
    async def reviews(task_id: str):
        with app.state.store.transaction() as tx:
            return tx.reviews.list(task_id=task_id)

    @app.get("/tool-calls")
    async def tool_calls(task_id: str):
        with app.state.store.transaction() as tx:
            return tx.tool_calls.list(task_id=task_id)

    return app
