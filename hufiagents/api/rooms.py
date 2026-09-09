"""HTTP surface for the Room->Runtime bridge (V1.3).

All endpoints are mounted under the prefix /rooms/{room_id}/ and are
protected by the global auth middleware in api/__init__.py.

Routes:
- GET  /rooms/{room_id}/messages              - paginated message list
- POST /rooms/{room_id}/messages              - post a new message
- POST /rooms/{room_id}/messages/{msg_id}/dispatch  - message -> Mission
- GET  /rooms/{room_id}/participants          - list participants
- POST /rooms/{room_id}/participants          - join room
- DELETE /rooms/{room_id}/participants/{agent_id}   - leave room
- PATCH  /rooms/{room_id}/participants/{agent_id}   - update participation state
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field


class MessageIn(BaseModel):
    sender_id: str = Field(min_length=1, max_length=200)
    sender_type: str = "user"
    content: str = Field(min_length=1, max_length=32000)
    parent_message_id: str | None = None


class DispatchIn(BaseModel):
    outcome: str = Field(min_length=1, max_length=16000)
    requested_by: str = "pascal"
    agent_ids: list[str] | None = None


class ParticipantIn(BaseModel):
    agent_id: str = Field(min_length=1, max_length=200)


class ParticipantStateIn(BaseModel):
    state: str = Field(min_length=1, max_length=50)


def router_for(app):
    """Return an APIRouter that closes over *app* for store/service access."""
    router = APIRouter()

    def _svc():
        return app.state.room_message_service

    @router.get("/rooms/{room_id}/messages")
    async def room_messages_list(
        room_id: str,
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ):
        try:
            return _svc().list_messages(room_id, limit=limit, offset=offset)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="room not found") from exc

    @router.post("/rooms/{room_id}/messages", status_code=201)
    async def room_messages_create(room_id: str, body: MessageIn):
        """Post a message; returns the persisted message and any unknown @mentions."""
        try:
            result = _svc().post_message(
                room_id=room_id,
                sender_id=body.sender_id,
                sender_type=body.sender_type,
                raw_content=body.content,
                parent_message_id=body.parent_message_id,
            )
            # result is {"message": RoomMessage, "unknown_mentions": [...]}
            return {
                "message": result["message"].model_dump(mode="json"),
                "unknown_mentions": result["unknown_mentions"],
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="room not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/rooms/{room_id}/messages/{message_id}/dispatch", status_code=202)
    async def room_messages_dispatch(room_id: str, message_id: str, body: DispatchIn):
        try:
            result = _svc().dispatch_mission(
                room_id=room_id,
                message_id=message_id,
                outcome=body.outcome,
                requested_by=body.requested_by,
                agent_ids=body.agent_ids,
            )
            return result
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (ValueError, PermissionError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except OverflowError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc

    @router.get("/rooms/{room_id}/participants")
    async def room_participants_list(room_id: str):
        try:
            return _svc().list_participants(room_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="room not found") from exc

    @router.post("/rooms/{room_id}/participants", status_code=201)
    async def room_participants_join(room_id: str, body: ParticipantIn):
        try:
            return _svc().join_room(room_id=room_id, agent_id=body.agent_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.delete("/rooms/{room_id}/participants/{agent_id}", status_code=200)
    async def room_participants_leave(room_id: str, agent_id: str):
        try:
            return _svc().leave_room(room_id=room_id, agent_id=agent_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.patch("/rooms/{room_id}/participants/{agent_id}")
    async def room_participants_state(room_id: str, agent_id: str, body: ParticipantStateIn):
        try:
            return _svc().set_participation_state(
                room_id=room_id, agent_id=agent_id, state=body.state
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    return router
