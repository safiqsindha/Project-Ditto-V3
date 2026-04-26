"""
v4 Cell 1 — methodology robustness analysis.

Loads v3's existing Phase 1 raw responses for all four cells, applies four
statistical methodologies, and produces a comparison table:

  Methodology 1: two-sample proportion z-test (v1's original)
  Methodology 2: paired McNemar, no actionable filter (v2's corrected)
  Methodology 3: paired McNemar with actionable filter, Bonferroni (v3 pre-registered)
                 — pulled from results/phase1_v31_scored_full.json, NOT recomputed
  Methodology 4: same as 3 but no Bonferroni (sensitivity)

Outputs:
  results/v4/cell_1_robustness.json
  results/v4/cell_1_robustness_table.md

Pre-committed: do NOT add a fifth methodology. Do NOT change v3's
pre-registered classification regardless of findings. This is sensitivity
characterization, not classification revision.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.normalize import normalize_action
from src.reference import ReferenceDistribution
from src.scorer import ACTIONABLE_TYPES
from src.v4_scorer_robustness import (
    BONFERRONI_DIVISOR,
    PRIMARY_CONFIG_KEY,
    TOP_K,
    classify_methodology_result,
    score_mcnemar_actionable_from_existing,
    score_mcnemar_actionable_no_bonferroni,
    score_mcnemar_no_filter,
    score_two_sample_proportion,
)


CELLS = ("chess_standard", "chess960", "checkers_american", "draughts_intl")


def _load_chain(path: Path):
    if not path.exists():
        return None
    return json.loads(path.open().readline().strip())


def collect_outcomes_for_cell(cell: str) -> dict[str, list]:
    """Walk v3's Phase 1 raw responses for primary config; produce:
       - real_outcomes: list of l1_match for real chains (n=1200 expected)
       - shuffled_outcomes: list of l1_match for shuffled chains (n=3600 expected)
       - paired_real_l1, paired_shuf_l1: aligned pair lists (each n=3600 expected)
       - paired_real_l1_act, paired_shuf_l1_act: same, restricted to both-actionable

    Uses the v3 pre-registered scoring logic (original reference,
    cutoff_k constraint as prediction target). Same logic as src/scorer.py.
    """
    dist_path = PROJECT_ROOT / "data" / f"reference_{cell}.pkl"
    dist = ReferenceDistribution.load(dist_path)

    chains_real = PROJECT_ROOT / "chains" / "real" / cell
    chains_shuf = PROJECT_ROOT / "chains" / "shuffled" / cell
    results = PROJECT_ROOT / "results" / "raw" / "phase1" / cell

    # First pass: score each result individually (mirroring src/scorer.py)
    real_scored: dict[tuple, dict] = {}
    shuf_scored: dict[tuple, list[dict]] = defaultdict(list)

    for path in results.glob("*.json"):
        r = json.loads(path.read_text())
        cfg = f"T{r['temperature']}_seed{r['seed']}"
        if cfg != PRIMARY_CONFIG_KEY:
            continue
        chain_id = r["chain_id"]
        is_shuf = "_shuffled_" in chain_id
        base_id = chain_id.split("_shuffled_")[0] if is_shuf else chain_id
        load_dir = chains_shuf if is_shuf else chains_real
        chain = _load_chain(load_dir / f"{chain_id}.jsonl")
        if chain is None:
            continue
        cs = chain["constraints"]
        cutoff_k = chain["cutoff_k"]
        if cutoff_k <= 0 or cutoff_k >= len(cs):
            continue
        actions, _level = dist.lookup_with_backoff(cs, cutoff_k, k=TOP_K)
        norm_resp = normalize_action(r["response"])
        norm_top = [normalize_action(a) for a in actions]
        l1_match = int(norm_resp in norm_top) if norm_top else None
        ctype = cs[cutoff_k].get("type", "")
        rec = {"l1_match": l1_match, "ctype": ctype}
        align = (base_id, r["model"], r["source"])
        if is_shuf:
            shuf_scored[align].append(rec)
        else:
            real_scored[align] = rec

    # Methodology 1 (two-sample): just need flat lists, no pairing
    real_outcomes = []
    shuffled_outcomes = []
    for align, rec in real_scored.items():
        if rec["l1_match"] is not None:
            real_outcomes.append(rec["l1_match"])
    for align, recs in shuf_scored.items():
        for rec in recs:
            if rec["l1_match"] is not None:
                shuffled_outcomes.append(rec["l1_match"])

    # Methodology 2 + 4: paired (each base × 3 shuffles = 3 pairs)
    paired_real_l1 = []
    paired_shuf_l1 = []
    paired_real_l1_act = []
    paired_shuf_l1_act = []

    for align in set(real_scored) | set(shuf_scored):
        real = real_scored.get(align)
        shufs = shuf_scored.get(align, [])
        if real is None or not shufs:
            continue
        for shuf in shufs:
            if real["l1_match"] is None or shuf["l1_match"] is None:
                continue
            paired_real_l1.append(real["l1_match"])
            paired_shuf_l1.append(shuf["l1_match"])
            both_act = (real["ctype"] in ACTIONABLE_TYPES
                        and shuf["ctype"] in ACTIONABLE_TYPES)
            if both_act:
                paired_real_l1_act.append(real["l1_match"])
                paired_shuf_l1_act.append(shuf["l1_match"])

    return {
        "real_outcomes": real_outcomes,
        "shuffled_outcomes": shuffled_outcomes,
        "paired_real_l1": paired_real_l1,
        "paired_shuf_l1": paired_shuf_l1,
        "paired_real_l1_act": paired_real_l1_act,
        "paired_shuf_l1_act": paired_shuf_l1_act,
    }


def main() -> int:
    out_dir = PROJECT_ROOT / "results" / "v4"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary: dict = {
        "study": "v4 cell 1 — statistical methodology robustness",
        "framing": "Apply 4 different statistical methodologies to v3's existing "
                   "primary-config response data. Pure code, no API calls. Does "
                   "NOT change v3's pre-registered classification.",
        "primary_config": PRIMARY_CONFIG_KEY,
        "methodologies": {
            "1_two_sample_proportion": {
                "description": "v1's original methodology: z-test on independent samples",
                "treats_pair_structure": False,
                "bonferroni_correction": False,
            },
            "2_mcnemar_no_filter": {
                "description": "v2's corrected methodology: paired McNemar, all pairs",
                "treats_pair_structure": True,
                "bonferroni_correction": True,
                "bonferroni_divisor": BONFERRONI_DIVISOR,
            },
            "3_mcnemar_actionable_pre_registered": {
                "description": "v3 pre-registered: paired McNemar, both-actionable filter, Bonferroni",
                "treats_pair_structure": True,
                "bonferroni_correction": True,
                "bonferroni_divisor": BONFERRONI_DIVISOR,
                "source": "pulled from results/phase1_v31_scored_full.json (not recomputed)",
            },
            "4_mcnemar_actionable_no_bonferroni": {
                "description": "Same as 3 but no Bonferroni (sensitivity)",
                "treats_pair_structure": True,
                "bonferroni_correction": False,
            },
        },
        "per_cell": {},
    }

    scored_full_path = PROJECT_ROOT / "results" / "phase1_v31_scored_full.json"

    for cell in CELLS:
        print(f"\n=== {cell} ===")
        outcomes = collect_outcomes_for_cell(cell)

        # Methodology 1
        m1 = score_two_sample_proportion(
            outcomes["real_outcomes"],
            outcomes["shuffled_outcomes"],
        )
        m1["tier_at_raw_p"] = classify_methodology_result(
            m1.get("gap"), m1.get("p_value_raw")
        )

        # Methodology 2
        m2 = score_mcnemar_no_filter(
            outcomes["paired_real_l1"],
            outcomes["paired_shuf_l1"],
        )
        m2["tier_at_bonferroni_p"] = classify_methodology_result(
            m2.get("gap"), m2.get("p_value_bonferroni")
        )

        # Methodology 3 (pulled from existing)
        m3 = score_mcnemar_actionable_from_existing(cell, scored_full_path)
        m3["tier_at_bonferroni_p"] = m3.get("tier")

        # Methodology 4
        m4 = score_mcnemar_actionable_no_bonferroni(
            outcomes["paired_real_l1_act"],
            outcomes["paired_shuf_l1_act"],
        )
        m4["tier_at_raw_p"] = classify_methodology_result(
            m4.get("gap"), m4.get("p_value_raw")
        )

        summary["per_cell"][cell] = {
            "1_two_sample_proportion": m1,
            "2_mcnemar_no_filter": m2,
            "3_mcnemar_actionable_pre_registered": m3,
            "4_mcnemar_actionable_no_bonferroni": m4,
        }

        # Per-methodology print
        for label, res in [
            ("1) two-sample prop", m1),
            ("2) mcnemar no filter", m2),
            ("3) v3 pre-reg (pulled)", m3),
            ("4) actionable no Bonf", m4),
        ]:
            gap = res.get("gap")
            p_raw = res.get("p_value_raw")
            p_bon = res.get("p_value_bonferroni")
            n = res.get("n_pairs") or res.get("n_real") or "?"
            ci_l = res.get("ci_95_lower")
            ci_h = res.get("ci_95_upper")
            tier = res.get("tier_at_raw_p") or res.get("tier_at_bonferroni_p") or res.get("tier")
            gap_s = f"{gap:+.4f}" if isinstance(gap, (int, float)) else "N/A"
            print(f"  {label:<25s} n={n:>6}  gap={gap_s}  p_raw={p_raw}  p_bon={p_bon}  "
                  f"CI=[{ci_l},{ci_h}]  {tier}")

    # ---- Save JSON ----
    out_json = out_dir / "cell_1_robustness.json"
    out_json.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nFull JSON → {out_json.relative_to(PROJECT_ROOT)}")

    # ---- Build markdown table ----
    md = [
        "# v4 Cell 1 — statistical methodology robustness table",
        "",
        "Layer 1 actionable gap (real_match_rate − shuffled_match_rate), primary config (T=0.0/seed=42).",
        "",
        f"Methodology 3 is pulled from `results/phase1_v31_scored_full.json` (not recomputed).",
        "Methodologies 1, 2, 4 are computed in this analysis.",
        "",
        "| Cell | Methodology | n | gap | p_raw | p_bonferroni | CI 95% | tier |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for cell in CELLS:
        for key, label in [
            ("1_two_sample_proportion", "1) two-sample proportion (v1)"),
            ("2_mcnemar_no_filter", "2) paired McNemar no filter (v2)"),
            ("3_mcnemar_actionable_pre_registered", "3) paired McNemar actionable+Bonf (v3 pre-reg)"),
            ("4_mcnemar_actionable_no_bonferroni", "4) paired McNemar actionable no Bonf"),
        ]:
            r = summary["per_cell"][cell][key]
            n = r.get("n_pairs") or r.get("n_real") or "?"
            gap = r.get("gap")
            p_raw = r.get("p_value_raw")
            p_bon = r.get("p_value_bonferroni")
            ci_l = r.get("ci_95_lower")
            ci_h = r.get("ci_95_upper")
            tier = r.get("tier_at_raw_p") or r.get("tier_at_bonferroni_p") or r.get("tier")

            def fmt_p(x):
                if x is None:
                    return "n/a"
                if isinstance(x, (int, float)):
                    if x < 0.001:
                        return "<0.001"
                    return f"{x:.4f}"
                return str(x)

            def fmt_g(x):
                if x is None: return "N/A"
                return f"{x:+.4f}"

            md.append(
                f"| {cell} | {label} | {n} | {fmt_g(gap)} | {fmt_p(p_raw)} | "
                f"{fmt_p(p_bon)} | [{fmt_g(ci_l)}, {fmt_g(ci_h)}] | {tier} |"
            )
    md_path = out_dir / "cell_1_robustness_table.md"
    md_path.write_text("\n".join(md) + "\n")
    print(f"Table     → {md_path.relative_to(PROJECT_ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
