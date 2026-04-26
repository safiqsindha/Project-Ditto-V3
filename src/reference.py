"""
Reference action distribution lookup table for objective scoring (Layer 1).

Maps (trajectory state signature) → (empirical action distribution from real
game trajectories). Used at evaluation time to score whether a model's proposed
action matches what real players did in the same state.

One ReferenceDistribution is built per data source (chess_standard, chess960,
checkers_american, draughts_intl) — see Session 8.

v3 adaptation: active_pair = (current_phase, last_move_type)
  current_phase:  "opening" | "middlegame" | "endgame"
  last_move_type: constraint type name of the most recent constraint
                  (e.g. "ResourceBudget", "SubGoalTransition", ...)

Backoff levels (same as v1/v2):
  Level 0 (full):   all components
  Level 1:          drop last_move_type
  Level 2:          drop last_move_type + resource_bracket
  Level 3 (max):    current_phase only

Coverage target: ≥ 90% non-max-backoff (matching v2 standard — SPEC §6).
"""

from __future__ import annotations

import json
import pickle
import random
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Entity extraction (domain-blind — same interface as v2)
# ---------------------------------------------------------------------------

def extract_entity_from_constraint(constraint: dict) -> str | None:
    """Return the key abstract entity label for a constraint dict, lowercased."""
    ctype = constraint.get("type", "")
    if ctype == "ToolAvailability":
        tool = constraint.get("tool", "")
        return tool.lower() if tool else None
    if ctype == "InformationState":
        obs = constraint.get("observable_added", [])
        return obs[0].lower() if obs else None
    if ctype == "SubGoalTransition":
        return constraint.get("to_phase", "").lower() or None
    if ctype == "ResourceBudget":
        return constraint.get("resource", "").lower() or None
    if ctype == "CoordinationDependency":
        dep = constraint.get("dependency", "")
        return dep.lower() if dep else None
    if ctype == "OptimizationCriterion":
        obj = constraint.get("objective", "")
        return obj.lower() if obj else None
    return None


# ---------------------------------------------------------------------------
# Resource bucketing helper (domain-blind — same as v2)
# ---------------------------------------------------------------------------

def _resource_bracket(amount: float) -> int:
    if amount <= 0.0:
        return 0
    if amount < 0.25:
        return 1
    if amount < 0.50:
        return 2
    if amount < 0.75:
        return 3
    return 4


# ---------------------------------------------------------------------------
# State signature
# ---------------------------------------------------------------------------

def extract_state_signature(
    constraints: list[dict],
    cutoff_k: int,
    backoff_level: int = 0,
) -> tuple:
    """
    Build a hashable state signature from the constraint sequence up to cutoff_k.

    v3 active_pair: (current_phase, last_move_type)
      current_phase  — derived from the most recent SubGoalTransition.to_phase
                       (defaults to "opening" if none seen yet)
      last_move_type — constraint type name of the constraint at position cutoff_k - 1

    Backoff levels reduce specificity when exact matches are sparse:
      0: (current_phase, last_move_type, resource_bracket, entity_label)
      1: (current_phase, last_move_type, resource_bracket)
      2: (current_phase, last_move_type)
      3: (current_phase,)
    """
    # Defensive default: return a shape consistent with the requested level.
    # Use "phase_opening" (with prefix) to match the actual data format —
    # bare "opening" would fragment state-sig keys for chains where no SGT
    # is in the prefix window vs. chains where one is.
    if not constraints or cutoff_k <= 0:
        if backoff_level == 0:
            return ("phase_opening", "unknown", 4, "unknown")
        if backoff_level == 1:
            return ("phase_opening", "unknown", 4)
        if backoff_level == 2:
            return ("phase_opening", "unknown")
        return ("phase_opening",)

    window = constraints[:cutoff_k]

    # current_phase: last SubGoalTransition.to_phase seen.
    # Default "phase_opening" (matches data format from chain generation).
    current_phase = "phase_opening"
    for c in reversed(window):
        if c.get("type") == "SubGoalTransition":
            current_phase = c.get("to_phase", "phase_opening")
            break

    # last_move_type: type of the constraint at the cutoff position
    last_constraint = window[-1]
    last_move_type = last_constraint.get("type", "unknown")

    # resource_bracket: bracket of the most recent ResourceBudget (material proxy)
    resource_bracket = 4  # default: full
    for c in reversed(window):
        if c.get("type") == "ResourceBudget":
            resource_bracket = _resource_bracket(c.get("amount", 1.0))
            break

    # entity_label: entity of the cutoff constraint
    entity_label = extract_entity_from_constraint(last_constraint) or "unknown"

    if backoff_level == 0:
        return (current_phase, last_move_type, resource_bracket, entity_label)
    elif backoff_level == 1:
        return (current_phase, last_move_type, resource_bracket)
    elif backoff_level == 2:
        return (current_phase, last_move_type)
    else:
        return (current_phase,)


# ---------------------------------------------------------------------------
# Reference distribution
# ---------------------------------------------------------------------------

@dataclass
class ReferenceDistribution:
    """
    Empirical action distribution over game states.

    Built from real game trajectories during Session 8.
    Queried at evaluation time to produce reference actions for scoring.
    """
    source: str
    counts: dict[tuple, dict[str, int]]   # state_sig → {action: count}
    total_chains: int = 0
    coverage_stats: dict[str, Any] | None = None

    def get_top_k_actions(
        self,
        state_sig: tuple,
        k: int = 3,
        rng: random.Random | None = None,
    ) -> list[str]:
        """
        Return the top-k most common actions for a state signature.

        Falls back through backoff levels if the exact signature has no data.
        Returns empty list if no data found at any backoff level.
        """
        dist = self.counts.get(state_sig, {})
        if dist:
            sorted_actions = sorted(dist.items(), key=lambda x: -x[1])
            return [a for a, _ in sorted_actions[:k]]
        return []

    def lookup_with_backoff(
        self,
        constraints: list[dict],
        cutoff_k: int,
        k: int = 3,
    ) -> tuple[list[str], int]:
        """
        Look up top-k actions with automatic backoff.

        Returns (actions, backoff_level_used).
        """
        for level in range(4):
            sig = extract_state_signature(constraints, cutoff_k, backoff_level=level)
            actions = self.get_top_k_actions(sig, k=k)
            if actions:
                return actions, level
        return [], 3

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, path: Path) -> "ReferenceDistribution":
        with open(path, "rb") as f:
            return pickle.load(f)

    @classmethod
    def build_from_chains(cls, chains: list[dict], source: str) -> "ReferenceDistribution":
        """
        Build a reference distribution from a list of real chain dicts.

        Per SPEC_v1.1 Amendment 2: focal_action is RECOMPUTED on-the-fly
        from constraints[cutoff_k] (the prediction target — first UNSHOWN
        constraint). The chain JSONLs' stored 'focal_action' field contains
        the OLD off-by-one value (entity at constraints[cutoff_k - 1]) and
        is intentionally NOT read here. Stored field is retained on disk
        as a deprecated audit trail.

        Bug 4 fix (audit, 2026-04-25): counts are populated at ALL backoff
        levels (0, 1, 2, 3), not just level 0. The pre-fix build only stored
        counts at level 0, so `lookup_with_backoff` at levels 1-3 returned
        empty (key shape mismatch — 4-tuple keys vs 3-tuple lookups). This
        caused 32% of pairs in Phase 1 partial scoring to be silently dropped
        when the shuffled chain's state-sig had no level-0 match. Populating
        all levels lets backoff actually engage, broadening the test
        population and avoiding the selection bias that caused the first
        partial scoring to show a counter-intuitive negative gap.

        Each chain contributes to 4 sigs (one per level), each pointing to
        the same focal_action. Distributions are preserved (proportions are
        what matter for top-k); absolute counts inflate by ~4× total but
        per-sig top-k orderings are correct.

        Each chain must have 'constraints' (list of dicts) and 'cutoff_k'.
        """
        counts: dict[tuple, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        total = 0

        for chain in chains:
            constraints = chain.get("constraints", [])
            if not constraints:
                continue
            # Defensive cutoff handling: clamp to valid range. Fallback to
            # length // 2 (matches chain generation default) if missing.
            cutoff_k = chain.get("cutoff_k") or max(1, len(constraints) // 2)
            # Need cutoff_k < len(constraints) so constraints[cutoff_k] exists
            # as the prediction target (post-Amendment-2 semantics).
            if cutoff_k <= 0 or cutoff_k >= len(constraints):
                continue

            # SPEC_v1.1 Amendment 2: focal_action = entity at constraints[cutoff_k]
            # (NOT chain['focal_action'], which holds the deprecated cutoff_k - 1
            # interpretation from chain generation in Session 7).
            focal_action = extract_entity_from_constraint(constraints[cutoff_k])
            if not focal_action:
                continue

            # Bug 4 fix: populate counts at ALL backoff levels so
            # lookup_with_backoff can find data at any level the caller hits.
            for level in range(4):
                sig = extract_state_signature(constraints, cutoff_k, backoff_level=level)
                counts[sig][focal_action] += 1
            total += 1

        # Convert defaultdicts to regular dicts for pickling
        regular_counts = {k: dict(v) for k, v in counts.items()}

        dist = cls(source=source, counts=regular_counts, total_chains=total)
        return dist

    def check_coverage(
        self,
        chains: list[dict],
        target: float = 0.9,
    ) -> dict[str, Any]:
        """
        Check what fraction of chain state signatures have a level-0 or level-1
        match in the distribution (non-max-backoff coverage).

        target: minimum acceptable coverage fraction (0.9 per SPEC).
        """
        level_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        total = 0

        for chain in chains:
            constraints = chain.get("constraints", [])
            if not constraints:
                continue
            cutoff_k = chain.get("cutoff_k") or max(1, len(constraints) // 2)
            # Per SPEC_v1.1 Amendment 2: cutoff_k indexes prediction target
            # constraints[cutoff_k]; need < len for it to exist.
            if cutoff_k <= 0 or cutoff_k >= len(constraints):
                continue
            _, level = self.lookup_with_backoff(constraints, cutoff_k)
            level_counts[level] += 1
            total += 1

        if total == 0:
            return {"error": "no chains", "coverage": 0.0, "passes": False}

        non_max = sum(v for k, v in level_counts.items() if k < 3)
        coverage = non_max / total

        return {
            "total_chains": total,
            "level_counts": level_counts,
            "non_max_backoff_fraction": round(coverage, 4),
            "target": target,
            "passes": coverage >= target,
        }


# ---------------------------------------------------------------------------
# CLI entry point (build and check subcommands)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(prog="src.reference")
    sub = parser.add_subparsers(dest="cmd")

    # build-raw subcommand
    build_parser = sub.add_parser("build-raw")
    build_parser.add_argument("--source", required=True)
    build_parser.add_argument("--raw", type=Path, required=True,
                              help="Path to games.jsonl (real chains JSONL)")
    build_parser.add_argument("--out", type=Path, required=True)

    # check subcommand
    check_parser = sub.add_parser("check")
    check_parser.add_argument("--dist", type=Path, required=True)
    check_parser.add_argument("--chains", type=Path, required=True,
                              help="Directory of real chain JSONL files")
    check_parser.add_argument("--target", type=float, default=0.9)

    args = parser.parse_args()

    if args.cmd == "build-raw":
        chains = []
        with open(args.raw) as f:
            for line in f:
                line = line.strip()
                if line:
                    chains.append(json.loads(line))
        dist = ReferenceDistribution.build_from_chains(chains, source=args.source)
        dist.save(args.out)
        print(f"Built reference distribution: {len(dist.counts)} unique states, "
              f"{dist.total_chains} chains → {args.out}")

    elif args.cmd == "check":
        dist = ReferenceDistribution.load(args.dist)
        chains = []
        for p in sorted(Path(args.chains).glob("*.jsonl")):
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        chains.append(json.loads(line))
        result = dist.check_coverage(chains, target=args.target)
        print(json.dumps(result, indent=2))
        if not result.get("passes"):
            sys.exit(1)

    else:
        parser.print_help()
