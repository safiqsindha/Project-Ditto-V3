# Project Ditto — Program Outlook

**Status:** Living document. Revised between experiment versions as
evidence accumulates. NOT part of the immutable v3 pre-registration —
SPEC.md is the immutable artifact.

This document records the longer-arc reasoning behind v3's design and
pre-specifies what each v3 outcome implies for v4 direction. It serves
two purposes:

1. **Defensibility**: pre-registering "what each outcome means for the
   program" prevents post-hoc rationalization of refuted hypotheses.
2. **Continuity**: maintains coherent program direction across
   experiment versions, preventing v3 → v4 drift driven by short-term
   reactions to results.

---

## The program in one paragraph

Project Ditto tests whether a six-type constraint-chain abstraction
captures generalizable structure in sequential decision-making, and
whether that structure is detectable in language models via real-vs-
shuffled comparison. v1 (Pokémon) established the methodology and
showed strong detectability on low-exposure domain. v2 (programming)
tested generality and partially replicated, with Haiku-TB clearing the
moderate-positive threshold under corrected paired analysis. The
observed gap-compression pattern in v2 (Sonnet < Haiku, SWE < TB)
suggested training exposure as a candidate mechanism. v3 (formal
games) directly tests the exposure hypothesis with within-family
exposure controls. The original cross-domain transfer question — using
constraint chains as training data to improve programming capability —
remains future work pending detection-tool credibility.

---

## What v3 establishes regardless of hypothesis outcome

Independent of whether the training-exposure hypothesis is supported or
refuted, v3 advances the program in three ways:

1. **Generality across a third domain family**. v1 + v2 + v3 together
   span Pokémon battles, programming agents, and formal-rule games —
   three structurally distinct domains. If v3's primary cells clear
   thresholds in any pattern, the cross-domain generality claim
   strengthens substantially compared to v2 alone.

2. **Methodological maturity**. v3 carries forward all corrections from
   v1 and v2: paired tests, both-actionable filter, Bonferroni
   correction, pre-registered adaptive design. The methodology is now
   battle-tested across three independent applications.

3. **Constraint on confound space**. Whichever direction v3 lands,
   one specific confound (training exposure) is either confirmed as a
   gap-compression mechanism or ruled out. Either result narrows the
   space of plausible explanations for cross-cell gap variation.

These are guaranteed-value outcomes. The hypothesis test is *additional*
upside, not the only value.

---

## v4 Direction Tree (pre-specified)

The branch taken in v4 depends on v3's outcome category. These branches
are pre-specified to prevent post-hoc rationalization but are not
binding — the authors retain the right to deviate based on new
information not anticipated here.

### Branch A: v3 Hypothesis Supported

(Chess gap < Chess960 gap AND checkers gap < draughts gap, both
predicted patterns observed.)

The methodology becomes a measurement tool, not just a detection tool.

**v4 candidate directions:**

- **A1: Triangulate the exposure measurement.** Add a third game
  family with a known exposure differential (e.g., Go and a less-trained
  Go variant; or two card games with different corpus sizes). If the
  pattern holds across three independent families, the measurement-tool
  claim is strongly supported.

- **A2: Calibrate the measurement against known exposure.** Use
  publicly available training-corpus statistics (e.g., GitHub repo
  counts for programming languages, FIDE database sizes for chess
  variants) to test whether gap magnitude correlates with corpus size
  in a graded fashion, not just binary high-vs-low.

- **A3: Test on a frontier model.** If exposure compresses the gap on
  Haiku and Sonnet, does it compress further on Opus or whatever
  successor model is available at v4 time? This tests whether the
  effect is model-size-driven.

- **A4: Cross-model validation.** Replicate on a non-Anthropic model
  family (e.g., GPT-4 family or open-weight model) to test whether the
  exposure-compression pattern is Claude-specific or general to
  transformer-based LLMs.

A1 is the highest-priority direction under this branch. A4 is the
highest-impact but breaks v1/v2/v3 model-comparability and would
require careful methodology adaptation.

### Branch B: v3 Hypothesis Refuted (both low-exposure variants clear strong-positive)

The exposure mechanism is ruled out as the gap-compression cause.
Detection-tool framing is preserved; measurement-tool framing is not
supported.

**v4 candidate directions:**

- **B1: Investigate alternative gap-compression mechanisms.** Specific
  candidates pre-specified:
  - Response-distribution entropy at the cutoff position (compressed
    distributions → smaller gaps regardless of structure)
  - Surface-pattern saliency (models latching on to surface tokens
    that survive shuffling)
  - Calibration differences between Haiku and Sonnet (if Sonnet is
    better-calibrated, its gap could compress for that reason alone)
  - Prompt-format sensitivity

- **B2: Publish v1+v2+v3 detection paper as planned.** With the
  exposure confound ruled out, the generality claim is cleaner. The
  paper becomes "the abstraction generalizes across three domain
  families; one specific confound (exposure) is ruled out as
  explanation; further mechanism investigation is future work."

- **B3: Pivot to the original transfer question.** With the detection
  methodology validated across three domains, the transfer experiment
  (use v1+v3 chains as training data, fine-tune Qwen 2.5 7B with
  LoRA, evaluate on programming benchmarks) becomes the next step.
  Cost $1-8k, time 4-8 weeks, requires new skills (LoRA,
  open-weight workflow). This is the "Option B" from the v3 planning
  framing.

B2 is the lowest-risk path. B3 is the highest-upside path but requires
skill expansion outside the lead author's current expertise; would
likely need either a collaborator or a deliberate skill-acquisition
phase.

### Branch C: v3 Partially Supported

(Pattern holds in one family, not the other, OR direction consistent
but neither low-exposure cell reaches strong-positive.)

The exposure hypothesis has some support but is confounded. The
within-family contrast was supposed to control for structural
differences, but if the two families behave differently, structural
differences are doing real work.

**v4 candidate directions:**

- **C1: Diagnose the asymmetry.** If chess showed compression but
  checkers did not (or vice versa), v4 investigates what differs
  between the two families that explains the divergence. Possible:
  game length distribution, branching factor, tactical density,
  endgame characteristics.

- **C2: Add within-family controls per family.** Run additional
  variants per family (e.g., Crazyhouse and atomic chess for chess
  family; Russian draughts and Brazilian draughts for checkers
  family) to disambiguate structural vs. exposure effects.

- **C3: Move to a third family with cleaner controls.** If chess and
  checkers are too different to be controlled by their respective
  variants, find a domain where exposure differential is more cleanly
  isolated.

C1 is the pre-specified default direction.

### Branch D: v3 Inconclusive (chain construction failure or underpowered)

(Three or more cells null; or per-cell power post-hoc < 70%.)

This branch suggests methodology failure rather than informative
absence of effect.

**v4 candidate directions:**

- **D1: Pilot expansion**. The pilot validation step in v3 should have
  caught chain construction failures, but if it didn't, v4 begins with
  an expanded pilot phase before any full evaluation runs.

- **D2: Domain reconsideration**. If formal-game chains genuinely don't
  support the abstraction, the program needs to clarify which kinds of
  sequential decision data the abstraction does and doesn't capture.
  This is itself a publishable methodology result.

- **D3: Sample size increase**. If post-hoc power was the issue, v4
  reruns with 2-3× sample size on selected cells. Budget implications
  significant but bounded.

D2 is the most informative direction even though it represents a
program slowdown.

---

## The Original Transfer Question (Option B from v3 planning framing)

The original goal of Project Ditto was a cross-domain transfer
experiment: take Pokémon-derived constraint chains, use them as
training data, and test whether the resulting model improves on
programming benchmarks. v1, v2, and v3 are detection-methodology
prerequisites for this experiment, not the experiment itself.

**Pre-conditions for pursuing the transfer experiment:**

1. Detection methodology is published and reviewed (post-v3 paper)
2. At least one v3 outcome supports continuing in the program (any
   branch except complete null)
3. Skill acquisition phase complete (LoRA fine-tuning, open-weight
   workflow) OR collaborator with relevant expertise engaged
4. Budget secured ($1-8k for fine-tuning + evaluation)

**Decision point**: After v3 results, the authors choose between:
- Continuing detection trajectory (v4 in the branches above) — lower
  risk, lower upside
- Pivoting to transfer experiment — higher risk, higher upside,
  requires new skills
- Splitting effort: detection paper first, then transfer experiment —
  current default plan

---

## Things explicitly out of scope across the program

The following are out of scope and will not enter v3 or any
foreseeable next-version planning:

- Adding constraint types beyond the original six
- Chains-on-chains layered abstraction experiments
- Domain expansion beyond what's been already specified
- Production applications, capability claims, or
  recommendation-system framing
- Real-time evaluation harnesses or live-game integrations

If any of these become tempting after v3 results, they go through a
deliberate scope-expansion review with both authors, not a quiet
inclusion in v4 planning.

---

*Drafted April 25, 2026. Will be revised after v3 results, before v4 spec
freeze.*
