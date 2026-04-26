"""
Phase A — Step A3: rebuild reference distributions with resource-side-*
downweighting.

Policy (per the Phase A spec):
  1. For each entity E, count how many state signatures have E in their
     top-3. Call this freq(E).
  2. Compute median_non_resource = median over freq(E) for E not matching
     "resource_side_*".
  3. For each resource_side_* entity E with freq(E) > median_non_resource,
     keep E in top-3 of only the top-median_non_resource state signatures
     (ranked by E's per-sig count, descending). Remove E from top-3 of
     the remaining sigs.
  4. Recompute top-3 for each affected state signature based on the
     post-cap counts.

Implementation: rather than mutating the original ReferenceDistribution
(which lives in src/reference.py and is under the T-code freeze), we
build a new distribution by reading the existing one and rewriting its
counts dict. The output is saved as
data/reference_{cell}_downweighted.pkl alongside the unmodified original.

This module does NOT modify src/reference.py.
"""

from __future__ import annotations

import math
import pickle
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.reference import ReferenceDistribution


RESOURCE_SIDE_PATTERN = re.compile(r"^resource_side_")


def _top3_for_sig(action_counts: dict[str, int]) -> list[str]:
    """Return the top-3 actions (by count, descending) for one state sig."""
    sorted_actions = sorted(action_counts.items(), key=lambda x: -x[1])
    return [a for a, _ in sorted_actions[:3]]


def downweight_distribution(dist: ReferenceDistribution) -> tuple[ReferenceDistribution, dict]:
    """
    Apply the resource-side downweighting policy to a reference distribution.

    Returns (new_dist, params_log).
    new_dist : a ReferenceDistribution with modified counts.
    params_log : dict of policy parameters and effects, suitable for
                 saving to results/phase_a/a3_downweight_params.json.
    """
    counts = dist.counts  # {sig: {action: count}}

    # ----- Step 1: cell-level entity → freq (# sigs with E in top-3) -----
    entity_top3_freq: Counter = Counter()
    sig_top3_map: dict[tuple, list[str]] = {}
    for sig, action_counts in counts.items():
        top3 = _top3_for_sig(action_counts)
        sig_top3_map[sig] = top3
        for ent in top3:
            entity_top3_freq[ent] += 1

    # ----- Step 2: median freq of non-resource entities -----
    non_resource_freqs = [
        f for ent, f in entity_top3_freq.items()
        if not RESOURCE_SIDE_PATTERN.match(ent)
    ]
    if non_resource_freqs:
        sorted_freqs = sorted(non_resource_freqs)
        n = len(sorted_freqs)
        # Median (handle even/odd uniformly with statistics-style midpoint)
        if n % 2 == 1:
            median_non_resource = sorted_freqs[n // 2]
        else:
            median_non_resource = (sorted_freqs[n // 2 - 1] + sorted_freqs[n // 2]) / 2
    else:
        median_non_resource = 0
    median_cap = int(math.floor(median_non_resource))
    # Use floor(median) as the integer cap

    # ----- Step 3: identify resource_side_* entities exceeding the cap -----
    resource_entities = {
        ent for ent in entity_top3_freq if RESOURCE_SIDE_PATTERN.match(ent)
    }

    capping_ledger: dict[str, dict] = {}
    # For each resource_side_X entity, find the sigs where it's in top-3,
    # rank them by per-sig count, keep top-`median_cap`, demote in the rest.
    sigs_to_demote: dict[str, set[tuple]] = {}  # entity → set of sigs to demote it from
    for ent in resource_entities:
        original_freq = entity_top3_freq[ent]
        sigs_with_ent = [
            (sig, counts[sig][ent])
            for sig in counts if ent in counts[sig] and ent in sig_top3_map[sig]
        ]
        # Sort by per-sig count, descending; ties broken by sig hash for stability
        sigs_with_ent.sort(key=lambda x: (-x[1], hash(x[0])))
        if original_freq > median_cap:
            keep = set(sig for sig, _ in sigs_with_ent[:median_cap])
            demote = set(sig for sig, _ in sigs_with_ent[median_cap:])
            sigs_to_demote[ent] = demote
            capping_ledger[ent] = {
                "original_freq": original_freq,
                "capped_freq": len(keep),
                "demoted_in_n_sigs": len(demote),
            }
        else:
            sigs_to_demote[ent] = set()
            capping_ledger[ent] = {
                "original_freq": original_freq,
                "capped_freq": original_freq,
                "demoted_in_n_sigs": 0,
            }

    # ----- Step 4: build new counts with demoted entries removed ---------
    new_counts: dict[tuple, dict[str, int]] = {}
    sigs_with_changed_top3 = 0
    sigs_with_empty_top3 = 0

    for sig, action_counts in counts.items():
        modified = dict(action_counts)
        any_demoted = False
        for ent in resource_entities:
            if sig in sigs_to_demote.get(ent, set()):
                if ent in modified:
                    del modified[ent]
                    any_demoted = True

        if not modified:
            sigs_with_empty_top3 += 1
            # Don't write this sig — it has nothing left
            continue

        new_counts[sig] = modified

        if any_demoted:
            # Did the top-3 actually change?
            new_top3 = _top3_for_sig(modified)
            if new_top3 != sig_top3_map[sig]:
                sigs_with_changed_top3 += 1

    new_dist = ReferenceDistribution(
        source=dist.source,
        counts=new_counts,
        total_chains=dist.total_chains,
        coverage_stats=dist.coverage_stats,
    )

    params_log = {
        "median_non_resource_freq": median_non_resource,
        "median_cap_floored": median_cap,
        "non_resource_entities_count": len(non_resource_freqs),
        "resource_entities_count": len(resource_entities),
        "capping_ledger": capping_ledger,
        "sigs_with_changed_top3": sigs_with_changed_top3,
        "sigs_dropped_empty_top3": sigs_with_empty_top3,
        "n_sigs_before": len(counts),
        "n_sigs_after": len(new_counts),
    }

    return new_dist, params_log


def main(cells: list[str]) -> int:
    out_dir = PROJECT_ROOT / "data"
    params_summary: dict = {"per_cell": {}}

    for cell in cells:
        original_path = out_dir / f"reference_{cell}.pkl"
        if not original_path.exists():
            print(f"  ❌ missing: {original_path}")
            continue
        original_dist = ReferenceDistribution.load(original_path)
        new_dist, params = downweight_distribution(original_dist)

        new_path = out_dir / f"reference_{cell}_downweighted.pkl"
        new_dist.save(new_path)

        params_summary["per_cell"][cell] = params
        n_top3_changed = params["sigs_with_changed_top3"]
        n_drop = params["sigs_dropped_empty_top3"]
        cap = params["median_cap_floored"]
        print(f"{cell:<22s}: median_cap={cap}, "
              f"top3_changed={n_top3_changed}/{params['n_sigs_before']}, "
              f"dropped_empty={n_drop}")
        if n_drop > 0:
            print(f"  ⚠ {n_drop} sigs dropped due to empty top-3 — review")

    out_json = PROJECT_ROOT / "results" / "phase_a" / "a3_downweight_params.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(__import__("json").dumps(params_summary, indent=2, default=str))
    print(f"\nParams → {out_json.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    main(["chess_standard", "chess960", "checkers_american", "draughts_intl"])
