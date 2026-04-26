"""
Phase A — leave-one-out (LOO) rescore.

Addresses data leakage at the source:
  - When real chain X was built into the reference, its focal_action F_X
    was added to counts at all 4 levels' sigs derived from X.
  - At score time, X's focal_action is therefore in the top-3 of X's own
    state_sig at level 0 (71.2% of real chains by construction).
  - Shuffled chain X' (permuted variant of X) also derives from X but
    didn't contribute to the reference. So shuffled chains lack this
    "self-contribution" advantage that real chains have.
  - At higher backoff levels (2, 3), X's contribution is in the
    distribution that BOTH real X and shuffled X' look up. So even
    shuffled chains benefit from X's contribution — but not in a way
    aligned with their own state.

LOO policy:
  When scoring chain Y (real or shuffled) whose BASE chain is X:
  Look up the reference normally, but at lookup time subtract X's
  contribution from the counts at all levels where X contributed to
  the looked-up sig. Top-3 is recomputed on these LOO counts.

This means:
  - Real X scored against ref - X's contribution → no self-leakage
  - Shuffled X' scored against ref - X's contribution → fair LOO
  - Both real and shuffled use a reference WITHOUT their own base data

Run twice:
  - LOO + original reference (data/reference_{cell}.pkl)
  - LOO + downweighted reference (data/reference_{cell}_downweighted.pkl)

Outputs:
  results/phase_a/loo_rescored.json — full per-cell scoring under LOO
  results/phase_a/loo_decomposition.{json,md} — multi-column decomposition
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.reference import (
    ReferenceDistribution,
    extract_state_signature,
    extract_entity_from_constraint,
)
from src.normalize import normalize_action
from src.scorer import (
    ACTIONABLE_TYPES, mcnemar_test, paired_ttest, apply_bonferroni,
)


CELLS = ("chess_standard", "chess960", "checkers_american", "draughts_intl")
PRIMARY_CONFIG_KEY = "T0.0_seed42"
TOP_K = 3
BONFERRONI_DIVISOR = 4


def _load_chain(path: Path):
    if not path.exists(): return None
    return json.loads(path.open().readline().strip())


def precompute_base_contributions(cell: str) -> dict[str, dict]:
    """For each base (real) chain, compute its sigs at all levels and its focal_action."""
    chains_real = PROJECT_ROOT / "chains" / "real" / cell
    out: dict[str, dict] = {}
    for path in chains_real.glob("*.jsonl"):
        chain = json.loads(path.read_text())
        cs = chain["constraints"]
        cutoff_k = chain["cutoff_k"]
        if cutoff_k <= 0 or cutoff_k >= len(cs):
            continue
        focal = extract_entity_from_constraint(cs[cutoff_k])
        if not focal:
            continue
        sigs_by_level = {
            L: extract_state_signature(cs, cutoff_k, backoff_level=L)
            for L in range(4)
        }
        out[chain["chain_id"]] = {
            "focal": focal,
            "sigs_by_level": sigs_by_level,
        }
    return out


def lookup_with_loo(
    dist: ReferenceDistribution,
    constraints: list[dict],
    cutoff_k: int,
    base_meta: dict | None,
    k: int = TOP_K,
) -> tuple[list[str], int]:
    """
    Like lookup_with_backoff but subtracts base chain's contribution at
    each level where base's sig matches the lookup sig.

    base_meta: precomputed {focal: ..., sigs_by_level: {0,1,2,3 → sig}}
               or None to skip subtraction.
    """
    for level in range(4):
        sig = extract_state_signature(constraints, cutoff_k, backoff_level=level)
        # Copy counts at this sig (avoid mutating the reference)
        counts_at_sig = dict(dist.counts.get(sig, {}))
        if base_meta is not None:
            base_sig_at_level = base_meta["sigs_by_level"].get(level)
            base_focal = base_meta["focal"]
            if base_sig_at_level == sig and base_focal in counts_at_sig:
                counts_at_sig[base_focal] -= 1
                if counts_at_sig[base_focal] <= 0:
                    del counts_at_sig[base_focal]
        if counts_at_sig:
            sorted_actions = sorted(counts_at_sig.items(), key=lambda x: -x[1])[:k]
            return [a for a, _ in sorted_actions], level
    return [], 3


def score_one_loo(
    response: str, chain: dict, cutoff_k: int,
    dist: ReferenceDistribution, base_meta: dict | None,
):
    cs = chain.get("constraints", [])
    if not cs or cutoff_k <= 0 or cutoff_k >= len(cs):
        return None, None, None
    actions, level = lookup_with_loo(dist, cs, cutoff_k, base_meta, k=TOP_K)
    norm_resp = normalize_action(response)
    norm_top = [normalize_action(a) for a in actions]
    l1_match = int(norm_resp in norm_top) if norm_top else None
    return l1_match, cs[cutoff_k].get("type", ""), level


def run_cell(cell: str, ref_path: Path) -> dict:
    if not ref_path.exists():
        return {"error": f"missing: {ref_path}"}
    dist = ReferenceDistribution.load(ref_path)
    base_metas = precompute_base_contributions(cell)
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
        base_id = chain_id.split("_shuffled_")[0] if is_shuf else chain_id
        load_dir = chains_shuf if is_shuf else chains_real
        chain = _load_chain(load_dir / f"{chain_id}.jsonl")
        if chain is None: continue
        cutoff_k = chain["cutoff_k"]
        base_meta = base_metas.get(base_id)
        l1_match, ctype, level = score_one_loo(r["response"], chain, cutoff_k, dist, base_meta)
        align = (base_id, r["model"], r["source"])
        rec = {"l1_match": l1_match, "ctype": ctype, "level": level}
        if is_shuf:
            shuf_scored[align].append(rec)
        else:
            real_scored[align] = rec

    # Aggregate: overall, actionable, same-level, per-stratum
    real_l1, shuf_l1 = [], []
    real_l1_act, shuf_l1_act = [], []
    same_real_l1_act, same_shuf_l1_act = [], []
    real_levels, shuf_levels = [], []
    strata: dict[tuple, dict] = defaultdict(lambda: {"real": [], "shuf": []})

    for align in set(real_scored) | set(shuf_scored):
        real = real_scored.get(align)
        shufs = shuf_scored.get(align, [])
        if real is None or not shufs: continue
        for shuf in shufs:
            if real["level"] is not None: real_levels.append(real["level"])
            if shuf["level"] is not None: shuf_levels.append(shuf["level"])
            if real["l1_match"] is None or shuf["l1_match"] is None: continue
            both_act = (real["ctype"] in ACTIONABLE_TYPES
                        and shuf["ctype"] in ACTIONABLE_TYPES)
            real_l1.append(real["l1_match"])
            shuf_l1.append(shuf["l1_match"])
            if both_act:
                real_l1_act.append(real["l1_match"])
                shuf_l1_act.append(shuf["l1_match"])
                stratum = (real["level"], shuf["level"])
                strata[stratum]["real"].append(real["l1_match"])
                strata[stratum]["shuf"].append(shuf["l1_match"])
                if real["level"] == shuf["level"]:
                    same_real_l1_act.append(real["l1_match"])
                    same_shuf_l1_act.append(shuf["l1_match"])

    rl_total = len(real_levels)
    sl_total = len(shuf_levels)
    real_lvl_count = Counter(real_levels)
    shuf_lvl_count = Counter(shuf_levels)

    overall_l1 = mcnemar_test(real_l1, shuf_l1)
    overall_l1_act = mcnemar_test(real_l1_act, shuf_l1_act)
    same_l1_act = mcnemar_test(same_real_l1_act, same_shuf_l1_act)
    pval_bon = apply_bonferroni(
        overall_l1_act.get("p_value", 1.0) if "error" not in overall_l1_act else 1.0,
        BONFERRONI_DIVISOR,
    )

    return {
        "overall": {
            "n_pairs_total": len(real_l1),
            "n_pairs_actionable": len(real_l1_act),
            "layer1": overall_l1,
            "layer1_actionable": overall_l1_act,
            "p_value_bonferroni": round(pval_bon, 6),
        },
        "same_level_only": {
            "n_pairs_actionable": len(same_real_l1_act),
            "layer1_actionable": same_l1_act,
        },
        "per_stratum": {
            f"real_L{r}_shuf_L{s}": {
                "n_pairs_actionable": len(bk["real"]),
                "layer1_actionable": mcnemar_test(bk["real"], bk["shuf"]),
            }
            for (r, s), bk in strata.items()
        },
        "backoff_breakdown": {
            "real": {
                "n": rl_total,
                "level_0_pct": round((real_lvl_count.get(0, 0)/rl_total*100) if rl_total else 0, 2),
                "level_1_pct": round((real_lvl_count.get(1, 0)/rl_total*100) if rl_total else 0, 2),
                "level_2plus_pct": round(
                    ((real_lvl_count.get(2, 0)+real_lvl_count.get(3, 0))/rl_total*100)
                    if rl_total else 0, 2
                ),
                "mean_level": round(sum(real_levels)/rl_total, 4) if rl_total else None,
            },
            "shuffled": {
                "n": sl_total,
                "level_0_pct": round((shuf_lvl_count.get(0, 0)/sl_total*100) if sl_total else 0, 2),
                "level_1_pct": round((shuf_lvl_count.get(1, 0)/sl_total*100) if sl_total else 0, 2),
                "level_2plus_pct": round(
                    ((shuf_lvl_count.get(2, 0)+shuf_lvl_count.get(3, 0))/sl_total*100)
                    if sl_total else 0, 2
                ),
                "mean_level": round(sum(shuf_levels)/sl_total, 4) if sl_total else None,
            },
        },
    }


def main() -> int:
    full: dict = {
        "phase": "loo_post_hoc",
        "policy": "leave-one-out: subtract base chain contribution at lookup time",
        "framing": "post-hoc methodology investigation; NOT a Phase A retry",
        "by_reference": {"original_loo": {}, "downweighted_loo": {}},
    }

    # Original ref + LOO
    for cell in CELLS:
        full["by_reference"]["original_loo"][cell] = run_cell(
            cell, PROJECT_ROOT / "data" / f"reference_{cell}.pkl"
        )

    # Downweighted (Option B) ref + LOO
    for cell in CELLS:
        full["by_reference"]["downweighted_loo"][cell] = run_cell(
            cell, PROJECT_ROOT / "data" / f"reference_{cell}_downweighted.pkl"
        )

    out_path = PROJECT_ROOT / "results" / "phase_a" / "loo_rescored.json"
    out_path.write_text(json.dumps(full, indent=2, default=str))

    # Build comparison table
    pre = json.loads((PROJECT_ROOT / "results" / "phase1_v31_scored_full.json").read_text())
    a4 = json.loads((PROJECT_ROOT / "results" / "phase_a" / "a4_rescored.json").read_text())
    strat = json.loads((PROJECT_ROOT / "results" / "phase_a" / "stratified_analysis.json").read_text())

    print(f"\n{'='*110}")
    print(f"LOO COMPARISON TABLE (Layer 1 actionable gap, primary config)")
    print(f"{'='*110}")
    print(f"{'Cell':<22s} {'pre-reg':>10s} {'orig':>10s} {'orig+LOO':>10s} "
          f"{'orig+LOO same':>14s} {'dwt':>10s} {'dwt+LOO':>10s} {'dwt+LOO same':>14s}")
    print("-" * 110)

    rows = []
    for cell in CELLS:
        col_prereg = pre.get("primary_cells", {}).get(f"haiku::{cell}", {}) \
                       .get("layer1_actionable_bonferroni", {}).get("gap")
        # original-ref overall (no LOO) — same as pre-reg actually
        col_orig = strat.get("by_reference", {}).get("original", {}).get(cell, {}) \
                       .get("overall", {}).get("layer1_actionable", {}).get("gap")
        col_orig_loo = full["by_reference"]["original_loo"][cell] \
                       .get("overall", {}).get("layer1_actionable", {}).get("gap")
        col_orig_loo_same = full["by_reference"]["original_loo"][cell] \
                       .get("same_level_only", {}).get("layer1_actionable", {}).get("gap")
        col_dwt = a4.get("primary_cells", {}).get(f"haiku::{cell}", {}) \
                       .get("layer1_actionable_bonferroni", {}).get("gap")
        col_dwt_loo = full["by_reference"]["downweighted_loo"][cell] \
                       .get("overall", {}).get("layer1_actionable", {}).get("gap")
        col_dwt_loo_same = full["by_reference"]["downweighted_loo"][cell] \
                       .get("same_level_only", {}).get("layer1_actionable", {}).get("gap")
        def fmt(x): return f"{x:+.4f}" if isinstance(x, (int, float)) else "  N/A "
        print(f"{cell:<22s} {fmt(col_prereg):>10s} {fmt(col_orig):>10s} {fmt(col_orig_loo):>10s} "
              f"{fmt(col_orig_loo_same):>14s} {fmt(col_dwt):>10s} {fmt(col_dwt_loo):>10s} "
              f"{fmt(col_dwt_loo_same):>14s}")
        rows.append({
            "cell": cell,
            "pre_registered": col_prereg,
            "original_overall": col_orig,
            "original_loo_overall": col_orig_loo,
            "original_loo_same_level": col_orig_loo_same,
            "downweighted_overall": col_dwt,
            "downweighted_loo_overall": col_dwt_loo,
            "downweighted_loo_same_level": col_dwt_loo_same,
        })

    # Backoff breakdown comparison
    print(f"\n{'='*110}")
    print(f"BACKOFF BREAKDOWN — chess_standard primary config")
    print(f"{'='*110}")
    cs_orig_loo = full["by_reference"]["original_loo"]["chess_standard"]["backoff_breakdown"]
    cs_dwt_loo = full["by_reference"]["downweighted_loo"]["chess_standard"]["backoff_breakdown"]
    print(f"  Original ref + LOO:")
    print(f"    real: L0={cs_orig_loo['real']['level_0_pct']}%, mean={cs_orig_loo['real']['mean_level']}")
    print(f"    shuf: L0={cs_orig_loo['shuffled']['level_0_pct']}%, mean={cs_orig_loo['shuffled']['mean_level']}")
    print(f"    differential: {cs_orig_loo['real']['level_0_pct'] - cs_orig_loo['shuffled']['level_0_pct']:+.2f}pp")
    print(f"  Downweighted ref + LOO:")
    print(f"    real: L0={cs_dwt_loo['real']['level_0_pct']}%, mean={cs_dwt_loo['real']['mean_level']}")
    print(f"    shuf: L0={cs_dwt_loo['shuffled']['level_0_pct']}%, mean={cs_dwt_loo['shuffled']['mean_level']}")
    print(f"    differential: {cs_dwt_loo['real']['level_0_pct'] - cs_dwt_loo['shuffled']['level_0_pct']:+.2f}pp")

    # Save decomposition
    decomp_out = {
        "policy": "leave-one-out (subtract base chain contribution at lookup)",
        "framing": "post-hoc methodology investigation; NOT a Phase A retry",
        "rows": rows,
    }
    decomp_path = PROJECT_ROOT / "results" / "phase_a" / "loo_decomposition.json"
    decomp_path.write_text(json.dumps(decomp_out, indent=2, default=str))

    # Markdown
    def fmt(x):
        if x is None: return "N/A"
        return f"{x:+.4f}"
    md = [
        "# Phase A — Leave-one-out (LOO) decomposition table\n",
        "Layer 1 actionable gap (real_match_rate − shuffled_match_rate), primary config.\n",
        "| Cell | pre-reg | orig overall | **orig+LOO** | orig+LOO same-lvl | dwt overall | **dwt+LOO** | dwt+LOO same-lvl |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        md.append(
            f"| **{r['cell']}** | "
            f"{fmt(r['pre_registered'])} | "
            f"{fmt(r['original_overall'])} | "
            f"**{fmt(r['original_loo_overall'])}** | "
            f"{fmt(r['original_loo_same_level'])} | "
            f"{fmt(r['downweighted_overall'])} | "
            f"**{fmt(r['downweighted_loo_overall'])}** | "
            f"{fmt(r['downweighted_loo_same_level'])} |"
        )
    md_path = PROJECT_ROOT / "results" / "phase_a" / "loo_decomposition.md"
    md_path.write_text("\n".join(md) + "\n")

    print(f"\nFull JSON     → {out_path.relative_to(PROJECT_ROOT)}")
    print(f"Decomposition → {decomp_path.relative_to(PROJECT_ROOT)}")
    print(f"Markdown      → {md_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
