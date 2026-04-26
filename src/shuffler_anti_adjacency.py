"""
Phase A — anti-adjacency shuffler (Mechanism 1 control).

Mirrors src/shuffler.py's interface but adds the constraint:
    shuffled_constraints[K-1].entity != shuffled_constraints[K].entity
where K = cutoff_k. This prevents the random-permutation artifact whereby
~13% of shuffled chains have target_entity == last_shown_entity (vs 0.33%
in real chains by T-code design).

Phase A uses these chains for structural analysis only — they are NOT
re-evaluated by the model in Phase A (no API budget). They exist to
support Phase B's potential re-evaluation under explicit author approval.

Design notes
------------
- Same shuffle seeds (42, 1337, 7919) as src/shuffler.py for traceability.
- Up to MAX_RETRIES attempts to find a permutation satisfying the
  anti-adjacency constraint; chains that hit the retry cap are excluded
  and logged.
- Anti-adjacency is checked on the EXTRACTED entity (per
  reference.extract_entity_from_constraint), matching the mechanism
  diagnosis (echo of last-shown entity).
- The shuffler does NOT modify constraints' content, only their order.
  Timestamps are reassigned to preserve monotonic ordering, identical
  to src/shuffler.py.

Created on a parallel branch (claude/phase-a-verification). Not merged
into main; src/shuffler.py is unchanged and remains under T-code freeze.
"""

from __future__ import annotations

import dataclasses
import random
from typing import Any

from src.translation import Constraint
from src.reference import extract_entity_from_constraint


MAX_RETRIES: int = 100


def _get_timestamps(constraints: list) -> list[int]:
    out = []
    for c in constraints:
        if isinstance(c, dict):
            out.append(c.get("timestamp", 0))
        else:
            out.append(getattr(c, "timestamp", 0))
    return out


def _set_timestamp(constraint, ts: int):
    if isinstance(constraint, dict):
        new = dict(constraint)
        new["timestamp"] = ts
        return new
    d = dataclasses.asdict(constraint)
    d["timestamp"] = ts
    return type(constraint)(**d)


def _entity_of(c) -> str | None:
    """Wrap extract_entity_from_constraint to handle both dataclass + dict."""
    if isinstance(c, dict):
        return extract_entity_from_constraint(c)
    return extract_entity_from_constraint(dataclasses.asdict(c))


def shuffle_chain_anti_adjacency(
    chain: dict,
    seed: int,
    cutoff_k: int | None = None,
    max_retries: int = MAX_RETRIES,
) -> dict | None:
    """
    Produce a shuffled chain whose constraints[cutoff_k - 1] and
    constraints[cutoff_k] have DIFFERENT extracted entities.

    Returns None if no valid permutation is found within max_retries.

    Parameters
    ----------
    chain : dict with 'constraints', 'chain_id', 'match_id'
    seed  : shuffle seed (42, 1337, 7919) for traceability
    cutoff_k : the cutoff position (K). Defaults to chain['cutoff_k']
               or len(constraints) // 2 if absent.
    max_retries : number of permutation attempts before giving up
    """
    constraints = chain["constraints"]
    n = len(constraints)
    if n < 2:
        return None

    if cutoff_k is None:
        cutoff_k = chain.get("cutoff_k") or max(1, n // 2)
    if cutoff_k <= 0 or cutoff_k >= n:
        return None

    original_timestamps = _get_timestamps(constraints)
    sorted_timestamps = sorted(original_timestamps)

    rng = random.Random(seed)
    perm: list[int] | None = None

    for attempt in range(max_retries):
        candidate = list(range(n))
        rng.shuffle(candidate)

        c_at_K_minus_1 = constraints[candidate[cutoff_k - 1]]
        c_at_K         = constraints[candidate[cutoff_k]]
        ent_minus_1 = _entity_of(c_at_K_minus_1)
        ent_K       = _entity_of(c_at_K)

        # Constraint: target's entity must differ from last-shown's entity.
        # Treat None entities as different from any other entity (including
        # other Nones), to avoid two consecutive InformationStates trivially
        # passing as "different" in some edge case.
        if ent_minus_1 != ent_K and ent_minus_1 is not None and ent_K is not None:
            perm = candidate
            break
        # Allow if either is None and the other is not — that's already
        # not the echo failure mode we're controlling for.
        if (ent_minus_1 is None) != (ent_K is None):
            perm = candidate
            break

    if perm is None:
        return None

    shuffled_constraints = [constraints[i] for i in perm]
    reassigned: list = []
    for i, c in enumerate(shuffled_constraints):
        new_ts = sorted_timestamps[i]
        reassigned.append(_set_timestamp(c, new_ts))

    original_id = chain["chain_id"]
    out = dict(chain)
    out["chain_id"] = f"{original_id}_shuffled_{seed}_aa"
    out["match_id"] = chain.get("match_id", original_id)
    out["constraints"] = reassigned
    if "active_pair_by_step" in chain:
        orig_pairs = chain["active_pair_by_step"]
        out["active_pair_by_step"] = [orig_pairs[i] for i in perm]
    return out
