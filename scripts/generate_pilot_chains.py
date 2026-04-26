"""
Session 6: Generate 50 pilot chains per cell (all 4 cells).

Outputs:
  chains/pilot/{cell}/pilot_chains.jsonl  — 50 valid chains per cell
  chains/pilot/{cell}/pilot_stats.json    — constraint type distribution stats

Pilot inspection criteria (Gate 6):
  1. Leakage check: 100% of rendered chains pass renderer.check_leakage()
  2. Chain validity: ≥80% of generated windows pass is_valid_chain()
  3. Constraint type distribution: all 6 types present across the 50 chains
  4. Qualitative spot-check (printed to stdout): 2 chains per cell rendered
"""

from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

# Ensure project root on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, '/Users/safiqsindha/Library/Python/3.9/lib/python/site-packages')

from src.aggregation import extract_all_windows
from src.filter import is_valid_chain
from src.renderer import check_leakage, render_trajectory_chain, _CELL_TO_PERSPECTIVE
from src.translation import translate_trajectory

# ---------------------------------------------------------------------------
# Cell configuration
# ---------------------------------------------------------------------------

CELLS = {
    "chess_standard": {
        "jsonl": PROJECT_ROOT / "data" / "chess_standard" / "games.jsonl",
        "parser": "chess",
        "chess960": False,
        "variant": "chess_standard",
    },
    "chess960": {
        "jsonl": PROJECT_ROOT / "data" / "chess960" / "games.jsonl",
        "parser": "chess",
        "chess960": True,
        "variant": "chess960",
    },
    "checkers_american": {
        "jsonl": PROJECT_ROOT / "data" / "checkers_american" / "games.jsonl",
        "parser": "checkers",
        "variant_key": "american",
        "variant": "checkers_american",
    },
    "draughts_intl": {
        "jsonl": PROJECT_ROOT / "data" / "draughts_intl" / "games.jsonl",
        "parser": "checkers",
        "variant_key": "standard",
        "variant": "draughts_intl",
    },
}

PILOT_TARGET = 50    # chains per cell
MAX_GAMES_TO_SCAN = 300   # scan up to this many games per cell to collect 50 chains
SPOT_CHECK_COUNT = 2  # chains per cell to print for qualitative review
RANDOM_SEED = 42


def load_chess_trajectories(jsonl_path: Path, chess960: bool, limit: int):
    """Load up to `limit` TrajectoryLogs from a chess JSONL file."""
    from src.parser_chess import parse_games_jsonl
    return list(parse_games_jsonl(jsonl_path, chess960=chess960, limit=limit))


def load_checkers_trajectories(jsonl_path: Path, variant_key: str, limit: int):
    """Load up to `limit` TrajectoryLogs from a checkers JSONL file."""
    from src.parser_checkers import parse_games_jsonl
    return list(parse_games_jsonl(jsonl_path, variant=variant_key, limit=limit))


def generate_pilot_chains(cell_name: str, cfg: dict) -> dict:
    """
    Generate up to PILOT_TARGET valid chains for one cell.

    Returns a stats dict.
    """
    rng = random.Random(RANDOM_SEED)
    variant = cfg["variant"]
    pilot_dir = PROJECT_ROOT / "chains" / "pilot" / cell_name
    pilot_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"Cell: {cell_name}")
    print(f"{'='*60}")

    # ---- Load trajectories ------------------------------------------------
    print(f"  Loading trajectories from {cfg['jsonl'].name} ...")
    if cfg["parser"] == "chess":
        trajs = load_chess_trajectories(cfg["jsonl"], cfg["chess960"], MAX_GAMES_TO_SCAN)
    else:
        trajs = load_checkers_trajectories(cfg["jsonl"], cfg["variant_key"], MAX_GAMES_TO_SCAN)
    print(f"  Loaded {len(trajs)} trajectories")

    # ---- Generate windows + translate -------------------------------------
    all_windows = 0
    valid_windows = 0
    chains_collected = []
    leakage_failures = 0
    type_counter: Counter = Counter()

    for traj in trajs:
        if len(chains_collected) >= PILOT_TARGET:
            break
        windows = extract_all_windows(traj)
        for window_events in windows:
            if len(chains_collected) >= PILOT_TARGET:
                break
            all_windows += 1
            constraints = translate_trajectory(window_events, variant=variant)
            if not is_valid_chain(constraints):
                continue
            valid_windows += 1

            # Leakage check (use abstract perspective label via render_trajectory_chain)
            try:
                rendered = render_trajectory_chain(constraints, source=variant)
                leaked = check_leakage(rendered)
                if leaked:
                    leakage_failures += 1
                    print(f"  ⚠ Leakage detected: {leaked}")
                    continue
            except ValueError as e:
                leakage_failures += 1
                print(f"  ⚠ Render error: {e}")
                continue

            # Collect type distribution
            for c in constraints:
                type_counter[type(c).__name__] += 1

            chain_id = f"{cell_name}_pilot_{len(chains_collected):04d}"
            chains_collected.append({
                "chain_id": chain_id,
                "cell": cell_name,
                "game_id": traj.game_id,
                "variant": variant,
                "length": len(constraints),
                "constraint_types": [type(c).__name__ for c in constraints],
                "rendered": rendered,
            })

    # ---- Stats ------------------------------------------------------------
    pass_rate = valid_windows / all_windows if all_windows > 0 else 0.0
    collected = len(chains_collected)

    print(f"  Windows scanned:   {all_windows}")
    print(f"  Valid windows:     {valid_windows}  ({pass_rate*100:.1f}%)")
    print(f"  Leakage failures:  {leakage_failures}")
    print(f"  Chains collected:  {collected}")
    print(f"  Constraint type distribution:")
    for ctype, cnt in sorted(type_counter.items()):
        avg = cnt / collected if collected > 0 else 0
        print(f"    {ctype:<30s}: {cnt:5d} total  ({avg:.2f}/chain)")

    # ---- Spot-check (qualitative) ----------------------------------------
    spot_indices = list(range(min(SPOT_CHECK_COUNT, collected)))
    if collected > SPOT_CHECK_COUNT:
        spot_indices = sorted(rng.sample(range(collected), SPOT_CHECK_COUNT))
    print(f"\n  --- Spot-check ({SPOT_CHECK_COUNT} chains) ---")
    for idx in spot_indices:
        print(f"\n  Chain {idx} ({chains_collected[idx]['chain_id']}):")
        for line in chains_collected[idx]["rendered"].split("\n")[:8]:
            print(f"    {line}")
        if len(chains_collected[idx]["rendered"].split("\n")) > 8:
            print(f"    ... ({chains_collected[idx]['length']} steps total)")

    # ---- Write JSONL output -----------------------------------------------
    out_path = pilot_dir / "pilot_chains.jsonl"
    with open(out_path, "w", encoding="utf-8") as fh:
        for chain in chains_collected:
            # Write serializable version (exclude rendered for JSONL size)
            record = {k: v for k, v in chain.items() if k != "rendered"}
            fh.write(json.dumps(record) + "\n")

    # ---- Write stats JSON -------------------------------------------------
    stats = {
        "cell": cell_name,
        "variant": variant,
        "games_scanned": len(trajs),
        "windows_scanned": all_windows,
        "valid_windows": valid_windows,
        "pass_rate": pass_rate,
        "leakage_failures": leakage_failures,
        "chains_collected": collected,
        "type_distribution": dict(type_counter),
        "type_per_chain": {k: v / collected for k, v in type_counter.items()} if collected > 0 else {},
        "gate6_checks": {
            "leakage_100pct": leakage_failures == 0,
            "pass_rate_gte_80pct": pass_rate >= 0.80,
            "all_6_types_present": len(type_counter) >= 6,
            "collected_50_chains": collected >= PILOT_TARGET,
        },
    }
    stats_path = pilot_dir / "pilot_stats.json"
    with open(stats_path, "w", encoding="utf-8") as fh:
        json.dump(stats, fh, indent=2)

    print(f"\n  Gate 6 checks:")
    for check, result in stats["gate6_checks"].items():
        mark = "✅" if result else "❌"
        print(f"    {mark}  {check}: {result}")

    return stats


def main():
    print("Session 6 — Pilot chain generation")
    print(f"Target: {PILOT_TARGET} chains per cell")
    print(f"Scanning up to {MAX_GAMES_TO_SCAN} games per cell\n")

    all_stats = {}
    gate6_all_pass = True

    for cell_name, cfg in CELLS.items():
        stats = generate_pilot_chains(cell_name, cfg)
        all_stats[cell_name] = stats
        if not all(stats["gate6_checks"].values()):
            gate6_all_pass = False

    # ---- Summary ----------------------------------------------------------
    print(f"\n{'='*60}")
    print("GATE 6 SUMMARY")
    print(f"{'='*60}")
    for cell_name, stats in all_stats.items():
        checks = stats["gate6_checks"]
        all_pass = all(checks.values())
        mark = "✅" if all_pass else "❌"
        print(f"  {mark}  {cell_name}: pass_rate={stats['pass_rate']*100:.1f}%, "
              f"chains={stats['chains_collected']}, "
              f"leakage_failures={stats['leakage_failures']}, "
              f"types={len(stats['type_distribution'])}")

    if gate6_all_pass:
        print("\n✅ GATE 6 PASSED — T-code freeze can proceed")
    else:
        print("\n❌ GATE 6 FAILED — review failures above before freezing T-code")

    # ---- Write combined stats ---------------------------------------------
    combined_path = PROJECT_ROOT / "chains" / "pilot" / "pilot_summary.json"
    combined_path.parent.mkdir(parents=True, exist_ok=True)
    with open(combined_path, "w", encoding="utf-8") as fh:
        json.dump({"gate6_passed": gate6_all_pass, "cells": all_stats}, fh, indent=2)
    print(f"\nSummary written to {combined_path}")

    return 0 if gate6_all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
