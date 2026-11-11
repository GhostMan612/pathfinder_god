# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Contract tests for the standalone encounter-stage page.

No browser automation here: the page and its JS island must exist, the Three.js
mount point and pinned version must be present, and the scene JSON the page
consumes must validate against the existing SceneResponse model.
"""
from __future__ import annotations

from app.agents.map_maker import MapLayout, MapMakerAgent, MapRoom
from app.api.maps import SceneResponse


def test_stage_page_and_script_are_served(authenticated_client):
    page = authenticated_client.get("/stage")
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert 'id="three-mount"' in page.text
    assert "/stage/stage.js" in page.text
    assert "Content-Security-Policy" in page.headers

    script = authenticated_client.get("/stage/stage.js")
    assert script.status_code == 200
    assert script.headers["content-type"].startswith("text/javascript")
    assert "three@0.170.0" in script.text
    assert "import * as THREE" in script.text
    assert "encounter_stage" in script.text


def test_stage_page_is_not_in_openapi(authenticated_client):
    schema = authenticated_client.get("/openapi.json").json()
    assert "/stage" not in schema["paths"]
    assert "/stage/stage.js" not in schema["paths"]


def test_stage_scene_contract_matches_scene_response(authenticated_client):
    layout = MapLayout(
        width=12,
        height=10,
        rooms=[MapRoom(x=1, y=1, w=10, h=8, name="SAMPLE STAGE")],
        secret_features=[],
    )
    scene = MapMakerAgent.derive_scene(
        layout,
        heroes=["SAMPLE HERO"],
        monsters=["SAMPLE MONSTER"],
        npcs=["SAMPLE NPC"],
        loot=["SAMPLE LOOT"],
    ).to_dict()

    validated = SceneResponse.model_validate(scene)
    assert validated.grid.w == 12
    assert validated.grid.h == 10
    assert any(token.kind == "hero" for token in validated.tokens)
    assert any(token.kind == "npc" for token in validated.tokens)
    assert any(token.kind == "loot" for token in validated.tokens)

    script = authenticated_client.get("/stage/stage.js")
    for field in ("grid", "walkable", "doors", "tokens", "spawn", "exit"):
        assert f"scene.{field}" in script.text or f"scene?.{field}" in script.text


def test_stage_reconnect_only_allows_current_socket_to_update_ui(
    authenticated_client,
) -> None:
    """Source-level regression; browser event-order testing remains separate."""
    source = authenticated_client.get("/stage/stage.js").text
    assert "const previous = ws;" in source
    assert "ws = null;" in source
    assert "const socket = new WebSocket(url);" in source
    assert "if (ws !== socket) return;" in source
    assert "if (ws === socket) setStatus('WebSocket error.');" in source
    assert "socket.send(JSON.stringify({" in source
    assert "ws.send(JSON.stringify({" not in source


def test_stage_stream_log_is_bounded_and_escaped(
    authenticated_client,
) -> None:
    source = authenticated_client.get("/stage/stage.js").text
    assert "const MAX_LOG_CHARS = 16_384;" in source
    assert "next.slice(0, MAX_LOG_CHARS)" in source
    assert "logEl.textContent = " in source
    assert "logEl.innerHTML" not in source


def test_stage_respects_valid_campaign_query_parameter(authenticated_client) -> None:
    """Dashboard links use /stage?campaign_id=N; page must honor that N."""
    html = authenticated_client.get("/stage?campaign_id=9").text
    assert 'id="campaign-id"' in html
    script = authenticated_client.get("/stage/stage.js").text
    assert "new URLSearchParams(location.search).get('campaign_id')" in script
    assert "Number.isSafeInteger(requestedNumber)" in script
    assert "requestedNumber <= 2147483647" in script
    assert "document.getElementById('campaign-id').value" in script
