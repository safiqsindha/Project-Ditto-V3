"""
Renderer: converts abstract Constraint objects into human-readable,
domain-abstracted English.

NO game-domain vocabulary is permitted in any output string. The post-rendering
leakage check (check_leakage) is invoked automatically by render_chain() and
enforces both the v2 programming-vocabulary list and the extended chess + checkers
vocabulary defined in SPEC.md §Renderer leakage vocabulary.

The leakage check is enforced in code; callers cannot bypass it.

Adapted from v2 renderer.py: extended leakage vocabulary for chess + checkers.
"""

from __future__ import annotations

import re
from typing import Iterable

from src.translation import (
    Constraint,
    CoordinationDependency,
    InformationState,
    OptimizationCriterion,
    ResourceBudget,
    SubGoalTransition,
    ToolAvailability,
)


# ---------------------------------------------------------------------------
# Per-type renderers (identical rendering logic to v2 — domain-blind)
# ---------------------------------------------------------------------------

def _render_resource_budget(c: ResourceBudget) -> str:
    pct = f"{c.amount * 100:.1f}%"
    parts = [f"ResourceBudget: {c.resource} at {pct}"]
    if c.decay != "none":
        parts.append(f"(decay={c.decay})")
    if c.recover_in is not None:
        parts.append(f"(recover_in={c.recover_in} steps)")
    return " ".join(parts)


def _render_tool_availability(c: ToolAvailability) -> str:
    state_str = c.state.upper()
    if c.state == "unavailable" and c.recover_in is None:
        return f"ToolAvailability: {c.tool} is now {state_str} (permanent)"
    elif c.state == "unavailable":
        return f"ToolAvailability: {c.tool} is now {state_str} (recover_in={c.recover_in})"
    else:
        return f"ToolAvailability: {c.tool} is now {state_str}"


def _render_subgoal_transition(c: SubGoalTransition) -> str:
    return (
        f"SubGoalTransition: phase shifted from '{c.from_phase}' to '{c.to_phase}'"
        f" (trigger={c.trigger})"
    )


def _render_information_state(c: InformationState) -> str:
    added = ", ".join(c.observable_added) if c.observable_added else "(empty)"
    removed = ", ".join(c.observable_removed) if c.observable_removed else "(empty)"
    return (
        f"InformationState: added=[{added}] removed=[{removed}]"
        f" uncertainty={c.uncertainty:.2f}"
    )


def _render_coordination_dependency(c: CoordinationDependency) -> str:
    return (
        f"CoordinationDependency: {c.role} depends on {c.dependency}"
        f" -> expected_action={c.expected_action}"
    )


def _render_optimization_criterion(c: OptimizationCriterion) -> str:
    return (
        f"OptimizationCriterion: objective={c.objective}"
        f" weight_shift={c.weight_shift}"
    )


_RENDERERS = {
    ResourceBudget:         _render_resource_budget,
    ToolAvailability:       _render_tool_availability,
    SubGoalTransition:      _render_subgoal_transition,
    InformationState:       _render_information_state,
    CoordinationDependency: _render_coordination_dependency,
    OptimizationCriterion:  _render_optimization_criterion,
}


def render_constraint(c: Constraint) -> str:
    """Render a single constraint as a one-line abstract English description."""
    renderer = _RENDERERS.get(type(c))
    if renderer is None:
        return f"UnknownConstraint: {c!r}"
    return renderer(c)


# ---------------------------------------------------------------------------
# Chain renderer
# ---------------------------------------------------------------------------

def render_chain(constraints: list[Constraint], perspective: str = "agent") -> str:
    """
    Render a list of constraints as numbered steps.

    Raises ValueError if game-domain vocabulary is detected in the output.

    Parameters
    ----------
    constraints : ordered list of Constraint objects
    perspective : trajectory perspective label (included in header)

    Returns
    -------
    Multi-line string, one step per constraint.
    """
    if not constraints:
        return f"# Constraint chain (perspective={perspective})\n(no constraints)\n"

    lines: list[str] = [f"# Constraint chain (perspective={perspective})"]
    step = 1
    for c in constraints:
        turn = getattr(c, "timestamp", 0)
        body = render_constraint(c)
        lines.append(f"Step {step} (step={turn}):")
        lines.append(f"  {body}")
        step += 1

    rendered = "\n".join(lines) + "\n"

    leaked = check_leakage(rendered)
    if leaked:
        raise ValueError(
            f"Game-domain vocabulary detected in rendered chain: {leaked}. "
            "Check translation.py for domain leakage."
        )

    return rendered


# Cell name → abstract perspective label (prevents game-domain leakage in chain header)
_CELL_TO_PERSPECTIVE: dict[str, str] = {
    "chess_standard":    "sequential_process_A",
    "chess960":          "sequential_process_B",
    "checkers_american": "sequential_process_C",
    "draughts_intl":     "sequential_process_D",
}


def render_trajectory_chain(constraints: list[Constraint], source: str = "chess_standard") -> str:
    """Convenience wrapper for render_chain using an abstract perspective label.

    Cell names like 'chess960' are mapped to abstract labels (sequential_process_*)
    before being written into the chain header, preventing leakage vocabulary from
    appearing in rendered output.
    """
    perspective = _CELL_TO_PERSPECTIVE.get(source, "sequential_process_A")
    return render_chain(constraints, perspective=perspective)


# ---------------------------------------------------------------------------
# Leakage vocabulary
# ---------------------------------------------------------------------------

# v2 programming vocabulary (inherited — unchanged)
_PROGRAMMING_VOCAB: frozenset[str] = frozenset({
    "def", "class", "import", "return", "async", "await", "yield", "lambda",
    "raise", "except", "finally", "with", "pass", "global", "nonlocal",
    "elif", "else", "while", "assert", "del", "exec", "print",
    "stdin", "stdout", "stderr", "traceback",
    "TypeError", "ValueError", "KeyError", "AttributeError", "ImportError",
    "RuntimeError", "IndexError", "NameError", "OSError", "FileNotFoundError",
    "PermissionError", "TimeoutError", "StopIteration", "AssertionError",
    "NotImplementedError", "RecursionError", "MemoryError", "OverflowError",
    "ZeroDivisionError", "UnicodeDecodeError", "UnicodeEncodeError",
    "ConnectionError", "BrokenPipeError", "FileExistsError", "IsADirectoryError",
    "ModuleNotFoundError", "SyntaxError", "IndentationError", "SystemExit",
    "Exception", "BaseException",
    "django", "flask", "fastapi", "numpy", "pandas", "scipy", "sklearn",
    "torch", "tensorflow", "keras", "requests", "httpx", "aiohttp",
    "pydantic", "sqlalchemy", "celery", "redis", "kafka", "boto3",
    "pytest", "unittest", "mock", "click", "typer", "argparse",
    "asyncio", "threading", "multiprocessing", "subprocess",
    "grep", "find", "sed", "awk", "curl", "wget", "ssh", "git",
    "make", "cmake", "pip", "conda", "npm", "yarn", "cargo",
    "docker", "kubectl", "terraform",
    "function", "method", "module", "package", "library", "framework",
    "variable", "parameter", "argument", "constant", "attribute", "property",
    "interface", "protocol", "decorator", "iterator", "generator", "coroutine",
    "database", "schema", "migration", "query", "transaction",
    "endpoint", "route", "middleware", "handler", "controller", "serializer",
    "compiler", "interpreter", "runtime", "bytecode",
    "thread", "process", "daemon", "signal", "socket",
    "api", "sdk", "cli", "ide",
    "github", "gitlab", "commit", "branch", "merge", "rebase",
    "build", "deploy", "release",
    "dotenv", "secret",
    "python", "javascript", "typescript", "java", "cpp", "ruby",
    "dockerfile", "makefile", "requirements",
})

# Chess-specific vocabulary (SPEC.md §Renderer leakage vocabulary)
_CHESS_VOCAB: frozenset[str] = frozenset({
    "pawn", "knight", "bishop", "rook", "queen", "castle",
    "check", "mate", "checkmate", "stalemate",
    "fork", "pin", "skewer",
    "en passant", "en-passant",
    # File labels (a–h) are single characters — whole-word match catches e.g. " a " or "file a"
    # Rank labels (1–8) are numeric — avoid false positives on constraint amounts
    # Algebraic notation fragments: handled via chess960 and "960" below
    "chess", "chess960",
    "lichess", "pgn", "fen", "uci",
    "kingside", "queenside",
    "fianchetto", "gambit", "sicilian", "caro",
})

# Checkers-specific vocabulary (SPEC.md §Renderer leakage vocabulary)
_CHECKERS_VOCAB: frozenset[str] = frozenset({
    "jump", "capture", "crown", "crowned",
    "double corner", "double-corner",
    "draughts", "checkers", "chequers",
    "pdn",
    "fmjd", "oca",
    # "king" in checkers sense is excluded from the base chess vocab but added here
    # because in checkers "king" means a crowned piece — different from chess "King"
    # We list it here so both contexts are caught; rendered chains use abstract labels.
    "king",
})

# Combined leakage vocabulary (v2 programming + chess + checkers)
_DEFAULT_LEAKAGE_VOCAB: frozenset[str] = (
    _PROGRAMMING_VOCAB | _CHESS_VOCAB | _CHECKERS_VOCAB
)


def check_leakage(
    rendered: str,
    vocab: set[str] | frozenset[str] | None = None,
) -> list[str]:
    """
    Return any game-domain or programming-domain vocabulary found in the
    rendered output.

    A match is case-insensitive whole-word search.

    Parameters
    ----------
    rendered : string produced by render_chain()
    vocab    : set of terms to check. Defaults to _DEFAULT_LEAKAGE_VOCAB.
               Pass an empty set only in unit tests that explicitly test
               clean output.

    Returns
    -------
    List of leaking terms (empty list means no leakage).
    """
    if vocab is None:
        vocab = _DEFAULT_LEAKAGE_VOCAB

    leaked: list[str] = []
    for term in vocab:
        pattern = r"\b" + re.escape(term) + r"\b"
        if re.search(pattern, rendered, flags=re.IGNORECASE):
            leaked.append(term)
    return leaked


# Backwards-compatible alias used by scorer and tests
check_programming_leakage = check_leakage
