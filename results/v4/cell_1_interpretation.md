# v4 Cell 1 — Interpretation

**Study**: apply 4 statistical methodologies to v3's existing primary-config
response data; characterize how robust the `reversed` outcome is to test choice.

**Pre-committed**: this analysis does NOT change v3's pre-registered classification.
v3 remains `reversed` per pre-registration regardless of findings here. This is
sensitivity characterization, not classification revision.

---

## Headline finding

The four methodologies split into TWO regimes by point estimate, with the
cleavage being the both-actionable filter:

| Cell | M1 (no filter) | M2 (no filter) | M3 (with filter) | M4 (with filter) | filter flips? |
|---|---|---|---|---|---|
| chess_standard | -0.043 | -0.043 | -0.187 | -0.187 | no (amplifies) |
| chess960 | -0.038 | -0.038 | -0.231 | -0.231 | no (amplifies) |
| **checkers_american** | **+0.039** | **+0.039** | **-0.115** | **-0.115** | **YES** |
| draughts_intl | -0.016 | -0.016 | -0.155 | -0.155 | no (amplifies) |

Within each regime (with vs without filter), point estimates are identical
across methodologies — the difference between M1 and M2 is purely in test
assumptions / pair handling, not in the gap itself; same for M3 and M4
(Bonferroni vs raw).

---

## Per-cell results applying the pre-committed interpretation framework

### chess_standard — `Robust reversed`

| Methodology | gap | p_raw | p_bon | tier |
|---|---|---|---|---|
| 1) two-sample proportion (v1) | -0.0431 | <0.001 | n/a | reversed |
| 2) paired McNemar no filter (v2) | -0.0431 | <0.001 | <0.001 | reversed |
| 3) v3 pre-reg actionable+Bonf | -0.1871 | <0.001 | <0.001 | reversed |
| 4) actionable no Bonf | -0.1871 | <0.001 | n/a | reversed |

All four methodologies show negative gap at significance. The magnitude
varies substantially (-0.043 vs -0.187), but the direction does not. This
is the "robust to methodology" pattern from the pre-committed framework.

The 4× amplification under the actionable filter is consistent with
Phase A's verified diagnosis: the filter selects pairs where shuffled chains
land more often on resource-friendly state-sigs (where the model's
collapse behavior wins). Without the filter, the gap is much smaller.

### chess960 — `Robust reversed`

Same pattern as chess_standard. Filter amplifies but doesn't flip.

### checkers_american — `Methodology choice flips the direction`

| Methodology | gap | p_raw | p_bon | tier |
|---|---|---|---|---|
| 1) two-sample proportion (v1) | **+0.0394** | 0.002 | n/a | weak_mixed (POSITIVE) |
| 2) paired McNemar no filter (v2) | **+0.0394** | <0.001 | <0.001 | weak_mixed (POSITIVE) |
| 3) v3 pre-reg actionable+Bonf | **-0.1150** | <0.001 | <0.001 | reversed |
| 4) actionable no Bonf | **-0.1150** | <0.001 | n/a | reversed |

**This is the "serious finding" case from the pre-committed framework.**

Without the actionable filter, checkers_american shows a small POSITIVE gap
of +0.04 (real beats shuffled) at high significance. With the filter, it
shows a strongly negative gap of -0.12 (shuffled beats real) at high
significance. **The actionable filter alone flips the direction.**

This means:
- The full sample of pairs in checkers_american supports the originally-
  hypothesized direction (real > shuffled).
- The both-actionable subset reverses this — and that subset IS what the
  pre-registered methodology tests.
- Per pre-registration, v3's classification for checkers_american is
  `reversed`. Per the unfiltered analysis, the underlying signal is mildly
  positive.

This is consistent with Phase A's diagnosis: the filter is selecting against
non-actionable (mostly ResourceBudget) pairs where real chains do reasonably
well, leaving an actionable subset where the resource_side_* dominance
mechanism produces the strongest reversal.

### draughts_intl — `Methodology choice flips the significance`

| Methodology | gap | p_raw | p_bon | tier |
|---|---|---|---|---|
| 1) two-sample proportion (v1) | -0.0164 | 0.145 | n/a | reversed (NOT significant) |
| 2) paired McNemar no filter (v2) | -0.0164 | 0.034 | 0.136 | reversed (raw sig only) |
| 3) v3 pre-reg actionable+Bonf | -0.1553 | <0.001 | <0.001 | reversed (significant) |
| 4) actionable no Bonf | -0.1553 | <0.001 | n/a | reversed (significant) |

**Fourth pattern, not in the pre-committed interpretation framework.** All
four methodologies show negative gap, so direction is consistent. But
significance is NOT robust:
- Methodology 1 (v1's): p = 0.145 — fails 0.05 threshold
- Methodology 2 (v2's): p_raw = 0.034 (sig), p_bonferroni = 0.136 (NOT sig)
- Methodologies 3 and 4 (v3's): both highly significant

For draughts_intl specifically, the v3 pre-registered methodology produces
significance that the looser tests do not. The underlying gap is small
(-0.016 unfiltered).

---

## Summary across all 4 cells

| Cell | Pattern from pre-committed framework |
|---|---|
| chess_standard | Robust reversed (all methodologies negative + significant) |
| chess960 | Robust reversed |
| **checkers_american** | **Methodology flips direction** (positive without filter, negative with) |
| draughts_intl | Methodology flips significance (consistent direction, but only v3 reaches significance) |

**2 of 4 cells show the pre-registered `reversed` result is robust to
methodology choice. 1 of 4 (checkers_american) flips direction depending
on the actionable filter. 1 of 4 (draughts_intl) flips significance
depending on Bonferroni / filter choices.**

---

## What drives the methodology sensitivity

Within the 4 methodologies tested, the dominant lever is **the both-actionable
filter** (Bonferroni and pair structure are second-order). Comparing
unfiltered vs filtered gaps:

| Cell | unfiltered gap | filtered gap | filter effect |
|---|---|---|---|
| chess_standard | -0.043 | -0.187 | 4.3× amplification (same sign) |
| chess960 | -0.038 | -0.231 | 6.0× amplification (same sign) |
| checkers_american | +0.039 | -0.115 | **sign flip** + 2.9× magnitude |
| draughts_intl | -0.016 | -0.155 | 9.7× amplification (same sign) |

The filter is doing substantial work — between 3× and 10× amplification on
already-reversed cells, and sign-flipping on the one borderline cell.

This is consistent with the Phase A verified mechanisms: the actionable
filter (which excludes ResourceBudget cutoff pairs) specifically over-selects
the regime where Mechanism 2 (resource_side dominance + model collapse) is
strongest. Without the filter, much of the ResourceBudget volume is in the
sample, and that volume is where real chains' varied predictions don't
match the metric's preference for common entities — but it's also where
shuffled chains can't easily exploit the resource_side dominance because
their cutoff is more often a non-RB constraint.

---

## What this analysis can and cannot conclude

### Can conclude

- v3's `reversed` classification is partially methodology-dependent.
  For chess_standard and chess960, reversed is robust. For checkers_american,
  the unfiltered analysis points the OPPOSITE direction. For draughts_intl,
  the result depends on Bonferroni.

- The actionable filter is doing more work than expected. It's not just
  "a power-improving subset" — for one cell it's responsible for the
  direction of the result.

- The Phase A diagnosis is supported by this independent analysis: the
  filter selects the regime where the diagnosed mechanisms operate.

### Cannot conclude

- This does NOT mean v3's `reversed` classification is wrong. Per pre-commitment,
  pre-registered methodology stands. The robustness sensitivity is documented
  context, not classification revision.

- This does NOT identify "the right" methodology. Each methodology has
  different power/assumptions; v3 chose v3's methodology in pre-registration
  for stated reasons.

- For checkers_american specifically: this analysis cannot tell us whether
  the unfiltered +0.039 or the filtered -0.115 is "more representative."
  Both are valid summaries of the data under their respective sampling
  decisions.

- The Bonferroni correction's effect on draughts_intl significance suggests
  multiple-comparison philosophy matters; this is a methodology-design
  question, not a data question.

---

## Recommendation for next v4 cell

The pre-committed plan said cell 1 is a decision point: based on what cell 1
shows, the author + co-author decide whether further v4 cells (which require
API calls) are worth running.

**My recommendation: this analysis warrants Myriam's input before any
additional v4 cells.** The checkers_american sign-flip is substantively
interesting and changes the framing of the v3 result. Whether to:

1. Treat checkers_american as evidence of weak positive signal in the
   unfiltered pool (which would require pre-registering a v4 cell that
   doesn't apply the actionable filter), or

2. Treat the unfiltered result as a statistical artifact and stick with
   v3's pre-registered filtered analysis (which says `reversed`), or

3. Run additional v4 cells with prompt variations / model variations to
   see whether the methodology sensitivity persists across conditions

…is a methodology decision that should not be made unilaterally by the
analysis loop.

**One specific thing not yet tested**: this analysis applied 4 statistical
tests to the SAME response data. It does not test methodology robustness
to chain construction or scoring architecture (those would require the
fully-controlled methodology from Phase A's three-mechanism decomposition,
or new chain generation in v4). Cell 1 is statistical-test robustness only.

---

## Files

```
src/v4_scorer_robustness.py  (new)
scripts/v4_robustness_analysis.py  (new)
results/v4/cell_1_robustness.json  (full per-cell + per-methodology stats)
results/v4/cell_1_robustness_table.md  (markdown summary table)
results/v4/cell_1_interpretation.md  (this document)
```
