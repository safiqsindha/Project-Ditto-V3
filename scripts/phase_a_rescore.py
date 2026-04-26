"""
Phase A — Step A4: rescore EXISTING Phase 1 v3.1 model responses against
the downweighted reference distribution.

Uses the existing src/scorer.py logic (DO NOT modify) plus the new
src/reference_downweighted.py reference. Adds backoff-level instrumentation
per Option B: when a chain's level-0 sig was dropped (because all top-3
were resource_side_*), lookup_with_backoff falls through. We track the
backoff-level distribution per cell × condition (real / shuffled).

Output:
  results/phase_a/a4_rescored.json — per-cell scoring under downweighted ref
                                     plus backoff-level breakdown
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.reference import ReferenceDistribution, extract_state_signature
from src.normalize import normalize_action
from src.scorer import (
    ACTIONABLE_TYPES, mcnemar_test, paired_ttest, apply_bonferroni,
    classify_outcome_tier,
)


CELLS = ("chess_standard", "chess960", "checkers_american", "draughts_intl")
TOP_K = 3
PRIMARY_CONFIG_KEY = "T0.0_seed42"


def _load_chain_dict(chain_id: str, source: str, base_dir: Path) -> dict | None:
    path = (base_dir / source) / f"{chain_id}.jsonl"
    if not path.exists():
        return None
    try:
        return json.loads(path.open().readline().strip())
    except Exception:
        return None


def _score_one_response(
    response: str,
    chain: dict,
    cutoff_k: int,
    dist: ReferenceDistribution,
) -> dict:
    """Compute Layer 1 match + record backoff level + Layer 2 coupled score."""
    constraints = chain.get("constraints", [])
    if not constraints or cutoff_k <= 0 or cutoff_k >= len(constraints):
        return {
            "l1_match": None, "l2_coupled": None,
            "constraint_type": None, "backoff_level": None,
        }
    cutoff_constraint = constraints[cutoff_k]
    constraint_type = cutoff_constraint.get("type", "")

    top_k_actions, backoff_level = dist.lookup_with_backoff(
        constraints, cutoff_k, k=TOP_K
    )

    norm_resp = normalize_action(response)
    norm_top_k = [normalize_action(a) for a in top_k_actions]

    if not top_k_actions:
        l1_match = None
        legality = 0.0
        optimality = 0.0
    else:
        l1_match = int(norm_resp in norm_top_k)
        import re
        legality = 1.0 if re.match(r"^[a-z][a-z0-9_ ]*$", norm_resp) else 0.0
        optimality = 1.0 if norm_resp in norm_top_k else 0.0
    coupled = legality * optimality if l1_match is not None else None

    return {
        "l1_match": l1_match,
        "l2_coupled": coupled,
        "constraint_type": constraint_type,
        "backoff_level": backoff_level,
    }


def main() -> int:
    chains_real_dir = PROJECT_ROOT / "chains" / "real"
    chains_shuffled_dir = PROJECT_ROOT / "chains" / "shuffled"
    results_dir = PROJECT_ROOT / "results" / "raw" / "phase1"
    bonferroni_divisor = 4

    summary: dict = {
        "phase": "phase_a_a4",
        "policy": "Option B (drop empty-top-3 sigs; backoff falls through)",
        "primary_cells": {},
        "variance_study": {},
        "backoff_rate_breakdown": {},
        "warnings": [],
    }

    for cell in CELLS:
        # Load downweighted reference (Option B)
        dist_path = PROJECT_ROOT / "data" / f"reference_{cell}_downweighted.pkl"
        if not dist_path.exists():
            print(f"[a4] missing: {dist_path}")
            continue
        dist = ReferenceDistribution.load(dist_path)

        # Walk all results for this cell, score against downweighted ref
        cell_results_dir = results_dir / cell
        if not cell_results_dir.exists():
            continue

        # Bucket scored records by alignment_key = (base_id, model, source, config_key)
        # mirroring src/scorer.py's score_all logic
        real_scored: dict[tuple, dict] = {}
        shuf_scored: dict[tuple, list[dict]] = defaultdict(list)

        for path in sorted(cell_results_dir.glob("*.json")):
            r = json.loads(path.read_text())
            chain_id = r["chain_id"]
            model = r["model"]
            source = r["source"]
            cutoff_k = r["cutoff_k"]
            seed = r["seed"]
            temp = r["temperature"]
            response = r["response"]

            is_shuf = "_shuffled_" in chain_id
            base_id = chain_id.split("_shuffled_")[0] if is_shuf else chain_id

            load_dir = chains_shuffled_dir if is_shuf else chains_real_dir
            chain = _load_chain_dict(chain_id, source, load_dir)
            if chain is None:
                continue

            scored = _score_one_response(response, chain, cutoff_k, dist)
            config_key = f"T{temp}_seed{seed}"
            align_key = (base_id, model, source, config_key)
            scored_record = {
                "l1_match": scored["l1_match"],
                "l1_constraint_type": scored["constraint_type"],
                "l2_coupled": scored["l2_coupled"],
                "backoff_level": scored["backoff_level"],
            }
            if is_shuf:
                shuf_scored[align_key].append(scored_record)
            else:
                real_scored[align_key] = scored_record

        # Build per (model, source, config_key) buckets, mirroring scorer
        per_cell_buckets: dict[tuple, dict[str, list]] = defaultdict(
            lambda: {
                "real_l1": [], "shuffled_l1": [],
                "real_l1_actionable": [], "shuffled_l1_actionable": [],
                "real_l2": [], "shuffled_l2": [],
                "real_backoff_levels": [], "shuf_backoff_levels": [],
                "n_base_chains": 0,
                "n_real_l1_none": 0, "n_shuf_l1_none": 0,
            }
        )

        for align_key in set(real_scored) | set(shuf_scored):
            base_id, model, source, config_key = align_key
            bk = per_cell_buckets[(model, source, config_key)]
            real = real_scored.get(align_key)
            shufs = shuf_scored.get(align_key, [])

            if real is None or not shufs:
                continue
            bk["n_base_chains"] += 1

            for shuf in shufs:
                # Track backoff (regardless of L1 None)
                if real["backoff_level"] is not None:
                    bk["real_backoff_levels"].append(real["backoff_level"])
                if shuf["backoff_level"] is not None:
                    bk["shuf_backoff_levels"].append(shuf["backoff_level"])

                # Skip pairs where either side has L1 None (top-3 empty
                # at all levels — degenerate; can't be scored)
                if real["l1_match"] is None or shuf["l1_match"] is None:
                    bk["n_real_l1_none"] += int(real["l1_match"] is None)
                    bk["n_shuf_l1_none"] += int(shuf["l1_match"] is None)
                    continue

                bk["real_l1"].append(real["l1_match"])
                bk["shuffled_l1"].append(shuf["l1_match"])

                # Both-actionable filter at PAIR level
                if (real["l1_constraint_type"] in ACTIONABLE_TYPES
                        and shuf["l1_constraint_type"] in ACTIONABLE_TYPES):
                    bk["real_l1_actionable"].append(real["l1_match"])
                    bk["shuffled_l1_actionable"].append(shuf["l1_match"])

                if real["l2_coupled"] is not None and shuf["l2_coupled"] is not None:
                    bk["real_l2"].append(real["l2_coupled"])
                    bk["shuffled_l2"].append(shuf["l2_coupled"])

        # Per-cell backoff breakdown (across all configs, primary first)
        backoff_summary_cell = {}
        for (model, source, config_key), bk in per_cell_buckets.items():
            real_levels = bk["real_backoff_levels"]
            shuf_levels = bk["shuf_backoff_levels"]
            real_count_by_level = Counter(real_levels)
            shuf_count_by_level = Counter(shuf_levels)
            real_total = len(real_levels)
            shuf_total = len(shuf_levels)
            backoff_summary_cell[config_key] = {
                "real": {
                    "n": real_total,
                    "level_0_pct": round((real_count_by_level.get(0, 0)/real_total*100) if real_total else 0, 2),
                    "level_1_pct": round((real_count_by_level.get(1, 0)/real_total*100) if real_total else 0, 2),
                    "level_2plus_pct": round(
                        ((real_count_by_level.get(2, 0)+real_count_by_level.get(3, 0))/real_total*100)
                        if real_total else 0, 2
                    ),
                    "mean_level": round(sum(real_levels)/real_total, 4) if real_total else None,
                },
                "shuffled": {
                    "n": shuf_total,
                    "level_0_pct": round((shuf_count_by_level.get(0, 0)/shuf_total*100) if shuf_total else 0, 2),
                    "level_1_pct": round((shuf_count_by_level.get(1, 0)/shuf_total*100) if shuf_total else 0, 2),
                    "level_2plus_pct": round(
                        ((shuf_count_by_level.get(2, 0)+shuf_count_by_level.get(3, 0))/shuf_total*100)
                        if shuf_total else 0, 2
                    ),
                    "mean_level": round(sum(shuf_levels)/shuf_total, 4) if shuf_total else None,
                },
            }

        summary["backoff_rate_breakdown"][cell] = backoff_summary_cell

        # Per cell × config tests
        for (model, source, config_key), bk in per_cell_buckets.items():
            l1_test = mcnemar_test(bk["real_l1"], bk["shuffled_l1"])
            l1_act_test = mcnemar_test(
                bk["real_l1_actionable"], bk["shuffled_l1_actionable"]
            )
            l2_test = paired_ttest(bk["real_l2"], bk["shuffled_l2"])

            gap = l1_act_test.get("gap", 0.0) if "error" not in l1_act_test else 0.0
            pval_raw = l1_act_test.get("p_value", 1.0) if "error" not in l1_act_test else 1.0

            is_primary = config_key == PRIMARY_CONFIG_KEY
            if is_primary:
                pval_bon = apply_bonferroni(pval_raw, bonferroni_divisor)
                tier = classify_outcome_tier(gap, pval_bon)
            else:
                pval_bon = None
                tier = None

            cell_data = {
                "layer1": l1_test,
                "layer1_actionable": l1_act_test,
                "layer2": l2_test,
                "diagnostics": {
                    "n_base_chains": bk["n_base_chains"],
                    "n_pairs_total": len(bk["real_l1"]),
                    "n_pairs_actionable": len(bk["real_l1_actionable"]),
                    "n_pairs_l2": len(bk["real_l2"]),
                    "n_real_l1_none": bk["n_real_l1_none"],
                    "n_shuf_l1_none": bk["n_shuf_l1_none"],
                },
            }
            if is_primary:
                cell_data["layer1_actionable_bonferroni"] = {
                    **l1_act_test,
                    "p_value_bonferroni": round(pval_bon, 6),
                    "bonferroni_divisor": bonferroni_divisor,
                    "significant_bonferroni": bool(pval_bon < 0.05),
                }
                cell_data["outcome_tier"] = tier
                summary["primary_cells"][f"{model}::{source}"] = cell_data
            else:
                summary["variance_study"][f"{model}::{source}::{config_key}"] = cell_data

    # Backoff differential check (>20pp flag)
    for cell, configs in summary["backoff_rate_breakdown"].items():
        primary = configs.get(PRIMARY_CONFIG_KEY, {})
        real = primary.get("real", {})
        shuf = primary.get("shuffled", {})
        if real and shuf:
            real_l0 = real.get("level_0_pct", 0)
            shuf_l0 = shuf.get("level_0_pct", 0)
            diff = abs(real_l0 - shuf_l0)
            if diff > 20:
                msg = (f"⚠ {cell} primary config: backoff differential "
                       f"|real_level0_pct - shuf_level0_pct| = "
                       f"|{real_l0} - {shuf_l0}| = {diff:.2f}pp > 20pp threshold")
                summary["warnings"].append(msg)
                print(msg)

    out_path = PROJECT_ROOT / "results" / "phase_a" / "a4_rescored.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\n=== A4 PRIMARY CELLS (Bonferroni divisor={bonferroni_divisor}) ===")
    for label, s in sorted(summary["primary_cells"].items()):
        l1a = s.get("layer1_actionable_bonferroni", {})
        gap = l1a.get("gap", "N/A")
        p_bon = l1a.get("p_value_bonferroni", "N/A")
        tier = s.get("outcome_tier", "?")
        sig = "*" if l1a.get("significant_bonferroni") else " "
        n_act = s.get("diagnostics", {}).get("n_pairs_actionable", "N/A")
        gapstr = f"{gap:+.4f}" if isinstance(gap, (int, float)) else gap
        pstr = f"{p_bon:.4f}" if isinstance(p_bon, (int, float)) else p_bon
        print(f"  {label:<30s}  n_act={n_act:>5}  gap={gapstr:>9}  p_bon={pstr:>8}  {sig} {tier}")

    print(f"\n=== A4 BACKOFF RATES (primary config T=0.0/seed=42) ===")
    for cell, configs in summary["backoff_rate_breakdown"].items():
        primary = configs.get(PRIMARY_CONFIG_KEY, {})
        if not primary:
            continue
        rl = primary.get("real", {})
        sl = primary.get("shuffled", {})
        print(f"\n  {cell}:")
        print(f"    REAL  (n={rl.get('n')}): "
              f"L0={rl.get('level_0_pct')}%, L1={rl.get('level_1_pct')}%, "
              f"L2+={rl.get('level_2plus_pct')}%, mean={rl.get('mean_level')}")
        print(f"    SHUF  (n={sl.get('n')}): "
              f"L0={sl.get('level_0_pct')}%, L1={sl.get('level_1_pct')}%, "
              f"L2+={sl.get('level_2plus_pct')}%, mean={sl.get('mean_level')}")
    print(f"\nOutput → {out_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
