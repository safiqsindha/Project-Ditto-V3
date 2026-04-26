# Project Ditto v3 — Pre-Registration Specification

**Specification v1.0** · Pre-registration draft
Full PDF: `SPEC.pdf` (immutable — do not edit after freeze)

> **This document will be frozen before evaluation begins.**
> Thresholds, methodology, and analysis plan are committed here before T-code
> implementation begins. Any methodology change after Gate 1 invalidates the
> pre-registration and requires a new dated spec.

---

## Hypothesis (precisely scoped)

The constraint-chain abstraction developed in Project Ditto (six constraint
types: `ResourceBudget`, `ToolAvailability`, `SubGoalTransition`,
`InformationState`, `CoordinationDependency`, `OptimizationCriterion`)
captures generalizable structure in sequential decision-making, AND
**training-data exposure compresses the magnitude of the real-vs-shuffled
detectability gap**. When applied to formal-rule game-playing trajectories
from two game families (chess and checkers), each with a high-exposure
standard variant and a low-exposure structural variant (Chess960 and
international draughts), the abstraction will produce a stronger
detectability gap in the lower-exposure variant of each family.

The experiment is a **directional hypothesis test of training-exposure as a
gap-compression mechanism**, conducted within a generality-test framing. It
extends v1 (Pokémon) and v2 (programming) by adding a third domain family
(formal games) and by directly testing one mechanistic explanation for v2's
observed Sonnet-vs-Haiku gap compression.

---

## What this experiment is NOT

- Not a test of whether game telemetry helps programming reasoning
- Not a cross-domain transfer test
- Not a fine-tuning experiment
- No Pokémon-derived or programming-derived data enters this evaluation
- Does not measure game-playing capability
- Does not justify any production application
- Does not test all confounds simultaneously — chess vs. Chess960 isolates
  exposure-within-structure; checkers vs. draughts replicates that isolation
  in a second game family

---

## Pre-registered Success Criteria

The criteria below test a *pattern* of per-cell results across the four
primary cells, not a single contrast statistic. Per-cell tests are well-
powered under the v3 sample plan; the contrast itself is reported as a
descriptive supporting analysis but is not the hypothesis test.

### Per-cell thresholds (each cell tested independently)

| Criterion | Threshold | Tier |
|-----------|-----------|------|
| Layer 1 actionable gap (real − shuffled, both-actionable filter) | ≥ 0.05 | Moderate-positive |
| Layer 1 actionable significance | Bonferroni-corrected p < 0.05 | Moderate-positive |
| Layer 2 gap (legality × optimality composite) | ≥ 0.04 | Layer 2 confirmation |
| Layer 2 significance | Bonferroni-corrected p < 0.05 | Layer 2 confirmation |
| Strong-positive | Layer 1 actionable gap ≥ 0.08 ∧ Bonferroni p < 0.01 | Strong-positive |

### Pre-registered hypothesis-pattern outcomes

The hypothesis is supported, partially supported, refuted, or inconclusive
based on the joint pattern across the four primary cells.

**Hypothesis supported (training-exposure compresses gap):**
Both of the following hold:
- (Chess family) Standard chess clears at most moderate-positive AND
  Chess960 clears strong-positive
- (Checkers family) American checkers clears at most moderate-positive AND
  international draughts clears strong-positive

**Hypothesis partially supported:**
The pattern holds in exactly one game family but not the other, OR the
direction is consistent across both families but neither low-exposure
variant clears strong-positive while both clear moderate-positive at higher
magnitude than their high-exposure counterparts (gap difference ≥ 0.03 in
the predicted direction within each family).

**Hypothesis refuted:**
Any of the following:
- Both standard chess and Chess960 clear strong-positive (no compression
  visible despite large exposure differential)
- Both American checkers and international draughts clear strong-positive
  (same; second family)
- Low-exposure variants show *smaller* gaps than their high-exposure
  counterparts in both families (wrong direction)

**Inconclusive:**
- Any cell fails to reach the per-cell sample-size target due to data
  acquisition or chain-construction issues
- Per-cell power post-hoc falls below 70% for the relevant threshold
- Three or more cells return null results, suggesting chain-construction
  failure rather than informative absence of effect

### Minimum publishable result (independent of hypothesis outcome)

At least one cell clears the moderate-positive threshold at Bonferroni-
corrected significance under the pre-registered methodology. This is the
v2-style minimum and is met independently of the hypothesis-pattern outcome.

Outcome tiers (consistent with v1 and v2):
`strong_positive`, `moderate_positive`, `weak_mixed`, `null`, `reversed`.

---

## Phase Structure (sequential / adaptive design — pre-registered)

v3 runs in two phases with a pre-committed gating rule between them.

### Phase 1: Haiku evaluation (4 cells)

Run all four primary cells on Claude Haiku 4.5 at full pre-registered
sample size before any gap statistics are computed across cells. Technical
monitoring (API errors, malformed chains, missing pairs) is permitted
during the run; effect-size monitoring is not.

### Phase 1 → Phase 2 gate (pre-committed before any data collection)

**Run Sonnet (Phase 2) iff at least one of:**

1. Any Haiku cell clears moderate-positive at Bonferroni-corrected p < 0.05
   under the Haiku-only divisor of 4 (gap ≥ 0.05).
2. The within-family gap difference in either chess or checkers reaches
   ≥ 0.03 in the predicted direction (Chess960 > standard chess, OR
   draughts > American checkers), regardless of per-cell significance.
3. Haiku per-cell results are mixed in a way Sonnet would resolve: exactly
   one cell clears moderate-positive AND its within-family partner falls
   between gap = 0.02 and gap = 0.05 (boundary case).

**Skip Sonnet (Phase 1 only is the final result) iff all of:**

1. All four Haiku cells have gaps within 0.015 of each other.
2. No Haiku cell reaches Bonferroni-corrected p < 0.05 (divisor 4).
3. No within-family gap difference exceeds 0.02 in either direction.

If neither the run nor the skip criteria are met (ambiguous Phase 1
result), default behavior is to **run Phase 2** to disambiguate. This is
intentionally asymmetric — the cost of Phase 2 is bounded; the cost of an
inconclusive v3 is much higher.

### Bonferroni divisor

- If Sonnet runs: divisor = 8 (4 cells × 2 models)
- If Sonnet does not run: divisor = 4 (4 cells × 1 model)
- The divisor used in the final report is determined by which phases ran,
  not by post-hoc convenience.

### Adaptive design disclosure

This sequential design is itself a pre-registered methodology choice. The
gate criteria above are committed before Phase 1 begins. No effect-size
peeking within Phase 1 is permitted. Phase 2 design is not modified based
on Phase 1 results (only the decision to run or skip Phase 2 is adaptive).

---

## Models and Evaluation Parameters

| Parameter | Value |
|-----------|-------|
| Models | Claude Haiku 4.5 (`claude-haiku-4-5-20251001`), Claude Sonnet 4.6 (`claude-sonnet-4-6`) |
| Primary config | Temperature 0.0, seed 42 |
| Variance study | T=0.5, seeds 1337 and 7919 |
| Max tokens | 50 |
| Cutoff K | `len(constraints) // 2` |
| Prompt version | v3.0-game |
| API | Anthropic Messages Batches (50% cost reduction) |
| Action normalization | Full normalization (case, punctuation, whitespace, word order) |

The three-config variance study (matching v1 and v2) is included to
characterize per-cell stability. The primary config result is the
pre-registered headline; T=0.5 configs are reported as supplementary
variance characterization, not as additional cells in the Bonferroni family.

---

## Data Sources (committed — will not change after freeze)

### Chess family (game family 1)

| Variant | Exposure | Source | Target chains |
|---------|----------|--------|---------------|
| Standard chess | High | `Lichess/standard-chess-games` (HuggingFace, Parquet, CC0) | 1,200 real chains |
| Chess960 | Low | `Lichess/chess960-chess-games` (HuggingFace, Parquet, CC0) | 1,200 real chains |

Rating filter applied at load time: `WhiteElo ≥ 1800 AND BlackElo ≥ 1800`.
Filtering is performed via `polars` or `pandas` on the Parquet files, not
in-stream, to ensure deterministic sampling.

Rationale: Both sources are from the same platform (Lichess) maintained as
the official Lichess HuggingFace organization. This reduces platform-specific
stylistic confounds. Both are CC0-licensed; both are auto-converted to
Parquet for fast filtering. The rating floor (1800) ensures non-trivial
play in both variants. Exposure differential is structural — the standard
chess corpus is dramatically larger than Chess960 in publicly available
training data (orders of magnitude difference in human-played game counts
across all sources, not just Lichess).

Access pattern: stream directly from HuggingFace via the `datasets` library
(`load_dataset("Lichess/standard-chess-games", streaming=True)` and likewise
for Chess960). No manual download required. For deterministic sampling under
the rating filter, materialize a filtered subset to local Parquet/JSONL once
during data validation (Session 2), then operate on the materialized subset
for chain construction. This avoids re-streaming the full dataset on every
chain-generation run while keeping initial acquisition lightweight.

PGN parsing: `python-chess` library. Chess960 starting FEN is provided per
game in the dataset; pass it to `chess.Board(fen=starting_fen, chess960=True)`
during parsing.

**Explicitly excluded**: `laion/strategic_game_chess` and any other engine
self-play chess dataset. v3's hypothesis test depends on training-corpus
exposure that reflects human play; engine self-play games have different
distributional properties and would confound the exposure-mechanism test.

### Checkers family (game family 2)

| Variant | Exposure | Source | Target chains |
|---------|----------|--------|---------------|
| American checkers (8x8) | Higher | Open Checkers Archive (OCA 2.0) PDN files; ACF tournament archives | 1,200 real chains |
| International draughts (10x10) | Lower | FMJD database PDN tournament archives | 1,200 real chains |

PDN parsing: `pydraughts` library (AttackingOrDefending package on PyPI).
This library supports both American (8x8) and Standard / International
(10x10) variants in the same interface via `Board(variant="american")`
and `Board(variant="standard")`. Single library, two variants.

Access pattern: PDN sources are not on HuggingFace and require download
during data validation (Session 3). Canonical sources: OCA 2.0 archive at
`http://fierz.ch/download.php`, ACF tournament archives, FMJD tournament
archives at `https://fmjd.org`. Materialize to local JSONL once and
operate on the materialized files for chain construction.

Rationale: Same family (move-and-capture), structurally analogous,
substantially different corpus sizes. International draughts is
geographically concentrated (continental Europe, francophone Africa); its
training-data corpus is substantially smaller than American checkers, but
the games have richer tactical structure (10x10 board, longer sequences).
This is a known asymmetry — corpus difference and structural difference are
confounded in this contrast. The *within-chess* contrast (standard vs.
Chess960) is the cleaner test; the checkers family is a secondary
replication.

Note on checkers data volumes: the checkers PDN sources (OCA, FMJD,
ACF archives) are smaller than the chess HuggingFace datasets (tens of
thousands of games rather than millions). The 1,200 chains/cell target
should still be reachable, but if pilot inspection in Session 6 shows
actionability rates below the assumed 83% retention through the both-
actionable filter, the checkers cells may be the binding constraint.

### Per-cell sample target: 1,200 real chains, generating ~1,000 paired evaluations after both-actionable filter

Power justification (full calculation in §Sample Size & Power):
- 1,000 paired evaluations per cell at v2-calibrated discordant rate gives
  ~94% per-cell power to detect gap = 0.06 at α = 0.0125 (Haiku-only) and
  ~90% power at α = 0.00625 (full Bonferroni).
- Per-cell power is the primary statistical concern given the reframed
  hypothesis structure.
- The descriptive contrast tests (chess vs. Chess960, checkers vs.
  draughts) have lower power and are reported with confidence intervals
  rather than as hypothesis tests.

---

## Chain Construction (chess and checkers T-codes, pre-frozen design)

### Chain definition

A constraint chain is a sequence of constraints derived from a 15–25 move
window of a game, anchored to game phase. Chains are extracted from full
games (not puzzles or tactical positions) to preserve the sequential-
decision structure that produced detectable gaps in v1 and v2.

### Constraint type mappings (frozen at T-code-game-v1.0)

| Type | Chess (and Chess960) | Checkers (and draughts) |
|------|---------------------|-------------------------|
| `ResourceBudget` | Material count and tempo (moves remaining, time budget if PGN includes clocks) | Piece count and tempo |
| `ToolAvailability` | Legal move set; piece mobility (count of legal moves per piece) | Legal move set; capture availability |
| `SubGoalTransition` | Phase transitions (opening → middlegame → endgame); plan changes inferred from pawn structure shifts | Phase transitions (opening → midgame → endgame); king-promotion subgoal |
| `InformationState` | Trivially complete (perfect information) — documented as a known asymmetry; entered into chains as constant `complete` to preserve six-type structure | Trivially complete — same treatment |
| `CoordinationDependency` | Piece coordination (defended pieces, X-rays, batteries); pawn structure dependencies | Piece coordination (back-row defense, double-corner control) |
| `OptimizationCriterion` | Implicit evaluation function (material, position, king safety) inferred from move choice | Implicit evaluation function (material, position, mobility) |

### Known asymmetry: `InformationState` is non-actionable in formal games

Chess and checkers are perfect-information games; `InformationState` is
constant across all chains. This means v3 effectively tests 5 of 6
constraint types in the actionable subset (vs. v1 and v2 which test all
6). This is documented as a known structural property of formal-game
chains, not a methodology change. The both-actionable filter still applies
on the remaining 5 types. The constraint enters chains as a constant
`InformationState(state="complete")` to preserve chain length and the
six-type structure for cross-experiment comparability.

### Pilot validation before full chain generation

Before generating the full 1,200 chains per cell, a pilot of 50 chains per
cell is generated and inspected for:
- Constraint type distribution (expected: ~30% each of ResourceBudget,
  ToolAvailability, SubGoalTransition, with smaller fractions of
  CoordinationDependency and OptimizationCriterion)
- Chain length within target range (15–25 events post-aggregation)
- Leakage check pass rate (must be 100%; chains containing chess- or
  checkers-specific vocabulary fail rendering)
- Renderer output spot-check by both authors

Pilot must pass before full generation. T-code freezes at tag
`T-code-game-v1.0-frozen` only after pilot inspection.

### Renderer leakage vocabulary

Domain-blind rendering uses an extended programming-vocabulary leakage
list from v2 plus chess- and checkers-specific terms:
- Chess: pawn, knight, bishop, rook, queen, king, castle, check, mate,
  fork, pin, skewer, en-passant, file/rank labels, algebraic notation
- Checkers: jump, capture, king (in checkers sense), crown, double-corner,
  square numbers (1-32 / 1-50)

Any rendered chain containing leakage vocabulary fails rendering. The
leakage check is enforced in code; callers cannot bypass.

---

## Pre-registered Statistical Methodology

### Layer 1 (primary) — paired McNemar's test with continuity correction

For each cell, paired binary outcomes (top-3 match, real vs. shuffled) are
analyzed with continuity-corrected McNemar's test. Pairs are aligned by
`(base_chain_id, model, eval_seed)`. Pairs missing either real or shuffled
result are reported and excluded.

Gap is computed as `real_match_rate − shuffled_match_rate` over all pairs
(not just discordant), matching v2's match-rate-difference estimand.

### Layer 2 (secondary) — paired t-test

Continuous Layer 2 scores (legality × optimality composite) are analyzed
with paired t-test (`scipy.stats.ttest_rel`) on aligned pairs.

### Both-actionable filter (Layer 1 actionable subset)

A pair enters the Layer 1 actionable analysis only if both the real and
shuffled chains have an actionable constraint type at the cutoff position.
Actionable types in the formal-game setting: `ToolAvailability`,
`SubGoalTransition`, `CoordinationDependency`, `OptimizationCriterion`
(four types; `InformationState` is excluded as non-actionable; matches v2's
filter logic adapted to formal games).

This is the corrected estimand from v2's correction process (matches
`scorer_corrected_v2.py` filter logic). Pairs where one chain has an
actionable cutoff and the other does not are excluded from the actionable
subset analysis.

### Multiple-comparisons correction

Bonferroni correction is applied across the primary cells:
- Phase 1 + Phase 2 (Sonnet runs): divisor = 8
- Phase 1 only (Sonnet does not run): divisor = 4

Per-config and per-source breakdown analyses are reported as supplementary
and use a separate Bonferroni divisor calculated post-hoc; these are not
primary cells.

### Pair alignment

All result files are indexed by `(base_chain_id, model, eval_seed)` before
scoring. The pair structure is:
```
(base_chain_id, model, eval_seed) × (shuffled_chain = base_chain_id +
    "_shuffled_" + shuffle_seed)
```
Three shuffled variants per real chain (seeds 42, 1337, 7919); each real
evaluation contributes three pairs (one per shuffled variant) under the
same eval_seed. This 3× replication is by design (matches v2) and
increases McNemar test power without inflating real_rate.

---

## Sample Size & Power

### Calibration

Power calculations are calibrated against v2 Haiku-TB (the cell that
cleared the pre-registered threshold under corrected paired analysis):
- n_pairs = 312 (after both-actionable filter)
- gap = 0.0801
- discordant rate (b+c)/n ≈ 0.228
- p_b = b/(b+c) ≈ 0.676 at gap 0.08

These are the closest analog to expected v3 cell behavior (Haiku, paired
McNemar with both-actionable filter, structurally similar chain length).

### Per-cell power table (computed under v2 calibration)

At Haiku-only divisor (α = 0.0125):

| n_pairs | gap = 0.04 | gap = 0.06 | gap = 0.08 |
|---------|-----------|-----------|-----------|
| 500 | 0.27 | 0.63 | 0.91 |
| 800 | 0.45 | 0.87 | 0.99 |
| **1,000** | **0.56** | **0.94** | **0.99** |
| 1,500 | 0.78 | 0.99 | 1.00 |

At full Bonferroni divisor (α = 0.00625, both phases):

| n_pairs | gap = 0.04 | gap = 0.06 | gap = 0.08 |
|---------|-----------|-----------|-----------|
| 500 | 0.19 | 0.54 | 0.86 |
| 800 | 0.36 | 0.81 | 0.99 |
| **1,000** | **0.47** | **0.90** | **1.00** |
| 1,500 | 0.70 | 0.99 | 1.00 |

### Pre-registered target

1,000 paired evaluations per cell after both-actionable filter, requiring
~1,200 real chains per cell (assuming ~83% retention through the filter,
calibrated against v2's actionable subset retention rate of ~40% for TB
adjusted upward for formal-game expected actionability of ~60%; pilot
will validate this estimate before full chain generation).

This target gives:
- ≥ 90% per-cell power for the moderate-positive threshold at full
  Bonferroni
- ≥ 99% per-cell power for the strong-positive threshold at full
  Bonferroni
- Modest contrast power (≈ 27% at the predicted 0.04 within-family
  difference) — descriptive only, not the hypothesis test

### Power deficiency disclosure

The within-family contrast tests (chess vs. Chess960, checkers vs.
draughts) are underpowered to detect a 0.04 gap difference at standard
α (≈ 27% power at full Bonferroni). This is a deliberate design tradeoff:
the per-cell pattern is the hypothesis test; the contrast statistics are
descriptive. The contrast underpowering is disclosed in the spec and will
be re-disclosed in the results write-up.

---

## Pipeline Reuse from v1/v2

The following modules are inherited and not rewritten:

| Module | Source | Modification |
|--------|--------|--------------|
| `src/filter.py` | v1/v2 (unchanged) | None — chain validity logic is domain-blind |
| `src/shuffler.py` | v1/v2 (unchanged) | None |
| `src/normalize.py` | v1/v2 (unchanged) | None |
| `src/scorer_corrected_v2.py` | v2 | Adapted for v3 actionable types |
| `src/runner.py` | v2 | Adapted for v3 sources |
| `src/reference.py` | v2 | New active_pair logic (current_phase, last_move_type) |

New modules required for v3:
- `src/translation.py` — game-domain T-code (replaces v2's programming T-code)
- `src/aggregation.py` — game event compression
- `src/parser_chess.py` — PGN parser via `python-chess` → TrajectoryLog
- `src/parser_checkers.py` — PDN parser via `pydraughts` → TrajectoryLog
- `src/renderer.py` — adapted leakage check with chess + checkers vocabularies
- `src/observability.py` — adapted entity labels for game domain

---

## Pre-registered Supplementary Analyses

1. **Per-config variance study** — three temperature/seed configs
   (T=0.0/seed=42, T=0.5/seed=1337, T=0.5/seed=7919), reported as
   supplementary stability characterization for each cell.
2. **Within-family contrast tests** — chess vs. Chess960 and checkers
   vs. draughts gap differences with 95% confidence intervals.
   Descriptive only; not in primary Bonferroni family.
3. **Cross-family contrast** — chess family vs. checkers family pattern
   comparison.
4. **Comparison to v1 and v2 effect sizes** — v1 Pokémon-Sonnet gap
   (0.206), Pokémon-Haiku gap (0.066), v2 Haiku-TB actionable gap
   (0.0801). v3 results placed in this context.
5. **Constraint-type carrier analysis** — which constraint types carry
   the actionable signal in each cell, following v2's TB-vs-SWE carrier
   asymmetry methodology.
6. **Sonnet-vs-Haiku gap compression** — within each cell, compare
   Sonnet gap to Haiku gap to test whether the v2-observed gap
   compression replicates in the game domain.

---

## What it would establish if the hypothesis is supported

> "The Project Ditto methodology measures more than the presence of
> abstract sequential structure — it also measures the degree to which
> a model has internalized that structure as surface pattern-matching
> versus deeper causal-structure detection. Training-data exposure
> compresses the real-vs-shuffled gap; this is empirically demonstrated
> in two structurally distinct game families (chess and checkers) using
> within-family controls (Chess960, international draughts) that hold
> game structure approximately constant while varying corpus size."

This would reframe the methodology from "detection tool" to
"measurement tool" and would be a substantially stronger contribution
than v2's generality result alone.

## What it would establish if the hypothesis is refuted

> "The constraint-chain abstraction generalizes to a third domain
> family (formal-rule games), strengthening the v1+v2 generality claim.
> Training-data exposure does NOT drive the real-vs-shuffled gap
> magnitude — the v2-observed Sonnet-vs-Haiku gap compression and any
> cross-domain gap variation must have a non-exposure cause. v4 will
> investigate alternative mechanisms."

This is a less exciting outcome but still a publishable result with a
clean negative finding on a specific confound. The detection paper
becomes stronger by virtue of having ruled out the exposure
explanation. v4 directions are pre-specified in `PROGRAM_OUTLOOK.md`.

---

## Authors and Review

- Lead: Safiq Sindha (Microsoft Azure Hardware PM, independent research)
- Co-author: Myriam (Columbia University, systems engineering;
  Boeing FT) — reviews all major decisions; on all v3 publications
- Spec drafts circulated to co-author before commit
- Pre-registration commit signed off by both authors before evaluation
  begins

---

*Pre-registration v1.0 — drafted April 25, 2026. Prior work:
[Project Ditto v1](https://github.com/safiqsindha/Project-Ditto) (Pokémon),
[Project Ditto v2](https://github.com/safiqsindha/Project-Ditto-v2) (programming).*
