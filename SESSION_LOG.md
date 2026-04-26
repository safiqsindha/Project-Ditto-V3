# Project Ditto v3 — Session Log

---

## Session 1 — 2026-04-25

**Tasks completed:**
- Initialized git repository; set remote to `github.com/safiqsindha/Project-Ditto-V3`
- Read SPEC.md, PROGRAM_OUTLOOK.md, BUILD_PLAN.md in full
- Read v2 repository at `github.com/safiqsindha/Project-Ditto-v2` for code reuse patterns
- Created full directory scaffold:
  - `data/{chess_standard,chess960,checkers_american/raw,draughts_intl/raw}/`
  - `chains/{real,shuffled}/{chess_standard,chess960,checkers_american,draughts_intl}/`
  - `results/{raw/phase1,raw/phase2,blinded,plots}/`
  - `.gitkeep` files in all empty directories
- Copied domain-blind v2 modules (unchanged):
  - `src/filter.py` — adapted chain validity for game length (15–25 vs v2's 20–40)
  - `src/shuffler.py` — verbatim copy (domain-blind)
  - `src/normalize.py` — verbatim copy (domain-blind)
- Adapted from v2 for game domain:
  - `src/runner.py` — SOURCES updated to [chess_standard, chess960, checkers_american, draughts_intl]
  - `src/prompt_builder.py` — PROMPT_VERSION="v3.0-game"; "pipeline" → "sequential decision process"
  - `src/renderer.py` — extended leakage vocabulary with chess + checkers terms (SPEC §Renderer leakage vocabulary)
  - `src/scorer.py` — ACTIONABLE_TYPES updated (removed InformationState, added CoordinationDependency, OptimizationCriterion per SPEC §Both-actionable filter); sources updated
  - `src/reference.py` — active_pair = (current_phase, last_move_type); updated entity labels
  - `src/observability.py` — entity labels for game domain (piece_N / phase labels)
- Created stubs (raise NotImplementedError, with docstrings and design notes):
  - `src/translation.py` — dataclasses defined (identical interface to v1/v2); translate_event/translate_trajectory stubbed
  - `src/aggregation.py` — aggregate_trajectory stubbed
  - `src/parser_chess.py` — parse_pgn_game / parse_games_jsonl stubbed
  - `src/parser_checkers.py` — parse_pdn_game / parse_games_jsonl stubbed
- Created `src/__init__.py`, `tests/__init__.py`
- Copied test: `tests/test_shuffler.py` — adapted source labels for game domain
- Wrote `CLAUDE.md` — architecture, module status, abstract label conventions, session protocol
- Wrote `pyproject.toml`, `requirements.txt`, `.env.example`, `.gitignore`
- Pre-registration commit created: "Pre-registration commit — thresholds and methodology frozen"

**Gate status:** Gate 1 PENDING — pre-registration commit is on GitHub; requires both-author sign-off before evaluation begins. T-code stubs are present but not implemented (correct — freeze happens after Session 6 pilot).

**Files created/modified:**
```
CLAUDE.md
SPEC.md (from working dir)
SPEC.pdf (from working dir, renamed Spec.pdf → SPEC.pdf)
PROGRAM_OUTLOOK.md
BUILD_PLAN.md
SESSION_LOG.md (this file)
pyproject.toml
requirements.txt
.env.example
.gitignore
src/__init__.py
src/filter.py
src/shuffler.py
src/normalize.py
src/runner.py
src/prompt_builder.py
src/renderer.py
src/scorer.py
src/reference.py
src/observability.py
src/translation.py (stub)
src/aggregation.py (stub)
src/parser_chess.py (stub)
src/parser_checkers.py (stub)
tests/__init__.py
tests/test_shuffler.py
data/{cell}/.gitkeep (x4)
chains/real/{cell}/.gitkeep (x4)
chains/shuffled/{cell}/.gitkeep (x4)
results/raw/phase1/.gitkeep
results/raw/phase2/.gitkeep
results/blinded/.gitkeep
results/plots/.gitkeep
```

**Blockers / open questions:**
- Gate 1 requires co-author (Myriam) sign-off — flag for Safiq to coordinate
- SPEC.md has placeholder `[DATE]` and `[Co-author name]` — Safiq should fill these in before the pre-registration is considered fully frozen
- Note: `filter.py` validity criteria adapted for games (length 15–25, ≥1 SubGoalTransition, ≥1 ToolAvailability, ≥3 ResourceBudget) — v2 had stricter counts for programming domain. Pilot in Session 6 will validate these thresholds against actual game chain distributions; flag if too loose or tight.

**Next session (Session 2) planned tasks:**
- Stream and materialize standard chess data: `Lichess/standard-chess-games` via HuggingFace `datasets` library
  - Apply rating filter: `WhiteElo >= 1800 AND BlackElo >= 1800`
  - Collect 1,500–2,000 games, write to `data/chess_standard/games.jsonl`
  - Sample 100 games, parse via python-chess, confirm validity
  - Record HuggingFace snapshot date in SESSION_LOG.md
- Stream and materialize Chess960 data: `Lichess/chess960-chess-games`
  - Same rating filter; include FEN column in output JSONL
  - Sample 100 games, parse via `chess.Board(fen=fen, chess960=True)`, confirm validity
  - Write to `data/chess960/games.jsonl`
  - Record snapshot date
- Confirm volumes sufficient for 1,200 chains/cell target
- Gate 2a: both chess sources validated

---

## Session 2 — 2026-04-26

**Tasks completed:**
- Streamed and materialized standard chess from `Lichess/standard-chess-games` (HuggingFace)
  - Rating filter: WhiteElo ≥ 1800 AND BlackElo ≥ 1800
  - 2,000 games written to `data/chess_standard/games.jsonl`
  - Snapshot: 2026-04-26 00:27 UTC
  - Sample validation (python-chess): examined ~26k records to collect 2k rated games
- Streamed and materialized Chess960 from `Lichess/chess960-chess-games` (HuggingFace)
  - Same rating filter; FEN column preserved for Chess960 board setup
  - 2,000 games written to `data/chess960/games.jsonl`
  - Snapshot: 2026-04-26 00:28 UTC
- Written `scripts/acquire_chess.py` — streaming + filter + PGN validation
- Key fixes discovered:
  - HuggingFace field name is `movetext` (not `Moves`)
  - Records contain Python `datetime.date` objects; serialization requires custom `default=_jsonify`
  - Chess960 PGN validation requires wrapping FEN header: `[FEN "..."]\n[Variant "Chess960"]\n\n{movetext}`
  - Python 3.9 union type syntax `X | Y` fails at runtime; use `Union[X, Y]` from typing
  - User site-packages path must be added to sys.path manually

**Gate status:** Gate 2a PASSED — both chess sources validated, 2,000 games/cell

**Files created/modified:**
```
data/chess_standard/games.jsonl (2000 lines)
data/chess960/games.jsonl (2000 lines)
data/acquisition_summary.json
scripts/acquire_chess.py
```

**Blockers / open questions:** none

**Next session (Session 3) planned tasks:**
- Download American checkers (OCA 2.0 PDN) and International draughts (FMJD/wiegerw sources)
- Materialize both to JSONL
- Gate 2b: both checkers sources ≥ 1,500 raw games

---

## Session 3 — 2026-04-26

**Tasks completed:**
- Downloaded American checkers (OCA 2.0):
  - Source: `data/checkers_american/raw/OCA_2.0.pdn` (22,621 games)
  - 2,000 games written to `data/checkers_american/games.jsonl` (all valid)
- Downloaded International draughts (10x10):
  - Source discovery: wiegerw/pdn (484 games from succeed/fail folders), then Lidraughts API
  - Lidraughts API discovery: `https://lidraughts.org/api/games/user/{username}?variant=standard`
    and `/api/tournament/{id}/games` both return PDN with `[GameType "20"]`
  - Key insight: Lidraughts is open-source fork of Lichess (https://github.com/RoepStoep/lidraughts)
    → same API patterns as Lichess
  - Downloaded from 3 working tournaments (392 games) + users roepstoep/special/Cacadosse/others
  - Total unique international draughts games: 3,890 valid after dedup + length filter
  - 2,000 games written to `data/draughts_intl/games.jsonl`
- Written `scripts/acquire_checkers.py` — PDN parsing, dedup by Lidraughts game ID, length filter
- Written `scripts/download_lidraughts_tournaments.py` and `scripts/download_lidraughts_users.py`

**Gate status:** Gate 2b PASSED — both checkers sources well above 1,500 threshold
  - checkers_american: 22,621 loaded, 22,619 valid ✅
  - draughts_intl: 4,157 loaded (after dedup), 3,890 valid ✅

**Files created/modified:**
```
data/checkers_american/games.jsonl (2000 lines)
data/draughts_intl/games.jsonl (2000 lines)
data/checkers_acquisition_summary.json
data/draughts_intl/raw/lidraughts/*.pdn (tournament exports)
data/draughts_intl/raw/lidraughts_users/*.pdn (user exports)
scripts/acquire_checkers.py
scripts/download_lidraughts_tournaments.py
scripts/download_lidraughts_users.py
```

**Blockers / open questions:** none

**Next session (Session 4) planned tasks:**
- Implement `src/parser_chess.py`: python-chess based PGN parser
  - parse_pgn_game(record, chess960=False) → TrajectoryLog
  - parse_games_jsonl(path, chess960, limit) → list[TrajectoryLog]
- Implement `src/parser_checkers.py`: draughts-library PDN parser
  - parse_pdn_game(record, variant) → TrajectoryLog
  - parse_games_jsonl(path, variant, limit) → list[TrajectoryLog]
- Implement `src/aggregation.py`: windowing to 15–25 events
- Unit tests for all three modules
- Gate 3: parsers produce valid TrajectoryLog objects on ≥95% of sampled games

---

## Session 4 — 2026-04-26

**Tasks completed:**
- Implemented `src/parser_chess.py`:
  - parse_pgn_game(record, chess960=False) → TrajectoryLog
  - parse_games_jsonl(path, chess960, limit) → Iterator[TrajectoryLog]
  - Phase detection: opening (ply<20 + material>50), endgame (no queens or material<20), middlegame (else)
  - Abstract piece labels: piece_A...piece_L (white pawn→piece_A, black king→piece_L, etc.)
  - Abstract square labels: sq_0...sq_63 (a1=0, h8=63)
  - Captures, promotions, castling correctly classified
  - Material counts stored in event metadata for T-code use
- Implemented `src/parser_checkers.py`:
  - parse_pdn_game(record, variant) → TrajectoryLog
  - parse_games_jsonl(path, variant, limit) → Iterator[TrajectoryLog]
  - Supports VARIANT_AMERICAN ("american") and VARIANT_INTERNATIONAL ("standard")
  - Uses draughts.Board + draughts.Move for position tracking + FEN parsing
  - Phase detection: by piece count fraction (opening >80%, endgame <45%)
  - Abstract piece labels: piece_A (white man), piece_B (white king), piece_C (black man), piece_D (black king)
  - Multi-captures (e.g. "18x27x36") handled via draughts.Move(board, pdn_move=...)
  - Promotions detected by comparing pre/post FEN piece types
- Implemented `src/aggregation.py`:
  - compute_windows(traj) → list of (start, end) index pairs, non-overlapping, length 15–25
  - aggregate_trajectory(traj, start, end) → list[GameEvent], capped at 25
  - extract_all_windows(traj) → all valid windows from one trajectory
  - sample_window(traj, rng) → one random valid window
  - Phase-boundary-aware window selection
- Written `tests/test_parsers.py`: 27 tests covering all four cells + aggregation + Gate 3

**Gate status:** Gate 3 PASSED — 100% parse success on 100 games/cell (all four cells)
  - chess_standard: 100/100 ✅
  - chess960: 100/100 ✅
  - checkers_american: 100/100 ✅
  - draughts_intl: 100/100 ✅

**Key implementation notes:**
- draughts library installed as `import draughts` (NOT `import pydraughts`)
- draughts.Board("american") creates 8x8 board; draughts.Board("standard") creates 10x10
- draughts.Move(board, pdn_move="33-28") creates move from PDN string
- board.fen is a property (not method) in this version
- FEN format: `{turn}:W{squares}:B{squares}` where K prefix = king

**Files created/modified:**
```
src/parser_chess.py
src/parser_checkers.py
src/aggregation.py
tests/test_parsers.py
```

**Blockers / open questions:** none

**Next session (Session 5) planned tasks:**
- Implement `src/translation.py` T-code:
  - translate_event(event, context) → list[Constraint]
  - translate_trajectory(events) → list[Constraint]
  - Map all 6 constraint types to game events (SPEC §Constraint type mappings)
  - ResourceBudget from material counts in event metadata
  - ToolAvailability from captures (piece → UNAVAILABLE permanently) and moves (piece → AVAILABLE)
  - SubGoalTransition from phase_indicator changes
  - InformationState: constant complete (non-actionable)
  - CoordinationDependency from piece coordination patterns
  - OptimizationCriterion from move type inference
- Verify T-code outputs pass both-actionable filter (≥1 SubGoalTransition, ≥1 ToolAvailability, ≥1 CoordinationDependency, ≥1 OptimizationCriterion)
- Run 50-game pilot (Session 6 prep)

---

## Session 5 — 2026-04-25

**Tasks completed:**
- Implemented `src/translation.py` T-code (full six-type constraint mapping):
  - `translate_event(event, context)` → single Constraint, using priority-ordered dispatch
  - `translate_trajectory(events, variant)` → list[Constraint], one per event, with state tracking
  - Six constraint types fully mapped:
    - ResourceBudget: material counts normalised (chess /39, checkers /initial_pieces); periodic slot at pos%4==3 (highest-priority periodic slot)
    - ToolAvailability: UNAVAILABLE on capture; AVAILABLE on non-capture move; periodic fallback at pos≥window//2 if no TA yet
    - SubGoalTransition: phase change (opening→middlegame→endgame); promotion; tactical turning point (capture after quiet); periodic slot at pos%8==0 if SGT count below target
    - InformationState: constant COMPLETE (non-actionable, lowest priority)
    - CoordinationDependency: check events; high-value pieces; balance fallback
    - OptimizationCriterion: inferred from move type (material_gain, king_safety, mobility)
  - Priority order (prevents starvation): phase-change SGT > promotion SGT > tactical SGT > periodic SGT > periodic RB > capture TA > late TA fallback > check CD > IS periodic > high-piece CD > balance CD/OC
- Validated filter pass rates on 100-game sample per cell:
  - chess_standard: 94.5% (409/433 windows pass ≥15 events + ≥1 SGT + ≥1 TA + ≥3 RB)
  - chess960: 94.5% (446/472 windows pass)
  - checkers_american: 86.6% (271/313 windows pass)
  - draughts_intl: 93.5% (594/635 windows pass)
- Ran full pipeline test (parse → aggregate → translate → filter → shuffle → render):
  - All shuffled chains (seeds 42, 1337, 7919) pass renderer leakage check
  - No domain vocabulary in rendered output
- Key bug fixes during implementation:
  - ResourceBudget starvation: moved periodic RB to pos%4==3 with HIGHER priority than capture handler → pass rates rose from ~66% to 94%+
  - SGT coverage: added tactical-opening SGT (capture after quiet move) and periodic SGT (pos%8==0) → pass rates rose from ~30% to ~66% before RB fix
  - Renderer test bug: must pass Constraint objects (not dataclasses.asdict() dicts) to render_chain()
  - Shuffler test bug: chain dict requires chain_id and match_id keys

**Gate status:** Session 5 has no formal gate — filter pass rates are informational targets (≥80% target in BUILD_PLAN.md). All four cells exceed 80%. Gate 6 pilot (Session 6) is next.

**Files created/modified:**
```
src/translation.py (full T-code implementation — was stub)
SESSION_LOG.md (this entry)
```

**Blockers / open questions:** none

**Next session (Session 6) planned tasks:**
- Generate 50 pilot chains per cell (all 4 cells) using T-code
- Inspect constraint type distribution across 50 chains per cell
- Leakage check: 100% of rendered chains pass renderer.leakage_check()
- Spot-check 3–5 rendered chains per cell for qualitative correctness
- Freeze T-code: git tag `T-code-game-v1.0-frozen` on translation.py + aggregation.py + renderer.py
- Gate 6: pilot inspection passes (no leakage, ≥80% chain validity, plausible constraint distributions)

---

## Session 6 — 2026-04-25

**Tasks completed:**
- Generated 50 pilot chains per cell (all 4 cells) using `scripts/generate_pilot_chains.py`
- Inspected constraint type distribution: all 6 types present across all cells, distributions reasonable
  - chess_standard: CD 6.32/chain, OC 3.78/chain, RB 4.96/chain, SGT 2.92/chain, TA 2.82/chain, IS 1.74/chain
  - chess960:       CD 5.88/chain, OC 3.82/chain, RB 4.68/chain, SGT 2.80/chain, TA 3.02/chain, IS 1.74/chain
  - checkers_american: CD 5.02/chain, OC 3.36/chain, RB 4.32/chain, SGT 3.28/chain, TA 3.14/chain, IS 1.66/chain
  - draughts_intl:  CD 5.70/chain, OC 4.02/chain, RB 4.74/chain, SGT 3.08/chain, TA 3.10/chain, IS 1.96/chain
- Leakage check: 0 failures across all 200 chains (50 per cell × 4 cells)
- Bug found and fixed: renderer.py `render_trajectory_chain()` was passing raw cell name (e.g.
  "chess960") as perspective label → leakage vocabulary triggered on chain header
  Fix: added `_CELL_TO_PERSPECTIVE` mapping (chess960 → "sequential_process_B", etc.)
- Frozen T-code at git tag `T-code-game-v1.0-frozen`:
  - `src/translation.py` (translate_event, translate_trajectory, all dataclasses)
  - `src/aggregation.py` (compute_windows, aggregate_trajectory, extract_all_windows, sample_window)
  - `src/renderer.py` (render_chain, render_trajectory_chain, check_leakage, _CELL_TO_PERSPECTIVE)

**Gate status:** Gate 6 PASSED — all four cells pass all pilot inspection criteria
  - chess_standard:    pass_rate=87.7%, chains=50/50, leakage_failures=0, types=6/6 ✅
  - chess960:          pass_rate=96.2%, chains=50/50, leakage_failures=0, types=6/6 ✅
  - checkers_american: pass_rate=87.7%, chains=50/50, leakage_failures=0, types=6/6 ✅
  - draughts_intl:     pass_rate=94.3%, chains=50/50, leakage_failures=0, types=6/6 ✅

**Files created/modified:**
```
src/renderer.py (added _CELL_TO_PERSPECTIVE mapping, updated render_trajectory_chain)
scripts/generate_pilot_chains.py (new)
chains/pilot/chess_standard/pilot_chains.jsonl (50 chains)
chains/pilot/chess_standard/pilot_stats.json
chains/pilot/chess960/pilot_chains.jsonl (50 chains)
chains/pilot/chess960/pilot_stats.json
chains/pilot/checkers_american/pilot_chains.jsonl (50 chains)
chains/pilot/checkers_american/pilot_stats.json
chains/pilot/draughts_intl/pilot_chains.jsonl (50 chains)
chains/pilot/draughts_intl/pilot_stats.json
chains/pilot/pilot_summary.json
SESSION_LOG.md (this entry)
```
Git tag: T-code-game-v1.0-frozen

**Blockers / open questions:** none

**Next session (Session 7) planned tasks:**
- Generate full chains: 1,200 real chains per cell × 4 cells = 4,800 chains
- For each valid chain, generate 3 shuffled variants (seeds 42, 1337, 7919) = 14,400 shuffled
- Write to chains/real/{cell}/*.jsonl and chains/shuffled/{cell}/*.jsonl
- Each JSONL record includes: chain_id, cell, game_id, variant, length, constraint_types, rendered
- Shuffled records include: chain_id, match_id (= real chain_id), seed, rendered

---

## Session 6 (continued) — leakage hardening pass — 2026-04-25

**Trigger:** Author paused before Session 7 to ask whether silent leakage was
possible based on V1/V2 experience. Investigation surfaced a critical class of
silent failures the existing word-boundary regex could not catch.

**Root cause identified:**
- Python `\b` word boundary treats `_` as a word character, so the regex
  `\bwhite\b` does NOT match inside `material_white`.
- CLAUDE.md prescribed several abstract labels (`material_white`, `material_black`,
  `king_safety`, `pawn_chain_B`, `battery_A`, `back_row_C`) that embed chess
  vocabulary. The leakage check silently passed all of these despite the
  embedded words being clearly visible to a human reader (or LLM evaluator).
- These prescriptions actively violated SPEC.md §Renderer leakage vocabulary,
  which lists "king", "pawn", "battery"-class terms as leakage. The rename
  brings the codebase INTO SPEC compliance — no SPEC supplement required.

**Tasks completed:**
- Built authoritative glossary `src/leakage_glossary.py` (158 entries, 23 categories)
  - Sources: Wikipedia Glossary of Chess, Wikipedia English Draughts, Wikipedia
    PDN spec, Chess.com terms, SPEC.md, curator domain knowledge
  - Each entry tagged with: term, category, severity (high/medium/low),
    definition, source, optional curator note, added_session
  - Categories include: chess.piece, checkers.piece, chess.tactic, chess.rule,
    chess.mate, chess.geometry, chess.structure, board.geometry, color.side,
    game.name, notation.format, metadata.body, engine, format.time,
    chess.strategy, result.token, chess.phase
- Refactored `src/renderer.py`:
  - Imports vocabulary from `leakage_glossary` (single source of truth)
  - Hard check uses pre-compiled alternation regex (~6× faster)
  - Added `check_leakage_substring()` soft check with relaxed boundaries
    (treats `_` as non-word so `material_white` triggers, but uses
    alphanumeric lookarounds so `permanent` doesn't false-positive on "man")
  - Soft check supports explicit exemptions (`phase_opening`, etc.)
- Renamed embedded-word labels in `src/translation.py`:
  - `material_{side}` → `resource_{side}` (was containing "material")
  - `tempo_remaining` → `progress_remaining` (was containing "tempo")
  - `tempo_advantage` → `progress_advantage`
  - `material_gain` → `resource_gain`
  - `material_exchange` → `resource_exchange`
  - `king_safety` → `objective_safety`
  - `battery_A/B` → `coordination_A/B`
  - `back_row_A/B` → `formation_A/B`
  - `positional_transition` → `structural_transition`
  - `tactical_shift` → `opportunity_shift`
  - `control_center` → `central_focus`
  - `defend_position` → `defend_zone`
  - `position` (objective) → `structural`
  - `weight_shift` formula: kept `phase_` prefix → `phase_endgame_priority`
    instead of bare `endgame_priority`
- Updated `tests/test_shuffler.py` fixtures (3 string updates)
- Updated `CLAUDE.md` abstract-label table with all renames + hardening note
- Re-ran pilot — all 4 cells pass HARD AND SOFT checks at the same pass rates
  (87.7%, 96.2%, 87.7%, 94.3%) with 0 leakage warnings under either check
- Full test suite: 42/42 pass

**Gate status:** Gate 6 RE-PASSED with hardened checks
  - chess_standard:    pass_rate=87.7%, hard=0, soft=0 ✅
  - chess960:          pass_rate=96.2%, hard=0, soft=0 ✅
  - checkers_american: pass_rate=87.7%, hard=0, soft=0 ✅
  - draughts_intl:     pass_rate=94.3%, hard=0, soft=0 ✅

**Files created/modified:**
```
src/leakage_glossary.py (NEW — 158 entries, single source of truth)
src/renderer.py (imports glossary; hard regex compiled; soft check added)
src/translation.py (12 label renames; phase-prefix preserved in weight_shift)
tests/test_shuffler.py (fixture renames: material_white, material_exchange,
                       tempo_remaining → resource_side_1, resource_exchange,
                       progress_remaining)
scripts/generate_pilot_chains.py (calls both hard + soft check; reports both)
chains/pilot/*/pilot_chains.jsonl (regenerated with new labels)
chains/pilot/*/pilot_stats.json (regenerated with both gate-check fields)
chains/pilot/pilot_summary.json (regenerated)
CLAUDE.md (abstract-label table updated; module status updated)
SESSION_LOG.md (this addendum)
```
Git tag `T-code-game-v1.0-frozen` advanced from previous commit to current HEAD
after the hardened pilot passed. The previous tag location remains in git
history (via reflog).

**Blockers / open questions:** none

**Decision log (Session 6 hardening):**
- Internal metadata keys (`material_side_1` in parser_chess.py event metadata,
  `white_pieces`/`black_pieces` in parser_checkers.py event metadata) were
  left as-is — they never flow into rendered output (only into a numeric
  lookup that produces a float). Renaming was deferred as P2 cleanup.
- Phase concept words (`phase_opening`, `phase_middlegame`, `phase_endgame`)
  are exempted from soft check — the `phase_` prefix is the abstraction
  marker, and an LLM seeing these can infer "sequential process with phase
  transitions" but cannot distinguish chess from any other phase-structured
  game.
- Soft check is a development guardrail, not a runtime gate. The hard check
  remains the enforced rendering gate. Soft check is invoked in pilot/full
  generation scripts but not in `render_chain()` itself.

---

## Session 7 — 2026-04-25

**Tasks completed:**
- Wrote `scripts/generate_full_chains.py`:
  - Loads up to 2,000 trajectories per cell from materialized JSONL
  - Generates valid windows → translates → validates → renders → leakage-checks
  - Writes one JSONL file per chain (matches runner.py's `_load_chain` expectation)
  - For each real chain, generates 3 shuffled variants with seeds 42, 1337, 7919
    (re-rendered after permutation; both hard- and soft-leakage checked)
  - Schema per chain: chain_id, match_id, source, variant, game_id, length,
    constraint_types, cutoff_k, focal_action, constraints (serialized dicts),
    rendered, seed (None for real)
  - Verified schema with 5-chain sanity run before full execution
- Generated complete chain set:
  - chess_standard:    1,200 real + 3,600 shuffled = 4,800 files
  - chess960:          1,200 real + 3,600 shuffled = 4,800 files
  - checkers_american: 1,200 real + 3,600 shuffled = 4,800 files
  - draughts_intl:     1,200 real + 3,600 shuffled = 4,800 files
  - **Total: 4,800 real + 14,400 shuffled = 19,200 chain files**
- Hard leakage failures: **0** across all 19,200 chains (real + shuffled)
- Soft leakage warnings: **0** across all rendered chains

**Gate status:** Session 7 had no formal gate — Session 6 pilot already
established that the T-code passes both leakage checks. This session was
production-scale execution. All cells hit the 1,200 real chain target.

**Per-cell metrics (full population pass rates):**
| Cell | Pass rate | Windows scanned | Source games used | Time |
|---|---|---|---|---|
| chess_standard | 95.2% | 1,261 | 207 / 2,000 | ~25s |
| chess960 | 94.4% | 1,272 | 197 / 2,000 | ~25s |
| checkers_american | 85.2% | 1,408 | 467 / 2,000 | ~25s |
| draughts_intl | 93.0% | 1,290 | 201 / 2,000 | ~22s |

(Wall time dominated by trajectory parsing — ~15 minutes total parsing across
4 cells; chain generation itself is ~25s per cell at ~50 chains/sec.)

**Validity failure breakdown (matches Session 6 finding — 100% rb_below_min in every cell):**
| Cell | Invalid windows | All rb_below_min |
|---|---|---|
| chess_standard | 61 | 100% |
| chess960 | 72 | 100% |
| checkers_american | 208 | 100% |
| draughts_intl | 90 | 100% |

The diagnostic confirms: the bottleneck is structural (15-event windows have
exactly 3 RB slots; preemption by phase-change SGT can drop RB count to 2).
checkers_american has the highest invalid count due to more short windows +
more frequent phase transitions from rapid material attrition.

**Length distribution of saved chains (where variation matters most):**
- chess_standard: 770 / 1,200 (64.2%) at length=25; rest spread
- chess960:       726 / 1,200 (60.5%) at length=25
- checkers_american: 423 / 1,200 (35.2%) at length=25 — much shorter mean
- draughts_intl:  777 / 1,200 (64.8%) at length=25

**Files created/modified:**
```
scripts/generate_full_chains.py (new)
chains/real/{cell}/*.jsonl (1,200 per cell — gitignored, ~36 MB total)
chains/shuffled/{cell}/*.jsonl (3,600 per cell — gitignored, ~108 MB total)
chains/generation_summary.json (committed)
chains/generation_log.txt (per-cell stdout from the run)
SESSION_LOG.md (this entry)
```

**Blockers / open questions:** none

**Next session (Session 8) planned tasks:**
- Build reference distributions per cell from real chains
- Coverage check: ≥90% non-max-backoff per SPEC §6
- Save to data/reference_{cell}.pkl

---

## Session 8 — 2026-04-25

**Tasks completed:**
- Wrote `scripts/build_reference_distributions.py`:
  - For each cell, loads 1,200 real chains from chains/real/{cell}/*.jsonl
  - Calls `ReferenceDistribution.build_from_chains(chains, source=cell)` —
    builds (state_signature → focal_action) frequency table
  - Saves `data/reference_{cell}.pkl`
  - Runs `dist.check_coverage(chains, target=0.90)` — counts how many
    chains' state signatures match at each backoff level (0=full, 1=drop
    entity, 2=drop bracket, 3=max-backoff)
- Built reference distributions for all 4 cells

**Gate status:** Gate 8 PASSED — all four cells exceed the SPEC §6 ≥0.90
non-max-backoff coverage threshold (every cell at 1.0000):

| Cell | Real chains | Unique level-0 state sigs | Non-max-backoff coverage |
|---|---|---|---|
| chess_standard | 1,200 | 102 | 1.0000 ✅ |
| chess960 | 1,200 | 105 | 1.0000 ✅ |
| checkers_american | 1,200 | 62 | 1.0000 ✅ |
| draughts_intl | 1,200 | 77 | 1.0000 ✅ |

**Diversity notes:**
- Level-0 state sigs are tuples of `(current_phase, last_move_type,
  resource_bracket, entity_label)`. The space is bounded by the T-code's
  abstract label vocabulary.
- 62–105 unique sigs across 1,200 chains means each sig is matched by
  ~12–19 chains on average — reasonable density for top-3 action lookup.
- checkers_american has the lowest sig diversity (62), consistent with
  shorter window lengths and a coarser optimization-objective vocabulary
  in checkers (no analog of chess's queen/rook/king pieces driving
  per-piece-type signatures).
- Every cell achieves 100% level-0 coverage — every chain has a sig that
  was also seen in another chain in the same cell. No backoff needed.

**Files created/modified:**
```
scripts/build_reference_distributions.py (new)
data/reference_chess_standard.pkl (gitignored — 8 KB)
data/reference_chess960.pkl (gitignored — 8 KB)
data/reference_checkers_american.pkl (gitignored — 8 KB)
data/reference_draughts_intl.pkl (gitignored — 8 KB)
data/reference_build_summary.json (committed)
SESSION_LOG.md (this entry)
```

**Blockers / open questions:** none

**Phase 1 readiness check (per CLAUDE.md "Stop at end of Session 8"):**
- Chains: 4,800 real + 14,400 shuffled across 4 cells ✅
- References: 4 distributions, all 100% level-0 coverage ✅
- T-code frozen at git tag T-code-game-v1.0-frozen ✅
- Leakage: 0 hard, 0 soft on all 19,200 rendered chains ✅
- Test suite: 42/42 passing ✅
- Pre-registration: SPEC.md immutable; all renames in CLAUDE.md/translation
  brought repo INTO compliance with SPEC §Renderer leakage vocabulary ✅

**STOPPING POINT** — author requested halt at end of Session 8. Next sessions
(per BUILD_PLAN.md):
- Session 9: dry run (~$1–2) — small batch through Anthropic Messages API to
  verify pipeline end-to-end before Phase 1
- Session 10: Phase 1 Haiku (~$60–120) — full evaluation of all chains
- Session 11: Gate 8 review — Phase 1 results decide whether Phase 2 runs
- Session 12: Phase 2 Sonnet conditional (~$200–280)
- Session 13: scoring + analysis

---

## Session 9 — 2026-04-25

**Tasks completed:**
- API key dropped by author into `.env`; verified loaded (108 chars, sk-ant-* prefix)
- Format-check (3 dry-run prompts) — clean, no leakage in previews, prompt
  template renders correctly with `phase_endgame_priority` etc.
- Wet smoke (3 Haiku calls, ~$0.001 spent) — all 3 succeeded with valid action
  labels (support_advance, advance_together, defend_zone). Surfaced two runner
  bugs (committed as fixes).
- Wrote `scripts/run_dryrun.py` orchestrator: 8 sequential batch invocations
  (4 cells × {real, shuffled}), 50 chains × 3 configs each.
- Ran full dry-run sweep: **1,200 API calls, all succeeded**, 0 errors,
  ~$0.40 spent, wall time 23.2 min.

**Bug fixes during Session 9:**
1. `src/runner.py` — blinded path was `output_dir.parent / "blinded"` →
   wrote to `results/raw/blinded/`. Fixed to `parent.parent` →
   `results/blinded/` per project layout (commit 830d912).
2. `src/runner.py` — `_CUSTOM_ID_SEP = "||"` violated Anthropic Batches
   pattern `^[a-zA-Z0-9_-]{1,64}$`; first sweep failed pre-submission with
   HTTP 400 on all 8 batches (zero spend). Changed to `"-"` (commit fab4221).
   Worst-case custom_id length: sonnet-1337-checkers_american_real_1199_shuffled_7919
   = 53 chars, under 64.

**Gate status:** Session 9 has no formal gate. Pipeline ready for Phase 1.
  - 1,200 / 1,200 calls succeeded across 4 cells × {real, shuffled}
  - Output schema correct (chain_id, cutoff_k, model, source, response,
    seed, temperature, prompt_version) in all raw files
  - Blinded mirrors landed in `results/blinded/` (400 unique chain×cutoff pairs)
  - Per-batch wall time ranged 61s (fast queue) to 362s (busier queue);
    all 8 batches completed in `processing_status=ended`

**Response distribution (1,200 calls; Haiku):**
- 42 unique responses; 13 singletons
- Top 6 responses are all from `_COORD_ACTIONS` and account for 92.5%
- Modal: maintain_formation (35%) — high concentration but not degenerate
- 51 responses (4.2%) used "switch_to_phase_X" patterns echoing the
  prompt's example template
- Real vs shuffled distribution divergence: 2nd-most-common response flips
  between conditions (advance_together for real / restrict_mobility for
  shuffled) — candidate experimental signal the scorer will quantify

**Leakage findings on responses:**
- HARD: 2 cases (0.17%) — both FALSE POSITIVES. Same chain produced verbose
  English text containing "with" ("Cannot proceed with standard adaptation").
  "with" is in our v2 `_PROGRAMMING_VOCAB` as a Python keyword. The leakage
  list was designed to scan chain CONTENT (where it has been 100% clean across
  all 19,200 chains), not model RESPONSES. Recommendation: don't gate on
  response leakage — track as diagnostic only.
- SOFT: 6 cases (0.5%) — REAL but minor. Two specific chains
  (chess960_real_0010, draughts_intl_real_0032) produced "switch_to_endgame_*"
  responses across all 3 configs. The model is decoding `phase_endgame_priority`
  and stripping the `phase_` abstraction prefix. This is the failure mode we
  discussed when we exempted `phase_X` compounds — predicted, low rate, not a
  methodology blocker.

**Files created/modified:**
```
scripts/run_dryrun.py (new, committed fab4221)
src/runner.py (custom_id separator fix, committed fab4221)
src/runner.py (blinded path fix, committed 830d912)
results/raw/dryrun/{cell}/*.json (1,200 raw response files — gitignored)
results/blinded/*.json (400 blinded mirrors — gitignored)
results/dryrun_summary.json (per-invocation stats — committed)
results/dryrun_log.txt (full stdout from the run — committed)
```

**Blockers / open questions:**
- The v2 `_PROGRAMMING_VOCAB` contains words that overlap with English
  ("with", "pass", "else", "while", "print", "class", "return"). For v3 these
  should be removed since we don't run code; they only fire on free-form
  model responses, never on chains. Track as deferred cleanup item — does NOT
  affect Phase 1 since chains are clean and we're not gating on responses.
- The "switch_to_endgame_*" pattern from Haiku suggests our prompt example
  `'e.g., "use piece_A" or "switch to phase_B"'` may be inducing it.
  Switching to a more neutral example (e.g., `'a token like piece_A or transition_B'`)
  could help post-freeze. Not blocking — log for v4 prompt design.

**Next session (Session 10) planned tasks:**
- Phase 1 full Haiku evaluation: 4,800 real + 14,400 shuffled = 19,200 chains
  × 3 EVAL_CONFIGS = 57,600 API calls
- Estimated cost: $60–120 (Haiku, batch-discounted)
- Estimated wall time: 4–24 hours (Anthropic batch queue dependent)
- Need orchestrator extension to handle the full chain set (current dryrun
  script uses `n=50` cap)
- Output: `results/raw/phase1/{cell}/*.json` (57,600 files) +
  `results/blinded/*.json` (19,200 unique chain×cutoff pairs)
