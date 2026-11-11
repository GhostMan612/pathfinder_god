# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================
"""Bounded, deterministic tests for the Hub's dice notation parser."""
from __future__ import annotations

import random

import pytest

from app.agents.dice_utils import DiceRoller, roll_dice


@pytest.mark.parametrize(
    "notation",
    [
        "d6+", "2d6++1", "d6--2", "d6+-2", "+-d6",
        "2d6-+3", "2d6+", "++1", "+", "-", "d6!",
        "2d6kh3", "3d8kl0", "2d6kh0",
    ],
)
def test_parser_rejects_malformed_or_impossible_terms(notation: str) -> None:
    with pytest.raises(ValueError):
        DiceRoller.parse(notation)


def test_parser_accepts_valid_signed_terms_and_keep_counts() -> None:
    terms = DiceRoller.parse("2d6kh1 + 3 - d4")
    assert len(terms) == 3
    assert terms[0].count == 2 and terms[0].sides == 6
    assert terms[0].keep_highest == 1
    assert terms[1].flat == 3 and terms[1].sign == 1
    assert terms[2].count == 1 and terms[2].sign == -1
    assert DiceRoller.parse("3d6kl3")[0].keep_lowest == 3


def test_rolling_replays_from_injected_rng() -> None:
    first = roll_dice("3d6kh2-1", rng=random.Random(42))
    second = roll_dice("3d6kh2-1", rng=random.Random(42))
    assert first == second
    total, rolls, kept = first
    assert len(rolls) == 3
    assert len(kept) == 2
    assert total == sum(kept) - 1


def test_parse_does_not_ignore_trailing_separator() -> None:
    with pytest.raises(ValueError):
        roll_dice("1d20+")
