# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import main
from app.api.deps import get_repo
from app.db.repository import CampaignRepository, RevisionConflictError


@pytest.fixture
def repo(tmp_path):
    return CampaignRepository(str(tmp_path / "campaign.db"))


@pytest.fixture
def authed_client(repo):
    main.app.dependency_overrides[get_repo] = lambda: repo
    client = TestClient(main.app)
    client.headers["X-API-Key"] = "pfg_test_key_12345"
    yield client
    main.app.dependency_overrides.clear()


@pytest.fixture
def unauthed_client(repo):
    main.app.dependency_overrides[get_repo] = lambda: repo
    client = TestClient(main.app)
    yield client
    main.app.dependency_overrides.clear()


def test_repo_sync_initial(repo):
    res = repo.sync_party_member(
        campaign_id=1,
        uuid="uuid-hero-1",
        name="Valeros",
        player_name="Player 1",
        class_="Fighter",
        level=1,
        ancestry="Human",
        background="Warrior",
        stats={"hp": 20, "ac": 18},
        expected_revision=None,
        idempotency_key="idemp-1",
    )
    assert res["uuid"] == "uuid-hero-1"
    assert res["name"] == "Valeros"
    assert res["revision"] == 1
    assert res["status"] == "synced"

    party = repo.get_party(1)
    assert len(party) == 1
    assert party[0]["uuid"] == "uuid-hero-1"
    assert party[0]["revision"] == 1


def test_repo_sync_update_revision_increment(repo):
    res1 = repo.sync_party_member(
        campaign_id=1,
        uuid="uuid-hero-1",
        name="Valeros",
        player_name="Player 1",
        class_="Fighter",
        level=1,
        ancestry="Human",
        background="Warrior",
        stats={"hp": 20, "ac": 18},
        expected_revision=None,
        idempotency_key="idemp-1",
    )
    assert res1["revision"] == 1

    res2 = repo.sync_party_member(
        campaign_id=1,
        uuid="uuid-hero-1",
        name="Valeros",
        player_name="Player 1",
        class_="Fighter",
        level=2,
        ancestry="Human",
        background="Warrior",
        stats={"hp": 30, "ac": 19},
        expected_revision=1,
        idempotency_key="idemp-2",
    )
    assert res2["revision"] == 2
    assert res2["status"] == "synced"

    party = repo.get_party(1)
    assert len(party) == 1
    assert party[0]["revision"] == 2
    assert party[0]["level"] == 2


def test_repo_sync_idempotent_replay(repo):
    res1 = repo.sync_party_member(
        campaign_id=1,
        uuid="uuid-hero-1",
        name="Valeros",
        level=1,
        expected_revision=None,
        idempotency_key="idemp-same",
    )
    assert res1["revision"] == 1

    res2 = repo.sync_party_member(
        campaign_id=1,
        uuid="uuid-hero-1",
        name="Valeros",
        level=1,
        expected_revision=None,
        idempotency_key="idemp-same",
    )
    assert res2["revision"] == 1
    assert res2["id"] == res1["id"]


def test_repo_sync_conflict_detection(repo):
    repo.sync_party_member(
        campaign_id=1,
        uuid="uuid-hero-1",
        name="Valeros",
        level=1,
        expected_revision=None,
        idempotency_key="idemp-1",
    )

    with pytest.raises(RevisionConflictError) as exc_info:
        repo.sync_party_member(
            campaign_id=1,
            uuid="uuid-hero-1",
            name="Valeros",
            level=2,
            expected_revision=99,
            idempotency_key="idemp-conflict",
        )
    assert exc_info.value.current_revision == 1
    assert exc_info.value.expected_revision == 99
    assert exc_info.value.server_character is not None
    assert exc_info.value.server_character["name"] == "Valeros"


def test_repo_sync_campaign_isolation(repo):
    res1 = repo.sync_party_member(
        campaign_id=1,
        uuid="uuid-hero-shared",
        name="SharedHero",
        level=1,
        expected_revision=None,
        idempotency_key="idemp-c1",
    )
    res2 = repo.sync_party_member(
        campaign_id=2,
        uuid="uuid-hero-shared",
        name="SharedHero",
        level=3,
        expected_revision=None,
        idempotency_key="idemp-c2",
    )
    assert res1["id"] != res2["id"]
    assert res1["revision"] == 1
    assert res2["revision"] == 1

    party1 = repo.get_party(1)
    party2 = repo.get_party(2)
    assert len(party1) == 1
    assert party1[0]["level"] == 1
    assert len(party2) == 1
    assert party2[0]["level"] == 3


def test_api_sync_endpoint(authed_client):
    payload = {
        "uuid": "uuid-hero-api",
        "name": "Seoni",
        "player_name": "Player 2",
        "class": "Sorcerer",
        "level": 1,
        "ancestry": "Human",
        "background": "Scholar",
        "stats": {"hp": 14, "ac": 15},
        "expected_revision": None,
        "idempotency_key": "idemp-api-1",
    }
    r = authed_client.post("/campaign/1/party/sync", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["uuid"] == "uuid-hero-api"
    assert data["revision"] == 1
    assert data["status"] == "synced"

    payload["expected_revision"] = 1
    payload["level"] = 2
    payload["idempotency_key"] = "idemp-api-2"
    r2 = authed_client.post("/campaign/1/party/sync", json=payload)
    assert r2.status_code == 200
    data2 = r2.json()
    assert data2["revision"] == 2

    payload["expected_revision"] = 1
    payload["idempotency_key"] = "idemp-api-3"
    r3 = authed_client.post("/campaign/1/party/sync", json=payload)
    assert r3.status_code == 409
    err = r3.json()["detail"]
    assert err["error"] == "conflict"
    assert err["current_revision"] == 2
    assert err["expected_revision"] == 1
    assert err["server_character"]["name"] == "Seoni"

    list_r = authed_client.get("/campaign/1/party")
    assert list_r.status_code == 200
    party = list_r.json()
    assert len(party) == 1
    assert party[0]["uuid"] == "uuid-hero-api"
    assert party[0]["revision"] == 2


def test_api_sync_auth_rejection(unauthed_client):
    payload = {
        "uuid": "uuid-hero-api",
        "name": "Seoni",
        "level": 1,
    }
    r1 = unauthed_client.post("/campaign/1/party/sync", json=payload)
    assert r1.status_code == 401

    unauthed_client.headers["X-API-Key"] = "wrong-bad-key"
    r2 = unauthed_client.post("/campaign/1/party/sync", json=payload)
    assert r2.status_code == 403


def test_repo_sync_rename_preserves_uuid_and_bumps_revision(repo):
    r1 = repo.sync_party_member(
        campaign_id=1,
        uuid="uuid-rename-1",
        name="Valeros",
        level=1,
        expected_revision=0,
        idempotency_key="idemp-r1",
    )
    assert r1["revision"] == 1

    r2 = repo.sync_party_member(
        campaign_id=1,
        uuid="uuid-rename-1",
        name="Valeros the Bold",
        level=2,
        expected_revision=1,
        idempotency_key="idemp-r2",
    )
    assert r2["revision"] == 2
    assert r2["uuid"] == "uuid-rename-1"
    assert r2["name"] == "Valeros the Bold"

    party = repo.get_party(1)
    assert len(party) == 1
    assert party[0]["name"] == "Valeros the Bold"


def test_repo_sync_rejects_uuid_name_hijack_and_unversioned_overwrite(repo):
    repo.sync_party_member(
        campaign_id=1,
        uuid="uuid-owner-1",
        name="Kyra",
        level=1,
        expected_revision=0,
        idempotency_key="idemp-owner-1",
    )

    with pytest.raises(RevisionConflictError) as hijack_exc:
        repo.sync_party_member(
            campaign_id=1,
            uuid="uuid-intruder-2",
            name="Kyra",
            level=5,
            expected_revision=0,
            idempotency_key="idemp-intruder-1",
        )
    assert hijack_exc.value.current_revision == 1
    assert hijack_exc.value.server_character["uuid"] == "uuid-owner-1"

    with pytest.raises(RevisionConflictError) as unversioned_exc:
        repo.sync_party_member(
            campaign_id=1,
            uuid="uuid-owner-1",
            name="Kyra",
            level=2,
            expected_revision=None,
            idempotency_key="idemp-new-client",
        )
    assert unversioned_exc.value.current_revision == 1

    with pytest.raises(RevisionConflictError) as missing_exc:
        repo.sync_party_member(
            campaign_id=1,
            uuid="uuid-missing-3",
            name="Ezren",
            level=1,
            expected_revision=2,
            idempotency_key="idemp-missing",
        )
    assert missing_exc.value.current_revision == 0
    assert missing_exc.value.expected_revision == 2


def test_repo_sync_rejects_rename_into_existing_name_with_conflict(repo):
    repo.sync_party_member(
        campaign_id=1,
        uuid="uuid-hero-a",
        name="Merisiel",
        level=1,
        expected_revision=0,
        idempotency_key="idemp-a",
    )
    repo.sync_party_member(
        campaign_id=1,
        uuid="uuid-hero-b",
        name="Harsk",
        level=1,
        expected_revision=0,
        idempotency_key="idemp-b",
    )

    with pytest.raises(RevisionConflictError) as rename_conflict:
        repo.sync_party_member(
            campaign_id=1,
            uuid="uuid-hero-b",
            name="Merisiel",
            level=2,
            expected_revision=1,
            idempotency_key="idemp-b-rename",
        )
    assert rename_conflict.value.server_character["uuid"] == "uuid-hero-a"


def test_repo_legacy_upsert_bumps_revision(repo):
    repo.sync_party_member(
        campaign_id=1,
        uuid="uuid-legacy-test",
        name="Amiri",
        level=1,
        expected_revision=0,
        idempotency_key="idemp-amiri-1",
    )
    repo.upsert_party_member(campaign_id=1, name="Amiri", level=2)

    with pytest.raises(RevisionConflictError) as exc_info:
        repo.sync_party_member(
            campaign_id=1,
            uuid="uuid-legacy-test",
            name="Amiri",
            level=3,
            expected_revision=1,
            idempotency_key="idemp-amiri-2",
        )
    assert exc_info.value.current_revision == 2


def test_repo_upgrades_pre_phase2_db_in_place(tmp_path):
    legacy_db = tmp_path / "legacy_campaign.db"
    conn = sqlite3.connect(legacy_db)
    conn.executescript(
        """
        CREATE TABLE campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            edition TEXT NOT NULL DEFAULT '2e',
            summary TEXT,
            combat_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE encounters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            kind TEXT NOT NULL DEFAULT 'battle',
            status TEXT NOT NULL DEFAULT 'pending',
            location_id INTEGER
        );
        CREATE TABLE party_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            player_name TEXT,
            class TEXT,
            level INTEGER DEFAULT 1,
            ancestry TEXT,
            background TEXT,
            stats_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(campaign_id, name)
        );
        INSERT INTO campaigns (id, name) VALUES (1, 'Legacy Campaign');
        INSERT INTO party_members (campaign_id, name, class, level)
        VALUES (1, 'OldHero', 'Wizard', 4);
        """
    )
    conn.close()

    upgraded_repo = CampaignRepository(str(legacy_db))
    synced = upgraded_repo.sync_party_member(
        campaign_id=1,
        uuid="uuid-upgraded-hero",
        name="OldHero",
        class_="Wizard",
        level=5,
        expected_revision=None,
        idempotency_key="idemp-upgrade-1",
    )
    assert synced["uuid"] == "uuid-upgraded-hero"
    assert synced["revision"] == 2


def test_api_sync_invalid_campaign_id_rejected(authed_client):
    r = authed_client.post(
        "/campaign/0/party/sync",
        json={"uuid": "uuid-bad-cid", "name": "Valeros", "level": 1},
    )
    assert r.status_code == 422
