# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Combat API endpoints — Deterministic combat resolution endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.combat_tracker import CombatTrackerAgent, StrikeResult
from app.api.deps import get_repo
from app.db.repository import CampaignRepository

router = APIRouter(prefix="/combat", tags=["combat"])


class StrikeRequest(BaseModel):
    attack_roll: int
    target_ac: int
    damage_roll: int
    target_hp: int
    target_temp_hp: int = 0


class StrikeResponse(BaseModel):
    outcome: str
    damage_dealt: int
    new_hp: int
    new_temp_hp: int
    notes: str


class ConditionItem(BaseModel):
    name: str
    value: int = 1
    duration_rounds: int | None = None


class EndTurnRequest(BaseModel):
    conditions: list[ConditionItem] = []
    current_hp: int = 0


class EndTurnResponse(BaseModel):
    conditions: list[ConditionItem]
    notes: str = ""
    damage_taken: int = 0


@router.post("/resolve-strike", response_model=StrikeResponse)
async def resolve_strike(request: StrikeRequest) -> StrikeResponse:
    """Resolve a single strike using deterministic PF2e math."""
    result: StrikeResult = CombatTrackerAgent.resolve_strike(
        attack_roll=request.attack_roll,
        target_ac=request.target_ac,
        damage_roll=request.damage_roll,
        target_hp=request.target_hp,
        target_temp_hp=request.target_temp_hp,
    )
    return StrikeResponse(
        outcome=result.outcome,
        damage_dealt=result.damage_dealt,
        new_hp=result.new_hp,
        new_temp_hp=result.new_temp_hp,
        notes=result.notes,
    )


@router.post("/end-turn", response_model=EndTurnResponse)
async def end_turn(request: EndTurnRequest) -> EndTurnResponse:
    """Process end-of-turn condition updates."""
    conditions = [c.model_dump() for c in request.conditions]
    updated, notes, damage_taken = CombatTrackerAgent.end_of_turn(
        conditions, current_hp=request.current_hp
    )
    return EndTurnResponse(
        conditions=[ConditionItem(**c) for c in updated],
        notes=notes,
        damage_taken=damage_taken,
    )


class CombatSceneIn(BaseModel):
    campaign_id: int = 1
    scene: str = Field(..., max_length=4000)


class CombatSceneOut(BaseModel):
    campaign_id: int
    scene: str


@router.post("/scene", response_model=CombatSceneOut)
async def set_scene(
    request: CombatSceneIn,
    repo: CampaignRepository = Depends(get_repo),
) -> CombatSceneOut:
    """Persist the current combat scene so the live GM can reason about it."""
    repo.set_combat_json(request.campaign_id, request.scene)
    return CombatSceneOut(campaign_id=request.campaign_id, scene=request.scene)


@router.get("/scene", response_model=CombatSceneOut)
async def get_scene(
    campaign_id: int = 1,
    repo: CampaignRepository = Depends(get_repo),
) -> CombatSceneOut:
    return CombatSceneOut(campaign_id=campaign_id, scene=repo.get_combat_json(campaign_id))