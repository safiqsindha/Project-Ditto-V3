"""
Session 8: Build per-cell reference distributions and check coverage.

For each cell:
  1. Load all real chain JSONL files from chains/real/{cell}/
  2. Build ReferenceDistribution from constraints + focal_action per chain
  3. Save to data/reference_{cell}.pkl
  4. Coverage check: ≥90% of chains' state signatures have non-max-backoff match

Gate 8 requirement (SPEC.md §6): non_max_backoff_fraction ≥ 0.90 per cell.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.reference import ReferenceDistribution


CELLS = ["chess_standard", "chess960", "checkers_american", "draughts_intl"]
COVERAGE_TARGET = 0.90


def _load_chains_dir(cell_dir: Path) -> list[dict]:
    chains = []
    for path in sorted(cell_dir.glob("*.jsonl")):
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                chains.append(json.loads(line))
    return chains


def main() -> int:
    print("Session 8 — Reference distribution build + coverage check\n")
    out_dir = PROJECT_ROOT / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary: dict = {"cells": {}, "gate8_passed": True}

    for cell in CELLS:
        print(f"=== {cell} ===")
        cell_dir = PROJECT_ROOT / "chains" / "real" / cell
        if not cell_dir.exists():
            print(f"  ❌ missing directory: {cell_dir}")
            summary["gate8_passed"] = False
            continue

        chains = _load_chains_dir(cell_dir)
        print(f"  Loaded {len(chains)} real chains")

        # Build
        dist = ReferenceDistribution.build_from_chains(chains, source=cell)
        out_path = out_dir / f"reference_{cell}.pkl"
        dist.save(out_path)
        print(f"  Built distribution: {len(dist.counts)} unique level-0 state sigs, "
              f"{dist.total_chains} chains contributed")
        print(f"  Saved → {out_path.relative_to(PROJECT_ROOT)}")

        # Coverage check
        cov = dist.check_coverage(chains, target=COVERAGE_TARGET)
        non_max = cov["non_max_backoff_fraction"]
        passed  = cov["passes"]
        mark = "✅" if passed else "❌"
        print(f"  Coverage:")
        print(f"    Level breakdown (chains with match at level k):")
        for level, count in sorted(cov["level_counts"].items()):
            label = ["full", "drop entity", "drop bracket", "max-backoff"][level]
            print(f"      level {level} ({label:<14s}): {count:5d}")
        print(f"    non_max_backoff_fraction: {non_max:.4f}  (target ≥ {COVERAGE_TARGET}) {mark}")

        summary["cells"][cell] = {
            "real_chains": len(chains),
            "unique_state_sigs": len(dist.counts),
            "total_chains_contributing": dist.total_chains,
            "level_counts": cov["level_counts"],
            "non_max_backoff_fraction": non_max,
            "passes": passed,
            "reference_path": str(out_path.relative_to(PROJECT_ROOT)),
        }
        if not passed:
            summary["gate8_passed"] = False

        print()

    # Summary
    print("=" * 60)
    print("GATE 8 SUMMARY")
    print("=" * 60)
    for cell, s in summary["cells"].items():
        mark = "✅" if s["passes"] else "❌"
        print(f"  {mark}  {cell:<22s}: {s['non_max_backoff_fraction']:.4f}  "
              f"({s['unique_state_sigs']} unique state sigs)")

    overall_mark = "✅" if summary["gate8_passed"] else "❌"
    print(f"\n{overall_mark} Gate 8: {'PASSED' if summary['gate8_passed'] else 'FAILED'} "
          f"(target ≥{COVERAGE_TARGET} on every cell)")

    summary_path = PROJECT_ROOT / "data" / "reference_build_summary.json"
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nSummary → {summary_path.relative_to(PROJECT_ROOT)}")

    return 0 if summary["gate8_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
