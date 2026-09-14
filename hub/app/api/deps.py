# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""
Dependency injection providers for FastAPI routes.
"""

from functools import lru_cache

from app.config import settings
from app.db.repository import CampaignRepository


@lru_cache
def get_repo() -> CampaignRepository:
    """Get or create the campaign repository singleton."""
    return CampaignRepository(str(settings.data_dir / "campaign.db"))