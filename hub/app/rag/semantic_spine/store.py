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
import sys
from contextlib import closing
from pathlib import Path
from typing import Protocol

from .chunker import chunk_rule
from .model import (
    ChunkRecord,
    RankedRule,
    RuleRecord,
    SemanticSpineError,
    cosine,
    normalize_vector,
)


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
    schema_version = "2"
    max_chunk_chars = 4096

    def __init__(self, index_path: Path, source_path: Path) -> None:
        self.index_path = Path(index_path).resolve()
        self.source_path = Path(source_path).resolve()
        if self.index_path == self.source_path:
            raise SemanticSpineError("Semantic sidecar cannot overwrite the rules database")

    @staticmethod
    def _readonly(path: Path) -> sqlite3.Connection:
        return sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=8.0)

    def status(self, *, deep: bool = True) -> dict[str, str]:
        return self._status(deep=deep)

    def _status(self, *, deep: bool) -> dict[str, str]:
        """Index state check.

        ``status()`` runs ``PRAGMA quick_check`` because the CLI reports health.
        Query paths use ``deep=False``: quick_check walks the whole sidecar
        (~0.7 s at 43k chunks), which would dwarf a 7 ms matmul on every
        search. The manifest read still validates the header and schema, and
        the index is immutable after the atomic publish.
        """
        if not self.index_path.is_file():
            return {"state": "absent"}
        try:
            with closing(self._readonly(self.index_path)) as conn:
                if deep:
                    check = conn.execute("PRAGMA quick_check(1)").fetchone()
                    if not check or check[0] != "ok":
                        return {"state": "corrupt"}
                manifest = dict(conn.execute("SELECT key, value FROM manifest"))
        except (sqlite3.DatabaseError, OSError):
            return {"state": "unreadable"}
        if manifest.get("schema_version") != self.schema_version:
            return {"state": "incompatible", **manifest}
        try:
            stamp = _source_stamp(self.source_path)
        except (OSError, SemanticSpineError):
            return {"state": "source-unavailable"}
        if manifest.get("source_stamp") != stamp:
            return {"state": "stale", **manifest}
        return {"state": "ready", **manifest}

    def build(
        self,
        embedder: Embedder,
        batch_size: int = 16,
        chunk_target_chars: int = 1800,
        chunk_overlap_chars: int = 200,
    ) -> dict[str, str]:
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
        staging = self.index_path.with_name(self.index_path.stem + ".staging.sqlite3")
        parent_count = 0
        chunk_count = 0
        last_rowid = 0

        with closing(sqlite3.connect(staging)) as dst:
            dst.execute("PRAGMA synchronous=NORMAL")
            dst.execute("CREATE TABLE IF NOT EXISTS manifest(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            dst.execute(
                "CREATE TABLE IF NOT EXISTS entries ("
                "id TEXT PRIMARY KEY, "
                "source_rowid INTEGER NOT NULL, "
                "parent_id TEXT NOT NULL, "
                "system TEXT NOT NULL, "
                "category TEXT NOT NULL, "
                "name TEXT NOT NULL, "
                "source_book TEXT NOT NULL, "
                "chunk_index INTEGER NOT NULL, "
                "total_chunks INTEGER NOT NULL, "
                "start_char INTEGER NOT NULL, "
                "end_char INTEGER NOT NULL, "
                "content TEXT NOT NULL, "
                "embedding BLOB NOT NULL"
                ")"
            )

            manifest_map = dict(dst.execute("SELECT key, value FROM manifest").fetchall())
            can_resume = (
                manifest_map.get("source_stamp") == source_stamp
                and manifest_map.get("model_identity") == model_identity
                and manifest_map.get("dimensions") == str(dimensions)
                and manifest_map.get("schema_version") == self.schema_version
            )

            if can_resume:
                rowid_row = dst.execute("SELECT COALESCE(MAX(source_rowid), 0) FROM entries").fetchone()
                last_rowid = int(rowid_row[0]) if rowid_row else 0
                if last_rowid > 0:
                    # A parent's chunks can straddle a batch flush. That parent was
                    # committed partially, so rebuild it whole instead of skipping
                    # the chunks that never reached the staging database.
                    dst.execute("DELETE FROM entries WHERE source_rowid = ?", (last_rowid,))
                    dst.commit()
                count_row = dst.execute("SELECT COUNT(DISTINCT parent_id), COUNT(*) FROM entries").fetchone()
                if count_row:
                    parent_count = int(count_row[0])
                    chunk_count = int(count_row[1])
                if last_rowid > 0:
                    sys.stderr.write(
                        f"[BUILD RESUME] Resuming build from rowid {last_rowid} "
                        f"({parent_count} records, {chunk_count} chunks already indexed)\n"
                    )
                    sys.stderr.flush()
            else:
                dst.execute("DELETE FROM entries")
                dst.execute("DELETE FROM manifest")
                init_manifest = {
                    "schema_version": self.schema_version,
                    "model_identity": model_identity,
                    "dimensions": str(dimensions),
                    "source_stamp": source_stamp,
                    "source_path": str(self.source_path),
                }
                dst.executemany("INSERT INTO manifest VALUES (?,?)", init_manifest.items())
                dst.commit()

            with closing(self._readonly(self.source_path)) as src:
                src.row_factory = sqlite3.Row
                cursor = src.execute(
                    "SELECT rowid, system, category, name, source_book, raw_content "
                    "FROM rules WHERE rowid >= ? ORDER BY rowid",
                    (last_rowid,),
                )

                pending_chunks: list[tuple[int, ChunkRecord]] = []

                def flush_batch() -> None:
                    nonlocal chunk_count
                    if not pending_chunks:
                        return
                    texts_to_embed = [c[1].embedding_text() for c in pending_chunks]
                    vectors = embedder.embed(texts_to_embed, query=False)
                    if len(vectors) != len(pending_chunks):
                        raise SemanticSpineError("Incomplete embedding batch")

                    batch_rows = []
                    for (src_rowid, chunk), vector in zip(pending_chunks, vectors):
                        packed = struct.pack(f"<{dimensions}f", *normalize_vector(vector, dimensions))
                        identifier = chunk.chunk_id()
                        batch_rows.append(
                            (
                                identifier,
                                src_rowid,
                                chunk.parent_id,
                                chunk.system,
                                chunk.category,
                                chunk.name,
                                chunk.source_book,
                                chunk.chunk_index,
                                chunk.total_chunks,
                                chunk.start_char,
                                chunk.end_char,
                                chunk.chunk_text,
                                packed,
                            )
                        )
                    dst.executemany("INSERT INTO entries VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", batch_rows)
                    dst.commit()
                    chunk_count += len(batch_rows)
                    pending_chunks.clear()

                while True:
                    rows = cursor.fetchmany(batch_size)
                    if not rows:
                        break
                    for row in rows:
                        record = RuleRecord.from_row(row)
                        parent_count += 1
                        record_chunks = chunk_rule(
                            record,
                            target_chars=chunk_target_chars,
                            overlap_chars=chunk_overlap_chars,
                        )
                        for c in record_chunks:
                            if len(c.chunk_text) > self.max_chunk_chars:
                                raise SemanticSpineError(f"Chunk exceeds maximum size: {c.name}")
                            pending_chunks.append((int(row["rowid"]), c))
                            if len(pending_chunks) >= batch_size:
                                flush_batch()
                        if parent_count % 1000 == 0:
                            sys.stderr.write(
                                f"[BUILD PROGRESS] {parent_count} records processed ({chunk_count} chunks embedded)\n"
                            )
                            sys.stderr.flush()

                flush_batch()

                total_parents = int(dst.execute("SELECT COUNT(DISTINCT parent_id) FROM entries").fetchone()[0])
                total_chunks = int(dst.execute("SELECT COUNT(*) FROM entries").fetchone()[0])

                if total_parents == 0 or total_chunks == 0:
                    raise SemanticSpineError("Refusing to publish an empty semantic index")
                if _source_stamp(self.source_path) != source_stamp:
                    raise SemanticSpineError("Rules database changed during index construction")

                row_digest = hashlib.sha256()
                for (entry_id,) in dst.execute("SELECT id FROM entries ORDER BY id"):
                    row_digest.update(entry_id.encode("ascii"))

                final_manifest = {
                    "schema_version": self.schema_version,
                    "model_identity": model_identity,
                    "dimensions": str(dimensions),
                    "source_stamp": source_stamp,
                    "source_path": str(self.source_path),
                    "rows": str(total_parents),
                    "chunks": str(total_chunks),
                    "row_digest": row_digest.hexdigest(),
                }
                dst.execute("DELETE FROM manifest")
                dst.executemany("INSERT INTO manifest VALUES (?,?)", final_manifest.items())
                dst.execute("CREATE INDEX IF NOT EXISTS idx_entries_system ON entries(system)")
                dst.execute("CREATE INDEX IF NOT EXISTS idx_entries_parent ON entries(parent_id)")
                dst.commit()
                checked = dst.execute("PRAGMA integrity_check").fetchone()[0]
                if checked != "ok":
                    raise SemanticSpineError("Semantic sidecar integrity check failed")

        if _source_stamp(self.source_path) != source_stamp:
            raise SemanticSpineError("Rules database changed before publishing index")
        if self.index_path.is_file():
            shutil.copy2(self.index_path, Path(str(self.index_path) + ".bak"))
        os.replace(staging, self.index_path)
        return {"state": "ready", **final_manifest}

    def search_vector(
        self,
        vector: tuple[float, ...] | list[float],
        edition: str,
        limit: int = 10,
    ) -> list[RankedRule]:
        status = self.status(deep=False)
        if status["state"] != "ready":
            raise SemanticSpineError("Semantic index is not ready: " + status["state"])
        if status.get("source_path") != str(self.source_path):
            raise SemanticSpineError("Index was built against a different rules database path")
        dimensions = int(status["dimensions"])
        if len(vector) < dimensions:
            raise SemanticSpineError("Embedding shorter than configured dimensions")
        needle = normalize_vector(vector, dimensions)
        edition = (edition or "both").lower().strip()
        preferred = ["1E", "2E"] if edition in ("1e", "1", "pf1") else ["2E", "1E"]
        if edition in ("both", "all", "any"):
            preferred = ["2E", "1E"]

        results: list[RankedRule] = []
        with closing(self._readonly(self.index_path)) as conn:
            for system in preferred:
                remaining = limit - len(results)
                if remaining <= 0:
                    break
                results.extend(
                    self._system_candidates(conn, system, needle, dimensions, remaining)
                )
        return results[:limit]

    @staticmethod
    def _system_candidates(
        conn: sqlite3.Connection,
        system: str,
        needle: tuple[float, ...],
        dimensions: int,
        limit: int,
    ) -> list[RankedRule]:
        """Best chunk per parent for one edition, highest score first.

        At full corpus (~24k chunks per edition) a Python cosine per row costs
        seconds per query. Embeddings are stored as little-endian float32, so
        the whole edition is one memcpy into a matrix and one BLAS matmul.
        The pure-Python path stays as the fallback when numpy is unavailable.
        """
        try:
            import numpy as np
        except ImportError:
            np = None

        if np is None:
            best_by_parent: dict[str, tuple[float, sqlite3.Row]] = {}
            cursor = conn.execute(
                "SELECT parent_id, system, category, name, source_book, chunk_index, total_chunks, content, embedding "
                "FROM entries WHERE system=?",
                (system,),
            )
            for row in cursor:
                packed = row[8]
                if len(packed) != 4 * dimensions:
                    raise SemanticSpineError("Index vector length mismatch")
                score = cosine(needle, struct.unpack(f"<{dimensions}f", packed))
                parent_id = row[0]
                if parent_id not in best_by_parent or score > best_by_parent[parent_id][0]:
                    best_by_parent[parent_id] = (score, row)
            ranked = heapq.nlargest(
                limit,
                best_by_parent.values(),
                key=lambda item: (
                    item[0],
                    item[1][4] != "Unknown Source",
                    item[1][3].casefold(),
                ),
            )
            return [
                RankedRule(
                    record=RuleRecord(
                        system=row[1],
                        category=row[2],
                        name=row[3],
                        source_book=row[4],
                        content=row[7],
                    ),
                    score=score,
                    chunk_index=row[5],
                    total_chunks=row[6],
                    chunk_text=row[7],
                )
                for score, row in ranked
            ]

        rows = conn.execute(
            "SELECT rowid, parent_id, system, category, name, source_book, chunk_index, total_chunks, embedding "
            "FROM entries WHERE system=?",
            (system,),
        ).fetchall()
        if not rows:
            return []
        blobs = [row[8] for row in rows]
        if any(len(blob) != 4 * dimensions for blob in blobs):
            raise SemanticSpineError("Index vector length mismatch")
        matrix = np.frombuffer(b"".join(blobs), dtype="<f4").reshape(len(rows), dimensions)
        scores = matrix @ np.asarray(needle, dtype="<f4")

        best_index: dict[str, int] = {}
        for index, row in enumerate(rows):
            parent_id = row[1]
            previous = best_index.get(parent_id)
            if previous is None or scores[index] > scores[previous]:
                best_index[parent_id] = index

        ranked = heapq.nlargest(
            limit,
            best_index.values(),
            key=lambda index: (
                float(scores[index]),
                rows[index][5] != "Unknown Source",
                rows[index][4].casefold(),
            ),
        )
        results: list[RankedRule] = []
        for index in ranked:
            row = rows[index]
            content_row = conn.execute(
                "SELECT content FROM entries WHERE rowid=?", (row[0],)
            ).fetchone()
            content = str(content_row[0]) if content_row else ""
            results.append(
                RankedRule(
                    record=RuleRecord(
                        system=row[2],
                        category=row[3],
                        name=row[4],
                        source_book=row[5],
                        content=content,
                    ),
                    score=float(scores[index]),
                    chunk_index=row[6],
                    total_chunks=row[7],
                    chunk_text=content,
                )
            )
        return results

    def search(self, query: str, edition: str, embedder: Embedder, limit: int = 10) -> list[RankedRule]:
        status = self.status(deep=False)
        if status["state"] != "ready":
            raise SemanticSpineError("Semantic index is not ready: " + status["state"])
        if status.get("model_identity") != embedder.identity() or int(status["dimensions"]) != embedder.dimensions:
            raise SemanticSpineError("Embedding model or dimensions changed; rebuild index")
        if not query.strip() or limit <= 0:
            return []
        vector = embedder.embed([query], query=True)
        if len(vector) != 1:
            raise SemanticSpineError("Missing query embedding")
        return self.search_vector(vector[0], edition, limit=limit)
