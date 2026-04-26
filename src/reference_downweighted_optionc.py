"""
Phase A — Option C cap policy (post-hoc methodology investigation).

Less destructive alternative to Option B (which dropped state sigs whose
top-3 became empty after capping):

For each state sig:
  1. Identify resource_side_* entries vs non-resource entries
  2. If sig has ANY non-resource entries:
       cap each resource_side_* entity's count at the highest count
       among non-resource entities at that sig
       (preserves resource entries but no longer lets them dominate)
  3. If sig has ONLY resource entries:
       leave the sig alone (no cap; preserve the sig in level 0)
  4. Recompute top-3 with ties broken in favor of non-resource entities

Effects vs Option B:
  - No empty top-3 sigs → no backoff-level inflation for chains landing
    on previously-dropped sigs
  - Resource entities still appear in top-3 where they're empirically
    dominant, just not monopolizing the slots
  - Should produce smaller backoff differential between real and shuffled
    chains than Option B

This module does NOT modify src/reference.py. It builds a parallel
reference distribution saved as data/reference_{cell}_downweighted_c.pkl.

NOTE: this is post-hoc investigation, NOT a Phase A retry. The
pre-committed Phase A criterion (chess_standard gap ≥ +0.02 under
Option B) remains failed regardless of what Option C produces.
"""

from __future__ import annotations

import json
import pickle
import re
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.reference import ReferenceDistribution


RESOURCE_SIDE_PATTERN = re.compile(r"^resource_side_")


def downweight_option_c(dist: ReferenceDistribution) -> tuple[ReferenceDistribution, dict]:
    """
    Apply per-sig cap: resource_side_* count capped at max non-resource
    count within each sig. If sig has no non-resource entries, leave it.

    Returns (new_dist, params_log).
    """
    counts = dist.counts  # {sig: {entity: count}}

    new_counts: dict[tuple, dict[str, int]] = {}
    sigs_with_resource_capped = 0
    sigs_no_capping_needed = 0
    sigs_resource_only = 0  # sigs with no non-resource entities (preserved unchanged)
    total_sigs = len(counts)
    sigs_with_top3_changed = 0

    def top3_of(action_counts):
        return sorted(action_counts.items(), key=lambda x: -x[1])[:3]

    for sig, action_counts in counts.items():
        original_top3 = [a for a, _ in top3_of(action_counts)]

        resource_entries = {
            e: c for e, c in action_counts.items()
            if RESOURCE_SIDE_PATTERN.match(e)
        }
        non_resource_entries = {
            e: c for e, c in action_counts.items()
            if not RESOURCE_SIDE_PATTERN.match(e)
        }

        if not non_resource_entries:
            # No non-resource alternative — preserve the sig unchanged
            new_counts[sig] = dict(action_counts)
            sigs_resource_only += 1
            continue

        if not resource_entries:
            # No resource entries to cap — passthrough
            new_counts[sig] = dict(action_counts)
            sigs_no_capping_needed += 1
            continue

        max_non_resource_count = max(non_resource_entries.values())
        # Cap STRICTLY LESS than max non-resource so non-resource wins ties.
        # If cap would be ≤ 0, drop the resource entity entirely.
        cap_value = max_non_resource_count - 1
        modified = {}
        any_capped = False

        for ent, cnt in action_counts.items():
            if RESOURCE_SIDE_PATTERN.match(ent):
                if cnt > cap_value:
                    if cap_value <= 0:
                        # Drop this resource entity (it would rank below non-resource)
                        any_capped = True
                        continue
                    modified[ent] = cap_value
                    any_capped = True
                else:
                    modified[ent] = cnt
            else:
                modified[ent] = cnt

        new_counts[sig] = modified
        if any_capped:
            sigs_with_resource_capped += 1
            new_top3 = [a for a, _ in top3_of(modified)]
            if set(new_top3) != set(original_top3):
                sigs_with_top3_changed += 1
        else:
            sigs_no_capping_needed += 1

    new_dist = ReferenceDistribution(
        source=dist.source,
        counts=new_counts,
        total_chains=dist.total_chains,
        coverage_stats=dist.coverage_stats,
    )

    params = {
        "policy": "Option C — per-sig cap to max non-resource count; preserve resource-only sigs",
        "n_sigs_total": total_sigs,
        "sigs_with_resource_capped": sigs_with_resource_capped,
        "sigs_no_capping_needed": sigs_no_capping_needed,
        "sigs_resource_only_preserved": sigs_resource_only,
        "sigs_with_top3_changed": sigs_with_top3_changed,
        "sigs_dropped_empty": 0,  # Option C never drops sigs
    }
    return new_dist, params


def main() -> int:
    out_dir = PROJECT_ROOT / "data"
    summary: dict = {"policy": "Option C", "per_cell": {}}

    cells = ["chess_standard", "chess960", "checkers_american", "draughts_intl"]
    for cell in cells:
        original = ReferenceDistribution.load(out_dir / f"reference_{cell}.pkl")
        new_dist, params = downweight_option_c(original)
        new_dist.save(out_dir / f"reference_{cell}_downweighted_c.pkl")
        summary["per_cell"][cell] = params
        print(f"{cell:<22s}: total={params['n_sigs_total']}, "
              f"capped={params['sigs_with_resource_capped']}, "
              f"top3_changed={params['sigs_with_top3_changed']}, "
              f"resource_only_preserved={params['sigs_resource_only_preserved']}, "
              f"dropped_empty={params['sigs_dropped_empty']}")

    out_path = PROJECT_ROOT / "results" / "phase_a" / "option_c_params.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nParams → {out_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
