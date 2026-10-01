"""Shared FTS5 MATCH query construction.

Two call sites built their own escaping and diverged: `retriever.py` OR-joined
the tokens, `raw_fallback.py` did not. Because FTS5 treats a bare multi-word
string as an implicit AND, every ordinary multi-word question through the
tier-2 fallback returned zero hits.

Quoting every token also removes an entire class of syntax errors: FTS5 rejects
a bare `and`/`or`/`not` in leading or trailing position, so a query like
"how do I attack and" was a hard error rather than a query.
"""

import re

# Characters FTS5 reads as operators. Stripped outright rather than padded with
# spaces, which left dangling operators behind.
_FTS_OPERATORS = "*-+():|@{}[]^~,;\\/"
_KEYWORDS = {"and", "or", "not", "near"}


def build_match_query(query: str) -> str:
    """Build a safe FTS5 MATCH expression from free-form user text.

    Returns an empty string when nothing searchable remains, so callers can
    short-circuit instead of issuing a MATCH that matches nothing.
    """
    cleaned = query or ""
    for ch in _FTS_OPERATORS:
        cleaned = cleaned.replace(ch, " ")
    cleaned = cleaned.replace("?", " ")
    cleaned = " ".join(cleaned.split())

    tokens = [
        t for t in cleaned.split()
        if len(t) > 2 and t.lower() not in _KEYWORDS
    ]
    if not tokens:
        return ""

    # Quote each token so it can never be parsed as FTS5 syntax. Doubling an
    # embedded double quote is the FTS5 escape for a literal quote.
    return " OR ".join('"' + t.replace('"', '""') + '"' for t in tokens)


def normalize_edition(edition: str | None) -> str:
    """Map any user-supplied edition spelling onto '2e' | '1e' | 'both'.

    Previously only the exact strings 'both', '2e', '1e', '2E', '1E' worked.
    Anything else ('Both', 'BOTH', 'pf2', '', 'both ') fell through to a
    `WHERE system = <uppercased input>` bind and silently matched nothing.
    """
    value = (edition or "").strip().lower()
    if value in ("", "both", "all", "any", "default"):
        return "both"
    if value in ("1e", "1", "pf1", "pathfinder1", "first"):
        return "1e"
    if value in ("2e", "2", "pf2", "remaster", "second"):
        return "2e"
    return "both"


def editions_for(edition: str | None) -> list[str]:
    """Ordered list of uppercase DB system codes to search.

    'both' searches 2E then 1E so second-edition rules win ties.
    """
    norm = normalize_edition(edition)
    if norm == "both":
        return ["2E", "1E"]
    if norm == "1e":
        return ["1E", "2E"]
    return ["2E", "1E"]


_WORD_RE = re.compile(r"\s+")


def tokenize(query: str) -> list[str]:
    """Split already-escaped text into tokens."""
    return [t for t in _WORD_RE.split(query or "") if t]