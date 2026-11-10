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
from app.agents.monster_builder import MonsterBuilderAgent
from app.agents.npc_compiler import NPCCompilerAgent
from app.agents.rules_lawyer import RulesLawyerAgent
from app.agents.world_builder import WorldBuilderAgent
from app.api.deps import get_repo
from app.api.security import require_auth
from app.config import get_settings
from app.db.repository import CampaignRepository
from app.llm.ollama_client import OllamaClient
from app.llm.orchestrator import LLMOrchestrator

router = APIRouter(prefix="/generate", tags=["gm"])


class BuildCharacterRequest(BaseModel):
    # Bounded: this was the only LLM-driving request model in the app with no
    # length limit at all, unlike GenerateRequest just below.
    prompt: str = Field(..., min_length=1, max_length=4000)


class BuildCharacterResponse(BaseModel):
    valid: bool
    character: dict | None = None
    errors: list[str] = []
    attempts: int = 1


class BuildNPCRequest(BaseModel):
    concept: str = Field(..., min_length=1, max_length=2000)
    campaign_id: int = Field(default=1, ge=1, le=2147483647)


class BuildNPCResponse(BaseModel):
    valid: bool
    npc: dict | None = None
    npc_id: int | None = None
    source: str = "llm"  # "llm" | "fallback"
    attempts: int = 1
    errors: list[str] = []


class BuildMonsterRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    level: int | None = Field(default=None, ge=1, le=20)
    party_level: int | None = Field(default=None, ge=1, le=20)


class BuildMonsterResponse(BaseModel):
    valid: bool
    monster: dict | None = None
    attempts: int = 1
    errors: list[str] = []


class BuildWorldRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    campaign_id: int = Field(default=1, ge=1, le=2147483647)


class BuildWorldResponse(BaseModel):
    valid: bool
    world: dict | None = None
    persisted: dict | None = None  # {"locations": n, "quests": n, "npcs": n}
    attempts: int = 1
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
        attempts=result.attempts,
    )


# ──────────────────────────────────────────────────────────────
# NPC Builder endpoint (LLM + Pydantic validation, persisted)
# ──────────────────────────────────────────────────────────────

@router.post("/npc", response_model=BuildNPCResponse)
async def build_npc_endpoint(
    request: BuildNPCRequest,
    repo: CampaignRepository = Depends(get_repo),
    user: dict = Depends(require_auth),
) -> BuildNPCResponse:
    agent = NPCCompilerAgent(repo)
    try:
        result = await agent.build(request.concept)
    finally:
        await agent.ollama.close()
    if not result.valid or result.npc is None:
        return BuildNPCResponse(
            valid=False, errors=result.errors, attempts=result.attempts, source=result.source
        )
    npc_dict = dict(result.npc.__dict__)
    npc_dict["class"] = result.npc.class_
    saved = await agent.save_npc_to_db(npc_dict, request.campaign_id)
    return BuildNPCResponse(
        valid=True,
        npc=npc_dict,
        npc_id=saved.get("id"),
        source=result.source,
        attempts=result.attempts,
        errors=result.errors,
    )


# ──────────────────────────────────────────────────────────────
# Monster / Boss Builder endpoints (LLM + Pydantic validation)
# Boss is the monster builder with the elite template, not a separate file.
# ──────────────────────────────────────────────────────────────

async def _build_monster_response(
    request: BuildMonsterRequest, *, elite: bool
) -> BuildMonsterResponse:
    settings = get_settings()
    llm = OllamaClient(settings.ollama_host)
    agent = MonsterBuilderAgent(llm)
    try:
        level = request.level if request.level is not None else request.party_level
        result = await agent.build(request.prompt, level=level, elite=elite)
    finally:
        await llm.close()
    return BuildMonsterResponse(
        valid=result.valid,
        monster=result.monster.model_dump(mode="python") if result.monster else None,
        attempts=result.attempts,
        errors=result.errors,
    )


@router.post("/monster", response_model=BuildMonsterResponse)
async def build_monster_endpoint(request: BuildMonsterRequest) -> BuildMonsterResponse:
    return await _build_monster_response(request, elite=False)


# Keep the existing prose /generate/{kind} route for kind="boss". The typed
# boss builder lives one path deeper so adding it cannot change the response
# shape of the already-published /generate/boss URL.
@router.post("/boss/statblock", response_model=BuildMonsterResponse)
async def build_boss_endpoint(request: BuildMonsterRequest) -> BuildMonsterResponse:
    return await _build_monster_response(request, elite=True)


# ──────────────────────────────────────────────────────────────
# World Builder endpoint (LLM + Pydantic validation, persisted)
# ──────────────────────────────────────────────────────────────

@router.post("/world", response_model=BuildWorldResponse)
async def build_world_endpoint(
    request: BuildWorldRequest,
    repo: CampaignRepository = Depends(get_repo),
    user: dict = Depends(require_auth),
) -> BuildWorldResponse:
    settings = get_settings()
    llm = OllamaClient(settings.ollama_host)
    agent = WorldBuilderAgent(llm)
    try:
        result = await agent.build(request.prompt)
    finally:
        await llm.close()
    if not result.valid or result.world is None:
        return BuildWorldResponse(
            valid=False, errors=result.errors, attempts=result.attempts
        )

    # Persist the structured world. Locations and quests have repo writers;
    # NPC givers are names only (no stat blocks), so they are referenced by
    # the quests, not created as NPC rows — persisted["npcs"] stays 0.
    persisted: dict[str, int] | None = {"locations": 0, "quests": 0, "npcs": 0}
    persist_errors: list[str] = []
    try:
        for settlement in result.world.settlements:
            repo.upsert_location(
                campaign_id=request.campaign_id,
                name=settlement.name,
                type_="settlement",
                description=settlement.description,
            )
            persisted["locations"] += 1
        for location in result.world.locations:
            repo.upsert_location(
                campaign_id=request.campaign_id,
                name=location.name,
                type_=location.type,
                description=location.description,
            )
            persisted["locations"] += 1
        for quest in result.world.quests:
            repo.upsert_quest(
                campaign_id=request.campaign_id,
                name=quest.name,
                status="active",
                giver_name=quest.giver,
                description=quest.objective,
                objectives=[{"description": quest.objective}],
                rewards=[{"description": quest.reward}] if quest.reward else [],
            )
            persisted["quests"] += 1
    except Exception as exc:  # persistence must not discard a built world
        persist_errors.append(f"World persistence failed: {exc}")
        persisted = None

    return BuildWorldResponse(
        valid=True,
        world=result.world.model_dump(mode="python"),
        persisted=persisted,
        attempts=result.attempts,
        errors=[*result.errors, *persist_errors],
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