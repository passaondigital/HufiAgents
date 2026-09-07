"""Manual network probe: actual connector, real clone, disposable doc commit, NO push.

Run from repository root with: uv run python scripts/review_phase3a_hufmanager.py
Uses the deterministic provider to isolate tool/policy correctness from model availability.
"""

import asyncio
import json
import subprocess
import tempfile
from pathlib import Path

from hufiagents.config import Settings
from hufiagents.contracts import State, ToolCall
from hufiagents.orchestrator.engine import Orchestrator
from hufiagents.orchestrator.planner import MissionCreate, TaskSpec
from hufiagents.persistence.repository import Store
from hufiagents.providers.fake import FakeProvider
from hufiagents.tools.git import GitTool
from hufiagents.tools.workspace import Workspace


async def main():
    with tempfile.TemporaryDirectory(prefix="hufi-phase3a-review-") as temporary:
        root = Path(temporary)
        settings = Settings(
            database_url=f"sqlite:///{root}/review.sqlite3",
            workspace_root=root / "workspaces",
            default_provider="fake",
            github_token="",
            git_remote_url="",
            _env_file=None,
            project_tool_timeout_seconds=240,
        )
        store = Store(settings.database_url)
        engine = Orchestrator(store, settings, {"fake": FakeProvider()})
        mission = engine.submit(
            MissionCreate(
                outcome="Independent Phase 3A review",
                risk_ceiling="R2",
                steps=[
                    TaskSpec(
                        objective="Commit one disposable security review note",
                        agent_id="integrator",
                        project_id="hufmanager",
                        dry_run=True,
                        allowed_tools=["files", "git"],
                        expected_output="review-artifact.md",
                        operations=[
                            {"tool": "git", "action": "clone"},
                            {
                                "tool": "git",
                                "action": "branch",
                                "params": {"branch": "hufi/codex-auth-review"},
                            },
                            {
                                "tool": "files",
                                "action": "write_file",
                                "target": "docs/CODEX-AUTH-PROBE.md",
                                "params": {"content": "Local auth review. No publication.\n"},
                            },
                            {"tool": "git", "action": "status"},
                            {
                                "tool": "git",
                                "action": "add",
                                "params": {"path": "docs/CODEX-AUTH-PROBE.md"},
                            },
                            {"tool": "git", "action": "diff"},
                            {
                                "tool": "git",
                                "action": "commit",
                                "params": {"message": "Local auth review probe"},
                            },
                        ],
                    ),
                    TaskSpec(
                        objective="Rehearse push and draft PR after review",
                        agent_id="integrator",
                        project_id="hufmanager",
                        dry_run=True,
                        allowed_tools=["files", "git", "github"],
                        expected_output="push-rehearsal.md",
                        operations=[
                            {"tool": "git", "action": "push"},
                            {"tool": "github", "action": "open_pr"},
                        ],
                    ),
                ],
            )
        )
        for _ in range(100):
            await engine.tick()
            if engine.active:
                await asyncio.gather(*engine.active.values())
            with store.transaction() as tx:
                status = tx.missions.get(mission.id).status
            if status in {State.completed, State.failed, State.cancelled}:
                break
        assert status == State.completed, "connector rehearsal did not complete"
        workspace = Workspace(settings.workspace_root / mission.id)

        def git(*args):
            return subprocess.check_output(
                ["/usr/bin/git", *args], cwd=workspace.root, text=True
            ).strip()

        assert (
            git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD")
            == "docs/CODEX-AUTH-PROBE.md"
        )
        assert git("remote", "get-url", "origin") == engine.projects.get("hufmanager").repo_url
        with store.transaction() as tx:
            tasks = tx.tasks.list(mission_id=mission.id)
            reviews = [r for task in tasks for r in tx.reviews.list(task_id=task.id)]
            calls = [c for task in tasks for c in tx.tool_calls.list(task_id=task.id)]
            audit = tx.audit.list(mission_id=mission.id, limit=1000)
        assert len(reviews) == 2 and all(r.verdict == "approve" for r in reviews)
        assert all("dry-run" in c.result_summary for c in calls if c.action in {"push", "open_pr"})
        push = next(c for c in calls if c.action == "push")
        try:
            await GitTool(workspace, project=engine.projects.get("hufmanager")).execute(push)
        except PermissionError as error:
            assert str(error) == "no push credential configured; set HUFI_GITHUB_TOKEN"
        else:
            raise AssertionError("missing credential did not fail closed")
        shell = engine.tools(workspace, tasks[0])["shell"]
        project_commands = {}
        for action in ("run_tests", "run_build", "run_lint"):
            result = await shell.execute(
                ToolCall(
                    task_id=tasks[0].id,
                    tool="shell",
                    action=action,
                    target="workspace",
                    params={},
                    risk_class="R1",
                    policy_decision="auto_allow",
                    idempotency_key=action,
                )
            )
            project_commands[action] = {
                "sandboxed": True,
                "status": result.result_status,
                "exit_code": result.exit_code,
            }
        print(
            json.dumps(
                {
                    "mission": status,
                    "source_commit": git("rev-parse", "HEAD^"),
                    "local_commit": git("rev-parse", "HEAD"),
                    "committed_files": 1,
                    "reviews_approved": len(reviews),
                    "audit_events": len(audit),
                    "push_and_pr": "dry-run only",
                    "missing_token": "blocked",
                    "project_commands": project_commands,
                    "provider": "fake (deterministic)",
                },
                indent=2,
            )
        )
        await engine.stop()
        store.close()


if __name__ == "__main__":
    asyncio.run(main())
