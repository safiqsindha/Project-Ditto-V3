"""
Session 9: Dry-run sweep through Anthropic Batches API.

Runs 8 batch invocations:
  4 cells × {real chains, shuffled chains}
each with:
  - 50 chains per directory
  - All 3 EVAL_CONFIGS (T=0.0/seed=42, T=0.5/seed=1337, T=0.5/seed=7919)
Total: 50 × 8 × 3 = 1,200 API calls (Haiku, batch-discounted).

Estimated cost: ~$0.40
Estimated wall time: 5–60 minutes (depends on Anthropic batch queue).

Output:
  results/raw/dryrun/{cell}/*.json     — raw model responses
  results/blinded/*.json                — blinded mirrors (chain_id, response)
  results/dryrun_summary.json           — per-invocation stats
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load API key with explicit path + override (sandbox-quirk-resistant)
from dotenv import load_dotenv
load_dotenv(dotenv_path=str(PROJECT_ROOT / ".env"), override=True)

import os
assert os.environ.get("ANTHROPIC_API_KEY"), "ANTHROPIC_API_KEY not loaded"

from src.runner import run_batch, EVAL_CONFIGS, SOURCES

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL = "haiku"               # Phase 1 model — Sonnet runs only after gate
CHAINS_PER_DIR = 50           # Per-direction sample size (real or shuffled)
OUT_DIR = PROJECT_ROOT / "results" / "raw" / "dryrun"


def main() -> int:
    invocations = []
    for cell in SOURCES:
        for kind in ("real", "shuffled"):
            invocations.append({
                "cell": cell,
                "kind": kind,
                "chains_dir": PROJECT_ROOT / "chains" / kind / cell,
            })

    print(f"Session 9 — Dry-run sweep")
    print(f"  Model:           {MODEL}")
    print(f"  Invocations:     {len(invocations)}  ({len(SOURCES)} cells × 2 directions)")
    print(f"  Chains per dir:  {CHAINS_PER_DIR}")
    print(f"  Configs/chain:   {len(EVAL_CONFIGS)}  (T=0.0 seed=42, T=0.5 seed=1337, T=0.5 seed=7919)")
    print(f"  Total API calls: {CHAINS_PER_DIR * len(invocations) * len(EVAL_CONFIGS)}")
    print(f"  Est. cost:       ~$0.40 (Haiku, batch-discounted)")
    print(f"  Output:          {OUT_DIR.relative_to(PROJECT_ROOT)}")
    print()

    summary: dict = {"invocations": [], "totals": {}}
    overall_t0 = time.time()

    for i, inv in enumerate(invocations, 1):
        cell = inv["cell"]
        kind = inv["kind"]
        chains_dir = inv["chains_dir"]
        invocation_label = f"[{i}/{len(invocations)}] {cell} ({kind})"

        if not chains_dir.exists():
            print(f"{invocation_label} ❌ chains_dir missing: {chains_dir}")
            summary["invocations"].append({
                "cell": cell, "kind": kind, "error": "missing chains_dir"
            })
            continue

        n_files = len(list(chains_dir.glob("*.jsonl")))
        if n_files < CHAINS_PER_DIR:
            print(f"{invocation_label} ⚠ only {n_files} chains available (need {CHAINS_PER_DIR})")

        print(f"{invocation_label} submitting batch ...")
        t0 = time.time()
        try:
            result = run_batch(
                chains_dir=chains_dir,
                source=cell,                 # cell name (runner uses for output dir)
                model_name=MODEL,
                output_dir=OUT_DIR,           # results/raw/dryrun
                configs=EVAL_CONFIGS,
                n=CHAINS_PER_DIR,
            )
        except Exception as exc:
            print(f"{invocation_label} ❌ exception: {exc}")
            summary["invocations"].append({
                "cell": cell, "kind": kind, "error": str(exc)
            })
            continue

        elapsed = time.time() - t0
        print(f"{invocation_label} ✅ submitted={result.get('submitted',0)}, "
              f"completed={result.get('completed',0)}, errors={result.get('errors',0)}  "
              f"({elapsed:.0f}s)")
        summary["invocations"].append({
            "cell": cell, "kind": kind,
            **result,
            "elapsed_seconds": round(elapsed, 1),
        })

    overall_elapsed = time.time() - overall_t0

    # Aggregate totals
    submitted = sum(s.get("submitted", 0) for s in summary["invocations"])
    completed = sum(s.get("completed", 0) for s in summary["invocations"])
    errors    = sum(s.get("errors", 0)    for s in summary["invocations"])
    summary["totals"] = {
        "submitted": submitted,
        "completed": completed,
        "errors":    errors,
        "wall_time_seconds": round(overall_elapsed, 1),
    }

    print()
    print("=" * 60)
    print("DRY-RUN SUMMARY")
    print("=" * 60)
    print(f"  Total submitted:  {submitted}")
    print(f"  Total completed:  {completed}")
    print(f"  Total errors:     {errors}")
    print(f"  Wall time:        {overall_elapsed:.0f}s ({overall_elapsed/60:.1f}min)")

    summary_path = PROJECT_ROOT / "results" / "dryrun_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nSummary → {summary_path.relative_to(PROJECT_ROOT)}")

    expected_calls = CHAINS_PER_DIR * len(invocations) * len(EVAL_CONFIGS)
    success = (
        submitted == expected_calls
        and completed == submitted
        and errors == 0
    )
    if success:
        print("\n✅ Dry-run COMPLETE — pipeline ready for Phase 1.")
        return 0
    print(f"\n⚠ Dry-run incomplete: expected {expected_calls} submissions, "
          f"got {submitted} submitted, {completed} completed, {errors} errors.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
