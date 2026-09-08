"""Additive V1.2 organization graph, rooms and credential handles."""

from hufiagents.persistence.schema import TABLES


def apply(connection):
    for name in (
        "teams",
        "graph_projects",
        "resources",
        "relationships",
        "chat_rooms",
        "credential_refs",
    ):
        TABLES[name].create(connection, checkfirst=True)
