"""
Leakage glossary: authoritative dictionary of game-domain vocabulary that must
NOT appear in rendered constraint chains.

This module is the SINGLE SOURCE OF TRUTH for what counts as leakage. The
renderer's check_leakage() and check_leakage_substring() functions both derive
their term sets from GLOSSARY here.

Sources cited per entry:
  - "wikipedia.glossary_of_chess"  (https://en.wikipedia.org/wiki/Glossary_of_chess)
  - "wikipedia.english_draughts"   (https://en.wikipedia.org/wiki/English_draughts)
  - "wikipedia.pdn"                (https://en.wikipedia.org/wiki/Portable_Draughts_Notation)
  - "chess.com.terms"              (https://www.chess.com/terms)
  - "spec.v1"                      (SPEC.md §Renderer leakage vocabulary)
  - "domain_knowledge"             (curator addition with rationale in `note`)

Two-tier check semantics:
  - hard_check (severity ∈ {high, medium}): word-boundary regex (\\bterm\\b);
    fails the rendered chain if any match found.
  - soft_check (all severities + extra suggestive terms): substring scan with
    explicit exemptions (SOFT_CHECK_EXEMPTIONS); warns but does not fail. Used
    during development to catch architecturally-suspect strings like
    "material_white" or "king_safety" where the regex would not fire.

Word-boundary subtlety (Python re):
  Python's \\b treats `_` as a word character. So \\bpawn\\b does NOT match
  inside `pawn_chain_B` (no boundary between `n` and `_`). The hard check
  therefore allows abstract compound labels that embed leakage terms — which
  is precisely why the soft check is needed as a second line of defense.

FROZEN as part of the T-code-game-v1.0-frozen tag. New terms may be added (with
provenance) but existing terms must not be removed without justification in
SESSION_LOG.md.
"""

from __future__ import annotations

from typing import TypedDict


# ---------------------------------------------------------------------------
# Glossary entry schema
# ---------------------------------------------------------------------------

class GlossaryEntry(TypedDict, total=False):
    term: str
    category: str       # e.g. "chess.piece", "checkers.rule"
    severity: str       # "high" | "medium" | "low"
    definition: str     # one-line, ≤15 words
    source: str         # provenance
    note: str           # optional curator note
    added_session: int  # session in which the term was added


# ---------------------------------------------------------------------------
# GLOSSARY (authoritative list)
# ---------------------------------------------------------------------------
# Entries are grouped by category for review. Order within group is alphabetical.

GLOSSARY: list[GlossaryEntry] = [

    # ----- CHESS PIECES (high severity — direct piece names) ----------------
    {"term": "pawn",   "category": "chess.piece", "severity": "high",
     "definition": "Lowest-value chess piece moving forward, capturing diagonally.",
     "source": "spec.v1", "added_session": 1},
    {"term": "knight", "category": "chess.piece", "severity": "high",
     "definition": "Chess piece moving in L-shape, jumps over pieces.",
     "source": "spec.v1", "added_session": 1},
    {"term": "bishop", "category": "chess.piece", "severity": "high",
     "definition": "Chess piece moving on diagonals only.",
     "source": "spec.v1", "added_session": 1},
    {"term": "rook",   "category": "chess.piece", "severity": "high",
     "definition": "Chess piece moving on ranks and files.",
     "source": "spec.v1", "added_session": 1},
    {"term": "queen",  "category": "chess.piece", "severity": "high",
     "definition": "Most powerful chess piece, combines rook and bishop moves.",
     "source": "spec.v1", "added_session": 1},
    {"term": "king",   "category": "chess.piece", "severity": "high",
     "definition": "Royal piece in chess and crowned piece in checkers.",
     "source": "spec.v1",
     "note": "Dual usage: chess (royal piece) and checkers (crowned). Both leak.",
     "added_session": 1},
    {"term": "chessmen", "category": "chess.piece", "severity": "high",
     "definition": "Collective name for chess pieces.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "minor piece", "category": "chess.piece", "severity": "high",
     "definition": "Bishop or knight (low-value pieces).",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "major piece", "category": "chess.piece", "severity": "high",
     "definition": "Rook or queen (high-value pieces).",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},

    # ----- CHECKERS PIECES --------------------------------------------------
    {"term": "man", "category": "checkers.piece", "severity": "high",
     "definition": "Uncrowned checkers piece moving diagonally forward.",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "men", "category": "checkers.piece", "severity": "high",
     "definition": "Plural of 'man' in checkers.",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "crown",   "category": "checkers.piece", "severity": "high",
     "definition": "Verb/noun: promotion of checkers piece to king.",
     "source": "spec.v1", "added_session": 1},
    {"term": "crowned", "category": "checkers.piece", "severity": "high",
     "definition": "Adjective: a man that has reached the king's row.",
     "source": "spec.v1", "added_session": 1},
    {"term": "crownhead", "category": "checkers.geometry", "severity": "high",
     "definition": "Alternative term for the king's row.",
     "source": "wikipedia.english_draughts", "added_session": 6},

    # ----- CHESS TACTICAL MOTIFS -------------------------------------------
    {"term": "fork", "category": "chess.tactic", "severity": "high",
     "definition": "Single piece attacking two enemy pieces simultaneously.",
     "source": "spec.v1", "added_session": 1},
    {"term": "pin", "category": "chess.tactic", "severity": "high",
     "definition": "Attack on piece shielding more valuable piece behind.",
     "source": "spec.v1", "added_session": 1},
    {"term": "skewer", "category": "chess.tactic", "severity": "high",
     "definition": "Reverse pin: high-value piece forced to move, exposing piece behind.",
     "source": "spec.v1", "added_session": 1},
    {"term": "battery", "category": "chess.tactic", "severity": "high",
     "definition": "Two pieces aligned attacking same target.",
     "source": "wikipedia.glossary_of_chess",
     "note": "Was prescribed as battery_A in CLAUDE.md; renamed to coordination_A in S6.",
     "added_session": 6},
    {"term": "x-ray", "category": "chess.tactic", "severity": "high",
     "definition": "Indirect attack through enemy piece.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "zugzwang", "category": "chess.tactic", "severity": "high",
     "definition": "Position where any move worsens player's situation.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "zwischenzug", "category": "chess.tactic", "severity": "high",
     "definition": "In-between move inserted into expected sequence.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "gambit", "category": "chess.tactic", "severity": "high",
     "definition": "Opening sacrifice for development or attack.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "fianchetto", "category": "chess.tactic", "severity": "high",
     "definition": "Bishop developed on long diagonal via knight pawn move.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "discovered attack", "category": "chess.tactic", "severity": "high",
     "definition": "Attack revealed when blocking piece moves.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "discovered check", "category": "chess.tactic", "severity": "high",
     "definition": "Check revealed when blocking piece moves.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "double attack", "category": "chess.tactic", "severity": "high",
     "definition": "Two attacks made by single move.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "double check", "category": "chess.tactic", "severity": "high",
     "definition": "Two pieces giving check simultaneously.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "decoy", "category": "chess.tactic", "severity": "medium",
     "definition": "Tactic luring enemy piece to bad square.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "deflection", "category": "chess.tactic", "severity": "medium",
     "definition": "Decoy tactic luring defender from key square.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "desperado", "category": "chess.tactic", "severity": "medium",
     "definition": "Piece giving itself for maximum compensation.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "sacrifice", "category": "chess.tactic", "severity": "medium",
     "definition": "Voluntary loss of material for compensation.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "sac", "category": "chess.tactic", "severity": "medium",
     "definition": "Slang abbreviation of sacrifice.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "blunder", "category": "chess.tactic", "severity": "medium",
     "definition": "Critically bad move; serious oversight.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "brilliancy", "category": "chess.tactic", "severity": "medium",
     "definition": "Game with spectacular strategic combination.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "trap", "category": "chess.tactic", "severity": "low",
     "definition": "Move designed to provoke losing reply.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "swindle", "category": "chess.tactic", "severity": "medium",
     "definition": "Trick in lost position to save game.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},

    # ----- CHESS RULES / SPECIAL MOVES -------------------------------------
    {"term": "castle",   "category": "chess.rule", "severity": "high",
     "definition": "King-rook combined move (special chess rule).",
     "source": "spec.v1", "added_session": 1},
    {"term": "castling", "category": "chess.rule", "severity": "high",
     "definition": "The act of castling; chess-only special move.",
     "source": "spec.v1", "added_session": 1},
    {"term": "en passant", "category": "chess.rule", "severity": "high",
     "definition": "Special pawn capture rule in chess.",
     "source": "spec.v1", "added_session": 1},
    {"term": "en-passant", "category": "chess.rule", "severity": "high",
     "definition": "Hyphenated spelling of en passant.",
     "source": "spec.v1", "added_session": 1},
    {"term": "promotion", "category": "chess.rule", "severity": "high",
     "definition": "Pawn reaching last rank converted to higher piece.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "promote",   "category": "chess.rule", "severity": "high",
     "definition": "Verb form of promotion.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "check",     "category": "chess.rule", "severity": "high",
     "definition": "Direct attack on enemy king.",
     "source": "spec.v1", "added_session": 1},
    {"term": "checkmate", "category": "chess.rule", "severity": "high",
     "definition": "King in check with no legal escape; game over.",
     "source": "spec.v1", "added_session": 1},
    {"term": "mate",      "category": "chess.rule", "severity": "high",
     "definition": "Short for checkmate.",
     "source": "spec.v1", "added_session": 1},
    {"term": "stalemate", "category": "chess.rule", "severity": "high",
     "definition": "Player has no legal move but is not in check; draw.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "fifty-move rule", "category": "chess.rule", "severity": "high",
     "definition": "Draw if no capture or pawn move in 50 moves.",
     "source": "chess.com.terms", "added_session": 6},
    {"term": "threefold repetition", "category": "chess.rule", "severity": "high",
     "definition": "Draw if same position occurs three times.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "perpetual check", "category": "chess.rule", "severity": "high",
     "definition": "Endless check sequence, often forcing draw.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},

    # ----- CHESS MATE PATTERNS ---------------------------------------------
    {"term": "back-rank mate", "category": "chess.mate", "severity": "high",
     "definition": "Mate on first/eighth rank by major piece.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "smothered mate", "category": "chess.mate", "severity": "high",
     "definition": "Mate by knight, king blocked by own pieces.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "anastasia's mate", "category": "chess.mate", "severity": "high",
     "definition": "Mate pattern using knight and rook.",
     "source": "chess.com.terms", "added_session": 6},
    {"term": "arabian mate",   "category": "chess.mate", "severity": "high",
     "definition": "Mate by knight and rook in corner.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "boden's mate",   "category": "chess.mate", "severity": "high",
     "definition": "Mate by two crisscrossing bishops.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "fool's mate",    "category": "chess.mate", "severity": "high",
     "definition": "Quickest possible chess mate (2 moves).",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "scholar's mate", "category": "chess.mate", "severity": "high",
     "definition": "Four-move mate targeting f7/f2.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "helpmate", "category": "chess.mate", "severity": "high",
     "definition": "Composition where both sides cooperate to mate.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},

    # ----- CHESS GEOMETRY --------------------------------------------------
    {"term": "file", "category": "chess.geometry", "severity": "high",
     "definition": "Column on chess/checkers board (a–h).",
     "source": "spec.v1", "added_session": 1},
    {"term": "rank", "category": "chess.geometry", "severity": "high",
     "definition": "Row on chess board (1–8).",
     "source": "spec.v1", "added_session": 1},
    {"term": "diagonal", "category": "chess.geometry", "severity": "high",
     "definition": "Line of same-color squares corner-to-corner.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "kingside",  "category": "chess.geometry", "severity": "high",
     "definition": "Half of board with kings (e–h files).",
     "source": "spec.v1", "added_session": 1},
    {"term": "queenside", "category": "chess.geometry", "severity": "high",
     "definition": "Half of board with queens (a–d files).",
     "source": "spec.v1", "added_session": 1},
    {"term": "back rank", "category": "chess.geometry", "severity": "high",
     "definition": "Player's first rank where pieces start.",
     "source": "wikipedia.glossary_of_chess",
     "note": "Was prescribed as back_row_C in CLAUDE.md; renamed to formation_C in S6.",
     "added_session": 6},
    {"term": "back row",  "category": "chess.geometry", "severity": "high",
     "definition": "Synonym for back rank.",
     "source": "domain_knowledge", "added_session": 6},
    {"term": "kings row", "category": "checkers.geometry", "severity": "high",
     "definition": "Last row in checkers; reaching it crowns the man.",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "double corner", "category": "checkers.geometry", "severity": "high",
     "definition": "Pair of dark squares in the corner of a checkers board.",
     "source": "spec.v1", "added_session": 1},
    {"term": "double-corner", "category": "checkers.geometry", "severity": "high",
     "definition": "Hyphenated form of double corner.",
     "source": "spec.v1", "added_session": 1},
    {"term": "dark squares",  "category": "board.geometry", "severity": "high",
     "definition": "Playable squares on a checkerboard; one of two colors in chess.",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "light squares", "category": "board.geometry", "severity": "high",
     "definition": "Light-colored half of board's 64/100 squares.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "checkerboard",  "category": "board.geometry", "severity": "high",
     "definition": "8x8 board with alternating square colors.",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "chessboard",    "category": "board.geometry", "severity": "high",
     "definition": "Checkered board of 64 squares.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},

    # ----- CHECKERS / DRAUGHTS RULES ---------------------------------------
    {"term": "jump",    "category": "checkers.rule", "severity": "high",
     "definition": "Capture move in checkers; over piece to empty square.",
     "source": "spec.v1", "added_session": 1},
    {"term": "capture", "category": "move.both",   "severity": "high",
     "definition": "Removing opponent's piece from board.",
     "source": "spec.v1",
     "note": "Used in both chess and checkers.",
     "added_session": 1},
    {"term": "huff",     "category": "checkers.rule", "severity": "medium",
     "definition": "Archaic: forced removal of piece that missed available capture.",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "huffing",  "category": "checkers.rule", "severity": "medium",
     "definition": "Practice of huffing.",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "mandatory jumping", "category": "checkers.rule", "severity": "high",
     "definition": "Player must take available jump.",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "three-move restriction", "category": "checkers.rule", "severity": "high",
     "definition": "Tournament variant: random 3-move opening.",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "two-move restriction",   "category": "checkers.rule", "severity": "high",
     "definition": "Earlier tournament variant: random 2-move opening.",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "go as you please", "category": "checkers.rule", "severity": "high",
     "definition": "Unrestricted opening (GAYP) checkers play.",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "gayp", "category": "checkers.rule", "severity": "high",
     "definition": "Acronym for Go As You Please.",
     "source": "wikipedia.english_draughts", "added_session": 6},

    # ----- CHESS POSITIONAL & PAWN STRUCTURE -------------------------------
    {"term": "isolated pawn", "category": "chess.structure", "severity": "high",
     "definition": "Pawn with no friendly pawn on adjacent files.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "doubled pawn",  "category": "chess.structure", "severity": "high",
     "definition": "Two pawns of same color on same file.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "passed pawn",   "category": "chess.structure", "severity": "high",
     "definition": "Pawn with no opposing pawn blocking promotion path.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "backward pawn", "category": "chess.structure", "severity": "high",
     "definition": "Pawn behind same-color neighbors, unable to advance.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "connected pawns", "category": "chess.structure", "severity": "high",
     "definition": "Pawns on adjacent files, mutually defensible.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "pawn chain",    "category": "chess.structure", "severity": "high",
     "definition": "Linked diagonally-defending pawn formation.",
     "source": "wikipedia.glossary_of_chess",
     "note": "Was prescribed as pawn_chain_B in CLAUDE.md; renamed to chain_B in S6.",
     "added_session": 6},
    {"term": "pawn structure", "category": "chess.structure", "severity": "high",
     "definition": "Configuration of pawns on board.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "pawn island",   "category": "chess.structure", "severity": "high",
     "definition": "Group of connected pawns separated from others.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "outpost",       "category": "chess.structure", "severity": "high",
     "definition": "Square deep in enemy territory unattackable by pawn.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "weak square",   "category": "chess.structure", "severity": "medium",
     "definition": "Square indefensible by pawn.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "hole",          "category": "chess.structure", "severity": "medium",
     "definition": "Weak square in own territory.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "bishop pair",   "category": "chess.structure", "severity": "high",
     "definition": "Both bishops; advantage in open positions.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "bad bishop",    "category": "chess.structure", "severity": "high",
     "definition": "Bishop blocked by own pawns.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},

    # ----- COLOR / SIDE NAMES ----------------------------------------------
    {"term": "white", "category": "color.side", "severity": "high",
     "definition": "Side moving first in chess and checkers.",
     "source": "wikipedia.glossary_of_chess",
     "note": "Critical: would render unmasked inside material_white. Renamed to side_1 in S6.",
     "added_session": 6},
    {"term": "black", "category": "color.side", "severity": "high",
     "definition": "Side moving second in chess and checkers.",
     "source": "wikipedia.glossary_of_chess",
     "note": "Critical: would render unmasked inside material_black. Renamed to side_2 in S6.",
     "added_session": 6},

    # ----- VARIANT NAMES / GAME NAMES --------------------------------------
    {"term": "chess",    "category": "game.name", "severity": "high",
     "definition": "The game itself.",
     "source": "spec.v1", "added_session": 1},
    {"term": "chess960", "category": "game.name", "severity": "high",
     "definition": "Fischer Random Chess variant.",
     "source": "spec.v1", "added_session": 1},
    {"term": "fischer random", "category": "game.name", "severity": "high",
     "definition": "Alternative name for Chess960.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "draughts",  "category": "game.name", "severity": "high",
     "definition": "British/international name for checkers.",
     "source": "spec.v1", "added_session": 1},
    {"term": "checkers",  "category": "game.name", "severity": "high",
     "definition": "American name for draughts.",
     "source": "spec.v1", "added_session": 1},
    {"term": "chequers",  "category": "game.name", "severity": "high",
     "definition": "British spelling of checkers.",
     "source": "spec.v1", "added_session": 1},
    {"term": "english draughts", "category": "game.name", "severity": "high",
     "definition": "American checkers variant; 8x8 board.",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "international draughts", "category": "game.name", "severity": "high",
     "definition": "10x10 draughts variant.",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "polish draughts",   "category": "game.name", "severity": "high",
     "definition": "Variant of international draughts.",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "russian draughts",  "category": "game.name", "severity": "high",
     "definition": "64-square variant.",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "italian draughts",  "category": "game.name", "severity": "high",
     "definition": "8x8 variant played with men over kings rules.",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "brazilian draughts", "category": "game.name", "severity": "high",
     "definition": "10x10 variant (Brazilian rules).",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "atomic chess",    "category": "game.name", "severity": "high",
     "definition": "Chess variant where captures cause adjacent piece explosions.",
     "source": "chess.com.terms", "added_session": 6},
    {"term": "antichess",       "category": "game.name", "severity": "high",
     "definition": "Chess variant: forced captures, lose pieces to win.",
     "source": "chess.com.terms", "added_session": 6},
    {"term": "bughouse",        "category": "game.name", "severity": "high",
     "definition": "Two-board chess variant played in teams.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "three check",     "category": "game.name", "severity": "high",
     "definition": "Chess variant: third check wins.",
     "source": "chess.com.terms", "added_session": 6},

    # ----- NOTATION FORMATS ------------------------------------------------
    {"term": "pgn", "category": "notation.format", "severity": "high",
     "definition": "Portable Game Notation (chess).",
     "source": "spec.v1", "added_session": 1},
    {"term": "pdn", "category": "notation.format", "severity": "high",
     "definition": "Portable Draughts Notation.",
     "source": "spec.v1", "added_session": 1},
    {"term": "fen", "category": "notation.format", "severity": "high",
     "definition": "Forsyth-Edwards Notation; board state encoding.",
     "source": "wikipedia.pdn", "added_session": 1},
    {"term": "epd", "category": "notation.format", "severity": "high",
     "definition": "Extended Position Description; FEN extension.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "uci", "category": "notation.format", "severity": "high",
     "definition": "Universal Chess Interface engine protocol.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "san", "category": "notation.format", "severity": "high",
     "definition": "Standard Algebraic Notation.",
     "source": "wikipedia.pdn", "added_session": 6},
    {"term": "algebraic notation", "category": "notation.format", "severity": "high",
     "definition": "Move recording using rank-file coordinates.",
     "source": "spec.v1", "added_session": 1},
    {"term": "descriptive notation", "category": "notation.format", "severity": "high",
     "definition": "Older notation using piece-relative descriptions.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},

    # ----- GOVERNING BODIES / SOURCES --------------------------------------
    {"term": "fide",   "category": "metadata.body", "severity": "high",
     "definition": "International Chess Federation.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "fmjd",   "category": "metadata.body", "severity": "high",
     "definition": "World Draughts Federation (Fédération Mondiale Jeu de Dames).",
     "source": "spec.v1", "added_session": 1},
    {"term": "acf",    "category": "metadata.body", "severity": "high",
     "definition": "American Checker Federation.",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "wcdf",   "category": "metadata.body", "severity": "high",
     "definition": "World Checkers Draughts Federation.",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "lichess",   "category": "metadata.body", "severity": "high",
     "definition": "Open chess platform.",
     "source": "domain_knowledge", "added_session": 1},
    {"term": "lidraughts","category": "metadata.body", "severity": "high",
     "definition": "Lichess fork for international draughts.",
     "source": "domain_knowledge", "added_session": 3},
    {"term": "chess.com", "category": "metadata.body", "severity": "high",
     "definition": "Commercial chess platform.",
     "source": "domain_knowledge", "added_session": 6},
    {"term": "oca",       "category": "metadata.body", "severity": "high",
     "definition": "Open Checkers Archive (OCA 2.0 PDN dataset).",
     "source": "spec.v1", "added_session": 1},

    # ----- ENGINES ---------------------------------------------------------
    {"term": "stockfish", "category": "engine", "severity": "high",
     "definition": "Strongest open-source chess engine.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "leela",     "category": "engine", "severity": "high",
     "definition": "Neural-net chess engine (Leela Chess Zero).",
     "source": "domain_knowledge", "added_session": 6},
    {"term": "lc0",       "category": "engine", "severity": "high",
     "definition": "Leela Chess Zero short form.",
     "source": "domain_knowledge", "added_session": 6},
    {"term": "alphazero", "category": "engine", "severity": "high",
     "definition": "DeepMind chess/go/shogi self-play system.",
     "source": "chess.com.terms", "added_session": 6},
    {"term": "chinook",   "category": "engine", "severity": "high",
     "definition": "Solved-checkers program (2007).",
     "source": "wikipedia.english_draughts", "added_session": 6},
    {"term": "kingsrow",  "category": "engine", "severity": "high",
     "definition": "Top contemporary draughts engine.",
     "source": "wikipedia.english_draughts", "added_session": 6},

    # ----- TIME CONTROL / GAME FORMAT --------------------------------------
    {"term": "blitz",   "category": "format.time", "severity": "high",
     "definition": "Fast chess: ~3-5 minutes per side.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "bullet",  "category": "format.time", "severity": "high",
     "definition": "Very fast chess: 1 minute per side.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "rapid",   "category": "format.time", "severity": "high",
     "definition": "Medium-pace chess time control (~10-25 min).",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "armageddon", "category": "format.time", "severity": "high",
     "definition": "Tiebreak: draw counts as black win.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "blindfold chess", "category": "format.special", "severity": "high",
     "definition": "Chess played without sight of board.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},

    # ----- CHESS STRATEGIC VOCABULARY (medium severity) --------------------
    {"term": "tempo",      "category": "chess.strategy", "severity": "medium",
     "definition": "A move's value as initiative gain.",
     "source": "wikipedia.glossary_of_chess",
     "note": "Was used in tempo_remaining, tempo_advantage; renamed to progress_* in S6.",
     "added_session": 6},
    {"term": "initiative", "category": "chess.strategy", "severity": "medium",
     "definition": "Ability to make threats opponent must answer.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "material",   "category": "chess.strategy", "severity": "medium",
     "definition": "Total piece value held.",
     "source": "wikipedia.glossary_of_chess",
     "note": "Was used in material_white/black, material_gain; renamed to resource_* in S6.",
     "added_session": 6},
    {"term": "positional", "category": "chess.strategy", "severity": "medium",
     "definition": "Pertaining to long-term position over tactics.",
     "source": "wikipedia.glossary_of_chess",
     "note": "Used in positional_transition trigger; renamed to structural_transition in S6.",
     "added_session": 6},
    {"term": "tactical",   "category": "chess.strategy", "severity": "medium",
     "definition": "Pertaining to short-term forcing sequences.",
     "source": "wikipedia.glossary_of_chess",
     "note": "Used in tactical_shift trigger; renamed to opportunity_shift in S6.",
     "added_session": 6},
    {"term": "tactics",    "category": "chess.strategy", "severity": "medium",
     "definition": "Short-term forcing combinations.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "centipawn",  "category": "chess.strategy", "severity": "high",
     "definition": "Engine evaluation unit: 1/100 of a pawn.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},

    # ----- RESULT TOKENS ---------------------------------------------------
    {"term": "1-0",     "category": "result.token", "severity": "high",
     "definition": "White wins.",
     "source": "wikipedia.pdn", "added_session": 6},
    {"term": "0-1",     "category": "result.token", "severity": "high",
     "definition": "Black wins.",
     "source": "wikipedia.pdn", "added_session": 6},
    {"term": "1/2-1/2", "category": "result.token", "severity": "high",
     "definition": "Draw.",
     "source": "wikipedia.pdn", "added_session": 6},
    {"term": "½-½",     "category": "result.token", "severity": "high",
     "definition": "Draw (Unicode form).",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},

    # ----- MISC HIGH-SIGNAL TERMS ------------------------------------------
    {"term": "elo",     "category": "metadata.rating", "severity": "high",
     "definition": "Player rating system.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "grandmaster", "category": "metadata.rating", "severity": "high",
     "definition": "Top chess title (GM).",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},
    {"term": "tournament",  "category": "metadata.event", "severity": "low",
     "definition": "Generic competition term; only suspicious in context.",
     "source": "domain_knowledge",
     "note": "Low severity due to generality. Kept in soft check only.",
     "added_session": 6},

    # ----- PHASE WORDS (medium — see SOFT_CHECK_EXEMPTIONS) ----------------
    # `opening`, `middlegame`, `endgame` are listed because bare uses leak.
    # The compound forms `phase_opening`, `phase_middlegame`, `phase_endgame`
    # are explicitly exempted in SOFT_CHECK_EXEMPTIONS below.
    {"term": "opening",    "category": "chess.phase", "severity": "medium",
     "definition": "First phase of game; piece development.",
     "source": "wikipedia.glossary_of_chess",
     "note": "Bare 'opening' is leakage. phase_opening is exempted in soft check.",
     "added_session": 6},
    {"term": "middlegame", "category": "chess.phase", "severity": "medium",
     "definition": "Phase between opening and endgame.",
     "source": "wikipedia.glossary_of_chess",
     "note": "Bare term leaks. phase_middlegame is exempted.",
     "added_session": 6},
    {"term": "endgame",    "category": "chess.phase", "severity": "medium",
     "definition": "Final phase with few pieces remaining.",
     "source": "wikipedia.glossary_of_chess",
     "note": "Bare term leaks. phase_endgame is exempted.",
     "added_session": 6},
    {"term": "midgame",    "category": "chess.phase", "severity": "medium",
     "definition": "Synonym for middlegame.",
     "source": "wikipedia.glossary_of_chess", "added_session": 6},

    # ----- BOARD WORDS (low/medium — generic but suspicious) ---------------
    {"term": "board",  "category": "board.geometry", "severity": "low",
     "definition": "Generic playing surface; only flags if other terms also present.",
     "source": "domain_knowledge",
     "note": "Soft-only; common in non-game contexts.",
     "added_session": 6},
    {"term": "square", "category": "board.geometry", "severity": "low",
     "definition": "Generic geometric term; suspicious in cluster.",
     "source": "domain_knowledge",
     "note": "Soft-only; common geometric word.",
     "added_session": 6},
]


# ---------------------------------------------------------------------------
# Soft-check exemptions
# ---------------------------------------------------------------------------
# These compound strings contain glossary terms but are explicitly approved as
# abstract labels. The soft-check substring scan ignores any glossary term that
# appears ONLY as part of one of these compounds.
SOFT_CHECK_EXEMPTIONS: frozenset[str] = frozenset({
    # Phase indicators — `phase_` prefix is the abstraction marker
    "phase_opening",
    "phase_middlegame",
    "phase_endgame",
    "phase_opening_priority",
    "phase_middlegame_priority",
    "phase_endgame_priority",
    # Piece labels — `piece_` prefix is the abstraction marker
    # (no glossary term is fully embedded in any single piece_X label)
})


# ---------------------------------------------------------------------------
# Derived sets
# ---------------------------------------------------------------------------

def _extract_terms_by_severity(severities: tuple[str, ...]) -> frozenset[str]:
    return frozenset(
        entry["term"].lower()
        for entry in GLOSSARY
        if entry.get("severity") in severities
    )


# Hard check vocab: high + medium severity only (low is suggestive, would
# false-positive on common words like "board", "square", "tournament").
HARD_CHECK_VOCAB: frozenset[str] = _extract_terms_by_severity(("high", "medium"))

# Soft check vocab: all entries — used for substring scan with exemptions.
SOFT_CHECK_VOCAB: frozenset[str] = _extract_terms_by_severity(("high", "medium", "low"))


# ---------------------------------------------------------------------------
# Convenience accessors
# ---------------------------------------------------------------------------

def terms_in_category(category: str) -> list[str]:
    """Return all terms in a given category (e.g. 'chess.piece')."""
    return [entry["term"] for entry in GLOSSARY if entry.get("category") == category]


def categories() -> list[str]:
    """Return all distinct categories present in the glossary."""
    seen: set[str] = set()
    out: list[str] = []
    for entry in GLOSSARY:
        cat = entry.get("category", "")
        if cat and cat not in seen:
            seen.add(cat)
            out.append(cat)
    return sorted(out)


def stats() -> dict:
    """Summary stats — useful for SESSION_LOG entries."""
    by_severity: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for entry in GLOSSARY:
        sev = entry.get("severity", "unknown")
        cat = entry.get("category", "unknown")
        by_severity[sev] = by_severity.get(sev, 0) + 1
        by_category[cat] = by_category.get(cat, 0) + 1
    return {
        "total_terms": len(GLOSSARY),
        "by_severity": by_severity,
        "by_category": by_category,
        "hard_check_vocab_size": len(HARD_CHECK_VOCAB),
        "soft_check_vocab_size": len(SOFT_CHECK_VOCAB),
        "exemptions": len(SOFT_CHECK_EXEMPTIONS),
    }
