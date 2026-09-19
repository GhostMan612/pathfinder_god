# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Loot Generator API — LLM concept + Rules Lawyer crafting validation."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.agents.loot_generator import LootBuildResult, LootGeneratorAgent
from app.agents.rules_lawyer import RulesLawyerAgent
from app.api.deps import get_repo
from app.config import get_settings
from app.db.repository import CampaignRepository
from app.llm.ollama_client import OllamaClient

router = APIRouter(prefix="/generate", tags=["gm"])


class LootRequest(BaseModel):
    prompt: str


class LootResponse(BaseModel):
    valid: bool
    item: dict | None = None
    craft_dc: int | None = None
    errors: list[str] = []


@router.post("/loot", response_model=LootResponse)
async def generate_loot(
    request: LootRequest,
    repo: CampaignRepository = Depends(get_repo),
) -> LootResponse:
    settings = get_settings()
    llm = OllamaClient(settings.ollama_host)
    lawyer = RulesLawyerAgent(repo)
    agent = LootGeneratorAgent(llm, lawyer)
    result: LootBuildResult = await agent.build(request.prompt)
    await llm.close()
    return LootResponse(
        valid=result.valid,
        item=result.item.model_dump(mode="python") if result.item else None,
        craft_dc=result.craft_dc,
        errors=result.errors,
    )
