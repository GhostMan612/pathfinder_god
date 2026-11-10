# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

from __future__ import annotations

from app.rag.semantic_spine import RankedRule, RuleRecord, chunk_rule


def test_empty_content_returns_single_empty_chunk():
    rule = RuleRecord(
        system="2E",
        category="action",
        name="EmptyRule",
        source_book="Player Core",
        content="",
    )
    chunks = chunk_rule(rule, target_chars=1800, overlap_chars=200)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_index == 0
    assert chunk.total_chunks == 1
    assert chunk.start_char == 0
    assert chunk.end_char == 0
    assert chunk.chunk_text == ""
    assert chunk.name == "EmptyRule"
    assert chunk.system == "2E"
    assert chunk.source_book == "Player Core"
    assert chunk.chunk_id().endswith(":0000")


def test_short_content_returns_single_chunk():
    text = "When you and an ally are on opposite sides of a foe, that foe is off-guard."
    rule = RuleRecord(
        system="2E",
        category="action",
        name="Flanking",
        source_book="Player Core",
        content=text,
    )
    chunks = chunk_rule(rule, target_chars=1800, overlap_chars=200)
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.chunk_index == 0
    assert chunk.total_chunks == 1
    assert chunk.start_char == 0
    assert chunk.end_char == len(text)
    assert chunk.chunk_text == text


def test_exact_target_chars_boundary():
    text = "x" * 1800
    rule = RuleRecord(
        system="2E",
        category="action",
        name="ExactRule",
        source_book="Player Core",
        content=text,
    )
    chunks = chunk_rule(rule, target_chars=1800, overlap_chars=200)
    assert len(chunks) == 1
    assert chunks[0].chunk_text == text


def test_chunk_ids_and_embedding_text():
    paragraphs = [f"Section {i} with several sentences describing specific mechanics and traits." for i in range(25)]
    full_text = "\n\n".join(paragraphs)
    rule = RuleRecord(
        system="2E",
        category="feat",
        name="ComplexFeat",
        source_book="Player Core",
        content=full_text,
    )
    chunks = chunk_rule(rule, target_chars=500, overlap_chars=50)
    assert len(chunks) > 1
    for idx, c in enumerate(chunks):
        assert c.chunk_id() == f"{rule.identity()}:{idx:04d}"
        assert c.chunk_index == idx
        assert c.total_chunks == len(chunks)
        embed_text = c.embedding_text()
        assert f"Edition: {rule.system}" in embed_text
        assert f"Name: {rule.name}" in embed_text
        assert f"Section: [{idx + 1}/{len(chunks)}]" in embed_text
        assert c.chunk_text in embed_text


def test_100_percent_coverage_zero_content_loss():
    paragraphs = [
        f"Paragraph {i}: Pathfinder second edition offers structured tactical combat with three-action economies. "
        f"Every character possesses unique feats and proficiencies that determine their capabilities in combat."
        for i in range(40)
    ]
    full_text = "\n\n".join(paragraphs)
    rule = RuleRecord(
        system="2E",
        category="general",
        name="TacticsOverview",
        source_book="Player Core",
        content=full_text,
    )
    chunks = chunk_rule(rule, target_chars=1200, overlap_chars=150)
    assert len(chunks) > 1
    assert chunks[0].start_char == 0
    assert chunks[-1].end_char == len(full_text)

    covered = [False] * len(full_text)
    for c in chunks:
        assert c.start_char < c.end_char
        for pos in range(c.start_char, c.end_char):
            covered[pos] = True
        assert full_text[c.start_char:c.end_char] == c.chunk_text

    assert all(covered)


def test_chunk_monotonicity_and_overlap_bounds():
    text = "word " * 2000
    rule = RuleRecord(
        system="1E",
        category="rules",
        name="LongRule",
        source_book="Core Rulebook 1E",
        content=text,
    )
    chunks = chunk_rule(rule, target_chars=1000, overlap_chars=100)
    assert len(chunks) >= 8
    for i in range(len(chunks) - 1):
        assert chunks[i].chunk_index == i
        assert chunks[i + 1].start_char < chunks[i].end_char
        assert chunks[i + 1].start_char >= chunks[i].start_char
        overlap = chunks[i].end_char - chunks[i + 1].start_char
        assert overlap > 0


def test_paragraph_and_section_boundary_splitting():
    p1 = "Paragraph 1 ends here cleanly with double newline.\n\n"
    p2 = "Paragraph 2 contains vital information regarding spellcasting and actions.\n\n"
    p3 = "Paragraph 3 concludes the rule description."
    full_text = p1 * 15 + p2 * 15 + p3
    rule = RuleRecord(
        system="2E",
        category="rules",
        name="MultiSection",
        source_book="Player Core",
        content=full_text,
    )
    chunks = chunk_rule(rule, target_chars=1500, overlap_chars=200)
    assert len(chunks) > 1
    for c in chunks[:-1]:
        assert c.chunk_text.endswith(("\n", ".", " ", ";", ","))


def test_massive_50k_omnibus_record_chunking():
    paragraphs = [
        f"Heading {i}: An omnibus monster rule entry with long description of aura, breath weapon, and immunities. "
        f"Creatures within range must succeed at a saving throw or suffer severe afflictions."
        for i in range(350)
    ]
    full_text = "\n\n".join(paragraphs)
    assert len(full_text) > 50000

    rule = RuleRecord(
        system="2E",
        category="bestiary",
        name="Universal Monster Rules",
        source_book="Monster Core",
        content=full_text,
    )
    chunks = chunk_rule(rule, target_chars=1800, overlap_chars=200)
    assert len(chunks) >= 25
    assert all(len(c.chunk_text) <= 4096 for c in chunks)
    assert chunks[0].start_char == 0
    assert chunks[-1].end_char == len(full_text)
    assert all(c.name == "Universal Monster Rules" for c in chunks)
    assert all(c.system == "2E" for c in chunks)
    assert all(c.source_book == "Monster Core" for c in chunks)


def test_ranked_rule_public_hit_returns_chunk_excerpt():
    rule = RuleRecord(
        system="2E",
        category="feat",
        name="ParentFeat",
        source_book="Player Core",
        content="Entire huge parent rule content here.",
    )
    ranked = RankedRule(
        record=rule,
        score=0.92,
        chunk_index=2,
        total_chunks=5,
        chunk_text="Bounded excerpt from section 3.",
    )
    hit = ranked.public_hit()
    assert hit["name"] == "ParentFeat"
    assert hit["source_book"] == "Player Core"
    assert hit["system"] == "2E"
    assert hit["category"] == "feat"
    assert hit["content"] == "Bounded excerpt from section 3."
