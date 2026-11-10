# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""World Builder Agent — LLM campaign world + deterministic validation.

Same pattern as CharacterBuilderAgent:
1. LLM generates a complete campaign world JSON blueprint with
   format="json", retried up to 3 times by app.agents.json_builder with
   the validation error fed back.
2. WorldModel (Pydantic) validates the shape: non-empty settlements,
   factions, locations and quests, bounded strings throughout.
3. The /generate/world endpoint persists the world into the campaign
   repository (locations, quests, NPC givers by name); this agent itself
   only builds and validates, it never writes to the database.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from app.agents.json_builder import generate_validated_json
from app.config import get_settings

logger = logging.getLogger(__name__)


class WorldSettlement(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    type: Literal["village", "town", "city", "hamlet", "fortress", "other"] = "town"
    population: int | None = Field(default=None, ge=0, le=10_000_000)
    description: str = Field(default="", max_length=1000)


class WorldFaction(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    goal: str = Field(..., min_length=1, max_length=500)
    attitude: Literal["friendly", "hostile", "neutral", "unknown"] = "unknown"
    relationships: list[str] = Field(default_factory=list, max_length=10)


class WorldLocation(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    type: Literal["settlement", "dungeon", "wilderness", "planar", "other"] = "other"
    description: str = Field(default="", max_length=1000)


class WorldQuest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    giver: str = Field(..., min_length=1, max_length=120)
    objective: str = Field(..., min_length=1, max_length=500)
    reward: str = Field(default="", max_length=500)


class WorldModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    premise: str = Field(..., min_length=1, max_length=2000)
    settlements: list[WorldSettlement] = Field(..., min_length=1, max_length=20)
    factions: list[WorldFaction] = Field(..., min_length=1, max_length=20)
    locations: list[WorldLocation] = Field(..., min_length=1, max_length=30)
    quests: list[WorldQuest] = Field(..., min_length=1, max_length=20)
    hooks: list[str] = Field(default_factory=list, max_length=10)


@dataclass
class WorldBuildResult:
    valid: bool
    world: WorldModel | None
    errors: list[str] = field(default_factory=list)
    attempts: int = 1


SYSTEM_PROMPT = """You are a Pathfinder 2e world builder.
Output ONLY a JSON object matching this schema exactly. No markdown, no commentary.

Required fields:
- name: world/campaign name (string)
- premise: one or two paragraphs, the campaign premise (string)
- settlements: array of at least one {name, type (village/town/city/hamlet/fortress/other), population (integer or null), description}
- factions: array of at least one {name, goal, attitude (friendly/hostile/neutral/unknown), relationships (array of strings)}
- locations: array of at least one {name, type (settlement/dungeon/wilderness/planar/other), description}
- quests: array of at least one {name, giver (an NPC name), objective, reward}
- hooks: array of strings (adventure hooks)

Rules:
- Every list must be non-empty; every name must be a distinct, evocative name
- Quest givers should be named NPCs who could plausibly live in one of the settlements
- Keep descriptions to a sentence or two each
"""


class WorldBuilderAgent:
    def __init__(self, llm):
        self._llm = llm
        self._settings = get_settings()

    async def build(self, prompt: str) -> WorldBuildResult:
        full_prompt = SYSTEM_PROMPT + "\n\nUser request: " + prompt.strip()
        validated: dict[str, WorldModel] = {}

        def _validate(data: object) -> list[str]:
            if not isinstance(data, dict):
                return ["LLM returned a JSON value that is not an object"]
            try:
                validated["model"] = WorldModel.model_validate(data)
            except Exception as exc:
                return [f"Schema validation failed: {exc}"]
            return []

        outcome = await generate_validated_json(
            self._llm,
            prompt=full_prompt,
            model=self._settings.model_for("builders"),
            temperature=0.3,
            num_predict=1500,
            validate=_validate,
        )
        if outcome.data is None or "model" not in validated:
            logger.info("WorldBuilder validation failed: %s", outcome.errors)
            return WorldBuildResult(
                False, None, outcome.errors or ["LLM returned no valid JSON object"],
                attempts=outcome.attempts,
            )
        return WorldBuildResult(True, validated["model"], outcome.errors, attempts=outcome.attempts)
