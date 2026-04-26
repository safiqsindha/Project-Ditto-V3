# Stage 1: Defensive patches plan (no methodology change)

This document describes the defensive patches that will land in a single
commit BEFORE SPEC v1.1 sign-off. None of these patches change methodology;
all bring the code into a more robust state for the upcoming re-run.

**To be deleted after the patches commit lands** — this is a planning doc
for review, not a permanent record (SESSION_LOG carries the audit trail).

---

## Patch 1 — `src/scorer.py:apply_bonferroni` clamp n_tests at 1

**Why**: `apply_bonferroni(p, 0)` currently returns `min(1.0, p * 0) = 0.0`,
which would falsely report all p-values as significant. CLI restricts
divisor to {4, 8} but `score_all` accepts arbitrary int — defense in depth.

**Diff**:
```python
def apply_bonferroni(p_value: float, n_tests: int) -> float:
    n_tests = max(1, n_tests)   # NEW: clamp at 1
    return min(1.0, p_value * n_tests)
```

---

## Patch 2 — `src/scorer.py:paired_ttest` handle zero-variance inputs

**Why**: scipy returns NaN when both arms are identical (divide-by-zero).
NaN propagates into significance flags counter-intuitively. Return a
defensive zero result.

**Diff**:
```python
def paired_ttest(real_scores, shuffled_scores):
    n = len(real_scores)
    if n < 2:
        return {"error": "insufficient data (need >=2 pairs)"}
    if n != len(shuffled_scores):
        return {"error": "list length mismatch"}

    # NEW: handle zero-variance case explicitly
    if all(r == s for r, s in zip(real_scores, shuffled_scores)):
        return {
            "n_pairs": n,
            "real_mean": round(float(np.mean(real_scores)), 4),
            "shuffled_mean": round(float(np.mean(shuffled_scores)), 4),
            "gap": 0.0, "mean_diff": 0.0,
            "t_stat": 0.0, "p_value": 1.0,
            "significant_05": False,
            "test": "paired_ttest",
            "note": "identical arms; no variance",
        }

    t, p = stats.ttest_rel(real_scores, shuffled_scores)
    # ... rest unchanged
```

---

## Patch 3 — `src/scorer.py:score_layer2` defensive None on invalid cutoff

**Why**: `score_layer2` currently returns `coupled=0.0` for invalid cutoffs,
and the aggregation appends these sentinel zeros to the t-test buckets,
biasing means downward. Mirror `score_layer1`'s defensive behavior.

**Diff**:
```python
def score_layer2(model_response, chain, cutoff_k, dist):
    constraints = chain.get("constraints", [])
    # NEW: explicit invalid-cutoff guard, mirrors score_layer1
    if not constraints or cutoff_k <= 0 or cutoff_k > len(constraints):
        return {"legality": None, "optimality": None, "coupled": None,
                "error": "invalid cutoff"}
    # ... rest unchanged
```

And in `score_all` aggregation:
```python
# Layer 2 (continuous): only append when both sides valid
if real["l2_coupled"] is not None and shuf["l2_coupled"] is not None:
    bucket["real_l2"].append(real["l2_coupled"])
    bucket["shuffled_l2"].append(shuf["l2_coupled"])
```

---

## Patch 4 — `src/scorer.py:_load_chain_dict` exact-match glob

**Why**: `glob(f"{chain_id}*.jsonl")` is too permissive; works narrowly for
current naming but fragile. Use exact filename match.

**Diff**:
```python
def _load_chain_dict(chain_id, source, base_dir):
    path = base_dir / source / f"{chain_id}.jsonl"
    if not path.exists():
        return None
    try:
        with path.open() as f:
            return json.loads(f.readline().strip())
    except Exception:
        return None
```

---

## Patch 5 — `src/runner.py:run_batch` polling status check

**Why**: `while True: ... if status == "ended": break` would loop forever if
status becomes "canceled" or any other terminal non-"ended" state. Break on
any terminal status, log if unexpected.

**Diff**:
```python
TERMINAL_BATCH_STATUSES = {"ended", "canceled", "expired", "failed"}

for batch_id in batch_ids:
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        if batch.processing_status in TERMINAL_BATCH_STATUSES:
            if batch.processing_status != "ended":
                print(f"[runner] WARN: batch {batch_id} terminated as "
                      f"{batch.processing_status}")
            break
        print(f"[runner] batch {batch_id} status={batch.processing_status} — polling...")
        time.sleep(_BATCH_POLL_INTERVAL)
```

---

## Patch 6 — `src/runner.py:run_batch` defensive `meta` lookup

**Why**: `meta = chain_meta.get(custom_id, {})` then `meta["chain_id"]` would
KeyError if Anthropic returns an unrecognized custom_id (shouldn't happen,
but defensive).

**Diff**:
```python
for result in client.messages.batches.results(batch_id):
    custom_id = result.custom_id
    meta = chain_meta.get(custom_id)
    if meta is None:
        print(f"[runner] WARN: unrecognized custom_id {custom_id}; skipping")
        stats["errors"] += 1
        continue
    # ... rest unchanged
```

---

## Patch 7 — `src/runner.py:_call_api_with_backoff` content type check

**Why**: `result.message.content[0].text` assumes the first content block is
text. We don't enable tools so this is fine for current models, but safer.

**Diff**:
```python
def _extract_response_text(content_blocks) -> str:
    for block in content_blocks:
        if hasattr(block, "type") and block.type == "text":
            return block.text.strip()
        # SDK variant: dict-like access
        if isinstance(block, dict) and block.get("type") == "text":
            return block.get("text", "").strip()
    return ""

# In _call_api_with_backoff:
return _extract_response_text(response.content)

# In run_batch:
response_text = _extract_response_text(result.result.message.content)
```

---

## Patch 8 — `src/reference.py:extract_state_signature` shape-correct default

**Why**: empty/invalid input returns 1-tuple `("opening",)` regardless of
requested level. Should match the requested level shape.

**Diff**:
```python
def extract_state_signature(constraints, cutoff_k, backoff_level=0):
    if not constraints or cutoff_k <= 0:
        # Return a shape consistent with the requested level
        if backoff_level == 0:
            return ("phase_opening", "unknown", 4, "unknown")
        if backoff_level == 1:
            return ("phase_opening", "unknown", 4)
        if backoff_level == 2:
            return ("phase_opening", "unknown")
        return ("phase_opening",)
    # ... rest unchanged
```

---

## Patch 9 — `src/reference.py` default phase token format

**Why**: default `current_phase = "opening"` doesn't match data format
`"phase_opening"`. State sigs from chains-without-SGT-in-window fragment.

**Diff**: in `extract_state_signature`, change `current_phase = "opening"`
to `current_phase = "phase_opening"` (matches actual data format from chain
generation).

---

## Patch 10 — `src/reference.py:build_from_chains` safer cutoff fallback

**Why**: `cutoff_k = chain.get("cutoff_k", len(constraints) // 2)` falls
back to 0 if constraints is empty, then state_sig defaults to 1-tuple.
Inconsistent with the rest of the run.

**Diff**:
```python
for chain in chains:
    constraints = chain.get("constraints", [])
    if not constraints:
        continue
    # NEW: guard cutoff in valid range
    cutoff_k = chain.get("cutoff_k") or max(1, len(constraints) // 2)
    if cutoff_k <= 0 or cutoff_k > len(constraints):
        continue
    # ... rest unchanged
```

---

## Patch 11 — `scripts/run_phase1.py` archive previous output before re-run

**Why**: re-running into `results/raw/phase1/` overwrites file-by-file. If
re-run fails partway, we'd have a mix of old + new responses. Add an opt-in
archive step.

**Diff** (NEW: `--archive` flag):
```python
parser.add_argument("--archive", action="store_true",
    help="Move existing results/raw/phase1/ to results/raw/phase1_<timestamp>/ before run")

if args.archive and OUT_DIR.exists() and any(OUT_DIR.iterdir()):
    archive_dir = OUT_DIR.parent / f"phase1_{int(time.time())}"
    OUT_DIR.rename(archive_dir)
    print(f"[archive] previous output → {archive_dir.relative_to(PROJECT_ROOT)}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
```

---

## Patches NOT applied (rationale)

- **Bug 13 (response.content access in single API)**: same fix as Patch 7,
  consolidated.
- **Bug 19 (orphan batches if orchestrator crashes)**: too invasive to fix
  defensively without a proper batch-tracking layer; out of scope.
- **Bug 24 (lookup_with_backoff "exhausted vs found at level 3" conflation)**:
  becomes irrelevant after methodology fix populates counts at multiple
  levels (Stage 2 work). Fixing now would be wasted effort.
- **Bug 28 (run_phase1 partial-state cleanup on crash)**: too invasive, not
  triggered by re-run.
- **Bug 29 (build_reference label list)**: stays correct under Stage 2 changes
  since we keep the 4-level structure.
- **Bug 37 (defensive `else 1` branch)**: never triggered by construction;
  cosmetic cleanup deferred.

---

## Test plan

After all patches land:

1. Run existing test suite (`pytest tests/`) — must pass 42/42.
2. Verify scorer still works on dryrun output (`results/raw/dryrun/`) and
   produces same shape as before for the patched paths.
3. Smoke test the patched `run_batch` polling on a 3-call invocation
   (already validated end-to-end before; just confirm patches haven't
   regressed it).

No re-run needed at this stage; methodology unchanged.

---

## After Stage 1 lands

→ Stage 2: Submit SPEC v1.1 for both-author sign-off
→ Stage 3 (post sign-off): land Amendment 1, 2, 3 implementation patches
→ Stage 4: rebuild references, re-run Phase 1, re-score
