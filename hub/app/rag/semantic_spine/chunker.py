# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

from __future__ import annotations

from .model import ChunkRecord, RuleRecord


def chunk_rule(
    record: RuleRecord,
    target_chars: int = 1800,
    overlap_chars: int = 200,
) -> list[ChunkRecord]:
    content = record.content or ""
    parent_id = record.identity()
    if not content:
        chunk = ChunkRecord(
            parent_id=parent_id,
            chunk_index=0,
            total_chunks=1,
            start_char=0,
            end_char=0,
            system=record.system,
            category=record.category,
            name=record.name,
            source_book=record.source_book,
            chunk_text="",
        )
        return [chunk]

    if len(content) <= target_chars:
        chunk = ChunkRecord(
            parent_id=parent_id,
            chunk_index=0,
            total_chunks=1,
            start_char=0,
            end_char=len(content),
            system=record.system,
            category=record.category,
            name=record.name,
            source_book=record.source_book,
            chunk_text=content,
        )
        return [chunk]

    spans: list[tuple[int, int]] = []
    pos = 0
    total_len = len(content)

    while pos < total_len:
        if total_len - pos <= target_chars:
            spans.append((pos, total_len))
            break

        end_limit = min(pos + target_chars, total_len)
        search_start = pos + max(target_chars // 2, target_chars - overlap_chars * 2)

        best_split = -1
        for sep in ("\n\n", "\n", ". ", "; ", ", ", " "):
            idx = content.rfind(sep, search_start, end_limit)
            if idx != -1:
                best_split = idx + len(sep)
                break

        if best_split == -1 or best_split <= pos:
            best_split = end_limit

        spans.append((pos, best_split))

        next_pos = max(best_split - overlap_chars, pos + 1)
        if next_pos >= total_len:
            break

        for sep in ("\n\n", "\n", ". ", " "):
            idx = content.find(sep, next_pos, min(next_pos + overlap_chars, total_len))
            if idx != -1 and idx < best_split:
                next_pos = idx + len(sep)
                break

        if next_pos <= pos:
            next_pos = best_split

        pos = next_pos

    total_chunks = len(spans)
    chunks: list[ChunkRecord] = []
    for idx, (start_char, end_char) in enumerate(spans):
        chunk_text = content[start_char:end_char]
        chunks.append(
            ChunkRecord(
                parent_id=parent_id,
                chunk_index=idx,
                total_chunks=total_chunks,
                start_char=start_char,
                end_char=end_char,
                system=record.system,
                category=record.category,
                name=record.name,
                source_book=record.source_book,
                chunk_text=chunk_text,
            )
        )
    return chunks
