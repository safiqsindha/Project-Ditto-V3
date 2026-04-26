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


def is_valid_chain(constraints: list[Constraint]) -> bool:
    """
    A chain is valid if ALL of:
    - length between 15 and 25 (inclusive) — game domain target (SPEC §Chain Construction)
    - contains >= 1 SubGoalTransition event (phase transition)
    - contains >= 1 ToolAvailability event (legal-move-set change)
    - contains >= 3 ResourceBudget events (material/tempo counts)
    - timestamps are strictly non-decreasing
    - no two consecutive constraints are identical (no stuttering)
    """
    n = len(constraints)

    if n < 15 or n > 25:
        return False

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
        return False
    if tool_count < 1:
        return False
    if resource_count < 3:
        return False

    for i in range(1, n):
        t_prev = getattr(constraints[i - 1], "timestamp", 0)
        t_curr = getattr(constraints[i], "timestamp", 0)
        if t_curr < t_prev:
            return False

    for i in range(1, n):
        if type(constraints[i]) == type(constraints[i - 1]):
            if dataclasses.asdict(constraints[i]) == dataclasses.asdict(constraints[i - 1]):
                return False

    return True


def filter_chains(chains: list[dict]) -> list[dict]:
    """Apply is_valid_chain to a list of chain dicts.

    Each chain dict must have a 'constraints' key containing a list of
    Constraint dataclass instances (not serialized dicts).
    """
    return [chain for chain in chains if is_valid_chain(chain["constraints"])]
