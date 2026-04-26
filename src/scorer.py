"""
Scorer v3 — paired tests with both-actionable filter (game domain).

Implements the pre-registered statistical methodology from SPEC.md:
  - Layer 1: continuity-corrected McNemar's test (paired)
  - Layer 2: paired t-test (scipy.stats.ttest_rel)
  - Both-actionable filter: pair enters actionable analysis iff BOTH real
    and shuffled chains have an actionable constraint at the cutoff position
  - Bonferroni correction: divisor = 4 (Phase 1 only) or 8 (Phase 1 + 2)

Actionable types in game domain (SPEC §Both-actionable filter):
  ToolAvailability, SubGoalTransition, CoordinationDependency, OptimizationCriterion
  (InformationState excluded — non-actionable in perfect-information games)

Adapted from v2 scorer_corrected_v2.py: sources and ACTIONABLE_TYPES updated.

Usage:
    python -m src.scorer \\
        --results results/raw/ \\
        --dist-chess-standard data/reference_chess_standard.pkl \\
        --dist-chess960 data/reference_chess960.pkl \\
        --dist-checkers-american data/reference_checkers_american.pkl \\
        --dist-draughts-intl data/reference_draughts_intl.pkl \\
        --bonferroni-divisor 4 \\
        --out results/scored.json
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

from src.normalize import normalize_action
from src.reference import ReferenceDistribution, extract_state_signature, extract_entity_from_constraint

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOP_K = 3

# v3 actionable types (SPEC §Both-actionable filter)
# InformationState is excluded — perfect-information games make it non-actionable
ACTIONABLE_TYPES: set[str] = {
    "ToolAvailability",
    "SubGoalTransition",
    "CoordinationDependency",
    "OptimizationCriterion",
}

SOURCES: list[str] = [
    "chess_standard",
    "chess960",
    "checkers_american",
    "draughts_intl",
]

# ---------------------------------------------------------------------------
# Statistical tests (identical logic to v2 scorer_corrected_v2.py)
# ---------------------------------------------------------------------------

def mcnemar_test(
    real_matches: list[int],
    shuffled_matches: list[int],
) -> dict[str, Any]:
    """McNemar's test (with continuity correction) for paired binary Layer 1 outcomes."""
    n = len(real_matches)
    if n == 0:
        return {"error": "empty sample"}
    if n != len(shuffled_matches):
        return {"error": "list length mismatch"}

    n11 = sum(r == 1 and s == 1 for r, s in zip(real_matches, shuffled_matches))
    b   = sum(r == 1 and s == 0 for r, s in zip(real_matches, shuffled_matches))
    c   = sum(r == 0 and s == 1 for r, s in zip(real_matches, shuffled_matches))
    n00 = sum(r == 0 and s == 0 for r, s in zip(real_matches, shuffled_matches))

    if b + c == 0:
        chi2_stat = 0.0
        p_value = 1.0
    else:
        chi2_stat = float((abs(b - c) - 1) ** 2) / float(b + c)
        p_value = float(1.0 - stats.chi2.cdf(chi2_stat, df=1))

    real_rate = sum(real_matches) / n
    shuf_rate = sum(shuffled_matches) / n

    return {
        "n_pairs": n,
        "n11_concordant_both_match": n11,
        "b_discordant_real_match": b,
        "c_discordant_shuffled_match": c,
        "n00_concordant_neither": n00,
        "real_rate": round(real_rate, 4),
        "shuffled_rate": round(shuf_rate, 4),
        "gap": round(real_rate - shuf_rate, 4),
        "chi2_stat": round(chi2_stat, 4),
        "p_value": round(p_value, 4),
        "significant_05": bool(p_value < 0.05),
        "test": "mcnemar_continuity_corrected",
    }


def paired_ttest(
    real_scores: list[float],
    shuffled_scores: list[float],
) -> dict[str, Any]:
    """Paired t-test for Layer 2 continuous scores."""
    n = len(real_scores)
    if n < 2:
        return {"error": "insufficient data (need >=2 pairs)"}
    if n != len(shuffled_scores):
        return {"error": "list length mismatch"}

    # Defensive: scipy.stats.ttest_rel returns NaN when both arms are
    # identical (divide-by-zero on std-dev). Detect and return a clean
    # zero result instead of letting NaN propagate into significance flags.
    if all(r == s for r, s in zip(real_scores, shuffled_scores)):
        mean_val = round(float(np.mean(real_scores)), 4)
        return {
            "n_pairs": n,
            "real_mean": mean_val,
            "shuffled_mean": mean_val,
            "gap": 0.0,
            "mean_diff": 0.0,
            "t_stat": 0.0,
            "p_value": 1.0,
            "significant_05": False,
            "test": "paired_ttest",
            "note": "identical arms; zero variance",
        }

    t, p = stats.ttest_rel(real_scores, shuffled_scores)
    diffs = [r - s for r, s in zip(real_scores, shuffled_scores)]

    return {
        "n_pairs": n,
        "real_mean": round(float(np.mean(real_scores)), 4),
        "shuffled_mean": round(float(np.mean(shuffled_scores)), 4),
        "gap": round(float(np.mean(real_scores)) - float(np.mean(shuffled_scores)), 4),
        "mean_diff": round(float(np.mean(diffs)), 4),
        "t_stat": round(float(t), 4),
        "p_value": round(float(p), 4),
        "significant_05": bool(p < 0.05),
        "test": "paired_ttest",
    }


def apply_bonferroni(p_value: float, n_tests: int) -> float:
    # Defensive: clamp at 1 to avoid spurious p=0 when no tests are configured
    # (e.g., empty per_cell or future auto-divisor mode). A divisor of 0 would
    # otherwise produce min(1.0, p × 0) = 0.0 — falsely "significant".
    n_tests = max(1, n_tests)
    return min(1.0, p_value * n_tests)


# ---------------------------------------------------------------------------
# Per-evaluation scoring helpers
# ---------------------------------------------------------------------------

def score_layer1(
    model_response: str,
    chain: dict,
    cutoff_k: int,
    dist: ReferenceDistribution,
) -> dict[str, Any]:
    """
    Score one model response against the reference distribution (Layer 1).

    Returns dict with top_k_match (0/1), constraint_type, and top_k_actions.
    """
    constraints = chain.get("constraints", [])
    if not constraints or cutoff_k <= 0 or cutoff_k > len(constraints):
        return {"top_k_match": None, "constraint_type": None, "error": "invalid cutoff"}

    cutoff_constraint = constraints[cutoff_k - 1]
    constraint_type = cutoff_constraint.get("type", "")

    top_k_actions, backoff_level = dist.lookup_with_backoff(constraints, cutoff_k, k=TOP_K)
    normalized_response = normalize_action(model_response)
    normalized_top_k = [normalize_action(a) for a in top_k_actions]

    match = int(normalized_response in normalized_top_k) if normalized_top_k else None

    return {
        "top_k_match": match,
        "constraint_type": constraint_type,
        "backoff_level": backoff_level,
        "top_k_actions": top_k_actions,
        "normalized_response": normalized_response,
    }


def score_layer2(
    model_response: str,
    chain: dict,
    cutoff_k: int,
    dist: ReferenceDistribution,
) -> dict[str, Any]:
    """
    Score one model response on legality × optimality composite (Layer 2).

    Legality: 1.0 if response matches a known action label format, 0.0 otherwise.
    Optimality: fraction of top-k actions the response matches.
    Coupled score: legality × optimality.

    Returns coupled=None on invalid cutoff so the aggregation can skip such
    pairs (mirrors score_layer1) — prevents sentinel-zero pollution of the
    paired t-test means.
    """
    constraints = chain.get("constraints", [])
    if not constraints or cutoff_k <= 0 or cutoff_k > len(constraints):
        return {"legality": None, "optimality": None, "coupled": None,
                "error": "invalid cutoff"}

    top_k_actions, _ = dist.lookup_with_backoff(constraints, cutoff_k, k=TOP_K)
    normalized_response = normalize_action(model_response)

    # Legality: does the response look like a valid action label?
    import re
    legality = 1.0 if re.match(r"^[a-z][a-z0-9_ ]*$", normalized_response) else 0.0

    if not top_k_actions:
        optimality = 0.0
    else:
        normalized_top_k = [normalize_action(a) for a in top_k_actions]
        optimality = 1.0 if normalized_response in normalized_top_k else 0.0

    coupled = legality * optimality

    return {
        "legality": round(legality, 4),
        "optimality": round(optimality, 4),
        "coupled": round(coupled, 4),
    }


def classify_outcome_tier(gap: float, p_value: float) -> str:
    """Map (gap, p_value) to outcome tier string (SPEC §Per-cell thresholds)."""
    if gap >= 0.08 and p_value < 0.01:
        return "strong_positive"
    if gap >= 0.05 and p_value < 0.05:
        return "moderate_positive"
    if gap >= 0.01:
        return "weak_mixed"
    if gap < 0:
        return "reversed"
    return "null"


# ---------------------------------------------------------------------------
# Pair alignment and both-actionable filter
# ---------------------------------------------------------------------------

def _is_actionable(constraint: dict) -> bool:
    return constraint.get("type", "") in ACTIONABLE_TYPES


def build_aligned_pairs(
    results: list[dict],
    chains_real_dir: Path,
    chains_shuffled_dir: Path,
) -> dict[str, dict]:
    """
    Align real and shuffled results by (base_chain_id, model, eval_seed).

    Returns dict keyed by alignment_key containing paired real and shuffled
    result dicts.

    Pair structure (SPEC §Pair alignment):
      real chain_id: base_chain_id
      shuffled chain_id: base_chain_id + "_shuffled_" + shuffle_seed
      Three shuffled variants per real chain (seeds 42, 1337, 7919).
    """
    real_results: dict[str, dict] = {}
    shuffled_results: dict[str, list[dict]] = defaultdict(list)

    for r in results:
        chain_id = r.get("chain_id", "")
        model = r.get("model", "")
        seed = r.get("seed", 0)

        if "_shuffled_" in chain_id:
            base_id = chain_id.split("_shuffled_")[0]
            key = f"{base_id}|{model}|{seed}"
            shuffled_results[key].append(r)
        else:
            key = f"{chain_id}|{model}|{seed}"
            real_results[key] = r

    pairs = {}
    for key, real_r in real_results.items():
        shuffled_list = shuffled_results.get(key, [])
        for shuf_r in shuffled_list:
            pair_key = f"{key}|{shuf_r['chain_id']}"
            pairs[pair_key] = {"real": real_r, "shuffled": shuf_r}

    return pairs


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def score_all(
    results_dir: Path,
    dist_paths: dict[str, Path],
    chains_real_dir: Path,
    chains_shuffled_dir: Path,
    bonferroni_divisor: int = 4,
) -> dict[str, Any]:
    """
    Score all results from results_dir against reference distributions.

    bonferroni_divisor: 4 (Phase 1 only) or 8 (Phase 1 + Phase 2).
    """
    # Load reference distributions
    dists: dict[str, ReferenceDistribution] = {}
    for source, path in dist_paths.items():
        if path and path.exists():
            dists[source] = ReferenceDistribution.load(path)
        else:
            print(f"[scorer] WARN: no reference distribution for {source} at {path}")

    # Load all result JSON files
    results: list[dict] = []
    for result_path in sorted(results_dir.rglob("*.json")):
        try:
            with open(result_path) as f:
                results.append(json.load(f))
        except Exception as e:
            print(f"[scorer] failed to load {result_path}: {e}")

    if not results:
        return {"error": "no results found", "n_results": 0}

    # Load chains (real and shuffled). Use exact filename match — the previous
    # glob pattern f"{chain_id}*.jsonl" was too permissive and silently picked
    # the first match if multiple files matched (e.g., chess_standard_real_0001
    # could match chess_standard_real_00010 if such a chain existed).
    def _load_chain_dict(chain_id: str, source: str, base_dir: Path) -> dict | None:
        path = (base_dir / source) / f"{chain_id}.jsonl"
        if not path.exists():
            return None
        try:
            with path.open() as f:
                return json.loads(f.readline().strip())
        except Exception:
            return None

    # ----- Phase 1: score each result individually -----------------------
    # per_result: alignment_key -> scored result with l1/l2/condition/etc.
    # alignment_key = (base_chain_id, model, source, config_key, condition,
    #                  shuffle_seed_suffix)
    # where condition ∈ {"real", "shuffled"} and shuffle_seed_suffix is "" for
    # real, or e.g. "_shuffled_42" for shuffled. The (real, shuffled-N) pair
    # share base_chain_id + model + source + config_key.

    # For each real chain at each eval_config, we expect exactly 1 real result
    # and 3 shuffled results (one per shuffle seed). McNemar's needs paired
    # binary outcomes — we expand the real outcome to match the 3 shuffled
    # partners (per SPEC §Pair alignment, alignment is by base_chain_id + model
    # + eval_seed; the 3 shuffle variants each form their own pair against
    # the same real outcome).

    real_scored: dict[tuple, dict] = {}                     # (base, model, src, cfg) -> scored
    shuf_scored: dict[tuple, list[dict]] = defaultdict(list)  # (base, model, src, cfg) -> [scored,…]

    skipped = 0
    for r in results:
        chain_id = r.get("chain_id", "")
        model = r.get("model", "")
        source = r.get("source", "")
        cutoff_k = r.get("cutoff_k", 0)
        temperature = r.get("temperature", 0.0)
        seed = r.get("seed", 42)
        response = r.get("response", "")

        if source not in dists:
            skipped += 1
            continue

        dist = dists[source]
        is_shuffled = "_shuffled_" in chain_id
        base_id = chain_id.split("_shuffled_")[0] if is_shuffled else chain_id

        # Load corresponding chain
        load_dir = chains_shuffled_dir if is_shuffled else chains_real_dir
        chain = _load_chain_dict(chain_id, source, load_dir)
        if chain is None:
            skipped += 1
            continue

        l1 = score_layer1(response, chain, cutoff_k, dist)
        l2 = score_layer2(response, chain, cutoff_k, dist)

        config_key = f"T{temperature}_seed{seed}"
        align_key = (base_id, model, source, config_key)
        scored_record = {
            "l1_match": l1["top_k_match"],
            "l1_constraint_type": l1.get("constraint_type", ""),
            "l2_coupled": l2["coupled"],
        }
        if is_shuffled:
            shuf_scored[align_key].append(scored_record)
        else:
            real_scored[align_key] = scored_record

    if skipped:
        print(f"[scorer] skipped {skipped} results (missing chain or distribution)")

    # ----- Phase 2: build paired buckets per cell × config -----------------
    # For each (model, source, config_key), iterate over base chains; for
    # each base chain pair the real outcome with EACH of its shuffled partners.
    # This produces 3 pairs per base chain (one per shuffle seed) per
    # cell × config × model.
    per_cell: dict[tuple, dict[str, list]] = defaultdict(
        lambda: {
            "real_l1": [], "shuffled_l1": [],
            "real_l1_actionable": [], "shuffled_l1_actionable": [],
            "real_l2": [], "shuffled_l2": [],
            "missing_real": 0,
            "missing_shuffled": 0,
            "n_base_chains": 0,
        }
    )

    all_align_keys = set(real_scored.keys()) | set(shuf_scored.keys())
    for align_key in all_align_keys:
        base_id, model, source, config_key = align_key
        cell_key = (model, source, config_key)
        bucket = per_cell[cell_key]

        real = real_scored.get(align_key)
        shufs = shuf_scored.get(align_key, [])

        if real is None:
            bucket["missing_real"] += len(shufs) if shufs else 1
            continue
        if not shufs:
            bucket["missing_shuffled"] += 1
            continue

        bucket["n_base_chains"] += 1
        for shuf in shufs:
            # Layer 1 — both-actionable filter applied at PAIR level:
            # include in actionable subset iff BOTH real and shuffled cutoff
            # constraints are in ACTIONABLE_TYPES (SPEC §Both-actionable filter).
            both_actionable = (
                real["l1_constraint_type"] in ACTIONABLE_TYPES
                and shuf["l1_constraint_type"] in ACTIONABLE_TYPES
            )

            if real["l1_match"] is not None and shuf["l1_match"] is not None:
                bucket["real_l1"].append(real["l1_match"])
                bucket["shuffled_l1"].append(shuf["l1_match"])
                if both_actionable:
                    bucket["real_l1_actionable"].append(real["l1_match"])
                    bucket["shuffled_l1_actionable"].append(shuf["l1_match"])

            # Layer 2 (continuous): only append when both sides have valid scores
            # (score_layer2 returns None for invalid cutoffs to avoid sentinel-zero
            # pollution of the paired t-test).
            if real["l2_coupled"] is not None and shuf["l2_coupled"] is not None:
                bucket["real_l2"].append(real["l2_coupled"])
                bucket["shuffled_l2"].append(shuf["l2_coupled"])

    # Build paired McNemar results per cell
    cell_results: dict[str, dict] = {}
    for (model, source, config_key), bucket in per_cell.items():
        l1_test = mcnemar_test(bucket["real_l1"], bucket["shuffled_l1"])
        l1_act_test = mcnemar_test(
            bucket["real_l1_actionable"], bucket["shuffled_l1_actionable"]
        )
        l2_test = paired_ttest(bucket["real_l2"], bucket["shuffled_l2"])

        gap = l1_act_test.get("gap", 0.0) if "error" not in l1_act_test else 0.0
        pval_raw = l1_act_test.get("p_value", 1.0) if "error" not in l1_act_test else 1.0
        pval_bonferroni = apply_bonferroni(pval_raw, bonferroni_divisor)

        label = f"{model}::{source}::{config_key}"
        cell_results[label] = {
            "layer1": l1_test,
            "layer1_actionable": l1_act_test,
            "layer1_actionable_bonferroni": {
                **l1_act_test,
                "p_value_bonferroni": round(pval_bonferroni, 6),
                "bonferroni_divisor": bonferroni_divisor,
                "significant_bonferroni": bool(pval_bonferroni < 0.05),
            },
            "layer2": l2_test,
            "outcome_tier": classify_outcome_tier(gap, pval_bonferroni),
            "diagnostics": {
                "n_base_chains": bucket["n_base_chains"],
                "n_pairs_total": len(bucket["real_l1"]),
                "n_pairs_actionable": len(bucket["real_l1_actionable"]),
                "missing_real": bucket["missing_real"],
                "missing_shuffled": bucket["missing_shuffled"],
            },
        }

    return {
        "n_results": len(results),
        "bonferroni_divisor": bonferroni_divisor,
        "per_cell": cell_results,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="src.scorer")
    parser.add_argument("--results", type=Path, default=Path("results/raw"))
    parser.add_argument("--dist-chess-standard", type=Path, default=None)
    parser.add_argument("--dist-chess960", type=Path, default=None)
    parser.add_argument("--dist-checkers-american", type=Path, default=None)
    parser.add_argument("--dist-draughts-intl", type=Path, default=None)
    parser.add_argument("--chains-real", type=Path, default=Path("chains/real"))
    parser.add_argument("--chains-shuffled", type=Path, default=Path("chains/shuffled"))
    parser.add_argument("--bonferroni-divisor", type=int, default=4,
                        choices=[4, 8])
    parser.add_argument("--out", type=Path, default=Path("results/scored.json"))
    args = parser.parse_args()

    dist_paths: dict[str, Path | None] = {
        "chess_standard": args.dist_chess_standard,
        "chess960": args.dist_chess960,
        "checkers_american": args.dist_checkers_american,
        "draughts_intl": args.dist_draughts_intl,
    }
    dist_paths = {k: v for k, v in dist_paths.items() if v is not None}

    if not dist_paths:
        parser.error("At least one --dist-* argument is required")

    scored = score_all(
        args.results, dist_paths,
        args.chains_real, args.chains_shuffled,
        bonferroni_divisor=args.bonferroni_divisor,
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(scored, f, indent=2)

    print(f"\nResults written to {args.out}")

    print("\n=== Per-cell results ===")
    for label, s in sorted(scored.get("per_cell", {}).items()):
        l1a = s.get("layer1_actionable_bonferroni", {})
        gap = l1a.get("gap", "N/A")
        p_bon = l1a.get("p_value_bonferroni", "N/A")
        tier = s.get("outcome_tier", "?")
        sig = "*" if l1a.get("significant_bonferroni") else " "
        print(f"  {label:55s}  gap={gap:>7}  p_bon={p_bon:>8}  {sig} {tier}")
