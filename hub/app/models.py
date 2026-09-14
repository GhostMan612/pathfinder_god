# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Pydantic request/response models — the wire contract with the Flutter app.

These drive the auto-generated OpenAPI schema in ``shared/openapi.yaml``, from
which the Dart client is generated. Keep field names stable.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Edition = Literal["1e", "2e", "both"]

# Generation modes the God understands.
GenerateKind = Literal["character", "npc", "monster", "boss", "map", "campaign", "encounter"]


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str
    ollama_model: str
    deepseek_enabled: bool
    databases_found: list[str] = Field(default_factory=list)


class AskRequest(BaseModel):
    query: str = Field(..., description="The GM question or free-form request.")
    edition: Edition = "both"
    mode: GenerateKind | None = Field(
        default=None, description="Force a generation mode; omit to auto-detect."
    )
    history: list[tuple[str, str]] = Field(
        default_factory=list,
        description="Recent (speaker, message) turns for continuity, e.g. ('user', '...').",
    )


class RuleHitModel(BaseModel):
    name: str
    content: str
    system: str = ""
    category: str = ""
    source_book: str = ""


class AskResponse(BaseModel):
    answer: str
    backend: Literal["deepseek", "ollama", "raw-excerpts"]
    mode: str
    edition: str
    sources: list[RuleHitModel] = Field(default_factory=list)


class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="What to create, e.g. 'a cunning goblin alchemist boss'.")
    edition: Edition = "both"


class RulesSearchResponse(BaseModel):
    query: str
    edition: str
    results: list[RuleHitModel]


class CampaignNote(BaseModel):
    prompt: str
    response: str


class CampaignStateModel(BaseModel):
    party: list[dict] = Field(default_factory=list)
    notes: list[CampaignNote] = Field(default_factory=list)


# WebSocket message shapes (documented for the client; sent as JSON text frames).
class StreamStart(BaseModel):
    type: Literal["start"] = "start"
    backend: str
    mode: str
    edition: str


class StreamChunk(BaseModel):
    type: Literal["chunk"] = "chunk"
    text: str


class StreamEnd(BaseModel):
    type: Literal["end"] = "end"
    sources: list[RuleHitModel] = Field(default_factory=list)
