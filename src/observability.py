"""
Asymmetric observability filter for game constraint chains (SPEC.md §3.3).

In the game domain, piece identities are progressively revealed through
moves and captures. The abstraction: ToolAvailability constraints should
only reference pieces that have been revealed via a prior event.

Entity labels for game domain (v3 adaptation from v2 file/command labels):
  piece_A, piece_B, ... piece_N  (abstract piece labels)
  move_set_side_1, move_set_side_2 (legal move set for each side)
  phase_opening, phase_middlegame, phase_endgame

Adapted from v2 observability.py: entity labels updated for game domain.
"""

from __future__ import annotations

import re

from src.translation import (
    Constraint,
    CoordinationDependency,
    InformationState,
    OptimizationCriterion,
    ResourceBudget,
    SubGoalTransition,
    ToolAvailability,
)


def bucket_resource(amount: float) -> float:
    """Bucket 0.0–1.0 resource amount to {0.0, 0.25, 0.5, 0.75, 1.0}."""
    if amount <= 0:
        return 0.0
    if amount <= 0.25:
        return 0.25
    if amount <= 0.5:
        return 0.5
    if amount <= 0.75:
        return 0.75
    return 1.0


def _find_reveal_indices(constraints: list[Constraint]) -> dict[str, int]:
    """
    Return a mapping from entity label to the index of its first
    InformationState revelation in the constraint list.

    In game domain, InformationState is constant (complete) so this
    primarily tracks piece labels surfaced through ToolAvailability events.
    """
    first_reveal: dict[str, int] = {}
    for i, c in enumerate(constraints):
        if isinstance(c, InformationState):
            for entity in c.observable_added:
                if entity not in first_reveal:
                    first_reveal[entity] = i
    return first_reveal


def _find_pre_reveal_ta_indices(
    constraints: list[Constraint],
    first_reveal: dict[str, int],
) -> set[int]:
    """
    Identify ToolAvailability constraints that appear before the corresponding
    entity has been revealed via InformationState.

    In game domain: piece captures and promotions reveal new mobility states.
    Any ToolAvailability for an entity before its first reveal is suppressed.
    """
    suppress_indices: set[int] = set()
    for i, c in enumerate(constraints):
        if not isinstance(c, ToolAvailability):
            continue
        entity = c.tool
        if entity in first_reveal and i < first_reveal[entity]:
            suppress_indices.add(i)
    return suppress_indices


def apply_asymmetric_observability_with_indices(
    constraints: list[Constraint],
    perspective: str = "agent",
) -> tuple[list[Constraint], list[int]]:
    """Apply asymmetric observability filter; return (filtered_constraints, kept_indices)."""
    first_reveal = _find_reveal_indices(constraints)
    suppress_ta_indices = _find_pre_reveal_ta_indices(constraints, first_reveal)

    result: list[Constraint] = []
    kept_indices: list[int] = []

    for i, c in enumerate(constraints):
        if i in suppress_ta_indices:
            continue
        if isinstance(c, ResourceBudget):
            bucketed_amount = bucket_resource(c.amount)
            import dataclasses
            c = dataclasses.replace(c, amount=bucketed_amount)
        result.append(c)
        kept_indices.append(i)

    return result, kept_indices


def apply_asymmetric_observability(
    constraints: list[Constraint],
    perspective: str = "agent",
) -> list[Constraint]:
    """Apply asymmetric observability filter; return filtered constraints."""
    result, _ = apply_asymmetric_observability_with_indices(constraints, perspective)
    return result


# ---------------------------------------------------------------------------
# Abstract entity label helpers (game domain — v3 specific)
# ---------------------------------------------------------------------------

_MAX_PIECES = 16  # up to 16 pieces per side at game start
_PIECE_LABELS = [f"piece_{chr(ord('A') + i)}" for i in range(_MAX_PIECES)]

_MAX_PHASE_LABELS = 3
_PHASE_LABELS = ["phase_opening", "phase_middlegame", "phase_endgame"]

_SIDE_LABELS = ["side_1", "side_2"]


def piece_label(index: int) -> str:
    """Return abstract piece label for the given index (0-based)."""
    if 0 <= index < len(_PIECE_LABELS):
        return _PIECE_LABELS[index]
    return f"piece_{index}"


def phase_label(phase: str) -> str:
    """Normalise a game phase string to an abstract phase label."""
    phase = phase.lower()
    if "open" in phase:
        return "phase_opening"
    if "mid" in phase or "middle" in phase:
        return "phase_middlegame"
    if "end" in phase:
        return "phase_endgame"
    return f"phase_{phase}"
