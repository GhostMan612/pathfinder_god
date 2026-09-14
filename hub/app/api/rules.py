# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Rules Search endpoint — Raw FTS5 lookup (no LLM).
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.deps import get_repo
from app.db.repository import CampaignRepository
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