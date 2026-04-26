"""
Phase A — Option C rescore + stratified analysis.

Runs Phase A's A4 + Path-1-stratified analysis using the Option C
downweighted reference (data/reference_{cell}_downweighted_c.pkl).

Outputs:
  results/phase_a/option_c_rescored.json — full per-cell scoring
  results/phase_a/option_c_decomposition.{json,md} — 4-column decomposition

Framing: post-hoc methodology investigation, NOT a Phase A retry. The
pre-committed Phase A criterion (chess_standard gap ≥ +0.02 under
Option B) remains failed. Option C is informational about what
alternative cap policies look like on v3 data.
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
    ACTIONABLE_TYPES, mcnemar_test, paired_ttest, apply_bonferroni,
)


CELLS = ("chess_standard", "chess960", "checkers_american", "draughts_intl")
PRIMARY_CONFIG_KEY = "T0.0_seed42"
TOP_K = 3
BONFERRONI_DIVISOR = 4


def _load_chain(path: Path):
    if not path.exists(): return None
    return json.loads(path.open().readline().strip())


def score_one(response: str, chain: dict, cutoff_k: int, dist):
    cs = chain.get("constraints", [])
    if not cs or cutoff_k <= 0 or cutoff_k >= len(cs):
        return None, None, None
    actions, level = dist.lookup_with_backoff(cs, cutoff_k, k=TOP_K)
    norm_resp = normalize_action(response)
    norm_top = [normalize_action(a) for a in actions]
    l1_match = int(norm_resp in norm_top) if norm_top else None
    return l1_match, cs[cutoff_k].get("type", ""), level


def run_cell(cell: str, ref_path: Path) -> dict:
    if not ref_path.exists():
        return {"error": f"missing: {ref_path}"}
    dist = ReferenceDistribution.load(ref_path)
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
        l1_match, ctype, level = score_one(r["response"], chain, cutoff_k, dist)
        align = (base, r["model"], r["source"])
        rec = {"l1_match": l1_match, "ctype": ctype, "level": level}
        if is_shuf:
            shuf_scored[align].append(rec)
        else:
            real_scored[align] = rec

    # Aggregate: overall + actionable + same-level + per-stratum
    real_l1, shuf_l1 = [], []
    real_l1_act, shuf_l1_act = [], []
    same_real_l1_act, same_shuf_l1_act = [], []
    real_levels, shuf_levels = [], []
    strata: dict[tuple, dict] = defaultdict(lambda: {"real_l1_act": [], "shuf_l1_act": []})

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
                strata[stratum]["real_l1_act"].append(real["l1_match"])
                strata[stratum]["shuf_l1_act"].append(shuf["l1_match"])
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

    # Bonferroni on overall
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
                "n_pairs_actionable": len(bk["real_l1_act"]),
                "layer1_actionable": mcnemar_test(bk["real_l1_act"], bk["shuf_l1_act"]),
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
    full: dict = {"phase": "option_c_post_hoc", "per_cell": {}}
    for cell in CELLS:
        ref_path = PROJECT_ROOT / "data" / f"reference_{cell}_downweighted_c.pkl"
        full["per_cell"][cell] = run_cell(cell, ref_path)
    out_path = PROJECT_ROOT / "results" / "phase_a" / "option_c_rescored.json"
    out_path.write_text(json.dumps(full, indent=2, default=str))

    # Compose 4-column decomposition table by pulling existing data + adding col4
    pre = json.loads((PROJECT_ROOT / "results" / "phase1_v31_scored_full.json").read_text())
    a4 = json.loads((PROJECT_ROOT / "results" / "phase_a" / "a4_rescored.json").read_text())
    strat = json.loads((PROJECT_ROOT / "results" / "phase_a" / "stratified_analysis.json").read_text())

    print(f"\n{'='*100}")
    print(f"4-COLUMN DECOMPOSITION (Layer 1 actionable gap, primary config)")
    print(f"{'='*100}")
    print(f"{'Cell':<22s} {'col1: pre-reg':>14s} {'col2: trv-filt':>14s} {'col3: Opt B':>13s} "
          f"{'col4: Opt C':>13s} {'col4 same-lvl':>15s}")
    print("-" * 100)

    decomp_rows = []
    for cell in CELLS:
        col1 = pre.get("primary_cells", {}).get(f"haiku::{cell}", {})\
                  .get("layer1_actionable_bonferroni", {}).get("gap")
        # col2: from stratified original-overall already had gap at -0.187 etc. but it's not
        # the trivial-filtered. We computed that in decomposition_table.json
        try:
            decomp_table = json.loads(
                (PROJECT_ROOT / "results" / "phase_a" / "decomposition_table.json").read_text()
            )
            row = next(r for r in decomp_table["rows"] if r["cell"] == cell)
            col2 = row["col2_trivial_filtered"].get("gap")
        except Exception:
            col2 = None
        col3 = a4.get("primary_cells", {}).get(f"haiku::{cell}", {})\
                  .get("layer1_actionable_bonferroni", {}).get("gap")
        col4 = full["per_cell"][cell]["overall"]["layer1_actionable"].get("gap")
        col4_same = full["per_cell"][cell]["same_level_only"]["layer1_actionable"].get("gap")
        def fmt(x):
            if x is None: return "  N/A "
            return f"{x:+.4f}"
        print(f"{cell:<22s} {fmt(col1):>14s} {fmt(col2):>14s} {fmt(col3):>13s} "
              f"{fmt(col4):>13s} {fmt(col4_same):>15s}")
        decomp_rows.append({
            "cell": cell,
            "col1_pre_reg": col1,
            "col2_trv_filt": col2,
            "col3_option_b": col3,
            "col4_option_c": col4,
            "col4_option_c_same_level": col4_same,
        })

    # Backoff breakdown comparison: Option B vs Option C
    print(f"\n{'='*100}")
    print(f"BACKOFF BREAKDOWN — Option C vs Option B (chess_standard primary)")
    print(f"{'='*100}")
    cs_optc = full["per_cell"]["chess_standard"]["backoff_breakdown"]
    cs_optb = a4.get("backoff_rate_breakdown", {}).get("chess_standard", {}).get(PRIMARY_CONFIG_KEY, {})
    print(f"  Option B (Phase A original):")
    if cs_optb:
        print(f"    real: L0={cs_optb['real']['level_0_pct']}%, L1={cs_optb['real']['level_1_pct']}%, "
              f"L2+={cs_optb['real']['level_2plus_pct']}%, mean={cs_optb['real']['mean_level']}")
        print(f"    shuf: L0={cs_optb['shuffled']['level_0_pct']}%, L1={cs_optb['shuffled']['level_1_pct']}%, "
              f"L2+={cs_optb['shuffled']['level_2plus_pct']}%, mean={cs_optb['shuffled']['mean_level']}")
        print(f"    differential (real_L0 - shuf_L0): "
              f"{cs_optb['real']['level_0_pct'] - cs_optb['shuffled']['level_0_pct']:+.2f}pp")
    print(f"  Option C (this analysis):")
    print(f"    real: L0={cs_optc['real']['level_0_pct']}%, L1={cs_optc['real']['level_1_pct']}%, "
          f"L2+={cs_optc['real']['level_2plus_pct']}%, mean={cs_optc['real']['mean_level']}")
    print(f"    shuf: L0={cs_optc['shuffled']['level_0_pct']}%, L1={cs_optc['shuffled']['level_1_pct']}%, "
          f"L2+={cs_optc['shuffled']['level_2plus_pct']}%, mean={cs_optc['shuffled']['mean_level']}")
    print(f"    differential (real_L0 - shuf_L0): "
          f"{cs_optc['real']['level_0_pct'] - cs_optc['shuffled']['level_0_pct']:+.2f}pp")

    # Save decomposition
    decomp_out = {
        "policy": "Option C (per-sig cap to max non-resource - 1; preserve resource-only sigs)",
        "framing": "post-hoc methodology investigation; NOT a Phase A retry",
        "rows": decomp_rows,
    }
    decomp_path = PROJECT_ROOT / "results" / "phase_a" / "option_c_decomposition.json"
    decomp_path.write_text(json.dumps(decomp_out, indent=2, default=str))

    # Markdown
    def fmt(x):
        if x is None: return "N/A"
        return f"{x:+.4f}"
    md = [
        "# Phase A — Option C decomposition table\n",
        "Layer 1 actionable gap (real_match_rate − shuffled_match_rate), primary config.\n",
        "| Cell | col1: pre-registered | col2: trv-filtered | col3: Option B | col4: Option C | col4 same-level |",
        "|---|---|---|---|---|---|",
    ]
    for r in decomp_rows:
        md.append(
            f"| **{r['cell']}** | "
            f"{fmt(r['col1_pre_reg'])} | "
            f"{fmt(r['col2_trv_filt'])} | "
            f"{fmt(r['col3_option_b'])} | "
            f"{fmt(r['col4_option_c'])} | "
            f"{fmt(r['col4_option_c_same_level'])} |"
        )
    md.append("")
    md.append(f"**Pre-committed Phase A criterion**: chess_standard col3 (Option B) ≥ +0.02 → SUCCESS")
    md.append(f"**Phase A result**: col3 = {fmt(decomp_rows[0]['col3_option_b'])} → FAILED (unchanged)")
    md.append(f"**Option C result is informational** — does NOT retroactively change Phase A.")
    md_path = PROJECT_ROOT / "results" / "phase_a" / "option_c_decomposition.md"
    md_path.write_text("\n".join(md) + "\n")

    print(f"\nDecomposition → {decomp_path.relative_to(PROJECT_ROOT)}")
    print(f"Markdown      → {md_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
