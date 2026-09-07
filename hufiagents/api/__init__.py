import fcntl
import hmac
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from hufiagents.config import Settings
from hufiagents.orchestrator.engine import Orchestrator
from hufiagents.orchestrator.planner import MissionCreate
from hufiagents.persistence.repository import Store


class Resolution(BaseModel):
    note: str = Field("", max_length=2000)


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
        }

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

    @app.get("/approvals")
    async def approvals(limit: int = Query(100, ge=1, le=100), offset: int = Query(0, ge=0)):
        with app.state.store.transaction() as tx:
            return tx.approvals.list(limit=limit, offset=offset)

    def resolve(identifier, body, authorization, status):
        token = settings.approval_token.get_secret_value()
        if not token:
            raise HTTPException(503, "approval resolution disabled; configure owner token")
        if not hmac.compare_digest(authorization or "", f"Bearer {token}"):
            raise HTTPException(401, "owner approval token required")
        app.state.engine.resolve(identifier, status, body.note)
        return {"status": status}

    @app.post("/approvals/{identifier}/approve")
    async def approve(identifier: str, body: Resolution, authorization: str | None = Header(None)):
        return resolve(identifier, body, authorization, "approved")

    @app.post("/approvals/{identifier}/deny")
    async def deny(identifier: str, body: Resolution, authorization: str | None = Header(None)):
        return resolve(identifier, body, authorization, "denied")

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
