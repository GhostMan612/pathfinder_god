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
    ollama_num_predict: int = 1200  # room for full character JSON + bio
    ollama_temperature: float = 0.3
    ollama_timeout_s: float = 600.0

    # --- Task model routing (different agents earn different models) ---
    # The hub has two strong small models installed. qwen2.5:3b carries the
    # live GM chat because it is the only one that reliably performs the
    # ReAct tool loop (Rules Lawyer / NPC Compiler / Continuity), while
    # phi4-mini carries the hard reasoning the Rules Lawyer does. Override
    # any of these from .env with PFGOD_MODEL_*.
    model_chat: str = "qwen2.5:3b"      # /ask + /stream live GM narration (tool-capable)
    model_reasoning: str = "phi4-mini"  # Rules Lawyer grounding/citations
    model_builders: str = "qwen2.5:3b"   # character/npc/loot/map/encounter JSON
    model_continuity: str = "qwen2.5:3b" # session compression

    # Stage 5 routing: set true to force every turn through the Rules Lawyer
    # tool loop (slower, maximum citation fidelity). Default false lets the
    # orchestrator route rules-intent turns to the tools and narration turns to
    # a single fast pass.
    force_rules_tools: bool = False

    def model_for(self, task: str) -> str:
        """Return the model assigned to a logical task, falling back to the
        single all-purpose model name for unknown tasks."""
        table = {
            "chat": self.model_chat,
            "gm": self.model_chat,
            "narrator": self.model_chat,
            "reasoning": self.model_reasoning,
            "rules": self.model_reasoning,
            "lawyer": self.model_reasoning,
            "builder": self.model_builders,
            "builders": self.model_builders,
            "json": self.model_builders,
            "character": self.model_builders,
            "npc": self.model_builders,
            "map": self.model_builders,
            "encounter": self.model_builders,
            "loot": self.model_builders,
            "continuity": self.model_continuity,
            "summary": self.model_continuity,
        }
        return table.get(task, self.ollama_model)

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000

    # Referenced by monitoring.py /version and /health/detailed. It was missing
    # from this model, so both endpoints raised AttributeError and returned 500.
    environment: str = "local"

    # --- Auth ---
    # Referenced by app/api/security.py for JWT signing. It was also missing,
    # so every Bearer-token request raised AttributeError and returned 500
    # instead of 401. Empty means "JWT signing disabled"; generate one with:
    # python -c "import secrets;print(secrets.token_urlsafe(48))"
    secret_key: str = ""
    # SHA-256 of the API key clients must present. Empty disables API-key auth.
    api_key_sha256: str = ""

    

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
