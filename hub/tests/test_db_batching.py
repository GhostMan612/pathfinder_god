# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""O1/O2/O3 regression tests: connection batching, snapshots, FTS hardening.

These are hermetic: every test builds a throwaway SQLite campaign DB under
tmp_path and counts connections by monkeypatching sqlite3.connect, so nothing
touches the real data/campaign.db or a live Ollama.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from app.db.repository import CampaignRepository


@pytest.fixture
def repo(tmp_path: Path) -> CampaignRepository:
    return CampaignRepository(str(tmp_path / "campaign.db"))


@pytest.fixture
def count_connections(monkeypatch):
    """Count sqlite3.connect calls made inside the block."""
    real = sqlite3.connect
    counter = {"n": 0}

    def counting(*args, **kwargs):
        counter["n"] += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", counting)
    return counter


# ── Phase 1: party + sessions batching ─────────────────────────────


def test_import_batches_use_one_connection_each(repo, count_connections):
    """A 30-member party and a 30-session history cost 1 connection each."""
    party = [
        {"name": f"Hero {i}", "level": 1 + (i % 20), "class": "fighter"}
        for i in range(30)
    ]
    sessions = [
        {"session_num": i + 1, "summary": f"Session {i+1} summary", "facts": [], "raw_log": ""}
        for i in range(30)
    ]

    count_connections["n"] = 0
    written_party = repo.upsert_party_batch(1, party)
    party_conns = count_connections["n"]

    count_connections["n"] = 0
    written_sessions = repo.insert_sessions_batch(1, sessions)
    session_conns = count_connections["n"]

    assert written_party == 30
    assert written_sessions == 30
    assert party_conns == 1, f"party batch opened {party_conns} connections, expected 1"
    assert session_conns == 1, f"session batch opened {session_conns} connections, expected 1"


def test_imported_sessions_are_immediately_searchable(repo):
    """sessions_fts triggers must fire inside the batch transaction."""
    repo.insert_sessions_batch(
        1,
        [
            {"session_num": 1, "summary": "The party infiltrated the goblin camp.",
             "facts": [{"fact": "camp"}], "raw_log": ""},
            {"session_num": 2, "summary": "They negotiated with the dragon.",
             "facts": [], "raw_log": ""},
        ],
    )
    hits = repo.search_sessions("infiltrated goblin camp", campaign_id=1)
    assert hits, "batch-imported session was not indexed into sessions_fts"
    assert hits[0]["session_num"] == 1
    # search_sessions already decodes facts_json into a list.
    assert hits[0]["facts_json"] == [{"fact": "camp"}]


def test_session_batch_upsert_is_idempotent(repo):
    """Re-importing the same session updates in place, does not duplicate."""
    row = {"session_num": 1, "summary": "first", "facts": [], "raw_log": ""}
    repo.insert_sessions_batch(1, [row])
    repo.insert_sessions_batch(1, [{**row, "summary": "second"}])

    with repo._conn() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE session_num = 1"
        ).fetchone()[0]
        summary = conn.execute(
            "SELECT summary FROM sessions WHERE session_num = 1"
        ).fetchone()[0]
    assert count == 1
    assert summary == "second"


def test_party_batch_upsert_conflict_updates(repo):
    repo.upsert_party_batch(1, [{"name": "Sahla", "level": 3}])
    repo.upsert_party_batch(1, [{"name": "Sahla", "level": 5}])

    with repo._conn() as conn:
        rows = conn.execute(
            "SELECT COUNT(*) FROM party_members WHERE name = 'Sahla'"
        ).fetchone()[0]
        level = conn.execute(
            "SELECT level FROM party_members WHERE name = 'Sahla'"
        ).fetchone()[0]
    assert rows == 1
    assert level == 5


# ── Phase 2: single-connection snapshot ───────────────────────────


def test_snapshot_matches_individual_getters(repo, count_connections):
    """get_campaign_snapshot must agree with the getters, on one connection."""
    repo.upsert_party_batch(1, [{"name": "Sahla", "level": 4}])
    repo.upsert_entities_batch(
        1,
        npcs=[{"name": "Goblin"}, {"name": "Ogre"}],
        locations=[{"name": "Vault"}],
        items=[{"name": "Sword"}],
        quests=[{"name": "Find the amulet"}, {"name": "Done already", "status": "completed"}],
    )
    repo.update_campaign_summary(1, "The party broke into the vault.")
    repo.set_combat_json(1, json.dumps({"round": 2}))

    count_connections["n"] = 0
    snap = repo.get_campaign_snapshot(1)
    used = count_connections["n"]

    assert used == 1, f"snapshot opened {used} connections, expected exactly 1"

    assert snap["campaign_id"] == 1
    assert snap["chronicle"] == repo.get_campaign_summary(1)
    assert snap["combat_json"] == repo.get_combat_json(1)
    assert [p["name"] for p in snap["party"]] == [
        p["name"] for p in repo.get_party(1)
    ]
    # The snapshot returns plain dicts (like get_party); the list getters
    # return dataclasses, so compare the names either way.
    assert [n["name"] for n in snap["npcs"]] == [n.name for n in repo.get_npcs(1)]
    assert [loc["name"] for loc in snap["locations"]] == [
        loc.name for loc in repo.get_locations(1)
    ]
    # There is no get_items() getter, so compare items against the table.
    with repo._conn() as conn:
        db_items = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM items WHERE campaign_id = 1 ORDER BY name"
            ).fetchall()
        ]
    assert [i["name"] for i in snap["items"]] == db_items
    # Only ACTIVE quests, matching get_active_quests.
    assert [q["name"] for q in snap["quests"]] == [
        q.name for q in repo.get_active_quests(1)
    ]


def test_snapshot_resolves_active_campaign_when_id_is_none(repo):
    repo.update_campaign_summary(1, "older campaign")
    repo.update_campaign_summary(2, "newest campaign")

    snap = repo.get_campaign_snapshot(None)
    assert snap["campaign_id"] == 2
    assert snap["chronicle"] == "newest campaign"


def test_snapshot_pushes_limits_into_sql(repo):
    """A LIMIT must bound rows, not just trim in Python."""
    repo.upsert_entities_batch(
        1, npcs=[{"name": f"NPC {i:02d}"} for i in range(20)]
    )
    snap = repo.get_campaign_snapshot(1, npc_limit=5)
    assert len(snap["npcs"]) == 5


def test_snapshot_handles_missing_campaign(repo):
    snap = repo.get_campaign_snapshot(4242)
    assert snap["campaign_id"] == 4242
    assert snap["chronicle"] == ""
    assert snap["combat_json"] == ""
    assert snap["npcs"] == []


# ── Phase 3: search_sessions FTS5 hardening ──────────────────────


@pytest.mark.parametrize(
    "hostile",
    [
        'unclosed "quote AND * OR ( )',
        '"',
        "AND",
        "*",
        "NEAR/2",
        "^foo",
        "col:val",
        "a AND (b OR",
        "-",
    ],
)
def test_search_sessions_survives_hostile_fts_syntax(repo, hostile):
    """Hostile MATCH input must return [] rather than raise OperationalError."""
    repo.insert_sessions_batch(
        1, [{"session_num": 1, "summary": "A normal summary.", "facts": [], "raw_log": ""}]
    )
    result = repo.search_sessions(hostile, campaign_id=1)
    assert isinstance(result, list)


def test_search_sessions_returns_empty_for_stopword_only(repo):
    repo.insert_sessions_batch(
        1, [{"session_num": 1, "summary": "A normal summary.", "facts": [], "raw_log": ""}]
    )
    assert repo.search_sessions("what is this about", campaign_id=1) == []


def test_search_sessions_still_finds_real_content(repo):
    repo.insert_sessions_batch(
        1,
        [{"session_num": 1, "summary": "The party grappled the ogre.",
          "facts": [], "raw_log": ""}],
    )
    hits = repo.search_sessions("what are the rules for grappling an ogre", campaign_id=1)
    assert hits
    assert hits[0]["session_num"] == 1