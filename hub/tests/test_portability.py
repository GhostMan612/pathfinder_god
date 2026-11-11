# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Campaign and character .db portability (schema version 1).

These tests build a real campaign with encounters/events/breadcrumbs, export a
standalone SQLite file, import it into a new campaign, and assert that ids were
remapped rather than copied. Corrupt and version-mismatched files are rejected.
Synthetic names only.
"""
from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from app.db.portability import (
    PortabilityError,
    _remap_id_list,
    _remap_json,
    export_campaign_db,
    export_character_db,
    import_campaign_db,
    import_character_db,
)
from app.db.repository import CampaignRepository


def _seed_campaign(repo: CampaignRepository, name: str = "SAMPLE CAMPAIGN"):
    campaign = repo.create_campaign(name)
    town = repo.upsert_location(campaign.id, "SAMPLE TOWN", type_="settlement")
    cave = repo.upsert_location(
        campaign.id,
        "SAMPLE CAVE",
        type_="dungeon",
        parent_name="SAMPLE TOWN",
    )
    repo.set_current_location(campaign.id, cave)
    npc_id = repo.upsert_npc(
        campaign.id, "SAMPLE MERCHANT", disposition="friendly"
    )
    item_id = repo.upsert_item(
        campaign.id,
        "SAMPLE SWORD",
        type_="weapon",
        level=1,
        holder_name="SAMPLE MERCHANT",
    )
    quest_id = repo.upsert_quest(
        campaign.id,
        "SAMPLE QUEST",
        giver_name="SAMPLE MERCHANT",
        objectives=[{"description": "Find the sample", "completed": False}],
        rewards=[{"description": "A sample reward"}],
    )
    repo.upsert_party_member(
        campaign.id,
        "SAMPLE HERO",
        player_name="SAMPLE PLAYER",
        class_="Fighter",
        level=3,
        stats={"equipment": [{"name": "SAMPLE SWORD"}]},
    )
    hero_id = repo.upsert_combatant(
        campaign.id, "SAMPLE HERO", kind="hero", hp=30, max_hp=30
    )
    repo.append_event(
        campaign.id,
        "sample_event",
        summary="The sample happened.",
        location_id=town,
        data={"npc_id": npc_id, "combatant_id": hero_id},
    )
    repo.upsert_location_edge(
        campaign.id, town, cave, kind="trail", travel_ticks=2
    )
    repo.save_session(
        campaign.id,
        1,
        "The party found the sample.",
        [{"fact": "The sample exists.", "category": "event"}],
        "SAMPLE RAW LOG",
    )
    repo.add_session_note(campaign.id, 1, "SAMPLE PROMPT", "SAMPLE RESPONSE")
    repo.add_decision(
        campaign.id,
        session_num=1,
        decision="Open the sample door.",
        made_by="SAMPLE HERO",
    )
    encounter = repo.create_encounter(
        campaign.id,
        "door",
        status="active",
        summary="SAMPLE DOOR",
        state={
            "locked": False,
            "key": None,
            "barred": False,
            "dc": None,
            "npc_id": npc_id,
            "combatant_id": hero_id,
        },
        location_id=cave,
    )
    repo.append_event(
        campaign.id,
        "sample_encounter",
        summary="The door appeared.",
        location_id=cave,
        encounter_id=encounter.id,
        data={"encounter_id": encounter.id, "item_id": item_id},
    )
    return {
        "campaign": campaign,
        "town": town,
        "cave": cave,
        "npc": npc_id,
        "item": item_id,
        "quest": quest_id,
        "hero": hero_id,
        "encounter": encounter,
    }


def test_export_campaign_db_is_standalone_and_remaps_campaign_id(
    tmp_path: Path, monkeypatch
) -> None:
    repo = CampaignRepository(str(tmp_path / "campaign.db"))
    seeded = _seed_campaign(repo)
    payload = export_campaign_db(repo, seeded["campaign"].id)
    path = tmp_path / "campaign_export.db"
    path.write_bytes(payload)

    with closing(sqlite3.connect(path)) as conn:
        conn.row_factory = sqlite3.Row
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        meta = {
            r["key"]: r["value"]
            for r in conn.execute("SELECT key, value FROM meta").fetchall()
        }
        assert meta["schema_version"] == "1"
        assert meta["exported_from"] == "SAMPLE CAMPAIGN"
        assert conn.execute("SELECT COUNT(*) FROM campaigns").fetchone()[0] == 1
        assert conn.execute("SELECT id FROM campaigns").fetchone()[0] == 1
        assert (
            conn.execute("SELECT COUNT(*) FROM encounters").fetchone()[0] == 1
        )
        assert conn.execute("SELECT COUNT(*) FROM campaign_events").fetchone()[0] == 3
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM sessions_fts WHERE sessions_fts MATCH 'sample'"
            ).fetchone()[0]
            >= 1
        )


def test_campaign_db_round_trip_remaps_all_row_ids(tmp_path: Path) -> None:
    repo = CampaignRepository(str(tmp_path / "campaign.db"))
    seeded = _seed_campaign(repo)
    export_path = tmp_path / "campaign_export.db"
    export_path.write_bytes(export_campaign_db(repo, seeded["campaign"].id))

    result = import_campaign_db(repo, str(export_path), replace_existing=False)
    new_id = result["campaign_id"]
    assert new_id != seeded["campaign"].id
    assert result["name"] == "SAMPLE CAMPAIGN"

    state = repo.get_solo_state(new_id)
    assert state is not None
    assert state.current_location_id is not None
    assert state.current_location_id != seeded["cave"]
    assert repo.get_location(new_id, state.current_location_id).name == "SAMPLE CAVE"

    locations = {loc.name: loc.id for loc in repo.get_locations(new_id)}
    assert locations["SAMPLE CAVE"] != seeded["cave"]
    assert repo.get_location(new_id, locations["SAMPLE CAVE"]).parent_id == locations[
        "SAMPLE TOWN"
    ]

    npcs = repo.get_npcs(new_id)
    assert len(npcs) == 1
    assert npcs[0].name == "SAMPLE MERCHANT"
    assert npcs[0].id != seeded["npc"]

    items = repo.get_items(new_id)
    assert len(items) == 1
    assert items[0]["name"] == "SAMPLE SWORD"
    assert items[0]["holder_id"] == npcs[0].id
    assert items[0]["id"] != seeded["item"]

    encounters = repo.list_encounters(new_id)
    assert len(encounters) == 1
    assert encounters[0].id != seeded["encounter"]
    assert encounters[0].state["npc_id"] == npcs[0].id
    assert encounters[0].state["combatant_id"] is not None
    assert encounters[0].state["combatant_id"] != seeded["hero"]

    events = repo.list_events(new_id)
    assert len(events) == 3
    by_kind = {event.kind: event for event in events}
    assert by_kind["sample_event"].location_id == locations["SAMPLE TOWN"]
    assert by_kind["sample_encounter"].encounter_id == encounters[0].id
    assert by_kind["sample_encounter"].data["encounter_id"] == encounters[0].id
    assert by_kind["sample_encounter"].data["item_id"] == items[0]["id"]

    edges = repo.get_location_edges(new_id)
    assert len(edges) == 1
    assert edges[0].from_location_id == locations["SAMPLE TOWN"]
    assert edges[0].to_location_id == locations["SAMPLE CAVE"]
    assert edges[0].travel_ticks == 2

    assert len(repo.get_party(new_id)) == 1
    assert repo.get_party(new_id)[0]["name"] == "SAMPLE HERO"
    assert len(repo.get_combatants(new_id)) == 1
    assert repo.get_combatants(new_id)[0].name == "SAMPLE HERO"
    assert len(repo.get_session_notes(new_id)) == 1
    with repo._conn() as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM player_decisions WHERE campaign_id = ?",
                (new_id,),
            ).fetchone()[0]
            == 1
        )


def test_campaign_db_import_replace_existing(tmp_path: Path) -> None:
    repo = CampaignRepository(str(tmp_path / "campaign.db"))
    seeded = _seed_campaign(repo)
    export_path = tmp_path / "campaign_export.db"
    export_path.write_bytes(export_campaign_db(repo, seeded["campaign"].id))
    target = repo.create_campaign("REPLACE ME")
    repo.upsert_location(target.id, "OLD LOCATION", type_="other")

    result = import_campaign_db(
        repo, str(export_path), campaign_id=target.id, replace_existing=True
    )

    assert result["campaign_id"] == target.id
    assert result["replaced"] is True
    names = {loc.name for loc in repo.get_locations(target.id)}
    assert names == {"SAMPLE TOWN", "SAMPLE CAVE"}


def test_campaign_db_import_rejects_version_mismatch(tmp_path: Path) -> None:
    repo = CampaignRepository(str(tmp_path / "campaign.db"))
    seeded = _seed_campaign(repo)
    export_path = tmp_path / "campaign_export.db"
    export_path.write_bytes(export_campaign_db(repo, seeded["campaign"].id))
    with closing(sqlite3.connect(export_path)) as conn:
        conn.execute("UPDATE meta SET value = '999' WHERE key = 'schema_version'")
        conn.commit()

    with pytest.raises(PortabilityError, match="schema version"):
        import_campaign_db(repo, str(export_path), replace_existing=False)


def test_campaign_db_import_rejects_corrupt_file(tmp_path: Path) -> None:
    repo = CampaignRepository(str(tmp_path / "campaign.db"))
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"this is not sqlite")

    with pytest.raises(PortabilityError):
        import_campaign_db(repo, str(bad), replace_existing=False)


def test_campaign_db_import_rejects_meta_less_file(tmp_path: Path) -> None:
    repo = CampaignRepository(str(tmp_path / "campaign.db"))
    seeded = _seed_campaign(repo)
    export_path = tmp_path / "campaign_export.db"
    export_path.write_bytes(export_campaign_db(repo, seeded["campaign"].id))
    with closing(sqlite3.connect(export_path)) as conn:
        conn.execute("DROP TABLE meta")
        conn.commit()

    # A missing meta table must be a clean PortabilityError, not a raw
    # sqlite3.OperationalError from the SELECT.
    with pytest.raises(PortabilityError, match="meta"):
        import_campaign_db(repo, str(export_path), replace_existing=False)


def test_character_export_matches_name_as_whole_word(tmp_path: Path) -> None:
    repo = CampaignRepository(str(tmp_path / "campaign.db"))
    campaign = repo.create_campaign("SAMPLE CAMPAIGN")
    repo.upsert_party_member(campaign.id, "Al")
    repo.upsert_item(
        campaign.id, "SAMPLE ALWAYS BLADE", notes="also carried always"
    )
    repo.upsert_item(
        campaign.id, "SAMPLE AL BLADE", notes="claimed by Al after the fight"
    )
    repo.insert_session_notes(
        campaign.id,
        [
            (1, "gm", "Al was here"),
            (1, "gm", "also ran the whole way"),
        ],
    )

    payload = export_character_db(repo, campaign.id, "Al")
    character_path = tmp_path / "al.db"
    character_path.write_bytes(payload)

    with closing(sqlite3.connect(character_path)) as conn:
        item_names = [
            row[0] for row in conn.execute("SELECT name FROM items").fetchall()
        ]
        note_contents = [
            row[0]
            for row in conn.execute("SELECT content FROM session_notes").fetchall()
        ]
    # "Al" as a whole word matches; "also" / "always" must not.
    assert item_names == ["SAMPLE AL BLADE"]
    assert note_contents == ["Al was here"]


def test_remap_json_nulls_unmapped_refs() -> None:
    maps = {"npcs": {5: 9}, "combatants": {1: 10, 2: 20}}
    assert _remap_json({"npc_id": 5}, maps) == {"npc_id": 9}
    assert _remap_json({"npc_id": 99}, maps) == {"npc_id": None}
    assert _remap_json({"npc_id": "5"}, maps) == {"npc_id": "9"}
    assert _remap_json({"npc_id": "99"}, maps) == {"npc_id": None}
    assert _remap_json({"combatant_ids": [1, 2, 99]}, maps) == {
        "combatant_ids": [10, 20]
    }
    assert _remap_json({"note": "nothing to remap"}, maps) == {
        "note": "nothing to remap"
    }
    assert _remap_id_list("[1, 2, 99]", maps["combatants"]) == "[10, 20]"
    assert _remap_id_list(None, maps["combatants"]) is None


def test_character_db_round_trip_and_conflict_rejection(tmp_path: Path) -> None:
    repo = CampaignRepository(str(tmp_path / "campaign.db"))
    seeded = _seed_campaign(repo)
    payload = export_character_db(repo, seeded["campaign"].id, "SAMPLE HERO")
    character_path = tmp_path / "hero.db"
    character_path.write_bytes(payload)

    with closing(sqlite3.connect(character_path)) as conn:
        assert conn.execute("SELECT COUNT(*) FROM party_members").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM combatants").fetchone()[0] == 1
        meta = {
            r[0]: r[1] for r in conn.execute("SELECT key, value FROM meta")
        }
        assert meta["exported_from"] == "SAMPLE HERO"

    target = repo.create_campaign("TARGET CAMPAIGN")
    result = import_character_db(repo, target.id, str(character_path))
    assert result["name"] == "SAMPLE HERO"
    assert result["party_member_id"] is not None
    assert result["combatant_id"] is not None
    assert repo.get_party(target.id)[0]["name"] == "SAMPLE HERO"
    heroes = [c for c in repo.get_combatants(target.id) if c.kind == "hero"]
    assert len(heroes) == 1

    with pytest.raises(PortabilityError, match="already exists"):
        import_character_db(repo, target.id, str(character_path))


@pytest.mark.asyncio
async def test_json_campaign_export_import_round_trip(authenticated_client) -> None:
    from app.api.deps import get_repo

    get_repo.cache_clear()
    repo = get_repo()
    seeded = _seed_campaign(repo, "JSON CAMPAIGN")

    export_response = authenticated_client.get(
        f"/campaign/export?campaign_id={seeded['campaign'].id}"
    )
    assert export_response.status_code == 200, export_response.text
    exported = export_response.json()
    assert exported["campaign"]["name"] == "JSON CAMPAIGN"
    assert len(exported["party"]) == 1
    assert len(exported["items"]) == 1
    assert len(exported["quests"]) == 1
    assert len(exported["decisions"]) == 1

    target = repo.create_campaign("JSON TARGET")
    import_response = authenticated_client.post(
        f"/campaign/import?campaign_id={target.id}&replace_existing=true",
        json=exported,
    )
    assert import_response.status_code == 200, import_response.text
    assert repo.get_party(target.id)[0]["name"] == "SAMPLE HERO"
    assert len(repo.get_items(target.id)) == 1
    assert len(repo.get_locations(target.id)) == 2
    with repo._conn() as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM quests WHERE campaign_id = ?",
                (target.id,),
            ).fetchone()[0]
            == 1
        )


@pytest.mark.asyncio
async def test_campaign_db_routes(authenticated_client, tmp_path: Path) -> None:
    from app.api.deps import get_repo

    get_repo.cache_clear()
    repo = get_repo()
    seeded = _seed_campaign(repo, "ROUTE CAMPAIGN")

    export_response = authenticated_client.get(
        f"/campaign/export-db?campaign_id={seeded['campaign'].id}"
    )
    assert export_response.status_code == 200, export_response.text
    assert export_response.headers["content-type"].startswith(
        "application/x-sqlite3"
    )
    assert export_response.content.startswith(b"SQLite format 3")

    import_response = authenticated_client.post(
        "/campaign/import-db",
        params={"replace_existing": "false"},
        files={
            "file": (
                "campaign.db",
                export_response.content,
                "application/x-sqlite3",
            )
        },
    )
    assert import_response.status_code == 200, import_response.text
    body = import_response.json()
    assert body["campaign_id"] != seeded["campaign"].id
    state = repo.get_campaign_state(body["campaign_id"])
    assert state["party"][0]["name"] == "SAMPLE HERO"

    char_response = authenticated_client.get(
        f"/campaign/{seeded['campaign'].id}/characters/SAMPLE HERO/export-db"
    )
    assert char_response.status_code == 200, char_response.text
    assert char_response.content.startswith(b"SQLite format 3")

    target = repo.create_campaign("CHARACTER TARGET")
    char_import = authenticated_client.post(
        f"/campaign/{target.id}/characters/import-db",
        files={
            "file": (
                "hero.db",
                char_response.content,
                "application/x-sqlite3",
            )
        },
    )
    assert char_import.status_code == 200, char_import.text
    assert char_import.json()["name"] == "SAMPLE HERO"
