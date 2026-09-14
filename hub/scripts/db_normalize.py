# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Shared normalization for the Pathfinder RAG rebuild.

Fixes found 2026-09-14 in data/pathfinder_rag.db (integrity ok, content bad):
- 16,295/34,554 rows (47%) source_book = 'Unknown Source'
- 92 categories: book names as categories ('Pathfinder Monster Core',
  'Pathfinder Bestiary 3', 'Pfs Season 1 Bestiary'), case variants
  ('Classfeatures' vs 'Class Abilities'), effect tables ('Feat Effects')
- 1e pathological duplicates (Waterskin x36, Trail Rations x36)
- raw HTML (<p>, <strong>, @UUID[...], replacement chars) in raw_content
- FTS5 rank returns junk first ('Flanking' -> Mirror's Reflection)

Provides: canonical categories, book-like category repair, HTML strip,
edition upper-casing, and longest-wins dedupe preferring known sources.
"""
from __future__ import annotations

import html
import re

UNKNOWN = "Unknown Source"

_CANON = {
    "feat": "feat",
    "feats": "feat",
    "feat effects": "feat",
    "spell": "spell",
    "spells": "spell",
    "spell effects": "spell",
    "ritual": "ritual",
    "rituals": "ritual",
    "equipment": "equipment",
    "items": "equipment",
    "weapons and ammo": "equipment",
    "armors and shields": "equipment",
    "equipment effects": "equipment",
    "technology": "equipment",
    "bestiary": "bestiary",
    "bestiary effects": "bestiary",
    "bestiary family ability glossary": "bestiary",
    "pathfinder monster core": "bestiary",
    "pathfinder bestiary": "bestiary",
    "pathfinder bestiary 2": "bestiary",
    "pathfinder bestiary 3": "bestiary",
    "pfs season 1 bestiary": "bestiary",
    "pfs season 2 bestiary": "bestiary",
    "pfs season 3 bestiary": "bestiary",
    "pfs season 4 bestiary": "bestiary",
    "pfs season 5 bestiary": "bestiary",
    "pfs season 6 bestiary": "bestiary",
    "pathfinder npc core": "bestiary",
    "action": "action",
    "actions": "action",
    "adventure specific actions": "action",
    "classfeatures": "classfeature",
    "class features": "classfeature",
    "class abilities": "classfeature",
    "ancestryfeatures": "ancestryfeature",
    "ancestry features": "ancestryfeature",
    "ancestries": "ancestry",
    "races": "ancestry",
    "classes": "class",
    "heritages": "heritage",
    "backgrounds": "background",
    "deities": "deity",
    "conditions": "condition",
    "boons and curses": "boon",
    "mythic_spell": "spell",
    "mythic_spells": "spell",
    "class_archetype": "archetype",
    "class archetype": "archetype",
    "resource": "rule",
    "kingdom_resource": "rule",
}

_BOOKLIKE = {
    "pathfinder monster core",
    "pathfinder bestiary",
    "pathfinder bestiary 2",
    "pathfinder bestiary 3",
    "pfs season 1 bestiary",
    "pfs season 2 bestiary",
    "pfs season 3 bestiary",
    "pfs season 4 bestiary",
    "pfs season 5 bestiary",
    "pfs season 6 bestiary",
    "pathfinder npc core",
    "bestiary family ability glossary",
    "kingmaker bestiary",
    "monster templates",
    "template abilities",
    "pathfinder society boons",
}

_UUID_RE = re.compile(r"@UUID\[[^\]]*\]\{?[^}]*\}?")
_WS_RE = re.compile(r"[ \t\xa0\u200b\ufeff]+")


def canonical_category(raw: str | None) -> str:
    key = (raw or "").strip().lower()
    if not key:
        return "rule"
    if key in _CANON:
        return _CANON[key]
    if key.startswith("pfs season") and "bestiary" in key:
        return "bestiary"
    if key.startswith("pathfinder") and ("bestiary" in key or "monster" in key):
        return "bestiary"
    if "bestiary" in key or "monster template" in key or "template abilit" in key:
        return "bestiary"
    if "boon" in key:
        return "boon"
    if key in ("buffs", "buff"):
        return "spell"
    if "kingmaker" in key:
        return "bestiary"
    return key


def repair_source(category_raw: str | None, source_raw: str | None) -> tuple[str, str]:
    cat = canonical_category(category_raw)
    src = (source_raw or "").strip() or UNKNOWN
    key = (category_raw or "").strip().lower()
    if src == UNKNOWN and key in _BOOKLIKE:
        src = (category_raw or "").strip().title()
    return cat, src


def clean_content(raw: str | None) -> str:
    if not raw:
        return ""
    text = raw.replace("</p>", "\n\n").replace("<br>", "\n").replace("<br/>", "\n")
    text = re.sub(r"<hr\s*/?>", "\n\n", text)
    text = re.sub(r"<li\s*>", "\n- ", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = _UUID_RE.sub("", text)
    text = html.unescape(text)
    text = text.replace("�", "")
    lines = [ln.strip() for ln in text.splitlines()]
    out: list[str] = []
    blanks = 0
    for ln in lines:
        ln = _WS_RE.sub(" ", ln).strip()
        if not ln:
            blanks += 1
            if blanks <= 1 and out:
                out.append("")
            continue
        blanks = 0
        out.append(ln)
    return "\n".join(out).strip()


def normalize_edition(raw: str | None) -> str:
    return (raw or "").strip().upper() or "2E"


def dedupe_key(system: str, name: str, category: str) -> tuple[str, str, str]:
    return (system, re.sub(r"\s+", " ", (name or "").strip().lower()), category)


def pick_winner(rows: list[dict]) -> dict:
    def rank(r: dict) -> tuple[int, int]:
        known = 0 if (r.get("source_book") or UNKNOWN) == UNKNOWN else 1
        return (known, len(r.get("raw_content") or ""))

    return max(rows, key=rank)
