"""Unit tests for the V1.3 Room->Runtime bridge.

Covers:
- Message persistence and reload
- @mention resolution (known + unknown)
- Dispatch precedence (participation states)
- Mission dispatch (parallel fan-out)
- Fan-in result persistence back to room
- Participation management
- Security boundaries
- Redaction policy
"""

import pytest

from hufiagents.contracts import Agent, ChatRoom, Risk
from hufiagents.orchestrator.planner import MissionCreate
from hufiagents.persistence.repository import Store
from hufiagents.room_runtime import (
    RoomMessageService,
    _eligible_targets,
    _MentionResult,
    _resolve_mentions,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def make_store(tmp_path):
    store = Store(f"sqlite:///{tmp_path}/state.sqlite3")
    return store


def make_room(tx, name="release-team"):
    return tx.chat_rooms.add(ChatRoom(room_type="team", host_type="team", name=name))


def make_agent(tx, agent_id, role="specialist"):
    return tx.agents.add(
        Agent(
            id=agent_id,
            role=role,
            capabilities={"tools": ["files"], "providers": ["fake"]},
            risk_ceiling=Risk.R1,
        )
    )


class _FakeOrchestrator:
    """Minimal orchestrator stub that records submitted missions."""

    def __init__(self, store):
        self.store = store
        self.submitted = []
        self.room_service = None
        self._room_notified = set()

    def submit(self, request):
        from hufiagents.orchestrator.planner import Planner

        mission, tasks = Planner().plan(request)
        with self.store.transaction() as tx:
            tx.missions.add(mission)
            for task, _ in tasks:
                tx.tasks.add(task)
        self.submitted.append(mission)
        return mission


# ---------------------------------------------------------------------------
# Message persistence
# ---------------------------------------------------------------------------


def test_post_message_persists_and_reloads(tmp_path):
    store = make_store(tmp_path)
    svc = RoomMessageService(store, _FakeOrchestrator(store))
    with store.transaction() as tx:
        room = make_room(tx)

    result = svc.post_message(
        room_id=room.id,
        sender_id="pascal",
        raw_content="Prüft bitte den aktuellen Release.",
    )
    msg = result["message"]
    assert msg.room_id == room.id
    assert msg.sender_id == "pascal"
    # Content redacted/stored safely
    assert len(msg.content) > 0

    # Reload via new store instance (simulates process restart)
    store2 = Store(f"sqlite:///{tmp_path}/state.sqlite3")
    svc2 = RoomMessageService(store2, _FakeOrchestrator(store2))
    messages = svc2.list_messages(room.id)
    assert len(messages) == 1
    assert messages[0].id == msg.id
    assert messages[0].sender_id == "pascal"


def test_post_message_empty_content_raises(tmp_path):
    store = make_store(tmp_path)
    svc = RoomMessageService(store, _FakeOrchestrator(store))
    with store.transaction() as tx:
        room = make_room(tx)
    with pytest.raises(ValueError, match="empty"):
        svc.post_message(room_id=room.id, sender_id="pascal", raw_content="   ")


def test_post_message_oversized_content_raises(tmp_path):
    store = make_store(tmp_path)
    svc = RoomMessageService(store, _FakeOrchestrator(store))
    with store.transaction() as tx:
        room = make_room(tx)
    with pytest.raises(ValueError, match="32 000"):
        svc.post_message(room_id=room.id, sender_id="pascal", raw_content="x" * 32001)


def test_post_message_unknown_room_raises(tmp_path):
    store = make_store(tmp_path)
    svc = RoomMessageService(store, _FakeOrchestrator(store))
    with pytest.raises(KeyError):
        svc.post_message(room_id="no-such-room", sender_id="pascal", raw_content="hello")


# ---------------------------------------------------------------------------
# @mention resolution
# ---------------------------------------------------------------------------


def test_known_mention_resolved(tmp_path):
    store = make_store(tmp_path)
    with store.transaction() as tx:
        make_agent(tx, "HM-SENTINEL")
        result = _resolve_mentions("@HM-SENTINEL please check.", tx)
    assert result.resolved == ["HM-SENTINEL"]
    assert result.unknown == []


def test_unknown_mention_not_silently_dropped(tmp_path):
    store = make_store(tmp_path)
    with store.transaction() as tx:
        result = _resolve_mentions("@GHOST-AGENT please check.", tx)
    assert result.unknown == ["GHOST-AGENT"]
    assert result.resolved == []


def test_mixed_mentions(tmp_path):
    store = make_store(tmp_path)
    with store.transaction() as tx:
        make_agent(tx, "HM-SENTINEL")
        result = _resolve_mentions("@HM-SENTINEL and @TYPO check this.", tx)
    assert "HM-SENTINEL" in result.resolved
    assert "TYPO" in result.unknown


def test_post_message_surfaces_unknown_mentions(tmp_path):
    store = make_store(tmp_path)
    svc = RoomMessageService(store, _FakeOrchestrator(store))
    with store.transaction() as tx:
        room = make_room(tx)
    result = svc.post_message(
        room_id=room.id,
        sender_id="pascal",
        raw_content="@UNKNOWN-BOT please check.",
    )
    assert "UNKNOWN-BOT" in result["unknown_mentions"]
    # Still persists the message
    assert result["message"].id is not None


def test_duplicate_mentions_deduped(tmp_path):
    store = make_store(tmp_path)
    with store.transaction() as tx:
        make_agent(tx, "HM-SENTINEL")
        result = _resolve_mentions("@HM-SENTINEL @HM-SENTINEL again", tx)
    assert result.resolved.count("HM-SENTINEL") == 1


# ---------------------------------------------------------------------------
# Dispatch precedence / participation states
# ---------------------------------------------------------------------------


def _make_participant(agent_id, state):
    from hufiagents.contracts import RoomParticipant

    return RoomParticipant(room_id="r1", agent_id=agent_id, participation_state=state)


def test_eligible_targets_active_participants_when_no_mentions():
    participants = [
        _make_participant("lead", "active"),
        _make_participant("security", "active"),
        _make_participant("observer", "listening"),
        _make_participant("sleeper", "sleeping"),
        _make_participant("gone", "left"),
    ]
    mention = _MentionResult(resolved=[], unknown=[])
    targets = _eligible_targets(mention, participants)
    assert set(targets) == {"lead", "security"}
    assert "observer" not in targets
    assert "sleeper" not in targets
    assert "gone" not in targets


def test_explicit_mention_includes_listening_excludes_sleeping_left():
    participants = [
        _make_participant("lead", "active"),
        _make_participant("observer", "listening"),
        _make_participant("sleeper", "sleeping"),
        _make_participant("gone", "left"),
    ]
    mention = _MentionResult(resolved=["lead", "observer", "sleeper", "gone"], unknown=[])
    targets = _eligible_targets(mention, participants)
    assert "lead" in targets
    assert "observer" in targets  # LISTENING + @mentioned -> eligible
    assert "sleeper" not in targets  # SLEEPING -> not dispatched even if mentioned
    assert "gone" not in targets  # LEFT -> never dispatched


def test_non_member_mentioned_agent_treated_as_active():
    """An @mentioned agent who is not a room participant gets treated as active."""
    participants = []  # no participants registered
    mention = _MentionResult(resolved=["external-agent"], unknown=[])
    targets = _eligible_targets(mention, participants)
    assert "external-agent" in targets


# ---------------------------------------------------------------------------
# Mission dispatch (parallel fan-out)
# ---------------------------------------------------------------------------


def test_dispatch_creates_one_mission_per_agent(tmp_path):
    store = make_store(tmp_path)
    orch = _FakeOrchestrator(store)
    svc = RoomMessageService(store, orch)
    with store.transaction() as tx:
        room = make_room(tx)
        make_agent(tx, "HM-SENTINEL")
        make_agent(tx, "HM-LIBRARIAN")

    result = svc.post_message(
        room_id=room.id,
        sender_id="pascal",
        raw_content="@HM-SENTINEL @HM-LIBRARIAN prüft bitte.",
    )
    msg_id = result["message"].id

    dispatch = svc.dispatch_mission(
        room_id=room.id,
        message_id=msg_id,
        outcome="Prüft bitte den aktuellen Release.",
    )
    # Two agents -> two independent Missions (parallel fan-out)
    assert len(dispatch["dispatched"]) == 2
    mission_ids = {d["mission_id"] for d in dispatch["dispatched"]}
    assert len(mission_ids) == 2  # distinct missions, not one shared mission


def test_dispatch_no_agents_creates_single_mission(tmp_path):
    store = make_store(tmp_path)
    orch = _FakeOrchestrator(store)
    svc = RoomMessageService(store, orch)
    with store.transaction() as tx:
        room = make_room(tx)

    result = svc.post_message(
        room_id=room.id,
        sender_id="pascal",
        raw_content="Prüft bitte.",
    )
    msg_id = result["message"].id

    dispatch = svc.dispatch_mission(
        room_id=room.id,
        message_id=msg_id,
        outcome="Prüft bitte.",
    )
    assert len(dispatch["dispatched"]) == 1


def test_dispatch_fan_out_cap_at_20(tmp_path):
    store = make_store(tmp_path)
    orch = _FakeOrchestrator(store)
    svc = RoomMessageService(store, orch)
    with store.transaction() as tx:
        room = make_room(tx)
        for i in range(25):
            make_agent(tx, f"agent-{i:02d}")

    agent_ids = [f"agent-{i:02d}" for i in range(25)]
    with store.transaction() as tx:
        msg_result = svc.post_message(
            room_id=room.id,
            sender_id="pascal",
            raw_content="check everything",
        )
    dispatch = svc.dispatch_mission(
        room_id=room.id,
        message_id=msg_result["message"].id,
        outcome="check",
        agent_ids=agent_ids,
    )
    assert len(dispatch["dispatched"]) == 20


def test_dispatch_message_wrong_room_raises(tmp_path):
    store = make_store(tmp_path)
    orch = _FakeOrchestrator(store)
    svc = RoomMessageService(store, orch)
    with store.transaction() as tx:
        room1 = make_room(tx, name="room1")
        room2 = make_room(tx, name="room2")

    result = svc.post_message(room_id=room1.id, sender_id="pascal", raw_content="hello")
    with pytest.raises(ValueError, match="does not belong"):
        svc.dispatch_mission(
            room_id=room2.id,
            message_id=result["message"].id,
            outcome="do it",
        )


def test_dispatch_records_mission_id_on_message(tmp_path):
    store = make_store(tmp_path)
    orch = _FakeOrchestrator(store)
    svc = RoomMessageService(store, orch)
    with store.transaction() as tx:
        room = make_room(tx)

    result = svc.post_message(room_id=room.id, sender_id="pascal", raw_content="check")
    msg_id = result["message"].id

    dispatch = svc.dispatch_mission(room_id=room.id, message_id=msg_id, outcome="check")
    with store.transaction() as tx:
        msg = tx.room_messages.get(msg_id)
    assert msg.mission_id == dispatch["dispatched"][-1]["mission_id"]


# ---------------------------------------------------------------------------
# Fan-in: result persistence back to room
# ---------------------------------------------------------------------------


def test_post_result_creates_system_message_in_room(tmp_path):
    store = make_store(tmp_path)
    orch = _FakeOrchestrator(store)
    svc = RoomMessageService(store, orch)
    with store.transaction() as tx:
        room = make_room(tx)
    mission = orch.submit(MissionCreate(outcome="check"))
    user_result = svc.post_message(room_id=room.id, sender_id="pascal", raw_content="check")
    user_msg_id = user_result["message"].id

    svc.post_result(
        room_id=room.id,
        mission_id=mission.id,
        result_summary="Security review completed. No issues found.",
        parent_message_id=user_msg_id,
    )

    messages = svc.list_messages(room.id)
    assert len(messages) == 2
    system_msg = messages[1]
    assert system_msg.sender_type == "system"
    assert system_msg.mission_id == mission.id
    assert system_msg.parent_message_id == user_msg_id


def test_notify_mission_outcome_posts_to_room(tmp_path):
    store = make_store(tmp_path)
    orch = _FakeOrchestrator(store)
    svc = RoomMessageService(store, orch)
    with store.transaction() as tx:
        room = make_room(tx)

    user_result = svc.post_message(room_id=room.id, sender_id="pascal", raw_content="check")
    msg_id = user_result["message"].id

    # Create a mission with room_id constraint (simulating dispatch)
    mission = MissionCreate(
        outcome="check",
        constraints={"room_id": room.id, "source_message_id": msg_id},
    )
    submitted = orch.submit(mission)

    svc.notify_mission_outcome(
        mission_id=submitted.id,
        status="completed",
        result="Security review: PASS.",
    )

    messages = svc.list_messages(room.id)
    assert any(m.mission_id == submitted.id for m in messages)
    result_msgs = [m for m in messages if m.sender_type == "system"]
    assert len(result_msgs) == 1


def test_notify_mission_outcome_noop_for_non_room_mission(tmp_path):
    store = make_store(tmp_path)
    orch = _FakeOrchestrator(store)
    svc = RoomMessageService(store, orch)
    with store.transaction() as tx:
        room = make_room(tx)

    # Mission with no room_id constraint
    mission = MissionCreate(outcome="standalone", constraints={})
    submitted = orch.submit(mission)
    # Should not raise; no messages posted
    svc.notify_mission_outcome(mission_id=submitted.id, status="completed", result="done")
    messages = svc.list_messages(room.id)
    assert len(messages) == 0


def test_notify_mission_outcome_unknown_mission_is_noop(tmp_path):
    store = make_store(tmp_path)
    svc = RoomMessageService(store, _FakeOrchestrator(store))
    # Should not raise
    svc.notify_mission_outcome(mission_id="nonexistent", status="completed", result="")


# ---------------------------------------------------------------------------
# Reload persistence
# ---------------------------------------------------------------------------


def test_reload_preserves_message_history(tmp_path):
    store = make_store(tmp_path)
    svc = RoomMessageService(store, _FakeOrchestrator(store))
    with store.transaction() as tx:
        room = make_room(tx)

    for i in range(3):
        svc.post_message(room_id=room.id, sender_id="pascal", raw_content=f"Message {i}")

    # New store instance (simulates process restart)
    store2 = Store(f"sqlite:///{tmp_path}/state.sqlite3")
    svc2 = RoomMessageService(store2, _FakeOrchestrator(store2))
    messages = svc2.list_messages(room.id)
    assert len(messages) == 3


# ---------------------------------------------------------------------------
# Participation management
# ---------------------------------------------------------------------------


def test_join_room_creates_participant(tmp_path):
    store = make_store(tmp_path)
    svc = RoomMessageService(store, _FakeOrchestrator(store))
    with store.transaction() as tx:
        room = make_room(tx)
        make_agent(tx, "sentinel")

    p = svc.join_room(room_id=room.id, agent_id="sentinel")
    assert p.participation_state == "active"
    assert p.room_id == room.id


def test_join_room_idempotent(tmp_path):
    store = make_store(tmp_path)
    svc = RoomMessageService(store, _FakeOrchestrator(store))
    with store.transaction() as tx:
        room = make_room(tx)
        make_agent(tx, "sentinel")

    p1 = svc.join_room(room_id=room.id, agent_id="sentinel")
    p2 = svc.join_room(room_id=room.id, agent_id="sentinel")
    assert p1.id == p2.id


def test_leave_room_marks_left(tmp_path):
    store = make_store(tmp_path)
    svc = RoomMessageService(store, _FakeOrchestrator(store))
    with store.transaction() as tx:
        room = make_room(tx)
        make_agent(tx, "sentinel")

    svc.join_room(room_id=room.id, agent_id="sentinel")
    p = svc.leave_room(room_id=room.id, agent_id="sentinel")
    assert p.participation_state == "left"
    assert p.left_at is not None


def test_leave_room_non_member_raises(tmp_path):
    store = make_store(tmp_path)
    svc = RoomMessageService(store, _FakeOrchestrator(store))
    with store.transaction() as tx:
        room = make_room(tx)
    with pytest.raises(KeyError):
        svc.leave_room(room_id=room.id, agent_id="nobody")


def test_set_participation_state_valid_states(tmp_path):
    store = make_store(tmp_path)
    svc = RoomMessageService(store, _FakeOrchestrator(store))
    with store.transaction() as tx:
        room = make_room(tx)
        make_agent(tx, "sentinel")

    svc.join_room(room_id=room.id, agent_id="sentinel")
    for state in ("active", "listening", "sleeping", "left"):
        p = svc.set_participation_state(room_id=room.id, agent_id="sentinel", state=state)
        assert p.participation_state == state


def test_set_participation_state_invalid_raises(tmp_path):
    store = make_store(tmp_path)
    svc = RoomMessageService(store, _FakeOrchestrator(store))
    with store.transaction() as tx:
        room = make_room(tx)
        make_agent(tx, "sentinel")

    svc.join_room(room_id=room.id, agent_id="sentinel")
    with pytest.raises(ValueError, match="state must be one of"):
        svc.set_participation_state(room_id=room.id, agent_id="sentinel", state="busy")


def test_rejoin_restores_active_state(tmp_path):
    store = make_store(tmp_path)
    svc = RoomMessageService(store, _FakeOrchestrator(store))
    with store.transaction() as tx:
        room = make_room(tx)
        make_agent(tx, "sentinel")

    svc.join_room(room_id=room.id, agent_id="sentinel")
    svc.leave_room(room_id=room.id, agent_id="sentinel")
    p = svc.join_room(room_id=room.id, agent_id="sentinel")
    assert p.participation_state == "active"
    assert p.left_at is None


# ---------------------------------------------------------------------------
# Security boundaries
# ---------------------------------------------------------------------------


def test_cross_room_isolation(tmp_path):
    """Messages from room A must not appear in room B."""
    store = make_store(tmp_path)
    svc = RoomMessageService(store, _FakeOrchestrator(store))
    with store.transaction() as tx:
        roomA = make_room(tx, name="room-a")
        roomB = make_room(tx, name="room-b")

    svc.post_message(room_id=roomA.id, sender_id="pascal", raw_content="Room A message")
    msgs_b = svc.list_messages(roomB.id)
    assert len(msgs_b) == 0


def test_unknown_room_safe_failure(tmp_path):
    store = make_store(tmp_path)
    svc = RoomMessageService(store, _FakeOrchestrator(store))
    with pytest.raises(KeyError):
        svc.list_messages("no-such-room")


def test_unknown_mention_does_not_create_agent(tmp_path):
    store = make_store(tmp_path)
    svc = RoomMessageService(store, _FakeOrchestrator(store))
    with store.transaction() as tx:
        room = make_room(tx)
    svc.post_message(room_id=room.id, sender_id="pascal", raw_content="@FAKE-GHOST do something")
    with store.transaction() as tx:
        agents = tx.agents.list(id="FAKE-GHOST", limit=1)
    assert len(agents) == 0


def test_mention_does_not_grant_privilege():
    """@mention inclusion in targets does NOT change risk ceiling or capabilities."""
    participants = [_make_participant("sentinel", "sleeping")]
    mention = _MentionResult(resolved=["sentinel"], unknown=[])
    # sleeping sentinel should NOT be dispatched even if mentioned
    targets = _eligible_targets(mention, participants)
    assert "sentinel" not in targets


def test_redaction_applied_to_message_content(tmp_path):
    """Secret-like content must be redacted before persistence."""
    store = make_store(tmp_path)
    svc = RoomMessageService(store, _FakeOrchestrator(store))
    with store.transaction() as tx:
        room = make_room(tx)
    # The redaction module strips patterns like token=... and ghp_...
    result = svc.post_message(
        room_id=room.id,
        sender_id="pascal",
        raw_content="Use token=secretval123456 and ghp_1234567890abcdef for access",
    )
    # The raw credential values should not appear verbatim
    assert "secretval123456" not in result["message"].content
    assert "ghp_1234567890abcdef" not in result["message"].content


def test_participation_state_change_does_not_raise_risk_ceiling(tmp_path):
    """Changing participation state is purely an execution hint; risk/caps unchanged."""
    store = make_store(tmp_path)
    svc = RoomMessageService(store, _FakeOrchestrator(store))
    with store.transaction() as tx:
        room = make_room(tx)
        make_agent(tx, "guarded")
    svc.join_room(room_id=room.id, agent_id="guarded")
    # Changing state should never touch agent contract
    svc.set_participation_state(room_id=room.id, agent_id="guarded", state="active")
    with store.transaction() as tx:
        a = tx.agents.get("guarded")
    assert a.risk_ceiling == Risk.R1  # unchanged


# ---------------------------------------------------------------------------
# Golden path: one message -> multi-agent execution -> result back to room
# ---------------------------------------------------------------------------


def test_golden_path_room_mission_dispatch_and_result(tmp_path):
    """
    Golden test:
    Room: release-team
    Agents: lead, security, librarian
    User posts ONE message -> recipients resolved -> real Mission created
    for each agent -> fan-in result posted back to room.
    """
    store = make_store(tmp_path)
    orch = _FakeOrchestrator(store)
    svc = RoomMessageService(store, orch)

    with store.transaction() as tx:
        room = make_room(tx, name="release-team")
        make_agent(tx, "lead", "lead")
        make_agent(tx, "security", "security")
        make_agent(tx, "librarian", "librarian")

    # Agents join room
    svc.join_room(room_id=room.id, agent_id="lead")
    svc.join_room(room_id=room.id, agent_id="security")
    svc.join_room(room_id=room.id, agent_id="librarian")

    # User posts ONE message
    result = svc.post_message(
        room_id=room.id,
        sender_id="pascal",
        raw_content="@security @librarian Prüft bitte den aktuellen Release.",
    )
    assert result["unknown_mentions"] == []
    msg_id = result["message"].id

    # Message persists
    messages = svc.list_messages(room.id)
    assert len(messages) == 1

    # Dispatch -> one real mission per agent
    dispatch = svc.dispatch_mission(
        room_id=room.id,
        message_id=msg_id,
        outcome="Prüft bitte den aktuellen Release.",
    )
    assert len(dispatch["dispatched"]) == 2
    agent_ids_dispatched = {d["agent_id"] for d in dispatch["dispatched"]}
    assert agent_ids_dispatched == {"security", "librarian"}

    # Each dispatched mission is independent and real (persisted)
    mission_ids = [d["mission_id"] for d in dispatch["dispatched"]]
    for mid in mission_ids:
        with store.transaction() as tx:
            m = tx.missions.get(mid)
        assert m.constraints["room_id"] == room.id

    # Fan-in: result posted back to room for each mission
    for _i, d in enumerate(dispatch["dispatched"]):
        svc.notify_mission_outcome(
            mission_id=d["mission_id"],
            status="completed",
            result=f"Agent {d['agent_id']} completed review.",
        )

    # Room now has user message + 2 result messages
    final_messages = svc.list_messages(room.id)
    assert len(final_messages) == 3
    system_msgs = [m for m in final_messages if m.sender_type == "system"]
    assert len(system_msgs) == 2

    # Reload from fresh store instance -> all messages preserved
    store2 = Store(f"sqlite:///{tmp_path}/state.sqlite3")
    svc2 = RoomMessageService(store2, _FakeOrchestrator(store2))
    reloaded = svc2.list_messages(room.id)
    assert len(reloaded) == 3
