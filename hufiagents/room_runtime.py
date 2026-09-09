"""Room→Runtime bridge: persistent messages, @mention dispatch, result persistence.

Design rules:
- NO second orchestrator.  Mission submission goes through ``Orchestrator.submit()``.
- NO second agent framework.  Fan-out goes through independent Mission submissions
  so each agent's task can run concurrently within the existing semaphore limit.
- NO fake status indicators.  Participation state reflects only runtime semantics.
- Content is always redacted before persistence via ``hufiagents.redaction.redact``.
- @mentions are resolved *before* redaction so agent IDs can be captured.
- Unknown mentions are REPORTED (not silently dropped) in the post_message response.
- Fan-in: when all missions dispatched from a room message reach a terminal state,
  a system result message is posted back to the originating room.

Participation-state dispatch semantics (execution only; NOT authorization):
  active    -> eligible for normal policy-driven dispatch
  listening -> dispatched ONLY if explicitly @mentioned in the message
  sleeping  -> NOT dispatched automatically; must be @mentioned
  left      -> NOT dispatched under any circumstance
"""

import re
from dataclasses import dataclass, field

from hufiagents.contracts import RoomMessage, RoomParticipant, now
from hufiagents.orchestrator.planner import MissionCreate, TaskSpec
from hufiagents.redaction import redact

# Pattern for @agent-id mentions: @<word-chars and hyphens, 1-200 chars>
_MENTION_RE = re.compile(r"@([\w-]{1,200})")

# -------------------------------------------------------------------------
# Internal data class returned from _resolve_mentions
# -------------------------------------------------------------------------


@dataclass
class _MentionResult:
    resolved: list = field(default_factory=list)
    unknown: list = field(default_factory=list)


def _resolve_mentions(content: str, tx) -> _MentionResult:
    """Resolve every @mention in *content* against the real agent registry.

    Returns a ``_MentionResult`` with:
    * ``resolved`` - agent IDs that exist in the registry.
    * ``unknown``  - candidate strings that could NOT be resolved.

    Unknown mentions are *not* silently ignored: callers must surface them
    as validation information so the user knows the mention failed.
    Mentions NEVER grant privileges; they only influence dispatch eligibility.
    """
    candidates = _MENTION_RE.findall(content)
    result = _MentionResult()
    seen: set = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        rows = tx.agents.list(id=candidate, limit=1)
        if rows:
            result.resolved.append(rows[0].id)
        else:
            result.unknown.append(candidate)
    return result


def _eligible_targets(
    mention_result: _MentionResult,
    participants: list,
) -> list:
    """Return the ordered list of agent IDs that should receive dispatch tasks.

    Dispatch precedence:
    1. Explicit @mentions (resolved only; must be ACTIVE or LISTENING).
    2. Otherwise: ACTIVE room participants.

    SLEEPING / LEFT participants are never auto-dispatched.
    Room membership does NOT grant capabilities or raise risk ceilings.
    """
    state_by_agent: dict = {p.agent_id: p.participation_state for p in participants}

    if mention_result.resolved:
        # Explicit mention path - includes ACTIVE and LISTENING agents
        eligible = []
        for agent_id in mention_result.resolved:
            state = state_by_agent.get(agent_id, "active")  # non-member -> treat as active
            if state not in ("sleeping", "left"):
                eligible.append(agent_id)
        return eligible

    # No explicit mentions -> fan-out to ACTIVE room participants only
    return [agent_id for agent_id, state in state_by_agent.items() if state == "active"]


class RoomMessageService:
    """Stateless service: all state lives in the Store."""

    def __init__(self, store, orchestrator):
        self.store = store
        self.orchestrator = orchestrator

    # ------------------------------------------------------------------
    # Message persistence
    # ------------------------------------------------------------------

    def post_message(
        self,
        *,
        room_id: str,
        sender_id: str,
        sender_type: str = "user",
        raw_content: str,
        parent_message_id: str | None = None,
    ) -> dict:
        """Persist a room message and return a dict with message + mention info.

        @mentions are resolved against real agents *before* content is
        redacted.  The persisted ``mention_agent_ids`` list is the source of
        truth used by the dispatch bridge.

        Unknown @mentions are surfaced in the response as ``unknown_mentions``
        so the caller can inform the user. They do NOT abort the post.
        """
        if not raw_content or not raw_content.strip():
            raise ValueError("message content must not be empty")
        if len(raw_content) > 32000:
            raise ValueError("message content exceeds 32 000 character limit")

        with self.store.transaction() as tx:
            # Validate room exists
            tx.chat_rooms.get(room_id)
            # Resolve mentions before redaction
            mention_result = _resolve_mentions(raw_content, tx)
            # Redact before persistence
            safe_content = redact(raw_content)
            message = RoomMessage(
                room_id=room_id,
                sender_type=sender_type,
                sender_id=sender_id,
                content=safe_content,
                mention_agent_ids=mention_result.resolved,
                parent_message_id=parent_message_id,
            )
            tx.room_messages.add(message)
            tx.log(
                "room_message_posted",
                actor=sender_id,
                room_id=room_id,
                message_id=message.id,
                mention_count=len(mention_result.resolved),
                unknown_mention_count=len(mention_result.unknown),
            )

        return {
            "message": message,
            "unknown_mentions": mention_result.unknown,
        }

    def list_messages(
        self,
        room_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list:
        """Return paginated messages for *room_id*, oldest first."""
        with self.store.transaction() as tx:
            tx.chat_rooms.get(room_id)
            return tx.room_messages.list(room_id=room_id, limit=limit, offset=offset)

    # ------------------------------------------------------------------
    # Mission dispatch bridge
    # ------------------------------------------------------------------

    def dispatch_mission(
        self,
        *,
        room_id: str,
        message_id: str,
        outcome: str,
        requested_by: str = "pascal",
        agent_ids: list | None = None,
    ) -> dict:
        """Convert a room message into one or more real Missions via the Orchestrator.

        Fan-out strategy (parallel):
        * If *agent_ids* is given explicitly, each agent gets its OWN Mission so
          tasks can execute concurrently within the existing semaphore budget.
        * Otherwise, target agents are resolved from the message's @mentions +
          room participant participation states.
        * If no targets can be determined, a single Mission with no agent
          assignment is created (normal Planner behaviour: defaulting to builder).

        The resulting mission IDs are written back onto the originating message
        (last-write wins if multiple; the audit log records all).

        Room membership and @mentions NEVER raise risk ceilings, capabilities,
        connector scopes, or credential rights.
        """
        with self.store.transaction() as tx:
            tx.chat_rooms.get(room_id)
            message = tx.room_messages.get(message_id)
            if message.room_id != room_id:
                raise ValueError("message does not belong to this room")
            participants = tx.room_participants.list(room_id=room_id, limit=10000)

        safe_outcome = redact(outcome)

        # Determine targets
        if agent_ids is not None:
            targets = agent_ids[:20]  # hard cap; never unlimited fan-out
        else:
            mention_result = _MentionResult(
                resolved=list(message.mention_agent_ids),
                unknown=[],
            )
            targets = _eligible_targets(mention_result, participants)[:20]

        # Parallel fan-out: one independent Mission per target agent.
        # Sequential chaining (Planner.plan default) would block Agent-B until
        # Agent-A completes; we submit separate Missions so the existing
        # asyncio.Semaphore distributes them concurrently.
        dispatched: list = []
        if targets:
            for agent_id in targets:
                request = MissionCreate(
                    outcome=safe_outcome,
                    constraints={
                        "room_id": room_id,
                        "source_message_id": message_id,
                        "requested_by": requested_by,
                        "assigned_agent": agent_id,
                    },
                    steps=[TaskSpec(objective=safe_outcome, agent_id=agent_id)],
                )
                mission = self.orchestrator.submit(request)
                dispatched.append({"mission_id": mission.id, "agent_id": agent_id})
                with self.store.transaction() as tx:
                    tx.log(
                        "room_mission_dispatched",
                        actor=requested_by,
                        room_id=room_id,
                        message_id=message_id,
                        mission_id=mission.id,
                        agent_id=agent_id,
                    )
        else:
            # No explicit targets -> single generic Mission
            request = MissionCreate(
                outcome=safe_outcome,
                constraints={
                    "room_id": room_id,
                    "source_message_id": message_id,
                    "requested_by": requested_by,
                },
            )
            mission = self.orchestrator.submit(request)
            dispatched.append({"mission_id": mission.id, "agent_id": None})
            with self.store.transaction() as tx:
                tx.log(
                    "room_mission_dispatched",
                    actor=requested_by,
                    room_id=room_id,
                    message_id=message_id,
                    mission_id=mission.id,
                    agent_id=None,
                )

        # Write last mission_id back to the originating message
        last_mission_id = dispatched[-1]["mission_id"]
        with self.store.transaction() as tx:
            msg = tx.room_messages.get(message_id)
            msg.mission_id = last_mission_id
            tx.room_messages.save(msg)

        return {
            "dispatched": dispatched,
            "message_id": message_id,
            "agent_ids": [d["agent_id"] for d in dispatched],
        }

    # ------------------------------------------------------------------
    # Result persistence back into the room (fan-in)
    # ------------------------------------------------------------------

    def post_result(
        self,
        *,
        room_id: str,
        mission_id: str,
        sender_id: str = "system",
        result_summary: str,
        parent_message_id: str | None = None,
    ) -> dict:
        """Post a system result message back into the room after mission completion.

        This is the fan-in end-point: called when the Orchestrator determines a
        mission has reached a terminal state (completed / failed / cancelled).
        The summary is always redacted before persistence.
        """
        safe_summary = redact(result_summary)
        result = self.post_message(
            room_id=room_id,
            sender_id=sender_id,
            sender_type="system",
            raw_content=safe_summary,
            parent_message_id=parent_message_id,
        )
        # Annotate the result message with the mission id
        with self.store.transaction() as tx:
            msg = tx.room_messages.get(result["message"].id)
            msg.mission_id = mission_id
            tx.room_messages.save(msg)
            tx.log(
                "room_result_posted",
                actor=sender_id,
                room_id=room_id,
                mission_id=mission_id,
                message_id=msg.id,
            )
        return result

    def notify_mission_outcome(self, *, mission_id: str, status: str, result: str) -> None:
        """Called when a mission reaches a terminal state.

        Looks up which room the mission originated from (via constraints) and
        posts a system result message.  If the mission has no ``room_id``
        constraint, this is a no-op (non-room missions are unaffected).

        This is the generic fan-in hook: it does NOT copy low-level audit events
        into the room - only the user-readable summary.
        """
        with self.store.transaction() as tx:
            try:
                mission = tx.missions.get(mission_id)
            except KeyError:
                return
            room_id = mission.constraints.get("room_id") if mission.constraints else None
            source_message_id = (
                mission.constraints.get("source_message_id") if mission.constraints else None
            )
            if not room_id:
                return

        summary = redact(result or f"Mission {mission_id} {status}.")
        self.post_result(
            room_id=room_id,
            mission_id=mission_id,
            sender_id="system",
            result_summary=summary,
            parent_message_id=source_message_id,
        )

    # ------------------------------------------------------------------
    # Participation management
    # ------------------------------------------------------------------

    def join_room(self, *, room_id: str, agent_id: str) -> RoomParticipant:
        """Add an agent to a room or restore them from 'left' state."""
        with self.store.transaction() as tx:
            tx.chat_rooms.get(room_id)
            tx.agents.get(agent_id)
            existing = tx.room_participants.list(room_id=room_id, agent_id=agent_id, limit=1)
            if existing:
                participant = existing[0]
                if participant.participation_state == "left":
                    participant.participation_state = "active"
                    participant.left_at = None
                    tx.room_participants.save(participant)
                    tx.log("room_rejoined", actor=agent_id, room_id=room_id)
                return participant
            participant = RoomParticipant(room_id=room_id, agent_id=agent_id)
            tx.room_participants.add(participant)
            tx.log("room_joined", actor=agent_id, room_id=room_id)
        return participant

    def leave_room(self, *, room_id: str, agent_id: str) -> RoomParticipant:
        """Mark agent as having left the room."""
        with self.store.transaction() as tx:
            participants = tx.room_participants.list(room_id=room_id, agent_id=agent_id, limit=1)
            if not participants:
                raise KeyError(f"agent {agent_id!r} is not in room {room_id!r}")
            participant = participants[0]
            participant.participation_state = "left"
            participant.left_at = now()
            tx.room_participants.save(participant)
            tx.log("room_left", actor=agent_id, room_id=room_id)
        return participant

    def set_participation_state(
        self, *, room_id: str, agent_id: str, state: str
    ) -> RoomParticipant:
        """Update participation state (active / listening / sleeping / left).

        This is an execution hint only.  It does NOT change the agent's
        risk ceiling, capabilities, connector access, or credential rights.
        """
        allowed = {"active", "listening", "sleeping", "left"}
        if state not in allowed:
            raise ValueError(f"state must be one of {sorted(allowed)}")
        with self.store.transaction() as tx:
            participants = tx.room_participants.list(room_id=room_id, agent_id=agent_id, limit=1)
            if not participants:
                raise KeyError(f"agent {agent_id!r} is not in room {room_id!r}")
            participant = participants[0]
            participant.participation_state = state
            if state == "left":
                participant.left_at = now()
            tx.room_participants.save(participant)
            tx.log(
                "room_participation_updated",
                actor=agent_id,
                room_id=room_id,
                state=state,
            )
        return participant

    def list_participants(self, room_id: str) -> list:
        with self.store.transaction() as tx:
            tx.chat_rooms.get(room_id)
            return tx.room_participants.list(room_id=room_id, limit=10000)
