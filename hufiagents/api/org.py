"""Reusable HTTP surface for the company graph and credential handles."""
# ruff: noqa: E501, E701

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from hufiagents.org_graph import (
    add_relationship,
    archive_org_unit,
    archive_team,
    create_org_unit,
    create_project,
    create_resource,
    create_room,
    create_team,
    register_credential,
    remove_relationship,
    update_org_unit_parent,
)


class OrgUnitIn(BaseModel):
    stable_key: str | None = Field(None, min_length=1, max_length=300)
    name: str = Field(min_length=1, max_length=200)
    unit_type: str = "DEPARTMENT"
    description: str = ""
    parent_unit_id: str | None = None
    project_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class OrgUnitMove(BaseModel):
    parent_unit_id: str | None = None


class TeamIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class ProjectIn(TeamIn):
    repository_ref: str | None = None


class ResourceIn(TeamIn):
    resource_type: str = "other"
    metadata: dict = {}


class RelationshipIn(BaseModel):
    relationship_type: str
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    primary: bool = False


class RoomIn(BaseModel):
    room_type: str
    host_type: str
    host_id: str | None = None
    name: str = Field(min_length=1, max_length=200)


class CredentialIn(BaseModel):
    connector: str
    label: str
    scopes: list[str] = []


def router_for(app):
    router = APIRouter()

    @router.get("/org")
    async def org(limit: int = Query(500, ge=1, le=1000)):
        with app.state.store.transaction() as tx:
            return {
                name: getattr(tx, name).list(limit=limit)
                for name in (
                    "organization_units",
                    "teams",
                    "graph_projects",
                    "resources",
                    "relationships",
                    "chat_rooms",
                )
            }

    @router.get("/org-units")
    async def org_units(limit: int = Query(200, ge=1, le=500), offset: int = Query(0, ge=0)):
        with app.state.store.transaction() as tx:
            return tx.organization_units.list(limit=limit, offset=offset)

    @router.post("/org-units")
    async def org_units_create(body: OrgUnitIn):
        with app.state.store.transaction() as tx:
            return create_org_unit(
                tx,
                name=body.name,
                unit_type=body.unit_type,
                description=body.description,
                parent_unit_id=body.parent_unit_id,
                project_id=body.project_id,
                metadata=body.metadata,
                stable_key=body.stable_key,
            )

    @router.post("/org-units/{identifier}/move")
    async def org_units_move(identifier: str, body: OrgUnitMove):
        with app.state.store.transaction() as tx:
            return update_org_unit_parent(tx, identifier, body.parent_unit_id)

    @router.post("/org-units/{identifier}/archive")
    async def org_units_archive(identifier: str):
        with app.state.store.transaction() as tx:
            return archive_org_unit(tx, identifier)

    @router.get("/org-units/{identifier}/members")
    async def org_unit_members(identifier: str):
        with app.state.store.transaction() as tx:
            tx.organization_units.get(identifier)
            return tx.relationships.list(relationship_type="member_of_unit", target_id=identifier)

    @router.get("/org-units/{identifier}/workspace")
    async def org_unit_workspace(identifier: str, limit: int = Query(50, ge=1, le=100)):
        with app.state.store.transaction() as tx:
            unit = tx.organization_units.get(identifier)
            events = tx.workforce_events.list(unit_id=identifier, limit=limit, descending=True)
            task_ids = {event.task_id for event in events if event.task_id}
            tasks = [tx.tasks.get(task_id) for task_id in task_ids if task_id]
            tasks = [task for task in tasks if task is not None]
            agent_ids = {task.assigned_agent_id for task in tasks if task.assigned_agent_id}
            agents = [tx.agents.get(agent_id) for agent_id in agent_ids if agent_id]
            active_agents = [agent for agent in agents if agent is not None]
            artifacts = [
                item for item in tx.work_artifacts.list(limit=500) if item.task_id in task_ids
            ]
            return {
                "unit": unit,
                "active_agents": active_agents,
                "tasks": tasks,
                "artifacts": artifacts,
                "events": events,
            }

    @router.get("/teams")
    async def teams():
        with app.state.store.transaction() as tx:
            return tx.teams.list()

    @router.post("/teams")
    async def teams_create(body: TeamIn):
        with app.state.store.transaction() as tx:
            return create_team(tx, body.name, body.description)

    @router.post("/teams/{identifier}/archive")
    async def teams_archive(identifier: str):
        with app.state.store.transaction() as tx:
            return archive_team(tx, identifier)

    @router.get("/teams/{identifier}/members")
    async def team_members(identifier: str):
        with app.state.store.transaction() as tx:
            tx.teams.get(identifier)
            return tx.relationships.list(relationship_type="member_of_team", target_id=identifier)

    @router.post("/projects")
    async def projects_create(body: ProjectIn):
        with app.state.store.transaction() as tx:
            return create_project(tx, body.name, body.description, body.repository_ref)

    @router.get("/projects/{identifier}/members")
    async def project_members(identifier: str):
        with app.state.store.transaction() as tx:
            tx.graph_projects.get(identifier)
            return tx.relationships.list(relationship_type="works_on_project", target_id=identifier)

    @router.get("/resources")
    async def resources():
        with app.state.store.transaction() as tx:
            return tx.resources.list()

    @router.get("/rooms")
    async def rooms():
        with app.state.store.transaction() as tx:
            return tx.chat_rooms.list()

    @router.get("/graph-projects")
    async def graph_projects():
        with app.state.store.transaction() as tx:
            return tx.graph_projects.list()

    @router.post("/graph-projects")
    async def graph_projects_create(body: ProjectIn):
        with app.state.store.transaction() as tx:
            return create_project(tx, body.name, body.description, body.repository_ref)

    @router.post("/resources")
    async def resources_create(body: ResourceIn):
        with app.state.store.transaction() as tx:
            return create_resource(
                tx, body.name, body.resource_type, body.description, body.metadata
            )

    @router.get("/relationships")
    async def relationships(limit: int = Query(100, ge=1, le=1000)):
        with app.state.store.transaction() as tx:
            return tx.relationships.list(limit=limit)

    @router.post("/relationships")
    async def relationships_create(body: RelationshipIn):
        with app.state.store.transaction() as tx:
            return add_relationship(tx, **body.model_dump())

    @router.delete("/relationships/{identifier}")
    async def relationships_delete(identifier: str):
        with app.state.store.transaction() as tx:
            return remove_relationship(tx, identifier)

    @router.post("/rooms")
    async def rooms_create(body: RoomIn):
        with app.state.store.transaction() as tx:
            return create_room(tx, **body.model_dump())

    @router.post("/credentials")
    async def credentials_create(body: CredentialIn):
        with app.state.store.transaction() as tx:
            return register_credential(tx, **body.model_dump())

    return router
