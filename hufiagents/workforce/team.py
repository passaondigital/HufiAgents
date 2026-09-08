"""Small, auditable HufManager team mission built on the durable workforce."""

import asyncio
import json

from hufiagents.contracts import Agent, Mission, Risk, State, Task
from hufiagents.providers.base import CompletionRequest
from hufiagents.tools.workspace import Workspace


class HufManagerTeamMission:
    """Run the safe, read-only sales-readiness benchmark with a real team shape.

    It deliberately uses only project-registry facts and a configured local
    provider. Repository mutation, browser launch and connector writes are not
    part of this benchmark.
    """

    def __init__(self, engine):
        self.engine = engine

    async def run(self):
        project = self.engine.projects.get("hufmanager")
        mission = Mission(
            outcome="Bewerte HufManager Verkaufsreife.",
            risk_ceiling=Risk.R0,
            constraints={"project_id": project.id, "mode": "read-only team assessment"},
            status=State.running,
        )
        with self.engine.store.transaction() as tx:
            tx.missions.add(mission)
            tx.log(
                "team_mission_started",
                mission_id=mission.id,
                actor="hufi_chief",
                project_id=project.id,
            )

        lead = self._create_agent(mission.id, "project-lead", "Project Lead")
        security = self._create_agent(mission.id, "security", "Security specialist")
        product = self._create_agent(mission.id, "product", "Product specialist")
        delegates = self.engine.workforce.fan_out(
            parent_agent_id=lead.id,
            child_agent_ids=[security.id, product.id],
            objective="Assess HufManager sales readiness from the registered repository facts.",
            mission_id=mission.id,
        )
        roles = {security.id: "security and delivery risk", product.id: "product and UX readiness"}
        results = await asyncio.gather(
            *(
                self._assess(item.child_agent_id, roles[item.child_agent_id], project)
                for item in delegates
            )
        )
        for delegation, result in zip(delegates, results, strict=True):
            self.engine.workforce.receive_agent_result(
                delegation.id, agent_id=delegation.child_agent_id, result=result
            )
        aggregate = self.engine.workforce.fan_in([item.id for item in delegates])
        return self._review_and_finish(mission, aggregate["report"])

    def _create_agent(self, mission_id, suffix, role):
        identifier = f"hufmanager-{suffix}-{mission_id[:8]}"
        parent = (
            "hufi_chief"
            if suffix == "project-lead"
            else f"hufmanager-project-lead-{mission_id[:8]}"
        )
        return self.engine.workforce.create_agent(
            Agent(
                id=identifier,
                name=role,
                role=role,
                description=f"Temporary HufManager {role.lower()} for one read-only mission.",
                parent_agent_id=parent,
                capabilities={"tools": [], "providers": [self.engine.settings.default_provider]},
                risk_ceiling=Risk.R0,
                project_id="hufmanager",
                memory_scope=f"mission:{mission_id}",
            ),
            delegator_id=parent,
        )

    async def _assess(self, agent_id, specialty, project):
        agent = self.engine.registry.get(agent_id)
        provider_id = self.engine.settings.default_provider
        if provider_id not in agent.capabilities.get("providers", []):
            raise PermissionError("team specialist lacks configured local provider capability")
        provider = self.engine.providers[provider_id]
        health = await provider.health()
        if not health.available:
            raise ConnectionError("configured local provider unavailable")
        facts = {
            "project": project.id,
            "repo_url": project.repo_url,
            "github_repo": project.github_repo,
            "default_branch": project.default_branch,
            "registered_test": bool(project.test_command),
            "registered_build": bool(project.build_command),
            "registered_lint": bool(project.lint_command),
            "fact_source": "server-side project registry",
        }
        objective = (
            f"Assess {specialty} for HufManager sales readiness. State evidence and blockers."
        )
        result = await provider.complete(
            CompletionRequest(
                objective=objective,
                context=json.dumps(facts),
                max_tokens=512,
            )
        )
        with self.engine.store.transaction() as tx:
            tx.log(
                "team_specialist_model_result",
                actor=agent_id,
                provider=provider_id,
                model=result.model,
                characters=len(result.text),
            )
        return result.text

    def _review_and_finish(self, mission, report):
        task = Task(
            mission_id=mission.id,
            objective="Independently review merged team report",
            expected_output="TEAM-REPORT.md",
            allowed_tools=[],
            risk_ceiling=Risk.R0,
            acceptance_criteria=[{"type": "nonempty"}],
        )
        workspace = Workspace(self.engine.settings.workspace_root / "team-missions" / mission.id)
        workspace.create(task.expected_output, report)
        with self.engine.store.transaction() as tx:
            tx.tasks.add(task)
            tx.transition(task, State.planning)
            tx.transition(task, State.running)
            task.result = report
            tx.tasks.save(task)
            tx.transition(task, State.review)
            review = self.engine.reviewer.review(task, workspace, task.expected_output, [])
            tx.reviews.add(review)
            tx.log("team_mission_review", task=task, actor="reviewer", verdict=review.verdict)
            tx.transition(
                task,
                State.completed if review.verdict == "approve" else State.failed,
                reason="independent team report review",
            )
            finished = tx.missions.get(mission.id)
            tx.log(
                "team_mission_completed",
                mission_id=mission.id,
                actor="hufi_chief",
                reviewer_verdict=review.verdict,
            )
            return {
                "mission_id": mission.id,
                "status": finished.status,
                "report": report,
                "review": review,
            }
