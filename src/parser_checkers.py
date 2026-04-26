"""
PDN parser for checkers (American 8x8 and international draughts 10x10).

Converts PDN game records from materialized JSONL files (Session 3)
into TrajectoryLog objects consumed by the T-code (Session 5).

Library: draughts (package installs as 'import draughts', NOT 'import pydraughts')
  American checkers:       Board("american")   squares 1–32
  International draughts:  Board("standard")   squares 1–50

Square numbering convention (SPEC §Data Sources note):
  American checkers uses dark-square numbers 1–32.
  International draughts uses numbers 1–50.
  Both are abstracted to sq_N labels to prevent leakage of numeric vocabulary.

FROZEN at git tag T-code-game-v1.0-frozen after Session 6 pilot.
"""

from __future__ import annotations

import json
import re
import sys
import warnings
from pathlib import Path
from typing import Iterator, Optional

sys.path.insert(0, '/Users/safiqsindha/Library/Python/3.9/lib/python/site-packages')

import draughts

from src.translation import TrajectoryLog, GameEvent

# Checkers variants
VARIANT_AMERICAN = "american"
VARIANT_INTERNATIONAL = "standard"   # draughts library uses "standard" for international 10x10

# ---------------------------------------------------------------------------
# Abstract piece label mappings (SPEC §Abstract label conventions)
# No checkers terminology — leakage check enforced by renderer.py
# ---------------------------------------------------------------------------
_PIECE_LABEL: dict[tuple, str] = {
    ("white", "man"):  "piece_A",
    ("white", "king"): "piece_B",
    ("black", "man"):  "piece_C",
    ("black", "king"): "piece_D",
}

# Starting piece counts by variant (for phase detection)
_INITIAL_PIECES = {
    VARIANT_AMERICAN:      24,   # 12 per side
    VARIANT_INTERNATIONAL: 40,   # 20 per side
}

# Phase thresholds as fraction of initial piece count
_OPENING_THRESH  = 0.80   # > 80% pieces remaining → opening
_ENDGAME_THRESH  = 0.45   # < 45% pieces remaining → endgame


# ---------------------------------------------------------------------------
# PDN move text parsing
# ---------------------------------------------------------------------------

_MOVE_PATTERN = re.compile(r'\d+(?:[-x]\d+)+')


def _parse_pdn_movetext(movetext: str) -> list[str]:
    """
    Extract ordered list of individual move strings from PDN move text.

    Handles:
    - Numbered format:  "1. 31-27 19-23 2. 33-28 ..."
    - Un-numbered:      "31-27 19-23 33-28 ..."
    - Multi-captures:   "18x27x36" → single token
    - Result tokens:    "1-0", "0-1", "2-0", "0-2", "1/2-1/2" → stripped
    """
    # Remove result tokens that look like move notation but aren't
    movetext = re.sub(r'\b(1-0|0-1|2-0|0-2|1/2-1/2|½-½)\b', '', movetext)
    moves = _MOVE_PATTERN.findall(movetext)
    return moves


def _parse_fen(fen: str) -> dict[int, tuple[str, str]]:
    """
    Parse draughts FEN string into board state dict.

    Parameters
    ----------
    fen : e.g. "W:W21,22,K30:B1,K5"

    Returns
    -------
    {square_number: (color, piece_type)} where piece_type is 'man' or 'king'
    """
    board: dict[int, tuple[str, str]] = {}
    parts = fen.split(':')
    for section in parts[1:]:
        if not section:
            continue
        color = 'white' if section[0] == 'W' else 'black'
        squares_str = section[1:]
        if not squares_str:
            continue
        for sq_str in squares_str.split(','):
            sq_str = sq_str.strip()
            if not sq_str:
                continue
            if sq_str.startswith('K'):
                board[int(sq_str[1:])] = (color, 'king')
            else:
                try:
                    board[int(sq_str)] = (color, 'man')
                except ValueError:
                    pass
    return board


def _checkers_phase(total_pieces: int, initial_pieces: int) -> str:
    """
    Classify game phase by fraction of pieces remaining.

    - Opening:    > 80% of initial pieces still on board
    - Endgame:    < 45% of initial pieces still on board
    - Middlegame: between
    """
    ratio = total_pieces / max(initial_pieces, 1)
    if ratio > _OPENING_THRESH:
        return "phase_opening"
    if ratio < _ENDGAME_THRESH:
        return "phase_endgame"
    return "phase_middlegame"


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

def parse_pdn_game(game_record: dict, variant: str = VARIANT_AMERICAN) -> TrajectoryLog:
    """
    Parse one PDN game record (dict from JSONL) into a TrajectoryLog.

    Parameters
    ----------
    game_record : dict with at minimum 'moves' (PDN movetext string)
    variant     : "american" (8x8, squares 1-32) or
                  "standard" (10x10 international, squares 1-50)

    Returns
    -------
    TrajectoryLog with one GameEvent per ply.

    Raises
    ------
    ValueError  : if moves field missing or no moves parse successfully.
    """
    movetext = game_record.get("moves", game_record.get("Moves", ""))
    if not movetext:
        raise ValueError("No moves in game record")

    raw_moves = _parse_pdn_movetext(movetext)
    if not raw_moves:
        raise ValueError("No moves parsed from movetext")

    # Initialise draughts board
    board = draughts.Board(variant)
    initial_pieces = _INITIAL_PIECES.get(variant, 24)
    initial_fen = board.fen

    events: list[GameEvent] = []
    ply = 0

    # Parse FEN before any moves to know starting positions
    prev_fen_state = _parse_fen(board.fen)

    for move_str in raw_moves:
        # Parse: from_sq is first number, to_sq is last number
        nums = [int(n) for n in re.findall(r'\d+', move_str)]
        if len(nums) < 2:
            ply += 1
            continue

        from_sq = nums[0]
        to_sq = nums[-1]
        is_capture = 'x' in move_str

        # Determine which side is moving and what piece
        piece_info = prev_fen_state.get(from_sq)
        if piece_info is None:
            # Try to infer from board turn
            turn_color = 'white' if board.turn == draughts.WHITE else 'black'
            piece_info = (turn_color, 'man')

        color, ptype = piece_info
        side = "side_1" if color == "white" else "side_2"
        piece_label = _PIECE_LABEL.get((color, ptype), "piece_A")

        # Compute phase from current piece count
        total_pieces = len(prev_fen_state)
        phase = _checkers_phase(total_pieces, initial_pieces)

        # Push move on draughts board
        try:
            move_obj = draughts.Move(board, pdn_move=move_str)
            board.push(move_obj)
            new_fen_state = _parse_fen(board.fen)

            # Detect promotions: piece was man, is now king on same destination
            dest_piece = new_fen_state.get(to_sq)
            is_promotion = (
                ptype == 'man'
                and dest_piece is not None
                and dest_piece[1] == 'king'
            )
        except Exception:
            # Move failed (illegal or parse error) — push minimally and continue
            new_fen_state = prev_fen_state
            is_promotion = False

        # Classify event type
        if is_promotion:
            evt_type = "promotion"
        elif is_capture:
            evt_type = "capture"
        else:
            evt_type = "move"

        events.append(GameEvent(
            move_number=ply,
            side=side,
            event_type=evt_type,
            piece_label=piece_label,
            from_square=f"sq_{from_sq}",
            to_square=f"sq_{to_sq}",
            is_capture=is_capture,
            is_check=False,      # checkers has no check
            phase_indicator=phase,
            metadata={
                "total_pieces": total_pieces,
                "white_pieces": sum(1 for c, _ in prev_fen_state.values() if c == 'white'),
                "black_pieces": sum(1 for c, _ in prev_fen_state.values() if c == 'black'),
                "is_promotion": is_promotion,
                "captured_squares": [nums[i] for i in range(1, len(nums) - 1)] if is_capture else [],
            },
        ))

        prev_fen_state = new_fen_state
        ply += 1

    if not events:
        raise ValueError("No events parsed from game record")

    # Derive game ID
    site = game_record.get("Site", "")
    game_id = site.split("/")[-1] if "/" in site else f"game_{abs(hash(movetext)) % 1_000_000}"
    variant_label = "checkers_american" if variant == VARIANT_AMERICAN else "draughts_intl"

    return TrajectoryLog(
        game_id=game_id,
        variant=variant_label,
        events=events,
        metadata={
            "result": game_record.get("Result", "?"),
            "ply_count": ply,
            "white_player": game_record.get("White", "?"),
            "black_player": game_record.get("Black", "?"),
            "event": game_record.get("Event", "?"),
            "initial_pieces": initial_pieces,
        },
    )


def parse_games_jsonl(
    jsonl_path: Path,
    variant: str = VARIANT_AMERICAN,
    limit: Optional[int] = None,
) -> Iterator[TrajectoryLog]:
    """
    Stream TrajectoryLogs from a materialized games JSONL file.

    Parameters
    ----------
    jsonl_path : path to data/checkers_american/games.jsonl or
                 data/draughts_intl/games.jsonl
    variant    : "american" or "standard"
    limit      : stop after this many games (None = all)

    Yields
    ------
    TrajectoryLog per game (skips malformed records with a warning).
    """
    count = 0
    with open(jsonl_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                traj = parse_pdn_game(record, variant=variant)
                yield traj
                count += 1
            except Exception as exc:
                warnings.warn(f"parser_checkers: skipped record (line {count + 1}): {exc}")
            if limit is not None and count >= limit:
                break
