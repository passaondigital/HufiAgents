"""Reusable HTTP surface for the company graph and credential handles."""
# ruff: noqa: E501, E701

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from hufiagents.org_graph import (
    add_relationship,
    archive_team,
    create_project,
    create_resource,
    create_room,
    create_team,
    register_credential,
    remove_relationship,
)


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
    async def org():
        with app.state.store.transaction() as tx:
            return {
                name: getattr(tx, name).list(limit=10000)
                for name in ("teams", "graph_projects", "resources", "relationships", "chat_rooms")
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
