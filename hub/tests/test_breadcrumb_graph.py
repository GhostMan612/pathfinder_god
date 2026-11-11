# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Breadcrumb graph, world clock, and generic encounter lifecycle tests.

Synthetic data only. The graph is exercised directly through the repository
and through the authenticated campaign routes; no model is contacted.
"""
from __future__ import annotations

from pathlib import Path

from app.agents.solo_loop import SoloLoop
from app.db.repository import CampaignRepository


def _repo(tmp_path: Path) -> CampaignRepository:
    return CampaignRepository(str(tmp_path / "campaign.db"))


def _locations(repo: CampaignRepository, campaign_id: int):
    town = repo.upsert_location(
        campaign_id, "SAMPLE TOWN", type_="settlement"
    )
    cave = repo.upsert_location(
        campaign_id, "SAMPLE CAVE", type_="dungeon"
    )
    return town, cave


def test_location_edges_upsert_and_bidirectional(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    town, cave = _locations(repo, campaign.id)

    edge = repo.upsert_location_edge(
        campaign.id,
        town,
        cave,
        kind="road",
        label="Old Road",
        travel_ticks=3,
        bidirectional=True,
    )
    assert edge.from_location_id == town
    assert edge.to_location_id == cave
    assert edge.travel_ticks == 3

    edges = repo.get_location_edges(campaign.id)
    assert len(edges) == 2
    reverse = next(e for e in edges if e.from_location_id == cave)
    assert reverse.to_location_id == town
    assert reverse.travel_ticks == 3

    # Re-upserting the same directed pair updates in place; it never adds a
    # duplicate edge or silently rewrites the reverse direction.
    updated = repo.upsert_location_edge(
        campaign.id, town, cave, kind="road", travel_ticks=5
    )
    assert updated.id == edge.id
    assert updated.travel_ticks == 5
    assert len(repo.get_location_edges(campaign.id)) == 2
    reverse = next(
        e for e in repo.get_location_edges(campaign.id)
        if e.from_location_id == cave
    )
    assert reverse.travel_ticks == 3


def test_move_advances_clock_and_records_lazy_trail(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    town, cave = _locations(repo, campaign.id)
    repo.set_current_location(campaign.id, town)

    movement = repo.move_to_location(campaign.id, cave)
    assert movement["location"] == "SAMPLE CAVE"
    assert movement["from_location_id"] == town
    assert movement["tick"] == 1
    assert movement["edge"] is not None
    assert movement["edge"].kind == "trail"
    assert movement["event"].kind == "move"
    assert movement["event"].tick == 1
    assert movement["event"].location_id == cave
    assert movement["event"].data["from_location_id"] == town
    assert movement["event"].data["to_location_id"] == cave

    state = repo.get_solo_state(campaign.id)
    assert state is not None
    assert state.current_location_id == cave
    assert state.world_tick == 1

    # The discovered route is usable in both directions and is not duplicated.
    edges = repo.get_location_edges(campaign.id)
    assert {(e.from_location_id, e.to_location_id) for e in edges} == {
        (town, cave),
        (cave, town),
    }
    back = repo.move_to_location(campaign.id, town)
    assert back["tick"] == 2
    assert len(repo.get_location_edges(campaign.id)) == 2

    trail = repo.list_events(campaign.id, kind="move")
    assert [e.tick for e in trail] == [1, 2]
    assert [e.data["to_location_id"] for e in trail] == [cave, town]


def test_lazy_trail_does_not_overwrite_an_explicit_reverse_edge(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    town, cave = _locations(repo, campaign.id)
    repo.set_current_location(campaign.id, town)
    repo.upsert_location_edge(
        campaign.id, cave, town, kind="road", label="RETURN ROAD", travel_ticks=3
    )

    repo.move_to_location(campaign.id, cave)

    edges = repo.get_location_edges(campaign.id)
    forward = next(e for e in edges if e.from_location_id == town)
    reverse = next(e for e in edges if e.from_location_id == cave)
    assert forward.kind == "trail"
    assert reverse.kind == "road"
    assert reverse.label == "RETURN ROAD"
    assert reverse.travel_ticks == 3


def test_explicit_edge_travel_ticks_advance_the_clock(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    town, cave = _locations(repo, campaign.id)
    repo.set_current_location(campaign.id, town)
    repo.upsert_location_edge(
        campaign.id, town, cave, kind="road", travel_ticks=4
    )

    movement = repo.move_to_location(campaign.id, cave)
    assert movement["tick"] == 4
    assert movement["event"].tick == 4
    assert movement["event"].data["travel_ticks"] == 4
    assert repo.get_solo_state(campaign.id).world_tick == 4


def test_legacy_db_gains_world_tick_and_encounter_location(
    tmp_path: Path,
) -> None:
    import sqlite3

    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE campaigns (id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, edition TEXT NOT NULL DEFAULT '2e',
            summary TEXT, combat_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE solo_state (campaign_id INTEGER PRIMARY KEY,
            phase TEXT NOT NULL DEFAULT 'exploration',
            round_num INTEGER NOT NULL DEFAULT 1,
            current_location_id INTEGER, active_combatant_id INTEGER,
            turn_order_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')));
        CREATE TABLE encounters (id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL, kind TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            summary TEXT NOT NULL DEFAULT '',
            state_json TEXT NOT NULL DEFAULT '{}', seed INTEGER,
            resolved_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')));
        INSERT INTO campaigns (id, name) VALUES (1, 'SAMPLE CAMPAIGN');
        INSERT INTO solo_state (campaign_id) VALUES (1);
        INSERT INTO encounters (campaign_id, kind, status)
            VALUES (1, 'door', 'pending');
        """
    )
    conn.commit()
    conn.close()

    repo = CampaignRepository(str(db_path))
    state = repo.get_solo_state(1)
    assert state is not None
    assert state.world_tick == 0
    assert state.next_turn_num == 1
    encounter = repo.get_encounter(1, 1)
    assert encounter is not None
    assert encounter.location_id is None
    assert encounter.kind == "door"
    # The migration ran, so the new columns are writable.
    updated = repo.transition_encounter(1, 1, "active")
    assert updated.status == "active"


def test_encounter_create_and_transition_log_location_events(
    tmp_path: Path,
) -> None:
    repo = _repo(tmp_path)
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    town, _cave = _locations(repo, campaign.id)
    repo.set_current_location(campaign.id, town)

    encounter = repo.create_encounter(
        campaign.id, "door", summary="SAMPLE DOOR", status="pending"
    )
    assert encounter.location_id == town

    created = repo.list_events(campaign.id, encounter_id=encounter.id)
    assert [e.kind for e in created] == ["encounter_created"]
    assert created[0].location_id == town
    assert created[0].data == {"kind": "door", "status": "pending"}

    active = repo.transition_encounter(
        campaign.id, encounter.id, "active", summary="SAMPLE DOOR OPENED"
    )
    assert active.status == "active"
    assert active.location_id == town

    resolved = repo.transition_encounter(
        campaign.id, encounter.id, "resolved", summary="SAMPLE DOOR CLEARED"
    )
    assert resolved.status == "resolved"
    assert resolved.resolved_at is not None

    events = repo.list_events(campaign.id, encounter_id=encounter.id)
    assert [e.kind for e in events] == [
        "encounter_created",
        "encounter_transition",
        "encounter_transition",
    ]
    assert [e.data.get("to") for e in events] == [None, "active", "resolved"]
    assert all(e.location_id == town for e in events)


def test_solo_loop_move_uses_the_breadcrumb_graph(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    town, cave = _locations(repo, campaign.id)
    repo.set_current_location(campaign.id, town)
    loop = SoloLoop(repo)

    moved = loop._resolve_move(
        campaign.id,
        "I travel to the SAMPLE CAVE",
        repo.get_locations(campaign.id),
        repo.ensure_solo_state(campaign.id),
    )
    assert moved == "SAMPLE CAVE"
    state = repo.get_solo_state(campaign.id)
    assert state.current_location_id == cave
    assert state.world_tick == 1
    assert repo.list_events(campaign.id, kind="move")[0].location_id == cave


def test_breadcrumb_and_encounter_api(
    authenticated_client, rules_db_dir: Path
) -> None:
    from app.api.deps import get_repo

    get_repo.cache_clear()
    repo = CampaignRepository(str(rules_db_dir / "campaign.db"))
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    cid = campaign.id
    town, cave = _locations(repo, cid)
    repo.set_current_location(cid, town)

    graph = authenticated_client.get(f"/campaign/{cid}/graph")
    assert graph.status_code == 200, graph.text
    body = graph.json()
    assert body["current_location_id"] == town
    assert body["world_tick"] == 0
    assert {node["name"] for node in body["nodes"]} == {
        "SAMPLE TOWN",
        "SAMPLE CAVE",
    }
    assert body["edges"] == []

    edge = authenticated_client.post(
        f"/campaign/{cid}/graph/edges",
        json={
            "from_location_id": town,
            "to_location_id": cave,
            "kind": "road",
            "label": "SAMPLE ROAD",
            "travel_ticks": 2,
            "bidirectional": True,
        },
    )
    assert edge.status_code == 200, edge.text
    assert edge.json()["travel_ticks"] == 2

    moved = authenticated_client.post(
        f"/campaign/{cid}/move", json={"location_id": cave}
    )
    assert moved.status_code == 200, moved.text
    moved_body = moved.json()
    assert moved_body["tick"] == 2
    assert moved_body["location"] == "SAMPLE CAVE"
    assert moved_body["edge"]["kind"] == "road"

    traits = authenticated_client.get(f"/campaign/{cid}/events")
    assert traits.status_code == 200, traits.text
    assert [e["kind"] for e in traits.json()["events"]] == ["move"]

    created = authenticated_client.post(
        f"/campaign/{cid}/encounters",
        json={
            "kind": "loot",
            "status": "active",
            "summary": "SAMPLE CACHE",
        },
    )
    assert created.status_code == 200, created.text
    encounter = created.json()
    assert encounter["kind"] == "loot"
    assert encounter["status"] == "active"
    assert encounter["location_id"] == cave

    conflict = authenticated_client.post(
        f"/campaign/{cid}/encounters",
        json={"kind": "trap", "status": "active"},
    )
    assert conflict.status_code == 409, conflict.text

    resolved = authenticated_client.post(
        f"/campaign/{cid}/encounters/{encounter['id']}/transition",
        json={"status": "resolved", "summary": "SAMPLE CACHE OPENED"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "resolved"

    terminal = authenticated_client.post(
        f"/campaign/{cid}/encounters/{encounter['id']}/transition",
        json={"status": "active"},
    )
    assert terminal.status_code == 400, terminal.text

    events = authenticated_client.get(f"/campaign/{cid}/events").json()
    assert [e["kind"] for e in events["events"]] == [
        "move",
        "encounter_created",
        "encounter_transition",
    ]
    assert events["events"][1]["encounter_id"] == encounter["id"]
    assert events["world_tick"] == 2
