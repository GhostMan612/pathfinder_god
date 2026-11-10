# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

"""Shared JSON retry helper for the LLM builders.

Every builder used to call ``OllamaClient.generate`` once, parse the reply
with first-``{``/last-``}`` slicing, and fail hard on one bad draw
(``valid: False`` for character/loot/map, HTTP 400 for encounters).
This helper is the single place that:

1. asks Ollama for grammar-constrained JSON (``format="json"``),
2. parses with :func:`app.agents.continuity.parse_json_loose` (which also
   repairs fences, ``<think>`` blocks and trailing commas),
3. runs the caller's ``validate`` callable on the parsed payload and, on
   failure, feeds the validation error back into the next attempt's prompt,
4. retries up to ``max_attempts`` (default 3) and returns the parsed payload
   plus the attempt count and every error seen along the way.

Callers keep their own public ``BuildResult`` shapes; they only gain
``attempts``/``errors`` detail. No builder invents its own JSON extraction
any more.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


@dataclass
class JsonBuildOutcome:
    """Result of a retried JSON generation.

    ``data`` is the parsed payload that passed ``validate`` (or ``None`` when
    every attempt failed). ``attempts`` counts LLM calls actually made.
    ``errors`` collects every parse/validation/LLM error, in order, so a
    caller can report what went wrong without hiding the failed draws.
    """

    data: Any | None
    attempts: int
    errors: list[str]


async def generate_validated_json(
    llm: Any,
    *,
    prompt: str,
    model: str,
    temperature: float,
    num_predict: int,
    validate: Callable[[Any], list[str]] | None = None,
    max_attempts: int = MAX_ATTEMPTS,
) -> JsonBuildOutcome:
    """Generate JSON with the LLM, retrying with the error fed back.

    ``validate`` receives the parsed payload and returns a list of error
    strings (empty means the payload is acceptable). It is also how a caller
    enforces Pydantic/deterministic checks inside the retry loop instead of
    after it, so a fixable draw gets a second chance instead of a rejection.
    """
    # Lazy import: continuity imports the orchestrator at module level, and
    # the orchestrator imports npc_compiler, which imports this module.
    # Importing parse_json_loose at the top would close that cycle at load
    # time; by call time every module is initialised.
    from app.agents.continuity import parse_json_loose

    errors: list[str] = []
    current_prompt = prompt
    attempts = 0
    for attempt in range(1, max_attempts + 1):
        attempts = attempt
        try:
            raw = await llm.generate(
                prompt=current_prompt,
                model=model,
                temperature=temperature,
                num_predict=num_predict,
                format="json",
            )
        except Exception as exc:  # LLM down / timeout: retry, then report.
            errors.append(f"LLM generation failed: {exc}")
            logger.warning("JSON builder attempt %d/%d LLM failed: %s", attempt, max_attempts, exc)
            current_prompt = (
                prompt
                + "\n\nPrevious attempt failed to generate a response. "
                + "Return ONLY a valid JSON object matching the schema."
            )
            continue

        parsed = parse_json_loose(raw or "")
        if parsed is None:
            errors.append("LLM returned no valid JSON object")
            current_prompt = (
                prompt
                + "\n\nPrevious attempt returned no valid JSON object. "
                + "Return ONLY a valid JSON object matching the schema, "
                + "no markdown, no commentary."
            )
            continue

        if validate is not None:
            validation_errors = validate(parsed)
            if validation_errors:
                errors.extend(validation_errors)
                current_prompt = (
                    prompt
                    + "\n\nPrevious attempt was rejected for these reasons:\n"
                    + "\n".join(f"- {err}" for err in validation_errors)
                    + "\nFix them and return ONLY a valid JSON object."
                )
                continue

        return JsonBuildOutcome(data=parsed, attempts=attempts, errors=errors)

    return JsonBuildOutcome(data=None, attempts=attempts, errors=errors)
