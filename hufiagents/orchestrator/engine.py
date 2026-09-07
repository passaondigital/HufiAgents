import asyncio
import contextlib
import json
from datetime import timedelta

from hufiagents.contracts import Handoff, MemoryRecord, State, now
from hufiagents.orchestrator.planner import Planner
from hufiagents.orchestrator.registry import AgentRegistry
from hufiagents.orchestrator.reviewer import Reviewer
from hufiagents.orchestrator.state import TERMINAL
from hufiagents.projects import ProjectRegistry
from hufiagents.providers.base import CompletionRequest
from hufiagents.providers.fake import FakeProvider
from hufiagents.providers.hufi_local_router import HufiLocalRouter
from hufiagents.providers.ollama import OllamaProvider
from hufiagents.providers.router import select_provider
from hufiagents.redaction import redact
from hufiagents.risk import Policy
from hufiagents.tools.files import FilesTool
from hufiagents.tools.gateway import ApprovalPending, ToolGateway
from hufiagents.tools.git import GitTool
from hufiagents.tools.github import GitHubTool
from hufiagents.tools.shell import ShellTool
from hufiagents.tools.workspace import Workspace


class Orchestrator:
    def __init__(self, store, settings, providers=None):
        self.store, self.settings = store, settings
        self.registry = AgentRegistry(store)
        self.registry.seed()
        self.projects = ProjectRegistry(settings.projects_path)
        self.providers = providers or {
            "fake": FakeProvider(),
            "hufi-local-router": HufiLocalRouter(
                settings.local_router_base_url, settings.local_model, settings.model_timeout_seconds
            ),
            "ollama": OllamaProvider(
                settings.ollama_base_url, settings.ollama_model, settings.model_timeout_seconds
            ),
        }
        self.planner, self.reviewer = Planner(), Reviewer()
        self.gateway = ToolGateway(store, Policy(settings.risk_policy_path))
        self.active = {}
        self.semaphore = asyncio.Semaphore(settings.max_concurrent_tasks)
        self.stopping = False
        self.loop_task = None

    def submit(self, request):
        mission, tasks = self.planner.plan(request)
        # Validate paths and any explicit agent request before persisting or
        # dispatching a task, so a bad request fails at submit time (409) and
        # never reaches a background executor.
        for task, _ in tasks:
            if not task.expected_output or task.expected_output.startswith("/"):
                raise ValueError("expected_output must be a relative artifact path")
            if any(p in {"..", ".git", ".env", ".ssh"} for p in task.expected_output.split("/")):
                raise ValueError("unsafe artifact path")
            if task.assigned_agent_id is not None:
                self.registry.get(task.assigned_agent_id)
            if task.project_id is not None:
                self.projects.get(task.project_id)
        with self.store.transaction() as tx:
            pending = tx.tasks.list(
                status=set(State) - TERMINAL, limit=self.settings.max_pending_tasks
            )
            if len(pending) + len(tasks) > self.settings.max_pending_tasks:
                raise OverflowError("task queue at capacity")
            tx.missions.add(mission)
            tx.log("mission_created", mission_id=mission.id)
            for task, operations in tasks:
                tx.tasks.add(task)
                tx.task_context.add(
                    MemoryRecord(
                        owner_id=task.id,
                        key="operations",
                        value={"items": [operation.model_dump() for operation in operations]},
                    )
                )
                tx.log("task_created", task=task, dependencies=task.dependencies)
                if task.project_id:
                    project = self.projects.get(task.project_id)
                    tx.log(
                        "project_bound",
                        task=task,
                        project_id=project.id,
                        repo_url=project.repo_url,
                        github_repo=project.github_repo,
                        default_branch=project.default_branch,
                        dry_run=task.dry_run,
                    )
        return mission

    async def start(self):
        self.recover()
        self.loop_task = asyncio.create_task(self._loop())

    async def stop(self):
        self.stopping = True
        if self.loop_task:
            self.loop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.loop_task
        pending = list(self.active.values())
        for runner in pending:
            runner.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    async def _loop(self):
        while not self.stopping:
            self.recover()
            await self.tick()
            await asyncio.sleep(self.settings.poll_interval_seconds)

    async def tick(self):
        for identifier, runner in list(self.active.items()):
            if runner.done():
                if not runner.cancelled() and runner.exception():
                    with self.store.transaction() as tx:
                        tx.log(
                            "executor_error",
                            task=tx.tasks.get(identifier),
                            error=type(runner.exception()).__name__,
                        )
                self.active.pop(identifier)
        with self.store.transaction() as tx:
            tasks = tx.tasks.list(
                status=[State.queued, State.blocked, State.review, State.running],
                limit=self.settings.max_pending_tasks,
            )
            for task in tasks:
                if task.id in self.active:
                    continue
                if task.status in {State.queued, State.blocked}:
                    deps = [tx.tasks.get(identifier).status for identifier in task.dependencies]
                    if any(state in {State.failed, State.cancelled} for state in deps):
                        tx.transition(
                            task, State.cancelled, cancel=True, reason="dependency failed"
                        )
                        continue
                    if any(state != State.completed for state in deps):
                        if task.status == State.queued:
                            tx.transition(task, State.planning)
                            tx.transition(task, State.blocked, reason="dependency not complete")
                        continue
                    if task.status == State.blocked:
                        tx.transition(task, State.queued, reason="dependency complete")
                if task.status == State.running:
                    approvals = tx.approvals.list(status="approved", limit=10000)
                    if not any(
                        a.tool_call_id and tx.tool_calls.get(a.tool_call_id).task_id == task.id
                        for a in approvals
                    ):
                        continue  # orphan running tasks are owned by the stale reaper
                if len(self.active) >= self.settings.max_concurrent_tasks:
                    break
                self.active[task.id] = asyncio.create_task(self.run(task.id))

    async def _heartbeat(self, identifier):
        while True:
            await asyncio.sleep(self.settings.heartbeat_interval_seconds)
            with self.store.transaction() as tx:
                task = tx.tasks.get(identifier)
                if task.status in {State.planning, State.running, State.review}:
                    task.heartbeat_at = now()
                    tx.tasks.save(task)

    async def run(self, identifier):
        async with self.semaphore:
            heartbeat = asyncio.create_task(self._heartbeat(identifier))
            try:
                with self.store.transaction() as tx:
                    task = tx.tasks.get(identifier)
                    if task.status == State.queued:
                        tx.transition(task, State.planning)
                        task.assigned_agent_id = task.assigned_agent_id or "builder"
                        tx.tasks.save(task)
                        tx.log("agent_assigned", task=task, actor=task.assigned_agent_id)
                        tx.transition(task, State.running)
                async with asyncio.timeout(task.budget_seconds or 300):
                    await self._execute(identifier)
            except ApprovalPending:
                pass
            except asyncio.CancelledError:
                # Shutdown leaves a durable checkpoint for the stale reaper; explicit API
                # cancellation has already committed its terminal state before interrupting us.
                with self.store.transaction() as tx:
                    tx.log("executor_interrupted", task=tx.tasks.get(identifier))
                raise
            except Exception as exc:
                self._fail(identifier, exc)
            finally:
                heartbeat.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat

    async def _execute(self, identifier):
        with self.store.transaction() as tx:
            task = tx.tasks.get(identifier)
            contexts = tx.task_context.list(owner_id=identifier, limit=1000)
            reviews = tx.reviews.list(task_id=identifier, limit=100)
            revision = sum(review.verdict == "revise" for review in reviews)
        agent = self.registry.get(task.assigned_agent_id)
        workspace = Workspace(self.settings.workspace_root / task.mission_id)
        artifact = f"{task.id}/revision-{revision}/{task.expected_output}"
        if task.status != State.review:
            cached = [item for item in contexts if item.key == f"completion:{revision}"]
            if cached:
                text = cached[-1].value["text"]
            else:
                provider_id = task.preferred_provider or self.settings.default_provider
                provider = self.providers.get(provider_id)
                if provider is None:
                    raise PermissionError("unknown provider")
                health = await provider.health()
                choice = select_provider(
                    task, agent, {provider_id: health}, self.settings.default_provider
                )
                with self.store.transaction() as tx:
                    task = tx.tasks.get(identifier)
                    task.selected_provider, task.routing_reason = choice.provider_id, choice.reason
                    tx.tasks.save(task)
                    tx.log(
                        "model_call", task=task, provider=choice.provider_id, reason=choice.reason
                    )
                with self.store.transaction() as tx:
                    mission = tx.missions.get(task.mission_id)
                    dependency_results = [tx.tasks.get(dep).result for dep in task.dependencies]
                context = json.dumps(
                    redact(
                        {
                            "constraints": mission.constraints,
                            "dependency_results": dependency_results,
                            "review_findings": [r.findings for r in reviews],
                        }
                    )
                )
                request = CompletionRequest(
                    objective=task.objective, context=context, max_tokens=task.budget_tokens or 512
                )
                result = await asyncio.wait_for(
                    provider.complete(request), self.settings.model_timeout_seconds
                )
                text = redact(result.text)
                with self.store.transaction() as tx:
                    tx.task_context.add(
                        MemoryRecord(
                            owner_id=identifier,
                            key=f"completion:{revision}",
                            value={"text": text, "model": result.model},
                        )
                    )
                    tx.log(
                        "model_result",
                        task=task,
                        provider=choice.provider_id,
                        model=result.model,
                        tokens=result.tokens,
                        characters=len(text),
                    )
            tools = self.tools(workspace, task)
            operations = next(item.value["items"] for item in contexts if item.key == "operations")
            for operation in operations:
                tool = tools.get(operation["tool"])
                if tool is None:
                    raise PermissionError("unsupported tool")
                await self.gateway.invoke(
                    task, agent, tool, operation["action"], operation["target"], operation["params"]
                )
            await self.gateway.invoke(
                task, agent, tools["files"], "write_file", artifact, {"content": text}
            )
            with self.store.transaction() as tx:
                task = tx.tasks.get(identifier)
                task.result = text
                tx.tasks.save(task)
                tx.handoffs.add(
                    Handoff(
                        from_agent_id=agent.id,
                        to_agent_id="reviewer",
                        task_id=identifier,
                        summary="Review artifact against acceptance criteria",
                        artifacts=[artifact],
                    )
                )
                tx.transition(task, State.review)
        self.registry.get("reviewer")
        with self.store.transaction() as tx:
            task = tx.tasks.get(identifier)
            calls = tx.tool_calls.list(task_id=identifier, limit=1000)
            review = self.reviewer.review(task, workspace, artifact, calls)
            tx.reviews.add(review)
            tx.log(
                "review",
                task=task,
                actor="reviewer",
                verdict=review.verdict,
                findings=review.findings,
            )
            if review.verdict == "approve":
                tx.transition(task, State.completed)
            elif review.verdict == "revise" and task.retry_count < task.retry_limit:
                tx.task_context.add(
                    MemoryRecord(
                        owner_id=identifier,
                        key="review_findings",
                        value={"findings": review.findings},
                    )
                )
                tx.transition(task, State.retrying, reason="reviewer requested revision")
                tx.transition(task, State.queued)
            else:
                tx.transition(task, State.failed, reason="reviewer rejected or retries exhausted")

    def tools(self, workspace, task=None):
        project = self.projects.get(task.project_id) if task and task.project_id else None
        dry_run = bool(task and task.dry_run)
        return {
            "files": FilesTool(workspace),
            "shell": ShellTool(
                workspace,
                self.settings.tool_timeout_seconds,
                project=project,
                project_timeout=self.settings.project_tool_timeout_seconds,
            ),
            "git": GitTool(
                workspace,
                self.settings.tool_timeout_seconds,
                remote_url=self.settings.git_remote_url,
                project=project,
                dry_run=dry_run,
                clone_timeout=self.settings.project_tool_timeout_seconds,
            ),
            "github": GitHubTool(
                workspace,
                self.settings.tool_timeout_seconds,
                repo=project.github_repo if project else self.settings.github_repo,
                base_branch=project.default_branch if project else self.settings.github_base_branch,
                token=self.settings.github_token.get_secret_value(),
                dry_run=dry_run,
            ),
        }

    def _fail(self, identifier, exc):
        with self.store.transaction() as tx:
            task = tx.tasks.get(identifier)
            tx.log("error", task=task, error=type(exc).__name__)
            if task.status in TERMINAL:
                return
            retryable = not isinstance(exc, (PermissionError, ValueError, FileExistsError))
            if (
                task.status in {State.running, State.review}
                and retryable
                and task.retry_count < task.retry_limit
            ):
                tx.transition(task, State.retrying, reason=type(exc).__name__)
                tx.transition(task, State.queued)
            else:
                tx.transition(task, State.failed, reason=type(exc).__name__)

    def recover(self):
        cutoff = now() - timedelta(seconds=self.settings.heartbeat_timeout_seconds)
        with self.store.transaction() as tx:
            for task in tx.tasks.list(
                status=[State.planning, State.running, State.retrying],
                limit=self.settings.max_pending_tasks,
            ):
                if task.id in self.active:
                    continue
                if task.status == State.retrying:
                    tx.transition(task, State.queued, reason="resume retry checkpoint")
                elif (task.heartbeat_at or task.created_at) < cutoff:
                    tx.log("recovery", task=task, reason="stale heartbeat")
                    if task.retry_count < task.retry_limit:
                        tx.transition(task, State.retrying, recovery=True)
                        tx.transition(task, State.queued)
                    else:
                        tx.transition(task, State.failed, reason="recovery retries exhausted")
            for approval in tx.approvals.list(status="pending", limit=10000):
                if (
                    now() - approval.requested_at
                ).total_seconds() > self.settings.approval_timeout_seconds:
                    self._resolve(tx, approval, "expired", "system", "approval expired")

    def _resolve(self, tx, approval, status, actor, note):
        if approval.status != "pending":
            raise ValueError("approval already resolved")
        call = tx.tool_calls.get(approval.tool_call_id)
        task = tx.tasks.get(call.task_id)
        if task.status != State.waiting_approval:
            raise ValueError("task no longer waiting for this approval")
        approval.status, approval.resolved_at = status, now()
        approval.resolved_by, approval.resolution_note = actor, redact(note)
        tx.approvals.save(approval)
        tx.log("approval_resolved", task=task, actor=actor, approval_id=approval.id, status=status)
        target = {"approved": State.running, "denied": State.cancelled, "expired": State.failed}[
            status
        ]
        tx.transition(task, target, reason=f"approval {status}")

    def resolve(self, identifier, status, note=""):
        with self.store.transaction() as tx:
            self._resolve(tx, tx.approvals.get(identifier), status, "pascal", note)

    async def cancel(self, identifier):
        with self.store.transaction() as tx:
            task = tx.tasks.get(identifier)
            tx.transition(task, State.cancelled, cancel=True, reason="API cancellation")
            for approval in tx.approvals.list(status="pending", limit=10000):
                if (
                    approval.tool_call_id
                    and tx.tool_calls.get(approval.tool_call_id).task_id == identifier
                ):
                    approval.status, approval.resolved_at = "expired", now()
                    approval.resolved_by = "system"
                    tx.approvals.save(approval)
                    tx.log(
                        "approval_resolved", task=task, approval_id=approval.id, status="expired"
                    )
        runner = self.active.get(identifier)
        if runner:
            runner.cancel()
            await asyncio.gather(runner, return_exceptions=True)
