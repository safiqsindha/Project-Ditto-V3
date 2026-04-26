# Project Ditto v3 — Build Plan

**Audience:** Claude Code working on the v3 repository
**Status:** Draft — finalize before Session 1 begins
**Companion docs:** `SPEC.md` (frozen pre-registration), `PROGRAM_OUTLOOK.md` (program direction)

> **Pre-registration discipline.** This build plan executes the
> methodology specified in `SPEC.md`. Any divergence from `SPEC.md`
> requires written sign-off from both authors before being implemented.
> If the spec needs amendment, amend the spec first; do not work around
> it in code.

---

## Required reading before Session 1

Read these in order:

1. `SPEC.md` (pre-registration — thresholds and methodology are frozen)
2. `PROGRAM_OUTLOOK.md` (program direction context)
3. `CLAUDE.md` (architecture and session protocol — written in Session 1)
4. v2 repo at `github.com/safiqsindha/Project-Ditto-v2` for code reuse
5. v1 repo at `github.com/safiqsindha/Project-Ditto` for original methodology

The v2 repo has the cleanest implementations of the corrected scorer,
the both-actionable filter, and the runner. v3 should reuse these
modules where possible (`SPEC.md §Pipeline Reuse`).

---

## Data sources

Chess data streams directly from HuggingFace via the `datasets` library —
no manual download required. Checkers PDN files require download during
Session 3 (sources are not on HuggingFace).

| Source | Access pattern | Library |
|--------|---------------|---------|
| `Lichess/standard-chess-games` (HuggingFace, Parquet) | Stream via `datasets.load_dataset(..., streaming=True)` | `python-chess` for PGN parsing |
| `Lichess/chess960-chess-games` (HuggingFace, Parquet) | Stream via `datasets.load_dataset(..., streaming=True)` | `python-chess` (chess960=True) |
| Open Checkers Archive (OCA 2.0) + ACF tournament archives | Download from `http://fierz.ch/download.php` and ACF sources | `pydraughts` (variant="american") |
| FMJD tournament archives | Download from `https://fmjd.org` | `pydraughts` (variant="standard") |

Filter at materialization time: chess datasets require `WhiteElo ≥ 1800
AND BlackElo ≥ 1800` per `SPEC.md §Data Sources`. Apply via `polars` or
`pandas` while iterating the streamed Parquet, then write filtered subset
to `data/{cell}/games.jsonl` for chain construction.

**Materialize-once pattern:** After streaming + filtering during Session 2
(chess) and Session 3 (checkers), all subsequent sessions operate on the
local JSONL files. This avoids re-streaming the full HuggingFace dataset
on every chain-generation run and ensures deterministic sampling.

**Explicitly excluded:** `laion/strategic_game_chess` and any other
engine self-play chess dataset. v3's hypothesis test depends on training-
corpus exposure that reflects human play; engine self-play games would
confound the exposure-mechanism test.

---

## Gates between phases

Each phase ends in a gate. Gate passage is required before proceeding.
Gate failures pause execution for author review; do not auto-recover
or work around gate failures.

| Gate | Phase | Pass criterion |
|------|-------|----------------|
| Gate 1 | Setup | Pre-registration commit signed off by both authors |
| Gate 2 | Data validation | All four data sources loaded and validated |
| Gate 3 | Chain construction | Pilot of 50 chains/cell passes inspection; T-code freezes |
| Gate 4 | Full chain generation | 1,200 real chains/cell + 3,600 shuffled variants/cell |
| Gate 5 | Reference distribution | All four reference distributions built and validated |
| Gate 6 | Live API dry-run | Dry-run on 5 chains/cell succeeds without errors |
| Gate 7 | Phase 1 evaluation complete | All four Haiku cells evaluated at full sample size |
| Gate 8 | Phase 1 → Phase 2 decision | Pre-registered gate criteria evaluated |
| Gate 9 | Phase 2 evaluation complete (if triggered) | All four Sonnet cells evaluated |
| Gate 10 | Scoring | Corrected scorer run on all completed cells |

---

## Session-by-session plan

### Session 1 — Repository setup and v2 module reuse

**Tasks:**
- Create v3 repository (`Project-Ditto-v3`) at GitHub
- Establish branch `claude/start-v3-build-XXXXX`
- Copy unchanged from v2:
  - `src/filter.py`
  - `src/shuffler.py`
  - `src/normalize.py`
  - `src/scorer_corrected_v2.py` (will be renamed `src/scorer.py` for v3)
  - `tests/test_shuffler.py`
- Adapt from v2:
  - `src/runner.py` — update sources to chess_standard / chess960 /
    checkers_american / draughts_intl. Model IDs unchanged from v2
    (Haiku 4.5 + Sonnet 4.6).
  - `src/observability.py` — entity labels for game domain (piece /
    move / phase instead of file / command / error_class)
  - `src/reference.py` — `active_pair = (current_phase, last_move_type)`
  - `src/prompt_builder.py` — `PROMPT_VERSION = "v3.0-game"`; prompts
    reference "game" not "pipeline"
  - `src/renderer.py` — extend leakage check with chess + checkers
    vocabulary (full lists in `SPEC.md §Renderer leakage vocabulary`)
- Create stubs (raise `NotImplementedError`):
  - `src/translation.py` (game T-code, all six constraint dataclasses
    plus `translate_event` / `translate_trajectory`)
  - `src/aggregation.py` (game event compression)
  - `src/parser_chess.py` (PGN → TrajectoryLog via `python-chess`)
  - `src/parser_checkers.py` (PDN → TrajectoryLog via `pydraughts`)
- Create directory scaffold:
  - `data/{chess_standard,chess960,checkers_american,draughts_intl}/`
  - `chains/{real,shuffled}/{chess_standard,chess960,checkers_american,draughts_intl}/`
  - `results/raw/`, `results/blinded/`
  - `.gitkeep` files in empty directories
- Write `CLAUDE.md`:
  - Architecture and pipeline data flow
  - Module status table
  - Abstract label conventions for game domain
  - Session handoff protocol
- Write `pyproject.toml` (include `python-chess`, `pydraughts`,
  `polars`, `datasets` as dependencies), `requirements.txt`,
  `.env.example`, `.gitignore`
- Commit `SPEC.md` + `SPEC.pdf` + `PROGRAM_OUTLOOK.md` + initial code as
  pre-registration commit

**Gate 1 criterion:** Pre-registration commit on GitHub. Both authors
have reviewed and approved. T-code stubs are present but not
implemented.

---

### Session 2 — Chess data acquisition and validation

**Context:** Chess data streams directly from HuggingFace. No prior
download required. Use `datasets.load_dataset(..., streaming=True)` to
iterate the Parquet files, apply rating filter inline, and materialize a
filtered subset to local JSONL once. All subsequent sessions operate on
the materialized JSONL.

**Tasks:**
- Stream and materialize standard chess (`Lichess/standard-chess-games`):
  ```python
  from datasets import load_dataset
  ds = load_dataset("Lichess/standard-chess-games", split="train",
                    streaming=True)
  # iterate, apply WhiteElo >= 1800 AND BlackElo >= 1800 filter,
  # collect until 1,500-2,000 games (margin over the 1,200 chains/cell
  # target), write to data/chess_standard/games.jsonl
  ```
  - Sample 100 random games from the materialized JSONL, parse PGN
    movetext via `python-chess`, confirm games are valid and complete
  - Document the streaming snapshot date in `SESSION_LOG.md` for the
    eventual reproducibility appendix (HuggingFace datasets are
    versioned but the snapshot at acquisition time should be recorded)
- Stream and materialize Chess960 (`Lichess/chess960-chess-games`):
  ```python
  ds = load_dataset("Lichess/chess960-chess-games", split="train",
                    streaming=True)
  # same rating filter, same 1,500-2,000 game target
  # note: Chess960 dataset has FEN column with starting position;
  # include this in the materialized JSONL
  ```
  - Sample 100 random games, parse via `chess.Board(fen=fen,
    chess960=True)`, confirm validity
  - Save filtered subset to `data/chess960/games.jsonl`
- Confirm volumes are sufficient for 1,200 chains/cell target (both
  chess datasets are millions of rated-≥1800 games, so streaming until
  the materialization target is hit should not be a constraint)

**Gate 2a (chess) criterion:** Both chess sources streamed, filtered,
and materialized; at least 1,500 rated-≥1800 games per variant in JSONL
form; sample parsing confirms games are well-formed.

---

### Session 3 — Checkers data acquisition and validation

**Context:** Checkers PDN sources are not on HuggingFace. They must be
downloaded from canonical archives. Once downloaded, materialize to local
JSONL for all subsequent sessions.

**Tasks:**
- Acquire American checkers data (OCA + ACF):
  - Download OCA 2.0 archive from `http://fierz.ch/download.php`
    (~20,000 games)
  - If volume is insufficient after filtering, supplement from ACF
    tournament archives
  - Save raw PDN files to `data/checkers_american/raw/`
  - Document the source combination (which archives contributed how
    many games) and download dates in `SESSION_LOG.md`
- Validate American checkers data:
  - Load PDN files via `pydraughts.PDNReader` with `variant="american"`
  - Verify: each game has valid PDN structure, both sides played to at
    least 20 plies (American checkers games are typically shorter than
    chess; adjust ply threshold if needed based on data)
  - Sample 100 random games, parse, confirm validity
  - Save normalized JSONL to `data/checkers_american/games.jsonl`
- Acquire international draughts data (FMJD):
  - Download FMJD tournament archives from `https://fmjd.org` or linked
    PDN sources
  - Save raw PDN files to `data/draughts_intl/raw/`
  - Document source combination and download dates
- Validate international draughts data:
  - Load PDN files via `pydraughts.PDNReader` with `variant="standard"`
    (note: pydraughts uses "standard" for international 10x10)
  - Verify game structure
  - Sample 100 random games, parse, confirm validity
  - Save normalized JSONL to `data/draughts_intl/games.jsonl`
- Confirm volumes are sufficient for 1,200 chains/cell target

**Gate 2b (checkers) criterion:** Both checkers sources downloaded and
materialized; sufficient game volume; sample parsing confirms validity.

**Note:** Checkers PDN sources are smaller than chess datasets. If
either checkers source provides fewer than ~1,500 raw games (insufficient
margin for 1,200 chains/cell after filtering), pause for author review
before proceeding to Session 4. Per `SPEC.md`, the checkers cells are
the binding sample-size constraint and need to be confirmed before
investing in chain construction.

---

### Session 4 — Parser implementation (chess and checkers)

**Tasks:**
- Implement `src/parser_chess.py`:
  - Input: chess JSONL (from Session 2)
  - Use `python-chess` library
  - For Chess960: pass `chess960=True` to `chess.Board(fen=starting_fen,
    chess960=True)`
  - Each move becomes an event with metadata: from_square, to_square,
    piece, capture, check, phase_indicator
  - Output: `TrajectoryLog` per game (matching v2's TrajectoryLog
    interface)
- Implement `src/parser_checkers.py`:
  - Input: checkers JSONL (from Session 3)
  - Use `pydraughts.PDNReader` and `pydraughts.Board`
  - For American: `Board(variant="american")`; for international:
    `Board(variant="standard")`
  - Each move becomes an event with metadata: from_square, to_square,
    capture, king_made, phase_indicator
  - Note: pydraughts square numbering differs between variants (1-32 for
    American, 1-50 for international). Document the convention used in
    `parser_checkers.py` docstring.
  - Output: `TrajectoryLog` per game
- Implement `src/aggregation.py`:
  - Compress consecutive same-phase events
  - Output 15-25 event windows per game
- Add tests:
  - `tests/test_parser_chess.py` — fixture games (one standard, one
    Chess960), expected event sequences
  - `tests/test_parser_checkers.py` — fixture games (one American, one
    international), expected event sequences
  - `tests/test_aggregation.py` — window boundaries, edge cases

**Gate criterion:** All parser tests pass; sample TrajectoryLogs from
each source validate manually.

---

### Session 5 — Game T-code implementation

**Tasks:**
- Implement `src/translation.py` for game domain:
  - All six constraint dataclasses (matching v2 interface)
  - `translate_event(event, context) → Constraint` for each game type
  - `translate_trajectory(traj) → list[Constraint]`
  - Constraint type mapping logic per `SPEC.md §Constraint type mappings`
  - `InformationState` always emitted as `complete` (perfect-information
    note in `SPEC.md`)
- Adapt `src/observability.py` for game domain:
  - Asymmetric reveal of `OptimizationCriterion` (model can see piece
    types and move counts, not the engine evaluation)
  - Bucketing for piece labels (white_pawn, white_knight, etc.) to
    keep entity space manageable
- Adapt `src/renderer.py`:
  - Domain-blind English rendering of game constraints
  - Extended leakage check with chess + checkers vocabulary
  - All chess- and checkers-specific terms must be replaced with
    abstract analogs (no "pawn", "knight", "jump", "king", etc.)
- Add tests:
  - `tests/test_translation_game.py` — known game positions →
    expected constraints
  - `tests/test_renderer_leakage.py` — chains containing leakage
    vocabulary must fail rendering

**Gate criterion:** T-code tests pass; manual inspection of 10 randomly
selected rendered chains confirms no leakage and abstract structure.

**Push back if:** the constraint type mappings in `SPEC.md` feel like
forced fits when implementing the T-code. The pilot is a safety net but
mapping issues are easier to address now than after the T-code freezes.

---

### Session 6 — Pilot chain generation and inspection

**Tasks:**
- Generate pilot chains: 50 chains per cell (200 total chains)
- Build pilot chains using `scripts/build_chains.py`:
  ```bash
  python scripts/build_chains.py --source chess_standard \
    --data data/chess_standard/games.jsonl \
    --out-real chains/real/chess_standard/ \
    --out-shuffled chains/shuffled/chess_standard/ \
    --target 50 --pilot
  ```
  (Repeat for all four cells)
- Pilot inspection (both authors):
  - Constraint type distribution (per `SPEC.md §Pilot validation`)
  - Chain length distribution (15-25 target)
  - Renderer output for 5 random chains per cell — read and verify
    abstractness
  - Leakage check pass rate (must be 100%)
  - Spot-check shuffled variants — ensure shuffle is meaningful
  - **Critical**: measure both-actionable filter retention rate per cell
    using a pilot evaluation. If retention rates are substantially below
    the SPEC's 83% assumption, escalate before proceeding to Session 7.
- If pilot fails any criterion: pause for author review, do not
  auto-fix and proceed
- If pilot passes: tag T-code as `T-code-game-v1.0-frozen` in git
  - This freezes `src/translation.py`, `src/aggregation.py`, and
    `src/renderer.py` for the rest of v3

**Gate 3 criterion:** Pilot passes all inspection criteria; T-code is
frozen at git tag.

**Push back if:** the both-actionable filter retention rate comes in
much lower than 83% (say, below 65%). The 1,200 chains/cell target may
be insufficient to hit 1,000 paired evaluations per cell. Flag this at
Gate 3 — do not proceed to full generation in Session 7 until this is
discussed.

---

### Session 7 — Full chain generation

**Tasks:**
- Generate full chains: 1,200 real chains per cell (4,800 total real
  chains; 14,400 total shuffled chains across 3 shuffle seeds per real)
- Estimated runtime: 30-60 minutes per cell (chain generation is CPU-
  bound, not API-bound at this stage)
- Validate output:
  - File counts match expectations
  - All chains pass leakage check
  - Distribution of chain lengths matches pilot expectations

**Gate 4 criterion:** All four cells have 1,200 real + 3,600 shuffled
chains; all pass leakage check.

---

### Session 8 — Reference distribution build

**Tasks:**
- Build reference distributions for each cell:
  ```bash
  python -m src.reference build-raw --source chess_standard \
    --raw data/chess_standard/games.jsonl \
    --out data/reference_chess_standard.pkl
  ```
  (Repeat for all four cells)
- Coverage check on each:
  ```bash
  python -m src.reference check \
    --dist data/reference_chess_standard.pkl \
    --chains chains/real/chess_standard/ --target 0.9
  ```

**Gate 5 criterion:** All four reference distributions built; coverage
≥ 0.9 for each (matching v2 standard).

---

### Session 9 — Live API dry-run

**Tasks:**
- Run dry-run evaluation on 5 chains per cell (both Haiku and Sonnet)
  to verify API integration:
  ```bash
  python -m src.runner --model haiku --source chess_standard \
    --chains chains/real/chess_standard/ \
    --seed 42 --dry-run --n 5
  ```
- Verify response parsing, blinding, result file format
- Estimate full evaluation cost based on dry-run token counts

**Gate 6 criterion:** Dry-run succeeds without errors on all four
cells; cost estimate within budget.

---

### Session 10 — Phase 1 full evaluation (Haiku)

**Tasks:**
- Run full Phase 1 evaluation: Haiku across all four cells, three
  seeds (T=0.0/seed=42 primary; T=0.5/seed=1337 and T=0.5/seed=7919
  variance study)
  ```bash
  python scripts/run_evaluation_phase1.py
  ```
- Use Anthropic Messages Batches API (50% cost reduction)
- Monitor for technical failures: API errors, malformed responses,
  missing pairs
- Do NOT compute gap statistics across cells during the run
- Save raw results to `results/raw/phase1/`

**Gate 7 criterion:** All four Haiku cells × three seeds evaluated;
no missing pairs; no API errors above pre-specified tolerance (< 1%
of evaluations).

---

### Session 11 — Phase 1 → Phase 2 gate evaluation

**Tasks:**
- Run scorer on Phase 1 results:
  ```bash
  python -m src.scorer --results results/raw/phase1/ \
    --dist-chess-standard data/reference_chess_standard.pkl \
    --dist-chess960 data/reference_chess960.pkl \
    --dist-checkers-american data/reference_checkers_american.pkl \
    --dist-draughts-intl data/reference_draughts_intl.pkl \
    --bonferroni-divisor 4 \
    --out results/scored_phase1.json
  ```
- Evaluate gate criteria from `SPEC.md §Phase 1 → Phase 2 gate`:
  - Run Sonnet criteria (any one triggers Phase 2)
  - Skip Sonnet criteria (all required to skip Phase 2)
  - Default to running Phase 2 if ambiguous
- Document gate decision in `SESSION_LOG.md` with full criterion
  evaluation
- If skipping Phase 2: proceed to Session 13 (final scoring with
  Bonferroni divisor 4)
- If running Phase 2: proceed to Session 12

**Gate 8 criterion:** Gate decision is documented and matches the
pre-registered criteria. No deviations from the gate logic.

---

### Session 12 — Phase 2 evaluation (Sonnet, conditional on gate)

**Tasks:** (only if Phase 2 triggered by Gate 8)
- Run full Phase 2 evaluation: Sonnet across all four cells, three
  seeds (same configs as Phase 1)
  ```bash
  python scripts/run_evaluation_phase2.py
  ```
- Same monitoring as Phase 1 (technical only, no effect-size peeking)
- Save raw results to `results/raw/phase2/`

**Gate 9 criterion:** All four Sonnet cells × three seeds evaluated;
no missing pairs.

---

### Session 13 — Final scoring

**Tasks:**
- Run scorer on all completed phases:
  ```bash
  python -m src.scorer --results results/raw/ \
    --dist-chess-standard data/reference_chess_standard.pkl \
    --dist-chess960 data/reference_chess960.pkl \
    --dist-checkers-american data/reference_checkers_american.pkl \
    --dist-draughts-intl data/reference_draughts_intl.pkl \
    --bonferroni-divisor [4 or 8 based on Phase 2 gate] \
    --out results/scored.json
  ```
- Run supplementary analyses per `SPEC.md §Pre-registered Supplementary Analyses`:
  - Per-config variance study
  - Within-family contrast tests with 95% CI
  - Cross-family contrast
  - Comparison to v1 and v2 effect sizes
  - Constraint-type carrier analysis
  - Sonnet-vs-Haiku gap compression analysis (if Phase 2 ran)
- Generate `results/scored.json` and `results/supplementary.json`
- Save plots to `results/plots/`

**Gate 10 criterion:** Scorer output matches pre-registered methodology;
all supplementary analyses complete; plots generated.

---

### Session 14 — Hypothesis evaluation and write-up

**Tasks:**
- Evaluate hypothesis-pattern outcomes per `SPEC.md §Pre-registered hypothesis-pattern outcomes`:
  - Hypothesis supported / partially supported / refuted / inconclusive
- Reference `PROGRAM_OUTLOOK.md` for v4 direction implications
- Draft `RESULTS.md`:
  - Status, abstract, hypothesis statement
  - Pre-registered success criteria with results
  - Methods (data sources, pipeline, eval params, scoring layers,
    methodology disclosure)
  - Results (primary cells table, all-cutoffs table, threshold check,
    variance study)
  - Discussion (what evidence supports / doesn't support; hypothesis
    outcome; comparison to v1/v2; implications and caveats)
  - Supplementary analyses summary
  - Conclusion
  - Appendix A: Reproducibility (include exact HuggingFace dataset
    versions / snapshot dates and PDN archive URLs/dates)
  - Appendix B: Methodology consistency with v1/v2
- Co-author review before commit

**Gate criterion:** `RESULTS.md` reviewed and approved by both authors;
hypothesis outcome documented; v4 direction implications referenced.

---

### Session 15 — Cleanup, documentation, publication-ready state

**Tasks:**
- Update `README.md` with v3 status and links to v1/v2
- Verify all code paths reproducible from raw results
- Pin all dependencies in `requirements.txt`
- Tag final v3 commit (e.g., `v3.0-published`)
- Document any deviations from spec in `DEVIATIONS.md` (if any —
  expected: zero or near-zero)

**Final gate:** Repository is publication-ready. v3 results document
is complete and reviewed.

---

## Cost estimate

| Phase | Cells × Seeds × Models | Estimated cost |
|-------|------------------------|----------------|
| Dry-run (Session 9) | 4 × 1 × 2 × 5 chains | ~$1-2 |
| Phase 1 (Haiku) | 4 × 3 × 1 × 1,200 chains × 4 (1 real + 3 shuffled) | ~$60-120 |
| Phase 2 (Sonnet, if triggered) | 4 × 3 × 1 × 1,200 chains × 4 | ~$200-280 |
| **Total if Phase 2 runs** | | **~$260-400** |
| **Total if Phase 1 only** | | **~$60-120** |

All costs assume Anthropic Messages Batches API (50% cost reduction).
Estimates calibrated against v2 actual evaluation costs scaled by chain
count.

---

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Pilot reveals chain construction failure | Medium | High | Gate 3 pauses execution; investigate before full generation |
| Both-actionable retention rate below SPEC assumption | Medium | High | Gate 3 measures retention; flag before Session 7 if <65% |
| Checkers PDN sources insufficient for 1,200 chains/cell | Medium | High | Validate volumes at Gate 2b; flag before Session 4 if insufficient |
| Pydraughts library issues with American/international parsing differences | Low | Medium | Add extra parser tests in Session 4; manual validation on more samples |
| Phase 1 results ambiguous (gate criteria neither clearly run nor skip) | Medium | Low | Pre-registered default is to run Phase 2 |
| Per-cell power post-hoc < 70% on key cells | Low | High | Disclosed in supplementary; v3 result becomes "inconclusive" per `SPEC.md` |
| API rate limits hit during full evaluation | Low | Low | Batches API has its own rate limits; budget extra time for Phase 1 and 2 |
| Sonnet 4.6 deprecated / unavailable at Phase 2 time | Low | High | Document at evaluation time; if necessary, use closest successor with explicit deviation note |

---

## Coordination protocol with authors

- **Daily**: `SESSION_LOG.md` updated with completed tasks, gate
  status, blockers
- **Per-gate**: Both authors review gate output before proceeding
- **Pre-Phase-2 decision**: Lead author confirms gate criteria
  evaluation before Sonnet run begins
- **Pre-results-publication**: Co-author reviews `RESULTS.md` draft
  before commit
- **Spec amendments**: Any spec changes require both-author sign-off
  AND a dated supplementary spec doc; do not silently work around
  spec constraints

---

*Drafted [DATE]. Will be updated as Sessions complete.*
