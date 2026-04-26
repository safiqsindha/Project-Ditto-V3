# Project Ditto v3 — Architecture and Session Protocol

**Read this at the start of every session** (after SESSION_LOG.md).

Companion docs:
- `SPEC.md` — frozen pre-registration (thresholds, methodology)
- `BUILD_PLAN.md` — session-by-session roadmap and gate criteria
- `PROGRAM_OUTLOOK.md` — long-arc program direction and v4 branch tree

---

## Pre-registration discipline

`SPEC.md` is frozen. If you find yourself wanting to deviate from it, **stop and ask first**.

- Do not work around spec constraints in code
- If the spec needs amendment: create a dated supplement (e.g. `SPEC_v1.1.md`) with both-author sign-off; do not overwrite `SPEC.md` or `SPEC.pdf`
- `SPEC.pdf` is the immutable anchor — do not touch it after the pre-registration commit
- Gate failures pause execution for author review; do not auto-recover

---

## Domain and hypothesis

v3 tests whether the six-type constraint-chain abstraction generalizes to
formal-rule games **and** whether training-data exposure compresses the
real-vs-shuffled detectability gap.

Four primary cells (two game families × two exposure levels):
| Cell | Game | Exposure | Source |
|------|------|----------|--------|
| chess_standard | Standard chess | High | `Lichess/standard-chess-games` (HuggingFace) |
| chess960 | Chess960 | Low | `Lichess/chess960-chess-games` (HuggingFace) |
| checkers_american | American checkers (8×8) | Higher | OCA 2.0 + ACF archives |
| draughts_intl | International draughts (10×10) | Lower | FMJD archives |

Models: Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) — Phase 1;
        Claude Sonnet 4.6 (`claude-sonnet-4-6`) — Phase 2 (conditional)

---

## Pipeline data flow

```
data/{cell}/games.jsonl          (materialized once in Sessions 2–3)
        │
        ▼ parser_chess.py / parser_checkers.py   (Session 4)
TrajectoryLog (GameEvents)
        │
        ▼ aggregation.py                          (Session 5)
windowed GameEvent list (15–25 events)
        │
        ▼ translation.py (T-code)                 (Session 5)
list[Constraint]
        │
        ▼ filter.py                               (domain-blind)
validated list[Constraint]
        │
        ▼ observability.py                        (domain-blind)
filtered + bucketed list[Constraint]
        │
        ├──▶ renderer.py → rendered string        (with leakage check)
        │                                         (Session 5)
        └──▶ shuffler.py → 3 shuffled variants   (seeds 42, 1337, 7919)
                │
                ▼
        chains/real/{cell}/*.jsonl
        chains/shuffled/{cell}/*.jsonl
                │
                ▼ reference.py                    (Session 8)
        data/reference_{cell}.pkl
                │
                ▼ runner.py                       (Sessions 9–12)
        results/raw/{phase}/{cell}/*.json
                │
                ▼ scorer.py                       (Session 13)
        results/scored.json
```

---

## Module status

| Module | Status | Notes |
|--------|--------|-------|
| `src/filter.py` | ✅ Adapted | Length 15–25 for game domain |
| `src/shuffler.py` | ✅ Copied | Domain-blind — unchanged from v2 |
| `src/normalize.py` | ✅ Copied | Domain-blind — unchanged from v2 |
| `src/scorer.py` | ✅ Adapted | ACTIONABLE_TYPES updated (no InformationState) |
| `src/runner.py` | ✅ Adapted | SOURCES updated to game cells |
| `src/observability.py` | ✅ Adapted | Entity labels for game domain |
| `src/reference.py` | ✅ Adapted | active_pair = (current_phase, last_move_type) |
| `src/prompt_builder.py` | ✅ Adapted | PROMPT_VERSION = "v3.0-game" |
| `src/renderer.py` | ✅ Adapted | Extended leakage vocab (chess + checkers) |
| `src/translation.py` | 🔲 STUB | Dataclasses defined; translate_* raises NotImplementedError |
| `src/aggregation.py` | 🔲 STUB | Session 5 |
| `src/parser_chess.py` | 🔲 STUB | Session 4 |
| `src/parser_checkers.py` | 🔲 STUB | Session 4 |

**T-code freeze**: `src/translation.py`, `src/aggregation.py`, `src/renderer.py` freeze at
git tag `T-code-game-v1.0-frozen` after Session 6 pilot inspection passes. No modifications
after that tag without a new pre-registration.

---

## Abstract label conventions (game domain)

| Concept | Abstract label |
|---------|---------------|
| Chess/checkers pieces | `piece_A`, `piece_B`, ... `piece_P` |
| Sides | `side_1`, `side_2` |
| Game phases | `phase_opening`, `phase_middlegame`, `phase_endgame` |
| Squares (chess) | `sq_0` ... `sq_63` (a1=0, h8=63) |
| Squares (checkers American) | `sq_1` ... `sq_32` |
| Squares (draughts intl) | `sq_1` ... `sq_50` |
| Material resources | `material_white`, `material_black` |
| Tempo resources | `tempo_remaining` |
| Coordination patterns | `battery_A`, `pawn_chain_B`, `back_row_C` |
| Optimization objectives | `material_gain`, `king_safety`, `mobility` |

**Never use**: pawn, knight, bishop, rook, queen, king, castle, check, fork, pin, skewer,
jump, capture, crown, draughts, checkers, chess, algebraic notation, file letters, rank
numbers (in context), or any term in the renderer leakage vocabulary.

---

## Constraint type mappings (SPEC §Constraint type mappings)

| Type | In game chains |
|------|---------------|
| `ResourceBudget` | Material count (normalised), tempo |
| `ToolAvailability` | Legal move set availability; piece captured → UNAVAILABLE (permanent) |
| `SubGoalTransition` | Opening → middlegame → endgame; king-promotion subgoal (checkers) |
| `InformationState` | Always `complete` (perfect information) — non-actionable |
| `CoordinationDependency` | Piece coordination patterns (batteries, pawn chains, back-row defense) |
| `OptimizationCriterion` | Implicit evaluation objective inferred from move (material, safety, mobility) |

**Known asymmetry**: `InformationState` is non-actionable in games. The both-actionable
filter uses: `{ToolAvailability, SubGoalTransition, CoordinationDependency, OptimizationCriterion}`.

---

## Session handoff protocol

**At session start:**
1. Read `SESSION_LOG.md` (last entry) for prior context
2. Read this file for current architecture state
3. Check module status table above — know which stubs are pending

**During session:**
- Mark tasks complete as you go, not in batches
- If a gate criterion fails, document in SESSION_LOG.md and stop for author review
- Do not auto-proceed past gate failures
- Do not compute gap statistics across cells during evaluation runs (Sessions 10, 12)

**At session end:**
- Append new entry to `SESSION_LOG.md` (format below)
- Commit with atomic, well-described commit messages

**SESSION_LOG.md entry format:**
```
## Session N — [date]
**Tasks completed:** [list]
**Gate status:** [passed/failed/pending — which gate]
**Files created/modified:** [list]
**Blockers / open questions:** [list or "none"]
**Next session planned tasks:** [list]
```

---

## Pre-registration commit

The first commit in this repository is the pre-registration commit:
> "Pre-registration commit — thresholds and methodology frozen"

This commit includes `SPEC.md`, `SPEC.pdf`, `PROGRAM_OUTLOOK.md`, and the
initial code scaffold. The pre-registration is frozen at this commit.

---

## Co-author coordination

Co-author: Myriam (Columbia University, systems engineering).

Required review gates:
- Gate 1 (pre-registration commit): both authors sign off before evaluation begins
- Gate 8 (Phase 1 → Phase 2 decision): lead author confirms gate criteria
- Final results: co-author reviews `RESULTS.md` draft before commit

If a session output requires co-author review per BUILD_PLAN.md "Coordination protocol",
flag it in SESSION_LOG.md and stop.

---

## Budget notes

| Phase | Estimated cost |
|-------|---------------|
| Dry-run (Session 9) | ~$1–2 |
| Phase 1 Haiku (Session 10) | ~$60–120 |
| Phase 2 Sonnet (Session 12, conditional) | ~$200–280 |
| **Total if Phase 2 runs** | **~$260–400** |

All costs assume Anthropic Messages Batches API (50% cost reduction).
