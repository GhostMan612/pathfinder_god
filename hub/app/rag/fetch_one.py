# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""On-demand single-term fetch — "ask, scrape, keep forever".

When a user asks for something missing from the database, /rules/fetch
tries to pull exactly that term from open sources and INSERT it, so the
next identical query is a plain DB hit. 1e path is live (AoN 1e search +
Paizo PRD slug fallback, both verified 2026-09-14). 2e single-fetch is not
wired yet — 2e misses are logged for the chunked fleet backfill instead.

Politeness: uses the shared fleet transport (rotating UA, probed 0.5s+
intervals, backoff). One term = a handful of requests, far under limits.
"""
from __future__ import annotations

import html
import logging
import re
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote, unquote

logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
try:
    from fleet import DomainLimiter, FetchError, fetch as fleet_fetch
except Exception:  # fleet unavailable (tests without aiohttp) — caller degrades
    DomainLimiter = None  # type: ignore
    FetchError = Exception  # type: ignore
    fleet_fetch = None  # type: ignore

from app.config import get_settings

AON1E_SEARCH = "https://www.aonprd.com/Search.aspx?query="
PRD_SPELL = "https://paizo.com/pathfinderRPG/prd/coreRulebook/spells/"

DISPLAY_CATEGORY = {
    "SpellDisplay": "spell",
    "FeatDisplay": "feat",
    "MonsterDisplay": "bestiary",
    "MagicItemDisplay": "equipment",
    "MagicWeaponDisplay": "equipment",
    "MagicArmorDisplay": "equipment",
    "ClassDisplay": "class",
    "PrestigeClassDisplay": "class",
    "RaceDisplay": "ancestry",
    "SkillDisplay": "skill",
    "TraitDisplay": "trait",
    "DeityDisplay": "deity",
    "ArchetypeDisplay": "archetype",
}


def _strip(text: str) -> str:
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"</p\s*>|<br\s*/?>|</li\s*>|</tr\s*>|</div\s*>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text).replace("�", "")
    text = re.sub(r"[ \t\xa0\u200b\ufeff]+", " ", text)
    lines = [ln.strip() for ln in text.splitlines()]
    out, blanks = [], 0
    for ln in lines:
        if not ln:
            blanks += 1
            if blanks <= 1 and out:
                out.append("")
            continue
        blanks = 0
        out.append(ln)
    return "\n".join(out).strip()


def _db_path() -> str | None:
    for p in get_settings().db_paths:
        if p.exists():
            return str(p)
    return None


def _exact(db: str, term: str, edition: str) -> dict | None:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT system, category, name, source_book, raw_content FROM rules"
            " WHERE system = ? AND name = ? COLLATE NOCASE LIMIT 1",
            (edition, term.strip()),
        ).fetchone()
        if row is None:
            return None
        return {
            "system": row["system"], "category": row["category"],
            "name": row["name"], "source_book": row["source_book"],
            "content": row["raw_content"],
        }
    finally:
        conn.close()


def _store(db: str, row: dict) -> None:
    conn = sqlite3.connect(db)
    try:
        cur = conn.execute(
            "SELECT rowid, source_book FROM rules"
            " WHERE system = ? AND name = ? COLLATE NOCASE LIMIT 1",
            (row["system"], row["name"]),
        ).fetchone()
        if cur is None:
            conn.execute(
                "INSERT INTO rules (system, category, name, source_book, raw_content)"
                " VALUES (?, ?, ?, ?, ?)",
                (row["system"], row["category"], row["name"],
                 row["source_book"], row["content"]),
            )
        elif (cur[1] or "Unknown Source") == "Unknown Source":
            conn.execute(
                "UPDATE rules SET category = ?, source_book = ?, raw_content = ?"
                " WHERE rowid = ?",
                (row["category"], row["source_book"], row["content"], cur[0]),
            )
        conn.commit()
    finally:
        conn.close()


def _aon1e_links(search_html: str) -> list[tuple[str, str]]:
    """(page_prefix, item_name) pairs from an AoN 1e search page."""
    out = []
    for m in re.finditer(r'href="((?:Spell|Feat|Monster|MagicItem|MagicWeapon|MagicArmor|Class|PrestigeClass|Race|Skill|Trait|Deity|Archetype)[^"]*?ItemName=([^"]+))"', search_html):
        out.append((m.group(1).split("Display")[0] + "Display", unquote(m.group(2))))
    return out


def _category_for(page: str) -> str:
    for prefix, cat in DISPLAY_CATEGORY.items():
        if page.startswith(prefix):
            return cat
    return "rule"


async def _fetch_1e(term: str, db: str) -> dict | None:
    import aiohttp

    limiter = DomainLimiter() if DomainLimiter else None
    async with aiohttp.ClientSession() as session:
        search_html = await fleet_fetch(
            session, AON1E_SEARCH + quote(term), limiter=limiter)
        links = _aon1e_links(search_html)
        if not links:
            return None
        want = term.strip().lower()
        links.sort(key=lambda t: 0 if t[1].strip().lower() == want else 1)
        page, item = links[0]
        detail = await fleet_fetch(
            session, f"https://www.aonprd.com/{page}.aspx?ItemName=" + quote(item),
            limiter=limiter)
        text = _strip(detail)
        if len(text) < 60:
            return None
        source = "Archives of Nethys 1e"
        m = re.search(r"Source\s*:?\s*([^\n]{2,80})", text)
        if m:
            source = m.group(1).strip()
        row = {
            "system": "1E",
            "category": _category_for(page),
            "name": item.strip(),
            "source_book": source,
            "content": f"# {item.strip()}\n\n**Source:** {source}\n\n{text[:8000]}",
        }
        _store(db, row)
        return row


def _prd_slug(term: str) -> str:
    words = re.findall(r"[A-Za-z]+", term)
    if not words:
        return ""
    return words[0].lower() + "".join(w.capitalize() for w in words[1:])


async def _fetch_prd_spell(term: str, db: str) -> dict | None:
    import aiohttp

    slug = _prd_slug(term)
    if not slug:
        return None
    limiter = DomainLimiter() if DomainLimiter else None
    async with aiohttp.ClientSession() as session:
        try:
            html = await fleet_fetch(session, PRD_SPELL + slug + ".html", limiter=limiter)
        except Exception:
            return None
    m = re.search(r"(?is)<title>(.*?)</title>", html)
    title = (m.group(1).strip() if m else "")
    if not title or title.lower() not in (term.strip().lower(), slug.lower()):
        # PRD serves soft-404s; require the title to actually match
        if term.strip().lower() not in title.lower():
            return None
    text = _strip(html)
    if len(text) < 60:
        return None
    row = {
        "system": "1E",
        "category": "spell",
        "name": title,
        "source_book": "Core Rulebook",
        "content": f"# {title}\n\n**Source:** Core Rulebook\n\n{text[:8000]}",
    }
    _store(db, row)
    return row


async def fetch_one(term: str, edition: str = "1e") -> dict | None:
    """Fetch one missing term into the DB. Returns the row or None."""
    term = (term or "").strip()
    if not term or fleet_fetch is None:
        return None
    db = _db_path()
    if db is None:
        return None
    ed = "1E" if edition.lower().startswith("1") else "2E"
    hit = _exact(db, term, ed)
    if hit:
        return hit
    if ed != "1E":
        return None
    try:
        hit = await _fetch_1e(term, db)
        if hit:
            logger.info(f"fetch-one: scraped 1e '{term}' -> {hit['name']}")
            return hit
    except Exception as e:
        logger.warning(f"fetch-one 1e AoN failed for '{term}': {e}")
    try:
        hit = await _fetch_prd_spell(term, db)
        if hit:
            logger.info(f"fetch-one: PRD spell '{term}' -> {hit['name']}")
            return hit
    except Exception as e:
        logger.warning(f"fetch-one PRD failed for '{term}': {e}")
    return None
