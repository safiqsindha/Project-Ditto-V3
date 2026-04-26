"""
Game event compression / aggregation (stub — implementation in Session 5).

Compresses consecutive same-phase events from a TrajectoryLog into a
15–25 event window suitable for chain construction.

Design notes (to be finalized in Session 5):
  - Sliding window over game moves (anchored to phase boundaries)
  - Consecutive events in the same phase and with the same constraint type
    may be merged (e.g. multiple ResourceBudget events in the same phase
    are bucketed into one summary event)
  - Target window: 15–25 constraints post-aggregation (SPEC §Chain definition)

FROZEN at git tag T-code-game-v1.0-frozen alongside translation.py.
"""

from __future__ import annotations

from src.translation import GameEvent, TrajectoryLog, Constraint


def aggregate_trajectory(
    traj: TrajectoryLog,
    window_start: int = 0,
    window_end: int | None = None,
) -> list[GameEvent]:
    """
    Extract and compress a 15–25 event window from a TrajectoryLog.

    Parameters
    ----------
    traj         : parsed game trajectory
    window_start : first move index (inclusive)
    window_end   : last move index (exclusive); None = end of trajectory

    Returns
    -------
    Compressed list of GameEvents within target length range.

    Implementation deferred to Session 5.
    """
    raise NotImplementedError(
        "aggregate_trajectory is a stub — implement in Session 5. "
        "See SPEC.md §Chain Construction for window and length targets."
    )


def compute_windows(
    traj: TrajectoryLog,
    target_min: int = 15,
    target_max: int = 25,
) -> list[tuple[int, int]]:
    """
    Compute all valid (start, end) window index pairs for a trajectory.

    Each window should yield a chain of length [target_min, target_max]
    after aggregation and translation.

    Implementation deferred to Session 5.
    """
    raise NotImplementedError(
        "compute_windows is a stub — implement in Session 5."
    )
