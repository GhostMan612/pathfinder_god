# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Solo campaign loop — server-owned turn state for one-player play.

The GM answers questions (``LLMOrchestrator``), but it could not *run* a
game: combat was a stateless calculator, HP/initiative lived in an opaque
``combat_json`` string the client pushed, and there was no turn, round, or
quest state on the server at all. This module is the missing core:

- ``SoloLoop.create_campaign`` — campaign row + solo_state + opening
  location/quest (via the world builder) + hero (via the NPC builder).
- ``SoloLoop.take_turn`` — one player action, resolved deterministically
  and persisted: classify, roll dice (seeded, replayable), resolve strikes
  through ``CombatTrackerAgent``, advance initiative/round, run
  end-of-turn conditions and recovery checks, apply validated
  quest/location changes, narrate, persist the turn + decision + note.
- ``SoloLoop.start_combat`` / ``end_turn`` / ``end_combat``.

The invariant: dice and HP are always deterministic code. The LLM only
narrates and proposes quest/location changes, which are then validated
against entities that actually exist in this campaign. If the LLM is
down, the turn still resolves with template narration and the same dice
— the game never invents an HP or dice result.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import weakref
import zlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agents.combat_tracker import (
    CombatTrackerAgent,
    dying_value,
    gain_dying,
    wounded_value,
)
from app.agents.dice_utils import roll_dice
from app.agents.json_builder import generate_validated_json
from app.config import get_settings
from app.db.repository import CampaignRepository
from app.llm.ollama_client import OllamaClient

logger = logging.getLogger(__name__)

TurnEmitter = Callable[[dict[str, Any]], Awaitable[None]]


async def _emit_turn_event(
    emit: TurnEmitter | None, event: dict[str, Any]
) -> None:
    if emit is None:
        return
    try:
        await emit(event)
    except Exception:
        logger.debug("turn event sink failed", exc_info=True)


def _narration_chunks(text: str) -> list[str]:
    value = (text or "").strip()
    if not value:
        return []
    chunks: list[str] = []
    start = 0
    for match in re.finditer(r"[.!?]+(?:\s+|$)", value):
        end = match.end()
        chunks.append(value[start:end])
        start = end
    if start < len(value):
        chunks.append(value[start:])
    return chunks

# ──────────────────────────────────────────────────────────────
# Deterministic play constants (documented, not hidden in prompts)
#
# A solo hero has no character sheet on the server yet — the spoke syncs
# sheets into party_members.stats_json, but its shape is not a contract
# the loop can rely on. Until a sheet parser lands, hero strikes use these
# fixed, recorded values so every turn is reproducible from its seed.
# ──────────────────────────────────────────────────────────────
HERO_ATTACK_BONUS_BASE = 4
HERO_DAMAGE_DICE = "1d8+2"
HERO_SKILL_MODIFIER = 3
SKILL_CHECK_DC = 15
REST_HEAL_DICE = "1d8"
HERO_INITIATIVE_BONUS = 2
MONSTER_INITIATIVE_BONUS = 1

# One turn gate per campaign, scoped to the running event loop. The API creates
# a fresh SoloLoop per request, so a per-instance lock would not coordinate two
# simultaneous requests. This keeps state mutations serialized in this process;
# reserve_turn_num() is still the database-level guard for turn numbering.
_TURN_LOCKS: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def _campaign_turn_lock(campaign_id: int) -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    by_campaign = _TURN_LOCKS.get(loop)
    if by_campaign is None:
        by_campaign = {}
        _TURN_LOCKS[loop] = by_campaign
    lock = by_campaign.get(campaign_id)
    if lock is None:
        lock = asyncio.Lock()
        by_campaign[campaign_id] = lock
    return lock


def hero_max_hp(level: int) -> int:
    """Default hero HP when no sheet HP is stored: 20 + 5 per level past 1."""
    return 20 + 5 * max(0, int(level or 1) - 1)


def _hero_hp_from_stats(stats: dict | None, level: int) -> int:
    """Best-effort HP from a synced character sheet, else the default."""
    if isinstance(stats, dict):
        for key in ("max_hp", "hp", "hit_points", "current_hp"):
            value = stats.get(key)
            if isinstance(value, int) and value > 0:
                return value
    return hero_max_hp(level)


def _encounter_monster_ac(level: int, template: str = "normal") -> int:
    """Armor Class for an encounter-built monster.

    EncounterMonster carries no AC, so derive it with the same house
    formula the deterministic fallbacks use (12 + level) plus the
    encounter template's AC modifier (elite +2, weak -2). A flat AC for
    every creature made low-level foes too hard to hit and high-level
    ones too easy.
    """
    from app.agents.encounter_builder import TEMPLATE_MODIFIERS

    key = (template or "normal").lower()
    modifier = int(TEMPLATE_MODIFIERS.get(key, {}).get("ac", 0))
    return 12 + int(level or 1) + modifier


class TurnQuestUpdate(BaseModel):
    quest_name: str = Field(..., min_length=1, max_length=120)
    objective: str = Field(..., min_length=1, max_length=500)
    completed: bool = False


class TurnOutcomeModel(BaseModel):
    """Structured outcome the LLM proposes for one turn.

    Everything here is a *proposal*: quest/location changes are checked
    against the campaign's real entities before they are applied, and the
    dice/HP fields in the returned TurnResult come from deterministic code,
    never from this model.
    """

    kind: Literal["attack", "skill", "move", "talk", "rest", "other"] = "other"
    target: str | None = Field(default=None, max_length=120)
    skill: str | None = Field(default=None, max_length=60)
    location: str | None = Field(default=None, max_length=120)
    quest_update: TurnQuestUpdate | None = None
    narration_hint: str = Field(default="", max_length=1000)
    choices: list[str] = Field(default_factory=list, max_length=3)


@dataclass
class TurnResult:
    campaign_id: int
    turn_num: int
    narration: str
    dice_rolls: list[dict]
    hp_changes: list[dict]
    conditions: list[dict]
    quest_updates: list[dict]
    location: str | None
    phase: str
    round: int
    active_combatant: str | None
    choices: list[str]
    seed: int
    source: str  # "llm" | "fallback"
    kind: str = "other"
    encounter: dict | None = None

    def to_dict(self) -> dict:
        return {
            "campaign_id": self.campaign_id,
            "turn_num": self.turn_num,
            "narration": self.narration,
            "dice_rolls": self.dice_rolls,
            "hp_changes": self.hp_changes,
            "conditions": self.conditions,
            "quest_updates": self.quest_updates,
            "location": self.location,
            "phase": self.phase,
            "round": self.round,
            "active_combatant": self.active_combatant,
            "choices": self.choices,
            "seed": self.seed,
            "source": self.source,
            "kind": self.kind,
            "encounter": self.encounter,
        }


@dataclass
class CombatStartResult:
    campaign_id: int
    phase: str
    round: int
    combatants: list[dict]
    active_combatant: str | None
    encounter_id: int | None = None

    def to_dict(self) -> dict:
        return {
            "campaign_id": self.campaign_id,
            "phase": self.phase,
            "round": self.round,
            "combatants": self.combatants,
            "active_combatant": self.active_combatant,
            "encounter_id": self.encounter_id,
        }


# ──────────────────────────────────────────────────────────────
# Action classification (deterministic, keyword-based)
# ──────────────────────────────────────────────────────────────

_ATTACK_RE = re.compile(r"\b(attack|strike|hit|swing|slash|stab|shoot|cast|fire)\b", re.IGNORECASE)
_SKILL_RE = re.compile(
    r"\b(stealth|perception|search|investigate|climb|swim|jump|sneak|hide|listen|"
    r"diplomacy|intimidate|deception|survival|nature|arcana|religion|medicine|"
    r"craft|thievery|acrobatics|athletics|check)\b",
    re.IGNORECASE,
)
_MOVE_RE = re.compile(r"\b(move|go|enter|leave|travel|walk|run|head|flee|retreat|advance)\b", re.IGNORECASE)
_TALK_RE = re.compile(r"\b(talk|speak|say|ask|tell|negotiate|persuade|greet|question)\b", re.IGNORECASE)
_REST_RE = re.compile(r"\b(rest|sleep|camp|recover|heal|bandage|treat wounds)\b", re.IGNORECASE)

# Encounter detection is deliberately verb-first and separate from the turn
# classifier: "I open the door" is an exploration action, but it must still
# create the door encounter before the normal resolver runs.
_DOOR_ACTION_RE = re.compile(
    r"\b(?:open(?:s|ed|ing)?|unlock(?:s|ed|ing)?|knock(?:s|ed|ing)?\s+on|"
    r"push(?:es|ed|ing)?|enter(?:s|ed|ing)?|force(?:s|d|ing)?)\b"
    r"[^.!?]{0,60}\b(?P<target>doors?|gates?|portals?)\b",
    re.IGNORECASE,
)
_LOOT_ACTION_RE = re.compile(
    r"\b(?:search(?:es|ed|ing)?|loot(?:s|ed|ing)?|open(?:s|ed|ing)?|"
    r"pry(?:ing|ies|ied)?|ransack(?:s|ed|ing)?|inspect(?:s|ed|ing)?)\b"
    r"[^.!?]{0,60}\b"
    r"(?P<target>chests?|coffers?|caches?|piles?|satchels?|crates?|corpses?)\b",
    re.IGNORECASE,
)
_TRAP_ACTION_RE = re.compile(
    r"\b(?:disarm(?:s|ed|ing)?|trigger(?:s|ed|ing)?|"
    r"step(?:s|ped|ping)?\s+on|avoid(?:s|ed|ing)?|detect(?:s|ed|ing)?|"
    r"find|spot(?:s|ted|ting)?)\b[^.!?]{0,60}"
    r"\b(?P<target>traps?|snares?|tripwires?)\b",
    re.IGNORECASE,
)
_TRAP_ONE_ROLL_RE = re.compile(
    r"\b(?:disarm(?:s|ed|ing)?|trigger(?:s|ed|ing)?|"
    r"step(?:s|ped|ping)?\s+on|avoid(?:s|ed|ing)?)\b",
    re.IGNORECASE,
)
_TRAP_MULTI_RE = re.compile(
    r"\b(begin|start|continue|work\s+on|take\s+(?:my|the)\s+time|"
    r"carefully|slowly)\b",
    re.IGNORECASE,
)
_NPC_ACTION_RE = re.compile(
    r"\b(?:talk(?:s|ed|ing)?|speak(?:s|ing)?|greet(?:s|ed|ing)?|"
    r"ask(?:s|ed|ing)?|hail(?:s|ed|ing)?|question(?:s|ed|ing)?|"
    r"address(?:es|ed|ing)?)\b"
    r"(?:\s+(?:to|with|at))?\s+(?P<target>[^,.!?]{1,60})",
    re.IGNORECASE,
)
_NPC_NON_TARGETS = {
    "about",
    "directions",
    "for",
    "hello",
    "hi",
    "hey",
    "information",
    "news",
    "question",
    "questions",
    "the weather",
    "weather",
}


def _clean_encounter_target(raw: str | None) -> str | None:
    """Trim a detected NPC phrase to the name/noun the player addressed."""
    if not raw:
        return None
    target = raw.strip(" .!?")
    target = re.split(
        r"\b(?:about|for|regarding)\b", target, maxsplit=1, flags=re.IGNORECASE
    )[0]
    target = re.sub(r"^(?:the|a|an)\s+", "", target, flags=re.IGNORECASE)
    target = target.strip(" .!?")
    if not target or target.lower() in _NPC_NON_TARGETS:
        return None
    return target


def detect_encounter_action(action: str) -> tuple[str, str | None] | None:
    """Return ``(kind, target)`` when a player action names an encounter.

    Pure and regex-based, matching the style of ``classify_action``. The
    function never consults the database; the caller refines the target against
    the campaign's entities and creates the encounter through the repository.
    """
    text = action or ""
    match = _DOOR_ACTION_RE.search(text)
    if match:
        return "door", match.group("target").lower()
    match = _LOOT_ACTION_RE.search(text)
    if match:
        return "loot", match.group("target").lower()
    match = _TRAP_ACTION_RE.search(text)
    if match:
        return "trap", match.group("target").lower()
    match = _NPC_ACTION_RE.search(text)
    if match:
        target = _clean_encounter_target(match.group("target"))
        if target:
            return "npc", target
    return None


def classify_action(action: str) -> str:
    """Classify a player action without any LLM call."""
    text = action or ""
    if _ATTACK_RE.search(text):
        return "attack"
    if _REST_RE.search(text):
        return "rest"
    if _SKILL_RE.search(text):
        return "skill"
    if _TALK_RE.search(text):
        return "talk"
    if _MOVE_RE.search(text):
        return "move"
    return "other"


class SoloLoop:
    """Server-owned solo campaign loop for one campaign repository."""

    def __init__(
        self,
        repo: CampaignRepository,
        llm: Any | None = None,
        orchestrator: Any | None = None,
    ):
        self.repo = repo
        self._llm = llm
        self._orchestrator = orchestrator
        self._settings = get_settings()

    # ── LLM plumbing ──────────────────────────────────────────

    @property
    def llm(self) -> OllamaClient:
        if self._llm is None:
            self._llm = OllamaClient(self._settings.ollama_host)
        return self._llm

    async def close(self) -> None:
        for holder in (self._llm, self._orchestrator):
            client = getattr(holder, "ollama", None)
            if client is not None:
                try:
                    await client.close()
                except Exception:
                    logger.debug("failed to close solo loop client", exc_info=True)
        # An injected orchestrator owns its own close(); the loop never
        # closes a client it did not create.
        if self._orchestrator is not None and hasattr(self._orchestrator, "close"):
            try:
                await self._orchestrator.close()
            except Exception:
                logger.debug("failed to close solo loop orchestrator", exc_info=True)

    # ── Campaign creation ─────────────────────────────────────

    async def create_campaign(
        self,
        name: str,
        edition: str = "2e",
        premise: str = "",
        hero_prompt: str | None = None,
    ) -> dict:
        """Create a solo campaign and open it in exploration phase.

        The world builder supplies the opening location and first quest when
        the LLM answers; when it does not, a default location + quest are
        used so creation never fails on a downed LLM. The hero is built the
        same way (NPC builder, whose own fallback is the template).
        """
        campaign = self.repo.create_campaign(name, edition)
        campaign_id = campaign.id
        self.repo.ensure_solo_state(campaign_id)
        if premise:
            self.repo.update_campaign_summary(campaign_id, premise)

        location_name = "Trailhead Village"
        location_id: int | None = None
        quest_name = "First Steps"
        world_source = "fallback"

        # World first: it defines where the campaign opens and what the
        # first quest is. Its builder never writes to the DB itself.
        try:
            from app.agents.world_builder import WorldBuilderAgent

            world = await WorldBuilderAgent(self.llm).build(
                premise or f"Create a world for a campaign called {name}."
            )
            if world.valid and world.world is not None:
                world_source = "llm"
                for settlement in world.world.settlements:
                    self.repo.upsert_location(
                        campaign_id=campaign_id,
                        name=settlement.name,
                        type_="settlement",
                        description=settlement.description,
                    )
                for location in world.world.locations:
                    self.repo.upsert_location(
                        campaign_id=campaign_id,
                        name=location.name,
                        type_=location.type,
                        description=location.description,
                    )
                for quest in world.world.quests:
                    self.repo.upsert_quest(
                        campaign_id=campaign_id,
                        name=quest.name,
                        status="active",
                        giver_name=quest.giver,
                        description=quest.objective,
                        objectives=[{"description": quest.objective}],
                        rewards=[{"description": quest.reward}] if quest.reward else [],
                    )
                first = (
                    world.world.settlements[0].name
                    if world.world.settlements
                    else world.world.locations[0].name
                )
                location_name = first
                quest_name = world.world.quests[0].name
        except Exception as exc:  # LLM down: fall through to defaults.
            logger.warning("Solo campaign world build failed: %s", exc)

        if world_source == "fallback":
            location_id = self.repo.upsert_location(
                campaign_id=campaign_id,
                name=location_name,
                type_="settlement",
                description="Where the journey begins.",
            )
            self.repo.upsert_quest(
                campaign_id=campaign_id,
                name=quest_name,
                status="active",
                description="Begin the journey.",
                objectives=[{"description": "Explore the starting location"}],
                rewards=[],
            )
        else:
            found = next(
                (loc for loc in self.repo.get_locations(campaign_id) if loc.name == location_name),
                None,
            )
            location_id = found.id if found else None

        if location_id is not None:
            self.repo.set_current_location(campaign_id, location_id)
        self.repo.append_event(
            campaign_id,
            "campaign_started",
            summary=f"Campaign started in {location_name}",
            location_id=location_id,
            data={
                "name": name,
                "edition": edition,
                "premise": premise,
                "world_source": world_source,
            },
        )

        # Hero: the NPC builder returns a valid stat block in all normal
        # cases (LLM, else its marked template fallback).
        hero_name: str | None = None
        if hero_prompt:
            try:
                from app.agents.npc_compiler import NPCCompilerAgent

                agent = NPCCompilerAgent(self.repo, llm=self.llm)
                result = await agent.build(hero_prompt)
                if result.valid and result.npc is not None:
                    npc = result.npc
                    await agent.save_npc_to_db(dict(npc.__dict__), campaign_id)
                    self.repo.upsert_party_member(
                        campaign_id=campaign_id,
                        name=npc.name,
                        class_=npc.class_,
                        level=npc.level,
                        ancestry=npc.ancestry,
                        background=npc.background,
                    )
                    hero_name = npc.name
            except Exception as exc:
                logger.warning("Solo campaign hero build failed: %s", exc)

        opening = await self._narrate_opening(
            name, premise, location_name, quest_name, hero_name, world_source
        )
        return {
            "campaign_id": campaign_id,
            "name": name,
            "edition": edition,
            "location": location_name,
            "quest": quest_name,
            "hero": hero_name,
            "opening_narration": opening,
            "source": world_source,
        }

    async def _narrate_opening(
        self, name: str, premise: str, location: str, quest: str, hero: str | None, source: str
    ) -> str:
        prompt = (
            "You are the Pathfinder GM opening a solo campaign. "
            f"Campaign: {name}. Premise: {premise or '(none given)'} "
            f"Opening location: {location}. First quest: {quest}. "
            f"Hero: {hero or 'an unnamed wanderer'}. "
            "Narrate the opening scene in 2-4 sentences, second person, "
            "and end by asking what the hero does."
        )
        try:
            text = await self._generate_narration(prompt, campaign_id=0)
            if text and text.strip():
                return text.strip()
        except Exception as exc:
            logger.warning("Opening narration failed: %s", exc)
        hero_bit = f"{hero}, you" if hero else "You"
        return (
            f"{hero_bit} arrive in {location} as the campaign '{name}' begins. "
            f"Your first task is '{quest}'. What do you do?"
        )

    async def _generate_narration(self, prompt: str, campaign_id: int) -> str:
        """GM narration, grounded in the turn, via orchestrator or raw LLM."""
        if self._orchestrator is not None:
            result = await self._orchestrator.generate(
                prompt=prompt, edition="2e", mode=None, campaign_id=campaign_id
            )
            return result.answer
        return await self.llm.generate(
            prompt=prompt,
            model=self._settings.model_for("chat"),
            temperature=0.7,
            num_predict=400,
        )

    # ── Turn resolution ───────────────────────────────────────

    def _turn_seed(self, campaign_id: int, turn_num: int, seed: int | None) -> int:
        """Deterministic per-turn seed: explicit seed wins, else CRC32 of
        campaign:turn so replaying a turn reproduces its dice exactly."""
        if seed is not None:
            return int(seed)
        return zlib.crc32(f"{campaign_id}:{turn_num}".encode())

    async def take_turn(
        self,
        campaign_id: int,
        action: str,
        actor: str = "player",
        seed: int | None = None,
        emit: TurnEmitter | None = None,
    ) -> TurnResult:
        """Resolve one player action, serialized with other state changes."""
        async with _campaign_turn_lock(campaign_id):
            return await self._take_turn_locked(
                campaign_id, action, actor=actor, seed=seed, emit=emit
            )

    async def _take_turn_locked(
        self,
        campaign_id: int,
        action: str,
        actor: str = "player",
        seed: int | None = None,
        emit: TurnEmitter | None = None,
    ) -> TurnResult:
        if not self.repo.campaign_exists(campaign_id):
            raise ValueError(f"no campaign {campaign_id}")
        state = self.repo.ensure_solo_state(campaign_id)
        # Reserve the number up front: the seed is derived from it, and the
        # locked counter guarantees no two concurrent turns share a number.
        turn_num = self.repo.reserve_turn_num(campaign_id)
        turn_seed = self._turn_seed(campaign_id, turn_num, seed)
        rng = random.Random(turn_seed)
        await _emit_turn_event(
            emit,
            {
                "type": "start",
                "campaign_id": campaign_id,
                "turn_num": turn_num,
                "phase": state.phase,
                "round": state.round_num,
            },
        )

        party = self.repo.get_party(campaign_id)
        combatants = self.repo.get_combatants(campaign_id, active_only=True)
        quests = self.repo.get_quests(campaign_id)
        locations = self.repo.get_locations(campaign_id)
        chronicle = self.repo.get_campaign_summary(campaign_id)

        kind = classify_action(action)
        dice_rolls: list[dict] = []
        hp_changes: list[dict] = []
        quest_updates: list[dict] = []
        notes: list[str] = []
        emitted_dice = 0
        emitted_hp = 0
        emitted_encounter = False
        encounter_result: dict | None = None

        # Start-of-turn recovery for the active combatant, if they are dying.
        # PF2e: the recovery check happens at the start of the creature's
        # own turn, not at end of turn.
        if state.phase == "combat" and state.active_combatant_id is not None:
            active = self.repo.get_combatant(campaign_id, state.active_combatant_id)
            if active is not None and dying_value(active.conditions or []) > 0:
                await self._run_recovery(campaign_id, active, rng, notes)

        # ── Deterministic encounter detection (words, not the LLM) ──
        encounter_result = self._apply_encounter_detection(
            campaign_id, action, state, rng, dice_rolls, notes
        )

        # ── Deterministic resolution (never the LLM) ──
        target_name, state = await self._resolve_deterministic(
            kind,
            campaign_id,
            action,
            party,
            combatants,
            locations,
            state,
            rng,
            dice_rolls,
            hp_changes,
            notes,
        )

        # ── LLM structured outcome (proposal only) ──
        if len(dice_rolls) > emitted_dice:
            await _emit_turn_event(
                emit, {"type": "dice", "dice_rolls": list(dice_rolls)}
            )
            emitted_dice = len(dice_rolls)
        if len(hp_changes) > emitted_hp:
            await _emit_turn_event(
                emit, {"type": "hp", "hp_changes": list(hp_changes)}
            )
            emitted_hp = len(hp_changes)
        if encounter_result is not None:
            await _emit_turn_event(
                emit, {"type": "encounter", **encounter_result}
            )
            emitted_encounter = True

        outcome, outcome_source = await self._structured_outcome(
            campaign_id, action, kind, state, combatants, quests, chronicle
        )
        if outcome is not None:
            # The deterministic classifier is authoritative: the LLM outcome
            # may only refine a turn the classifier could not place ("other").
            # Letting the model overwrite a classified attack with "other"
            # silently dropped the whole deterministic resolution.
            if kind == "other" and outcome.kind:
                refined = outcome.kind
                kind = refined
                # The classifier placed nothing, so the first resolution
                # pass did nothing. A refinement to a resolvable kind must
                # actually resolve — re-run it here — or the turn would be
                # recorded and narrated as an attack/skill/rest/move that
                # never happened (no damage rolled, no healing, no move).
                if refined in ("attack", "skill", "rest", "move"):
                    refined_target, state = await self._resolve_deterministic(
                        refined,
                        campaign_id,
                        action,
                        party,
                        combatants,
                        locations,
                        state,
                        rng,
                        dice_rolls,
                        hp_changes,
                        notes,
                    )
                    if refined_target and not target_name:
                        target_name = refined_target
                # The first pass ran before the LLM refined an unplaced turn.
                # Re-run detection against the refined state so a late
                # classification cannot skip a door/NPC/loot/trap trigger.
                if encounter_result is None:
                    encounter_result = self._apply_encounter_detection(
                        campaign_id, action, state, rng, dice_rolls, notes
                    )
            if outcome.target and not target_name:
                target_name = outcome.target
            if outcome.quest_update is not None and outcome.quest_update.completed:
                applied = self.repo.set_quest_objective(
                    campaign_id,
                    outcome.quest_update.quest_name,
                    outcome.quest_update.objective,
                )
                if applied is not None:
                    quest_updates.append(applied)
                    notes.append(
                        f"Quest update: {applied['quest']} — {applied['objective']} completed."
                        + (" Quest complete!" if applied["quest_completed"] else "")
                    )
            if outcome.location:
                moved = self._resolve_move(
                    campaign_id, outcome.location, locations, state
                )
                if moved:
                    state = self.repo.get_solo_state(campaign_id) or state
                    notes.append(f"Moved to {moved}.")

        if len(dice_rolls) > emitted_dice:
            await _emit_turn_event(
                emit, {"type": "dice", "dice_rolls": list(dice_rolls)}
            )
            emitted_dice = len(dice_rolls)
        if len(hp_changes) > emitted_hp:
            await _emit_turn_event(
                emit, {"type": "hp", "hp_changes": list(hp_changes)}
            )
            emitted_hp = len(hp_changes)
        if encounter_result is not None and not emitted_encounter:
            await _emit_turn_event(
                emit, {"type": "encounter", **encounter_result}
            )

        # ── Initiative advance + end-of-turn conditions (combat only) ──
        if state.phase == "combat":
            state = await self._advance_turn(campaign_id, state, rng, notes)

        conditions = self._conditions_snapshot(campaign_id)
        await _emit_turn_event(
            emit, {"type": "conditions", "conditions": conditions}
        )

        # ── Narration ──
        narration = await self._narrate_turn(
            campaign_id, action, kind, outcome, dice_rolls, hp_changes, notes, state
        )
        source = outcome_source if outcome_source == "llm" else "fallback"
        # Narration itself came from the LLM whenever it answered; the
        # "source" flag reports whether the *structured outcome* was LLM or
        # template, which is the part that can change game state.
        if outcome is None:
            source = "fallback"

        location_name = self._current_location_name(campaign_id, state)
        active_name = None
        if state.active_combatant_id is not None:
            active = self.repo.get_combatant(campaign_id, state.active_combatant_id)
            active_name = active.name if active else None

        # ── Persist ──
        outcome_dict = outcome.model_dump(mode="python") if outcome is not None else {"kind": kind}
        self.repo.record_turn(
            campaign_id, turn_num, actor, action, narration, outcome_dict, dice_rolls
        )
        self.repo.append_event(
            campaign_id,
            "turn",
            summary=f"Turn {turn_num}: {action[:200]}",
            location_id=state.current_location_id,
            data={
                "turn_num": turn_num,
                "kind": kind,
                "phase": state.phase,
                "source": source,
                "actor": actor,
            },
        )
        self.repo.add_decision(
            campaign_id=campaign_id,
            session_num=max(1, self.repo.get_latest_session_num(campaign_id)),
            decision=action,
            context=f"turn {turn_num} ({kind})",
            consequences=[n for n in notes],
            made_by=actor,
        )
        if self._orchestrator is None:
            # The orchestrator's generate() already records the live note;
            # only record one here when it was not involved.
            self.repo.add_session_note(
                campaign_id,
                max(1, self.repo.get_latest_session_num(campaign_id)),
                action,
                narration,
            )
        if state.phase == "combat":
            self.repo.mirror_combat_json(campaign_id)

        choices = (
            list(outcome.choices)[:3]
            if outcome is not None and outcome.choices
            else self._default_choices(kind, state.phase)
        )

        result = TurnResult(
            campaign_id=campaign_id,
            turn_num=turn_num,
            narration=narration,
            dice_rolls=dice_rolls,
            hp_changes=hp_changes,
            conditions=conditions,
            quest_updates=quest_updates,
            location=location_name,
            phase=state.phase,
            round=state.round_num,
            active_combatant=active_name,
            choices=choices,
            seed=turn_seed,
            source=source,
            kind=kind,
            encounter=(
                encounter_result["encounter"]
                if encounter_result is not None
                else None
            ),
        )
        for chunk in _narration_chunks(narration):
            await _emit_turn_event(emit, {"type": "narration", "text": chunk})
        await _emit_turn_event(emit, {"type": "end", "result": result.to_dict()})
        return result

    def _current_location_name(self, campaign_id: int, state: Any) -> str | None:
        if state.current_location_id is None:
            return None
        for loc in self.repo.get_locations(campaign_id):
            if loc.id == state.current_location_id:
                return loc.name
        return None

    def _conditions_snapshot(self, campaign_id: int) -> list[dict]:
        conditions: list[dict] = []
        for c in self.repo.get_combatants(campaign_id, active_only=True):
            conditions.extend(
                {"combatant": c.name, **cond} for cond in (c.conditions or [])
            )
        return conditions

    # ── Encounter detection ───────────────────────────────────

    def _apply_encounter_detection(
        self,
        campaign_id: int,
        action: str,
        state: Any,
        rng: random.Random,
        dice_rolls: list[dict],
        notes: list[str],
    ) -> dict | None:
        """Create or advance the encounter named by the player's action.

        Detection is additive: the turn's normal deterministic resolution still
        runs, and a missing map door or NPC never fails the turn. Door, NPC,
        loot, and trap records all go through the same repository service the
        REST routes and GM tools use.
        """
        detected = detect_encounter_action(action)
        if detected is None:
            return None
        kind, target = detected
        location_id = state.current_location_id
        encounter = self._find_open_encounter(
            campaign_id, kind, location_id, target
        )
        if encounter is None:
            encounter = self.repo.create_encounter(
                campaign_id,
                kind,
                summary=action[:1000],
                location_id=location_id,
                state=self._encounter_state_for(
                    campaign_id, kind, target, location_id
                ),
            )
            notes.append(
                f"{kind.title()} encounter created (id {encounter.id})."
            )
        else:
            notes.append(f"Continuing {kind} encounter {encounter.id}.")

        instant = False
        activated = False
        if (
            kind == "trap"
            and self._is_instant_trap(action)
            and encounter.status == "pending"
        ):
            dc = self._trap_dc(encounter)
            success = self._roll_skill_check(
                rng, dice_rolls, notes, dc=dc, label="Trap check"
            )
            status = "resolved" if success else "failed"
            encounter = self.repo.transition_encounter(
                campaign_id,
                encounter.id,
                status,
                summary=action[:1000],
                instant=True,
            )
            instant = True
            notes.append(f"Trap {status} without taking the active slot.")
        elif encounter.status == "pending":
            try:
                encounter = self.repo.transition_encounter(
                    campaign_id,
                    encounter.id,
                    "active",
                    summary=action[:1000],
                )
                activated = True
                notes.append(
                    f"{kind.title()} encounter active (id {encounter.id})."
                )
            except ValueError as exc:
                notes.append(f"{kind.title()} encounter pending: {exc}")
        else:
            notes.append(
                f"{kind.title()} encounter already active (id {encounter.id})."
            )

        return {
            "encounter": encounter.to_dict(),
            "activated": activated,
            "instant": instant,
            "note": notes[-1],
        }

    def _find_open_encounter(
        self,
        campaign_id: int,
        kind: str,
        location_id: int | None,
        target: str | None,
    ) -> Any | None:
        """Return an existing pending/active encounter for this story beat."""
        for encounter in self.repo.list_encounters(campaign_id, limit=200):
            if encounter.kind != kind:
                continue
            if encounter.location_id != location_id:
                continue
            if encounter.status not in ("pending", "active"):
                continue
            if kind == "npc" and target:
                existing = str(encounter.state.get("target") or "")
                if existing and existing.lower() != target.lower():
                    continue
            return encounter
        return None

    def _encounter_state_for(
        self,
        campaign_id: int,
        kind: str,
        target: str | None,
        location_id: int | None,
    ) -> dict:
        """Attach a known NPC or map door when one is present; never required."""
        state: dict[str, Any] = {}
        if target:
            state["target"] = target
        if kind == "npc" and target:
            match = next(
                (
                    c
                    for c in self.repo.get_combatants(campaign_id)
                    if c.kind == "npc"
                    and target.lower() in c.name.lower()
                ),
                None,
            )
            if match is not None:
                state["npc_id"] = match.id
                state["npc_name"] = match.name
                state["target"] = match.name
        elif kind == "door":
            door = self._door_from_recent_map(campaign_id, location_id)
            if door is not None:
                state["door"] = door
        return state

    def _door_from_recent_map(
        self, campaign_id: int, location_id: int | None
    ) -> dict | None:
        """Find a persisted map door at this location, if a scene exists."""
        for encounter in self.repo.list_encounters(campaign_id, limit=200):
            if encounter.location_id != location_id:
                continue
            map_state = encounter.state.get("map") or {}
            scene = map_state.get("scene") or {}
            doors = scene.get("doors") or map_state.get("doors") or []
            if doors:
                return dict(doors[0])
        return None

    @staticmethod
    def _trap_dc(encounter: Any) -> int:
        """Use the trap's authored DC when present, else the skill-check DC."""
        try:
            return max(1, int(encounter.state.get("dc") or SKILL_CHECK_DC))
        except (TypeError, ValueError):
            return SKILL_CHECK_DC

    @staticmethod
    def _is_instant_trap(action: str) -> bool:
        """A one-roll trap attempt, unless the player is starting a long disarm."""
        return bool(_TRAP_ONE_ROLL_RE.search(action)) and not bool(
            _TRAP_MULTI_RE.search(action)
        )

    @staticmethod
    def _default_choices(kind: str, phase: str) -> list[str]:
        if phase == "combat":
            return ["Attack the nearest foe", "Move to cover", "End your turn"]
        if kind == "talk":
            return ["Ask about the quest", "Ask about the area", "Move on"]
        return ["Look around", "Move on", "Rest a moment"]

    # ── Deterministic resolvers ───────────────────────────────

    def _find_target(
        self, action: str, combatants: list[Any]
    ) -> Any | None:
        text = (action or "").lower()
        for c in combatants:
            if c.kind == "monster" and c.name.lower() in text:
                return c
        monsters = [c for c in combatants if c.kind == "monster"]
        return monsters[0] if monsters else None

    async def _resolve_deterministic(
        self,
        kind: str,
        campaign_id: int,
        action: str,
        party: list[dict],
        combatants: list[Any],
        locations: list[Any],
        state: Any,
        rng: random.Random,
        dice_rolls: list[dict],
        hp_changes: list[dict],
        notes: list[str],
    ) -> tuple[str | None, Any]:
        """Run the deterministic resolver for one action kind.

        Returns (target_name, state). Only attack produces a target; only
        move can change state (the current location). Talk and other have
        no deterministic effect — they are narration only. take_turn calls
        this once for the classifier's kind and again when the LLM refines
        an unplaced ("other") turn into a resolvable kind, so a refined
        attack actually rolls damage instead of only changing the label.
        """
        target_name: str | None = None
        if kind == "attack":
            target_name, hp_change = await self._resolve_attack(
                campaign_id, action, party, combatants, rng, dice_rolls, notes
            )
            if hp_change:
                hp_changes.append(hp_change)
        elif kind == "skill":
            self._resolve_skill(action, rng, dice_rolls, notes)
        elif kind == "rest":
            self._resolve_rest(campaign_id, rng, dice_rolls, hp_changes, notes)
        elif kind == "move":
            moved = self._resolve_move(campaign_id, action, locations, state)
            if moved:
                state = self.repo.get_solo_state(campaign_id) or state
                notes.append(f"Moved to {moved}.")
        return target_name, state

    async def _resolve_attack(
        self,
        campaign_id: int,
        action: str,
        party: list[dict],
        combatants: list[Any],
        rng: random.Random,
        dice_rolls: list[dict],
        notes: list[str],
    ) -> tuple[str | None, dict | None]:
        target = self._find_target(action, combatants)
        if target is None:
            notes.append("No foe in reach to attack.")
            return None, None
        hero_level = 1
        if party:
            try:
                hero_level = int(party[0].get("level") or 1)
            except (TypeError, ValueError):
                hero_level = 1
        attack_bonus = HERO_ATTACK_BONUS_BASE + hero_level // 2
        d20 = rng.randint(1, 20)
        attack_roll = d20 + attack_bonus
        damage_total, damage_rolls, _ = roll_dice(HERO_DAMAGE_DICE, rng=rng)
        dice_rolls.append({"notation": "d20", "rolls": [d20], "total": attack_roll})
        dice_rolls.append(
            {"notation": HERO_DAMAGE_DICE, "rolls": damage_rolls, "total": damage_total}
        )
        result = CombatTrackerAgent.resolve_strike(
            attack_roll=attack_roll,
            target_ac=target.ac,
            damage_roll=damage_total,
            target_hp=target.hp,
            target_temp_hp=target.temp_hp,
        )
        conditions = list(target.conditions or [])
        dead = False
        if result.new_hp <= 0 and result.damage_dealt > 0:
            conditions, dead = gain_dying(conditions, wounded=wounded_value(conditions))
            if dead:
                notes.append(f"{target.name} is dead.")
        update_kwargs: dict[str, Any] = {
            "hp": result.new_hp,
            "temp_hp": result.new_temp_hp,
            "conditions": conditions,
        }
        if dead:
            # Dead foes must leave the active roster immediately; waiting for
            # their initiative slot left a corpse in the turn order and kept
            # the encounter from ever reaching its resolved state.
            update_kwargs["is_active"] = False
        self.repo.update_combatant(target.id, **update_kwargs)
        notes.append(
            f"Attack vs {target.name} (AC {target.ac}): {result.outcome}, "
            f"{result.damage_dealt} damage. {result.notes}"
        )
        return target.name, {
            "name": target.name,
            "hp": result.new_hp,
            "max_hp": target.max_hp,
            "damage": result.damage_dealt,
        }

    def _roll_skill_check(
        self,
        rng: random.Random,
        dice_rolls: list[dict],
        notes: list[str],
        *,
        dc: int = SKILL_CHECK_DC,
        label: str = "Skill check",
    ) -> bool:
        """Roll one d20 skill check into the turn's shared dice stream."""
        d20 = rng.randint(1, 20)
        total = d20 + HERO_SKILL_MODIFIER
        dice_rolls.append({"notation": "d20", "rolls": [d20], "total": total})
        success = total >= dc
        notes.append(
            f"{label}: d20 {d20} + {HERO_SKILL_MODIFIER} = {total} vs DC {dc} — "
            + ("success." if success else "failure.")
        )
        return success

    def _resolve_skill(
        self,
        action: str,
        rng: random.Random,
        dice_rolls: list[dict],
        notes: list[str],
    ) -> None:
        self._roll_skill_check(rng, dice_rolls, notes)

    def _resolve_rest(
        self,
        campaign_id: int,
        rng: random.Random,
        dice_rolls: list[dict],
        hp_changes: list[dict],
        notes: list[str],
    ) -> None:
        heal_total, heal_rolls, _ = roll_dice(REST_HEAL_DICE, rng=rng)
        dice_rolls.append(
            {"notation": REST_HEAL_DICE, "rolls": heal_rolls, "total": heal_total}
        )
        # Heal every hero row, active or not. Resting used to read only the
        # active combatants, and heroes are inactive outside combat — so a
        # rest in exploration healed nothing while still reporting HP
        # recovered. Before the first combat there are no hero rows at all;
        # create them from the party at full HP so the rest has state.
        heroes = [c for c in self.repo.get_combatants(campaign_id) if c.kind == "hero"]
        if not heroes:
            ids = self._ensure_hero_combatants(campaign_id, rng)
            heroes = [
                c
                for c in (self.repo.get_combatant(campaign_id, i) for i in ids)
                if c is not None
            ]
        healed_total = 0
        for c in heroes:
            if c.hp >= c.max_hp:
                continue
            new_hp = min(c.max_hp, c.hp + heal_total)
            self.repo.update_combatant(c.id, hp=new_hp)
            healed = new_hp - c.hp
            healed_total += healed
            hp_changes.append(
                {"name": c.name, "hp": new_hp, "max_hp": c.max_hp, "healed": healed}
            )
        if healed_total > 0:
            notes.append(f"Rested: recovered {healed_total} HP.")
        else:
            notes.append("Rested: no wounds to heal.")

    def _resolve_move(
        self, campaign_id: int, text: str, locations: list[Any], state: Any
    ) -> str | None:
        lowered = (text or "").lower()
        for loc in locations:
            if loc.name.lower() in lowered:
                if state.current_location_id != loc.id:
                    movement = self.repo.move_to_location(campaign_id, loc.id)
                    return movement["location"]
                return None
        return None

    async def _run_recovery(
        self,
        campaign_id: int,
        combatant: Any,
        rng: random.Random,
        notes: list[str],
    ) -> None:
        """Start-of-turn recovery check for a dying combatant."""
        conditions = list(combatant.conditions or [])
        dying = dying_value(conditions)
        wounded = wounded_value(conditions)
        result = CombatTrackerAgent.recovery_check(dying, wounded=wounded, rng=rng)
        notes.append(result.notes)
        new_conditions = [c for c in conditions if str(c.get("name", "")).lower() != "dying"]
        if result.dead:
            new_conditions.append({"name": "Dying", "value": 4})
            new_conditions.append({"name": "Dead", "value": 1})
            self.repo.update_combatant(
                combatant.id, conditions=new_conditions, is_active=False
            )
        elif result.stabilized:
            # Recovering from dying adds a level of Wounded.
            new_conditions.append({"name": "Wounded", "value": wounded + 1})
            self.repo.update_combatant(combatant.id, conditions=new_conditions)
        else:
            new_conditions.append({"name": "Dying", "value": result.dying})
            self.repo.update_combatant(combatant.id, conditions=new_conditions)

    async def _advance_turn(
        self, campaign_id: int, state: Any, rng: random.Random, notes: list[str]
    ) -> Any:
        """End the current combatant's turn, advance initiative, wrap rounds."""
        order = list(state.turn_order or [])
        combatants = self.repo.get_combatants(campaign_id, active_only=True)
        if not combatants:
            self.repo.resolve_active_encounter(
                campaign_id, "resolved", summary="Combat ended"
            )
            return self._leave_combat(campaign_id)
        current_id = state.active_combatant_id
        current = next((c for c in combatants if c.id == current_id), None)
        if current is not None:
            updated, turn_notes, damage = CombatTrackerAgent.end_of_turn(
                list(current.conditions or []), current_hp=current.hp, rng=rng
            )
            new_hp = max(0, current.hp - damage)
            self.repo.update_combatant(
                current.id, hp=new_hp, conditions=updated
            )
            if turn_notes:
                notes.append(f"End of {current.name}'s turn: {turn_notes}")
            if any(
                str(c.get("name", "")).lower() == "dead" for c in updated
            ):
                self.repo.update_combatant(current.id, is_active=False)
                combatants = self.repo.get_combatants(campaign_id, active_only=True)

        # Victory/defeat is a roster condition, not an initiative condition.
        # The old loop kept advancing heroes after every monster was dead
        # because it only stopped when the entire roster was empty.
        if not any(c.kind == "hero" for c in combatants):
            self.repo.resolve_active_encounter(
                campaign_id, "failed", summary="All heroes defeated"
            )
            return self._leave_combat(campaign_id)
        if not any(c.kind == "monster" for c in combatants):
            self.repo.resolve_active_encounter(
                campaign_id, "resolved", summary="All foes defeated"
            )
            return self._leave_combat(campaign_id)

        # Re-read the order: deaths may have removed combatants.
        order = [c.id for c in combatants if c.id in order]
        if not order:
            # Defensive: active combatants exist but the saved initiative
            # order has lost them. End cleanly rather than leaving phase
            # combat with no turn owner.
            self.repo.resolve_active_encounter(
                campaign_id, "resolved", summary="Combat ended"
            )
            return self._leave_combat(campaign_id)
        if current_id in order:
            idx = order.index(current_id)
            nxt = order[(idx + 1) % len(order)]
            new_round = state.round_num + (1 if idx + 1 >= len(order) else 0)
        else:
            nxt = order[0]
            new_round = state.round_num
        return self.repo.update_solo_state(
            campaign_id, round_num=new_round, active_combatant_id=nxt, turn_order=order
        )

    def _leave_combat(self, campaign_id: int) -> Any:
        """Leave the combat phase and retire the active roster."""
        self.repo.deactivate_combatants(campaign_id)
        return self.repo.update_solo_state(
            campaign_id,
            phase="exploration",
            round_num=1,
            clear_active=True,
            turn_order=[],
        )

    # ── LLM structured outcome + narration ────────────────────

    async def _structured_outcome(
        self,
        campaign_id: int,
        action: str,
        kind: str,
        state: Any,
        combatants: list[Any],
        quests: list[Any],
        chronicle: str,
    ) -> tuple[TurnOutcomeModel | None, str]:
        """Ask the LLM for a structured turn outcome; deterministic on failure."""
        prompt = (
            "SOLO TURN OUTCOME. You are the Pathfinder GM adjudicating one solo "
            "turn. Output ONLY a JSON object matching this schema: "
            '{"kind": "attack|skill|move|talk|rest|other", "target": string or null, '
            '"skill": string or null, "location": string or null, '
            '"quest_update": {"quest_name": string, "objective": string, "completed": bool} or null, '
            '"narration_hint": string, "choices": [up to 3 short strings]}. '
            f"Player action: {action}. Classified kind: {kind}. "
            f"Phase: {state.phase}, round {state.round_num}. "
            f"Combatants: {json.dumps([{'name': c.name, 'kind': c.kind, 'hp': c.hp, 'max_hp': c.max_hp} for c in combatants])}. "
            f"Quests: {json.dumps([{'name': q.name, 'status': q.status} for q in quests])}. "
            f"Chronicle: {(chronicle or '(none)')[:500]} "
            "Only name a quest or location that appears above. "
            "Do not invent dice results or HP changes."
        )
        validated: dict[str, TurnOutcomeModel] = {}

        def _validate(data: object) -> list[str]:
            if not isinstance(data, dict):
                return ["LLM returned a JSON value that is not an object"]
            try:
                validated["model"] = TurnOutcomeModel.model_validate(data)
            except Exception as exc:
                return [f"Schema validation failed: {exc}"]
            return []

        try:
            outcome = await generate_validated_json(
                self.llm,
                prompt=prompt,
                model=self._settings.model_for("builders"),
                temperature=0.3,
                num_predict=800,
                validate=_validate,
            )
        except Exception as exc:
            logger.warning("Solo turn outcome LLM failed: %s", exc)
            return None, "fallback"
        if outcome.data is not None and "model" in validated:
            return validated["model"], "llm"
        return None, "fallback"

    async def _narrate_turn(
        self,
        campaign_id: int,
        action: str,
        kind: str,
        outcome: TurnOutcomeModel | None,
        dice_rolls: list[dict],
        hp_changes: list[dict],
        notes: list[str],
        state: Any,
    ) -> str:
        hint = outcome.narration_hint if outcome is not None else ""
        prompt = (
            "You are the Pathfinder GM narrating one solo turn. "
            f"Player action: {action} (kind: {kind}). "
            f"Dice: {json.dumps(dice_rolls)}. HP changes: {json.dumps(hp_changes)}. "
            f"Events: {' '.join(notes) or '(none)'} "
            f"GM hint: {hint or '(none)'} "
            f"Phase: {state.phase}, round {state.round_num}. "
            "Narrate in 2-4 sentences, second person, then end by asking "
            "what the hero does next."
        )
        try:
            text = await self._generate_narration(prompt, campaign_id)
            if text and text.strip():
                return text.strip()
        except Exception as exc:
            logger.warning("Solo turn narration failed: %s", exc)
        if hp_changes:
            change = hp_changes[0]
            return (
                f"Your strike lands on {change['name']}, leaving it at "
                f"{change['hp']} of {change['max_hp']} HP. What do you do?"
            )
        if dice_rolls:
            return (
                f"The dice settle: {dice_rolls[0].get('total')}. "
                f"{' '.join(notes) or ''} What do you do?"
            )
        return f"You press on. {' '.join(notes) or ''} What do you do?"

    # ── Combat lifecycle ──────────────────────────────────────

    def _ensure_hero_combatants(
        self, campaign_id: int, rng: random.Random, party_level: int = 1
    ) -> list[int]:
        """Create missing hero rows and reactivate existing ones.

        Existing rows keep their HP, conditions, AC, and max HP across
        encounters. Only a hero with no row yet starts at full HP. This is
        what lets rest healing and Wounded/Dying state survive the next
        ``start_combat``; the old implementation cleared every row and
        recreated heroes at full HP.
        """
        party = self.repo.get_party(campaign_id)
        existing = [
            c for c in self.repo.get_combatants(campaign_id) if c.kind == "hero"
        ]
        hero_ids: list[int] = []
        for member in party:
            name = member.get("name") or "Hero"
            initiative = rng.randint(1, 20) + HERO_INITIATIVE_BONUS
            match = next((c for c in existing if c.name == name), None)
            if match is not None:
                existing.remove(match)
                self.repo.update_combatant(
                    match.id, initiative=initiative, is_active=True
                )
                hero_ids.append(match.id)
                continue

            level = int(member.get("level") or 1)
            stats = member.get("stats_json")
            if isinstance(stats, str):
                try:
                    stats = json.loads(stats)
                except (TypeError, ValueError):
                    stats = None
            max_hp = _hero_hp_from_stats(stats if isinstance(stats, dict) else None, level)
            hero_ids.append(
                self.repo.upsert_combatant(
                    campaign_id=campaign_id,
                    name=name,
                    kind="hero",
                    hp=max_hp,
                    max_hp=max_hp,
                    ac=15,
                    initiative=initiative,
                )
            )

        if not hero_ids:
            initiative = rng.randint(1, 20) + HERO_INITIATIVE_BONUS
            if existing:
                hero = existing[0]
                self.repo.update_combatant(
                    hero.id, initiative=initiative, is_active=True
                )
                hero_ids.append(hero.id)
            else:
                max_hp = hero_max_hp(party_level)
                hero_ids.append(
                    self.repo.upsert_combatant(
                        campaign_id=campaign_id,
                        name="Hero",
                        kind="hero",
                        hp=max_hp,
                        max_hp=max_hp,
                        ac=15,
                        initiative=initiative,
                    )
                )
        return hero_ids

    async def start_combat(
        self,
        campaign_id: int,
        monster_names: list[str] | None = None,
        theme: str | None = None,
        threat: str = "moderate",
        party_level: int = 1,
        seed: int | None = None,
    ) -> CombatStartResult:
        """Build combatants from party + monsters, serialized with turns."""
        async with _campaign_turn_lock(campaign_id):
            return await self._start_combat_locked(
                campaign_id,
                monster_names=monster_names,
                theme=theme,
                threat=threat,
                party_level=party_level,
                seed=seed,
            )

    async def _start_combat_locked(
        self,
        campaign_id: int,
        monster_names: list[str] | None = None,
        theme: str | None = None,
        threat: str = "moderate",
        party_level: int = 1,
        seed: int | None = None,
    ) -> CombatStartResult:
        if not self.repo.campaign_exists(campaign_id):
            raise ValueError(f"no campaign {campaign_id}")
        state = self.repo.ensure_solo_state(campaign_id)
        combat_seed = (
            seed
            if seed is not None
            else zlib.crc32(f"combat:{campaign_id}".encode())
        )
        rng = random.Random(combat_seed)
        # A new battle supersedes whatever lifecycle record was active. The
        # encounter row must be abandoned before the roster is cleared, so a
        # failed setup cannot leave an active battle pointing at deleted foes.
        self.repo.abandon_active_encounter(
            campaign_id, summary="Superseded by a new battle"
        )
        encounter = self.repo.create_encounter(
            campaign_id,
            "battle",
            summary=theme or ", ".join(monster_names or []) or "Battle",
            state={
                "monster_names": list(monster_names or []),
                "theme": theme,
                "threat": threat,
                "party_level": party_level,
                "seed": combat_seed,
            },
            seed=combat_seed,
        )
        # Keep persistent hero rows; discard only the previous encounter.
        self.repo.clear_non_hero_combatants(campaign_id)

        # Heroes first, in party order. Existing heroes keep HP/conditions.
        hero_ids = self._ensure_hero_combatants(campaign_id, rng, party_level)

        # Monsters: named builds via the monster builder, theme via the
        # encounter builder, deterministic fallback when the LLM is down.
        monster_specs: list[dict] = []
        if monster_names:
            for name in monster_names:
                monster_specs.append(await self._build_monster_spec(name, party_level))
        elif theme:
            monster_specs = await self._build_encounter_specs(
                theme, threat, party_level, len(hero_ids)
            )
        if not monster_specs:
            monster_specs = [
                {
                    "name": f"{theme or 'Wild'} Creature",
                    "level": party_level,
                    "hp": 10 + 5 * party_level,
                    "ac": 12 + party_level,
                }
            ]

        monster_ids: list[int] = []
        for spec in monster_specs:
            # add_combatant, not upsert: an encounter may field several
            # creatures with the same name, and each needs its own row.
            monster_ids.append(
                self.repo.add_combatant(
                    campaign_id=campaign_id,
                    name=spec["name"],
                    kind="monster",
                    hp=spec["hp"],
                    max_hp=spec["hp"],
                    ac=spec["ac"],
                    initiative=rng.randint(1, 20) + MONSTER_INITIATIVE_BONUS,
                )
            )

        combatants = self.repo.get_combatants(campaign_id, active_only=True)
        combatants.sort(key=lambda c: (-c.initiative, c.name))
        for order, c in enumerate(combatants):
            self.repo.update_combatant(c.id, turn_order=order)
        order_ids = [c.id for c in combatants]
        self.repo.update_solo_state(
            campaign_id,
            phase="combat",
            round_num=1,
            active_combatant_id=order_ids[0] if order_ids else None,
            turn_order=order_ids,
        )
        encounter = self.repo.transition_encounter(
            campaign_id,
            encounter.id,
            "active",
            state={
                **encounter.state,
                "combatant_ids": order_ids,
                "turn_order": order_ids,
                "round": 1,
                "active_combatant_id": order_ids[0] if order_ids else None,
            },
        )
        self.repo.mirror_combat_json(campaign_id)
        return CombatStartResult(
            campaign_id=campaign_id,
            phase="combat",
            round=1,
            combatants=[self._combatant_dict(c) for c in combatants],
            active_combatant=combatants[0].name if combatants else None,
            encounter_id=encounter.id,
        )

    @staticmethod
    def _combatant_dict(c: Any) -> dict:
        return {
            "id": c.id,
            "name": c.name,
            "kind": c.kind,
            "hp": c.hp,
            "max_hp": c.max_hp,
            "temp_hp": c.temp_hp,
            "ac": c.ac,
            "initiative": c.initiative,
            "conditions": c.conditions or [],
            "is_active": c.is_active,
        }

    async def _build_monster_spec(self, name: str, party_level: int) -> dict:
        try:
            from app.agents.monster_builder import MonsterBuilderAgent

            result = await MonsterBuilderAgent(self.llm).build(
                name, level=party_level
            )
            if result.valid and result.monster is not None:
                return {
                    "name": result.monster.name,
                    "level": result.monster.level,
                    "hp": result.monster.hp,
                    "ac": result.monster.ac,
                }
        except Exception as exc:
            logger.warning("Solo combat monster build failed for %s: %s", name, exc)
        return {
            "name": name,
            "level": party_level,
            "hp": 10 + 5 * party_level,
            "ac": 12 + party_level,
        }

    async def _build_encounter_specs(
        self, theme: str, threat: str, party_level: int, party_size: int
    ) -> list[dict]:
        try:
            from app.agents.encounter_builder import EncounterBuilderAgent
            from app.rag.retriever import Retriever

            agent = EncounterBuilderAgent(self.llm, Retriever(self.repo))
            result = await agent.build(
                party_level=party_level,
                party_size=max(1, party_size),
                threat=threat,
                theme=theme,
            )
            specs: list[dict] = []
            for monster in result.monsters:
                for _ in range(monster.count):
                    specs.append(
                        {
                            "name": monster.name,
                            "level": monster.level,
                            "hp": max(1, monster.hp or 10),
                            # EncounterMonster carries no AC, so derive it the
                            # same way the deterministic fallbacks do (12 +
                            # level) plus the encounter template's AC modifier
                            # — never a flat 15 for every creature.
                            "ac": _encounter_monster_ac(monster.level, monster.template),
                        }
                    )
            return specs
        except Exception as exc:
            logger.warning("Solo combat encounter build failed for %s: %s", theme, exc)
            return []

    async def end_turn(self, campaign_id: int) -> dict:
        """Advance initiative by one combatant, serialized with other turns."""
        async with _campaign_turn_lock(campaign_id):
            return await self._end_turn_locked(campaign_id)

    async def _end_turn_locked(self, campaign_id: int) -> dict:
        if not self.repo.campaign_exists(campaign_id):
            raise ValueError(f"no campaign {campaign_id}")
        state = self.repo.ensure_solo_state(campaign_id)
        if state.phase != "combat":
            return {"phase": state.phase, "round": state.round_num, "active_combatant": None}
        rng = random.Random(zlib.crc32(f"endturn:{campaign_id}:{state.round_num}".encode()))
        state = await self._advance_turn(campaign_id, state, rng, [])
        self.repo.mirror_combat_json(campaign_id)
        active = None
        if state.active_combatant_id is not None:
            combatant = self.repo.get_combatant(campaign_id, state.active_combatant_id)
            active = combatant.name if combatant else None
        return {"phase": state.phase, "round": state.round_num, "active_combatant": active}

    async def end_combat(self, campaign_id: int) -> dict:
        """Close combat: back to exploration, initiative cleared."""
        async with _campaign_turn_lock(campaign_id):
            return await self._end_combat_locked(campaign_id)

    async def _end_combat_locked(self, campaign_id: int) -> dict:
        if not self.repo.campaign_exists(campaign_id):
            raise ValueError(f"no campaign {campaign_id}")
        active = self.repo.get_active_encounter(campaign_id)
        if active is not None and active.kind == "battle":
            self.repo.resolve_active_encounter(
                campaign_id, "resolved", summary="Combat ended by player"
            )
        self.repo.update_solo_state(
            campaign_id, phase="exploration", round_num=1, clear_active=True, turn_order=[]
        )
        # The roster must go inactive too: leaving combatants active after
        # the phase flip meant exploration turns still saw live foes.
        self.repo.deactivate_combatants(campaign_id)
        self.repo.mirror_combat_json(campaign_id)
        return {"phase": "exploration", "round": 1, "active_combatant": None}

    def get_state(self, campaign_id: int) -> dict:
        """Full solo state for the state endpoint."""
        if not self.repo.campaign_exists(campaign_id):
            raise ValueError(f"no campaign {campaign_id}")
        state = self.repo.ensure_solo_state(campaign_id)
        combatants = self.repo.get_combatants(campaign_id)
        quests = self.repo.get_quests(campaign_id)
        turns = self.repo.get_recent_turns(campaign_id, limit=10)
        campaign = self.repo.get_or_create_campaign(campaign_id)
        return {
            "campaign_id": campaign_id,
            "name": campaign.name,
            "edition": campaign.edition,
            "phase": state.phase,
            "round": state.round_num,
            "world_tick": state.world_tick,
            "location": self._current_location_name(campaign_id, state),
            "location_id": state.current_location_id,
            "active_combatant_id": state.active_combatant_id,
            "combatants": [self._combatant_dict(c) for c in combatants],
            "quests": [
                {
                    "id": q.id,
                    "name": q.name,
                    "status": q.status,
                    "description": q.description,
                    "objectives": q.objectives,
                    "rewards": q.rewards,
                }
                for q in quests
            ],
            "recent_turns": [
                {
                    "turn_num": t.turn_num,
                    "actor": t.actor,
                    "action": t.action,
                    "narration": t.narration,
                    "dice": t.dice,
                }
                for t in turns
            ],
            "active_encounter": (
                active.to_dict()
                if (active := self.repo.get_active_encounter(campaign_id))
                is not None
                else None
            ),
            "chronicle": self.repo.get_campaign_summary(campaign_id),
        }
