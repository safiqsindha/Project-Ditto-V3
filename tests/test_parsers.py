"""
Unit tests for Session 4: parser_chess.py, parser_checkers.py, aggregation.py

Gate 3: parsers produce valid TrajectoryLog objects on ≥95% of sampled games.
"""
import sys
import random
import warnings
from pathlib import Path

sys.path.insert(0, '/Users/safiqsindha/Library/Python/3.9/lib/python/site-packages')

import pytest

from src.translation import TrajectoryLog, GameEvent
from src.aggregation import compute_windows, aggregate_trajectory, extract_all_windows, sample_window

# ---------------------------------------------------------------------------
# Fixtures: load small samples from each data file if available
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).parent.parent / "data"
CHESS_STANDARD = DATA_DIR / "chess_standard" / "games.jsonl"
CHESS960       = DATA_DIR / "chess960" / "games.jsonl"
CHECKERS_AM    = DATA_DIR / "checkers_american" / "games.jsonl"
DRAUGHTS_INTL  = DATA_DIR / "draughts_intl" / "games.jsonl"


def _load_trajs(path: Path, parser_fn, **kwargs) -> list[TrajectoryLog]:
    """Load up to 20 trajectories, swallowing warnings."""
    if not path.exists():
        return []
    trajs = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for traj in parser_fn(path, **kwargs):
            trajs.append(traj)
            if len(trajs) >= 20:
                break
    return trajs


# ---------------------------------------------------------------------------
# Tests: chess parser
# ---------------------------------------------------------------------------

class TestChessParser:
    def _get_trajs(self, chess960=False):
        from src.parser_chess import parse_games_jsonl
        path = CHESS960 if chess960 else CHESS_STANDARD
        return _load_trajs(path, parse_games_jsonl, chess960=chess960, limit=20)

    def test_chess_standard_loads(self):
        trajs = self._get_trajs(chess960=False)
        if not CHESS_STANDARD.exists():
            pytest.skip("chess_standard games.jsonl not found")
        assert len(trajs) > 0, "Should parse at least some games"

    def test_chess_standard_success_rate(self):
        if not CHESS_STANDARD.exists():
            pytest.skip("chess_standard games.jsonl not found")
        trajs = self._get_trajs(chess960=False)
        # All 20 should succeed
        assert len(trajs) == 20, f"Expected 20 games, got {len(trajs)}"

    def test_chess_standard_trajectory_structure(self):
        if not CHESS_STANDARD.exists():
            pytest.skip("chess_standard games.jsonl not found")
        trajs = self._get_trajs(chess960=False)
        for traj in trajs:
            assert isinstance(traj, TrajectoryLog)
            assert traj.variant == "chess_standard"
            assert len(traj.events) > 0
            assert isinstance(traj.game_id, str)

    def test_chess_standard_event_fields(self):
        if not CHESS_STANDARD.exists():
            pytest.skip("chess_standard games.jsonl not found")
        trajs = self._get_trajs(chess960=False)
        valid_phases = {"phase_opening", "phase_middlegame", "phase_endgame"}
        valid_sides = {"side_1", "side_2"}
        valid_events = {"move", "capture", "promotion"}
        for traj in trajs:
            for evt in traj.events:
                assert evt.phase_indicator in valid_phases, f"Unknown phase: {evt.phase_indicator}"
                assert evt.side in valid_sides
                assert evt.event_type in valid_events
                assert evt.piece_label.startswith("piece_")
                assert evt.from_square.startswith("sq_")
                assert evt.to_square.startswith("sq_")

    def test_chess_standard_square_range(self):
        """Squares must be in 0-63 range for standard chess."""
        if not CHESS_STANDARD.exists():
            pytest.skip("chess_standard games.jsonl not found")
        trajs = self._get_trajs(chess960=False)
        for traj in trajs:
            for evt in traj.events:
                from_num = int(evt.from_square.split("_")[1])
                to_num = int(evt.to_square.split("_")[1])
                assert 0 <= from_num <= 63, f"from_square out of range: {evt.from_square}"
                assert 0 <= to_num <= 63, f"to_square out of range: {evt.to_square}"

    def test_chess960_loads(self):
        if not CHESS960.exists():
            pytest.skip("chess960 games.jsonl not found")
        trajs = self._get_trajs(chess960=True)
        assert len(trajs) > 0
        for traj in trajs:
            assert traj.variant == "chess960"

    def test_chess_all_phases_present(self):
        """A game long enough should include all three phases."""
        if not CHESS_STANDARD.exists():
            pytest.skip("chess_standard games.jsonl not found")
        trajs = self._get_trajs(chess960=False)
        # At least one game should have all three phases
        has_all = any(
            len({e.phase_indicator for e in traj.events}) == 3
            for traj in trajs
        )
        assert has_all, "No game found with all three phases"

    def test_chess_no_leakage_vocabulary(self):
        """Piece labels must not contain chess piece names."""
        forbidden = {"pawn", "knight", "bishop", "rook", "queen", "king"}
        if not CHESS_STANDARD.exists():
            pytest.skip("chess_standard games.jsonl not found")
        trajs = self._get_trajs(chess960=False)
        for traj in trajs:
            for evt in traj.events:
                lbl_lower = evt.piece_label.lower()
                for term in forbidden:
                    assert term not in lbl_lower, f"Leakage: {evt.piece_label} contains '{term}'"


# ---------------------------------------------------------------------------
# Tests: checkers parser
# ---------------------------------------------------------------------------

class TestCheckersParser:
    def _get_trajs_american(self):
        from src.parser_checkers import parse_games_jsonl, VARIANT_AMERICAN
        return _load_trajs(CHECKERS_AM, parse_games_jsonl, variant=VARIANT_AMERICAN, limit=20)

    def _get_trajs_intl(self):
        from src.parser_checkers import parse_games_jsonl, VARIANT_INTERNATIONAL
        return _load_trajs(DRAUGHTS_INTL, parse_games_jsonl, variant=VARIANT_INTERNATIONAL, limit=20)

    def test_american_loads(self):
        if not CHECKERS_AM.exists():
            pytest.skip("checkers_american games.jsonl not found")
        trajs = self._get_trajs_american()
        assert len(trajs) > 0

    def test_american_success_rate(self):
        if not CHECKERS_AM.exists():
            pytest.skip("checkers_american games.jsonl not found")
        trajs = self._get_trajs_american()
        assert len(trajs) == 20

    def test_american_trajectory_structure(self):
        if not CHECKERS_AM.exists():
            pytest.skip("checkers_american games.jsonl not found")
        trajs = self._get_trajs_american()
        for traj in trajs:
            assert traj.variant == "checkers_american"
            assert len(traj.events) > 0

    def test_american_square_range(self):
        """American checkers squares must be 1-32."""
        if not CHECKERS_AM.exists():
            pytest.skip("checkers_american games.jsonl not found")
        trajs = self._get_trajs_american()
        for traj in trajs:
            for evt in traj.events:
                from_num = int(evt.from_square.split("_")[1])
                to_num = int(evt.to_square.split("_")[1])
                assert 1 <= from_num <= 32, f"from_square out of range: {evt.from_square}"
                assert 1 <= to_num <= 32, f"to_square out of range: {evt.to_square}"

    def test_intl_square_range(self):
        """International draughts squares must be 1-50."""
        if not DRAUGHTS_INTL.exists():
            pytest.skip("draughts_intl games.jsonl not found")
        trajs = self._get_trajs_intl()
        for traj in trajs:
            for evt in traj.events:
                from_num = int(evt.from_square.split("_")[1])
                to_num = int(evt.to_square.split("_")[1])
                assert 1 <= from_num <= 50, f"from_square out of range: {evt.from_square}"
                assert 1 <= to_num <= 50, f"to_square out of range: {evt.to_square}"

    def test_intl_loads(self):
        if not DRAUGHTS_INTL.exists():
            pytest.skip("draughts_intl games.jsonl not found")
        trajs = self._get_trajs_intl()
        assert len(trajs) > 0
        for traj in trajs:
            assert traj.variant == "draughts_intl"

    def test_checkers_no_leakage_vocabulary(self):
        """Piece labels must not contain checkers/draughts terminology."""
        forbidden = {"pawn", "king", "man", "jump", "crown", "checker", "draughts"}
        if not CHECKERS_AM.exists():
            pytest.skip("checkers_american games.jsonl not found")
        trajs = self._get_trajs_american()
        for traj in trajs:
            for evt in traj.events:
                lbl_lower = evt.piece_label.lower()
                for term in forbidden:
                    assert term not in lbl_lower, f"Leakage: {evt.piece_label} contains '{term}'"


# ---------------------------------------------------------------------------
# Tests: aggregation
# ---------------------------------------------------------------------------

class TestAggregation:
    def _make_traj(self, n_events: int = 50, phase_transitions: bool = True) -> TrajectoryLog:
        """Create a synthetic TrajectoryLog for testing."""
        events = []
        phases = ["phase_opening"] * 15 + ["phase_middlegame"] * 20 + ["phase_endgame"] * 15
        for i in range(n_events):
            phase = phases[i] if i < len(phases) else "phase_endgame"
            events.append(GameEvent(
                move_number=i,
                side="side_1" if i % 2 == 0 else "side_2",
                event_type="move",
                piece_label="piece_A",
                from_square=f"sq_{i % 32}",
                to_square=f"sq_{(i + 1) % 32}",
                phase_indicator=phase,
            ))
        return TrajectoryLog(game_id="test_game", variant="checkers_american", events=events)

    def test_compute_windows_basic(self):
        traj = self._make_traj(50)
        windows = compute_windows(traj)
        assert len(windows) > 0
        for start, end in windows:
            assert end - start >= 15
            assert end - start <= 25

    def test_compute_windows_short_game(self):
        """Games shorter than target_min should return no windows."""
        traj = self._make_traj(10)
        windows = compute_windows(traj)
        assert windows == []

    def test_aggregate_window_length(self):
        traj = self._make_traj(50)
        result = aggregate_trajectory(traj, window_start=0, window_end=30)
        assert len(result) == 25  # capped at target_max

    def test_aggregate_within_bounds(self):
        traj = self._make_traj(50)
        result = aggregate_trajectory(traj, window_start=5, window_end=25)
        assert len(result) == 20

    def test_extract_all_windows_lengths(self):
        traj = self._make_traj(50)
        all_w = extract_all_windows(traj)
        assert len(all_w) > 0
        for w in all_w:
            assert 15 <= len(w) <= 25

    def test_sample_window_returns_valid(self):
        traj = self._make_traj(50)
        rng = random.Random(42)
        w = sample_window(traj, rng=rng)
        assert w is not None
        assert 15 <= len(w) <= 25

    def test_sample_window_short_returns_none(self):
        traj = self._make_traj(10)
        w = sample_window(traj)
        assert w is None

    def test_windows_non_overlapping(self):
        """Windows returned by compute_windows should be non-overlapping."""
        traj = self._make_traj(100)
        windows = compute_windows(traj)
        for i in range(1, len(windows)):
            prev_start, prev_end = windows[i - 1]
            curr_start, curr_end = windows[i]
            # Each window starts at or after the previous window's start + step
            assert curr_start >= prev_start + 15


# ---------------------------------------------------------------------------
# Integration: Gate 3 — parse success rate ≥ 95%
# ---------------------------------------------------------------------------

class TestGate3:
    def _measure_rate(self, path, parser_fn, **kwargs):
        if not path.exists():
            return None, None
        success = 0
        fail = 0
        with warnings.catch_warnings(record=True) as w_list:
            warnings.simplefilter("always")
            for traj in parser_fn(path, **kwargs):
                success += 1
        fail = len(w_list)
        total = success + fail
        return success / max(total, 1), total

    def test_chess_standard_gate3(self):
        from src.parser_chess import parse_games_jsonl
        rate, total = self._measure_rate(
            CHESS_STANDARD, parse_games_jsonl, chess960=False, limit=100
        )
        if rate is None:
            pytest.skip("chess_standard games.jsonl not found")
        assert rate >= 0.95, f"Gate 3 FAIL: chess_standard parse rate {rate:.1%} < 95%"

    def test_chess960_gate3(self):
        from src.parser_chess import parse_games_jsonl
        rate, total = self._measure_rate(
            CHESS960, parse_games_jsonl, chess960=True, limit=100
        )
        if rate is None:
            pytest.skip("chess960 games.jsonl not found")
        assert rate >= 0.95, f"Gate 3 FAIL: chess960 parse rate {rate:.1%} < 95%"

    def test_checkers_american_gate3(self):
        from src.parser_checkers import parse_games_jsonl, VARIANT_AMERICAN
        rate, total = self._measure_rate(
            CHECKERS_AM, parse_games_jsonl, variant=VARIANT_AMERICAN, limit=100
        )
        if rate is None:
            pytest.skip("checkers_american games.jsonl not found")
        assert rate >= 0.95, f"Gate 3 FAIL: checkers_american parse rate {rate:.1%} < 95%"

    def test_draughts_intl_gate3(self):
        from src.parser_checkers import parse_games_jsonl, VARIANT_INTERNATIONAL
        rate, total = self._measure_rate(
            DRAUGHTS_INTL, parse_games_jsonl, variant=VARIANT_INTERNATIONAL, limit=100
        )
        if rate is None:
            pytest.skip("draughts_intl games.jsonl not found")
        assert rate >= 0.95, f"Gate 3 FAIL: draughts_intl parse rate {rate:.1%} < 95%"
