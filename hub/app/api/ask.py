# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Ask/Stream endpoints — GM Q&A with WebSocket streaming.
"""


import logging
from typing import Literal

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError

from app.agents.solo_loop import SoloLoop
from app.api.campaign import build_solo_loop
from app.api.deps import get_repo
from app.api.security import websocket_authorized
from app.db.repository import CampaignRepository
from app.llm.orchestrator import LLMOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ask", tags=["gm"])


class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    # Literal rather than str: edition previously fell through to a silent
    # "search both editions" path for any unrecognised spelling. mode likewise.
    edition: Literal["1e", "2e", "both"] = "both"
    mode: Literal[
        "character", "npc", "monster", "boss", "map", "campaign", "encounter"
    ] | None = None
    history: list[list[str]] = Field(default_factory=list, max_length=20)
    # Bounded: this is a raw int, so a client could mint unbounded auto-fold
    # buckets in LLMOrchestrator._AUTO_COUNTS and cascade a negative or huge id
    # through the repository DELETEs.
    campaign_id: int = Field(1, ge=1, le=2147483647)


class AskResponse(BaseModel):
    answer: str
    backend: str  # "ollama" | "raw-excerpts"
    mode: str
    edition: str
    sources: list[dict]


# ──────────────────────────────────────────────────────────────
# Buffered /ask endpoint
# ──────────────────────────────────────────────────────────────

@router.post("", response_model=AskResponse)
async def ask_endpoint(
    request: AskRequest,
    repo: CampaignRepository = Depends(get_repo),
) -> AskResponse:
    orchestrator = LLMOrchestrator(repo)
    try:
        result = await orchestrator.generate(
            prompt=request.query,
            edition=request.edition,
            mode=request.mode,
            history=request.history,
            campaign_id=request.campaign_id,
        )
    finally:
        await orchestrator.close()
    return AskResponse(**result.__dict__)


# ──────────────────────────────────────────────────────────────
# WebSocket /stream endpoint
# ──────────────────────────────────────────────────────────────

class StreamEvent(BaseModel):
    type: str  # start | chunk | end | error
    backend: str | None = None
    mode: str | None = None
    edition: str | None = None
    text: str | None = None
    message: str | None = None
    sources: list[dict] = []


class SoloTurnStreamRequest(BaseModel):
    campaign_id: int
    action: str = Field(..., min_length=1, max_length=1000)
    actor: str = "player"
    seed: int | None = None


stream_router = APIRouter(tags=["gm"])


@router.websocket("/stream")
@stream_router.websocket("/stream")
async def stream_endpoint(
    websocket: WebSocket,
    repo: CampaignRepository = Depends(get_repo),
) -> None:
    await websocket.accept()
    orchestrator: LLMOrchestrator | None = None
    solo_loop: SoloLoop | None = None
    try:
        data = await websocket.receive_json()
        if not isinstance(data, dict):
            await websocket.send_json(
                StreamEvent(type="error", message="Expected JSON object.").model_dump()
            )
            return

        if "action" in data and ("campaign_id" in data or data.get("type") == "turn"):
            if not websocket_authorized(websocket):
                await websocket.send_json(
                    StreamEvent(type="error", message="Unauthorized.").model_dump()
                )
                return

            try:
                turn_req = SoloTurnStreamRequest(**data)
            except ValidationError as err:
                await websocket.send_json(
                    StreamEvent(type="error", message=f"Invalid turn request: {err}").model_dump()
                )
                return

            solo_loop = build_solo_loop(repo)

            async def _emit_turn_ws(event: dict) -> None:
                await websocket.send_json(event)

            try:
                await solo_loop.take_turn(
                    turn_req.campaign_id,
                    turn_req.action,
                    actor=turn_req.actor,
                    seed=turn_req.seed,
                    emit=_emit_turn_ws,
                )
            except ValueError as exc:
                await websocket.send_json(
                    StreamEvent(type="error", message=str(exc)).model_dump()
                )
            return

        request = AskRequest(**data)

        orchestrator = LLMOrchestrator(repo)
        # Send start event. backend is reported per frame from now on: the
        # orchestrator yields (backend, chunk), so an offline fallback is no
        # longer mislabelled as an Ollama answer.
        await websocket.send_json(StreamEvent(type="start", backend="ollama").model_dump())

        # Stream chunks
        backend = "ollama"
        async for backend, chunk in orchestrator.stream(
            prompt=request.query,
            edition=request.edition,
            mode=request.mode,
            history=request.history,
            campaign_id=request.campaign_id,
        ):
            await websocket.send_json(
                StreamEvent(type="chunk", text=chunk, backend=backend).model_dump()
            )

        # Citations come from the rows stream() already retrieved. This used to call
        # get_sources(), re-running the identical FTS5 query a second time per
        # stream connection.
        sources = orchestrator.retriever.extract_sources_from_context(
            orchestrator.last_context
        )
        await websocket.send_json(
            StreamEvent(
                type="end",
                backend=backend,
                mode=request.mode,
                edition=request.edition,
                sources=sources,
            ).model_dump()
        )

    except WebSocketDisconnect:
        pass
    except Exception:
        # Do not forward str(e) to the client: it leaks paths and internals.
        logger.exception("stream endpoint failed")
        await websocket.send_json(
            StreamEvent(type="error", message="An internal error occurred.").model_dump()
        )
    finally:
        # The orchestrator owns three httpx clients, each with its own socket
        # pool. stream_endpoint never closed them, so every stream connection
        # permanently leaked three connection pools plus their file handles.
        if orchestrator is not None:
            try:
                await orchestrator.close()
            except Exception:
                pass
        if solo_loop is not None:
            try:
                await solo_loop.close()
            except Exception:
                pass
        try:
            await websocket.close()
        except Exception:
            pass