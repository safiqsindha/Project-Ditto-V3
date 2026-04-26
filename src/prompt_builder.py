"""
Prompt builder for the Ditto v3 constraint-chain evaluation (game domain).

PROMPT_VERSION = "v3.1-game" — per SPEC_v1.1.md Amendment 1, the prompt
example was changed from a verb-noun format ("use piece_A or switch to
phase_B") to an entity-only format. The verb-noun example induced models
to emit verb-noun phrases that could not match the reference distribution's
stored entity vocabulary. The new prompt aligns the model's output space
with the reference's action space.

Versioned separately from v2's v2.0-code. The prompt is deliberately
generic: no game-domain vocabulary. Must work identically on all four
game cells with no source-specific branching.

Adapted from v2 prompt_builder.py: "pipeline" → "sequential decision process".
"""

from __future__ import annotations

import re

PROMPT_VERSION = "v3.1-game"

SYSTEM_PROMPT = """You are reasoning about a sequential decision process that operates
under a sequence of changing constraints. At each step, new constraints
may appear, existing constraints may change, and resources may be
depleted or recovered. Your job is to propose the correct adaptation
at each step, given the full prior history.

At each step you receive a partially-observable state: you see the
constraints and resource levels that have been revealed, but some
entities remain hidden until they are explicitly surfaced through an
action or information event.

Constraints carry forward unless explicitly superseded. Treat a tool
or resource marked UNAVAILABLE as persistent unless a later event
restores it."""


def cutoff_rendered(rendered: str, k: int) -> str:
    """Return only the first k steps of a rendered chain string.

    Steps in the rendered format start with "Step N" (where N is a positive
    integer). The function splits on those boundaries and returns the
    re-joined prefix for the first k steps.
    """
    if k <= 0:
        return ""

    parts = re.split(r"(Step \d+)", rendered)

    steps: list[tuple[str, str]] = []
    i = 0
    while i < len(parts) and not re.fullmatch(r"Step \d+", parts[i]):
        i += 1

    while i + 1 < len(parts):
        header = parts[i]
        body = parts[i + 1] if i + 1 < len(parts) else ""
        if re.fullmatch(r"Step \d+", header):
            steps.append((header, body))
            i += 2
        else:
            i += 1

    if not steps:
        return ""

    selected = steps[:k]
    return "".join(header + body for header, body in selected)


def build_prompt(rendered_steps: str, cutoff_k: int) -> str:
    """Build the user-facing prompt given a rendered chain up to step K.

    The system prompt is kept separate; this function returns only the
    user message.

    Prompt format (PROMPT_VERSION="v3.1-game", per SPEC_v1.1 Amendment 1):
    asks for an entity label only — no verb prefix. Reference distribution
    stores entity nouns (piece_A, chain_B, phase_endgame, etc.); aligning
    the model's output space avoids the v3.0-game vocabulary mismatch
    that produced 0% match rate at Phase 1.
    """
    return (
        f"{rendered_steps.rstrip()}\n"
        "\n"
        "---\n"
        "\n"
        f"Given the state above, what is the most likely entity (resource, tool,\n"
        f"phase, or coordination tag) at step {cutoff_k + 1}?\n"
        f"Output only a single token like piece_A, chain_B, formation_C,\n"
        f"phase_endgame, or progress_remaining.\n"
        f"No verbs, no explanation."
    )
