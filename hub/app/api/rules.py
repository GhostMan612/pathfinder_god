# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Rules Search endpoint — Raw FTS5 lookup (no LLM).
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import get_repo
from app.db.repository import CampaignRepository
from app.rag import misslog
from app.rag.fetch_one import fetch_one
from app.rag.retriever import Retriever

router = APIRouter(prefix="/rules", tags=["rules"])


class RuleHit(BaseModel):
    name: str
    content: str
    system: str = ""
    category: str = ""
    source_book: str = ""


class RulesSearchResponse(BaseModel):
    query: str
    edition: str
    results: list[RuleHit]


# ──────────────────────────────────────────────────────────────
# Rules Search endpoint
# ──────────────────────────────────────────────────────────────

@router.get("/search", response_model=RulesSearchResponse)
async def search_rules(
    q: str = Query(..., description="Search query"),
    edition: str = Query("both", description="Edition: 1e, 2e, or both"),
    limit: int = Query(5, ge=1, le=20),
    repo: CampaignRepository = Depends(get_repo),
) -> RulesSearchResponse:
    retriever = Retriever(repo)
    results = await retriever.search(query=q, edition=edition, limit=limit)

    return RulesSearchResponse(
        query=q,
        edition=edition,
        results=[RuleHit(**r) for r in results],
    )


class FetchRequest(BaseModel):
    q: str
    edition: str = "both"


class MissedQuery(BaseModel):
    q: str
    edition: str = "both"


class MissedBatch(BaseModel):
    queries: list[MissedQuery]


@router.post("/fetch", response_model=RuleHit)
async def fetch_missing_rule(body: FetchRequest) -> RuleHit:
    """On-demand scrape: fetch one missing term into the DB, permanently.

    1e terms are scraped live (AoN 1e search, PRD spell fallback). Anything
    else is queued to data/misses.jsonl for the chunked fleet backfill.
    """
    hit = await fetch_one(body.q, body.edition)
    if hit is None:
        misslog.log_miss(body.q, body.edition, source="fetch")
        raise HTTPException(
            status_code=404,
            detail="Not found and not fetchable right now — queued for backfill.",
        )
    return RuleHit(
        name=hit["name"],
        content=hit["content"],
        system=hit.get("system", ""),
        category=hit.get("category", ""),
        source_book=hit.get("source_book", ""),
    )


@router.post("/missed")
async def report_missed(body: MissedBatch) -> dict:
    """Drain a Spoke offline miss queue into data/misses.jsonl."""
    n = 0
    for item in body.queries[:200]:
        misslog.log_miss(item.q, item.edition, source="spoke-queue")
        n += 1
    return {"queued": n}


@router.get("/missed")
async def list_missed(limit: int = Query(200, ge=1, le=1000)) -> dict:
    """Queued misses, oldest first — feed for chunked backfill runs."""
    misses = misslog.read_misses(limit=limit)
    return {"count": len(misses), "misses": misses}