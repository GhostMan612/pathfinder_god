# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Encounter Builder Agent — Deterministic PF2e XP budget + LLM monster selection.

Workflow:
1. Calculate exact XP budget using PF2e Remaster tables.
2. Query FTS5 for theme-filtered monsters (system=2e, level within PL-4..PL+4).
3. LLM selects a mix matching the exact XP budget.
4. Return hydrated monster list with full rule content.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.llm.ollama_client import OllamaClient
from app.config import get_settings
from app.db.repository import CampaignRepository
from app.rag.retriever import Retriever
from app.agents.dice_utils import roll_dice

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# PF2e Remaster XP Tables (deterministic — never LLM)
# ──────────────────────────────────────────────────────────────

# Base XP budget for 4 players by threat level
THREAT_BUDGET_4: dict[str, int] = {
    "trivial": 40,
    "low": 60,
    "moderate": 80,
    "severe": 120,
    "extreme": 160,
}

# Adjustment per player above/below 4
THREAT_ADJ_PER_PLAYER: dict[str, int] = {
    "trivial": 10,
    "low": 15,
    "moderate": 20,
    "severe": 30,
    "extreme": 40,
}

# Creature XP cost by level difference from Party Level (PL)
# Keys: creature_level - party_level
CREATURE_XP_BY_LEVEL_DIFF: dict[int, int] = {
    -4: 10,
    -3: 15,
    -2: 20,
    -1: 30,
    0: 40,
    1: 60,
    2: 80,
    3: 120,
    4: 160,
}

VALID_THREATS = tuple(THREAT_BUDGET_4.keys())

# Elite / Weak adjustment templates (PF2e Bestiary building rules).
# Strikes, saves, AC, DCs and damage shift by 2; HP scales by 20%;
# the adjusted creature counts one level up (elite) or down (weak) for XP.
TEMPLATE_MODIFIERS: dict[str, dict[str, float]] = {
    "normal": {"ac": 0, "saves": 0, "strikes": 0, "damage": 0, "hp_mult": 1.0, "level_bump": 0},
    "elite": {"ac": 2, "saves": 2, "strikes": 2, "damage": 2, "hp_mult": 1.2, "level_bump": 1},
    "weak": {"ac": -2, "saves": -2, "strikes": -2, "damage": -2, "hp_mult": 0.8, "level_bump": -1},
}

VALID_TEMPLATES = tuple(TEMPLATE_MODIFIERS.keys())

HP_STATIC_RE = re.compile(r"\bHP\s+(\d{1,4})\b", re.IGNORECASE)
HP_DICE_RE = re.compile(
    r"\bHP\s*\(?\s*(\d+\s*d\s*\d+(?:\s*[+-]\s*\d+)?)\s*\)?",
    re.IGNORECASE,
)
HP_PAREN_DICE_RE = re.compile(
    r"\bHP\s*\d+\s*\(\s*(\d+\s*d\s*\d+(?:\s*[+-]\s*\d+)?)\s*\)",
    re.IGNORECASE,
)


@dataclass
class AdjustedStats:
    level: int
    ac: int
    saves: int
    strikes: int
    damage_bonus: int
    hp: int
    template: str


@dataclass
class EncounterMonster:
    name: str
    count: int
    level: int
    xp_each: int
    content: str
    source_book: str
    hp: int = 0
    template: str = "normal"

    @property
    def total_xp(self) -> int:
        return self.xp_each * self.count


@dataclass
class BuildResult:
    target_xp: int
    total_xp: int
    monsters: list[EncounterMonster]
    party_level: int
    party_size: int
    threat: str
    theme: str


SYSTEM_PROMPT = """You are a Pathfinder 2e encounter designer.
Given a target XP budget and a list of available monsters (name, level, XP each),
select a mix that exactly matches the target budget.
Output ONLY a valid JSON array of objects:
[{"name": "Monster Name", "count": 2}]
No markdown, no commentary, no extra keys. The total XP must equal the target."""


class EncounterBuilderAgent:
    def __init__(self, llm: OllamaClient, retriever: Retriever):
        self._llm = llm
        self._retriever = retriever
        self._settings = get_settings()

    def calculate_budget(self, party_level: int, party_size: int, threat: str) -> int:
        threat = threat.lower()
        if threat not in THREAT_BUDGET_4:
            raise ValueError(f"Invalid threat: {threat}. Valid: {VALID_THREATS}")
        base = THREAT_BUDGET_4[threat]
        adj = THREAT_ADJ_PER_PLAYER[threat]
        diff = party_size - 4
        return base + adj * diff

    def creature_xp(self, party_level: int, creature_level: int) -> int:
        diff = creature_level - party_level
        if diff < -4:
            return CREATURE_XP_BY_LEVEL_DIFF[-4]
        if diff > 4:
            return CREATURE_XP_BY_LEVEL_DIFF[4]
        return CREATURE_XP_BY_LEVEL_DIFF[diff]

    def apply_template(
        self,
        level: int,
        ac: int,
        saves: int,
        strikes: int,
        hp: int,
        template: str,
    ) -> AdjustedStats:
        key = (template or "normal").lower()
        if key not in TEMPLATE_MODIFIERS:
            raise ValueError(f"Invalid template: {template}. Valid: {VALID_TEMPLATES}")
        mods = TEMPLATE_MODIFIERS[key]
        return AdjustedStats(
            level=level,
            ac=ac + int(mods["ac"]),
            saves=saves + int(mods["saves"]),
            strikes=strikes + int(mods["strikes"]),
            damage_bonus=int(mods["damage"]),
            hp=max(1, int(hp * float(mods["hp_mult"]))),
            template=key,
        )

    def template_level_bump(self, template: str) -> int:
        key = (template or "normal").lower()
        if key not in TEMPLATE_MODIFIERS:
            raise ValueError(f"Invalid template: {template}. Valid: {VALID_TEMPLATES}")
        return int(TEMPLATE_MODIFIERS[key]["level_bump"])

    def extract_hp(self, content: str) -> int | None:
        m = HP_STATIC_RE.search(content or "")
        if m:
            return int(m.group(1))
        return None

    def extract_hit_dice(self, content: str) -> str | None:
        text = content or ""
        m = HP_DICE_RE.search(text) or HP_PAREN_DICE_RE.search(text)
        if m:
            return re.sub(r"\s+", "", m.group(1))
        return None

    def roll_hp(self, content: str, rng: Any = None) -> int | None:
        dice = self.extract_hit_dice(content)
        if dice:
            total, _, _ = roll_dice(dice, rng)
            return max(1, total)
        return self.extract_hp(content)

    async def build(
        self,
        party_level: int,
        party_size: int,
        threat: str,
        theme: str,
        template: str = "normal",
    ) -> BuildResult:
        # 1. Calculate budget
        target_xp = self.calculate_budget(party_level, party_size, threat)
        level_bump = self.template_level_bump(template)

        # 2. Query FTS5 for theme, filter by level range PL-4..PL+4
        min_level = max(1, party_level - 4)
        max_level = party_level + 4
        hits = await self._retriever.search(
            query=theme,
            edition="2e",
            limit=100,
        )

        candidates: list[dict[str, Any]] = []
        for h in hits:
            if h.get("system") != "2e":
                continue
            content = h.get("content", "")
            level = self._extract_level(content)
            if level is None or not (min_level <= level <= max_level):
                continue
            xp = self.creature_xp(party_level, level + level_bump)
            candidates.append({
                "name": h["name"],
                "level": level,
                "xp_each": xp,
                "content": h["content"],
                "source_book": h.get("source_book", ""),
            })

        if not candidates:
            raise ValueError(f"No valid creatures found for theme '{theme}' at PL {party_level}")

        # 3. LLM selects exact budget match
        candidate_summary = "\n".join(
            f'- {c["name"]} (Level {c["level"]}, {c["xp_each"]} XP)' for c in candidates
        )

        prompt = f"{SYSTEM_PROMPT}\n\nTarget XP: {target_xp}\nAvailable monsters:\n{candidate_summary}"
        raw = await self._llm.generate(
            prompt=prompt,
            model=self._settings.ollama_model,
            temperature=0.2,
            num_predict=800,
        )

        selection = self._parse_selection(raw)
        if not selection:
            raise ValueError("LLM returned invalid selection")

        # 4. Hydrate selected monsters with full content
        monsters: list[EncounterMonster] = []
        total_xp = 0
        template_key = (template or "normal").lower()
        for item in selection:
            name = item["name"]
            count = int(item["count"])
            match = next((c for c in candidates if c["name"] == name), None)
            if not match:
                raise ValueError(f"LLM selected unknown monster: {name}")
            xp = self.creature_xp(party_level, match["level"] + level_bump)
            base_hp = self.roll_hp(match["content"]) or 0
            hp = base_hp
            if template_key != "normal" and base_hp > 0:
                hp = max(
                    1,
                    int(base_hp * float(TEMPLATE_MODIFIERS[template_key]["hp_mult"])),
                )
            monsters.append(EncounterMonster(
                name=name,
                count=count,
                level=match["level"],
                xp_each=xp,
                content=match["content"],
                source_book=match["source_book"],
                hp=hp,
                template=template_key,
            ))
            total_xp += xp * count

        if total_xp != target_xp:
            raise ValueError(f"Selection total XP ({total_xp}) != target ({target_xp})")

        return BuildResult(
            target_xp=target_xp,
            total_xp=total_xp,
            monsters=monsters,
            party_level=party_level,
            party_size=party_size,
            threat=threat,
            theme=theme,
        )

    def _extract_level(self, content: str) -> int | None:
        # Try to find "Level X" in content
        m = re.search(r"\bLevel\s+(\d{1,2})\b", content, re.IGNORECASE)
        if m:
            return int(m.group(1))
        # Fallback: look for "Creature X" pattern
        m = re.search(r"\bCreature\s+(\d{1,2})\b", content, re.IGNORECASE)
        if m:
            return int(m.group(1))
        return None

    def _parse_selection(self, raw: str) -> list[dict[str, Any]] | None:
        text = raw.strip()
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None