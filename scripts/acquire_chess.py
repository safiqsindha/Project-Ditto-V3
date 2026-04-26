"""
Session 2: Stream and materialize chess data from HuggingFace.

Streams Lichess/standard-chess-games and Lichess/chess960-chess-games,
applies rating filter (WhiteElo >= 1800 AND BlackElo >= 1800), and
materializes filtered subsets to local JSONL files.

Usage:
    python scripts/acquire_chess.py --variant standard --target 2000
    python scripts/acquire_chess.py --variant chess960 --target 2000
    python scripts/acquire_chess.py --all --target 2000
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, '/Users/safiqsindha/Library/Python/3.9/lib/python/site-packages')

from datasets import load_dataset
import chess
import chess.pgn
import io

RATING_FLOOR = 1800
VARIANTS = {
    "standard": {
        "dataset": "Lichess/standard-chess-games",
        "out": Path("data/chess_standard/games.jsonl"),
        "chess960": False,
    },
    "chess960": {
        "dataset": "Lichess/chess960-chess-games",
        "out": Path("data/chess960/games.jsonl"),
        "chess960": True,
    },
}


def _elo(record: dict, key: str) -> int:
    """Extract ELO, returning 0 if missing or non-numeric."""
    v = record.get(key, 0)
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


def _passes_rating_filter(record: dict) -> bool:
    return (
        _elo(record, "WhiteElo") >= RATING_FLOOR
        and _elo(record, "BlackElo") >= RATING_FLOOR
    )


def _validate_pgn(movetext: str, chess960: bool = False, fen: str | None = None) -> bool:
    """Return True if the movetext parses without error (at least 5 plies)."""
    try:
        # Wrap raw movetext in minimal PGN headers for the parser
        if chess960 and fen:
            pgn_text = f'[FEN "{fen}"]\n[Variant "Chess960"]\n\n{movetext}'
        else:
            pgn_text = f'\n{movetext}'
        game = chess.pgn.read_game(io.StringIO(pgn_text))
        if game is None:
            return False
        # Count moves to confirm game has enough content (at least 10 plies)
        count = 0
        for _ in game.mainline_moves():
            count += 1
            if count >= 10:
                return True
        return count >= 5
    except Exception:
        return False


def acquire_variant(variant_key: str, target: int, validate_sample: int = 100) -> dict:
    """Stream, filter, and materialize one chess variant."""
    cfg = VARIANTS[variant_key]
    dataset_name = cfg["dataset"]
    out_path = cfg["out"]
    is_chess960 = cfg["chess960"]

    out_path.parent.mkdir(parents=True, exist_ok=True)

    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    print(f"\n[{variant_key}] Streaming {dataset_name} …")
    print(f"[{variant_key}] Rating filter: WhiteElo >= {RATING_FLOOR} AND BlackElo >= {RATING_FLOOR}")
    print(f"[{variant_key}] Target: {target} games")

    ds = load_dataset(dataset_name, split="train", streaming=True, trust_remote_code=True)

    collected = []
    examined = 0
    skipped_rating = 0

    for record in ds:
        examined += 1
        if examined % 50000 == 0:
            print(f"[{variant_key}]   examined={examined:,}  collected={len(collected):,}")
        if not _passes_rating_filter(record):
            skipped_rating += 1
            continue
        collected.append(record)
        if len(collected) >= target:
            break

    print(f"[{variant_key}] Done streaming: examined={examined:,}, collected={len(collected):,}, "
          f"skipped_rating={skipped_rating:,}")

    # Write JSONL — convert date/time objects to strings for JSON serialization
    import datetime as dt

    def _jsonify(obj):
        if isinstance(obj, (dt.date, dt.datetime)):
            return obj.isoformat()
        if isinstance(obj, dt.time):
            return obj.isoformat()
        raise TypeError(f"Not serializable: {type(obj)}")

    written = 0
    with out_path.open("w", encoding="utf-8") as fh:
        for rec in collected:
            try:
                fh.write(json.dumps(dict(rec), default=_jsonify) + "\n")
                written += 1
            except (TypeError, ValueError) as e:
                print(f"[{variant_key}] WARN: could not serialize record: {e}")

    print(f"[{variant_key}] Written {written} records to {out_path}")

    # Sample validation: parse 100 games via python-chess
    print(f"[{variant_key}] Validating sample of {min(validate_sample, len(collected))} games …")
    valid = 0
    invalid = 0
    import random
    sample = random.sample(collected, min(validate_sample, len(collected)))
    for rec in sample:
        movetext = rec.get("movetext", rec.get("Moves", rec.get("pgn", rec.get("moves", ""))))
        fen = rec.get("FEN", rec.get("fen", None)) if is_chess960 else None
        if movetext and _validate_pgn(str(movetext), chess960=is_chess960, fen=fen):
            valid += 1
        else:
            invalid += 1

    validation_rate = valid / max(valid + invalid, 1)
    print(f"[{variant_key}] Sample validation: {valid}/{valid+invalid} valid ({validation_rate:.1%})")

    return {
        "variant": variant_key,
        "dataset": dataset_name,
        "snapshot_date": snapshot_date,
        "examined": examined,
        "collected": len(collected),
        "written": written,
        "skipped_rating": skipped_rating,
        "sample_valid": valid,
        "sample_invalid": invalid,
        "sample_validation_rate": round(validation_rate, 4),
        "output_path": str(out_path),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=["standard", "chess960"], default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--target", type=int, default=2000,
                        help="Number of filtered games to collect per variant")
    parser.add_argument("--validate-sample", type=int, default=100)
    args = parser.parse_args()

    if not args.all and not args.variant:
        parser.error("Specify --variant or --all")

    variants_to_run = list(VARIANTS) if args.all else [args.variant]

    results = {}
    for v in variants_to_run:
        result = acquire_variant(v, target=args.target, validate_sample=args.validate_sample)
        results[v] = result

    # Summary
    print("\n=== Acquisition Summary ===")
    for v, r in results.items():
        print(f"  {v}: {r['collected']} games → {r['output_path']}")
        print(f"    snapshot: {r['snapshot_date']}")
        print(f"    validation: {r['sample_valid']}/{r['sample_valid']+r['sample_invalid']} ({r['sample_validation_rate']:.1%})")

    # Write summary to SESSION_LOG entry placeholder
    summary_path = Path("data/acquisition_summary.json")
    with summary_path.open("w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSummary written to {summary_path}")

    return results


if __name__ == "__main__":
    main()
