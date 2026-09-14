# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Generate endpoints — Typed generators (character, npc, monster, boss, map, campaign, encounter).
"""

from fastapi import APIRouter, HTTPException, Path, Depends
from pydantic import BaseModel

from app.api.deps import get_repo
from app.db.repository import CampaignRepository
from app.llm.orchestrator import LLMOrchestrator

router = APIRouter(prefix="/generate", tags=["gm"])


class GenerateRequest(BaseModel):
    prompt: str
    edition: str = "both"


class GenerateResponse(BaseModel):
    answer: str
    backend: str
    mode: str
    edition: str
    sources: list[dict]


VALID_KINDS = {
    "character",
    "npc",
    "monster",
    "boss",
    "map",
    "campaign",
    "encounter",
}


# ──────────────────────────────────────────────────────────────
# Generate endpoint
# ──────────────────────────────────────────────────────────────

@router.post("/{kind}", response_model=GenerateResponse)
async def generate_endpoint(
    kind: str = Path(..., description="Generator kind"),
    request: GenerateRequest = ...,
    repo: CampaignRepository = Depends(get_repo),
) -> GenerateResponse:
    if kind not in VALID_KINDS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown kind: {kind}. Valid: {', '.join(sorted(VALID_KINDS))}",
        )

    orchestrator = LLMOrchestrator(repo)
    result = await orchestrator.generate(
        prompt=request.prompt,
        edition=request.edition,
        mode=kind,
    )
    return GenerateResponse(
        answer=result.answer,
        backend=result.backend,
        mode=result.mode,
        edition=result.edition,
        sources=result.sources,
    )