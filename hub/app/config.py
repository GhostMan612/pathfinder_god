# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Central configuration for the hub.

All settings can be overridden with environment variables (or a local ``.env``),
so the same code runs on the laptop (native Windows or WSL) without edits.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root = two levels up from this file (hub/app/config.py -> repo/).
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_DIR = REPO_ROOT / "data"


class Settings(BaseSettings):
    """Runtime settings for the Pathfinder God hub."""

    model_config = SettingsConfigDict(
        env_prefix="PFGOD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Pathfinder God Hub"
    version: str = "0.1.0"

    # --- Where the big rules databases live (laptop-only, git-ignored) ---
    data_dir: Path = DEFAULT_DATA_DIR

    # Ordered by preference; the first that exists is used. The unified DB
    # (pathfinder_rag.db) carries a `system` column so it can serve both editions.
    db_filenames: tuple[str, ...] = (
        "pathfinder_rag.db",
        "pathfinder_god.db",
        "pathfinder_1e_rag.db",
        "pathfinder_2e_rag.db",
    )

    # --- Local LLM (Ollama) ---
    # The laptop is CPU-only, so default to a small, fast model.
    ollama_host: str = "http://127.0.0.1:11450"
    ollama_model: str = "phi4-mini"
    ollama_num_predict: int = 700  # room for a full biography/backstory
    ollama_temperature: float = 0.6
    ollama_timeout_s: float = 120.0

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000

    

    # --- Retrieval ---
    rag_limit: int = 4  # rule snippets pulled into context per request
    rag_enabled: bool = True

    # --- Campaign state ---
    campaign_state_path: Path = DEFAULT_DATA_DIR / "campaign_state.json"

    @property
    def db_paths(self) -> list[Path]:
        """Absolute paths of the configured DB files (whether or not they exist)."""
        return [self.data_dir / name for name in self.db_filenames]


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()


settings = get_settings()
