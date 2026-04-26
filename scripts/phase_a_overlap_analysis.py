"""
Phase A — Step A2: overlap between anti-adjacency shuffles and existing
model responses (informational).

For each new anti-adjacency-shuffled chain, compute a
constraint-sequence hash. Check if that hash matches any chain in
results/raw/phase1/{cell}/ (which has chains identifiable by chain_id
embedded in the result filename).

Reports:
  - total new shuffled chains
  - count whose chain_id matches an existing model response
  - count whose constraint-sequence hash matches a different existing chain
    (i.e., we accidentally produced an existing permutation)
  - percent overlap

Honest expectation: near-zero overlap on chain_id (since new chain_ids
have "_aa" suffix). Hash overlap could be non-zero but small.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

CELLS = ("chess_standard", "chess960", "checkers_american", "draughts_intl")


def constraint_sequence_hash(constraints: list[dict]) -> str:
    """Stable hash of a constraint sequence (preserves order, content)."""
    # Use type + entity-bearing fields so that two different shuffles of
    # the same constraints produce different hashes (we want order-sensitive).
    parts = []
    for c in constraints:
        # Drop timestamp from hash (since shuffler reassigns timestamps)
        c_no_ts = {k: v for k, v in c.items() if k != "timestamp"}
        parts.append(json.dumps(c_no_ts, sort_keys=True))
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()


def main() -> int:
    summary: dict = {"per_cell": {}}

    for cell in CELLS:
        # Build a hash table of EXISTING shuffled chains (the ones that have
        # been scored against the model)
        existing_shuf_dir = PROJECT_ROOT / "chains" / "shuffled" / cell
        existing_hashes: dict[str, str] = {}  # hash -> chain_id
        for path in existing_shuf_dir.glob("*.jsonl"):
            chain = json.loads(path.read_text())
            h = constraint_sequence_hash(chain["constraints"])
            existing_hashes[h] = chain["chain_id"]

        # Walk new anti-adjacency shuffles
        new_shuf_dir = PROJECT_ROOT / "chains" / "shuffled_anti_adjacency" / cell
        total_new = 0
        chain_id_collisions = 0
        hash_collisions = 0
        hash_collision_examples = []
        existing_responses_dir = PROJECT_ROOT / "results" / "raw" / "phase1" / cell

        for path in new_shuf_dir.glob("*.jsonl"):
            chain = json.loads(path.read_text())
            total_new += 1
            cid = chain["chain_id"]

            # Chain ID collision: do we have a model response file with this id?
            # (Should be 0 since new ids have "_aa" suffix.)
            if cid in {"" }:  # placeholder
                pass
            # More robust: check if any response file exists with this chain_id
            # Build response file path pattern.
            response_path_pattern = f"haiku_42_{cid}_T0.0.json"
            if (existing_responses_dir / response_path_pattern).exists():
                chain_id_collisions += 1

            # Constraint-sequence hash collision with existing shuffled chains
            h = constraint_sequence_hash(chain["constraints"])
            if h in existing_hashes:
                hash_collisions += 1
                if len(hash_collision_examples) < 5:
                    hash_collision_examples.append({
                        "new_chain_id": cid,
                        "existing_chain_id": existing_hashes[h],
                    })

        chain_id_overlap_pct = (chain_id_collisions / total_new * 100) if total_new else 0.0
        hash_overlap_pct = (hash_collisions / total_new * 100) if total_new else 0.0

        print(f"{cell:<22s}: total_new={total_new:5d}  "
              f"chain_id_overlap={chain_id_collisions} ({chain_id_overlap_pct:.2f}%)  "
              f"hash_overlap={hash_collisions} ({hash_overlap_pct:.2f}%)")
        if hash_overlap_pct > 5.0:
            print(f"  ⚠ hash overlap >5% — unexpected; investigate")

        summary["per_cell"][cell] = {
            "total_new_shuffled": total_new,
            "chain_id_overlap": chain_id_collisions,
            "chain_id_overlap_pct": round(chain_id_overlap_pct, 4),
            "hash_overlap": hash_collisions,
            "hash_overlap_pct": round(hash_overlap_pct, 4),
            "hash_collision_examples": hash_collision_examples,
        }

    out_path = PROJECT_ROOT / "results" / "phase_a" / "a2_overlap.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nSummary → {out_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
