"""
Session 10: Phase 1 Haiku full evaluation.

8 batch invocations (4 cells × {real, shuffled}):
  Real per cell:     1,200 chains × 3 EVAL_CONFIGS = 3,600 calls
  Shuffled per cell: 3,600 chains × 3 EVAL_CONFIGS = 10,800 calls
  Total per cell:    14,400 calls
  GRAND TOTAL:       4 × 14,400 = 57,600 API calls (Haiku, batch-discounted)

Each shuffled invocation exceeds the Anthropic batch limit of 10,000 requests
per batch; runner._MAX_BATCH_SIZE auto-chunks them into multiple batches.

Estimated cost: $60-120 (Haiku, with 50% Batches API discount per SPEC §7).
Estimated wall time: 4-24 hours (Anthropic batch queue dependent).

Output:
  results/raw/phase1/{cell}/*.json     — 57,600 raw response files
  results/blinded/*.json                — 19,200 unique chain×cutoff blinded mirrors
  results/phase1_summary.json           — per-invocation stats

Pre-launch checks:
  1. Verify all 4 cells have 1,200 real + 3,600 shuffled chain files
  2. Verify .env loads ANTHROPIC_API_KEY
  3. Print cost estimate banner (5s pause for confirmation)
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Sandbox-quirk-resistant env load
from dotenv import load_dotenv
load_dotenv(dotenv_path=str(PROJECT_ROOT / ".env"), override=True)
assert os.environ.get("ANTHROPIC_API_KEY"), "ANTHROPIC_API_KEY not loaded — check .env"

from src.runner import run_batch, EVAL_CONFIGS, SOURCES

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL = "haiku"               # Phase 1 model — Sonnet (Phase 2) only after gate review
OUT_DIR = PROJECT_ROOT / "results" / "raw" / "phase1"
CONFIRMATION_PAUSE_SECONDS = 5  # let the human Ctrl-C if something looks wrong


def _verify_chain_inventory() -> dict[tuple[str, str], int]:
    """Verify all 4 cells have the expected real + shuffled chain files."""
    counts: dict[tuple[str, str], int] = {}
    for cell in SOURCES:
        for kind, expected in (("real", 1200), ("shuffled", 3600)):
            cell_dir = PROJECT_ROOT / "chains" / kind / cell
            if not cell_dir.exists():
                raise SystemExit(f"❌ chains_dir missing: {cell_dir}")
            n = len(list(cell_dir.glob("*.jsonl")))
            counts[(cell, kind)] = n
            if n != expected:
                raise SystemExit(
                    f"❌ {cell}/{kind}: found {n} chains, expected {expected}"
                )
    return counts


def _archive_existing_output() -> Path | None:
    """Move any existing results/raw/phase1/ to a timestamped archive dir.

    Returns the archive path if archive happened, None otherwise.
    Prevents partial overwrite if a re-run is interrupted: existing output
    is preserved instead of being merged file-by-file with new output.
    """
    if not OUT_DIR.exists() or not any(OUT_DIR.iterdir()):
        return None
    archive_dir = OUT_DIR.parent / f"phase1_archive_{int(time.time())}"
    OUT_DIR.rename(archive_dir)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    return archive_dir


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="scripts.run_phase1")
    parser.add_argument(
        "--archive", action="store_true",
        help="Move existing results/raw/phase1/ to a timestamped archive dir "
             "before launching. Safer for re-runs (prevents partial overwrite).",
    )
    args = parser.parse_args()

    # ---- Pre-flight inventory ---------------------------------------------
    print("Session 10 — Phase 1 Haiku full evaluation\n")

    if args.archive:
        archive = _archive_existing_output()
        if archive:
            print(f"[archive] previous output → {archive.relative_to(PROJECT_ROOT)}\n")
        else:
            print("[archive] no existing output to archive\n")

    print("Verifying chain inventory ...")
    counts = _verify_chain_inventory()
    total_calls = sum(counts.values()) * len(EVAL_CONFIGS)
    for (cell, kind), n in sorted(counts.items()):
        print(f"  ✅ {cell}/{kind:<8s}: {n:5d} chains")

    # ---- Cost banner ------------------------------------------------------
    print()
    print("=" * 60)
    print("LAUNCH SUMMARY")
    print("=" * 60)
    print(f"  Model:           {MODEL}")
    print(f"  Cells:           {len(SOURCES)} (chess_standard, chess960,")
    print(f"                       checkers_american, draughts_intl)")
    print(f"  Configs/chain:   {len(EVAL_CONFIGS)} (T=0.0/seed=42, T=0.5/seed=1337,")
    print(f"                       T=0.5/seed=7919)")
    print(f"  Total chains:    {sum(counts.values())} (4,800 real + 14,400 shuffled)")
    print(f"  Total API calls: {total_calls:,}")
    print(f"  Mode:            batch (50% discount)")
    print(f"  Est. cost:       $60–120")
    print(f"  Est. wall time:  4–24 hours (Anthropic queue dependent)")
    print(f"  Output dir:      {OUT_DIR.relative_to(PROJECT_ROOT)}")
    print("=" * 60)
    print(f"  Pausing {CONFIRMATION_PAUSE_SECONDS}s — Ctrl-C now to abort, or wait to launch.")
    print("=" * 60)
    for s in range(CONFIRMATION_PAUSE_SECONDS, 0, -1):
        print(f"  {s} ...", flush=True)
        time.sleep(1)
    print("  LAUNCHING.\n")

    # ---- Launch sequential batch invocations -----------------------------
    invocations = []
    for cell in SOURCES:
        for kind in ("real", "shuffled"):
            invocations.append({
                "cell": cell,
                "kind": kind,
                "chains_dir": PROJECT_ROOT / "chains" / kind / cell,
            })

    summary: dict = {
        "phase": "phase1",
        "model": MODEL,
        "invocations": [],
        "totals": {},
    }
    overall_t0 = time.time()

    for i, inv in enumerate(invocations, 1):
        cell = inv["cell"]
        kind = inv["kind"]
        chains_dir = inv["chains_dir"]
        label = f"[{i}/{len(invocations)}] {cell} ({kind})"

        n_files = len(list(chains_dir.glob("*.jsonl")))
        expected_calls = n_files * len(EVAL_CONFIGS)
        print(f"{label} submitting batch — {n_files} chains × {len(EVAL_CONFIGS)} configs "
              f"= {expected_calls:,} calls")

        t0 = time.time()
        try:
            result = run_batch(
                chains_dir=chains_dir,
                source=cell,
                model_name=MODEL,
                output_dir=OUT_DIR,
                configs=EVAL_CONFIGS,
                n=None,                    # FULL chain set — no cap
            )
        except Exception as exc:
            elapsed = time.time() - t0
            print(f"{label} ❌ exception after {elapsed:.0f}s: {exc}")
            summary["invocations"].append({
                "cell": cell, "kind": kind, "error": str(exc),
                "elapsed_seconds": round(elapsed, 1),
            })
            # Save partial summary so we don't lose progress on crash
            _save_summary(summary, overall_t0)
            continue

        elapsed = time.time() - t0
        print(f"{label} ✅ submitted={result.get('submitted',0):,}, "
              f"completed={result.get('completed',0):,}, "
              f"errors={result.get('errors',0)} ({elapsed/60:.1f}min)")
        summary["invocations"].append({
            "cell": cell,
            "kind": kind,
            **result,
            "elapsed_seconds": round(elapsed, 1),
        })

        # Save per-invocation in case of later crash
        _save_summary(summary, overall_t0)

    # ---- Final summary ----------------------------------------------------
    overall_elapsed = time.time() - overall_t0
    submitted = sum(s.get("submitted", 0) for s in summary["invocations"])
    completed = sum(s.get("completed", 0) for s in summary["invocations"])
    errors    = sum(s.get("errors",    0) for s in summary["invocations"])
    summary["totals"] = {
        "submitted": submitted,
        "completed": completed,
        "errors":    errors,
        "wall_time_seconds": round(overall_elapsed, 1),
    }
    _save_summary(summary, overall_t0)

    print()
    print("=" * 60)
    print("PHASE 1 SUMMARY")
    print("=" * 60)
    print(f"  Total submitted:  {submitted:,}")
    print(f"  Total completed:  {completed:,}")
    print(f"  Total errors:     {errors:,}")
    print(f"  Wall time:        {overall_elapsed/60:.1f}min ({overall_elapsed/3600:.2f}h)")

    success = (completed == submitted == total_calls) and (errors == 0)
    if success:
        print("\n✅ Phase 1 COMPLETE — all batches succeeded. Ready for Session 11 review.")
        return 0
    print(f"\n⚠ Phase 1 finished with discrepancies: expected {total_calls:,} calls, "
          f"got {submitted:,} submitted, {completed:,} completed, {errors:,} errors. "
          f"Review summary before deciding on Session 12 (Sonnet).")
    return 1


def _save_summary(summary: dict, overall_t0: float) -> None:
    """Save the running summary to disk after each invocation (crash-resilient)."""
    summary_path = PROJECT_ROOT / "results" / "phase1_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_with_partial = dict(summary)
    summary_with_partial["partial_wall_time_seconds"] = round(time.time() - overall_t0, 1)
    with summary_path.open("w", encoding="utf-8") as fh:
        json.dump(summary_with_partial, fh, indent=2)


if __name__ == "__main__":
    sys.exit(main())
