# Project Ditto v3 — Formal Games

**Status:** Phase 1 evaluation complete (Sessions 1–10). Paused at Gate 8 (Phase 1 → Phase 2 decision). See [SESSION_LOG.md](SESSION_LOG.md) for current state.

Pre-registration: [SPEC.md](SPEC.md) / [Spec.pdf](Spec.pdf) (immutable after freeze)

Prior work: [Project Ditto v1](https://github.com/safiqsindha/Project-Ditto) (Pokémon) · [Project Ditto v2](https://github.com/safiqsindha/Project-Ditto-v2) (programming)

---

## What this is

Project Ditto tests whether a **six-type constraint-chain abstraction** captures generalizable structure in sequential decision-making, and whether that structure is detectable by language models via real-vs-shuffled comparison.

v3 extends the methodology to **formal-rule games** (chess and checkers) and directly tests a mechanistic hypothesis:

> **Training-data exposure compresses the real-vs-shuffled detectability gap.** When applied to game-playing trajectories from two game families, each with a high-exposure and a low-exposure variant, the abstraction will produce a stronger detectability gap in the lower-exposure variant.

### Experimental cells

| Cell | Game | Exposure | Source |
|------|------|----------|--------|
| `chess_standard` | Standard chess | High | `Lichess/standard-chess-games` (HuggingFace) |
| `chess960` | Chess960 | Low | `Lichess/chess960-chess-games` (HuggingFace) |
| `checkers_american` | American checkers (8×8) | Higher | OCA 2.0 + ACF archives |
| `draughts_intl` | International draughts (10×10) | Lower | FMJD archives |

### Models

- **Phase 1:** Claude Haiku 4.5 (`claude-haiku-4-5-20251001`)
- **Phase 2 (conditional):** Claude Sonnet 4.6 (`claude-sonnet-4-6`)

---

## Hypothesis

**Supported** if: Chess960 clears strong-positive AND standard chess clears at most moderate-positive, AND the same pattern holds in the checkers family (draughts > American checkers).

**Refuted** if: Both variants within a family clear strong-positive (no compression despite large exposure differential), or low-exposure variants show *smaller* gaps.

Pre-registered success thresholds:

| Tier | Criterion |
|------|-----------|
| Moderate-positive | Layer 1 actionable gap ≥ 0.05 at Bonferroni-corrected p < 0.05 |
| Strong-positive | Layer 1 actionable gap ≥ 0.08 at Bonferroni-corrected p < 0.01 |

---

## Pipeline

```
data/{cell}/games.jsonl
    │
    ▼ parser_chess.py / parser_checkers.py
TrajectoryLog (GameEvents)
    │
    ▼ aggregation.py          (15–25 event windows)
    │
    ▼ translation.py          (six-type constraint chain)
    │
    ▼ filter.py               (domain-blind validity check)
    │
    ▼ renderer.py             (abstract English rendering + leakage check)
    │
    ├──▶ chains/real/{cell}/*.jsonl
    └──▶ shuffler.py ──▶ chains/shuffled/{cell}/*.jsonl (seeds 42, 1337, 7919)
                │
                ▼ reference.py
        data/reference_{cell}.pkl
                │
                ▼ runner.py (Anthropic Messages Batches API)
        results/raw/{phase}/{cell}/*.json
                │
                ▼ scorer.py
        results/scored.json
```

The six constraint types used in every chain:

| Type | Game domain mapping |
|------|---------------------|
| `ResourceBudget` | Normalised material count, tempo |
| `ToolAvailability` | Legal move set; captures → UNAVAILABLE |
| `SubGoalTransition` | Phase transitions (opening → middlegame → endgame); promotion |
| `InformationState` | Always `complete` (perfect-information games) |
| `CoordinationDependency` | Piece coordination patterns |
| `OptimizationCriterion` | Evaluation objective inferred from move |

`InformationState` is non-actionable in formal games. The both-actionable filter uses the remaining four types (`ToolAvailability`, `SubGoalTransition`, `CoordinationDependency`, `OptimizationCriterion`).

---

## Repository layout

```
src/
  parser_chess.py       PGN parser (python-chess)
  parser_checkers.py    PDN parser (draughts library)
  aggregation.py        Phase-anchored windowing (15–25 events)
  translation.py        Game T-code — six constraint types    [FROZEN]
  filter.py             Domain-blind chain validity
  renderer.py           Abstract English rendering + leakage check [FROZEN]
  leakage_glossary.py   158-entry leakage vocabulary (single source of truth)
  shuffler.py           Domain-blind shuffler (seeds 42, 1337, 7919)
  normalize.py          Action normalization
  reference.py          Reference distribution builder/lookup
  prompt_builder.py     Prompt assembly (PROMPT_VERSION=v3.0-game)
  runner.py             Anthropic Batches API orchestrator
  scorer.py             Paired McNemar's test + Layer 2 scoring
  observability.py      Entity labels for game domain

scripts/
  acquire_chess.py                Chess data streaming + materialization
  acquire_checkers.py             Checkers PDN download + materialization
  download_lidraughts_tournaments.py
  download_lidraughts_users.py
  generate_pilot_chains.py        50-chain pilot per cell
  generate_full_chains.py         Full 1,200-chain generation
  build_reference_distributions.py
  run_dryrun.py                   50-chain live API smoke test
  run_phase1.py                   Phase 1 Haiku full evaluation

data/
  chess_standard/games.jsonl      2,000 rated games (WhiteElo/BlackElo ≥ 1800)
  chess960/games.jsonl            2,000 rated games (FEN column included)
  checkers_american/games.jsonl   2,000 OCA 2.0 games
  draughts_intl/games.jsonl       2,000 Lidraughts tournament games
  reference_{cell}.pkl            Reference distributions (gitignored)

chains/
  pilot/{cell}/                   50-chain pilot JSONL + stats
  real/{cell}/*.jsonl             1,200 real chains per cell (gitignored)
  shuffled/{cell}/*.jsonl         3,600 shuffled chains per cell (gitignored)

results/
  raw/phase1/{cell}/*.json        57,600 Haiku responses (gitignored)
  blinded/*.json                  Blinded mirrors (gitignored)
  phase1_summary.json
  dryrun_summary.json

tests/
  test_shuffler.py
  test_parsers.py
```

---

## Current status

| Session | Task | Gate |
|---------|------|------|
| 1 | Repo setup, v2 module reuse, stubs | Gate 1: pre-registration commit ✅ |
| 2 | Chess data acquisition (HuggingFace) | Gate 2a ✅ |
| 3 | Checkers data acquisition (OCA + Lidraughts) | Gate 2b ✅ |
| 4 | Parser + aggregation implementation | Gate 3: 100% parse success ✅ |
| 5 | T-code implementation (`translation.py`) | — |
| 6 | Pilot chain generation + leakage hardening | Gate 6 ✅ · T-code frozen at `T-code-game-v1.0-frozen` |
| 7 | Full chain generation (19,200 chains) | All 4 cells × 1,200 real + 3,600 shuffled ✅ |
| 8 | Reference distribution build | 100% level-0 coverage across all cells ✅ |
| 9 | Live API dry-run (1,200 calls, ~$0.40) | Pipeline end-to-end verified ✅ |
| 10 | Phase 1 Haiku full evaluation (57,600 calls, ~$17) | **STOP: Gate 8 author review pending** |
| 11–13 | Phase 2 decision → scoring → analysis | Pending |

**Next step:** Lead author reviews Phase 1 results and decides whether to proceed with Phase 2 Sonnet evaluation (estimated ~$85–100).

---

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Add your Anthropic API key to .env
```

Key dependencies: `python-chess`, `draughts`, `datasets`, `polars`, `anthropic`, `scipy`.

Python 3.10+ recommended.

---

## Pre-registration and reproducibility

- `SPEC.md` / `Spec.pdf` — frozen pre-registration (thresholds, methodology, adaptive design)
- T-code frozen at git tag `T-code-game-v1.0-frozen`
- Chess data snapshot: 2026-04-26 UTC (`Lichess/standard-chess-games` and `Lichess/chess960-chess-games` on HuggingFace)
- Checkers data: OCA 2.0 (fierz.ch), Lidraughts tournament exports (2026-04-26)
- Rating filter applied at materialization time: `WhiteElo ≥ 1800 AND BlackElo ≥ 1800`

---

## Authors

- **Safiq Sindha** — lead (Microsoft Azure Hardware PM, independent research)
- **Myriam** — co-author (Columbia University, systems engineering; Boeing FT)

*Pre-registration v1.0 — April 25, 2026.*
