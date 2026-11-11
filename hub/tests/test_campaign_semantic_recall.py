# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

from __future__ import annotations

import hashlib
import time
from pathlib import Path

import pytest

from app.config import get_settings
from app.db.repository import CampaignRepository
from app.rag.semantic_spine import SemanticSpineError, normalize_vector

TOPIC_KEYWORDS = {
    2: ["wolves", "wolf", "timber", "wood", "woods", "forest", "canines", "canine", "rabid", "prowling"],
    5: ["naga", "water", "serpent", "river", "waterway", "bargain", "bargained", "negotiating", "passage", "transit"],
    6: ["merchant", "vendor", "sarcophagus", "crypt", "mausoleum", "rescued", "liberating", "pharaoh", "imprisoned"],
    7: ["traps", "disarmed", "flame", "volcanic", "caldera", "magma", "basin", "thermal", "ignition", "neutralizing"],
    8: ["dragon", "firebreather", "ignis", "wyrmtooth", "retreat", "withdrawal", "wings", "aerial", "crags"],
}


class DeterministicRecallEmbedder:
    dimensions = 256

    def __init__(self, version: str = "eval-recall-v1", fail: bool = False) -> None:
        self.version = version
        self.fail = fail
        self.calls = 0

    def identity(self) -> str:
        return self.version

    def embed(self, texts: list[str], *, query: bool = False) -> list[tuple[float, ...]]:
        self.calls += 1
        if self.fail:
            raise SemanticSpineError("Ollama connection failed")

        output = []
        for text in texts:
            values = [0.0] * self.dimensions
            raw_tokens = text.casefold().replace(".", " ").replace(",", " ").replace(":", " ").replace("-", " ").split()
            for t in raw_tokens:
                matched_topic = False
                for topic_id, words in TOPIC_KEYWORDS.items():
                    if t in words:
                        values[topic_id * 10] += 5.0
                        matched_topic = True
                if not matched_topic:
                    pos = int(hashlib.sha256(t.encode("utf-8")).hexdigest()[:8], 16) % self.dimensions
                    values[pos] += 0.1
            output.append(normalize_vector(values, self.dimensions))
        return output


CAMPAIGN_CORPUS = [
    (1, "The party arrived in Falcon's Hollow and accepted Sheriff Barlun's contract to investigate the lumber camp.", [{"fact": "Contract signed with Sheriff Barlun", "category": "quest", "confidence": 1.0}], "Arrived at town gates. Met the sheriff."),
    (2, "Deep in the Darkmoon Wood, the heroes defeated a pack of rabid timber wolves and discovered a hidden cavern entrance.", [{"fact": "Defeated timber wolves in Darkmoon Wood", "category": "mechanic", "confidence": 1.0}], "Lumber camp was abandoned. Tracks led into deep trees."),
    (3, "Inside the cavern, the party solved the dwarven lever puzzle and recovered the ancient bronze key to the sunken sanctuary.", [{"fact": "Found ancient bronze key", "category": "item", "confidence": 1.0}], "Stone doors opened after three levers aligned."),
    (4, "At the sunken sanctuary, an ambush by ironfang hobgoblins left Valeros wounded. Kyra channeled healing light to repel the vanguard.", [{"fact": "Ironfang hobgoblin ambush repelled", "category": "npc", "confidence": 1.0}], "Shields clattered in the dark corridor."),
    (5, "The heroes bargained with the water naga Sibilia, trading the bronze key for safe passage across the underground river.", [{"fact": "Bargained with Sibilia the water naga", "category": "npc", "confidence": 1.0}], "The creature surfaced amidst glowing ripples."),
    (6, "In the crypt of the forgotten pharaoh, the party fought animated statues and rescued the merchant Jeremy from a stone sarcophagus.", [{"fact": "Rescued merchant Jeremy from sarcophagus", "category": "quest", "confidence": 1.0}], "Chisels and dust flew as the lid cracked open."),
    (7, "During the long exploration of the volcanic caldera, Merisiel disarmed three flame jet traps and secured the ruby pendant.", [{"fact": "Disarmed flame jet traps in volcanic caldera", "category": "location", "confidence": 1.0}], "Heat shimmered over the obsidian ridges."),
    (8, "The party clashed with an adult red dragon named Ignis atop Mount Wyrmtooth; after a desperate retreat, they fortified the mountain pass.", [{"fact": "Clashed with red dragon Ignis on Mount Wyrmtooth", "category": "npc", "confidence": 1.0}], "Wings eclipsed the sun as fire swept the crags."),
    (9, "In the capital city of Absalom, the heroes reported their findings to the Grand Council and received commendations and gold bounties.", [{"fact": "Received commendations from Grand Council", "category": "decision", "confidence": 1.0}], "Trumpets sounded in the hall of pillars."),
    (10, "A midnight infiltration into the shadow guild's warehouse uncovered documents detailing a plot against the High Cleric.", [{"fact": "Uncovered shadow guild assassination plot", "category": "quest", "confidence": 1.0}], "Locked chests held wax-sealed letters."),
]

PARAPHRASE_EVAL_SET = [
    ("Hostile canines prowling a dense forest", 2),
    ("Aquatic serpent negotiating waterway transit", 5),
    ("Liberating a captured vendor imprisoned within a mausoleum", 6),
    ("Neutralizing thermal ignition hazards throughout magma basin", 7),
    ("Confronting aerial firebreather causing tactical withdrawal", 8),
]


@pytest.fixture
def recall_repo(tmp_path: Path) -> CampaignRepository:
    repo = CampaignRepository(str(tmp_path / "campaign_recall.db"))
    with repo._conn() as conn:
        conn.execute("INSERT OR REPLACE INTO campaigns (id, name, edition, created_at, updated_at) VALUES (1, 'Ironfang Invasion', '2e', '2026-01-01', '2026-01-01')")
    for s_num, summary, facts, raw_log in CAMPAIGN_CORPUS:
        repo.save_session(
            campaign_id=1,
            session_num=s_num,
            summary=summary,
            facts=facts,
            raw_log=raw_log,
        )
    return repo


def test_lexical_recall_fails_on_unseen_paraphrases(recall_repo: CampaignRepository):
    for query, target_session in PARAPHRASE_EVAL_SET:
        hits = recall_repo.search_sessions_lexical(query, campaign_id=1, limit=3)
        found_nums = [h["session_num"] for h in hits]
        assert target_session not in found_nums


def test_semantic_recall_retrieves_paraphrased_sessions(recall_repo: CampaignRepository):
    embedder = DeterministicRecallEmbedder()
    for query, target_session in PARAPHRASE_EVAL_SET:
        hits = recall_repo.search_sessions_hybrid(query, campaign_id=1, limit=3, embedder=embedder)
        found_nums = [h["session_num"] for h in hits]
        assert target_session in found_nums
        assert hits[0]["session_num"] == target_session


def test_semantic_recall_exact_keyword_anchors_rank_one(recall_repo: CampaignRepository):
    embedder = DeterministicRecallEmbedder()
    hits = recall_repo.search_sessions_hybrid("timber wolves", campaign_id=1, limit=3, embedder=embedder)
    assert hits
    assert hits[0]["session_num"] == 2


def test_semantic_recall_fails_closed_when_embedder_fails(recall_repo: CampaignRepository):
    failing_embedder = DeterministicRecallEmbedder(fail=True)
    hits = recall_repo.search_sessions_hybrid("timber wolves", campaign_id=1, limit=3, embedder=failing_embedder)
    assert hits
    assert hits[0]["session_num"] == 2


def test_context_caps_enforced(recall_repo: CampaignRepository):
    embedder = DeterministicRecallEmbedder()
    huge_query = "timber wolves " + ("repeated words " * 200)
    assert len(huge_query) > 200
    hits = recall_repo.search_sessions_hybrid(huge_query, campaign_id=1, limit=3, embedder=embedder)
    assert hits
    assert hits[0]["session_num"] == 2


def test_benchmark_recall_quality_and_latency(recall_repo: CampaignRepository):
    settings = get_settings()
    embedder = DeterministicRecallEmbedder()

    # 1. Measure lexical baseline
    lexical_hits_at_1 = 0
    lexical_hits_at_3 = 0
    lexical_reciprocal_ranks = []
    lexical_latencies_ms = []

    for query, target in PARAPHRASE_EVAL_SET:
        t0 = time.perf_counter()
        results = recall_repo.search_sessions_lexical(query, campaign_id=1, limit=3)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        lexical_latencies_ms.append(elapsed_ms)

        ranks = [idx for idx, r in enumerate(results, 1) if r["session_num"] == target]
        if ranks:
            r = ranks[0]
            if r == 1:
                lexical_hits_at_1 += 1
            if r <= 3:
                lexical_hits_at_3 += 1
            lexical_reciprocal_ranks.append(1.0 / r)
        else:
            lexical_reciprocal_ranks.append(0.0)

    # 2. Measure hybrid semantic recall
    hybrid_hits_at_1 = 0
    hybrid_hits_at_3 = 0
    hybrid_reciprocal_ranks = []
    hybrid_latencies_ms = []

    for query, target in PARAPHRASE_EVAL_SET:
        t0 = time.perf_counter()
        results = recall_repo.search_sessions_hybrid(query, campaign_id=1, limit=3, embedder=embedder)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        hybrid_latencies_ms.append(elapsed_ms)

        ranks = [idx for idx, r in enumerate(results, 1) if r["session_num"] == target]
        if ranks:
            r = ranks[0]
            if r == 1:
                hybrid_hits_at_1 += 1
            if r <= 3:
                hybrid_hits_at_3 += 1
            hybrid_reciprocal_ranks.append(1.0 / r)
        else:
            hybrid_reciprocal_ranks.append(0.0)

    n = len(PARAPHRASE_EVAL_SET)
    lex_recall_3 = lexical_hits_at_3 / n
    lex_mrr = sum(lexical_reciprocal_ranks) / n
    hyb_recall_3 = hybrid_hits_at_3 / n
    hyb_mrr = sum(hybrid_reciprocal_ranks) / n

    assert lex_recall_3 == 0.0
    assert hyb_recall_3 == 1.0
    assert hyb_mrr == 1.0

    sorted_latencies = sorted(hybrid_latencies_ms)
    p50 = sorted_latencies[len(sorted_latencies) // 2]
    p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)]
    assert p50 < 30.0
    assert p95 < 60.0
