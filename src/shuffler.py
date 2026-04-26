"""
Shuffler: produces a control-condition shuffled variant for each real chain.

The shuffled chain has its constraints permuted uniformly at random, but
timestamps are re-assigned to preserve monotonic ordering so the shuffle
cannot be detected from timestamp order alone.

Copied verbatim from v2 (domain-blind — no modifications needed).
"""

from __future__ import annotations

import copy
import dataclasses
import random
from typing import Any

from src.translation import Constraint


def _get_timestamps(constraints: list) -> list[int]:
    """Extract ordered timestamps from the original chain (handles both dicts and dataclasses)."""
    result = []
    for c in constraints:
        if isinstance(c, dict):
            result.append(c.get("timestamp", 0))
        else:
            result.append(getattr(c, "timestamp", 0))
    return result


def _set_timestamp(constraint, ts: int):
    """Return a copy of the constraint with the timestamp replaced (handles both formats)."""
    if isinstance(constraint, dict):
        new = dict(constraint)
        new["timestamp"] = ts
        return new
    d = dataclasses.asdict(constraint)
    d["timestamp"] = ts
    return type(constraint)(**d)


def shuffle_chain(chain: dict, seed: int) -> dict:
    """
    Produce one shuffled variant of a real chain.

    Rules:
    - Permute constraints uniformly at random (seeded)
    - Reassign timestamps to preserve monotonic ordering (so shuffled chains
      don't reveal themselves via out-of-order timestamps)
    - Preserve InformationState semantics — the event moves but keeps its content
    - Chain ID: {original_id}_shuffled_{seed}
    - Preserve match_id field
    """
    original_constraints: list[Constraint] = chain["constraints"]

    original_timestamps = _get_timestamps(original_constraints)
    sorted_timestamps = sorted(original_timestamps)

    rng = random.Random(seed)
    perm = list(range(len(original_constraints)))
    rng.shuffle(perm)
    shuffled_constraints = [original_constraints[i] for i in perm]

    reassigned: list[Constraint] = []
    for i, c in enumerate(shuffled_constraints):
        new_ts = sorted_timestamps[i]
        reassigned.append(_set_timestamp(c, new_ts))

    original_id = chain["chain_id"]
    shuffled_chain = dict(chain)
    shuffled_chain["chain_id"] = f"{original_id}_shuffled_{seed}"
    shuffled_chain["match_id"] = chain["match_id"]
    shuffled_chain["constraints"] = reassigned
    if "active_pair_by_step" in chain:
        orig_pairs = chain["active_pair_by_step"]
        shuffled_chain["active_pair_by_step"] = [orig_pairs[i] for i in perm]

    return shuffled_chain
