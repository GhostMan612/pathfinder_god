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
