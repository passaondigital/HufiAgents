"""V1.3 Room→Runtime bridge: persistent room messages and participant tracking."""

from hufiagents.persistence.schema import TABLES


def apply(connection):
    for name in ("room_messages", "room_participants"):
        TABLES[name].create(connection, checkfirst=True)
