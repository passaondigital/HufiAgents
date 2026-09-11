"""Migration 012 compatibility and preservation tests."""

import importlib

from sqlalchemy import create_engine, inspect

from hufiagents.contracts import Agent, ChatRoom, GraphProject, MemoryRecord, Skill, Team
from hufiagents.org_graph import bootstrap_corporate_matrix
from hufiagents.persistence.repository import Store

migration_012 = importlib.import_module(
    "hufiagents.persistence.migrations.012_v1_4a_corporate_matrix"
)


def test_migration_012_fresh_database_and_bootstrap_are_idempotent(tmp_path):
    path = tmp_path / "fresh.sqlite3"
    store = Store(f"sqlite:///{path}")
    bootstrap_corporate_matrix(store)
    bootstrap_corporate_matrix(store)
    with store.engine.begin() as connection:
        names = set(inspect(connection).get_table_names())
        assert {
            "organization_units",
            "owner_outcome_contracts",
            "work_artifacts",
            "workforce_events",
        } <= names
        migration_012.apply(connection)
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
    with store.transaction() as tx:
        keys = [unit.stable_key for unit in tx.organization_units.list(limit=1000)]
        assert len(keys) == len(set(keys))
    store.close()


def test_v131_records_survive_additive_upgrade(tmp_path):
    path = tmp_path / "upgrade.sqlite3"
    url = f"sqlite:///{path}"
    store = Store(url)
    with store.transaction() as tx:
        tx.agents.add(Agent(id="legacy-agent", role="Legacy", capabilities={"tools": []}))
        tx.teams.add(Team(id="legacy-team", name="Legacy Team"))
        tx.graph_projects.add(GraphProject(id="legacy-project", name="Legacy Project"))
        tx.chat_rooms.add(
            ChatRoom(
                id="legacy-room",
                room_type="company",
                host_type="company",
                name="Legacy Room",
            )
        )
        tx.agent_memory.add(
            MemoryRecord(id="legacy-memory", owner_id="legacy-agent", key="k", value={"v": 1})
        )
        tx.skills.add(Skill(id="legacy-skill", name="Legacy Skill"))
    store.close()

    engine = create_engine(url)
    with engine.begin() as connection:
        for table in (
            "workforce_events",
            "work_artifacts",
            "owner_outcome_contracts",
            "organization_units",
        ):
            connection.exec_driver_sql(f"DROP TABLE {table}")
        connection.exec_driver_sql("DELETE FROM schema_migrations WHERE version = 12")
    engine.dispose()

    upgraded = Store(url)
    with upgraded.transaction() as tx:
        assert tx.agents.get("legacy-agent").role == "Legacy"
        assert tx.teams.get("legacy-team").name == "Legacy Team"
        assert tx.graph_projects.get("legacy-project").name == "Legacy Project"
        assert tx.chat_rooms.get("legacy-room").name == "Legacy Room"
        assert tx.agent_memory.get("legacy-memory").value == {"v": 1}
        assert tx.skills.get("legacy-skill").name == "Legacy Skill"
    with upgraded.engine.begin() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
    upgraded.close()
