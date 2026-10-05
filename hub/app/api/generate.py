# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Generate endpoints — Typed generators (character, npc, monster, boss, map, campaign, encounter).
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from app.agents.character_builder import BuildResult, CharacterBuilderAgent
from app.agents.rules_lawyer import RulesLawyerAgent
from app.api.deps import get_repo
from app.config import get_settings
from app.db.repository import CampaignRepository
from app.llm.ollama_client import OllamaClient
from app.llm.orchestrator import LLMOrchestrator

router = APIRouter(prefix="/generate", tags=["gm"])


class BuildCharacterRequest(BaseModel):
    prompt: str


class BuildCharacterResponse(BaseModel):
    valid: bool
    character: dict | None = None
    errors: list[str] = []


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=4000)
    edition: Literal["1e", "2e", "both"] = "both"


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
# Character Builder endpoint (LLM + Rules Lawyer validation)
# ──────────────────────────────────────────────────────────────

@router.post("/character", response_model=BuildCharacterResponse)
async def build_character_endpoint(
    request: BuildCharacterRequest,
    repo: CampaignRepository = Depends(get_repo),
) -> BuildCharacterResponse:
    settings = get_settings()
    llm = OllamaClient(settings.ollama_host)
    lawyer = RulesLawyerAgent(repo)
    agent = CharacterBuilderAgent(llm, lawyer)
    try:
        result: BuildResult = await agent.build(request.prompt)
    finally:
        # try/finally: _validate_with_lawyer runs outside any internal try, so
        # an exception there leaked the httpx client and its socket pool.
        await llm.close()
    return BuildCharacterResponse(
        valid=result.valid,
        character=result.character.model_dump(mode="python") if result.character else None,
        errors=result.errors,
    )


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
    try:
        result = await orchestrator.generate(
            prompt=request.prompt,
            edition=request.edition,
            mode=kind,
        )
    finally:
        await orchestrator.close()
    return GenerateResponse(
        answer=result.answer,
        backend=result.backend,
        mode=result.mode,
        edition=result.edition,
        sources=result.sources,
    )