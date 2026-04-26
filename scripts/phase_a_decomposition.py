"""
Phase A — Step A5: produce the 3-column decomposition table.

Columns:
  1. Pre-registered (original reference)            — pulled from results/phase1_v31_scored_full.json
  2. Trivial-coincidence filtered (original ref)    — computed: exclude pairs where shuffled has target==last_shown
  3. Downweighted reference (Option B)              — pulled from results/phase_a/a4_rescored.json

The trivial-coincidence-filtered column is computed from existing data
using the existing scorer logic; no additional API calls.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.reference import ReferenceDistribution, extract_entity_from_constraint
from src.normalize import normalize_action
from src.scorer import (
    ACTIONABLE_TYPES, mcnemar_test, apply_bonferroni, classify_outcome_tier,
)

CELLS = ("chess_standard", "chess960", "checkers_american", "draughts_intl")
PRIMARY_CONFIG_KEY = "T0.0_seed42"
TOP_K = 3


def _load_chain(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.open().readline().strip())


def compute_filtered_gap(cell: str) -> dict:
    """Compute the trivial-coincidence-filtered gap (Layer 1 actionable)
    using the original (non-downweighted) reference. Excludes pairs where
    shuffled chain has target_entity == last_shown_entity."""
    dist = ReferenceDistribution.load(PROJECT_ROOT / "data" / f"reference_{cell}.pkl")
    chains_real = PROJECT_ROOT / "chains" / "real" / cell
    chains_shuf = PROJECT_ROOT / "chains" / "shuffled" / cell
    results = PROJECT_ROOT / "results" / "raw" / "phase1" / cell

    # Index real and shuffled responses by alignment
    real_scored: dict[tuple, dict] = {}
    shuf_scored: dict[tuple, list[dict]] = defaultdict(list)

    for path in results.glob("*.json"):
        r = json.loads(path.read_text())
        chain_id = r["chain_id"]
        is_shuf = "_shuffled_" in chain_id
        base = chain_id.split("_shuffled_")[0] if is_shuf else chain_id
        cfg = f"T{r['temperature']}_seed{r['seed']}"
        load_dir = chains_shuf if is_shuf else chains_real
        chain = _load_chain(load_dir / f"{chain_id}.jsonl")
        if chain is None:
            continue
        cs = chain["constraints"]
        cutoff_k = chain["cutoff_k"]
        if cutoff_k <= 0 or cutoff_k >= len(cs):
            continue
        actions, _ = dist.lookup_with_backoff(cs, cutoff_k, k=TOP_K)
        norm_resp = normalize_action(r["response"])
        norm_top = [normalize_action(a) for a in actions]
        l1_match = int(norm_resp in norm_top) if norm_top else None
        ctype = cs[cutoff_k].get("type", "")
        # Trivial check (only meaningful for shuffled)
        last_ent = extract_entity_from_constraint(cs[cutoff_k - 1])
        targ_ent = extract_entity_from_constraint(cs[cutoff_k])
        is_trivial = (last_ent == targ_ent and last_ent is not None)
        rec = {
            "l1_match": l1_match,
            "constraint_type": ctype,
            "is_trivial_adjacency": is_trivial,
        }
        align_key = (base, r["model"], r["source"], cfg)
        if is_shuf:
            shuf_scored[align_key].append(rec)
        else:
            real_scored[align_key] = rec

    real_l1 = []
    shuf_l1 = []
    real_l1_act = []
    shuf_l1_act = []

    for align_key in set(real_scored) | set(shuf_scored):
        if align_key[3] != PRIMARY_CONFIG_KEY:
            continue
        real = real_scored.get(align_key)
        shufs = shuf_scored.get(align_key, [])
        if real is None or not shufs:
            continue
        for shuf in shufs:
            # FILTER: exclude pairs where shuffled is trivially adjacent
            if shuf["is_trivial_adjacency"]:
                continue
            if real["l1_match"] is None or shuf["l1_match"] is None:
                continue
            real_l1.append(real["l1_match"])
            shuf_l1.append(shuf["l1_match"])
            if (real["constraint_type"] in ACTIONABLE_TYPES
                    and shuf["constraint_type"] in ACTIONABLE_TYPES):
                real_l1_act.append(real["l1_match"])
                shuf_l1_act.append(shuf["l1_match"])

    test = mcnemar_test(real_l1_act, shuf_l1_act)
    return {
        "n_pairs_actionable": len(real_l1_act),
        "gap": test.get("gap"),
        "p_value": test.get("p_value"),
    }


def main() -> int:
    # Column 1: pull from existing scored
    scored_full = json.loads((PROJECT_ROOT / "results" / "phase1_v31_scored_full.json").read_text())
    col1 = {}
    for label, cell_data in scored_full.get("primary_cells", {}).items():
        cell = label.replace("haiku::", "")
        l1ab = cell_data.get("layer1_actionable_bonferroni", {})
        col1[cell] = {
            "gap": l1ab.get("gap"),
            "p_value_bon": l1ab.get("p_value_bonferroni"),
            "n_pairs_actionable": cell_data.get("diagnostics", {}).get("n_pairs_actionable"),
            "outcome_tier": cell_data.get("outcome_tier"),
        }

    # Column 2: compute filtered gap per cell
    col2 = {}
    for cell in CELLS:
        result = compute_filtered_gap(cell)
        col2[cell] = result

    # Column 3: pull from a4_rescored.json
    a4 = json.loads((PROJECT_ROOT / "results" / "phase_a" / "a4_rescored.json").read_text())
    col3 = {}
    for label, cell_data in a4.get("primary_cells", {}).items():
        cell = label.replace("haiku::", "")
        l1ab = cell_data.get("layer1_actionable_bonferroni", {})
        col3[cell] = {
            "gap": l1ab.get("gap"),
            "p_value_bon": l1ab.get("p_value_bonferroni"),
            "n_pairs_actionable": cell_data.get("diagnostics", {}).get("n_pairs_actionable"),
            "outcome_tier": cell_data.get("outcome_tier"),
        }

    # Build the table
    rows = []
    for cell in CELLS:
        rows.append({
            "cell": cell,
            "col1_pre_registered": col1.get(cell, {}),
            "col2_trivial_filtered": col2.get(cell, {}),
            "col3_downweighted": col3.get(cell, {}),
        })

    out = {
        "phase": "phase_a_a5",
        "rows": rows,
        "criterion": {
            "primary_cell": "chess_standard",
            "metric": "Layer 1 actionable gap (col3_downweighted)",
            "threshold_succeed": 0.02,
            "threshold_fail": -0.02,
        },
    }

    # Apply criterion to chess_standard col3 gap
    cs_col3_gap = col3.get("chess_standard", {}).get("gap")
    if cs_col3_gap is None:
        out["criterion"]["result"] = "ERROR — chess_standard col3 gap missing"
    elif cs_col3_gap >= 0.02:
        out["criterion"]["result"] = "SUCCEEDED"
    elif cs_col3_gap <= -0.02:
        out["criterion"]["result"] = "FAILED"
    else:
        out["criterion"]["result"] = "AMBIGUOUS"
    out["criterion"]["chess_standard_col3_gap"] = cs_col3_gap

    # Save JSON
    out_path = PROJECT_ROOT / "results" / "phase_a" / "decomposition_table.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, default=str))

    # Markdown rendering
    def fmt_gap(d):
        g = d.get("gap")
        if g is None:
            return "  N/A"
        if isinstance(g, str):
            try: g = float(g)
            except: return g
        return f"{g:+.4f}"

    def fmt_n(d):
        return d.get("n_pairs_actionable", "?")

    md_lines = [
        "# Phase A — Decomposition Table\n",
        "Layer 1 actionable gap (real_match_rate − shuffled_match_rate), primary config (T=0.0/seed=42).\n",
        "| Cell | Pre-registered (original ref) | Trivial-coincidence filtered | Downweighted reference (Option B) |",
        "|---|---|---|---|",
    ]
    for cell in CELLS:
        c1 = col1.get(cell, {})
        c2 = col2.get(cell, {})
        c3 = col3.get(cell, {})
        md_lines.append(
            f"| **{cell}** | "
            f"{fmt_gap(c1)} (n={fmt_n(c1)}) | "
            f"{fmt_gap(c2)} (n={fmt_n(c2)}) | "
            f"{fmt_gap(c3)} (n={fmt_n(c3)}) |"
        )
    md_lines.extend([
        "",
        f"**Pre-committed success criterion**: chess_standard gap (col 3) ≥ +0.02 = SUCCESS",
        f"**Observed**: chess_standard col 3 gap = {fmt_gap(col3.get('chess_standard', {}))}",
        f"**Result**: {out['criterion']['result']}",
        "",
    ])
    md_path = PROJECT_ROOT / "results" / "phase_a" / "decomposition_table.md"
    md_path.write_text("\n".join(md_lines) + "\n")

    # Print
    print("=" * 90)
    print("PHASE A — DECOMPOSITION TABLE")
    print("=" * 90)
    print(f"{'Cell':<22s} {'Col1: pre-reg':>16s} {'Col2: filtered':>16s} {'Col3: downwght':>16s}")
    print("-" * 90)
    for cell in CELLS:
        c1 = fmt_gap(col1.get(cell, {}))
        c2 = fmt_gap(col2.get(cell, {}))
        c3 = fmt_gap(col3.get(cell, {}))
        print(f"{cell:<22s} {c1:>16s} {c2:>16s} {c3:>16s}")
    print()
    print(f"chess_standard col3 gap = {col3.get('chess_standard', {}).get('gap')}")
    print(f"Pre-committed criterion: ≥ +0.02 → SUCCESS / between -0.02 and +0.02 → AMBIGUOUS / ≤ -0.02 → FAIL")
    print(f"RESULT: {out['criterion']['result']}")
    print()
    print(f"JSON → {out_path.relative_to(PROJECT_ROOT)}")
    print(f"MD   → {md_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
