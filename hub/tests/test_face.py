# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""The htmx face renders campaign state and streams a turn over SSE.

These tests keep the browser face honest: it must expose the same deterministic
turn path as the WS stream, use vendored htmx (no CDN dependency), and protect
campaign data with the existing API key when one is configured.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.deps import get_repo

TEST_API_KEY = "pfg_test_key_12345"


def _seed_campaign():
    get_repo.cache_clear()
    repo = get_repo()
    campaign = repo.create_campaign("FACE CAMPAIGN", "2e")
    repo.upsert_party_member(
        campaign.id,
        "FACE HERO",
        player_name="Glenn",
        class_="Fighter",
        level=3,
        ancestry="Human",
        stats={"hp": 20, "max_hp": 20},
    )
    repo.add_combatant(
        campaign.id,
        "FACE HERO",
        "hero",
        hp=20,
        max_hp=20,
        ac=17,
        initiative=12,
    )
    repo.add_combatant(
        campaign.id,
        "FACE GOBLIN",
        "monster",
        hp=6,
        max_hp=6,
        ac=12,
        initiative=8,
    )
    repo.ensure_solo_state(campaign.id)
    return repo, campaign


def test_face_page_renders_campaign_and_turn_form(authenticated_client: TestClient):
    _, campaign = _seed_campaign()

    response = authenticated_client.get(f"/play?campaign_id={campaign.id}")

    assert response.status_code == 200
    assert "FACE CAMPAIGN" in response.text
    assert "FACE HERO" in response.text
    assert 'id="turn-form"' in response.text
    assert "/play/static/htmx.min.js" in response.text
    assert "/play/static/face.js" in response.text
    assert "/play/turn/stream" not in response.text  # assembled in JS, not inline
    assert "<script>" not in response.text


def test_face_assets_are_vendored_and_htmx_typed(authenticated_client: TestClient):
    htmx = authenticated_client.get("/play/static/htmx.min.js")
    assert htmx.status_code == 200
    assert "text/javascript" in htmx.headers["content-type"]
    assert "htmx" in htmx.text

    face = authenticated_client.get("/play/static/face.js")
    assert face.status_code == 200
    assert "text/javascript" in face.headers["content-type"]
    assert "/play/turn/stream" in face.text

    css = authenticated_client.get("/play/static/face.css")
    assert css.status_code == 200
    assert "text/css" in css.headers["content-type"]


def test_face_dashboard_fragment_refreshes(authenticated_client: TestClient):
    _, campaign = _seed_campaign()

    response = authenticated_client.get(f"/play/campaign/{campaign.id}/dashboard")

    assert response.status_code == 200
    assert 'class="dashboard"' in response.text
    assert "FACE HERO" in response.text
    assert "HP 20 / 20" in response.text
    assert "pfg-turn-complete" not in response.text


def test_face_turn_stream_emits_start_dice_narration_end(authenticated_client: TestClient):
    _, campaign = _seed_campaign()

    response = authenticated_client.get(
        "/play/turn/stream",
        params={
            "campaign_id": campaign.id,
            "action": "I attack the nearest monster.",
            "seed": 7,
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: start" in body
    assert "event: dice" in body
    assert "event: narration" in body
    assert "event: end" in body
    assert '"type":"error"' not in body


def test_face_login_round_trip(client: TestClient):
    get_repo.cache_clear()
    get_repo().get_or_create_campaign(1, "LOGIN CAMPAIGN")

    unauth = client.get("/play", follow_redirects=False)
    assert unauth.status_code == 303
    assert unauth.headers["location"] == "/play/login"

    bad = client.post(
        "/play/login",
        data={"api_key": "wrong-key", "next_path": "/play"},
        follow_redirects=False,
    )
    assert bad.status_code == 401
    assert "Invalid API key" in bad.text

    good = client.post(
        "/play/login",
        data={"api_key": TEST_API_KEY, "next_path": "/play"},
        follow_redirects=False,
    )
    assert good.status_code == 303
    assert good.headers["location"] == "/play"
    assert good.cookies.get("pfgod_face")

    page = client.get("/play")
    assert page.status_code == 200
    assert "LOGIN CAMPAIGN" in page.text


def test_face_rejects_bad_stream_auth(client: TestClient):
    get_repo.cache_clear()
    campaign = get_repo().get_or_create_campaign(1, "STREAM AUTH")

    response = client.get(
        "/play/turn/stream",
        params={"campaign_id": campaign.id, "action": "look around"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized"


def test_face_create_campaign_uses_htmx_redirect(authenticated_client: TestClient):
    response = authenticated_client.post(
        "/play/campaigns",
        data={"name": "  Second   Campaign  ", "edition": "1e"},
        headers={"HX-Request": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 200
    redirect = response.headers["hx-redirect"]
    assert redirect.startswith("/play?campaign_id=")
    assert int(redirect.rsplit("=", 1)[1]) > 0

    page = authenticated_client.get(redirect)
    assert page.status_code == 200
    assert "Second Campaign" in page.text
