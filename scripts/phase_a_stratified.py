"""
Phase A — Path 1 follow-up: stratified analysis to isolate backoff confound.

For each pair (real_X, shuf_X_seed), records the backoff level used by EACH
side. Then buckets pairs by joint (real_level, shuf_level) and computes
the Layer 1 actionable gap per bucket.

Critical question: gap restricted to pairs where real_level == shuf_level.
If that gap → 0, the residual -0.07 is explained by backoff differential
(real and shuffled were being scored against different reference granularities).
If that gap stays negative, residual signal is real and unexplained.

Run twice:
  - Against ORIGINAL reference (data/reference_{cell}.pkl)
  - Against DOWNWEIGHTED reference (data/reference_{cell}_downweighted.pkl, Option B)
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.reference import ReferenceDistribution
from src.normalize import normalize_action
from src.scorer import (
    ACTIONABLE_TYPES, mcnemar_test, apply_bonferroni,
)

CELLS = ("chess_standard", "chess960", "checkers_american", "draughts_intl")
PRIMARY_CONFIG_KEY = "T0.0_seed42"
TOP_K = 3
BONFERRONI_DIVISOR = 4


def _load_chain(path: Path):
    if not path.exists(): return None
    return json.loads(path.open().readline().strip())


def score_one(response: str, chain: dict, cutoff_k: int, dist) -> dict:
    cs = chain.get("constraints", [])
    if not cs or cutoff_k <= 0 or cutoff_k >= len(cs):
        return {"l1_match": None, "ctype": None, "level": None}
    actions, level = dist.lookup_with_backoff(cs, cutoff_k, k=TOP_K)
    norm_resp = normalize_action(response)
    norm_top = [normalize_action(a) for a in actions]
    l1_match = int(norm_resp in norm_top) if norm_top else None
    return {
        "l1_match": l1_match,
        "ctype": cs[cutoff_k].get("type", ""),
        "level": level,
    }


def run_stratified(cell: str, ref_pkl_path: Path) -> dict:
    """Score all primary-config pairs for one cell, bucket by (real_level, shuf_level)."""
    if not ref_pkl_path.exists():
        return {"error": f"missing reference: {ref_pkl_path}"}
    dist = ReferenceDistribution.load(ref_pkl_path)
    chains_real = PROJECT_ROOT / "chains" / "real" / cell
    chains_shuf = PROJECT_ROOT / "chains" / "shuffled" / cell
    results = PROJECT_ROOT / "results" / "raw" / "phase1" / cell

    real_scored: dict[tuple, dict] = {}
    shuf_scored: dict[tuple, list[dict]] = defaultdict(list)

    for path in results.glob("*.json"):
        r = json.loads(path.read_text())
        chain_id = r["chain_id"]
        cfg = f"T{r['temperature']}_seed{r['seed']}"
        if cfg != PRIMARY_CONFIG_KEY:
            continue
        is_shuf = "_shuffled_" in chain_id
        base = chain_id.split("_shuffled_")[0] if is_shuf else chain_id
        load_dir = chains_shuf if is_shuf else chains_real
        chain = _load_chain(load_dir / f"{chain_id}.jsonl")
        if chain is None: continue
        cutoff_k = chain["cutoff_k"]
        scored = score_one(r["response"], chain, cutoff_k, dist)
        align_key = (base, r["model"], r["source"])
        if is_shuf:
            shuf_scored[align_key].append(scored)
        else:
            real_scored[align_key] = scored

    # Stratified buckets: keyed by (real_level, shuf_level)
    strata: dict[tuple, dict[str, list]] = defaultdict(
        lambda: {"real_l1": [], "shuf_l1": [],
                 "real_l1_act": [], "shuf_l1_act": []}
    )
    # Also overall (all pairs, no stratification)
    overall = {"real_l1": [], "shuf_l1": [],
               "real_l1_act": [], "shuf_l1_act": []}

    for align_key in set(real_scored) | set(shuf_scored):
        real = real_scored.get(align_key)
        shufs = shuf_scored.get(align_key, [])
        if real is None or not shufs: continue
        for shuf in shufs:
            if real["l1_match"] is None or shuf["l1_match"] is None: continue
            if real["level"] is None or shuf["level"] is None: continue
            both_act = (real["ctype"] in ACTIONABLE_TYPES
                        and shuf["ctype"] in ACTIONABLE_TYPES)
            stratum = (real["level"], shuf["level"])
            strata[stratum]["real_l1"].append(real["l1_match"])
            strata[stratum]["shuf_l1"].append(shuf["l1_match"])
            overall["real_l1"].append(real["l1_match"])
            overall["shuf_l1"].append(shuf["l1_match"])
            if both_act:
                strata[stratum]["real_l1_act"].append(real["l1_match"])
                strata[stratum]["shuf_l1_act"].append(shuf["l1_match"])
                overall["real_l1_act"].append(real["l1_match"])
                overall["shuf_l1_act"].append(shuf["l1_match"])

    # Compute per-stratum metrics
    out = {"per_stratum": {}, "overall": {}, "same_level_only": {}}
    same_level_real_l1_act = []
    same_level_shuf_l1_act = []
    same_level_real_l1 = []
    same_level_shuf_l1 = []

    for stratum, bk in strata.items():
        rl, sl = stratum
        # All pairs in this stratum
        l1_test = mcnemar_test(bk["real_l1"], bk["shuf_l1"])
        l1_act_test = mcnemar_test(bk["real_l1_act"], bk["shuf_l1_act"])
        out["per_stratum"][f"real_L{rl}_shuf_L{sl}"] = {
            "n_pairs_total": len(bk["real_l1"]),
            "n_pairs_actionable": len(bk["real_l1_act"]),
            "layer1": l1_test,
            "layer1_actionable": l1_act_test,
        }
        if rl == sl:
            same_level_real_l1.extend(bk["real_l1"])
            same_level_shuf_l1.extend(bk["shuf_l1"])
            same_level_real_l1_act.extend(bk["real_l1_act"])
            same_level_shuf_l1_act.extend(bk["shuf_l1_act"])

    # Overall (no stratification)
    out["overall"] = {
        "n_pairs_total": len(overall["real_l1"]),
        "n_pairs_actionable": len(overall["real_l1_act"]),
        "layer1": mcnemar_test(overall["real_l1"], overall["shuf_l1"]),
        "layer1_actionable": mcnemar_test(overall["real_l1_act"], overall["shuf_l1_act"]),
    }

    # Same-level only (the controlled comparison)
    out["same_level_only"] = {
        "n_pairs_total": len(same_level_real_l1),
        "n_pairs_actionable": len(same_level_real_l1_act),
        "layer1": mcnemar_test(same_level_real_l1, same_level_shuf_l1),
        "layer1_actionable": mcnemar_test(same_level_real_l1_act, same_level_shuf_l1_act),
    }

    return out


def main() -> int:
    full: dict = {
        "phase": "phase_a_path1_stratified",
        "primary_config": PRIMARY_CONFIG_KEY,
        "by_reference": {"original": {}, "downweighted": {}},
    }

    for ref_kind, suffix in [("original", ""), ("downweighted", "_downweighted")]:
        for cell in CELLS:
            pkl = PROJECT_ROOT / "data" / f"reference_{cell}{suffix}.pkl"
            full["by_reference"][ref_kind][cell] = run_stratified(cell, pkl)

    out_path = PROJECT_ROOT / "results" / "phase_a" / "stratified_analysis.json"
    out_path.write_text(json.dumps(full, indent=2, default=str))

    # Print summary table per reference kind
    for ref_kind in ("original", "downweighted"):
        print(f"\n{'=' * 90}")
        print(f"REFERENCE: {ref_kind.upper()}")
        print(f"{'=' * 90}")
        print(f"{'Cell':<22s} {'overall_gap':>12s} {'overall_n':>10s} "
              f"{'samelvl_gap':>12s} {'samelvl_n':>10s} {'delta':>10s}")
        print("-" * 90)
        for cell in CELLS:
            data = full["by_reference"][ref_kind].get(cell, {})
            ov = data.get("overall", {}).get("layer1_actionable", {})
            sl = data.get("same_level_only", {}).get("layer1_actionable", {})
            ov_gap = ov.get("gap")
            ov_n = data.get("overall", {}).get("n_pairs_actionable", 0)
            sl_gap = sl.get("gap")
            sl_n = data.get("same_level_only", {}).get("n_pairs_actionable", 0)
            delta = (sl_gap - ov_gap) if (ov_gap is not None and sl_gap is not None) else None
            ov_s = f"{ov_gap:+.4f}" if isinstance(ov_gap, (int, float)) else "N/A"
            sl_s = f"{sl_gap:+.4f}" if isinstance(sl_gap, (int, float)) else "N/A"
            d_s = f"{delta:+.4f}" if delta is not None else "N/A"
            print(f"{cell:<22s} {ov_s:>12s} {ov_n:>10d} {sl_s:>12s} {sl_n:>10d} {d_s:>10s}")

        # Per-stratum table for chess_standard (the headline cell)
        print(f"\n  chess_standard {ref_kind} per-stratum (Layer 1 actionable):")
        cs = full["by_reference"][ref_kind]["chess_standard"]["per_stratum"]
        print(f"  {'(real_L, shuf_L)':<20s} {'n_act':>8s} {'gap':>10s} {'p':>10s}")
        for stratum_label in sorted(cs.keys()):
            s = cs[stratum_label]
            l1a = s.get("layer1_actionable", {})
            n_act = s.get("n_pairs_actionable", 0)
            gap = l1a.get("gap")
            p = l1a.get("p_value")
            gap_s = f"{gap:+.4f}" if isinstance(gap, (int, float)) else "N/A"
            p_s = f"{p:.4f}" if isinstance(p, (int, float)) else "N/A"
            print(f"  {stratum_label:<20s} {n_act:>8d} {gap_s:>10s} {p_s:>10s}")

    print(f"\nFull JSON → {out_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
