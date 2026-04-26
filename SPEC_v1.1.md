# SPEC v1.1 — Supplement to SPEC.md

**Date drafted**: 2026-04-25
**Date signed**: 2026-04-25
**Status**: SIGNED — both-author sign-off recorded; amendments in effect
**Authors**: Safiq Sindha (lead), Myriam (co-author, Columbia University)

This document is a dated supplement to `SPEC.md` (the immutable pre-registration
anchor), per CLAUDE.md "Pre-registration discipline":

> "If the spec needs amendment: create a dated supplement (e.g. `SPEC_v1.1.md`)
> with both-author sign-off; do not overwrite `SPEC.md` or `SPEC.pdf`"

`SPEC.md` is **not modified**. This file documents amendments that take effect
once both authors sign below.

---

## Trigger

Pre-launch audit of the Phase 1 scoring pipeline (Session 13 audit, 2026-04-25)
identified a vocabulary mismatch between the model prompt and the reference
distribution lookup, plus an off-by-one in the cutoff semantics. Both prevent
the scorer from registering ANY matches under the current pipeline:

- Phase 1 ran with prompt example `'use piece_A or switch to phase_B'` →
  Haiku produced 1,029 unique verb-noun action phrases (`maintain_formation`,
  `use piece_g`, `switch_to_phase_endgame`, …)
- Reference distribution stores 30 unique entity nouns (`piece_g`,
  `chain_c`, `phase_endgame`, `progress_remaining`, …)
- **Intersection: 0**. 100% of 57,600 Phase 1 responses matched=0 by
  measurement-instrument failure, not by experimental signal absence.

Empirical verification of these findings is recorded in the audit notebook in
`SESSION_LOG.md` under "Pre-rerun comprehensive audit" (Session 13).

---

## Amendment 1 — Prompt template revision (PROMPT_VERSION → v3.1-game)

### What SPEC.md currently says

`SPEC.md` §"Models and Evaluation Parameters" specifies `PROMPT_VERSION =
"v3.0-game"` and the prompt is implemented in `src/prompt_builder.py`. The
specific text of the prompt is referenced by version label only.

### Change

PROMPT_VERSION advances from `"v3.0-game"` to `"v3.1-game"`.

The user-facing prompt example string is changed from a verb-noun example
(which induced the model to emit verb-noun phrases) to an entity-only example
(which aligns with the reference distribution's stored entity vocabulary).

**Old prompt** (`v3.0-game`):
```
Given the state above, propose the next adaptation for this sequential
decision process at step {cutoff_k + 1}. Output only the action label
(e.g., "use piece_A" or "switch to phase_B"). No explanation.
```

**New prompt** (`v3.1-game`):
```
Given the state above, what is the most likely entity (resource, tool,
phase, or coordination tag) at step {cutoff_k + 1}?
Output only a single token like piece_A, chain_B, formation_C,
phase_endgame, or progress_remaining.
No verbs, no explanation.
```

### Rationale

The reference distribution is built from `extract_entity_from_constraint`,
which returns canonical entity strings (`piece_*`, `chain_*`, `phase_*`,
`resource_*`, `progress_*`, etc.). The pipeline's `score_layer1` matches the
model's response against the reference distribution's top-3 entities by
exact (case-insensitive, normalized) string equality. Verb-noun outputs like
`use piece_g` cannot match the reference's `piece_g` after normalization.

The methodology requires the model's output space and the reference's action
space to share a common vocabulary. The new prompt brings them into alignment
without changing the underlying state representation, scoring procedure, or
constraint chain content.

### What stays the same

- Chain content and rendering (frozen at `T-code-game-v1.0-frozen`)
- Reference state-signature definition (still 4 levels)
- Cutoff position (`cutoff_k = max(1, total_steps // 2)`)
- Statistical methodology (McNemar's, paired t-test, Bonferroni)
- Both-actionable filter actionable types
- The system prompt (`SYSTEM_PROMPT` unchanged)

### Cost impact

Phase 1 must be re-run with the new prompt template. Estimated ~$17 for Haiku
batch (matches actual Phase 1 run cost); estimated wall time ~30 min.

---

## Amendment 2 — Cutoff semantics clarification (focal_action target)

### What SPEC.md currently says

`SPEC.md` §"Layer 1 (primary) — paired McNemar's test with continuity correction"
and §"Pair alignment" describe how pairs are aligned but do not explicitly
specify which constraint index serves as the prediction target.

### Clarification

The model is asked to predict the constraint at **step `cutoff_k + 1`** in
the prompt (1-indexed) ⇔ **constraints[cutoff_k]** (0-indexed). This is the
first UNSHOWN constraint after the prompt prefix.

The reference distribution's `focal_action` for a chain is therefore:

```python
focal_action = extract_entity_from_constraint(constraints[cutoff_k])
```

(NOT `constraints[cutoff_k - 1]`, which is the last SHOWN constraint and is
already visible to the model in the prompt.)

The state signature continues to be built from `constraints[:cutoff_k]` —
i.e., the prefix shown to the model. The state signature describes the state
at cutoff; the focal_action is the prediction target one step ahead.

### Rationale

The pre-Phase-1 implementation set `focal_action = constraints[cutoff_k - 1]`,
which made the prediction target identical to the last shown constraint. This:
1. Coupled the reference's state signature with its target action (since both
   came from the same constraint), making the level-0 distribution tautological
   at chain-build time;
2. Misaligned with what the prompt template asks for ("step `cutoff_k + 1`");
3. Reduced the both-actionable filter retention from a SPEC-expected ~83% to
   ~24% (sampled empirically pre-supplement).

Post-clarification, the level-0 distribution becomes informative
(empirically: 35-50% of state signatures across the 4 cells have multiple
distinct focal_actions; mean 2.6-2.8 actions per signature; tautology rate
< 1.0% per cell).

### Implementation impact

- `src/reference.py:extract_state_signature` — UNCHANGED. Continues to use
  `constraints[:cutoff_k]` for state.
- `src/reference.py:build_from_chains` — recompute `focal_action` on-the-fly
  from `constraints[cutoff_k]` rather than reading the stored value (which
  was computed from `cutoff_k - 1` during chain generation in Session 7).
- `src/scorer.py:score_layer1` — change `cutoff_constraint = constraints[cutoff_k - 1]`
  to `constraints[cutoff_k]`.
- `src/scorer.py:score_layer2` — same change applied via `lookup_with_backoff`.
- The stored `focal_action` field in chain JSONLs is **deprecated but retained**
  as audit trail. New code must NOT read it; new code derives focal_action
  from `(constraints, cutoff_k)`.

### Stored chain data

The 19,200 chain JSONL files in `chains/real/` and `chains/shuffled/`
retain their stored `focal_action` field (computed via the old
`cutoff_k - 1` interpretation). These remain on disk as an audit trail.
Reference distribution rebuild uses the corrected on-the-fly computation
and does NOT depend on the stored value.

### Cost impact

Reference distribution rebuild only — no API spend. Wall time < 1 second.

---

## Amendment 3 — Scorer output structure: separate primary from variance configs

### What SPEC.md currently says

`SPEC.md` §"Models and Evaluation Parameters" (lines 167-178):

> | Primary config | Temperature 0.0, seed 42 |
> | Variance study | T=0.5, seeds 1337 and 7919 |
>
> The three-config variance study (matching v1 and v2) is included to
> characterize per-cell stability. The primary config result is the
> hypothesis test; variance configs are reported alongside as variance
> characterization, not as additional cells in the Bonferroni family.

`SPEC.md` §"Phase 1 → Phase 2 decision" (lines 124-129):

> 1. Any Haiku cell clears moderate-positive at Bonferroni-corrected p < 0.05
>    under the Haiku-only divisor of 4 (gap ≥ 0.05).

### Clarification (no methodology change — bringing scorer into SPEC compliance)

The scorer output structure separates results into two top-level keys:

```python
{
  "primary_cells": {
    # 4 entries: one per (cell × T=0.0/seed=42).
    # Bonferroni-corrected at divisor=4 for Phase 1; divisor=8 for Phase 1 + Phase 2.
    "haiku::chess_standard": { ... },
    "haiku::chess960": { ... },
    "haiku::checkers_american": { ... },
    "haiku::draughts_intl": { ... },
  },
  "variance_study": {
    # 8 entries (Phase 1 only): one per (cell × variance config).
    # Reported descriptively. NO Bonferroni correction.
    "haiku::chess_standard::T0.5_seed1337": { ... },
    ...
  },
  "n_results": int,
  "bonferroni_divisor_primary": 4,
}
```

Outcome tier classification per `SPEC.md` §"Per-cell thresholds" applies only
to `primary_cells`. Variance study cells include the same per-cell statistics
(gap, raw p, n_pairs, both-actionable retention) but no significance flag.

### Rationale

The pre-supplement scorer treated all 12 (cell × config) results identically,
applying Bonferroni divisor=4 to all of them — under-correcting variance
results AND emitting a `significant_bonferroni: True` flag for variance
configs that should not carry one per SPEC §477 ("descriptive only; not in
primary Bonferroni family").

This amendment is a clarification: the SPEC already specified this separation;
the scorer was non-compliant.

### Cost impact

Scorer output schema change only — no API spend, no chain rebuild.

---

## Amendments NOT made (considered and rejected)

The audit also surfaced these candidate methodology changes which we considered
and **decided NOT to amend**:

### Considered: drop `entity_label` from the level-0 state signature

The level-0 state signature is `(phase, type, bracket, entity_label)`. The
audit hypothesized that this would remain tautological even after the cutoff
fix.

**Rejected**: empirical smoke test (across all 4 cells, 4,800 real chains)
showed tautology rate < 1.0% per cell after Amendment 2 alone. Mean actions
per signature: 2.6-2.8. The 4-level signature structure documented in the
original SPEC remains informative and is preserved.

### Considered: pass `seed` parameter to the Anthropic Messages API

The runner's `_call_api_with_backoff` and `run_batch` accept a `seed`
parameter but do not pass it to `client.messages.create()`. This means
the `EVAL_CONFIGS` seed values (42, 1337, 7919) function as labels only;
the API's randomness at T=0.5 is uncontrolled across calls.

**Rejected**: The Anthropic Messages API does not currently expose a top-level
`seed` parameter (as of the v3 design epoch). The "variance study" interpretation
is preserved as in v2 — different random samples at T=0.5, not deterministic
seeded variance. SPEC §379-382 ("3× replication is by design ... increases
McNemar test power without inflating real_rate") is consistent with both
interpretations. We document this in Amendment notes and proceed.

---

## Defensive cleanup (out of scope; no SPEC change)

The audit also surfaced ~15 minor defensive issues (off-by-one in error
defaults, NaN propagation in paired t-test on identical inputs, glob pattern
fragility, etc.). These are implementation hardening only — no methodology
impact, no SPEC supplement needed. They will be addressed in a separate
"defensive patches" commit before re-run, with no methodology implications.

A complete list is in `SESSION_LOG.md` under "Pre-rerun comprehensive audit".

---

## Sign-off

This amendment takes effect once both authors sign:

- [x] **Safiq Sindha** (lead author) — date: 2026-04-25
- [x] **Myriam** (co-author, Columbia University) — date: 2026-04-25
      (joint approval communicated to lead author per session record)

Once signed:
1. The amendment becomes part of the pre-registration record alongside `SPEC.md`.
2. Implementation patches in `src/prompt_builder.py`, `src/reference.py`,
   `src/scorer.py` are committed under the message "SPEC v1.1: implement
   Amendments 1–3".
3. Reference distributions are rebuilt (`scripts/build_reference_distributions.py`).
4. Phase 1 is re-run (`scripts/run_phase1.py`) under PROMPT_VERSION="v3.1-game".
5. Re-scoring with the patched scorer produces the formal Layer 1 / Layer 2
   results.
6. Per `BUILD_PLAN.md` "Coordination protocol", Phase 2 (Sonnet) decision is
   based on the re-scored Phase 1 results; not on pre-supplement output.

---

## Change log

| Version | Date | Authors | Summary |
|---|---|---|---|
| v1.0 (SPEC.md) | 2026-04-25 | Safiq, Myriam | Original pre-registration |
| v1.1 (this file) | 2026-04-25 | Safiq, Myriam | Prompt template + cutoff clarification + scorer output structure |
