"""
Evaluation runner for the Ditto v3 constraint-chain study (game domain).

Drives model evaluations against chain files, saves raw and blinded results,
and handles rate-limit errors with exponential backoff.

Two execution modes:
  - Synchronous (default / dry-run): client.messages.create, one call at a time.
  - Batch (--batch): Anthropic Messages Batches API, 50% cost reduction (SPEC §7).
    Submits all chain × model × seed requests as one batch, polls until done,
    then writes results identical to the synchronous mode.

Sources (v3 game cells):
  chess_standard, chess960, checkers_american, draughts_intl

Adapted from v2 runner.py: sources updated; model IDs unchanged.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from src.prompt_builder import PROMPT_VERSION, SYSTEM_PROMPT, build_prompt, cutoff_rendered

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODELS: dict[str, str] = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
}

SOURCES: list[str] = [
    "chess_standard",
    "chess960",
    "checkers_american",
    "draughts_intl",
]

# Full evaluation matrix (SPEC §Models and Evaluation Parameters)
# Primary:        T=0.0, seed 42
# Variance study: T=0.5, seeds 1337 and 7919
EVAL_CONFIGS: list[dict] = [
    {"temperature": 0.0, "seed": 42},
    {"temperature": 0.5, "seed": 1337},
    {"temperature": 0.5, "seed": 7919},
]

_BACKOFF_DELAYS: list[float] = [2.0, 4.0, 8.0, 16.0]

_CUSTOM_ID_SEP = "||"

_BATCH_POLL_INTERVAL = 60

_MAX_BATCH_SIZE = 10_000


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_chain(chain_path: Path) -> dict:
    with chain_path.open("r", encoding="utf-8") as fh:
        first_line = fh.readline().strip()
    return json.loads(first_line)


def _count_steps(rendered: str) -> int:
    import re
    return len(re.findall(r"Step \d+", rendered))


def _build_user_message(chain: dict) -> tuple[str, int]:
    """Return (user_message, cutoff_k) for a chain dict."""
    rendered: str = chain["rendered"]
    total_steps = _count_steps(rendered)
    cutoff_k = max(1, total_steps // 2)
    truncated = cutoff_rendered(rendered, cutoff_k)
    return build_prompt(truncated, cutoff_k), cutoff_k


def _make_custom_id(model_name: str, seed: int, chain_id: str) -> str:
    return f"{model_name}{_CUSTOM_ID_SEP}{seed}{_CUSTOM_ID_SEP}{chain_id}"


def _parse_custom_id(custom_id: str) -> tuple[str, int, str]:
    """Return (model_name, seed, chain_id)."""
    parts = custom_id.split(_CUSTOM_ID_SEP, 2)
    return parts[0], int(parts[1]), parts[2]


def _save_results(
    chain_id: str,
    model_name: str,
    seed: int,
    source: str,
    cutoff_k: int,
    temperature: float,
    response_text: str,
    output_dir: Path,
) -> None:
    """Write raw and blinded result files."""
    result = {
        "chain_id": chain_id,
        "model": model_name,
        "seed": seed,
        "source": source,
        "cutoff_k": cutoff_k,
        "response": response_text,
        "prompt_version": PROMPT_VERSION,
        "temperature": temperature,
    }

    source_dir = Path(output_dir) / source
    source_dir.mkdir(parents=True, exist_ok=True)
    raw_path = source_dir / f"{model_name}_{seed}_{chain_id}_T{temperature}.json"
    with raw_path.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    # output_dir is `results/raw/{phase}` → blinded is `results/blinded/` (sibling of raw/)
    blinded_dir = Path(output_dir).parent.parent / "blinded"
    blinded_dir.mkdir(parents=True, exist_ok=True)
    blinded = {
        "chain_id": chain_id,
        "cutoff_k": cutoff_k,
        "response": response_text,
        "prompt_version": PROMPT_VERSION,
    }
    blinded_path = blinded_dir / f"{chain_id}_{cutoff_k}.json"
    with blinded_path.open("w", encoding="utf-8") as fh:
        json.dump(blinded, fh, indent=2)


def _call_api_with_backoff(
    client: anthropic.Anthropic,
    model_id: str,
    user_message: str,
    temperature: float = 0.0,
    seed: int = 42,
) -> str:
    """Call the Messages API with exponential backoff on rate-limit / 5xx errors."""
    last_exc: Exception | None = None

    for attempt, delay in enumerate([None] + _BACKOFF_DELAYS):
        if delay is not None:
            time.sleep(delay)
        try:
            response = client.messages.create(
                model=model_id,
                max_tokens=50,
                temperature=temperature,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            return response.content[0].text.strip()
        except anthropic.RateLimitError as e:
            last_exc = e
            print(f"[runner] rate limit (attempt {attempt + 1}): {e}")
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                last_exc = e
                print(f"[runner] server error {e.status_code} (attempt {attempt + 1}): {e}")
            else:
                raise
        except Exception as e:
            raise

    raise RuntimeError(f"API call failed after all retries: {last_exc}") from last_exc


# ---------------------------------------------------------------------------
# Synchronous runner
# ---------------------------------------------------------------------------

def run_sync(
    chains_dir: Path,
    source: str,
    model_name: str,
    output_dir: Path,
    configs: list[dict] | None = None,
    n: int | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Run synchronous evaluation for one source × model across all eval configs.

    Parameters
    ----------
    chains_dir : directory containing real chain JSONL files for this source
    source     : one of SOURCES
    model_name : "haiku" or "sonnet"
    output_dir : results/raw/phase1 or results/raw/phase2
    configs    : eval configs to run (default: EVAL_CONFIGS)
    n          : limit to first n chains (dry-run convenience)
    dry_run    : if True, only print prompts without calling the API
    """
    if source not in SOURCES:
        raise ValueError(f"Unknown source: {source!r}. Must be one of {SOURCES}")
    if model_name not in MODELS:
        raise ValueError(f"Unknown model: {model_name!r}. Must be one of {list(MODELS)}")

    configs = configs or EVAL_CONFIGS
    model_id = MODELS[model_name]

    load_dotenv()
    client = anthropic.Anthropic()

    chain_files = sorted(chains_dir.glob("*.jsonl"))
    if n is not None:
        chain_files = chain_files[:n]

    stats = {"evaluated": 0, "skipped": 0, "errors": 0}

    for chain_path in chain_files:
        try:
            chain = _load_chain(chain_path)
        except Exception as e:
            print(f"[runner] failed to load {chain_path}: {e}")
            stats["skipped"] += 1
            continue

        chain_id = chain.get("chain_id", chain_path.stem)
        user_message, cutoff_k = _build_user_message(chain)

        for cfg in configs:
            temperature = cfg["temperature"]
            seed = cfg["seed"]

            if dry_run:
                print(f"[dry-run] {model_name}/{source}/{chain_id} T={temperature} seed={seed}")
                print(f"  prompt_preview: {user_message[:120]}...")
                stats["evaluated"] += 1
                continue

            try:
                response_text = _call_api_with_backoff(
                    client, model_id, user_message, temperature=temperature, seed=seed
                )
                _save_results(
                    chain_id, model_name, seed, source,
                    cutoff_k, temperature, response_text, output_dir
                )
                stats["evaluated"] += 1
            except Exception as e:
                print(f"[runner] error on {chain_id} T={temperature} seed={seed}: {e}")
                stats["errors"] += 1

    return stats


# ---------------------------------------------------------------------------
# Batch runner (Anthropic Messages Batches API)
# ---------------------------------------------------------------------------

def run_batch(
    chains_dir: Path,
    source: str,
    model_name: str,
    output_dir: Path,
    configs: list[dict] | None = None,
    n: int | None = None,
) -> dict:
    """
    Submit one Anthropic Messages Batch covering all chains × configs for
    one source × model, then poll until complete and save results.
    """
    if source not in SOURCES:
        raise ValueError(f"Unknown source: {source!r}")
    if model_name not in MODELS:
        raise ValueError(f"Unknown model: {model_name!r}")

    configs = configs or EVAL_CONFIGS
    model_id = MODELS[model_name]

    load_dotenv()
    client = anthropic.Anthropic()

    chain_files = sorted(chains_dir.glob("*.jsonl"))
    if n is not None:
        chain_files = chain_files[:n]

    requests = []
    chain_meta: dict[str, dict] = {}

    for chain_path in chain_files:
        try:
            chain = _load_chain(chain_path)
        except Exception:
            continue

        chain_id = chain.get("chain_id", chain_path.stem)
        user_message, cutoff_k = _build_user_message(chain)

        for cfg in configs:
            temperature = cfg["temperature"]
            seed = cfg["seed"]
            custom_id = _make_custom_id(model_name, seed, chain_id)
            chain_meta[custom_id] = {
                "chain_id": chain_id,
                "cutoff_k": cutoff_k,
                "source": source,
                "temperature": temperature,
                "seed": seed,
            }
            requests.append({
                "custom_id": custom_id,
                "params": {
                    "model": model_id,
                    "max_tokens": 50,
                    "temperature": temperature,
                    "system": SYSTEM_PROMPT,
                    "messages": [{"role": "user", "content": user_message}],
                },
            })

    if not requests:
        return {"submitted": 0, "completed": 0, "errors": 0}

    # Submit batch (split if over API limit)
    batch_ids = []
    for i in range(0, len(requests), _MAX_BATCH_SIZE):
        chunk = requests[i:i + _MAX_BATCH_SIZE]
        batch = client.messages.batches.create(requests=chunk)
        batch_ids.append(batch.id)
        print(f"[runner] submitted batch {batch.id} ({len(chunk)} requests)")

    # Poll until all batches complete
    for batch_id in batch_ids:
        while True:
            batch = client.messages.batches.retrieve(batch_id)
            if batch.processing_status == "ended":
                break
            print(f"[runner] batch {batch_id} status={batch.processing_status} — polling...")
            time.sleep(_BATCH_POLL_INTERVAL)

    # Collect results
    stats = {"submitted": len(requests), "completed": 0, "errors": 0}
    for batch_id in batch_ids:
        for result in client.messages.batches.results(batch_id):
            custom_id = result.custom_id
            meta = chain_meta.get(custom_id, {})
            if result.result.type == "succeeded":
                response_text = result.result.message.content[0].text.strip()
                _save_results(
                    meta["chain_id"], model_name, meta["seed"], source,
                    meta["cutoff_k"], meta["temperature"], response_text, output_dir
                )
                stats["completed"] += 1
            else:
                print(f"[runner] batch result error for {custom_id}: {result.result}")
                stats["errors"] += 1

    return stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(prog="src.runner")
    parser.add_argument("--model", choices=list(MODELS), required=True)
    parser.add_argument("--source", choices=SOURCES, required=True)
    parser.add_argument("--chains", type=Path, required=True,
                        help="Directory of chain JSONL files for this source")
    parser.add_argument("--out", type=Path, default=Path("results/raw/phase1"))
    parser.add_argument("--seed", type=int, default=None,
                        help="Run only this seed (default: all three configs)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch", action="store_true",
                        help="Use Anthropic Messages Batches API (50%% cost reduction)")
    parser.add_argument("-n", type=int, default=None,
                        help="Limit to first n chains (dry-run / test)")
    args = parser.parse_args()

    selected_configs = EVAL_CONFIGS
    if args.seed is not None:
        selected_configs = [c for c in EVAL_CONFIGS if c["seed"] == args.seed]
        if not selected_configs:
            parser.error(f"Seed {args.seed} not in EVAL_CONFIGS")

    if args.batch and not args.dry_run:
        result = run_batch(
            args.chains, args.source, args.model, args.out,
            configs=selected_configs, n=args.n,
        )
    else:
        result = run_sync(
            args.chains, args.source, args.model, args.out,
            configs=selected_configs, n=args.n, dry_run=args.dry_run,
        )

    print(f"\n[runner] done: {result}")
