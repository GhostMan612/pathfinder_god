# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass


class SemanticSpineError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuleRecord:
    system: str
    category: str
    name: str
    source_book: str
    content: str

    @classmethod
    def from_row(cls, row: object) -> RuleRecord:
        return cls(
            system=str(row["system"] or ""),
            category=str(row["category"] or ""),
            name=str(row["name"] or ""),
            source_book=str(row["source_book"] or ""),
            content=str(row["raw_content"] or ""),
        )

    def identity(self) -> str:
        fields = (self.system, self.category, self.name, self.source_book, self.content)
        return hashlib.sha256(json.dumps(fields, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()

    def embedding_text(self) -> str:
        return f"Edition: {self.system}\nCategory: {self.category}\nName: {self.name}\nSource: {self.source_book}\nRule: {self.content}"

    def public_hit(self) -> dict[str, str]:
        return {
            "system": self.system,
            "category": self.category,
            "name": self.name,
            "source_book": self.source_book,
            "content": self.content,
        }


@dataclass(frozen=True)
class ChunkRecord:
    parent_id: str
    chunk_index: int
    total_chunks: int
    start_char: int
    end_char: int
    system: str
    category: str
    name: str
    source_book: str
    chunk_text: str

    def chunk_id(self) -> str:
        return f"{self.parent_id}:{self.chunk_index:04d}"

    def embedding_text(self) -> str:
        header = f"Edition: {self.system}\nCategory: {self.category}\nName: {self.name}\nSource: {self.source_book}"
        if self.total_chunks > 1:
            header += f"\nSection: [{self.chunk_index + 1}/{self.total_chunks}]"
        return f"{header}\nRule: {self.chunk_text}"


@dataclass(frozen=True)
class RankedRule:
    record: RuleRecord
    score: float
    chunk_index: int = 0
    total_chunks: int = 1
    chunk_text: str = ""

    def public_hit(self) -> dict[str, str]:
        hit = self.record.public_hit()
        if self.chunk_text:
            hit["content"] = self.chunk_text
        return hit


def normalize_vector(values: Iterable[float], dimensions: int) -> tuple[float, ...]:
    if dimensions not in (128, 256, 512, 768):
        raise SemanticSpineError("Unsupported dimensions; choose 128, 256, 512, or 768")
    numbers = tuple(float(x) for x in values)
    if len(numbers) < dimensions:
        raise SemanticSpineError("Embedding shorter than configured dimensions")
    numbers = numbers[:dimensions]
    if any(not math.isfinite(x) for x in numbers):
        raise SemanticSpineError("Embedding contains non-finite components")
    magnitude = math.sqrt(sum(x * x for x in numbers))
    if magnitude <= 1e-12:
        raise SemanticSpineError("Embedding has zero magnitude")
    return tuple(x / magnitude for x in numbers)


def cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if len(left) != len(right):
        raise SemanticSpineError("Embedding dimension mismatch")
    return sum(a * b for a, b in zip(left, right))
