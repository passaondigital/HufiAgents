"""Typed company graph services.  Membership is additive and never identity."""
# The compact service functions intentionally keep transaction operations together.
# ruff: noqa: E501

import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from hufiagents.contracts import (
    ChatRoom,
    CredentialRef,
    GraphProject,
    GraphRelationship,
    Resource,
    Team,
)

RELATIONSHIPS = {
    "reports_to",
    "member_of_team",
    "works_on_project",
    "responsible_for_resource",
    "may_use_resource",
}


def _active(tx, relation):
    return tx.relationships.list(relationship_type=relation, removed_at=None, limit=10000)


def create_team(tx, name, description=""):
    team = tx.teams.add(Team(name=name, description=description))
    tx.log("team_created", team_id=team.id, name=team.name)
    return team


def archive_team(tx, team_id):
    team = tx.teams.get(team_id)
    team.status, team.archived_at = "archived", datetime.now(UTC)
    tx.teams.save(team)
    tx.log("team_archived", team_id=team_id)
    return team


def create_project(tx, name, description="", repository_ref=None):
    return tx.graph_projects.add(
        GraphProject(name=name, description=description, repository_ref=repository_ref)
    )


def create_resource(tx, name, resource_type="other", description="", metadata=None):
    return tx.resources.add(
        Resource(
            name=name, resource_type=resource_type, description=description, metadata=metadata or {}
        )
    )


def create_room(tx, room_type, host_type, host_id, name):
    room = tx.chat_rooms.add(
        ChatRoom(room_type=room_type, host_type=host_type, host_id=host_id, name=name)
    )
    tx.log("room_created", room_id=room.id, room_type=room_type, host_id=host_id)
    return room


def add_relationship(
    tx, relationship_type, source_type, source_id, target_type, target_id, primary=False
):
    if relationship_type not in RELATIONSHIPS:
        raise ValueError("unsupported relationship type")
    if source_type == target_type and source_id == target_id:
        raise ValueError("self relationships are not allowed")
    if relationship_type == "reports_to":
        if source_type != "agent" or target_type != "agent":
            raise ValueError("reports_to requires agent nodes")
        # Walk target's reporting chain to prevent obvious cycles.
        current = target_id
        seen = {source_id}
        while current:
            if current in seen:
                raise ValueError("reporting cycle")
            seen.add(current)
            edges = [e for e in _active(tx, "reports_to") if e.source_id == current and e.primary]
            current = edges[0].target_id if edges else None
    if relationship_type == "member_of_team":
        team = tx.teams.get(target_id)
        agent = next((a for a in tx.agents.list(id=source_id)), None)
        if team.status == "archived" or (agent and agent.status != "active"):
            raise ValueError("archived nodes cannot gain memberships")
    edge = tx.relationships.add(
        GraphRelationship(
            relationship_type=relationship_type,
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            primary=primary,
        )
    )
    tx.log(
        "relationship_created",
        relationship_id=edge.id,
        relationship_type=relationship_type,
        source_id=source_id,
        target_id=target_id,
    )
    return edge


def remove_relationship(tx, relationship_id):
    edge = tx.relationships.get(relationship_id)
    edge.removed_at = datetime.now(UTC)
    tx.relationships.save(edge)
    tx.log(
        "relationship_removed", relationship_id=edge.id, relationship_type=edge.relationship_type
    )
    return edge


def register_credential(tx, connector, label, scopes=None):
    """Register a handle only. Callers must store secret material externally."""
    ref = tx.credential_refs.add(
        CredentialRef(connector=connector, label=label, scopes=scopes or [])
    )
    tx.log("credential_registered", credential_id=ref.id, connector=connector, scopes=ref.scopes)
    return ref


def revoke_credential(tx, credential_id):
    ref = tx.credential_refs.get(credential_id)
    ref.status, ref.revoked_at = "revoked", datetime.now(UTC)
    tx.credential_refs.save(ref)
    tx.log("credential_revoked", credential_id=ref.id, connector=ref.connector)
    return ref


def rotate_credential(tx, credential_id):
    ref = tx.credential_refs.get(credential_id)
    if ref.status != "active":
        raise ValueError("cannot rotate revoked credential")
    ref.rotated_at = datetime.now(UTC)
    tx.credential_refs.save(ref)
    tx.log("credential_rotated", credential_id=ref.id, connector=ref.connector)
    return ref


class CostGovernor:
    """Provider-neutral budget gate. Local aliases always carry zero EUR cost."""

    LOCAL = {"hufi-qwen9-fast", "hufi-qwen9", "hufi-gemma", "hufi-local-router", "fake", "ollama"}

    def __init__(self, external_cost_limit=0.0):
        self.external_cost_limit = float(external_cost_limit)
        self.reserved = 0.0

    def estimate(self, provider, input_tokens=0, output_tokens=0, price_per_1k=0.0):
        return (
            0.0 if provider in self.LOCAL else (input_tokens + output_tokens) / 1000 * price_per_1k
        )

    def reserve(self, provider, input_tokens=0, output_tokens=0, price_per_1k=0.0):
        amount = self.estimate(provider, input_tokens, output_tokens, price_per_1k)
        if self.reserved + amount > self.external_cost_limit:
            raise PermissionError("external cost budget exceeded")
        self.reserved += amount
        return amount


def deterministic_check(kind, target):
    """Small no-LLM checks return structured facts, suitable for Work Evidence."""
    if kind == "http_status":
        import urllib.request

        try:
            with urllib.request.urlopen(target, timeout=5) as response:
                return {"healthy": 200 <= response.status < 400, "status": response.status}
        except Exception as exc:
            return {"healthy": False, "error": type(exc).__name__}
    if kind == "disk_usage":
        usage = shutil.disk_usage(target)
        return {"healthy": usage.free > 0, "free_bytes": usage.free, "total_bytes": usage.total}
    if kind == "file_exists":
        return {"healthy": Path(target).exists(), "path": str(target)}
    if kind == "git_clean":
        result = subprocess.run(
            ["git", "-C", target, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return {
            "healthy": result.returncode == 0 and not result.stdout.strip(),
            "clean": not result.stdout.strip(),
        }
    raise ValueError("unsupported deterministic check")
