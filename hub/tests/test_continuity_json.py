# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Continuity extraction hardening for noisy qwen2.5:3b output (BP-08).

Pure functions + one async path with a stubbed LLM, so no model is needed.
"""

from __future__ import annotations

import asyncio
import pathlib

import pytest

from app.agents.continuity import (
    ContinuityKeeper,
    _coerce_entries,
    normalize_entity_payload,
    parse_json_loose,
    repair_json_text,
)

# ── JSON repair ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"npcs": [{"name": "Garrick"}]}', {"npcs": [{"name": "Garrick"}]}),
        # Markdown fence
        ('```json\n{"npcs": [{"name": "Garrick"}]}\n```',
         {"npcs": [{"name": "Garrick"}]}),
        ('```\n{"npcs": []}\n```', {"npcs": []}),
        # conversational prose wrapped around the payload
        ('Here you go:\n{"npcs": [{"name": "Lyra"}]}\nHope that helps!',
         {"npcs": [{"name": "Lyra"}]}),
        # trailing commas
        ('{"npcs": [{"name": "Seraphina"},]}', {"npcs": [{"name": "Seraphina"}]}),
        ('{"npcs": [{"name": "Ogre"},],}', {"npcs": [{"name": "Ogre"}]}),
        # leaked reasoning block
        ('<think>let me think</think>{"items": [{"name": "Sword"}]}',
         {"items": [{"name": "Sword"}]}),
        # bare top-level array
        ('[{"name": "Goblin"}]', [{"name": "Goblin"}]),
    ],
)
def test_parse_json_loose_recovers(raw: str, expected):
    assert parse_json_loose(raw) == expected


def test_parse_json_loose_returns_none_for_garbage():
    assert parse_json_loose("I am afraid I cannot do that.") is None
    assert parse_json_loose("") is None
    assert parse_json_loose(None) is None


def test_repair_strips_unbalanced_prose_around_object():
    text = 'Sure! {"npcs": [{"name": "A"}]} but only that.'
    assert "npcs" in repair_json_text(text)


# ── alias normalisation + coercion ───────────────────────────────


def test_alias_keys_are_mapped_to_contract_names():
    payload = {
        "characters": [{"name": "Garrick"}],
        "people": [{"name": "Lyra"}],
        "places": [{"name": "The Vault"}],
        "rooms": [{"name": "Inner Room"}],
        "loot": [{"name": "Wand of Doom"}],
        "objects": [{"name": "Cloak"}],
        "tasks": [{"name": "Find the amulet"}],
        "hooks": [{"name": "Seraphina returns"}],
        "choices": [{"name": "Spare the goblin"}],
    }
    out = normalize_entity_payload(payload)
    assert [e["name"] for e in out["npcs"]] == ["Garrick", "Lyra"]
    assert [e["name"] for e in out["locations"]] == ["The Vault", "Inner Room"]
    assert [e["name"] for e in out["items"]] == ["Wand of Doom", "Cloak"]
    assert [e["name"] for e in out["quests"]] == ["Find the amulet", "Seraphina returns"]
    assert [e["name"] for e in out["decisions"]] == ["Spare the goblin"]


def test_canonical_keys_still_win():
    out = normalize_entity_payload({"npcs": [{"name": "Canonical"}], "characters": []})
    assert [e["name"] for e in out["npcs"]] == ["Canonical"]


def test_bare_string_entities_are_coerced_not_dropped():
    """The old isinstance(dict) filter silently discarded every one of these."""
    assert _coerce_entries(["Garrick", "Lyra"]) == [
        {"name": "Garrick"},
        {"name": "Lyra"},
    ]


def test_coerce_skips_unusable_entries():
    assert _coerce_entries([{"name": "ok"}, 42, None, "  ", "", "Real"]) == [
        {"name": "ok"},
        {"name": "Real"},
    ]


def test_normalize_ignores_non_dict_payloads():
    assert normalize_entity_payload(["nope"]) == {}
    assert normalize_entity_payload(None) == {}
    assert normalize_entity_payload("string") == {}


# ── end-to-end extraction through the keeper ─────────────────────


class _StubLLM:
    """Stands in for OllamaClient; records the kwargs the caller passed."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[dict] = []

    async def generate(self, prompt: str, **kwargs) -> str:
        self.calls.append(kwargs)
        return self.reply


def _keeper(reply: str, tmp_path: pathlib.Path) -> tuple[ContinuityKeeper, _StubLLM]:
    llm = _StubLLM(reply)
    keeper = ContinuityKeeper.__new__(ContinuityKeeper)
    keeper.llm = llm
    keeper.repo = None
    return keeper, llm


def test_extract_entities_from_noisy_output(tmp_path):
    reply = (
        "Sure, here is the JSON you asked for:\n"
        "```json\n"
        '{\n  "characters": ["Garrick", "Lyra"],\n'
        '  "places": [{"name": "The Vault"}],\n'
        '  "loot": [{"name": "Wand of Doom"},],\n'
        '  "tasks": ["Find the amulet"]\n'
        "}\n"
        "```\n"
        "Let me know if you need more."
    )
    keeper, llm = _keeper(reply, tmp_path)
    entities = asyncio.run(keeper._extract_entities("log"))

    assert [n.name for n in entities.npcs] == ["Garrick", "Lyra"]
    assert [loc.name for loc in entities.locations] == ["The Vault"]
    assert [i.name for i in entities.items] == ["Wand of Doom"]
    assert [q.name for q in entities.quests] == ["Find the amulet"]

    # JSON mode + deterministic temperature must be requested.
    assert llm.calls[0].get("format") == "json"
    assert llm.calls[0].get("temperature") == 0.0


def test_extract_entities_survives_total_garbage(tmp_path):
    keeper, _ = _keeper("I'm sorry Dave, I'm afraid I can't do that.", tmp_path)
    entities = asyncio.run(keeper._extract_entities("log"))
    assert entities.npcs == [] and entities.items == []


def test_extract_entities_handles_bare_array(tmp_path):
    keeper, _ = _keeper('[{"name": "Ogre"}, {"name": "Goblin"}]', tmp_path)
    entities = asyncio.run(keeper._extract_entities("log"))
    assert [n.name for n in entities.npcs] == ["Ogre", "Goblin"]


def test_extract_facts_from_wrapped_array(tmp_path):
    reply = '```json\n{"facts": [{"fact": "The vault is trapped."}]}\n```'
    keeper, _ = _keeper(reply, tmp_path)
    facts = asyncio.run(
        keeper._extract_facts("log", type("E", (), {"all_names": lambda self: []})())
    )
    assert len(facts) == 1
    assert facts[0].fact == "The vault is trapped."


def test_extract_facts_returns_empty_on_garbage(tmp_path):
    keeper, _ = _keeper("no json", tmp_path)
    facts = asyncio.run(
        keeper._extract_facts("log", type("E", (), {"all_names": lambda self: []})())
    )
    assert facts == []