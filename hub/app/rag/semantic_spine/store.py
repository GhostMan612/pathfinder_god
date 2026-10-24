# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

from __future__ import annotations

import hashlib
import heapq
import json
import os
import shutil
import sqlite3
import struct
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Protocol

from .model import RankedRule, RuleRecord, SemanticSpineError, cosine, normalize_vector


class Embedder(Protocol):
    dimensions: int

    def identity(self) -> str: ...

    def embed(self, texts: list[str], *, query: bool = False) -> list[tuple[float, ...]]: ...


def _source_stamp(source: Path) -> str:
    parts = []
    for path in (source, Path(str(source) + "-wal"), Path(str(source) + "-shm")):
        if path.exists():
            info = path.stat()
            parts.append((path.name, info.st_size, info.st_mtime_ns))
    if not parts or parts[0][0] != source.name:
        raise SemanticSpineError("Source rules database is unavailable")
    return hashlib.sha256(json.dumps(parts, separators=(",", ":")).encode("utf-8")).hexdigest()


class SemanticStore:
    schema_version = "1"
    max_record_chars = 8192

    def __init__(self, index_path: Path, source_path: Path) -> None:
        self.index_path = Path(index_path).resolve()
        self.source_path = Path(source_path).resolve()
        if self.index_path == self.source_path:
            raise SemanticSpineError("Semantic sidecar cannot overwrite the rules database")

    @staticmethod
    def _readonly(path: Path) -> sqlite3.Connection:
        return sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=8.0)

    def status(self) -> dict[str, str]:
        if not self.index_path.is_file():
            return {"state": "absent"}
        try:
            with closing(self._readonly(self.index_path)) as conn:
                manifest = dict(conn.execute("SELECT key, value FROM manifest"))
        except (sqlite3.DatabaseError, OSError):
            return {"state": "unreadable"}
        if manifest.get("schema_version") != self.schema_version:
            return {"state": "incompatible"}
        try:
            stamp = _source_stamp(self.source_path)
        except (OSError, SemanticSpineError):
            return {"state": "source-unavailable"}
        if manifest.get("source_stamp") != stamp:
            return {"state": "stale", **manifest}
        return {"state": "ready", **manifest}

    def build(self, embedder: Embedder, batch_size: int = 16) -> dict[str, str]:
        if not self.source_path.is_file():
            raise SemanticSpineError("Source rules database is unavailable")
        if not (1 <= batch_size <= 128):
            raise SemanticSpineError("Batch size must be between 1 and 128")
        model_identity = embedder.identity()
        dimensions = embedder.dimensions
        if dimensions not in (128, 256, 512, 768):
            raise SemanticSpineError("Unsupported embedding dimensions")
        source_stamp = _source_stamp(self.source_path)
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        fd, filename = tempfile.mkstemp(prefix=".semantic-build-", suffix=".sqlite3", dir=self.index_path.parent)
        os.close(fd)
        staging = Path(filename)
        count = 0
        digest = hashlib.sha256()
        try:
            with closing(self._readonly(self.source_path)) as src:
                src.row_factory = sqlite3.Row
                src.execute("BEGIN")
                with closing(sqlite3.connect(staging)) as dst:
                    dst.execute("PRAGMA synchronous=FULL")
                    dst.execute("CREATE TABLE manifest(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                    dst.execute(
                        "CREATE TABLE entries ("
                        "id TEXT PRIMARY KEY, "
                        "system TEXT NOT NULL, "
                        "category TEXT NOT NULL, "
                        "name TEXT NOT NULL, "
                        "source_book TEXT NOT NULL, "
                        "content TEXT NOT NULL, "
                        "embedding BLOB NOT NULL"
                        ")"
                    )
                    cursor = src.execute(
                        "SELECT rowid, system, category, name, source_book, raw_content "
                        "FROM rules ORDER BY rowid"
                    )
                    while True:
                        rows = cursor.fetchmany(batch_size)
                        if not rows:
                            break
                        records = [RuleRecord.from_row(row) for row in rows]
                        for record in records:
                            if len(record.embedding_text()) > self.max_record_chars:
                                raise SemanticSpineError(f"Record exceeds maximum context budget: {record.name}")
                        vectors = embedder.embed([r.embedding_text() for r in records], query=False)
                        if len(vectors) != len(records):
                            raise SemanticSpineError("Incomplete embedding batch")
                        batch = []
                        for row, record, vector in zip(rows, records, vectors):
                            packed = struct.pack(f"<{dimensions}f", *normalize_vector(vector, dimensions))
                            identifier = hashlib.sha256((str(row["rowid"]) + ":" + record.identity()).encode("utf-8")).hexdigest()
                            digest.update(identifier.encode("ascii"))
                            batch.append((identifier, record.system, record.category, record.name, record.source_book, record.content, packed))
                        dst.executemany("INSERT INTO entries VALUES (?,?,?,?,?,?,?)", batch)
                        dst.commit()
                        count += len(batch)
                    if count == 0:
                        raise SemanticSpineError("Refusing to publish an empty semantic index")
                    if _source_stamp(self.source_path) != source_stamp:
                        raise SemanticSpineError("Rules database changed during index construction")
                    manifest = {
                        "schema_version": self.schema_version,
                        "model_identity": model_identity,
                        "dimensions": str(dimensions),
                        "source_stamp": source_stamp,
                        "source_path": str(self.source_path),
                        "rows": str(count),
                        "row_digest": digest.hexdigest(),
                    }
                    dst.executemany("INSERT INTO manifest VALUES (?,?)", manifest.items())
                    dst.execute("CREATE INDEX idx_entries_system ON entries(system)")
                    dst.commit()
                    checked = dst.execute("PRAGMA integrity_check").fetchone()[0]
                    if checked != "ok":
                        raise SemanticSpineError("Semantic sidecar integrity check failed")
            if _source_stamp(self.source_path) != source_stamp:
                raise SemanticSpineError("Rules database changed before publishing index")
            if self.index_path.is_file():
                shutil.copy2(self.index_path, Path(str(self.index_path) + ".bak"))
            os.replace(staging, self.index_path)
            return {"state": "ready", **manifest}
        finally:
            if staging.exists():
                staging.unlink()

    def search(self, query: str, edition: str, embedder: Embedder, limit: int = 10) -> list[RankedRule]:
        status = self.status()
        if status["state"] != "ready":
            raise SemanticSpineError("Semantic index is not ready: " + status["state"])
        if status.get("source_path") != str(self.source_path):
            raise SemanticSpineError("Index was built against a different rules database path")
        if status.get("model_identity") != embedder.identity() or int(status["dimensions"]) != embedder.dimensions:
            raise SemanticSpineError("Embedding model or dimensions changed; rebuild index")
        if not query.strip() or limit <= 0:
            return []
        vector = embedder.embed([query], query=True)
        if len(vector) != 1:
            raise SemanticSpineError("Missing query embedding")
        needle = normalize_vector(vector[0], embedder.dimensions)
        edition = (edition or "both").lower().strip()
        preferred = ["1E", "2E"] if edition in ("1e", "1", "pf1") else ["2E", "1E"]
        if edition in ("both", "all", "any"):
            preferred = ["2E", "1E"]
        results: list[RankedRule] = []
        with closing(self._readonly(self.index_path)) as conn:
            for system in preferred:
                ranked = []
                cursor = conn.execute(
                    "SELECT system,category,name,source_book,content,embedding FROM entries WHERE system=?",
                    (system,),
                )
                for row in cursor:
                    packed = row[5]
                    dimensions = embedder.dimensions
                    if len(packed) != 4 * dimensions:
                        raise SemanticSpineError("Index vector length mismatch")
                    vector_values = struct.unpack(f"<{dimensions}f", packed)
                    score = cosine(needle, vector_values)
                    record = RuleRecord(system=row[0], category=row[1], name=row[2], source_book=row[3], content=row[4])
                    ranked.append(RankedRule(record=record, score=score))
                selected = heapq.nlargest(
                    limit - len(results),
                    ranked,
                    key=lambda item: (item.score, item.record.source_book != "Unknown Source", item.record.name.casefold()),
                )
                results.extend(selected)
                if len(results) >= limit:
                    break
        return results[:limit]
