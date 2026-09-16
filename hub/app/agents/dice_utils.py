# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Dice rolling utility for deterministic dice notation parsing and rolling."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass


@dataclass
class DiceTerm:
    sign: int
    count: int
    sides: int
    keep_highest: int = -1
    keep_lowest: int = -1
    flat: int = 0

    @property
    def is_flat(self) -> bool:
        return self.count == 0 or self.sides == 0


@dataclass
class TermResult:
    term: "DiceTerm"
    rolls: list[int]
    kept: list[int]
    subtotal: int


@dataclass
class DiceResult:
    notation: str
    terms: list["TermResult"]
    total: int

    @property
    def breakdown(self) -> str:
        parts = []
        for t in self.terms:
            if t.term.is_flat:
                parts.append(f"{t.subtotal:+d}")
            else:
                rolled = ",".join(str(r) for r in t.rolls)
                kept_note = (
                    f"->[{','.join(map(str, t.kept))}]"
                    if len(t.kept) != len(t.rolls)
                    else ""
                )
                sign = "" if t.term.sign > 0 else "- "
                parts.append(
                    f"{sign}{t.term.count}d{t.term.sides}[{rolled}]{kept_note}"
                )
        return f"{' '.join(parts)} = {self.total}"


class DiceFormatException(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(f"DiceFormatException: {message}")


class DiceRoller:
    def __init__(self, rng: random.Random | None = None):
        self._rng = rng or random.SystemRandom()

    def roll(self, notation: str) -> "DiceResult":
        terms = self.parse(notation)
        results = []
        total = 0
        for term in terms:
            r = self._roll_term(term)
            results.append(r)
            total += r.subtotal
        return DiceResult(notation.strip(), results, total)

    def _roll_term(self, term: "DiceTerm") -> "TermResult":
        if term.is_flat:
            v = term.sign * term.flat
            return TermResult(term, [], [], v)
        rolls = [random.randint(1, term.sides) for _ in range(term.count)]
        kept = list(rolls)
        if term.keep_highest >= 0:
            kept.sort(reverse=True)
            kept = kept[: term.keep_highest]
        elif term.keep_lowest >= 0:
            kept.sort()
            kept = kept[: term.keep_lowest]
        s = sum(kept)
        return TermResult(term, rolls, kept, term.sign * s)

    @staticmethod
    def parse(notation: str) -> list["DiceTerm"]:
        cleaned = notation.replace(" ", "").lower()
        if not cleaned:
            raise ValueError("empty notation")

        term_regex = re.compile(r"([+-]?)([^+-]+)")
        terms = []
        for m in term_regex.finditer(cleaned):
            sign = -1 if m.group(1) == "-" else 1
            body = m.group(2)
            if not body:
                continue
            terms.append(_parse_body(sign, body))
        if not terms:
            raise ValueError("no terms in notation")
        return terms


def _parse_body(sign: int, body: str) -> "DiceTerm":
    if body.isdigit():
        return DiceTerm(sign=sign, count=0, sides=0, flat=int(body))

    m = re.match(r"^(\d*)d(\d+)(?:(kh|kl)(\d+))?$", body)
    if not m:
        raise ValueError(f"cannot parse term: {body}")

    count = int(m.group(1)) if m.group(1) else 1
    sides = int(m.group(2))
    if not (1 <= count <= 1000 and 1 <= sides <= 1000):
        raise ValueError(f"invalid dice: {count}d{sides}")

    keep_highest = -1
    keep_lowest = -1
    kind = m.group(3)
    if kind == "kh":
        keep_highest = int(m.group(4))
    elif kind == "kl":
        keep_lowest = int(m.group(4))

    return DiceTerm(
        sign=sign,
        count=count,
        sides=sides,
        keep_highest=keep_highest,
        keep_lowest=keep_lowest,
    )


def roll_dice(
    notation: str, rng: random.Random | None = None
) -> tuple[int, list[int], list[int]]:
    """Roll dice and return (total, all_rolls, kept_rolls)."""
    roller = DiceRoller()
    result = roller.roll(notation)
    all_rolls = []
    kept_rolls = []
    for term in result.terms:
        all_rolls.extend(term.rolls)
        kept_rolls.extend(term.kept)
    return result.total, all_rolls, kept_rolls