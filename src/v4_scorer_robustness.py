"""
v4 Cell 1 — methodology robustness scorer.

Applies four statistical methodologies to v3's existing Phase 1 response data
to characterize how robust the `reversed` outcome is to test choice.

The four methodologies:
  1. Two-sample proportion z-test (v1's original methodology)
       - Treats real and shuffled as independent samples
       - Ignores pair structure
       - No Bonferroni correction
  2. Paired McNemar's test, no actionable filter (v2's corrected methodology)
       - All pairs included
       - Bonferroni divisor 4
  3. Paired McNemar's test with both-actionable filter (v3 pre-registered)
       - Pulled from results/phase1_v31_scored_full.json — DO NOT recompute
       - Bonferroni divisor 4
  4. Paired McNemar's test with both-actionable filter, no Bonferroni
       - Same as v3 pre-registered minus the multiple-comparison correction
       - Diagnostic: shows how much Bonferroni matters

Pure code analysis on existing data. No API calls. The existing v3 scorer
is unchanged; this module is parallel to it.

Per pre-committed plan: do NOT add a fifth methodology. If results suggest
additional analysis would be informative, document the suggestion as a
finding and require pre-registration before execution.
"""

from __future__ import annotations

import json
from collections import defaultdict
from math import sqrt
from pathlib import Path
from typing import Any

from scipy import stats

from src.scorer import (
    ACTIONABLE_TYPES,
    mcnemar_test,
    apply_bonferroni,
    classify_outcome_tier,
)


PRIMARY_CONFIG_KEY = "T0.0_seed42"
TOP_K = 3
BONFERRONI_DIVISOR = 4


# ---------------------------------------------------------------------------
# Methodology 1: two-sample proportion z-test
# ---------------------------------------------------------------------------

def score_two_sample_proportion(
    real_outcomes: list[int],
    shuffled_outcomes: list[int],
) -> dict[str, Any]:
    """
    Two-sample proportion z-test (v1's original methodology).

    Tests H0: p_real == p_shuffled. Treats real and shuffled as independent
    samples (ignores within-base-chain pair structure). 95% CI on the
    difference uses the Wald formula.

    Real and shuffled need NOT have the same length — this test handles
    unequal sample sizes (n_real=1200, n_shuf=3600 in v3).
    """
    n_r = len(real_outcomes)
    n_s = len(shuffled_outcomes)
    if n_r == 0 or n_s == 0:
        return {"methodology_name": "two_sample_proportion", "error": "empty input"}

    p_r = sum(real_outcomes) / n_r
    p_s = sum(shuffled_outcomes) / n_s
    diff = p_r - p_s

    # Pooled proportion for z-test under H0
    n_total = n_r + n_s
    p_pool = (sum(real_outcomes) + sum(shuffled_outcomes)) / n_total
    se_pool = sqrt(p_pool * (1 - p_pool) * (1 / n_r + 1 / n_s))
    if se_pool == 0:
        z_stat = 0.0
        p_value = 1.0
    else:
        z_stat = diff / se_pool
        # Two-sided p-value
        p_value = 2.0 * (1.0 - stats.norm.cdf(abs(z_stat)))

    # 95% Wald CI on the difference (uses unpooled SE — standard for CI)
    se_unpooled = sqrt(p_r * (1 - p_r) / n_r + p_s * (1 - p_s) / n_s)
    ci_low = diff - 1.96 * se_unpooled
    ci_high = diff + 1.96 * se_unpooled

    return {
        "methodology_name": "two_sample_proportion",
        "n_real": n_r,
        "n_shuffled": n_s,
        "real_rate": round(p_r, 4),
        "shuffled_rate": round(p_s, 4),
        "gap": round(diff, 4),
        "z_stat": round(z_stat, 4),
        "p_value_raw": round(p_value, 6),
        "p_value_bonferroni": None,  # pre-committed: methodology 1 has no Bonferroni
        "ci_95_lower": round(ci_low, 4),
        "ci_95_upper": round(ci_high, 4),
        "significant_05_raw": bool(p_value < 0.05),
        "significant_05_bonferroni": None,
        "test": "two_sample_proportion_ztest",
    }


# ---------------------------------------------------------------------------
# Methodology 2: paired McNemar, no actionable filter
# ---------------------------------------------------------------------------

def score_mcnemar_no_filter(
    paired_real: list[int],
    paired_shuffled: list[int],
    bonferroni_divisor: int = BONFERRONI_DIVISOR,
) -> dict[str, Any]:
    """
    Paired McNemar (continuity-corrected) on all pairs, no actionable filter.

    paired_real and paired_shuffled must be aligned (same index = paired
    real and shuffled outcome).
    """
    test = mcnemar_test(paired_real, paired_shuffled)
    if "error" in test:
        return {"methodology_name": "mcnemar_no_filter", **test}

    n = test["n_pairs"]
    b = test["b_discordant_real_match"]
    c = test["c_discordant_shuffled_match"]
    gap = test["gap"]
    # 95% CI on gap (Wald formula based on discordant pairs)
    if n > 0 and (b + c) > 0:
        gap_se = sqrt((b + c) / n**2)
        ci_low = gap - 1.96 * gap_se
        ci_high = gap + 1.96 * gap_se
    else:
        ci_low = gap
        ci_high = gap

    p_raw = test["p_value"]
    p_bon = apply_bonferroni(p_raw, bonferroni_divisor)

    return {
        "methodology_name": "mcnemar_no_filter",
        "n_pairs": n,
        "real_rate": test["real_rate"],
        "shuffled_rate": test["shuffled_rate"],
        "gap": gap,
        "p_value_raw": round(p_raw, 6),
        "p_value_bonferroni": round(p_bon, 6),
        "ci_95_lower": round(ci_low, 4),
        "ci_95_upper": round(ci_high, 4),
        "significant_05_raw": bool(p_raw < 0.05),
        "significant_05_bonferroni": bool(p_bon < 0.05),
        "bonferroni_divisor": bonferroni_divisor,
        "test": "mcnemar_continuity_corrected",
        "n11_concordant_both_match": test["n11_concordant_both_match"],
        "b_discordant_real_match": b,
        "c_discordant_shuffled_match": c,
        "n00_concordant_neither": test["n00_concordant_neither"],
    }


# ---------------------------------------------------------------------------
# Methodology 3: paired McNemar with actionable filter (v3 pre-registered)
# Pulled from existing results — DO NOT recompute.
# ---------------------------------------------------------------------------

def score_mcnemar_actionable_from_existing(
    cell: str,
    scored_full_path: Path,
) -> dict[str, Any]:
    """
    Pull v3's pre-registered result from results/phase1_v31_scored_full.json.

    Per pre-committed plan: 'pull, don't recompute' for methodology 3.
    """
    scored = json.loads(scored_full_path.read_text())
    cell_data = scored.get("primary_cells", {}).get(f"haiku::{cell}", {})
    if not cell_data:
        return {"methodology_name": "mcnemar_actionable_pre_registered",
                "error": f"no entry for haiku::{cell} in scored_full"}

    l1ab = cell_data.get("layer1_actionable_bonferroni", {})
    l1a = cell_data.get("layer1_actionable", {})
    diag = cell_data.get("diagnostics", {})

    n = l1a.get("n_pairs", 0)
    b = l1a.get("b_discordant_real_match", 0)
    c = l1a.get("c_discordant_shuffled_match", 0)
    gap = l1a.get("gap", 0.0)
    if n > 0 and (b + c) > 0:
        gap_se = sqrt((b + c) / n**2)
        ci_low = gap - 1.96 * gap_se
        ci_high = gap + 1.96 * gap_se
    else:
        ci_low = gap
        ci_high = gap

    return {
        "methodology_name": "mcnemar_actionable_pre_registered",
        "n_pairs": n,
        "real_rate": l1a.get("real_rate"),
        "shuffled_rate": l1a.get("shuffled_rate"),
        "gap": gap,
        "p_value_raw": l1a.get("p_value"),
        "p_value_bonferroni": l1ab.get("p_value_bonferroni"),
        "ci_95_lower": round(ci_low, 4),
        "ci_95_upper": round(ci_high, 4),
        "significant_05_raw": l1a.get("significant_05"),
        "significant_05_bonferroni": l1ab.get("significant_bonferroni"),
        "bonferroni_divisor": l1ab.get("bonferroni_divisor"),
        "test": "mcnemar_continuity_corrected",
        "tier": cell_data.get("outcome_tier"),
        "n_pairs_total": diag.get("n_pairs_total"),
        "n_pairs_actionable": diag.get("n_pairs_actionable"),
        "source": "pulled from results/phase1_v31_scored_full.json",
    }


# ---------------------------------------------------------------------------
# Methodology 4: paired McNemar with actionable filter, no Bonferroni
# ---------------------------------------------------------------------------

def score_mcnemar_actionable_no_bonferroni(
    paired_real_actionable: list[int],
    paired_shuffled_actionable: list[int],
) -> dict[str, Any]:
    """
    Same as v3 pre-registered methodology, but no Bonferroni correction.

    Diagnostic: shows how much the Bonferroni correction matters.
    """
    test = mcnemar_test(paired_real_actionable, paired_shuffled_actionable)
    if "error" in test:
        return {"methodology_name": "mcnemar_actionable_no_bonferroni", **test}

    n = test["n_pairs"]
    b = test["b_discordant_real_match"]
    c = test["c_discordant_shuffled_match"]
    gap = test["gap"]
    if n > 0 and (b + c) > 0:
        gap_se = sqrt((b + c) / n**2)
        ci_low = gap - 1.96 * gap_se
        ci_high = gap + 1.96 * gap_se
    else:
        ci_low = gap
        ci_high = gap

    p_raw = test["p_value"]
    return {
        "methodology_name": "mcnemar_actionable_no_bonferroni",
        "n_pairs": n,
        "real_rate": test["real_rate"],
        "shuffled_rate": test["shuffled_rate"],
        "gap": gap,
        "p_value_raw": round(p_raw, 6),
        "p_value_bonferroni": None,
        "ci_95_lower": round(ci_low, 4),
        "ci_95_upper": round(ci_high, 4),
        "significant_05_raw": bool(p_raw < 0.05),
        "significant_05_bonferroni": None,
        "test": "mcnemar_continuity_corrected",
        "n11_concordant_both_match": test["n11_concordant_both_match"],
        "b_discordant_real_match": b,
        "c_discordant_shuffled_match": c,
        "n00_concordant_neither": test["n00_concordant_neither"],
    }


# ---------------------------------------------------------------------------
# Tier classification helper for non-pre-registered methodologies
# ---------------------------------------------------------------------------

def classify_methodology_result(gap: float | None, p_value: float | None) -> str:
    """Apply v3's outcome tier thresholds to a gap+p combination.

    For methodologies without Bonferroni correction, use the raw p-value;
    for methodologies with Bonferroni, the caller should pass the corrected p.
    """
    if gap is None or p_value is None:
        return "unknown"
    return classify_outcome_tier(gap, p_value)
