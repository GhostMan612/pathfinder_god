# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Ask/Stream endpoints — GM Q&A with WebSocket streaming.
"""


from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.api.deps import get_repo
from app.db.repository import CampaignRepository
from app.llm.orchestrator import LLMOrchestrator

router = APIRouter(prefix="/ask", tags=["gm"])


class AskRequest(BaseModel):
    query: str
    edition: str = "both"
    mode: str | None = None
    history: list[list[str]] = []


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


stream_router = APIRouter(tags=["gm"])


@router.websocket("/stream")
@stream_router.websocket("/stream")
async def stream_endpoint(
    websocket: WebSocket,
    repo: CampaignRepository = Depends(get_repo),
) -> None:
    await websocket.accept()
    try:
        data = await websocket.receive_json()
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
        ):
            await websocket.send_json(
                StreamEvent(type="chunk", text=chunk, backend=backend).model_dump()
            )

        sources = await orchestrator.retriever.get_sources(
            request.query, edition=request.edition, k=5,
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
    except Exception as e:
        await websocket.send_json(
            StreamEvent(type="error", message=str(e)).model_dump()
        )
    finally:
        try:
            await websocket.close()
        except Exception:
            pass