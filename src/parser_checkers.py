"""
PDN parser for checkers (American 8x8 and international draughts 10x10).

Converts PDN game records from materialized JSONL files (Session 3)
into TrajectoryLog objects consumed by the T-code (Session 5).

Library: pydraughts (AttackingOrDefending on PyPI)
  American checkers:    Board(variant="american")   squares 1–32
  International draughts: Board(variant="standard")  squares 1–50

Square numbering convention (SPEC §Data Sources note):
  American checkers uses dark-square numbers 1–32.
  International draughts uses numbers 1–50.
  Both are abstracted to sq_N labels to prevent leakage of numeric vocabulary.

Implementation deferred to Session 4.
FROZEN at git tag T-code-game-v1.0-frozen after Session 6 pilot.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from src.translation import TrajectoryLog, GameEvent

# Checkers variants supported by pydraughts
VARIANT_AMERICAN = "american"
VARIANT_INTERNATIONAL = "standard"   # pydraughts uses "standard" for international 10x10


def parse_pdn_game(game_record: dict, variant: str = VARIANT_AMERICAN) -> TrajectoryLog:
    """
    Parse one PDN game record (dict from JSONL) into a TrajectoryLog.

    Parameters
    ----------
    game_record : dict with at minimum 'moves' (PDN movetext) and
                  optionally 'result', 'white', 'black' header fields
    variant     : "american" (8x8, squares 1-32) or
                  "standard" (10x10 international, squares 1-50)

    Returns
    -------
    TrajectoryLog with one GameEvent per ply.

    Notes
    -----
    - American checkers: Board(variant="american"), squares 1–32
    - International draughts: Board(variant="standard"), squares 1–50
    - Both variants: kings are pieces that have been promoted;
      label as piece_N in abstract output (no "king" vocabulary per leakage check)

    Implementation deferred to Session 4.
    """
    raise NotImplementedError(
        "parse_pdn_game is a stub — implement in Session 4. "
        "Use pydraughts library. variant='american' or variant='standard'."
    )


def parse_games_jsonl(
    jsonl_path: Path,
    variant: str = VARIANT_AMERICAN,
    limit: int | None = None,
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

    Implementation deferred to Session 4.
    """
    raise NotImplementedError(
        "parse_games_jsonl is a stub — implement in Session 4."
    )
