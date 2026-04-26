"""
Phase A — Step A1: produce anti-adjacency shuffled chains for all 4 cells.

Reads existing real chains from chains/real/{cell}/, applies the
anti-adjacency constraint via shuffle_chain_anti_adjacency, writes
output to chains/shuffled_anti_adjacency/{cell}/.

Logs per-cell stats to results/phase_a/a1_shuffle_summary.json:
  - total_real
  - shuffled_generated (across 3 seeds, so up to 3× total_real)
  - retry_cap_exclusions (chains that couldn't be shuffled)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.shuffler_anti_adjacency import shuffle_chain_anti_adjacency

SEEDS = (42, 1337, 7919)
CELLS = ("chess_standard", "chess960", "checkers_american", "draughts_intl")


def main() -> int:
    summary: dict = {"per_cell": {}}
    out_root = PROJECT_ROOT / "chains" / "shuffled_anti_adjacency"

    for cell in CELLS:
        cell_dir_in = PROJECT_ROOT / "chains" / "real" / cell
        cell_dir_out = out_root / cell
        cell_dir_out.mkdir(parents=True, exist_ok=True)

        total_real = 0
        shuffled_generated = 0
        retry_cap_exclusions = []

        for chain_path in sorted(cell_dir_in.glob("*.jsonl")):
            chain = json.loads(chain_path.read_text())
            total_real += 1
            for seed in SEEDS:
                shuffled = shuffle_chain_anti_adjacency(chain, seed)
                if shuffled is None:
                    retry_cap_exclusions.append({
                        "chain_id": chain["chain_id"],
                        "seed": seed,
                    })
                    continue
                # Write as JSONL (one chain per file, matches existing convention)
                out_path = cell_dir_out / f"{shuffled['chain_id']}.jsonl"
                out_path.write_text(json.dumps(shuffled, ensure_ascii=False) + "\n")
                shuffled_generated += 1

        n_retried = len(retry_cap_exclusions)
        max_possible = total_real * len(SEEDS)
        retry_pct = (n_retried / max_possible * 100) if max_possible else 0.0
        print(f"{cell:<22s}: real={total_real:5d}  "
              f"shuffled_generated={shuffled_generated:5d}  "
              f"retry_cap_excluded={n_retried} ({retry_pct:.2f}% of attempts)")
        if retry_pct > 5.0:
            print(f"  ⚠ retry-cap rate >5% — anti-adjacency constraint may be too tight for this cell")

        summary["per_cell"][cell] = {
            "total_real": total_real,
            "shuffled_generated": shuffled_generated,
            "max_possible": max_possible,
            "retry_cap_exclusions": n_retried,
            "retry_cap_pct": round(retry_pct, 4),
            "exclusions_sample": retry_cap_exclusions[:10],
        }

    # Write summary
    out_path = PROJECT_ROOT / "results" / "phase_a" / "a1_shuffle_summary.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nSummary → {out_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
