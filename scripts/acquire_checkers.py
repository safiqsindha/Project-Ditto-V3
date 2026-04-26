"""
Session 3: Materialize checkers/draughts data from PDN sources.

American checkers (8x8): OCA 2.0 PDN
International draughts (10x10): Lidraughts API downloads + wiegerw/pdn

Usage:
    python scripts/acquire_checkers.py --variant american --target 2000
    python scripts/acquire_checkers.py --variant international --target 2000
    python scripts/acquire_checkers.py --all --target 2000
"""
from __future__ import annotations

import argparse
import json
import re
import random
from datetime import datetime, timezone
from pathlib import Path

VARIANTS = {
    "american": {
        "sources": [Path("data/checkers_american/raw/OCA_2.0.pdn")],
        "out": Path("data/checkers_american/games.jsonl"),
        "gametype": None,  # OCA games have their own format
        "board_size": 32,
    },
    "international": {
        "sources": [
            Path("data/draughts_intl/raw/lidraughts"),
            Path("data/draughts_intl/raw/lidraughts_users"),
            Path("data/draughts_intl/raw/succeed"),
            Path("data/draughts_intl/raw/fail"),
        ],
        "out": Path("data/draughts_intl/games.jsonl"),
        "gametype": "20",
        "board_size": 50,
    },
}


def parse_pdn_games(text: str) -> list[dict]:
    """Parse PDN text into a list of game dicts."""
    games = []
    # Split by double-blank lines followed by [ (new game starts with headers)
    # More robust: find each [Event block
    # A game consists of: header lines + moves line

    # Split on empty lines before header tags
    blocks = re.split(r'\n\s*\n(?=\[)', text.strip())

    for block in blocks:
        if not block.strip() or '[' not in block:
            continue

        game = {}
        lines = block.strip().split('\n')
        moves_lines = []
        in_header = True

        for line in lines:
            line = line.strip()
            if not line:
                continue
            tag_match = re.match(r'\[(\w+)\s+"([^"]*)"\]', line)
            if tag_match:
                in_header = True
                key, val = tag_match.groups()
                game[key] = val
            else:
                in_header = False
                if line:
                    moves_lines.append(line)

        game['moves'] = ' '.join(moves_lines).strip()
        if game.get('moves') or game.get('Event'):
            games.append(game)

    return games


def is_international_10x10(game: dict) -> bool:
    """Check if game is international 10x10 draughts."""
    gt = game.get('GameType', '')
    if gt == '20':
        return True

    # Check move notation for squares > 32
    moves = game.get('moves', '')
    sq_nums = re.findall(r'\b(\d+)\b', moves)
    if sq_nums:
        max_sq = max(int(n) for n in sq_nums)
        return max_sq > 32

    return False


def is_valid_game(game: dict, min_plies: int = 20) -> bool:
    """Check if game has enough moves to be useful."""
    moves = game.get('moves', '')
    if not moves:
        return False
    # Count move tokens: numbers and dashes/x
    tokens = re.findall(r'\d+-\d+|\d+x\d+', moves)
    return len(tokens) >= min_plies // 2


def load_pdn_from_source(source: Path, gametype_filter: str | None = None) -> list[dict]:
    """Load and parse PDN games from a file or directory."""
    games = []

    if source.is_file():
        files = [source]
    elif source.is_dir():
        files = list(source.glob("*.pdn"))
    else:
        return games

    for pdn_file in files:
        try:
            text = pdn_file.read_text(encoding='utf-8', errors='replace')
            file_games = parse_pdn_games(text)
            if gametype_filter:
                file_games = [g for g in file_games if is_international_10x10(g)]
            games.extend(file_games)
        except Exception as e:
            print(f"  WARN: Could not read {pdn_file}: {e}")

    return games


def acquire_variant(variant_key: str, target: int) -> dict:
    """Load, filter, deduplicate, and materialize one checkers variant."""
    cfg = VARIANTS[variant_key]
    out_path = cfg["out"]
    gametype_filter = cfg.get("gametype")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    print(f"\n[{variant_key}] Loading PDN sources...")

    all_games = []
    seen_ids = set()

    for source in cfg["sources"]:
        before = len(all_games)
        games = load_pdn_from_source(source, gametype_filter=gametype_filter)
        # Deduplicate by Lidraughts game ID (from Site URL)
        for g in games:
            site = g.get('Site', '')
            game_id_match = re.search(r'lidraughts\.org/([A-Za-z0-9]{8,12})', site)
            if game_id_match:
                gid = game_id_match.group(1)
                if gid in seen_ids:
                    continue
                seen_ids.add(gid)
            all_games.append(g)
        after = len(all_games)
        print(f"  {source}: +{after - before} games (total: {after})")

    print(f"[{variant_key}] Total after dedup: {len(all_games)}")

    # Filter by minimum game length
    valid = [g for g in all_games if is_valid_game(g)]
    print(f"[{variant_key}] After length filter (≥10 moves): {len(valid)}")

    if len(valid) < 1500:
        print(f"[{variant_key}] WARNING: Only {len(valid)} valid games — below Gate 2b threshold of 1,500!")

    # Sample or truncate to target
    if len(valid) > target:
        random.seed(42)
        selected = random.sample(valid, target)
    else:
        selected = valid

    print(f"[{variant_key}] Writing {len(selected)} games to {out_path}")

    written = 0
    with out_path.open('w', encoding='utf-8') as fh:
        for g in selected:
            try:
                fh.write(json.dumps(g) + '\n')
                written += 1
            except (TypeError, ValueError) as e:
                print(f"  WARN: serialization error: {e}")

    print(f"[{variant_key}] Written: {written}")

    return {
        "variant": variant_key,
        "snapshot_date": snapshot_date,
        "total_loaded": len(all_games),
        "after_length_filter": len(valid),
        "selected": len(selected),
        "written": written,
        "output_path": str(out_path),
        "gate_2b_ok": len(valid) >= 1500,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=["american", "international"], default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--target", type=int, default=2000)
    args = parser.parse_args()

    if not args.all and not args.variant:
        parser.error("Specify --variant or --all")

    variants_to_run = list(VARIANTS) if args.all else [args.variant]

    results = {}
    for v in variants_to_run:
        result = acquire_variant(v, target=args.target)
        results[v] = result

    print("\n=== Acquisition Summary ===")
    for v, r in results.items():
        gate_status = "✅ PASS" if r['gate_2b_ok'] else "❌ GATE 2b FAIL"
        print(f"  {v}: {r['written']} games → {r['output_path']}")
        print(f"    loaded: {r['total_loaded']}, after_filter: {r['after_length_filter']}")
        print(f"    Gate 2b: {gate_status}")

    # Write summary
    summary_path = Path("data/checkers_acquisition_summary.json")
    with summary_path.open("w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSummary written to {summary_path}")

    return results


if __name__ == "__main__":
    main()
