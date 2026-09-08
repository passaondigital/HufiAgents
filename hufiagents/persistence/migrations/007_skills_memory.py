"""V1.2 procedural knowledge and explicitly scoped memory tables."""

from hufiagents.persistence.schema import TABLES


def apply(connection):
    for name in ("skills", "scoped_memories", "learning_records"):
        TABLES[name].create(connection, checkfirst=True)
