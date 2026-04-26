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
