<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
    <img src="assets/banner-light.svg" alt="Project Ditto v3" width="100%">
  </picture>
</p>

# Project Ditto v3 — Formal Games

**Does training-data exposure compress the real-vs-shuffled detectability gap?**

v3 extends the constraint-chain abstraction to **formal-rule games** and, for the first time in the program, tests a *mechanistic* hypothesis rather than a generality one. Each game family contributes a high-exposure and a low-exposure variant — standard chess against Chess960, American checkers against international draughts. If detectability is driven by memorized game distributions rather than by structure in the chain, the low-exposure variant should show the **larger** gap.

- **A mechanism test with a built-in control** — exposure varies within family while the rules, the translation function, and the scoring stay fixed
- **Falsifiable in both directions** — pre-registered criteria specify what would refute the hypothesis, not only what would support it
- **Leakage hardened** — a 158-entry glossary is the single source of truth, checked under both word-boundary and relaxed-substring matching
- **Fully domain-blind** — the shuffler, filter, and normalizer are shared verbatim with v2 and never see the game

![License](https://img.shields.io/badge/license-MIT-22c55e?style=flat-square)
![Python](https://img.shields.io/badge/python-3.10%2B-0891b2?style=flat-square)
![Status](https://img.shields.io/badge/status-paused%20at%20Gate%208-F59E0B?style=flat-square)
![Pre-registered](https://img.shields.io/badge/pre--registered-v1.0-7C3AED?style=flat-square)

**[Pre-registration](SPEC.md)** · **[Amendments](SPEC_v1.1.md)** · **[Build plan](BUILD_PLAN.md)** · **[Session log](SESSION_LOG.md)** · **[Program outlook](PROGRAM_OUTLOOK.md)**

> **Status:** Phase 1 evaluation complete (Sessions 1–10; 57,600 Haiku calls, ~$17). Paused at **Gate 8** — the Phase 1 → Phase 2 decision — pending lead-author review. Scoring is Session 13 and has not yet run, so no gap statistic is reported here.

```bash
pip install -r requirements.txt && cp .env.example .env   # add your Anthropic API key
python scripts/run_dryrun.py
```

## The hypothesis

> **Training-data exposure compresses the real-vs-shuffled detectability gap.** Applied to trajectories from two game families, each with a high-exposure and a low-exposure variant, the abstraction will produce a stronger gap in the lower-exposure variant.

| | Criterion |
|---|---|
| **Supported if** | Chess960 clears strong-positive **and** standard chess clears at most moderate-positive, **and** the same pattern holds in the checkers family (draughts > American checkers) |
| **Refuted if** | Both variants within a family clear strong-positive — no compression despite a large exposure differential — or low-exposure variants show *smaller* gaps |

| Tier | Threshold |
|---|---|
| Moderate-positive | Layer 1 actionable gap ≥ 0.05 at Bonferroni-corrected *p* < 0.05 |
| Strong-positive | Layer 1 actionable gap ≥ 0.08 at Bonferroni-corrected *p* < 0.01 |

## Experimental cells

| Cell | Game | Exposure | Source |
|---|---|---|---|
| `chess_standard` | Standard chess | High | `Lichess/standard-chess-games` (HuggingFace) |
| `chess960` | Chess960 | Low | `Lichess/chess960-chess-games` (HuggingFace) |
| `checkers_american` | American checkers (8×8) | Higher | OCA 2.0 + ACF archives |
| `draughts_intl` | International draughts (10×10) | Lower | FMJD / Lidraughts archives |

Each cell: 2,000 materialized games → 1,200 real chains + 3,600 shuffled (seeds 42, 1337, 7919). Rating filter applied at materialization: `WhiteElo ≥ 1800 AND BlackElo ≥ 1800`.

**Models** — Phase 1: Claude Haiku 4.5 (`claude-haiku-4-5-20251001`). Phase 2 (conditional): Claude Sonnet 4.6 (`claude-sonnet-4-6`).

## Constraint mapping into the game domain

| Type | In game chains |
|---|---|
| `ResourceBudget` | Normalised material count, tempo |
| `ToolAvailability` | Legal move set; a captured piece becomes permanently UNAVAILABLE |
| `SubGoalTransition` | Phase transitions; king-promotion subgoal in checkers |
| `InformationState` | Always `complete` — these are perfect-information games |
| `CoordinationDependency` | Piece coordination patterns |
| `OptimizationCriterion` | Evaluation objective inferred from the move |

**Known asymmetry:** `InformationState` is non-actionable in perfect-information games, so the both-actionable filter uses the remaining four types. This is a real limitation of applying the abstraction here, and it is pre-registered rather than discovered after the fact.

### A leakage bug worth reading about

The original label scheme embedded game vocabulary inside label names — `material_white`, `king_safety`, `pawn_chain_B`, `battery_A`. Python's `\b` word-boundary regex treats `_` as a word character, so the leakage check **silently passed** every one of them, even though a human reader plainly sees the chess words. Session 6 replaced the labels with truly abstract forms and added a relaxed-boundary soft check alongside the hard one. [`src/leakage_glossary.py`](src/leakage_glossary.py) is now the single source of truth, and the renderer derives both vocabularies from it.

## Pipeline

```
data/{cell}/games.jsonl
    ▼ parser_chess.py / parser_checkers.py        python-chess · draughts
TrajectoryLog (GameEvents)
    ▼ aggregation.py                              phase-anchored 15–25 event windows
    ▼ translation.py                              six-type constraint chain      [FROZEN]
    ▼ filter.py                                   domain-blind validity check
    ▼ renderer.py                                 abstract English + leakage check [FROZEN]
    ├──▶ chains/real/{cell}/*.jsonl
    └──▶ shuffler.py ──▶ chains/shuffled/{cell}/*.jsonl   seeds 42, 1337, 7919
                ▼ reference.py     → data/reference_{cell}.pkl
                ▼ runner.py        → results/raw/{phase}/{cell}/*.json
                ▼ scorer.py        → results/scored.json
```

T-code is frozen at tag `T-code-game-v1.0-frozen`, covering `translation.py`, `aggregation.py`, `renderer.py`, and `leakage_glossary.py`.

## Progress

| Session | Task | Gate |
|---|---|---|
| 1 | Repo setup, v2 module reuse, stubs | Gate 1: pre-registration commit ✅ |
| 2 | Chess data acquisition (HuggingFace) | Gate 2a ✅ |
| 3 | Checkers data acquisition (OCA + Lidraughts) | Gate 2b ✅ |
| 4 | Parser + aggregation implementation | Gate 3: 100% parse success ✅ |
| 5 | T-code implementation | — |
| 6 | Pilot chains + leakage hardening | Gate 6 ✅ · T-code frozen |
| 7 | Full chain generation (19,200 chains) | 4 cells × 1,200 real + 3,600 shuffled ✅ |
| 8 | Reference distribution build | 100% level-0 coverage, all cells ✅ |
| 9 | Live API dry-run (1,200 calls, ~$0.40) | End-to-end verified ✅ |
| 10 | Phase 1 Haiku evaluation (57,600 calls, ~$17) | **Gate 8 review pending** |
| 11–13 | Phase 2 decision → scoring → analysis | Pending |

**Next step:** lead author reviews Phase 1 and decides whether to fund Phase 2 Sonnet evaluation (~$85–100).

## Repository layout

```
src/
  parser_chess.py       PGN parser (python-chess)
  parser_checkers.py    PDN parser (draughts)
  aggregation.py        phase-anchored windowing                [FROZEN]
  translation.py        game T-code, six constraint types       [FROZEN]
  renderer.py           abstract English + leakage check        [FROZEN]
  leakage_glossary.py   158-entry leakage vocabulary            [FROZEN]
  filter.py             domain-blind chain validity
  shuffler.py           domain-blind shuffler (42, 1337, 7919)
  normalize.py          action normalization
  reference.py          reference distribution builder/lookup
  prompt_builder.py     PROMPT_VERSION = v3.0-game
  runner.py             Anthropic Batches API orchestrator
  scorer.py             paired McNemar + Layer 2 scoring
  observability.py      entity labels for the game domain

scripts/     acquisition, pilot + full chain generation, dry-run, Phase 1
data/        {cell}/games.jsonl — 2,000 rated games per cell
chains/      pilot/ · real/{cell}/ · shuffled/{cell}/
results/     raw/phase1/{cell}/ · blinded/ · phase1_summary.json
tests/       test_shuffler.py · test_parsers.py
```

Key dependencies: `python-chess`, `draughts`, `datasets`, `polars`, `anthropic`, `scipy`. Python 3.10+.

## Reproducibility

- `SPEC.md` / `Spec.pdf` — frozen pre-registration. `Spec.pdf` is the immutable anchor and is never edited after the pre-registration commit.
- Amendments go in a dated supplement ([`SPEC_v1.1.md`](SPEC_v1.1.md)) with both-author sign-off — never by overwriting the original.
- Chess data snapshot: 2026-04-26 UTC. Checkers: OCA 2.0 (fierz.ch) and Lidraughts tournament exports, same date.
- Gate failures pause execution for author review. There is no auto-recovery.

## The Ditto program

| Version | Domain | Headline |
|---|---|---|
| [v1](https://github.com/safiqsindha/Project-Ditto) | Pokémon Showdown telemetry | Sonnet +0.206 · Haiku +0.066 |
| [v2](https://github.com/safiqsindha/Project-Ditto-v2) | Programming agent trajectories | Partial reproduction |
| **v3** ⟵ *you are here* | **Chess · Chess960 · checkers · draughts** | **Phase 1 complete, paused at Gate 8** |
| [v4](https://github.com/safiqsindha/Project-Ditto-V4) | Pokémon, as a methodology control | +0.131, strong-positive |
| [v4.5](https://github.com/safiqsindha/Ditto-V4.5--DeepSeek-Flash-test) | DeepSeek V4 Flash cross-model probe | Scoping stub |
| [v5](https://github.com/safiqsindha/Ditto-V5) | PUBG · NBA · CS:GO · Rocket League · poker | 4-tier hierarchy, closed |
| [v5.1](https://github.com/safiqsindha/Ditto-5.1) | 22-model cross-provider panel | Near-chance across the panel |
| [v5.2](https://github.com/safiqsindha/Ditto-5.2-diagostic) | Diagnostic kit for the v5.1 null | Pre-registered, in progress |
| [v5.4](https://github.com/safiqsindha/DITTO-V5.4-OLAT) | 24 inference levers, two DeepSeek models | 6 meaningful conditions |

## Authors

**Safiq Sindha** — lead author · **Myriam Khalil** — co-author (Columbia University, systems engineering)

Review gates requiring both authors: Gate 1 (pre-registration), Gate 8 (Phase 1 → Phase 2), and the final `RESULTS.md` draft.

## License

[MIT](LICENSE) — free to use, modify, and distribute.
