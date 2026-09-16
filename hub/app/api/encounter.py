# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Encounter Generator API — LLM + deterministic XP budget."""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.agents.encounter_builder import EncounterBuilderAgent, BuildResult
from app.llm.ollama_client import OllamaClient
from app.config import get_settings
from app.db.repository import CampaignRepository
from app.rag.retriever import Retriever
from app.api.deps import get_repo

router = APIRouter(prefix="/encounter", tags=["encounter"])


class EncounterRequest(BaseModel):
    party_level: int = Field(..., ge=1, le=20)
    party_size: int = Field(..., ge=1, le=10)
    threat: str = Field(..., pattern="^(trivial|low|moderate|severe|extreme)$")
    theme: str = Field(..., min_length=1, max_length=200)


class EncounterMonsterResponse(BaseModel):
    name: str
    count: int
    level: int
    xp_each: int
    total_xp: int
    source_book: str


class EncounterResponse(BaseModel):
    target_xp: int
    total_xp: int
    party_level: int
    party_size: int
    threat: str
    theme: str
    monsters: list[EncounterMonsterResponse]


@router.post("/generate", response_model=EncounterResponse)
async def generate_encounter(
    request: EncounterRequest,
    repo: CampaignRepository = Depends(get_repo),
) -> EncounterResponse:
    settings = get_settings()
    llm = OllamaClient(settings.ollama_host)
    retriever = Retriever(repo)
    agent = EncounterBuilderAgent(llm, retriever)

    try:
        result: BuildResult = await agent.build(
            party_level=request.party_level,
            party_size=request.party_size,
            threat=request.threat,
            theme=request.theme,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        await llm.close()

    return EncounterResponse(
        target_xp=result.target_xp,
        total_xp=result.total_xp,
        party_level=result.party_level,
        party_size=result.party_size,
        threat=result.threat,
        theme=result.theme,
        monsters=[
            EncounterMonsterResponse(
                name=m.name,
                count=m.count,
                level=m.level,
                xp_each=m.xp_each,
                total_xp=m.total_xp,
                source_book=m.source_book,
            )
            for m in result.monsters
        ],
    )