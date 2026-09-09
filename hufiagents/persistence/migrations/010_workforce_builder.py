"""V1.3 Workforce Builder: agent profile history table."""

from hufiagents.persistence.schema import TABLES


def apply(connection):
    TABLES["agent_profile_history"].create(connection, checkfirst=True)
