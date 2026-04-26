"""
Chain validity filter — adapted for v3 game domain (SPEC.md §Chain Construction).

Checks whether a constraint chain meets the quality criteria for inclusion
in the evaluation dataset. Chain length target for games is 15–25 events
(vs. 20–40 for v2 programming agents).
"""

from __future__ import annotations

import dataclasses

from src.translation import (
    Constraint,
    CoordinationDependency,
    InformationState,
    OptimizationCriterion,
    ResourceBudget,
    SubGoalTransition,
    ToolAvailability,
)


# ---------------------------------------------------------------------------
# Validity failure reason codes
# ---------------------------------------------------------------------------
# Stable codes used by the diagnostic tooling (scripts/*) and SESSION_LOG.md
# entries. New codes may be added; existing codes must not be renamed without
# a SESSION_LOG note since downstream debug scripts grep for them.

VALIDITY_REASONS = (
    "length_below_min",       # < 15 constraints
    "length_above_max",       # > 25 constraints
    "sgt_below_min",          # < 1 SubGoalTransition
    "ta_below_min",           # < 1 ToolAvailability
    "rb_below_min",           # < 3 ResourceBudget
    "timestamp_order",        # timestamps not non-decreasing
    "consecutive_duplicate",  # two adjacent identical constraints
)


def validity_failures(constraints: list[Constraint]) -> list[str]:
    """
    Diagnostic counterpart to is_valid_chain(): returns ALL failure reasons.

    Empty list ↔ chain is valid.
    Returns a list of stable reason codes (see VALIDITY_REASONS) describing
    every criterion the chain violates. This bucketed view is what
    scripts/generate_pilot_chains.py and any future debug tooling use to
    surface bottlenecks (e.g. "all chess_standard rejections fail on
    sgt_below_min" → priority weights are off, not a sample-size issue).

    Single-pass: counts constraint types in one walk, then evaluates all
    threshold criteria. Same logical checks as is_valid_chain() but does
    not short-circuit.

    Validity criteria (SPEC §Chain Construction):
      - length ∈ [15, 25]                        (game domain target)
      - ≥ 1 SubGoalTransition (phase shift / subgoal completion)
      - ≥ 1 ToolAvailability  (legal-move-set change)
      - ≥ 3 ResourceBudget    (material / progress counts)
      - timestamps non-decreasing
      - no two adjacent constraints identical (no stuttering)
    """
    failures: list[str] = []
    n = len(constraints)

    # Length bounds
    if n < 15:
        failures.append("length_below_min")
        # Cannot evaluate other criteria meaningfully on tiny chains, but
        # continue anyway so the caller sees the full picture.
    elif n > 25:
        failures.append("length_above_max")

    # Type counts (single pass)
    subgoal_count = 0
    tool_count = 0
    resource_count = 0
    for c in constraints:
        if isinstance(c, SubGoalTransition):
            subgoal_count += 1
        elif isinstance(c, ToolAvailability):
            tool_count += 1
        elif isinstance(c, ResourceBudget):
            resource_count += 1

    if subgoal_count < 1:
        failures.append("sgt_below_min")
    if tool_count < 1:
        failures.append("ta_below_min")
    if resource_count < 3:
        failures.append("rb_below_min")

    # Timestamp ordering
    for i in range(1, n):
        t_prev = getattr(constraints[i - 1], "timestamp", 0)
        t_curr = getattr(constraints[i], "timestamp", 0)
        if t_curr < t_prev:
            failures.append("timestamp_order")
            break

    # Consecutive duplicate (same type AND same field values)
    for i in range(1, n):
        if type(constraints[i]) == type(constraints[i - 1]):
            if dataclasses.asdict(constraints[i]) == dataclasses.asdict(constraints[i - 1]):
                failures.append("consecutive_duplicate")
                break

    return failures


def is_valid_chain(constraints: list[Constraint]) -> bool:
    """
    A chain is valid if ALL of:
    - length between 15 and 25 (inclusive) — game domain target (SPEC §Chain Construction)
    - contains >= 1 SubGoalTransition event (phase transition)
    - contains >= 1 ToolAvailability event (legal-move-set change)
    - contains >= 3 ResourceBudget events (material/progress counts)
    - timestamps are strictly non-decreasing
    - no two consecutive constraints are identical (no stuttering)

    Implementation: thin wrapper around validity_failures() so the boolean
    gate and the diagnostic tracker can never drift out of sync.
    """
    return not validity_failures(constraints)


def filter_chains(chains: list[dict]) -> list[dict]:
    """Apply is_valid_chain to a list of chain dicts.

    Each chain dict must have a 'constraints' key containing a list of
    Constraint dataclass instances (not serialized dicts).
    """
    return [chain for chain in chains if is_valid_chain(chain["constraints"])]
