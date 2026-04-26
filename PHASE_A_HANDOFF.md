# Phase A handoff — three-mechanism decomposition of v3's reversed result

**For**: a fresh Claude chat to read cold and discuss before briefing Myriam.

**Status**: post-hoc verification of the pre-registered v3 result. Claims here
have NOT received co-author sign-off. The pre-registered analysis on `main`
is unchanged; this work lives on three branches (`claude/phase-a-verification`,
`claude/phase-a-option-c`, `claude/phase-a-loo`).

---

## 1. What v3 is, in one paragraph

Ditto v3 tests whether a six-type constraint-chain abstraction (developed in v1/v2
for programming agents) generalizes to formal-rule games — chess (standard +
Chess960) and checkers (American + international draughts), 1,200 real chains
per cell. Each chain is paired with three shuffled variants (random permutations
of the same constraints). A model (Haiku 4.5) predicts the next constraint's
entity given the chain prefix; we score whether the response is in the top-3 of
an empirical reference distribution built from real chains. The pre-registered
hypothesis: real chains' prefixes carry causal information that the model can
use; shuffled chains' prefixes don't; therefore real-match-rate > shuffled-match-rate.

## 2. Pre-registered result

All four primary cells (Haiku, T=0.0/seed=42, Bonferroni divisor=4) showed
**negative** Layer 1 actionable gap:

| Cell | gap | p (Bonf.) | tier |
|---|---|---|---|
| chess_standard | -0.1871 | <0.001 | reversed |
| chess960 | -0.2312 | <0.001 | reversed |
| checkers_american | -0.1150 | <0.001 | reversed |
| draughts_intl | -0.1553 | <0.001 | reversed |

The pre-registered outcome is `reversed` across all four cells: the model
appears to predict shuffled chains' targets *better* than real chains'.

This is unexpected. It could be:
- (a) A real experimental finding that shuffled chains are easier to predict
  in this setup (interesting but not what the hypothesis predicted)
- (b) A measurement-instrument failure where methodology contamination produces
  the inversion (boring, not informative about the hypothesis)

Phase A was designed to test (b).

## 3. The diagnostic frame

Three candidate methodology artifacts were proposed before any post-hoc
analysis. Each was analyzable from the existing data without new model API
calls. They are independent — fixing one doesn't fix the others.

### Mechanism 2 — reference distribution dominated by `resource_side_*`

The T-code (chain construction) has a rule `pos%4==3 → ResourceBudget`. This
forces ResourceBudget constraints at positions 3, 7, 11, 15, 19, 23 of every
chain. The ResourceBudget constraint's entity is `resource_side_1`,
`resource_side_2`, or `progress_remaining` — never anything else.

Consequence: across the ~1,200 chains used to build the reference distribution
in chess_standard, `resource_side_*` entities are the focal_action of many
state signatures, and they appear in the top-3 of the reference at 28-67% of
state signatures depending on backoff level.

The model under v3.1's prompt produces `resource_side_*` responses 54% of the
time on real chains and **76%** of the time on shuffled chains (verified by
recounting raw response files). The model's "collapse to common entity" on
shuffled prefixes happens to align with the reference's empirical top-3, which
also concentrates on the same common entities.

The result: when shuffled chains land on a state-sig where the reference's
top-3 contains `resource_side_*`, the model's collapse behavior matches and
shuffled wins. When they don't, real wins (small margin). Net: shuffled wins
overall.

**Test**: build a reference where `resource_side_*` entities are capped to no
longer dominate top-3, then rescore against it.

### Mechanism 3 — backoff-level differential

The reference uses 4-level backoff: level 0 = (phase, type, bracket, entity_label),
level 1 drops entity, level 2 drops bracket, level 3 = phase only. When the
chain's level-0 sig isn't in the reference, lookup falls to level 1, etc.

By construction, real chain X always finds its own data at level 0 (X
contributed during reference build). Real chains lookup at level 0: ~95% of
the time. Shuffled chain X' has a *permuted* prefix — its level-0 sig is
typically not in the reference. Shuffled chains lookup at level 0: ~67% of
the time. The remaining 33% of shuffled chains backoff to broader cell-level
distributions, which are dominated by overall-common entities.

This is a confound: real chains scored against narrow sig-specific top-3;
shuffled chains scored against broader cell-level top-3 a third of the time.
The two arms are comparing different reference granularities.

**Test**: stratify pairs by joint backoff level. Restrict to pairs where both
real and shuffled hit level 0 — apples to apples.

### Mechanism 1 — shuffle adjacency × echo bias (verified small effect)

Earlier analysis found: real chains have target_entity == last_shown_entity
0.33% of the time (T-code prevents adjacency). Shuffled chains have it 13%
of the time (random permutation can adjacency-pair same-entity constraints).
The model echoes last-shown ~30-40% of the time, giving shuffled a ~1pp
structural advantage. Verified contribution: ~0.4 percentage points of the
inversion. Small relative to Mechanisms 2 and 3.

### A fourth artifact emerged during the LOO test — self-contribution leakage

Each real chain X contributes its focal_action to counts at sig_X during
reference build. So when X is later scored, its top-3 lookup at sig_X
includes X's own focal_action — by construction, 71% of the time (verified).
Shuffled chains derived from X don't have this self-contribution at sig_X'
(their permuted state-sig is different).

This is data leakage that *favors* real chains relative to shuffled. So if
anything, leakage should bias toward positive gap, not the reversed gap we
see. But removing it (via leave-one-out) is methodologically correct
regardless of direction.

**Test**: leave-one-out lookup that subtracts X's contribution from the
reference at lookup time, for both real X and X's shuffled variants.

## 4. The decomposition (chess_standard, primary config)

Each row applies one additional methodology fix on top of the previous:

| Stage | gap | 95% CI | p | movement | % of original inversion explained |
|---|---|---|---|---|---|
| Pre-registered (original ref) | -0.1871 | [-0.214, -0.160] | <0.001 | — | 0% |
| + Mech 2 (downweighted ref) | -0.0675 | [-0.082, -0.053] | <0.001 | +0.120 | 64% |
| + Mech 3 (matched backoff level) | -0.0046 | [-0.016, +0.006] | 0.683 | +0.063 | 97.5% |
| + Self-leakage (LOO) | **+0.0047** | (small n) | n/a | +0.009 | **~100%** |

Read this as: each fix is independent, and they compound. After all three:
gap is essentially zero, with sign flipped to weakly positive but well within
noise. The residual is 0.5 percentage points of the original 18.7-percentage-
point inversion.

**All four cells under all three fixes (Layer 1 actionable, primary config):**

| Cell | dwt+LOO same-level gap |
|---|---|
| chess_standard | +0.0047 |
| chess960 | +0.0066 |
| **checkers_american** | **+0.0451** ← clearly positive |
| draughts_intl | +0.0114 |

All four cells go non-negative. `checkers_american` shows a real positive gap
of ~4.5 percentage points. The others sit at +0.5 to +1.1 pp — within
statistical noise of zero.

## 5. The Phase A pre-committed criterion (and why it formally failed)

Before any post-hoc analysis, a binary criterion was set:

> chess_standard Layer 1 actionable gap **under downweighted reference** ≥ +0.02 → SUCCESS

The criterion was on the *overall* gap under downweighted reference. That
column shows -0.0675 (still negative, far from +0.02). Phase A formally failed.

The criterion implicitly assumed Mechanism 2 alone would suffice. The
verification work showed it doesn't — Mechanism 3 was also at play, and so was
self-leakage. When you stack the three corrections, you get to roughly zero,
not to +0.02.

**Important**: the +0.0047 dwt+LOO+same-level number is *not* a pass of the
Phase A criterion. The criterion was on overall (not stratified, no LOO) and
the threshold was +0.02 (not "above zero"). Treating dwt+LOO+same-level as a
"pass" would be motivated reasoning. It does, however, support the diagnostic
claim that the inversion is fully explained.

## 6. What this DOES support

> The pre-registered v3 reversed finding (-0.187 across all 4 cells) is fully
> attributable to three independent, identifiable methodology artifacts. When
> all three are controlled in post-hoc analysis, the gap is statistically
> indistinguishable from zero across all 4 cells, with one cell (checkers_american)
> showing a small positive gap. The model is not detectably better at predicting
> real chains than shuffled chains under v3 methodology, but it is also not
> detectably worse — the apparent reversal vanishes once methodology contamination
> is removed.

This is a substantive claim. It says: don't take the reversed result at face
value as a real experimental finding. It's measurement-instrument failure.

## 7. What this does NOT support

A few things to be careful about:

**(a) "We've shown the constraint-chain hypothesis is true."** No. Under
fully-corrected methodology, the gap is essentially zero. Three of four cells
show *no detectable* signal. Only checkers_american shows a clearly positive
gap, and that's one cell out of four — not enough for the four-cell pattern
the SPEC required.

**(b) "We've shown the constraint-chain hypothesis is false."** Also no. The
v3 chain construction has structural skew that makes the metric uninterpretable
even under three corrections. We've shown the methodology can't reliably
detect anything; we haven't shown there's nothing to detect.

**(c) "Three corrections is the right answer; v4 should bake them in."** The
three corrections are post-hoc data analysis fixes. They're not the *experimental
design fix*. The right v4 design wouldn't have the contaminations in the first
place — drop or replace the `pos%4==3` rule, build the reference from a
held-out set of chains, score against the same reference granularity for
both arms. The corrections here are diagnostic (what went wrong), not
prescriptive (what to do instead).

## 8. The honest framing for Myriam

The pre-registered result is `reversed` across all four cells. The post-hoc
diagnosis attributes ~100% of the reversal to identifiable methodology
artifacts. The corrected gap is null with one cell showing weak positive
signal. Two paths forward:

**Path A: report v3 as `reversed` per pre-registration, with the diagnostic
appendix.** Honest pre-registered result. The appendix says "we don't think
this is real signal; here's why," and the v4 design priorities follow from
the diagnosis.

**Path B: report v3 as `null` with the diagnostic appendix.** This makes a
substantive claim about what the data means, not just what the metric said.
But it's not the pre-registered result — it's the post-hoc-corrected result.
It needs more careful framing about pre-registration discipline.

I lean toward Path A. It respects the pre-registration; the diagnostic
section is where the substantive point goes. Your call.

## 9. Where to look in the repo

Documents:
- `SPEC.md` — pre-registration anchor (immutable)
- `SPEC_v1.1.md` — signed amendments (prompt template, cutoff clarification)
- `SESSION_LOG.md` — full session history with verification work

Branches:
- `main` — pre-registered analysis. `results/phase1_v31_scored_full.json` is
  the formal result.
- `claude/phase-a-verification` — Phase A + Path 1 stratified analysis. The
  Mechanism 2 + Mechanism 3 work.
- `claude/phase-a-option-c` — alternative cap policy test (worse than Option B,
  ruled out).
- `claude/phase-a-loo` — leave-one-out reference. The three-mechanism
  decomposition lives here.

Key data files (all on the LOO branch):
- `results/phase_a/loo_decomposition.{json,md}` — multi-column decomposition
- `results/phase_a/loo_rescored.json` — full per-cell + stratified
- `results/phase_a/stratified_analysis.json` — Path 1 work (on phase-a-verification)
- `results/phase_a/decomposition_table.{json,md}` — initial 3-column work

## 10. Suggested questions for the fresh chat to consider

1. Does the three-mechanism diagnosis hold up structurally, or is there a
   fourth confound we haven't considered?
2. Is "report v3 as `reversed` with full diagnostic appendix" the right call,
   or is "report as `null` post-hoc-corrected" defensible?
3. The `+0.0047` chess_standard same-level result is in the AMBIGUOUS range
   for the original Phase A criterion (-0.02 to +0.02). Does that change anything?
4. Is the post-hoc analysis chain (downweight → stratify → LOO) something a
   reviewer would accept, or does it look like p-hacking even though each step
   is independently motivated?
5. For v4 design: which of the three artifacts is the highest priority to
   address structurally? My guess is Mechanism 2 (chain construction itself)
   but Mechanism 3 (scoring architecture) is also fixable.
