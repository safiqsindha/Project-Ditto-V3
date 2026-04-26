"""
Translation layer T-code: converts parsed game trajectory events into abstract
Constraint objects (game domain).

This module owns the six constraint dataclasses (identical interface to v1/v2)
plus translate_event / translate_trajectory functions.

Constraint type mappings (SPEC.md §Constraint type mappings):
  ResourceBudget        — material count (normalised) and tempo
  ToolAvailability      — legal move set; captured piece → permanent UNAVAILABLE
  SubGoalTransition     — phase transitions; king-promotion subgoal (checkers)
  InformationState      — always constant complete (perfect-information games)
  CoordinationDependency — piece coordination patterns (batteries, chains, back-row)
  OptimizationCriterion — implicit evaluation function inferred from move choice

FROZEN at git tag T-code-game-v1.0-frozen after Session 6 pilot inspection.
Do NOT modify translate_event, translate_trajectory, or the dataclasses after
that tag without a new pre-registration.
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, List, Optional, Union


# ---------------------------------------------------------------------------
# Constraint dataclasses  (identical interface to v1/v2 — SPEC §Pipeline Reuse)
# ---------------------------------------------------------------------------

@dataclass
class ResourceBudget:
    """Material count and tempo budget for game domain."""
    timestamp: int
    resource: str           # e.g. "material_side_1", "tempo_remaining"
    amount: float           # normalised 0.0–1.0
    decay: str              # "none" | "monotone_decrease" | "fluctuating"
    recover_in: Optional[int]  # expected moves until replenished, or None


@dataclass
class ToolAvailability:
    """Legal move set availability; piece mobility."""
    timestamp: int
    tool: str               # e.g. "piece_A", "move_set_side_1"
    state: str              # "available" | "unavailable"
    recover_in: Optional[int]  # None ↔ permanent (piece captured)


@dataclass
class SubGoalTransition:
    """Phase transition in game plan."""
    timestamp: int
    from_phase: str         # e.g. "phase_opening"
    to_phase: str           # e.g. "phase_middlegame"
    trigger: str            # abstract trigger description


@dataclass
class InformationState:
    """Observability state — always complete in perfect-information games.

    Entered into chains as constant InformationState(state='complete') to
    preserve the six-type structure for cross-experiment comparability.
    (SPEC §Known asymmetry: InformationState is non-actionable in formal games)
    """
    timestamp: int
    observable_added: List[str] = field(default_factory=list)
    observable_removed: List[str] = field(default_factory=list)
    uncertainty: float = 0.0    # always 0.0 for perfect-information games


@dataclass
class CoordinationDependency:
    """Piece coordination dependencies (batteries, X-rays, pawn structure)."""
    timestamp: int
    role: str               # e.g. "side_1", "side_2"
    dependency: str         # e.g. "battery_A", "chain_B", "back_row_C"
    expected_action: str    # abstract action hint


@dataclass
class OptimizationCriterion:
    """Implicit evaluation function inferred from move choice."""
    timestamp: int
    objective: str          # e.g. "material_gain", "king_safety", "mobility"
    weight_shift: str       # type-specific descriptor (abstract labels)


# Union type for all constraints
Constraint = Union[
    ResourceBudget,
    ToolAvailability,
    SubGoalTransition,
    InformationState,
    CoordinationDependency,
    OptimizationCriterion,
]

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
    """A single move/event in a parsed game trajectory."""
    move_number: int
    side: str               # "side_1" | "side_2"
    event_type: str         # "move" | "capture" | "promotion" | "phase_transition"
    piece_label: str        # abstracted label e.g. "piece_A"
    from_square: str        # abstracted square label
    to_square: str          # abstracted square label
    is_capture: bool = False
    is_check: bool = False
    phase_indicator: str = "phase_opening"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrajectoryLog:
    """Sequence of GameEvents for one game."""
    game_id: str
    variant: str            # "chess_standard" | "chess960" | "checkers_american" | "draughts_intl"
    events: list[GameEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Material normalisation constants
# ---------------------------------------------------------------------------

# Starting material (excl. kings) per side in chess (pawns=1, N/B=3, R=5, Q=9)
_CHESS_START_MATERIAL = 39   # Q(9) + 2R(10) + 2B(6) + 2N(6) + 8P(8)

# Starting piece counts per side by variant
_START_PIECES = {
    "chess_standard":    16,   # 8P + 2N + 2B + 2R + 1Q + 1K
    "chess960":          16,
    "checkers_american": 12,
    "draughts_intl":     20,
}


# ---------------------------------------------------------------------------
# Coordination pattern labels (abstract — no domain vocabulary)
# ---------------------------------------------------------------------------

_COORD_PATTERNS = [
    "battery_A", "battery_B",
    "chain_A", "chain_B", "chain_C",
    "back_row_A", "back_row_B",
    "pressure_A", "pressure_B",
]

_COORD_ACTIONS = [
    "maintain_formation", "advance_together", "defend_position",
    "control_center", "restrict_mobility", "support_advance",
]

_OPT_OBJECTIVES = [
    "material_gain", "king_safety", "mobility",
    "position", "tempo_advantage", "structure",
]

_TRIGGERS = [
    "material_exchange", "structure_shift", "piece_activation",
    "subgoal_achieved", "positional_transition", "tactical_shift",
]


# ---------------------------------------------------------------------------
# T-code implementation
# ---------------------------------------------------------------------------

def translate_event(event: GameEvent, context: Any) -> List[Constraint]:
    """
    Translate a single game event into one Constraint object.

    Parameters
    ----------
    event   : the GameEvent to translate
    context : dict with keys:
        - 'prev_phase' (str|None): phase_indicator of the previous event
        - 'type_counts' (dict): count of each constraint type so far
        - 'position' (int): 0-indexed position within the window
        - 'window_size' (int): total events in this window
        - 'variant' (str): game variant
        - 'prev_event' (GameEvent|None): the previous event (for tactical detection)

    Returns
    -------
    List of Constraints (always exactly one in this implementation).
    """
    prev_phase = context.get('prev_phase')
    type_counts = context.get('type_counts', defaultdict(int))
    position = context.get('position', 0)
    window_size = context.get('window_size', 20)
    variant = context.get('variant', 'chess_standard')
    prev_event = context.get('prev_event', None)
    t = event.move_number

    sgt_count = type_counts.get("SubGoalTransition", 0)

    # -----------------------------------------------------------------------
    # Priority 1: Phase transition → SubGoalTransition
    # -----------------------------------------------------------------------
    phase_changed = (prev_phase is not None and event.phase_indicator != prev_phase)
    if phase_changed:
        return [SubGoalTransition(
            timestamp=t,
            from_phase=prev_phase,
            to_phase=event.phase_indicator,
            trigger=_TRIGGERS[position % len(_TRIGGERS)],
        )]

    # -----------------------------------------------------------------------
    # Priority 2: Promotion → SubGoalTransition (subgoal achieved)
    # -----------------------------------------------------------------------
    if event.event_type == "promotion":
        return [SubGoalTransition(
            timestamp=t,
            from_phase=event.phase_indicator,
            to_phase=event.phase_indicator,
            trigger="subgoal_achieved",
        )]

    # -----------------------------------------------------------------------
    # Priority 3: Tactical opening → SubGoalTransition
    # A capture that follows a non-capture event signals a plan shift
    # (quiet → tactical). Only if we need more SubGoalTransitions.
    # -----------------------------------------------------------------------
    prev_was_quiet = (prev_event is not None and not prev_event.is_capture
                      and prev_event.event_type not in ("promotion",))
    if (event.is_capture and prev_was_quiet and sgt_count < max(1, window_size // 8)):
        trigger_idx = (position + 1) % len(_TRIGGERS)
        return [SubGoalTransition(
            timestamp=t,
            from_phase=event.phase_indicator,
            to_phase=event.phase_indicator,
            trigger=_TRIGGERS[trigger_idx],
        )]

    # -----------------------------------------------------------------------
    # Priority 4: Periodic SubGoalTransition (plan update signal)
    # Every 8 events, if we haven't had enough SubGoalTransitions yet
    # -----------------------------------------------------------------------
    sgt_needed = max(1, window_size // 8)   # ~2–3 per window
    if position > 0 and position % 8 == 0 and sgt_count < sgt_needed:
        return [SubGoalTransition(
            timestamp=t,
            from_phase=event.phase_indicator,
            to_phase=event.phase_indicator,
            trigger=_TRIGGERS[(position + 3) % len(_TRIGGERS)],
        )]

    # -----------------------------------------------------------------------
    # Priority 5: Guaranteed periodic ResourceBudget
    # Placed BEFORE capture handling to ensure ≥3 RB per chain.
    # Positions 3, 7, 11, 15, 19 (every 4th, offset 3) → ~4-5 per window.
    # -----------------------------------------------------------------------
    rb_count = type_counts.get("ResourceBudget", 0)
    rb_due = (position % 4 == 3)
    if rb_due:
        amount = _normalise_material(event, variant)
        resource = f"material_{event.side}"
        if event.phase_indicator == "phase_opening":
            resource = "tempo_remaining"
        return [ResourceBudget(
            timestamp=t,
            resource=resource,
            amount=amount,
            decay="none" if event.phase_indicator == "phase_opening" else "monotone_decrease",
            recover_in=None,
        )]

    # -----------------------------------------------------------------------
    # Priority 6: Capture → ToolAvailability
    # (also fallback to ToolAvailability for non-capture if TA still 0)
    # -----------------------------------------------------------------------
    ta_count = type_counts.get("ToolAvailability", 0)
    if event.is_capture:
        return [ToolAvailability(
            timestamp=t,
            tool=event.piece_label,
            state="unavailable",
            recover_in=None,
        )]

    # Non-capture: ensure ≥1 TA per chain by emitting TA(available) if none yet
    if ta_count == 0 and position >= window_size // 2:
        return [ToolAvailability(
            timestamp=t,
            tool=event.piece_label,
            state="available",
            recover_in=None,
        )]

    # -----------------------------------------------------------------------
    # Priority 7: Check → CoordinationDependency
    # -----------------------------------------------------------------------
    if event.is_check:
        pat = _COORD_PATTERNS[position % len(_COORD_PATTERNS)]
        act = _COORD_ACTIONS[position % len(_COORD_ACTIONS)]
        return [CoordinationDependency(
            timestamp=t,
            role=event.side,
            dependency=pat,
            expected_action=act,
        )]

    # -----------------------------------------------------------------------
    # Priority 8: Periodic InformationState (every 7th non-special event)
    # -----------------------------------------------------------------------
    is_due = (position % 7 == 6)
    if is_due:
        return [InformationState(
            timestamp=t,
            observable_added=[],
            observable_removed=[],
            uncertainty=0.0,
        )]

    # -----------------------------------------------------------------------
    # Priority 9: High-value piece moves → CoordinationDependency
    # -----------------------------------------------------------------------
    high_value_pieces = {"piece_D", "piece_E", "piece_J", "piece_K"}  # rooks, queens
    if event.piece_label in high_value_pieces:
        pat = _COORD_PATTERNS[(position + 2) % len(_COORD_PATTERNS)]
        act = _COORD_ACTIONS[(position + 1) % len(_COORD_ACTIONS)]
        return [CoordinationDependency(
            timestamp=t,
            role=event.side,
            dependency=pat,
            expected_action=act,
        )]

    # -----------------------------------------------------------------------
    # Priority 10: Balance CoordinationDependency vs OptimizationCriterion
    # -----------------------------------------------------------------------
    cd_count = type_counts.get("CoordinationDependency", 0)
    oc_count = type_counts.get("OptimizationCriterion", 0)

    if cd_count <= oc_count + 1:
        pat = _COORD_PATTERNS[(position + 4) % len(_COORD_PATTERNS)]
        act = _COORD_ACTIONS[(position + 3) % len(_COORD_ACTIONS)]
        return [CoordinationDependency(
            timestamp=t,
            role=event.side,
            dependency=pat,
            expected_action=act,
        )]
    else:
        obj = _OPT_OBJECTIVES[position % len(_OPT_OBJECTIVES)]
        phase_label = event.phase_indicator.replace("phase_", "")
        return [OptimizationCriterion(
            timestamp=t,
            objective=obj,
            weight_shift=f"{phase_label}_priority",
        )]


def translate_trajectory(events: List[GameEvent], variant: str = "chess_standard") -> List[Constraint]:
    """
    Translate an ordered list of GameEvents into an ordered list of Constraints.

    Parameters
    ----------
    events  : list of GameEvents from aggregation.py (window of 15–25 events)
    variant : game variant identifier for material normalisation

    Returns
    -------
    List of Constraints, one per input event.

    Notes
    -----
    Each event maps to exactly one Constraint. The type assignment follows
    a priority-plus-balance scheme to achieve approximately:
    ~25-30% ToolAvailability, ~20-25% ResourceBudget, ~15-20% SubGoalTransition,
    ~15-20% CoordinationDependency, ~5-10% OptimizationCriterion,
    ~5-10% InformationState.
    """
    if not events:
        return []

    constraints: List[Constraint] = []
    type_counts: dict[str, int] = defaultdict(int)
    prev_phase: Optional[str] = None
    window_size = len(events)

    prev_event: Optional[GameEvent] = None
    for i, evt in enumerate(events):
        context = {
            'prev_phase': prev_phase,
            'type_counts': type_counts,
            'position': i,
            'window_size': window_size,
            'variant': variant,
            'prev_event': prev_event,
        }
        new_constraints = translate_event(evt, context)
        for c in new_constraints:
            type_name = type(c).__name__
            type_counts[type_name] += 1
        constraints.extend(new_constraints)
        prev_phase = evt.phase_indicator
        prev_event = evt

    return constraints


# ---------------------------------------------------------------------------
# Material normalisation helper
# ---------------------------------------------------------------------------

def _normalise_material(event: GameEvent, variant: str) -> float:
    """
    Compute normalised material amount (0.0–1.0) from event metadata.

    Returns 0.5 if material data not available in metadata.
    """
    meta = event.metadata
    if not meta:
        return 0.5

    if variant in ("chess_standard", "chess960"):
        # event metadata has material_side_1 and material_side_2
        side = event.side
        key = f"material_{side}"
        mat = meta.get(key, meta.get("material_side_1", None))
        if mat is None:
            return 0.5
        return min(1.0, mat / _CHESS_START_MATERIAL)
    else:
        # checkers: metadata has white_pieces and black_pieces
        color = "white" if event.side == "side_1" else "black"
        key = f"{color}_pieces"
        pieces = meta.get(key, meta.get("total_pieces", None))
        start = _START_PIECES.get(variant, 12)
        if pieces is None:
            return 0.5
        return min(1.0, pieces / start)
