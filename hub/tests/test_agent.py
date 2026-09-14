# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Tests for GM mode detection and prompt building."""
from __future__ import annotations

from app.agent.gm import MODE_INSTRUCTIONS, build_prompt, detect_mode


def test_detect_mode_character():
    assert detect_mode("build me a level 3 rogue") == "character"


def test_detect_mode_map():
    assert detect_mode("draw a dungeon map with a hidden crypt") == "map"


def test_detect_mode_encounter():
    assert detect_mode("make a boss monster for the finale") == "encounter"


def test_detect_mode_default_general():
    assert detect_mode("what are the rules for flanking?") == "general"


def test_build_prompt_includes_context_and_query():
    prompt = build_prompt(
        "build a rogue", "character", "2e", "Rule context here", history=[("user", "hi")]
    )
    assert "Rule context here" in prompt
    assert "build a rogue" in prompt
    assert "Edition focus: 2e" in prompt
    assert MODE_INSTRUCTIONS["character"][:20] in prompt


def test_build_prompt_no_history():
    prompt = build_prompt("q", "general", "both", "ctx")
    assert "Recent conversation:\nNone" in prompt
