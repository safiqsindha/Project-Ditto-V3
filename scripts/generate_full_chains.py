"""
Session 7: Full chain generation.

Generates the production chain set used by Session 8 (reference distributions),
Session 9 (dry run), Session 10 (Phase 1 Haiku), and Session 12 (Phase 2 Sonnet).

Per cell × 4 cells:
  - 1,200 real chains          → chains/real/{cell}/{chain_id}.jsonl
  - 1,200 × 3 shuffled (seeds 42, 1337, 7919) → chains/shuffled/{cell}/{chain_id}.jsonl

Total: 4,800 real + 14,400 shuffled = 19,200 chain files.

Per-chain JSONL schema (matches what src/runner.py and src/reference.py read):
{
  "chain_id":       str,           # unique e.g. "chess_standard_real_0001"
  "match_id":       str,           # = real chain's chain_id (links real ↔ shuffled)
  "source":         str,           # cell name (chess_standard, chess960, ...)
  "variant":        str,           # alias of source
  "game_id":        str,           # source trajectory id (for traceability)
  "length":         int,           # number of constraints (15..25)
  "constraint_types": list[str],   # type names per step
  "cutoff_k":       int,           # ⌊length/2⌋ — Layer 1 evaluation cutoff
  "focal_action":   str,           # entity at constraints[cutoff_k - 1]
  "constraints":    list[dict],    # serialized (each has "type" field)
  "rendered":       str,           # human-readable chain (post leakage check)
  "seed":           int | None,    # shuffled seed; null for real
}

Hard leakage check is run on every rendered chain (real and shuffled). Any
failure aborts the run. Soft leakage warnings are aggregated and reported at
the end but do not abort.
"""

from __future__ import annotations

import dataclasses
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, '/Users/safiqsindha/Library/Python/3.9/lib/python/site-packages')

from src.aggregation import extract_all_windows
from src.filter import VALIDITY_REASONS, validity_failures
from src.reference import extract_entity_from_constraint
from src.renderer import (
    check_leakage,
    check_leakage_substring,
    render_trajectory_chain,
)
from src.shuffler import shuffle_chain
from src.translation import (
    Constraint,
    constraint_from_dict,
    translate_trajectory,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CELLS = {
    "chess_standard": {
        "jsonl": PROJECT_ROOT / "data" / "chess_standard" / "games.jsonl",
        "parser": "chess",
        "chess960": False,
    },
    "chess960": {
        "jsonl": PROJECT_ROOT / "data" / "chess960" / "games.jsonl",
        "parser": "chess",
        "chess960": True,
    },
    "checkers_american": {
        "jsonl": PROJECT_ROOT / "data" / "checkers_american" / "games.jsonl",
        "parser": "checkers",
        "variant_key": "american",
    },
    "draughts_intl": {
        "jsonl": PROJECT_ROOT / "data" / "draughts_intl" / "games.jsonl",
        "parser": "checkers",
        "variant_key": "standard",
    },
}

CHAINS_PER_CELL = 1200          # SPEC §Per-cell sample target
SHUFFLE_SEEDS = (42, 1337, 7919) # SPEC §Shuffle seeds
MAX_GAMES_TO_SCAN = 2000        # full materialised dataset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_constraint(c: Constraint) -> dict[str, Any]:
    """Dataclass → dict with type tag (matches reference.py + scorer.py expectations)."""
    d = dataclasses.asdict(c)
    d["type"] = type(c).__name__
    return d


def _focal_action_for(constraint_dicts: list[dict], cutoff_k: int) -> str:
    """Entity label for the constraint at the cutoff position."""
    if cutoff_k <= 0 or cutoff_k > len(constraint_dicts):
        return "unknown"
    return extract_entity_from_constraint(constraint_dicts[cutoff_k - 1]) or "unknown"


def _load_trajectories(cell_name: str, cfg: dict, limit: int) -> list:
    """Stream trajectories for one cell."""
    if cfg["parser"] == "chess":
        from src.parser_chess import parse_games_jsonl
        return list(parse_games_jsonl(cfg["jsonl"], chess960=cfg["chess960"], limit=limit))
    else:
        from src.parser_checkers import parse_games_jsonl
        return list(parse_games_jsonl(cfg["jsonl"], variant=cfg["variant_key"], limit=limit))


def _build_real_chain_record(
    constraints: list[Constraint],
    cell_name: str,
    chain_index: int,
    game_id: str,
    rendered: str,
) -> dict:
    chain_id = f"{cell_name}_real_{chain_index:04d}"
    serialized = [_serialize_constraint(c) for c in constraints]
    cutoff_k = max(1, len(constraints) // 2)
    return {
        "chain_id": chain_id,
        "match_id": chain_id,
        "source": cell_name,
        "variant": cell_name,
        "game_id": game_id,
        "length": len(constraints),
        "constraint_types": [type(c).__name__ for c in constraints],
        "cutoff_k": cutoff_k,
        "focal_action": _focal_action_for(serialized, cutoff_k),
        "constraints": serialized,
        "rendered": rendered,
        "seed": None,
    }


def _build_shuffled_record(real_record: dict, seed: int) -> dict:
    """Shuffle a real chain, re-render, return shuffled chain record."""
    real_id = real_record["chain_id"]
    cell_name = real_record["source"]

    # Shuffle on serialized dicts (shuffle_chain handles both formats).
    shuffled = shuffle_chain(
        {
            "chain_id": real_id,
            "match_id": real_record["match_id"],
            "constraints": real_record["constraints"],
        },
        seed=seed,
    )

    # Re-hydrate to dataclass instances for re-rendering.
    constraints_dataclass = [constraint_from_dict(d) for d in shuffled["constraints"]]
    rendered = render_trajectory_chain(constraints_dataclass, source=cell_name)

    cutoff_k = max(1, len(constraints_dataclass) // 2)
    return {
        "chain_id": shuffled["chain_id"],     # already "<real_id>_shuffled_<seed>"
        "match_id": real_record["match_id"],
        "source": cell_name,
        "variant": cell_name,
        "game_id": real_record.get("game_id"),
        "length": len(constraints_dataclass),
        "constraint_types": [type(c).__name__ for c in constraints_dataclass],
        "cutoff_k": cutoff_k,
        "focal_action": _focal_action_for(shuffled["constraints"], cutoff_k),
        "constraints": shuffled["constraints"],
        "rendered": rendered,
        "seed": seed,
    }


def _write_chain_record(record: dict, out_dir: Path) -> None:
    """One JSONL file per chain (matches runner.py expectations)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{record['chain_id']}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Per-cell generation
# ---------------------------------------------------------------------------

def generate_for_cell(cell_name: str, cfg: dict) -> dict:
    print(f"\n{'='*60}")
    print(f"Cell: {cell_name}  (target: {CHAINS_PER_CELL} real chains)")
    print(f"{'='*60}")

    real_dir     = PROJECT_ROOT / "chains" / "real" / cell_name
    shuffled_dir = PROJECT_ROOT / "chains" / "shuffled" / cell_name
    real_dir.mkdir(parents=True, exist_ok=True)
    shuffled_dir.mkdir(parents=True, exist_ok=True)

    # Load trajectories
    t0 = time.time()
    print(f"  Loading trajectories from {cfg['jsonl'].name} (limit {MAX_GAMES_TO_SCAN}) ...")
    trajs = _load_trajectories(cell_name, cfg, MAX_GAMES_TO_SCAN)
    print(f"  Loaded {len(trajs)} trajectories in {time.time()-t0:.1f}s")

    # Walk windows
    real_count = 0
    windows_total = 0
    invalid_total = 0
    failure_reasons: Counter = Counter()
    hard_leakage_failures = 0
    soft_leakage_terms: Counter = Counter()
    games_used: set[str] = set()
    type_counter: Counter = Counter()
    length_counter: Counter = Counter()

    t_gen = time.time()
    for traj in trajs:
        if real_count >= CHAINS_PER_CELL:
            break
        windows = extract_all_windows(traj)
        for window_events in windows:
            if real_count >= CHAINS_PER_CELL:
                break
            windows_total += 1

            # Translate
            constraints = translate_trajectory(window_events, variant=cell_name)

            # Validate
            failures = validity_failures(constraints)
            if failures:
                invalid_total += 1
                for r in failures:
                    failure_reasons[r] += 1
                continue

            # Render real chain (HARD leakage gate)
            try:
                rendered = render_trajectory_chain(constraints, source=cell_name)
            except ValueError as exc:
                hard_leakage_failures += 1
                print(f"  ABORT — hard leakage in real chain: {exc}")
                raise

            # Hard leakage on real (defensive — render_trajectory_chain already enforces)
            leaked = check_leakage(rendered)
            if leaked:
                hard_leakage_failures += 1
                print(f"  ABORT — leaked terms in real chain: {leaked}")
                raise RuntimeError(f"Hard leakage in {cell_name}: {leaked}")

            # Soft leakage tracking (non-fatal)
            for term in check_leakage_substring(rendered):
                soft_leakage_terms[term] += 1

            # Build real record + write
            real_record = _build_real_chain_record(
                constraints=constraints,
                cell_name=cell_name,
                chain_index=real_count,
                game_id=traj.game_id,
                rendered=rendered,
            )
            _write_chain_record(real_record, real_dir)

            # Build + write 3 shuffled variants
            for seed in SHUFFLE_SEEDS:
                shuffled_record = _build_shuffled_record(real_record, seed)
                # Hard leakage on shuffled (constraint reordering shouldn't introduce
                # any new strings — every label comes from the real chain — but
                # check defensively).
                leaked_s = check_leakage(shuffled_record["rendered"])
                if leaked_s:
                    hard_leakage_failures += 1
                    print(f"  ABORT — leaked terms in shuffled chain "
                          f"({shuffled_record['chain_id']}): {leaked_s}")
                    raise RuntimeError(f"Hard leakage in shuffled chain")
                _write_chain_record(shuffled_record, shuffled_dir)

            type_counter.update(real_record["constraint_types"])
            length_counter[real_record["length"]] += 1
            games_used.add(traj.game_id)
            real_count += 1

            if real_count % 100 == 0 or real_count == CHAINS_PER_CELL:
                elapsed = time.time() - t_gen
                rate = real_count / elapsed if elapsed > 0 else 0
                print(f"  ... {real_count}/{CHAINS_PER_CELL} chains "
                      f"({rate:.1f}/s, {elapsed:.0f}s elapsed, "
                      f"{windows_total} windows scanned)")

    elapsed = time.time() - t_gen
    pass_rate = (real_count / windows_total) if windows_total else 0.0

    # ---- Per-cell summary -------------------------------------------------
    print(f"\n  Done in {elapsed:.0f}s")
    print(f"  Windows scanned:        {windows_total}")
    print(f"  Real chains written:    {real_count}")
    print(f"  Shuffled written:       {real_count * len(SHUFFLE_SEEDS)}")
    print(f"  Source games used:      {len(games_used)} / {len(trajs)}")
    print(f"  Validity pass rate:     {pass_rate*100:.1f}%")
    print(f"  Hard leakage failures:  {hard_leakage_failures}")
    print(f"  Soft leakage warnings:  "
          f"{'none ✅' if not soft_leakage_terms else dict(soft_leakage_terms)}")
    print(f"  Validity failure breakdown:")
    for reason in VALIDITY_REASONS:
        cnt = failure_reasons.get(reason, 0)
        if cnt:
            pct = (cnt / invalid_total * 100) if invalid_total else 0.0
            print(f"    {reason:<24s}: {cnt:5d}  ({pct:5.1f}%)")
    print(f"  Length distribution (saved chains):")
    for length in sorted(length_counter):
        print(f"    len={length}: {length_counter[length]}")

    return {
        "cell": cell_name,
        "real_chains_written": real_count,
        "shuffled_chains_written": real_count * len(SHUFFLE_SEEDS),
        "windows_scanned": windows_total,
        "invalid_windows": invalid_total,
        "validity_failure_breakdown": {r: failure_reasons.get(r, 0) for r in VALIDITY_REASONS},
        "validity_pass_rate": round(pass_rate, 4),
        "hard_leakage_failures": hard_leakage_failures,
        "soft_leakage_warnings": dict(soft_leakage_terms),
        "type_distribution": dict(type_counter),
        "length_distribution": dict(length_counter),
        "source_games_used": len(games_used),
        "elapsed_seconds": round(elapsed, 1),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print(f"Session 7 — Full chain generation")
    print(f"Target: {CHAINS_PER_CELL} real chains × 4 cells "
          f"+ {len(SHUFFLE_SEEDS)} shuffled per real "
          f"= {CHAINS_PER_CELL * 4} real + {CHAINS_PER_CELL * 4 * len(SHUFFLE_SEEDS)} shuffled "
          f"= {CHAINS_PER_CELL * 4 * (1 + len(SHUFFLE_SEEDS))} chain files\n")

    all_stats: dict[str, dict] = {}
    overall_t0 = time.time()
    for cell_name, cfg in CELLS.items():
        all_stats[cell_name] = generate_for_cell(cell_name, cfg)

    # Combined summary
    print(f"\n{'='*60}")
    print(f"SESSION 7 SUMMARY")
    print(f"{'='*60}")
    total_real = sum(s["real_chains_written"] for s in all_stats.values())
    total_shuf = sum(s["shuffled_chains_written"] for s in all_stats.values())
    total_hard = sum(s["hard_leakage_failures"] for s in all_stats.values())
    total_elapsed = time.time() - overall_t0
    for cell, s in all_stats.items():
        achieved = "✅" if s["real_chains_written"] >= CHAINS_PER_CELL else "❌"
        print(f"  {achieved}  {cell:<22s}: real={s['real_chains_written']:5d}  "
              f"shuffled={s['shuffled_chains_written']:5d}  "
              f"pass_rate={s['validity_pass_rate']*100:.1f}%  "
              f"hard_leakage={s['hard_leakage_failures']}")
    print(f"\nTotal real:     {total_real:6d}")
    print(f"Total shuffled: {total_shuf:6d}")
    print(f"Total files:    {total_real + total_shuf:6d}")
    print(f"Hard leakage:   {total_hard}")
    print(f"Elapsed:        {total_elapsed:.0f}s ({total_elapsed/60:.1f}min)")

    out_path = PROJECT_ROOT / "chains" / "generation_summary.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump({"cells": all_stats, "elapsed_seconds": round(total_elapsed, 1)},
                  fh, indent=2)
    print(f"\nSummary → {out_path}")

    success = (
        total_real == CHAINS_PER_CELL * len(CELLS)
        and total_hard == 0
    )
    if not success:
        print("\n❌ Session 7 INCOMPLETE — fewer real chains than target or hard leakage detected.")
        return 1
    print("\n✅ Session 7 COMPLETE — all cells hit target with zero hard leakage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
