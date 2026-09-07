from hufiagents.contracts import State

TERMINAL = {State.failed, State.completed, State.cancelled}
ALLOWED = {
    State.queued: {State.planning},
    State.planning: {State.running, State.blocked, State.failed},
    State.running: {State.waiting_approval, State.review, State.failed, State.retrying},
    State.waiting_approval: {State.running, State.cancelled, State.failed},
    State.blocked: {State.queued, State.cancelled},
    State.review: {State.completed, State.retrying, State.failed},
    State.retrying: {State.queued},
    State.failed: set(),
    State.completed: set(),
    State.cancelled: set(),
}


def validate_transition(source: State, target: State, *, recovery=False, cancel=False):
    # §7 explicitly permits cancellation everywhere and recovery from planning;
    # these exceptional edges require explicit intent (ADR-008).
    if cancel and source not in TERMINAL and target == State.cancelled:
        return
    if recovery and source == State.planning and target == State.retrying:
        return
    if target not in ALLOWED[source]:
        raise ValueError(f"illegal transition: {source} -> {target}")
