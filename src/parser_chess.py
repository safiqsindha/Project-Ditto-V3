"""
PGN parser for chess (standard and Chess960) using python-chess.

Converts PGN game records from the materialized JSONL files (Session 2)
into TrajectoryLog objects consumed by the T-code (Session 5).

Chess960 note (SPEC §Data Sources):
  Each game in the Chess960 dataset includes a starting FEN. Pass it to
  chess.Board(fen=starting_fen, chess960=True) during parsing.

Square numbering convention: algebraic notation squares are abstracted to
integer indices (a1=0 ... h8=63) and then re-labelled as abstract square
labels (sq_0 ... sq_63) to prevent leakage of file/rank vocabulary.

FROZEN at git tag T-code-game-v1.0-frozen after Session 6 pilot.
"""

from __future__ import annotations

import io
import json
import sys
import warnings
from pathlib import Path
from typing import Iterator, Optional

sys.path.insert(0, '/Users/safiqsindha/Library/Python/3.9/lib/python/site-packages')

import chess
import chess.pgn

from src.translation import TrajectoryLog, GameEvent

# ---------------------------------------------------------------------------
# Abstract piece label mappings (SPEC §Abstract label conventions)
# No chess terminology in labels — leakage check enforced by renderer.py
# ---------------------------------------------------------------------------
_PIECE_LABEL: dict[tuple, str] = {
    (chess.WHITE, chess.PAWN):   "piece_A",
    (chess.WHITE, chess.KNIGHT): "piece_B",
    (chess.WHITE, chess.BISHOP): "piece_C",
    (chess.WHITE, chess.ROOK):   "piece_D",
    (chess.WHITE, chess.QUEEN):  "piece_E",
    (chess.WHITE, chess.KING):   "piece_F",
    (chess.BLACK, chess.PAWN):   "piece_G",
    (chess.BLACK, chess.KNIGHT): "piece_H",
    (chess.BLACK, chess.BISHOP): "piece_I",
    (chess.BLACK, chess.ROOK):   "piece_J",
    (chess.BLACK, chess.QUEEN):  "piece_K",
    (chess.BLACK, chess.KING):   "piece_L",
}

_MATERIAL_VALUES: dict[int, int] = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9,
}


# ---------------------------------------------------------------------------
# Phase detection helpers
# ---------------------------------------------------------------------------

def _total_material(board: chess.Board) -> tuple[int, int]:
    """Returns (total_material_excl_kings, queen_count) for phase detection."""
    total = 0
    queens = 0
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None or piece.piece_type == chess.KING:
            continue
        total += _MATERIAL_VALUES.get(piece.piece_type, 0)
        if piece.piece_type == chess.QUEEN:
            queens += 1
    return total, queens


def _chess_phase(board: chess.Board, ply: int) -> str:
    """
    Classify game phase based on ply number and board material.

    Heuristics (chess theory aligned):
    - Opening:    ply < 20 AND material > 50 (most pieces on board)
    - Endgame:    no queens OR total material < 20
    - Middlegame: everything else
    """
    total, queens = _total_material(board)
    if ply < 20 and total > 50:
        return "phase_opening"
    if queens == 0 or total < 20:
        return "phase_endgame"
    return "phase_middlegame"


def _material_counts(board: chess.Board) -> dict:
    """Return {side_1: int, side_2: int} material scores (excluding kings)."""
    counts = {"side_1": 0, "side_2": 0}
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece is None or piece.piece_type == chess.KING:
            continue
        side = "side_1" if piece.color == chess.WHITE else "side_2"
        counts[side] += _MATERIAL_VALUES.get(piece.piece_type, 0)
    return counts


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

def parse_pgn_game(game_record: dict, chess960: bool = False) -> TrajectoryLog:
    """
    Parse one PGN game record (dict from JSONL) into a TrajectoryLog.

    Parameters
    ----------
    game_record : dict with at minimum 'movetext' (PGN movetext string) and
                  optionally 'FEN' (starting position for Chess960)
    chess960    : if True, pass chess960=True to chess.Board()

    Returns
    -------
    TrajectoryLog with one GameEvent per ply.

    Raises
    ------
    ValueError  : if movetext is missing or PGN fails to parse.
    """
    movetext = game_record.get("movetext", game_record.get("Moves", ""))
    if not movetext:
        raise ValueError("No movetext in game record")

    # Build PGN string the parser can handle
    fen = game_record.get("FEN", game_record.get("fen", None)) if chess960 else None
    if chess960 and fen:
        pgn_text = f'[FEN "{fen}"]\n[Variant "Chess960"]\n\n{movetext}'
    else:
        pgn_text = f'\n{movetext}'

    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        raise ValueError("chess.pgn.read_game returned None")

    board = game.board()
    events: list[GameEvent] = []
    ply = 0

    for move in game.mainline_moves():
        piece = board.piece_at(move.from_square)
        if piece is None:
            # Shouldn't happen in a valid game, but skip gracefully
            board.push(move)
            ply += 1
            continue

        is_capture = board.is_capture(move)
        is_castling = board.is_castling(move)
        is_promotion = move.promotion is not None

        phase = _chess_phase(board, ply)

        # Classify event type
        if is_promotion:
            evt_type = "promotion"
        elif is_capture:
            evt_type = "capture"
        else:
            evt_type = "move"

        piece_label = _PIECE_LABEL.get((piece.color, piece.piece_type), "piece_X")
        from_sq = f"sq_{move.from_square}"
        to_sq = f"sq_{move.to_square}"
        side = "side_1" if piece.color == chess.WHITE else "side_2"

        # Push move, then check if opponent is now in check
        board.push(move)
        is_check = board.is_check()

        material = _material_counts(board)
        total_pieces = sum(
            1 for sq in chess.SQUARES
            if board.piece_at(sq) is not None and board.piece_at(sq).piece_type != chess.KING
        )

        events.append(GameEvent(
            move_number=ply,
            side=side,
            event_type=evt_type,
            piece_label=piece_label,
            from_square=from_sq,
            to_square=to_sq,
            is_capture=is_capture,
            is_check=is_check,
            phase_indicator=phase,
            metadata={
                "material_side_1": material["side_1"],
                "material_side_2": material["side_2"],
                "total_pieces_excl_kings": total_pieces,
                "is_castling": is_castling,
            },
        ))
        ply += 1

    # Derive game ID from Site URL or generate from hash
    site = game_record.get("Site", "")
    game_id = site.split("/")[-1] if "/" in site else f"game_{abs(hash(movetext)) % 1_000_000}"
    variant = "chess960" if chess960 else "chess_standard"

    return TrajectoryLog(
        game_id=game_id,
        variant=variant,
        events=events,
        metadata={
            "white_elo": game_record.get("WhiteElo"),
            "black_elo": game_record.get("BlackElo"),
            "result": game_record.get("Result", "?"),
            "ply_count": ply,
            "white_player": game_record.get("White", "?"),
            "black_player": game_record.get("Black", "?"),
        },
    )


def parse_games_jsonl(
    jsonl_path: Path,
    chess960: bool = False,
    limit: Optional[int] = None,
) -> Iterator[TrajectoryLog]:
    """
    Stream TrajectoryLogs from a materialized games JSONL file.

    Parameters
    ----------
    jsonl_path : path to data/chess_standard/games.jsonl or data/chess960/games.jsonl
    chess960   : if True, parse as Chess960 (uses FEN column)
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
                traj = parse_pgn_game(record, chess960=chess960)
                yield traj
                count += 1
            except Exception as exc:
                warnings.warn(f"parser_chess: skipped record (line {count + 1}): {exc}")
            if limit is not None and count >= limit:
                break
