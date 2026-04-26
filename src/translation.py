"""
Translation layer T-code: converts parsed game trajectory events into abstract
Constraint objects (game domain stub — implementation in Session 5).

This module owns the six constraint dataclasses (identical interface to v1/v2)
plus stub translate_event / translate_trajectory functions.

Constraint type mappings (SPEC.md §Constraint type mappings):
  ResourceBudget        — material count and tempo
  ToolAvailability      — legal move set; piece mobility
  SubGoalTransition     — phase transitions (opening → middlegame → endgame)
  InformationState      — always constant complete (perfect-information games)
  CoordinationDependency — piece coordination (batteries, pawn structure)
  OptimizationCriterion — implicit evaluation function inferred from move choice

FROZEN at git tag T-code-game-v1.0-frozen after Session 6 pilot inspection.
Do NOT modify translate_event, translate_trajectory, or the dataclasses after
that tag without a new pre-registration.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Constraint dataclasses  (identical interface to v1/v2 — SPEC §Pipeline Reuse)
# ---------------------------------------------------------------------------

@dataclass
class ResourceBudget:
    """Material count and tempo budget for game domain."""
    timestamp: int
    resource: str           # e.g. "material_white", "tempo_remaining"
    amount: float           # normalised 0.0–1.0
    decay: str              # "none" | "monotone_decrease" | "fluctuating"
    recover_in: int | None  # expected moves until replenished, or None


@dataclass
class ToolAvailability:
    """Legal move set availability; piece mobility."""
    timestamp: int
    tool: str               # e.g. "piece_A", "move_set_side_1"
    state: str              # "available" | "unavailable"
    recover_in: int | None  # None ↔ permanent (piece captured)


@dataclass
class SubGoalTransition:
    """Phase transition in game plan."""
    timestamp: int
    from_phase: str         # e.g. "opening", "middlegame"
    to_phase: str           # e.g. "middlegame", "endgame"
    trigger: str            # e.g. "material_exchange", "pawn_structure_change"


@dataclass
class InformationState:
    """Observability state — always complete in perfect-information games.

    Entered into chains as constant InformationState(state='complete') to
    preserve the six-type structure for cross-experiment comparability.
    (SPEC §Known asymmetry: InformationState is non-actionable in formal games)
    """
    timestamp: int
    observable_added: list[str] = field(default_factory=list)
    observable_removed: list[str] = field(default_factory=list)
    uncertainty: float = 0.0    # always 0.0 for perfect-information games


@dataclass
class CoordinationDependency:
    """Piece coordination dependencies (batteries, X-rays, pawn structure)."""
    timestamp: int
    role: str               # e.g. "side_white", "side_black"
    dependency: str         # e.g. "battery_A", "pawn_chain_B"
    expected_action: str    # abstract action hint


@dataclass
class OptimizationCriterion:
    """Implicit evaluation function inferred from move choice."""
    timestamp: int
    objective: str          # e.g. "material_gain", "king_safety", "mobility"
    weight_shift: str       # type-specific descriptor (abstract labels)


# Union type for all constraints
Constraint = (
    ResourceBudget
    | ToolAvailability
    | SubGoalTransition
    | InformationState
    | CoordinationDependency
    | OptimizationCriterion
)

# Mapping from type name string → dataclass (used by deserialisation)
_TYPE_MAP: dict[str, type] = {
    "ResourceBudget": ResourceBudget,
    "ToolAvailability": ToolAvailability,
    "SubGoalTransition": SubGoalTransition,
    "InformationState": InformationState,
    "CoordinationDependency": CoordinationDependency,
    "OptimizationCriterion": OptimizationCriterion,
}


def constraint_from_dict(d: dict[str, Any]) -> Constraint:
    """Deserialise a constraint dict (from JSONL) back to a dataclass instance."""
    type_name = d.get("type", "")
    cls = _TYPE_MAP.get(type_name)
    if cls is None:
        raise ValueError(f"Unknown constraint type: {type_name!r}")
    fields = {f.name for f in dataclasses.fields(cls)}
    kwargs = {k: v for k, v in d.items() if k in fields and k != "type"}
    return cls(**kwargs)


# ---------------------------------------------------------------------------
# Game trajectory event type (input to T-code)
# ---------------------------------------------------------------------------

@dataclass
class GameEvent:
    """A single move/event in a parsed game trajectory.

    Populated by parser_chess.py or parser_checkers.py.
    Full implementation in Session 4.
    """
    move_number: int
    side: str               # "white" | "black"
    event_type: str         # "move" | "capture" | "promotion" | "phase_transition"
    piece_label: str        # abstracted label e.g. "piece_A"
    from_square: str        # abstracted square label
    to_square: str          # abstracted square label
    is_capture: bool = False
    is_check: bool = False
    phase_indicator: str = "opening"   # "opening" | "middlegame" | "endgame"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrajectoryLog:
    """Sequence of GameEvents for one game.

    Populated by parser_chess.py or parser_checkers.py.
    Full implementation in Session 4.
    """
    game_id: str
    variant: str            # "chess_standard" | "chess960" | "checkers_american" | "draughts_intl"
    events: list[GameEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# T-code stubs (implemented in Session 5)
# ---------------------------------------------------------------------------

def translate_event(event: GameEvent, context: Any) -> list[Constraint]:
    """Translate a single game event into one or more Constraint objects.

    Implementation deferred to Session 5.
    Freezes at git tag T-code-game-v1.0-frozen after Session 6 pilot.
    """
    raise NotImplementedError(
        "translate_event is a stub — implement in Session 5. "
        "See SPEC.md §Constraint type mappings."
    )


def translate_trajectory(traj: TrajectoryLog) -> list[Constraint]:
    """Translate a full TrajectoryLog into an ordered list of Constraints.

    Implementation deferred to Session 5.
    Freezes at git tag T-code-game-v1.0-frozen after Session 6 pilot.
    """
    raise NotImplementedError(
        "translate_trajectory is a stub — implement in Session 5. "
        "See SPEC.md §Chain Construction."
    )
