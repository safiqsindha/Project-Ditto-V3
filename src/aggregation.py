"""
Game event compression / aggregation for chain construction.

Compresses events from a TrajectoryLog into a 15–25 event window
suitable for chain construction and T-code translation.

Strategy:
  1. Divide the trajectory into phase-anchored windows.
  2. Within each candidate window, select events that maximise constraint
     type diversity while staying within [target_min, target_max] length.
  3. Multiple non-overlapping windows can be derived from a single game
     for the 1,200 chains/cell target.

FROZEN at git tag T-code-game-v1.0-frozen alongside translation.py.
"""

from __future__ import annotations

import random
from typing import Optional

from src.translation import GameEvent, TrajectoryLog


# ---------------------------------------------------------------------------
# Window computation
# ---------------------------------------------------------------------------

def compute_windows(
    traj: TrajectoryLog,
    target_min: int = 15,
    target_max: int = 25,
) -> list[tuple[int, int]]:
    """
    Compute all valid (start, end) window index pairs for a trajectory.

    A valid window:
    - Has length [target_min, target_max] in ply indices
    - Spans at least one phase boundary (opening→middlegame or middlegame→endgame)
      OR has enough events if the game is short
    - Does not overlap with previously found windows (step = target_min)

    Parameters
    ----------
    traj       : parsed game trajectory
    target_min : minimum window length (inclusive)
    target_max : maximum window length (inclusive)

    Returns
    -------
    List of (start_idx, end_idx) tuples (end_idx exclusive).
    """
    n = len(traj.events)
    if n < target_min:
        return []

    windows: list[tuple[int, int]] = []
    step = target_min  # non-overlapping stride

    start = 0
    while start + target_min <= n:
        # Prefer windows that span a phase boundary
        end_max = min(start + target_max, n)
        end_min = start + target_min

        # Try to find a phase transition within this window
        best_end = end_max  # default: use full target_max
        for i in range(start, end_max - 1):
            if i + 1 < n and traj.events[i].phase_indicator != traj.events[i + 1].phase_indicator:
                # Found a phase transition; try to capture it
                candidate_end = min(i + target_min // 2, end_max)
                candidate_end = max(candidate_end, end_min)
                best_end = candidate_end
                break

        windows.append((start, best_end))
        start += step

    return windows


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def aggregate_trajectory(
    traj: TrajectoryLog,
    window_start: int = 0,
    window_end: Optional[int] = None,
) -> list[GameEvent]:
    """
    Extract a 15–25 event window from a TrajectoryLog.

    Parameters
    ----------
    traj         : parsed game trajectory
    window_start : first event index (inclusive)
    window_end   : last event index (exclusive); None = end of trajectory

    Returns
    -------
    List of GameEvents in the window (length = min(window, 25) capped).

    Notes
    -----
    - The raw events are returned in order (no merging at this stage).
    - T-code in translation.py processes these events into Constraints.
    - If the window is longer than target_max, it is truncated.
    - If the window is shorter than target_min, the caller should discard it.
    """
    events = traj.events
    n = len(events)

    start = max(0, window_start)
    end = min(n, window_end) if window_end is not None else n

    TARGET_MAX = 25
    # Cap window at target_max
    if end - start > TARGET_MAX:
        end = start + TARGET_MAX

    return events[start:end]


# ---------------------------------------------------------------------------
# High-level: generate all windows from a trajectory
# ---------------------------------------------------------------------------

def extract_all_windows(
    traj: TrajectoryLog,
    target_min: int = 15,
    target_max: int = 25,
) -> list[list[GameEvent]]:
    """
    Generate all valid non-overlapping windows from a single trajectory.

    Returns a list of GameEvent lists, each of length [target_min, target_max].
    Caller passes each list to translate_trajectory() in translation.py.
    """
    windows = compute_windows(traj, target_min=target_min, target_max=target_max)
    result = []
    for start, end in windows:
        window_events = aggregate_trajectory(traj, window_start=start, window_end=end)
        if len(window_events) >= target_min:
            result.append(window_events)
    return result


def sample_window(
    traj: TrajectoryLog,
    target_min: int = 15,
    target_max: int = 25,
    rng: Optional[random.Random] = None,
) -> Optional[list[GameEvent]]:
    """
    Sample one random valid window from a trajectory.

    Returns None if the trajectory is too short for any valid window.
    Used by the chain generation script (Session 7) when sampling one chain per game.
    """
    windows = compute_windows(traj, target_min=target_min, target_max=target_max)
    if not windows:
        return None
    if rng is None:
        rng = random.Random()
    start, end = rng.choice(windows)
    return aggregate_trajectory(traj, window_start=start, window_end=end)
