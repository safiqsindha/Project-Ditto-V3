"""
PGN parser for chess (standard and Chess960) using python-chess.

Converts PGN game records from the materialized JSONL files (Sessions 2)
into TrajectoryLog objects consumed by the T-code (Session 5).

Chess960 note (SPEC §Data Sources):
  Each game in the Chess960 dataset includes a starting FEN. Pass it to
  chess.Board(fen=starting_fen, chess960=True) during parsing.

Square numbering convention: algebraic notation squares are abstracted to
integer indices (a1=0 ... h8=63) and then re-labelled as abstract square
labels (sq_0 ... sq_63) to prevent leakage of file/rank vocabulary.

Implementation deferred to Session 4.
FROZEN at git tag T-code-game-v1.0-frozen after Session 6 pilot.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from src.translation import TrajectoryLog, GameEvent


def parse_pgn_game(game_record: dict, chess960: bool = False) -> TrajectoryLog:
    """
    Parse one PGN game record (dict from JSONL) into a TrajectoryLog.

    Parameters
    ----------
    game_record : dict with at minimum 'Moves' (PGN movetext string) and
                  optionally 'FEN' (starting position for Chess960)
    chess960    : if True, pass chess960=True to chess.Board()

    Returns
    -------
    TrajectoryLog with one GameEvent per move.

    Implementation deferred to Session 4.
    """
    raise NotImplementedError(
        "parse_pgn_game is a stub — implement in Session 4. "
        "Use python-chess library. For Chess960, pass chess960=True to chess.Board()."
    )


def parse_games_jsonl(
    jsonl_path: Path,
    chess960: bool = False,
    limit: int | None = None,
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

    Implementation deferred to Session 4.
    """
    raise NotImplementedError(
        "parse_games_jsonl is a stub — implement in Session 4."
    )
